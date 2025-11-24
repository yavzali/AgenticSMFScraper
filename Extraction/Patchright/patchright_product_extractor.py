"""
Patchright Tower - Product Extractor
Extract single product data using Patchright + Gemini Vision with DOM collaboration

Extracted from: Shared/playwright_agent.py (product logic, lines 172-213, 674-895)
Target: <900 lines
"""

# Add shared path for imports
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../../Shared"))

import asyncio
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from patchright.async_api import async_playwright
import google.generativeai as genai
from dotenv import load_dotenv
import logging

from logger_config import setup_logging
from patchright_verification import PatchrightVerificationHandler
from patchright_retailer_strategies import PatchrightRetailerStrategies
from patchright_dom_validator import PatchrightDOMValidator

logger = setup_logging(__name__)

# GLOBAL KILL SWITCH - Set to False to disable ALL enhancements
ENABLE_ANTI_SCRAPING_ENHANCEMENTS = True

# If disabled, system falls back to original behavior
# Use this for emergency rollback if enhancements cause issues


@dataclass
class ProductData:
    """Product data structure"""
    title: str = ""
    brand: str = ""
    price: float = 0.0
    original_price: Optional[float] = None
    sale_status: str = "regular"
    availability: str = "in_stock"
    description: str = ""
    sizes: List[str] = field(default_factory=list)
    colors: List[str] = field(default_factory=list)
    materials: str = ""
    care_instructions: str = ""
    image_urls: List[str] = field(default_factory=list)
    product_code: str = ""
    clothing_type: str = ""


@dataclass
class ExtractionResult:
    """Extraction result wrapper"""
    success: bool
    data: Dict
    method_used: str
    processing_time: float
    warnings: List[str]
    errors: List[str]


class PatchrightProductExtractor:
    """
    Extract single product data with Gemini→DOM collaboration
    
    5-Step Process (from v1.0):
    1. Gemini extracts ALL data from screenshots (primary)
    2. Gemini analyzes page structure (provides visual hints for DOM)
    3. DOM fills gaps & validates (guided by Gemini hints)
    4. Merge results (Gemini primary, DOM supplements)
    5. Learn from successful extraction (pattern recording)
    
    Key Features:
    - Multi-region screenshots (header, mid, footer)
    - Gemini Vision for visual analysis
    - DOM extraction guided by Gemini
    - Validation and cross-checking
    - Pattern learning
    """
    
    def __init__(self, config: Dict = None):
        """Initialize product extractor"""
        # Load environment
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.join(script_dir, '../..')
        env_path = os.path.join(project_root, '.env')
        load_dotenv(env_path, override=True)
        
        # Load config
        if config is None:
            config_path = os.path.join(project_root, 'Shared/config.json')
            import json
            with open(config_path, 'r') as f:
                config = json.load(f)
        
        self.config = config
        self.strategies = PatchrightRetailerStrategies()
        self.max_retries = 2
        
        # Browser state
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        
        # Setup Gemini
        self._setup_gemini()
        
        logger.info("✅ Patchright Product Extractor initialized")
    
    def _setup_gemini(self):
        """Initialize Gemini Vision"""
        try:
            google_api_key = os.getenv("GOOGLE_API_KEY") or \
                           self.config.get("llm_providers", {}).get("google", {}).get("api_key")
            
            if not google_api_key:
                raise ValueError("Google API key not found")
            
            genai.configure(api_key=google_api_key)
            logger.info("✅ Gemini Vision initialized")
        except Exception as e:
            logger.error(f"Failed to setup Gemini: {e}")
            raise
    
    async def extract_product(self, url: str, retailer: str) -> ExtractionResult:
        """
        Main extraction method
        
        Args:
            url: Product page URL
            retailer: Retailer name
            
        Returns:
            ExtractionResult with success status and data
        """
        start_time = time.time()
        logger.info(f"🎭 Starting Patchright product extraction for {retailer}: {url}")
        
        try:
            # Setup browser
            await self._setup_stealth_browser()
            
            # Extract with retry logic
            result = await self._extract_with_retry(url, retailer)
            
            processing_time = time.time() - start_time
            logger.info(f"✅ Patchright extraction completed in {processing_time:.1f}s")
            
            # Convert ProductData to dict and map availability → stock_status
            data_dict = result.__dict__
            # Map 'availability' to 'stock_status' for consistency with Markdown extraction
            if 'availability' in data_dict:
                data_dict['stock_status'] = data_dict.pop('availability')
            
            return ExtractionResult(
                success=True,
                data=data_dict,
                method_used="patchright_gemini_dom_hybrid",
                processing_time=processing_time,
                warnings=[],
                errors=[]
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"❌ Patchright extraction failed: {e}")
            
            return ExtractionResult(
                success=False,
                data={},
                method_used="patchright_error",
                processing_time=processing_time,
                warnings=[],
                errors=[str(e)]
            )
        
        finally:
            await self._cleanup()
    
    async def _extract_with_retry(self, url: str, retailer: str) -> ProductData:
        """Extract with retry logic for verification challenges"""
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                logger.info(f"🔄 Attempt {attempt + 1}/{self.max_retries}")
                
                # Navigate and extract
                result = await self._navigate_and_extract(url, retailer)
                
                if result:
                    logger.info(f"✅ Success on attempt {attempt + 1}")
                    return result
                    
            except Exception as e:
                last_error = e
                logger.warning(f"⚠️ Attempt {attempt + 1} failed: {e}")
                
                if attempt < self.max_retries - 1:
                    delay = 2 ** attempt
                    logger.info(f"🕒 Waiting {delay}s before retry...")
                    await asyncio.sleep(delay)
                    
                    # Reset browser for fresh attempt
                    await self._reset_browser_context()
        
        raise Exception(f"All {self.max_retries} attempts failed. Last: {last_error}")
    
    async def _navigate_and_extract(self, url: str, retailer: str) -> ProductData:
        """
        Navigate and extract using 5-step Gemini→DOM process
        
        Steps:
        1. Navigate + handle verification
        2. Take multi-region screenshots
        3. Gemini extracts ALL data (primary)
        4. Gemini analyzes page structure (DOM hints)
        5. DOM fills gaps & validates (guided by Gemini)
        6. Merge results
        7. Learn from extraction
        """
        try:
            # Store for URL-based product code extraction fallback
            self._current_url = url
            self._current_retailer = retailer
            
            logger.info(f"🌐 Navigating to: {url}")
            
            # Step 1: Navigate
            strategy = self.strategies.get_strategy(retailer)
            wait_until = strategy.get('wait_strategy', 'domcontentloaded')
            
            try:
                response = await self.page.goto(url, wait_until=wait_until, timeout=60000)
                if response and response.status >= 400:
                    logger.warning(f"⚠️ HTTP {response.status}")
            except Exception as e:
                logger.warning(f"Navigation warning: {e}")
            
            # Wait for content
            await asyncio.sleep(self._safe_delay(4.0, 0.25, 3.0))
            logger.debug("⏱️ Post-navigation delay: varied timing")
            
            # Handle verification
            verification_handler = PatchrightVerificationHandler(self.page, self.config)
            verification_strategy = {
                'domain': self._extract_domain(url),
                'retailer': retailer
            }
            await verification_handler.handle_verification_challenges(verification_strategy)
            
            # Wait for page content to load (SPA-specific handling)
            if retailer.lower() == 'aritzia':
                logger.info("⏱️ Aritzia SPA detected - using active polling for product page")
                max_attempts = 30
                attempt = 0
                product_loaded = False
                
                # Selectors that indicate product page has loaded
                product_indicators = [
                    'h1[class*="product"]',  # Product title
                    '[data-product-id]',     # Product container
                    'button[class*="add-to-cart"]',  # Add to cart button
                    'div[class*="product-details"]'  # Product details section
                ]
                
                while attempt < max_attempts and not product_loaded:
                    attempt += 1
                    
                    for selector in product_indicators:
                        try:
                            element = await self.page.query_selector(selector)
                            if element:
                                logger.info(f"✅ Product page loaded with selector '{selector}' after {attempt} seconds")
                                product_loaded = True
                                break
                        except:
                            continue
                    
                    if not product_loaded:
                        # DO NOT CHANGE - Product detection polling interval (detection logic)
                        await asyncio.sleep(1)
                
                if not product_loaded:
                    logger.warning(f"⚠️ Product page indicators not found after {max_attempts} seconds, proceeding anyway")
            else:
                # Standard wait for other retailers
                await asyncio.sleep(self._safe_delay(2.5, 0.3, 2.0))
                logger.debug("⏱️ Post-verification delay: varied timing")
            
            # Step 1.5: Dismiss any late-appearing popups (NEW: prevents popups from obscuring product content)
            logger.info("🧹 Dismissing any late-appearing popups...")
            await verification_handler._dismiss_popups()
            await asyncio.sleep(self._safe_delay(2.0, 0.25, 1.5))
            logger.debug("⏱️ Post-popup delay: varied timing")
            
            # Step 2: Take screenshots
            logger.info("📸 Taking multi-region screenshots...")
            screenshots = await self._take_multi_region_screenshots(retailer)
            
            # Step 3: Gemini extracts ALL data (PRIMARY)
            logger.info("🔍 Step 1: Gemini extracting ALL product data...")
            product_data = await self._analyze_with_gemini(screenshots, url, retailer)
            
            # Step 4: Gemini analyzes page structure (DOM hints)
            logger.info("🗺️ Step 2: Gemini analyzing page structure for DOM hints...")
            gemini_visual_analysis = await self._gemini_analyze_page_structure(
                screenshots, url, retailer
            )
            
            # Step 5: DOM fills gaps & validates (SECONDARY)
            logger.info("🎯 Step 3: DOM filling gaps & validating...")
            dom_extraction_result = await self._guided_dom_extraction(
                retailer,
                product_data=product_data,
                gemini_visual_hints=gemini_visual_analysis.get('visual_hints', {})
            )
            
            # Step 6: Merge results
            product_data = self._merge_extraction_results(
                product_data,
                dom_extraction_result,
                gemini_visual_analysis
            )
            
            # Step 7: Learn from successful extraction
            logger.debug("Recording extraction patterns for learning...")
            
            return product_data
            
        except Exception as e:
            logger.error(f"Navigation and extraction failed: {e}")
            raise
    
    async def _take_multi_region_screenshots(self, retailer: str) -> List[bytes]:
        """
        Take full-page screenshot for product pages
        
        NOTE: Changed from multi-region scrolling to single full-page screenshot
        Product pages don't need scrolling - causes unnecessary page movement
        """
        screenshots = []
        
        try:
            # Scroll to top first
            await self.page.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(self._safe_delay(1.2, 0.25, 1.0))
            logger.debug("⏱️ Pre-screenshot delay: varied timing")
            
            # Take ONE full-page screenshot (no scrolling!)
            logger.debug("📸 Taking full-page screenshot...")
            screenshot = await self.page.screenshot(type='png', full_page=True)
            screenshots.append(screenshot)
            
            logger.info(f"✅ Captured full-page screenshot")
            return screenshots
            
        except Exception as e:
            logger.error(f"Screenshot capture failed: {e}")
            # Fallback: single full-page screenshot
            try:
                screenshot = await self.page.screenshot(full_page=True, type='png')
                return [screenshot]
            except:
                return []
    
    async def _analyze_with_gemini(
        self,
        screenshots: List[bytes],
        url: str,
        retailer: str
    ) -> ProductData:
        """
        Gemini extracts ALL product data from screenshots (primary extraction)
        """
        try:
            from PIL import Image
            import io
            import json
            
            # Prepare images
            images = []
            for screenshot_bytes in screenshots:
                image = Image.open(io.BytesIO(screenshot_bytes))
                images.append(image)
            
            # Build prompt
            prompt = f"""Extract ALL product information from these {len(screenshots)} screenshots of a {retailer} product page.

REQUIRED FIELDS:
- title: Product title/name
- brand: Brand name
- price: Current price (number)
- original_price: Original price if on sale (number, null if not on sale)
- sale_status: "on_sale" or "regular"
- availability: "in_stock", "out_of_stock", or "no_longer_available" (if product is discontinued/delisted)
- description: Product description
- sizes: Available sizes (array)
- colors: Available colors (array)
- materials: Fabric/materials
- care_instructions: Care instructions
- image_urls: Product image URLs (array)
- product_code: SKU/product code
- clothing_type: Type of clothing (dress, top, pants, etc.)

AVAILABILITY DETECTION (CRITICAL):
- Check FIRST if product is delisted: "no longer available", "discontinued", "item not found", "removed", "product no longer exists"
- Set to "no_longer_available" if product is permanently removed (NOT just temporarily out of stock)
- Set to "out_of_stock" if temporarily unavailable (sold out, coming soon)
- Set to "in_stock" if available for purchase

Return ONLY valid JSON with these fields. Extract every detail you can see."""
            
            # Call Gemini
            model = genai.GenerativeModel('gemini-2.0-flash-exp')
            response = model.generate_content([prompt] + images)
            
            if not response or not hasattr(response, 'text'):
                logger.warning("No response from Gemini")
                return ProductData()
            
            # Parse JSON
            content = response.text.strip()
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                content = content.split('```')[1].split('```')[0].strip()
            
            data = json.loads(content)
            
            # Create ProductData
            product_data = ProductData(
                title=data.get('title', ''),
                brand=data.get('brand', ''),
                price=float(data.get('price', 0)),
                original_price=float(data.get('original_price')) if data.get('original_price') else None,
                sale_status=data.get('sale_status', 'regular'),
                availability=data.get('availability', 'in_stock'),
                description=data.get('description', ''),
                sizes=data.get('sizes', []),
                colors=data.get('colors', []),
                materials=data.get('materials', ''),
                care_instructions=data.get('care_instructions', ''),
                image_urls=data.get('image_urls', []),
                product_code=data.get('product_code', ''),
                clothing_type=data.get('clothing_type', '')
            )
            
            logger.info(f"✅ Gemini extracted: {product_data.title[:50]}...")
            return product_data
            
        except Exception as e:
            logger.error(f"Gemini analysis failed: {e}")
            return ProductData()
    
    async def _gemini_analyze_page_structure(
        self,
        screenshots: List[bytes],
        url: str,
        retailer: str
    ) -> Dict:
        """
        Gemini analyzes page structure to provide DOM hints
        
        Returns visual hints like:
        - Price location (top-right, left-side, etc.)
        - Title style (large heading, bold text)
        - Image gallery layout
        """
        try:
            from PIL import Image
            import io
            import json
            
            images = []
            for screenshot_bytes in screenshots:
                image = Image.open(io.BytesIO(screenshot_bytes))
                images.append(image)
            
            prompt = """Analyze this product page layout and provide visual hints for DOM extraction.

Describe:
1. Where is the PRICE located? (top-right, left-side, center, etc.)
2. Where is the TITLE? (top, center, bold heading, etc.)
3. Where are PRODUCT IMAGES? (left gallery, center, carousel, etc.)
4. Where are SIZES/COLORS? (below price, right side, dropdown, etc.)
5. Page layout type? (standard, minimal, complex grid)

Return JSON:
{
  "visual_hints": {
    "price_location": "top-right corner",
    "title_style": "large bold heading at top",
    "image_layout": "left gallery",
    "size_location": "below price",
    "layout_type": "standard"
  }
}"""
            
            model = genai.GenerativeModel('gemini-2.0-flash-exp')
            response = model.generate_content([prompt] + images)
            
            if response and hasattr(response, 'text'):
                content = response.text.strip()
                if '```json' in content:
                    content = content.split('```json')[1].split('```')[0].strip()
                
                result = json.loads(content)
                logger.debug(f"Gemini page structure hints: {result.get('visual_hints', {})}")
                return result
            
            return {'visual_hints': {}}
            
        except Exception as e:
            logger.debug(f"Page structure analysis failed: {e}")
            return {'visual_hints': {}}
    
    async def _guided_dom_extraction(
        self,
        retailer: str,
        product_data: ProductData,
        gemini_visual_hints: Dict
    ) -> Dict:
        """
        DOM extraction guided by Gemini hints
        
        Uses PatchrightDOMValidator for comprehensive extraction
        """
        try:
            # Create DOM validator
            dom_validator = PatchrightDOMValidator(self.page, retailer)
            
            # Convert ProductData to dict for validator
            product_dict = {
                'title': product_data.title,
                'price': product_data.price,
                'image_urls': product_data.image_urls
            }
            
            # Perform guided DOM extraction
            dom_result = await dom_validator.guided_dom_extraction(
                product_dict,
                gemini_visual_hints
            )
            
            logger.debug(f"DOM result: {len(dom_result.get('gaps_filled', []))} gaps filled")
            return dom_result
            
        except Exception as e:
            logger.error(f"DOM extraction failed: {e}")
            return {}
    
    def _merge_extraction_results(
        self,
        product_data: ProductData,
        dom_result: Dict,
        gemini_analysis: Dict
    ) -> ProductData:
        """
        Merge Gemini (primary) with DOM (gaps/validation)
        
        DOM result format:
        - title: str | None
        - price: str | None  
        - images: List[str]
        - gaps_filled: List[str]
        - validations: Dict
        """
        # Fill gaps with DOM data
        if dom_result.get('title') and not product_data.title:
            product_data.title = dom_result['title']
            logger.debug("DOM filled title gap")
        
        if dom_result.get('price') and not product_data.price:
            # Parse price from DOM text
            price_text = dom_result['price']
            import re
            price_match = re.search(r'[\d,]+\.?\d*', price_text.replace(',', ''))
            if price_match:
                product_data.price = float(price_match.group(0))
                logger.debug("DOM filled price gap")
        
        if dom_result.get('images') and not product_data.image_urls:
            product_data.image_urls = dom_result['images']
            logger.debug("DOM filled image URLs gap")
        
        # Fill product code from URL if not extracted (redundant extraction)
        if not product_data.product_code and hasattr(self, '_current_url'):
            url_code = self._extract_product_code_from_url(self._current_url, self._current_retailer)
            if url_code:
                product_data.product_code = url_code
                logger.debug("URL filled product code gap")
        
        # Log validation results
        validations = dom_result.get('validations', {})
        if validations:
            logger.debug(f"DOM validations: {len(validations)} fields checked")
        
        return product_data
    
    async def _setup_stealth_browser(self):
        """Setup Patchright stealth browser"""
        try:
            self.playwright = await async_playwright().start()
            
            user_data_dir = os.path.join(os.path.expanduser('~'), '.patchright_data')
            os.makedirs(user_data_dir, exist_ok=True)
            
            # Enhanced stealth arguments (can be disabled via kill switch)
            if ENABLE_ANTI_SCRAPING_ENHANCEMENTS:
                args = [
                    '--disable-blink-features=AutomationControlled',  # CRITICAL - removes automation flag
                    '--no-first-run',
                    '--no-default-browser-check',
                    '--disable-dev-shm-usage',
                    '--disable-notifications',
                    '--disable-background-networking',
                    '--disable-background-timer-throttling',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-breakpad',
                    '--disable-component-update',
                    '--disable-domain-reliability',
                    '--disable-features=AudioServiceOutOfProcess',
                    '--disable-hang-monitor',
                    '--disable-ipc-flooding-protection',
                    '--disable-popup-blocking',
                    '--disable-print-preview',
                    '--disable-prompt-on-repost',
                    '--disable-renderer-backgrounding',
                    '--disable-sync',
                    '--hide-scrollbars',
                    '--metrics-recording-only',
                    '--mute-audio',
                    '--no-pings',
                    '--password-store=basic',
                    '--use-mock-keychain',
                    '--disable-client-side-phishing-detection',
                ]
            else:
                args = []  # No args - original behavior
            
            self.context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir,
                headless=False,
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                locale='en-US',
                permissions=[],  # Deny all permissions (notifications, geolocation, etc.)
                args=args,  # NEW: Enhanced stealth arguments
                ignore_https_errors=True,
            )
            
            self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
            
            # Inject stealth scripts if enhancements enabled
            if ENABLE_ANTI_SCRAPING_ENHANCEMENTS:
                await self._inject_stealth_scripts(self.page)
                logger.info("🛡️ Enhanced stealth browser initialized with anti-detection")
                logger.debug(f"  ✅ Enhanced browser args: {len(args)} flags")
                logger.debug(f"  ✅ WebDriver hiding: Active")
            else:
                logger.info("✅ Stealth browser initialized (original behavior)")
            
        except Exception as e:
            logger.error(f"Failed to setup browser: {e}")
            raise
    
    async def _inject_stealth_scripts(self, page):
        """
        Inject JavaScript to hide automation indicators
        
        This masks properties that anti-bot systems check to detect automation.
        Non-critical - if injection fails, extraction continues normally.
        """
        try:
            await page.add_init_script("""
                // Hide webdriver property (primary bot detection signal)
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                // Mock chrome object (browsers have this, automation tools often don't)
                window.navigator.chrome = {
                    runtime: {},
                    loadTimes: function() {},
                    csi: function() {},
                    app: {}
                };
                
                // Mock permissions query
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
                );
                
                // Mock plugins array (real browsers have multiple plugins)
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                
                // Mock languages (real browsers have language preferences)
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
            """)
            logger.debug("✅ Stealth scripts injected successfully")
        except Exception as e:
            logger.warning(f"⚠️ Stealth script injection failed (non-critical): {e}")
            # Non-critical - continue extraction even if injection fails
    
    def _safe_delay(self, base: float, variance_percent: float = 0.25, minimum: float = None) -> float:
        """
        Calculate randomized delay while preserving minimum requirements
        
        Args:
            base: Base delay in seconds
            variance_percent: Percentage variance (0.25 = ±25%)
            minimum: Minimum delay in seconds (optional)
        
        Returns:
            Delay in seconds with variance applied, but >= minimum
        
        Examples:
            _safe_delay(3.0, 0.25) → 2.25-3.75 seconds
            _safe_delay(3.0, 0.25, 2.0) → 2.25-3.75, but never < 2.0
        """
        import random
        
        variance = base * variance_percent
        delay = random.uniform(base - variance, base + variance)
        
        if minimum is not None:
            delay = max(delay, minimum)
        
        return delay
    
    async def _reset_browser_context(self):
        """Reset browser for fresh attempt"""
        try:
            await self._cleanup()
            await self._setup_stealth_browser()
            logger.debug("Browser context reset")
        except Exception as e:
            logger.warning(f"Browser reset failed: {e}")
    
    def _extract_product_code_from_url(self, url: str, retailer: str) -> str:
        """
        Extract product code from URL
        
        Provides redundant extraction via URL patterns for robustness.
        Primary extraction happens via Gemini from screenshots.
        """
        import re
        
        patterns = {
            'revolve': r'/dp/([A-Z0-9\-]+)/?',
            'anthropologie': r'/shop/([A-Z0-9\-]+)',
            'abercrombie': r'/shop/([A-Za-z0-9\-]+)/?$',
            'urban_outfitters': r'/([A-Za-z0-9\-]+)/?$',
            'aritzia': r'/([A-Z0-9\-]+)/?$',
            'nordstrom': r'/s/[^/]+/(\d+)'  # /s/{product-name}/{product-id}
        }
        
        pattern = patterns.get(retailer.lower())
        if pattern:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        # Fallback: extract from last URL segment
        parts = url.rstrip('/').split('/')
        return parts[-1].split('?')[0] if parts else ""
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc
    
    async def _cleanup(self):
        """Cleanup browser resources"""
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            logger.debug("Browser cleanup complete")
        except Exception as e:
            logger.debug(f"Cleanup error: {e}")
