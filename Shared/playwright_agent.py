# Add shared path for imports
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../Shared"))
sys.path.append(os.path.dirname(__file__))

import asyncio
import base64
import json
import time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime
import os
import logging
import re

from patchright.async_api import async_playwright, Page, Browser, BrowserContext
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from PIL import Image
import io
import google.generativeai as genai

from logger_config import setup_logging
from page_structure_learner import PageStructureLearner

logger = setup_logging(__name__)

@dataclass
class ProductData:
    """Standardized product data format (matches existing system)"""
    title: str = ""
    brand: str = ""
    price: Optional[float] = None
    original_price: Optional[float] = None
    description: str = ""
    stock_status: str = ""
    sale_status: str = ""
    clothing_type: str = ""
    product_code: str = ""
    image_urls: List[str] = None
    retailer: str = ""
    colors: List[str] = None
    sizes: List[str] = None
    material: str = ""
    care_instructions: str = ""
    neckline: str = ""
    sleeve_length: str = ""
    visual_analysis_confidence: Optional[float] = None
    visual_analysis_source: str = ""
    
    def __post_init__(self):
        if self.image_urls is None:
            self.image_urls = []
        if self.colors is None:
            self.colors = []
        if self.sizes is None:
            self.sizes = []

@dataclass
class ExtractionResult:
    """Matches existing system's ExtractionResult format"""
    success: bool
    data: Dict[str, Any]
    method_used: str
    processing_time: float
    warnings: List[str]
    errors: List[str]

class PlaywrightMultiScreenshotAgent:
    """
    Complete replacement for Browser Use using Playwright + Multi-Screenshot + Gemini 2.0 Flash
    Handles verification challenges, anti-scraping, and provides better performance
    """
    
    def __init__(self, config: Dict = None):
        """Initialize with existing system configuration"""
        self.config = config or self._load_config()
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        
        # Initialize Gemini 2.0 Flash (use existing config)
        self._setup_gemini()
        
        # Retailer-specific screenshot strategies
        self.screenshot_strategies = self._load_screenshot_strategies()
        
        # Anti-scraping settings
        self.stealth_enabled = True
        self.max_retries = 3
        
        # Initialize Page Structure Learner
        self.structure_learner = PageStructureLearner()
        logger.info("✅ Page Structure Learner initialized")
        
    def _load_config(self) -> Dict:
        """Load configuration from config.json"""
        try:
            config_path = os.path.join(os.path.dirname(__file__), '../Shared/config.json')
            with open(config_path, 'r') as f:
                config = json.load(f)
            logger.info("✅ Configuration loaded from config.json")
            return config
        except Exception as e:
            logger.warning(f"⚠️ Failed to load config.json: {e}")
            return {}
    
    def _setup_gemini(self):
        """Setup Gemini 2.0 Flash using existing configuration"""
        try:
            # Use existing API key from config
            api_key = os.getenv("GOOGLE_API_KEY") or self.config.get("llm_providers", {}).get("google", {}).get("api_key")
            if not api_key:
                raise ValueError("No Google API key found")
            
            # Use langchain_google_genai (same as existing system)
            self.model = ChatGoogleGenerativeAI(
                model="gemini-2.0-flash-exp",
                api_key=api_key,
                temperature=0.1,
                max_output_tokens=2048,
                top_p=0.8,
                top_k=40
            )
            logger.info("✅ Gemini 2.0 Flash initialized for Playwright agent")
            
        except Exception as e:
            logger.error(f"Failed to initialize Gemini: {e}")
            raise
    
    def _load_screenshot_strategies(self) -> Dict:
        """Load retailer-specific screenshot strategies"""
        return {
            'aritzia.com': {
                'screenshots': ['full_page', 'main_image', 'product_details', 'size_color_options'],
                'anti_scraping': 'medium',
                'wait_conditions': ['networkidle', '.product-name, .product-title'],
                'scroll_positions': [0, 0.3, 0.6, 1.0],
                'cloudflare_likely': True
            },
            'anthropologie.com': {
                'screenshots': ['full_page', 'hero_section', 'product_info', 'image_gallery'],
                'anti_scraping': 'high',
                'wait_conditions': ['load', '.product-name, .product-title'],
                'scroll_positions': [0, 0.4, 0.8],
                'verification_challenge': 'press_and_hold'
            },
            'nordstrom.com': {
                'screenshots': ['full_page', 'main_content', 'product_details', 'images_section'],
                'anti_scraping': 'very_high',  # Known to block Browser Use
                'wait_conditions': ['networkidle', '.product-title, .product-name'],
                'scroll_positions': [0, 0.5, 1.0],
                'ip_blocking': True
            },
            'urbanoutfitters.com': {
                'screenshots': ['full_page', 'product_hero', 'details_section', 'related_images'],
                'anti_scraping': 'high',
                'wait_conditions': ['load', '.product-title, .product-name'],
                'scroll_positions': [0, 0.3, 0.7],
                'verification_challenge': 'press_and_hold'
            },
            'abercrombie.com': {
                'screenshots': ['full_page', 'main_product', 'product_info', 'image_carousel'],
                'anti_scraping': 'medium',
                'wait_conditions': ['networkidle', '.product-name, .product-title'],
                'scroll_positions': [0, 0.4, 0.8],
                'category_page_handling': True
            }
        }
    
    async def extract_product(self, url: str, retailer: str) -> ExtractionResult:
        """
        Main extraction method - replaces Browser Use completely
        """
        start_time = time.time()
        logger.info(f"🎭 Starting Patchright extraction for {retailer}: {url}")
        
        try:
            # Setup stealth browser
            await self._setup_stealth_browser()
            
            # Extract with retry logic
            result = await self._extract_with_retry(url, retailer)
            
            processing_time = time.time() - start_time
            logger.info(f"✅ Patchright extraction completed in {processing_time:.1f}s")
            
            return ExtractionResult(
                success=True,
                data=result.__dict__,
                method_used="patchright_multi_screenshot",
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
                method_used="patchright_multi_screenshot",
                processing_time=processing_time,
                warnings=[],
                errors=[str(e)]
            )
        
        finally:
            await self._cleanup()
    
    async def extract_catalog(self, catalog_url: str, retailer: str, catalog_prompt: str) -> Dict[str, Any]:
        """
        Extract ALL products from a catalog/listing page using Patchright screenshots + Gemini Vision
        
        This method is for catalog pages (multi-product listings).
        For single product pages, use extract_product() instead.
        
        Args:
            catalog_url: URL of the catalog/listing page
            retailer: Retailer identifier
            catalog_prompt: Pre-built catalog-specific prompt from catalog_extractor
            
        Returns:
            Dict containing:
            - success: bool
            - products: List[Dict] - Array of product summaries
            - total_found: int
            - method_used: str ('patchright_gemini')
            - processing_time: float
            - warnings: List[str]
            - errors: List[str]
        """
        start_time = time.time()
        
        try:
            logger.info(f"🎭 Starting Patchright catalog extraction for {retailer}: {catalog_url}")
            
            # Setup stealth browser
            await self._setup_stealth_browser()
            
            # Navigate to catalog page
            logger.debug(f"Navigating to catalog page: {catalog_url}")
            await self.page.goto(catalog_url, wait_until='networkidle', timeout=60000)
            await asyncio.sleep(3)  # Let dynamic content load
            
            # Handle any verification challenges
            strategy = {'domain': self._extract_domain(catalog_url), 'retailer': retailer}
            await self._handle_verification_challenges(strategy)
            
            # Wait for page to fully load (no scrolling needed - full_page screenshot captures everything)
            await asyncio.sleep(3)
            
            # Take FULL PAGE screenshot to capture ALL products (not just viewport)
            screenshots = []
            screenshot_descriptions = []
            
            # Scroll to top first for clean screenshot
            await self.page.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(1)
            
            # Take ONE full-page PNG screenshot (PNG has no size limit, WebP limited to 16383px)
            logger.debug(f"📸 Taking full-page PNG screenshot (captures all products on page)")
            full_page_screenshot = await self.page.screenshot(full_page=True, type='png')
            screenshots.append(full_page_screenshot)
            screenshot_descriptions.append("Full catalog page showing all products")
            
            logger.info(f"✅ Captured full-page catalog screenshot")
            
            # STEP 1: Gemini extracts ALL visual data FIRST
            logger.info("🔍 Step 1: Gemini Vision extracting product data from screenshot")
            
            # Build Gemini prompt with screenshots
            screenshot_list = "\n".join([f"{i+1}. {desc}" for i, desc in enumerate(screenshot_descriptions)])
            
            full_prompt = f"""{catalog_prompt}

SCREENSHOT ANALYSIS INSTRUCTIONS:
You are viewing {len(screenshots)} screenshot(s) of a {retailer} catalog page. 
Analyze ALL visible products across all screenshots.
Extract EVERY product you can see.

Screenshots show:
{screenshot_list}

IMPORTANT: Extract ALL visual information you can see for each product:
- Product title (as shown in the image)
- Current price (visible in screenshot)
- Original price if on sale (if product is on sale)
- Product image URL (visible in screenshot, if available)
- Sale status (on_sale or regular)
- Any other visual details you can identify

NOTE: You cannot read URLs or product codes from screenshots. 
We will extract those separately using DOM after you provide the visual data.

Return a JSON array with ALL products found across all screenshots."""

            # Call Gemini Vision with all screenshots
            logger.debug("Sending full-page screenshot to Gemini Vision for catalog extraction")
            
            # Configure Gemini API
            api_key = os.getenv("GOOGLE_API_KEY") or self.config.get("llm_providers", {}).get("google", {}).get("api_key")
            genai.configure(api_key=api_key)
            
            # Prepare image parts for Gemini
            image_parts = []
            for screenshot_bytes in screenshots:
                # Convert bytes to PIL Image for Gemini
                from PIL import Image
                import io
                image = Image.open(io.BytesIO(screenshot_bytes))
                
                # Resize if height exceeds Gemini's WebP limit (16383px)
                # Gemini converts to WebP internally, so we must stay under the limit
                max_height = 16000  # Stay under 16383 limit with buffer
                if image.height > max_height:
                    scale_factor = max_height / image.height
                    new_width = int(image.width * scale_factor)
                    logger.info(f"📐 Resizing screenshot from {image.width}x{image.height} to {new_width}x{max_height} (Gemini WebP limit)")
                    image = image.resize((new_width, max_height), Image.Resampling.LANCZOS)
                
                image_parts.append(image)
            
            # Call Gemini Vision model
            model = genai.GenerativeModel('gemini-2.0-flash-exp')
            response = model.generate_content([full_prompt] + image_parts)
            
            # Parse response
            extraction_result = None
            if response and hasattr(response, 'text'):
                content = response.text
                
                # Look for JSON pattern
                import re
                import json
                json_pattern = r"(\{[\s\S]*\}|\[[\s\S]*\])"
                json_match = re.search(json_pattern, content)
                
                if json_match:
                    json_str = json_match.group(1)
                    try:
                        extraction_result = json.loads(json_str)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse JSON from Gemini response: {e}")
            
            processing_time = time.time() - start_time
            
            # Process results
            if not extraction_result:
                logger.warning(f"⚠️ Failed to extract catalog products with Patchright")
                return {
                    'success': False,
                    'products': [],
                    'total_found': 0,
                    'method_used': 'patchright_gemini',
                    'processing_time': processing_time,
                    'warnings': ['Failed to parse Gemini response'],
                    'errors': ['Could not extract product array from response']
                }
            
            # Extract products array
            products = []
            if isinstance(extraction_result, dict):
                if 'products' in extraction_result:
                    products = extraction_result['products']
                elif 'data' in extraction_result and isinstance(extraction_result['data'], list):
                    products = extraction_result['data']
            elif isinstance(extraction_result, list):
                products = extraction_result
            
            # Validate we got an array
            if not isinstance(products, list):
                return {
                    'success': False,
                    'products': [],
                    'total_found': 0,
                    'method_used': 'patchright_gemini',
                    'processing_time': processing_time,
                    'warnings': [f'Expected array, got {type(products)}'],
                    'errors': ['Extraction result was not in array format']
                }
            
            logger.info(f"✅ Gemini extracted {len(products)} products visually")
            
            # STEP 2: DOM extracts URLs + validates Gemini's work (guided by Gemini's visual data)
            logger.info("🔗 Step 2: DOM extracting URLs and validating Gemini data")
            
            # DEBUG: Save page HTML to inspect selectors (temporary)
            if len(products) > 0 and retailer == 'abercrombie':
                try:
                    page_html = await self.page.content()
                    debug_file = f"/tmp/{retailer}_catalog_debug.html"
                    with open(debug_file, 'w', encoding='utf-8') as f:
                        f.write(page_html)
                    logger.info(f"🐛 DEBUG: Saved page HTML to {debug_file}")
                except Exception as e:
                    logger.debug(f"Failed to save debug HTML: {e}")
            
            dom_product_links = await self._extract_catalog_product_links_from_dom(retailer)
            logger.info(f"✅ DOM found {len(dom_product_links)} product URLs")
            
            # STEP 3: Merge DOM URLs with Gemini visual data + validate
            logger.info("🔗 Step 3: Merging DOM URLs with Gemini visual data + validation")
            merged_products, validation_stats = self._merge_catalog_dom_with_gemini(dom_product_links, products, retailer)
            logger.info(f"✅ Merged result: {len(merged_products)} products with complete data")
            
            # Use merged products for final result
            products = merged_products
            
            logger.info(f"✅ Patchright catalog extraction successful: {len(products)} products found")
            
            # Record catalog extraction performance for learning (with validation stats)
            try:
                self.structure_learner.record_extraction_performance(
                    retailer=retailer,
                    gemini_success=True,
                    gemini_time=processing_time,
                    gemini_completeness=1.0 if len(products) > 5 else 0.7,
                    dom_needed=True,  # We use DOM for URLs and validation
                    dom_gaps=['urls', 'product_codes'],  # DOM fills these gaps
                    dom_time=0.0,
                    total_time=processing_time,
                    final_completeness=1.0 if len(products) > 5 else 0.7,
                    method_used='patchright_catalog_gemini_dom_hybrid',
                    validation_stats=validation_stats  # Pass validation metrics
                )
            except Exception as e:
                logger.debug(f"Failed to record catalog performance: {e}")
            
            return {
                'success': True,
                'products': products,
                'total_found': len(products),
                'method_used': 'patchright_gemini',
                'processing_time': processing_time,
                'warnings': [],
                'errors': []
            }
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Patchright catalog extraction error: {e}")
            return {
                'success': False,
                'products': [],
                'total_found': 0,
                'method_used': 'patchright_error',
                'processing_time': processing_time,
                'warnings': [],
                'errors': [str(e)]
            }
            
        finally:
            await self._cleanup()
    
    async def _setup_stealth_browser(self):
        """Setup Patchright browser with persistent context for enhanced anti-detection"""
        try:
            # Import stealth (install if needed)
            try:
                from playwright_stealth import stealth_async
                self.stealth_available = True
            except ImportError:
                logger.warning("playwright-stealth not available, using Patchright's built-in stealth")
                self.stealth_available = False
            
            self.playwright = await async_playwright().start()
            
            # Create profile directory for persistent context
            profile_dir = os.path.join(os.path.dirname(__file__), "browser_profiles")
            os.makedirs(profile_dir, exist_ok=True)
            
            # CRITICAL: Use launch_persistent_context (not launch) for better stealth
            self.context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                channel="chrome",           # Real Chrome, not Chromium
                headless=False,             # Headless = easily detected
                no_viewport=True,           # Natural viewport behavior
                
                # Enhanced anti-detection args
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage', 
                    '--no-sandbox',
                    '--disable-gpu',
                    '--disable-extensions',
                    '--disable-plugins',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor',
                    '--no-first-run',
                    '--disable-default-apps',
                    '--disable-sync',
                    '--exclude-switches=enable-automation',
                    '--disable-automation',
                    '--disable-blink-features=AutomationControlled',
                    '--use-fake-ui-for-media-stream',
                    '--use-fake-device-for-media-stream',
                    '--autoplay-policy=user-gesture-required',
                    '--disable-background-timer-throttling',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-renderer-backgrounding',
                    '--disable-field-trial-config',
                    '--disable-back-forward-cache',
                    '--disable-ipc-flooding-protection',
                ],
                
                # Realistic browser settings
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                extra_http_headers={
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1'
                },
                
                # Preserve existing timeouts
                timeout=120000,
            )
            
            # No browser object with persistent context
            self.browser = None
            
            # Create initial page
            self.page = await self.context.new_page()
            
            # Apply stealth if available
            if self.stealth_available:
                await stealth_async(self.page)
            
            # Additional stealth measures - hide WebDriver properties
            await self.page.add_init_script("""
                // Remove webdriver property
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
                
                // Mock chrome object
                window.chrome = {
                    runtime: {},
                    loadTimes: function() {},
                    csi: function() {},
                    app: {}
                };
                
                // Mock plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5],
                });
                
                // Mock languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en'],
                });
                
                // Hide automation indicators
                delete navigator.__proto__.webdriver;
            """)
            
            logger.info("🥷 Patchright persistent context setup complete - enhanced stealth enabled")
            
        except Exception as e:
            logger.error(f"Failed to setup Patchright browser: {e}")
            raise
    
    async def _extract_with_retry(self, url: str, retailer: str) -> ProductData:
        """Extract with retry logic for verification challenges"""
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                logger.info(f"🔄 Attempt {attempt + 1}/{self.max_retries} for {retailer}")
                
                # Navigate with smart waiting
                result = await self._navigate_and_capture(url, retailer)
                
                if result:
                    logger.info(f"✅ Success on attempt {attempt + 1}")
                    return result
                    
            except Exception as e:
                last_error = e
                logger.warning(f"⚠️ Attempt {attempt + 1} failed: {e}")
                
                if attempt < self.max_retries - 1:
                    # Progressive delay
                    delay = 2 ** attempt
                    logger.info(f"🕒 Waiting {delay}s before retry...")
                    await asyncio.sleep(delay)
                    
                    # Reset browser context for fresh attempt
                    await self._reset_browser_context()
        
        raise Exception(f"All {self.max_retries} attempts failed. Last error: {last_error}")
    
    async def _navigate_and_capture(self, url: str, retailer: str) -> ProductData:
        """Navigate to URL and capture screenshots with DOM image extraction"""
        # Get retailer strategy  
        domain = self._extract_domain(url)
        strategy = self.screenshot_strategies.get(domain, self.screenshot_strategies.get('default', {
            'screenshots': ['full_page', 'main_content'],
            'anti_scraping': 'medium',
            'wait_conditions': ['load'],
            'scroll_positions': [0, 0.5, 1.0]
        }))
        
        # Add domain info for enhanced processing
        strategy['domain'] = domain
        strategy['retailer'] = retailer
        
        logger.info(f"📋 Using strategy for {domain}: {strategy.get('anti_scraping')} anti-scraping")
        
        try:
            logger.info(f"🌐 Navigating to: {url}")
            
            # Navigate with enhanced error handling
            try:
                response = await self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
                if response and response.status >= 400:
                    logger.warning(f"⚠️ HTTP {response.status} response")
            except Exception as e:
                logger.warning(f"Navigation warning: {e}")
            
            # Wait for content to load (with enhanced Anthropologie support)
            await self._wait_for_content(strategy)
            
            # Handle verification challenges
            await self._handle_verification_challenges(strategy)
            
            # Take strategic screenshots for content analysis
            screenshots = await self._take_strategic_screenshots(strategy, retailer)
            
            # STEP 1: Gemini extracts ALL product data from screenshots (PRIMARY)
            logger.info("🔍 Step 1: Gemini extracting ALL product data from screenshots")
            product_data = await self._analyze_with_gemini(screenshots, url, retailer)
            
            # STEP 2: Gemini analyzes page structure for DOM guidance
            logger.info("🗺️ Step 2: Gemini analyzing page structure for DOM hints")
            gemini_visual_analysis = await self._gemini_analyze_page_structure(screenshots, url, retailer)
            
            # STEP 3: DOM fills gaps and validates Gemini's work (SECONDARY)
            logger.info("🎯 Step 3: DOM filling gaps & validating (guided by Gemini)")
            dom_extraction_result = await self._guided_dom_extraction(
                retailer,
                product_data=product_data,  # Pass Gemini's results
                gemini_visual_hints=gemini_visual_analysis.get('visual_hints', {})
            )
            
            # STEP 4: Merge results (Gemini primary, DOM fills gaps/validates)
            product_data = self._merge_extraction_results(
                product_data,
                dom_extraction_result,
                gemini_visual_analysis
            )
            
            # STEP 5: Learn from successful extraction
            await self._learn_from_extraction(
                retailer,
                dom_extraction_result,
                gemini_visual_analysis,
                product_data,
                url
            )
            
            return product_data
            
        except Exception as e:
            logger.error(f"Error during navigation and capture: {e}")
            # Return minimal data with any DOM images we found
            dom_images = await self._extract_image_urls_from_dom(retailer) if self.page else []
            return ProductData(
                title="Extraction Error",
                retailer=retailer,
                image_urls=dom_images[:3]  # Fallback images
            )
    
    async def _wait_for_content(self, strategy: Dict):
        """Smart waiting based on retailer strategy with enhanced image loading support"""
        wait_conditions = strategy.get('wait_conditions', ['load'])
        domain = strategy.get('domain', '')
        
        # Special handling for Anthropologie's lazy-loading issues
        if 'anthropologie' in domain.lower():
            logger.info("🎨 Applying enhanced Anthropologie image loading strategy")
            await self._wait_for_anthropologie_images(strategy)
            return
        
        # Standard wait processing for other retailers
        for condition in wait_conditions:
            try:
                if condition == 'networkidle':
                    await self.page.wait_for_load_state('networkidle', timeout=15000)
                elif condition == 'load':
                    await self.page.wait_for_load_state('load', timeout=10000)
                elif condition.startswith('.') or condition.startswith('#'):
                    # CSS selector
                    await self.page.wait_for_selector(condition, timeout=10000)
                
                logger.debug(f"✅ Wait condition met: {condition}")
                
            except Exception as e:
                logger.warning(f"⚠️ Wait condition failed: {condition} - {e}")
                continue
    
    async def _wait_for_anthropologie_images(self, strategy: Dict):
        """
        Enhanced waiting specifically for Anthropologie's lazy-loading image system
        Addresses the color placeholder issue by ensuring images actually load
        """
        logger.info("🎨 Starting enhanced Anthropologie image loading sequence")
        
        try:
            # Step 1: Basic page load
            await self.page.wait_for_load_state('load', timeout=15000)
            logger.debug("✅ Basic page load complete")
            
            # Step 2: Pre-scroll to trigger lazy loading
            logger.info("📜 Pre-scrolling to trigger lazy-loaded images")
            await self._scroll_to_position(0.3)
            await asyncio.sleep(2)  # Allow images to start loading
            await self._scroll_to_position(0.6)
            await asyncio.sleep(2)  # Allow more images to load
            await self._scroll_to_position(0)  # Back to top
            await asyncio.sleep(1)
            
            # Step 3: Wait for network to settle
            try:
                await self.page.wait_for_load_state('networkidle', timeout=20000)
                logger.debug("✅ Network idle achieved")
            except Exception as e:
                logger.warning(f"⚠️ Network idle timeout (continuing): {e}")
            
            # Step 4: Wait for actual Anthropologie images (not placeholders)
            image_selectors = [
                'img[src*="anthropologie.com"]:not([src*="placeholder"])',
                'img[src*="assets.anthropologie.com"]',
                'img[src*="scene7.com"]',
                '.product-images img[src]:not([src=""])',
                '.hero-image img[src]:not([src*="loading"])'
            ]
            
            for selector in image_selectors:
                try:
                    await self.page.wait_for_selector(selector, timeout=8000)
                    logger.debug(f"✅ Found images: {selector}")
                    break
                except Exception as e:
                    logger.debug(f"⚠️ Image selector failed: {selector} - {e}")
                    continue
            
            # Step 5: Verify images have actually loaded (not just placeholders)
            try:
                # Check if we have real image content loaded
                image_count = await self.page.evaluate("""
                    () => {
                        const images = document.querySelectorAll('img[src*="anthropologie"], img[src*="assets.anthropologie"], img[src*="scene7"]');
                        let loadedCount = 0;
                        images.forEach(img => {
                            if (img.complete && img.naturalWidth > 100 && img.naturalHeight > 100) {
                                loadedCount++;
                            }
                        });
                        return loadedCount;
                    }
                """)
                
                if image_count > 0:
                    logger.info(f"✅ Verified {image_count} high-quality images loaded")
                else:
                    logger.warning("⚠️ No high-quality images detected, proceeding anyway")
                    
            except Exception as e:
                logger.warning(f"⚠️ Image verification failed: {e}")
            
            # Step 6: Final wait for any remaining content
            await asyncio.sleep(3)  # Allow final rendering
            logger.info("🎨 Enhanced Anthropologie image loading complete")
            
        except Exception as e:
            logger.error(f"❌ Enhanced Anthropologie waiting failed: {e}")
            # Fallback to basic wait
            try:
                await self.page.wait_for_load_state('load', timeout=10000)
            except:
                pass
    
    async def _dismiss_popups(self):
        """Dismiss common popups: notifications, cookie banners, email signup, ads"""
        dismissed_count = 0
        
        # Common popup close button patterns (generalized across retailers)
        close_selectors = [
            # X buttons and close icons
            'button[aria-label*="close" i]',
            'button[aria-label*="dismiss" i]',
            'button[title*="close" i]',
            '[class*="close-button" i]',
            '[class*="close-btn" i]',
            '[class*="modal-close" i]',
            '[id*="close-button" i]',
            '.close-icon',
            
            # Text-based close buttons
            'button:has-text("Close")',
            'button:has-text("No Thanks")',
            'button:has-text("No thanks")',
            'button:has-text("Maybe Later")',
            'button:has-text("Not Now")',
            'button:has-text("Dismiss")',
            'button:has-text("Continue")',
            'button:has-text("Accept")',
            
            # Cookie banners
            'button:has-text("Accept All")',
            'button:has-text("Accept Cookies")',
            'button:has-text("I Agree")',
            '[id*="cookie-accept"]',
            '[class*="cookie-accept"]',
            
            # Email signup dismissal
            '[data-testid*="close"]',
            '[data-testid*="dismiss"]',
            '.email-signup-close',
            '.newsletter-close',
            
            # Modal overlays (last resort - click overlay itself)
            '.modal-overlay',
            '.popup-overlay',
            '[class*="overlay"][class*="modal"]'
        ]
        
        for selector in close_selectors:
            try:
                # Check if element exists and is visible
                elements = await self.page.locator(selector).all()
                
                for element in elements:
                    try:
                        if await element.is_visible(timeout=500):
                            await element.click(timeout=1000)
                            dismissed_count += 1
                            logger.info(f"✅ Dismissed popup: {selector}")
                            await asyncio.sleep(0.5)  # Let popup close animation finish
                    except:
                        continue
                        
            except Exception as e:
                logger.debug(f"Popup check failed for {selector}: {e}")
                continue
        
        if dismissed_count > 0:
            logger.info(f"🧹 Dismissed {dismissed_count} popups total")
        
        return dismissed_count > 0
    
    async def _handle_verification_challenges(self, strategy: Dict):
        """Enhanced verification with Patchright shadow DOM support"""
        
        # First, dismiss any popups that might be blocking
        await self._dismiss_popups()
        
        # Then handle verification challenges
        verification_selectors = [
            'button:has-text("Press & Hold")',
            'button:has-text("I am human")',
            'button:has-text("Verify")',
            '.captcha-container',
            '.cloudflare-browser-verification',
            '#challenge-form',
            '[data-testid="press-hold-button"]',
            'iframe[src*="challenges.cloudflare.com"]',
            '[aria-label*="verification"]',
            '[aria-label*="challenge"]'
        ]
        
        for selector in verification_selectors:
            try:
                element = await self.page.locator(selector).first
                if await element.is_visible(timeout=2000):
                    logger.info(f"🛡️ Handling verification with Patchright: {selector}")
                    
                    if "Press & Hold" in selector or "press-hold" in selector:
                        # Enhanced press-and-hold with Patchright
                        await element.hover()
                        await self.page.wait_for_timeout(1000)
                        await element.click()
                        await self.page.wait_for_timeout(6000)  # Hold longer
                    elif "I am human" in selector:
                        await element.click()
                        await self.page.wait_for_timeout(3000)
                    elif 'verify' in selector.lower():
                        await element.click()
                        await self.page.wait_for_timeout(3000)
                    else:
                        # Generic verification handling
                        await element.click()
                        await self.page.wait_for_timeout(2000)
                    
                    return True
                    
            except Exception as e:
                logger.debug(f"Verification check failed for {selector}: {e}")
                continue
        
        return False
    
    async def _handle_press_and_hold(self, element):
        """Handle press-and-hold verification (Browser Use's biggest failure)"""
        try:
            logger.info("🔘 Attempting press-and-hold verification...")
            
            # Method 1: Mouse down and hold
            box = await element.bounding_box()
            if box:
                x = box['x'] + box['width'] / 2
                y = box['y'] + box['height'] / 2
                
                await self.page.mouse.move(x, y)
                await self.page.mouse.down()
                await asyncio.sleep(5)  # Hold for 5 seconds
                await self.page.mouse.up()
                
                logger.info("✅ Press-and-hold completed")
            
        except Exception as e:
            logger.warning(f"⚠️ Press-and-hold failed: {e}")
    
    async def _take_strategic_screenshots(self, strategy: Dict, retailer: str) -> Dict[str, bytes]:
        """Take multiple strategic screenshots for comprehensive analysis"""
        screenshots = {}
        screenshot_types = strategy.get('screenshots', ['full_page'])
        scroll_positions = strategy.get('scroll_positions', [0, 0.5, 1.0])
        
        logger.info(f"📸 Taking {len(screenshot_types)} types of screenshots")
        
        try:
            # Full page screenshot first
            if 'full_page' in screenshot_types:
                screenshot = await self.page.screenshot(full_page=True, type='png')
                screenshots['full_page'] = screenshot
                logger.debug("✅ Full page screenshot captured")
            
            # Viewport screenshots at different scroll positions
            for i, position in enumerate(scroll_positions):
                await self._scroll_to_position(position)
                await asyncio.sleep(1)  # Let content load
                
                screenshot = await self.page.screenshot(type='png')
                screenshots[f'viewport_scroll_{position}'] = screenshot
                logger.debug(f"✅ Viewport screenshot captured at scroll {position}")
            
            # Specific element screenshots if selectors are available
            element_selectors = {
                'main_image': '.product-image, .hero-image, .main-image, [data-testid="product-image"]',
                'product_details': '.product-details, .product-info, .product-description',
                'price_section': '.price, .product-price, .pricing',
                'image_gallery': '.image-gallery, .product-images, .carousel'
            }
            
            for screenshot_type in screenshot_types:
                if screenshot_type in element_selectors:
                    selector = element_selectors[screenshot_type]
                    try:
                        element = await self.page.query_selector(selector)
                        if element:
                            screenshot = await element.screenshot(type='png')
                            screenshots[screenshot_type] = screenshot
                            logger.debug(f"✅ Element screenshot captured: {screenshot_type}")
                    except Exception as e:
                        logger.debug(f"Element screenshot failed for {screenshot_type}: {e}")
            
            logger.info(f"📸 Captured {len(screenshots)} screenshots total")
            return screenshots
            
        except Exception as e:
            logger.error(f"❌ Screenshot capture failed: {e}")
            raise
    
    async def _scroll_to_position(self, position: float):
        """Scroll to specific position on page (0.0 = top, 1.0 = bottom)"""
        try:
            await self.page.evaluate(f"""
                window.scrollTo({{
                    top: document.body.scrollHeight * {position},
                    behavior: 'smooth'
                }});
            """)
        except Exception as e:
            logger.debug(f"Scroll to {position} failed: {e}")
    
    async def _analyze_with_gemini(self, screenshots: Dict[str, bytes], url: str, retailer: str) -> ProductData:
        """Analyze screenshots with Gemini 2.0 Flash and enhanced visual analysis"""
        try:
            # Convert screenshots to PIL Images
            images = []
            screenshot_types = list(screenshots.keys())
            
            for screenshot_type, screenshot_data in screenshots.items():
                try:
                    image = Image.open(io.BytesIO(screenshot_data))
                    images.append(image)
                except Exception as e:
                    logger.warning(f"Failed to process {screenshot_type} screenshot: {e}")
                    continue
            
            if not images:
                raise ValueError("No valid screenshots to analyze")
            
            # Build analysis prompt
            prompt = self._build_analysis_prompt(url, retailer, screenshot_types)
            
            # Call Gemini with all screenshots
            response = await self._call_gemini_with_images(prompt, images)
            
            # Parse response into ProductData
            product_data = self._parse_gemini_response(response, retailer)
            
            # If we have image URLs from the analysis, perform enhanced visual analysis
            if hasattr(product_data, 'image_urls') and product_data.image_urls:
                logger.info(f"Performing enhanced visual analysis for {retailer}")
                enhanced_data = await self._perform_enhanced_visual_analysis(
                    screenshots, product_data.image_urls, retailer, url
                )
                
                # Create new ProductData with enhanced information
                product_data = ProductData(
                    title=enhanced_data.get('title', ''),
                    brand=enhanced_data.get('brand', ''),
                    price=enhanced_data.get('price'),
                    original_price=enhanced_data.get('original_price'),
                    description=enhanced_data.get('description', ''),
                    stock_status=enhanced_data.get('stock_status', ''),
                    sale_status=enhanced_data.get('sale_status', ''),
                    clothing_type=enhanced_data.get('clothing_type', ''),
                    product_code=enhanced_data.get('product_code', ''),
                    image_urls=enhanced_data.get('image_urls', []),
                    retailer=retailer,
                    colors=enhanced_data.get('colors', []),
                    sizes=enhanced_data.get('sizes', []),
                    material=enhanced_data.get('material', ''),
                    care_instructions=enhanced_data.get('care_instructions', ''),
                    neckline=enhanced_data.get('neckline', ''),
                    sleeve_length=enhanced_data.get('sleeve_length', ''),
                    visual_analysis_confidence=enhanced_data.get('visual_analysis_confidence'),
                    visual_analysis_source=enhanced_data.get('visual_analysis_source', '')
                )
            
            return product_data
            
        except Exception as e:
            logger.error(f"❌ Gemini analysis failed: {e}")
            raise
    
    def _build_analysis_prompt(self, url: str, retailer: str, screenshot_types: List[str]) -> str:
        """Build comprehensive analysis prompt for Gemini"""
        return f"""
You are analyzing a clothing product page from {retailer}. URL: {url}

I'm providing {len(screenshot_types)} screenshots: {', '.join(screenshot_types)}

Extract ALL available product information and return as JSON with this exact structure:

{{
    "title": "Full product name",
    "brand": "Brand name",
    "price": 99.99,
    "original_price": 149.99,
    "description": "Full product description",
    "stock_status": "in_stock/low_stock/out_of_stock",
    "sale_status": "on_sale/regular_price",
    "clothing_type": "dress/top/bottom/etc",
    "product_code": "SKU or product ID",
    "image_urls": ["url1", "url2", "url3"],
    "colors": ["color1", "color2"],
    "sizes": ["XS", "S", "M", "L", "XL"],
    "material": "fabric composition",
    "care_instructions": "washing instructions",
    "neckline": "crew/v-neck/scoop/off-shoulder/halter/strapless/boat/square/sweetheart/mock/turtleneck/cowl/other/unknown",
    "sleeve_length": "sleeveless/cap/short/3-quarter/long/other/unknown",
    "retailer": "{retailer}"
}}

CRITICAL REQUIREMENTS:
1. NECKLINE & SLEEVE ANALYSIS:
   - First check if neckline/sleeve info is mentioned in text on the page
   - If not in text, analyze the main product images carefully
   - Use "unknown" if cannot determine with confidence
   - Valid necklines: crew, v-neck, scoop, off-shoulder, halter, strapless, boat, square, sweetheart, mock, turtleneck, cowl, other, unknown
   - Valid sleeve lengths: sleeveless, cap, short, 3-quarter, long, other, unknown

2. IMAGE PRIORITY - Extract high-quality product images:
   - Look for URLs containing: 'large', 'full', 'original', 'main', 'front', 'zoom'
   - Avoid: 'thumb', 'small', 'preview' in URLs
   - For {retailer}: Focus on main product shots showing neckline and sleeves clearly

3. PRICING - Be precise:
   - Extract exact price format (e.g., "$29.99")
   - If on sale: current price in "price", original price in "original_price"
   - If not on sale: current price in "price", null in "original_price"

4. VALIDATION - Ensure all fields are populated with meaningful data

Focus on extracting comprehensive product data and ALL available image URLs, with special attention to neckline and sleeve details.
"""
    
    async def _call_gemini_with_images(self, prompt: str, images: List[Image.Image]) -> str:
        """Make single Gemini API call with all images using langchain"""
        try:
            # Convert images to base64 for langchain
            image_content = []
            
            for image in images:
                # Convert PIL Image to bytes
                img_byte_arr = io.BytesIO()
                image.save(img_byte_arr, format='PNG')
                img_byte_arr = img_byte_arr.getvalue()
                
                # Convert to base64
                img_base64 = base64.b64encode(img_byte_arr).decode('utf-8')
                
                image_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{img_base64}"
                    }
                })
            
            # Prepare message with text and images
            content = [{"type": "text", "text": prompt}] + image_content
            
            message = HumanMessage(content=content)
            
            # Call Gemini via langchain
            response = await asyncio.to_thread(self.model.invoke, [message])
            
            return response.content
            
        except Exception as e:
            logger.error(f"Gemini API call failed: {e}")
            raise
    
    def _parse_gemini_response(self, response: str, retailer: str) -> ProductData:
        """Parse Gemini response into ProductData object"""
        try:
            # Extract JSON from response with better error handling
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                logger.warning(f"No JSON found in Gemini response for {retailer}")
                logger.debug(f"Response content: {response[:200]}...")
                raise ValueError("No JSON found in response")
            
            json_str = response[json_start:json_end]
            
            # Clean up common JSON issues
            json_str = re.sub(r',\s*}', '}', json_str)  # Remove trailing commas
            json_str = re.sub(r',\s*]', ']', json_str)  # Remove trailing commas in arrays
            
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.warning(f"JSON decode error for {retailer}: {e}")
                logger.debug(f"Malformed JSON: {json_str[:300]}...")
                
                # Try to fix common JSON issues
                json_str = json_str.replace('\n', ' ').replace('\r', ' ')
                json_str = re.sub(r'\s+', ' ', json_str)
                
                try:
                    data = json.loads(json_str)
                except json.JSONDecodeError:
                    # Last resort: create basic product data
                    title_match = re.search(r'"title"\s*:\s*"([^"]+)"', json_str)
                    title = title_match.group(1) if title_match else "Product"
                    
                    data = {
                        "title": title,
                        "retailer": retailer,
                        "price": None,
                        "image_urls": []
                    }
            
            # Process and standardize the data using the same logic as the old system
            processed_data = self._process_extracted_data(data, retailer)
            
            # Ensure price is a proper format for Shopify (string)
            price = processed_data.get('price')
            if isinstance(price, (int, float)) and price > 0:
                processed_data['price'] = f"{price:.2f}"
            elif not price:
                processed_data['price'] = "0.00"
            
            original_price = processed_data.get('original_price')
            if isinstance(original_price, (int, float)) and original_price > 0:
                processed_data['original_price'] = f"{original_price:.2f}"
            
            # Create ProductData object with processed data
            product_data = ProductData(
                title=processed_data.get('title', ''),
                brand=processed_data.get('brand', ''),
                price=processed_data.get('price'),
                original_price=processed_data.get('original_price'),
                description=processed_data.get('description', ''),
                stock_status=processed_data.get('stock_status', ''),
                sale_status=processed_data.get('sale_status', ''),
                clothing_type=processed_data.get('clothing_type', ''),
                product_code=processed_data.get('product_code', ''),
                image_urls=processed_data.get('image_urls', []),
                retailer=retailer,
                colors=processed_data.get('colors', []),
                sizes=processed_data.get('sizes', []),
                material=processed_data.get('material', ''),
                care_instructions=processed_data.get('care_instructions', ''),
                neckline=processed_data.get('neckline', ''),
                sleeve_length=processed_data.get('sleeve_length', ''),
                visual_analysis_confidence=processed_data.get('visual_analysis_confidence'),
                visual_analysis_source=processed_data.get('visual_analysis_source', '')
            )
            
            return product_data
            
        except Exception as e:
            logger.error(f"Failed to parse Gemini response for {retailer}: {e}")
            logger.debug(f"Response was: {response[:500]}...")
            
            # Return minimal ProductData on parse failure
            return ProductData(
                title="Parse Error",
                retailer=retailer,
                price="0.00"  # Ensure valid price format
            )
    
    def _process_extracted_data(self, data: dict, retailer: str) -> dict:
        """Apply retailer-specific data cleaning and formatting (from old system)"""
        
        # Ensure data is a dictionary
        if not isinstance(data, dict):
            logger.warning(f"Expected dict but got {type(data)}: {data}")
            data = {
                "retailer": retailer,
                "title": "Extracted Product",
                "raw_output": str(data)
            }
        
        processed = data.copy()
        
        # Clean price formats
        if 'price' in processed:
            processed['price'] = self._clean_price_format(processed['price'], retailer)
        
        if 'original_price' in processed:
            processed['original_price'] = self._clean_price_format(processed['original_price'], retailer)
        
        # Special handling for Uniqlo - they don't show original prices during sales
        if retailer == 'uniqlo':
            sale_status = processed.get('sale_status', '')
            # Handle both boolean and string sale_status
            is_on_sale = False
            if isinstance(sale_status, bool):
                is_on_sale = sale_status
            elif isinstance(sale_status, str) and sale_status and 'sale' in sale_status.lower():
                is_on_sale = True
            
            if is_on_sale:
                # If item is on sale but no original price provided, set to None
                if not processed.get('original_price'):
                    processed['original_price'] = None
                    logger.debug(f"Uniqlo sale item without original price: {processed.get('title', 'Unknown')}")
        
        # Clean title
        if 'title' in processed:
            processed['title'] = self._clean_title_format(processed['title'], retailer)
        
        # Clean brand
        if 'brand' in processed:
            processed['brand'] = self._clean_brand_format(processed['brand'], retailer)
        
        # Standardize status fields
        if 'stock_status' in processed:
            processed['stock_status'] = self._standardize_stock_status(processed['stock_status'])
        
        if 'sale_status' in processed:
            processed['sale_status'] = self._standardize_sale_status(processed['sale_status'])
        
        if 'clothing_type' in processed:
            processed['clothing_type'] = self._standardize_clothing_type(processed['clothing_type'])
        
        # Validate retailer name
        processed['retailer'] = retailer  # Ensure consistency
        
        return processed
    
    def _clean_price_format(self, price_string, retailer: str) -> Optional[float]:
        """Clean and validate price format (from old system)"""
        if not price_string:
            return None
        
        # Handle numeric input
        if isinstance(price_string, (int, float)):
            return float(price_string) if price_string > 0 else None
        
        # Retailer-specific price patterns
        patterns = {
            "aritzia": r'CAD\s*\$?(\d+(?:\.\d{2})?)',
            "mango": r'US\$\s*(\d+(?:[.,]\d{2})?)|(\d+(?:[.,]\d{2})?)\s*€',
            "hm": r'£(\d+(?:\.\d{2})?)|\$(\d+(?:\.\d{2})?)',
            "revolve": r'\$(\d+(?:\.\d{2})?)',
            "nordstrom": r'\$(\d+(?:\.\d{2})?)',
            "anthropologie": r'\$(\d+(?:\.\d{2})?)',
            "default": r'[\$£€]?(\d+(?:[.,]\d{2})?)'
        }
        
        pattern = patterns.get(retailer, patterns["default"])
        
        # Clean the price string
        import re
        clean_price = str(price_string).replace(',', '').replace(' ', '')
        
        match = re.search(pattern, clean_price)
        
        if match:
            try:
                # Get the first non-None group
                price_value = next((group for group in match.groups() if group is not None), None)
                if price_value:
                    return float(price_value.replace(',', '.'))
            except (ValueError, AttributeError):
                pass
        
        # Fallback: try to extract any number
        fallback_match = re.search(r'(\d+(?:[.,]\d{2})?)', clean_price)
        if fallback_match:
            try:
                return float(fallback_match.group(1).replace(',', '.'))
            except ValueError:
                pass
        
        return None
    
    def _clean_title_format(self, title: str, retailer: str) -> str:
        """Clean retailer-specific title formats (from old system)"""
        if not title:
            return ""
        
        import re
        # Remove retailer suffixes
        cleaning_rules = {
            "aritzia": lambda t: re.sub(r'\s+\|\s+Aritzia.*$', '', t),
            "asos": lambda t: re.sub(r'\s+\|\s+ASOS.*$', '', t),
            "hm": lambda t: re.sub(r'\s+-\s+H&M.*$', '', t),
        }
        
        cleaner = cleaning_rules.get(retailer, lambda t: t)
        return cleaner(title).strip()
    
    def _clean_brand_format(self, brand: str, retailer: str) -> str:
        """Clean and validate brand names (from old system)"""
        if not brand:
            return retailer.title()
        
        import re
        # Remove retailer suffixes and validate
        brand = re.sub(r'\s+\|\s+.*$', '', brand).strip()
        
        # Retailer-specific brand validation
        valid_brands = {
            "aritzia": ["Aritzia", "TNA", "Wilfred", "Babaton"],
            "hm": ["H&M"],
            "uniqlo": ["Uniqlo"],
            "mango": ["Mango"]
        }
        
        if retailer in valid_brands:
            if brand.lower() not in [b.lower() for b in valid_brands[retailer]]:
                return valid_brands[retailer][0]  # Default to main brand
        
        return brand
    
    def _standardize_stock_status(self, status) -> str:
        """Standardize stock status - handles various input types (from old system)"""
        if status is None:
            return "in stock"
        
        # Handle boolean input (True = in stock, False = out of stock)
        if isinstance(status, bool):
            return 'in stock' if status else 'out of stock'
        
        # Handle string input
        if not isinstance(status, str):
            status = str(status)
        
        status_lower = status.lower()
        
        if any(indicator in status_lower for indicator in 
               ['sold out', 'unavailable', 'out of stock']):
            return 'out of stock'
        elif any(indicator in status_lower for indicator in 
                 ['few left', 'limited', 'low stock', 'almost gone']):
            return 'low in stock'
        else:
            return 'in stock'
    
    def _standardize_sale_status(self, status) -> str:
        """Standardize sale status - handles both string and boolean inputs (from old system)"""
        if status is None:
            return "not on sale"
        
        # Handle boolean input
        if isinstance(status, bool):
            return 'on sale' if status else 'not on sale'
        
        # Handle string input
        if not isinstance(status, str):
            status = str(status)
        
        sale_indicators = ['sale', 'clearance', 'reduced', 'discount', 'marked down', 'on sale']
        
        if any(indicator in status.lower() for indicator in sale_indicators):
            return 'on sale'
        return 'not on sale'
    
    def _standardize_clothing_type(self, clothing_type: str) -> str:
        """Standardize clothing type categories (from old system)"""
        if not clothing_type:
            return "clothing"
        
        type_mapping = {
            'dresses': 'dress',
            'dress tops': 'dress top',        # NEW - normalize plural to singular
            'dress-tops': 'dress top',        # NEW - handle hyphenated version
            'tops & tees': 'top',
            'blouses': 'top',
            'shirts': 'top',
            'sweaters': 'top',
            'pants': 'bottom',
            'jeans': 'bottom',
            'skirts': 'bottom',
            'shorts': 'bottom',
            'jackets': 'outerwear',
            'coats': 'outerwear',
            'blazers': 'outerwear'
        }
        
        clothing_type_lower = clothing_type.lower()
        for key, value in type_mapping.items():
            if key in clothing_type_lower:
                return value
        
        return clothing_type.lower()
    
    async def _reset_browser_context(self):
        """Reset browser context for fresh retry"""
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                self.context = await self.browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                )
                self.page = await self.context.new_page()
                
                if self.stealth_available:
                    from playwright_stealth import stealth_async
                    await stealth_async(self.page)
                
        except Exception as e:
            logger.warning(f"Browser context reset failed: {e}")
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL for strategy lookup"""
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc
            return domain.replace('www.', '')
        except:
            return 'unknown'
    
    async def _cleanup(self):
        """Clean up Patchright persistent context resources"""
        try:
            # Persistent context cleanup - context handles everything
            if self.context:
                await self.context.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception as e:
            logger.warning(f"Cleanup failed: {e}")
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self._cleanup()

    async def test_patchright_stealth(self):
        """Test Patchright anti-detection capabilities"""
        try:
            if not self.context:
                await self._setup_stealth_browser()
            
            page = await self.context.new_page()
            
            # Test detection resistance
            logger.info("🧪 Testing Patchright stealth capabilities...")
            await page.goto("https://bot.sannysoft.com/")
            await page.wait_for_timeout(3000)
            
            # Check results
            title = await page.title()
            logger.info(f"🔍 Stealth test result: {title}")
            
            # Check for specific detection indicators
            try:
                # Look for automation detection
                automation_detected = await page.locator('text="Automated"').count()
                headless_detected = await page.locator('text="Headless"').count()
                webdriver_detected = await page.locator('text="WebDriver"').count()
                
                logger.info(f"🔍 Detection results:")
                logger.info(f"   - Automation detected: {automation_detected > 0}")
                logger.info(f"   - Headless detected: {headless_detected > 0}")
                logger.info(f"   - WebDriver detected: {webdriver_detected > 0}")
                
                if automation_detected == 0 and headless_detected == 0 and webdriver_detected == 0:
                    logger.info("✅ Patchright stealth test: PASSED - Not detected as bot")
                else:
                    logger.warning("⚠️ Patchright stealth test: Some detection indicators found")
                    
            except Exception as e:
                logger.warning(f"Could not parse detection results: {e}")
            
            await page.close()
            return True
            
        except Exception as e:
            logger.error(f"Stealth test failed: {e}")
            return False

    async def save_screenshots_as_fallback(self, url: str, retailer: str, product_code: str) -> List[str]:
        """
        NEW FEATURE: Save Playwright screenshots as fallback images
        This provides a backup when image URL extraction/processing fails
        """
        logger.info(f"🖼️ Saving Playwright screenshots as image fallback for {retailer}")
        
        try:
            # Setup browser if not already done
            if not self.browser:
                await self._setup_stealth_browser()
            
            # Navigate to the product page
            domain = self._extract_domain(url)
            strategy = self.screenshot_strategies.get(domain, {})
            
            await self.page.goto(url, wait_until='load', timeout=30000)
            await self._wait_for_content(strategy)
            
            # Take high-quality product screenshots
            screenshot_paths = []
            downloads_dir = "downloads"
            os.makedirs(downloads_dir, exist_ok=True)
            
            # Full page screenshot
            full_page_path = f"{downloads_dir}/{retailer}_{product_code}_full_page.png"
            await self.page.screenshot(path=full_page_path, full_page=True, type='png')
            screenshot_paths.append(full_page_path)
            logger.info(f"📸 Saved full page screenshot: {full_page_path}")
            
            # Main product element screenshot (if available)
            product_selectors = [
                '.product-image', '.hero-image', '.main-image',
                '[data-testid="product-image"]', '.product-gallery img'
            ]
            
            for selector in product_selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element:
                        element_path = f"{downloads_dir}/{retailer}_{product_code}_product_element.png"
                        await element.screenshot(path=element_path, type='png')
                        screenshot_paths.append(element_path)
                        logger.info(f"📸 Saved product element screenshot: {element_path}")
                        break
                except:
                    continue
            
            # Viewport screenshots at different scroll positions
            scroll_positions = [0, 0.3, 0.7]
            for i, position in enumerate(scroll_positions):
                await self._scroll_to_position(position)
                await asyncio.sleep(1)
                
                viewport_path = f"{downloads_dir}/{retailer}_{product_code}_viewport_{i}.png"
                await self.page.screenshot(path=viewport_path, type='png')
                screenshot_paths.append(viewport_path)
                logger.info(f"📸 Saved viewport screenshot: {viewport_path}")
            
            logger.info(f"✅ Saved {len(screenshot_paths)} fallback screenshots for {retailer}")
            return screenshot_paths
            
        except Exception as e:
            logger.error(f"❌ Failed to save screenshot fallback: {e}")
            return []
    
    async def get_screenshot_as_base64(self, element_selector: str = None) -> str:
        """
        Get a screenshot as base64 for immediate use
        Useful for real-time image processing fallback
        """
        try:
            if element_selector:
                element = await self.page.query_selector(element_selector)
                if element:
                    screenshot_bytes = await element.screenshot(type='png')
                else:
                    screenshot_bytes = await self.page.screenshot(type='png')
            else:
                screenshot_bytes = await self.page.screenshot(type='png')
            
            import base64
            return base64.b64encode(screenshot_bytes).decode('utf-8')
            
        except Exception as e:
            logger.error(f"Failed to capture screenshot as base64: {e}")
            return ""

    async def _extract_image_urls_from_dom(self, retailer: str) -> List[str]:
        """Extract image URLs directly from DOM elements"""
        try:
            # Retailer-specific image selectors
            image_selectors = {
                'aritzia': [
                    'img[src*="media.aritzia.com"]',
                    '.product-images img',
                    '.product-carousel img',
                    'img[data-src*="aritzia"]'
                ],
                'urban_outfitters': [
                    'img[src*="urbanoutfitters.com"]',
                    '.product-image img',
                    '.carousel-item img',
                    'img[data-src*="urbanoutfitters"]'
                ],
                'abercrombie': [
                    'img[src*="abercrombie.com"]',
                    'img[src*="anf.scene7.com"]',
                    '.product-images img',
                    'img[data-src*="abercrombie"]'
                ],
                'anthropologie': [
                    'img[src*="anthropologie.com"]',
                    'img[src*="assets.anthropologie.com"]',
                    '.product-images img',
                    'img[data-src*="anthropologie"]'
                ],
                'nordstrom': [
                    'img[src*="nordstrommedia.com"]',
                    '.product-media img',
                    'img[data-src*="nordstrom"]'
                ]
            }
            
            # Generic fallback selectors
            generic_selectors = [
                'img[src*="product"]',
                'img[src*="image"]',
                'img[src*="media"]',
                '.product img',
                '.product-image img',
                '.product-photo img',
                'img[data-src]',
                'img[src]:not([src*="icon"]):not([src*="logo"])'
            ]
            
            selectors = image_selectors.get(retailer, []) + generic_selectors
            image_urls = []
            
            for selector in selectors:
                try:
                    # Get all matching elements
                    elements = await self.page.query_selector_all(selector)
                    
                    for element in elements:
                        # Try to get src or data-src
                        src = await element.get_attribute('src')
                        if not src:
                            src = await element.get_attribute('data-src')
                        if not src:
                            src = await element.get_attribute('data-original')
                        
                        if src and self._is_valid_product_image_url(src, retailer):
                            # Convert relative URLs to absolute
                            if src.startswith('//'):
                                src = 'https:' + src
                            elif src.startswith('/'):
                                base_url = await self.page.evaluate('() => window.location.origin')
                                src = base_url + src
                            
                            if src not in image_urls:
                                image_urls.append(src)
                    
                    # Stop if we have enough images
                    if len(image_urls) >= 10:
                        break
                        
                except Exception as e:
                    logger.debug(f"Error with selector {selector}: {e}")
                    continue
            
            # Filter and rank images by quality indicators
            quality_images = self._rank_image_urls(image_urls, retailer)
            
            logger.info(f"🖼️ DOM extracted {len(quality_images)} image URLs for {retailer}")
            return quality_images[:5]  # Return top 5 images
            
        except Exception as e:
            logger.error(f"Error extracting images from DOM: {e}")
            return []
    
    def _is_valid_product_image_url(self, url: str, retailer: str) -> bool:
        """Check if URL is likely a valid product image"""
        if not url or len(url) < 10:
            return False
        
        url_lower = url.lower()
        
        # Exclude obvious non-product images
        exclude_patterns = [
            'icon', 'logo', 'badge', 'button', 'banner', 'header', 'footer',
            'star', 'rating', 'arrow', 'chevron', '1x1', 'spacer', 'pixel',
            'thumb', 'avatar', 'profile', 'social'
        ]
        
        if any(pattern in url_lower for pattern in exclude_patterns):
            return False
        
        # Must be an image file or have image-like URL structure
        image_indicators = [
            '.jpg', '.jpeg', '.png', '.webp', '.gif',
            'image', 'img', 'photo', 'picture', 'product', 'media'
        ]
        
        if not any(indicator in url_lower for indicator in image_indicators):
            return False
        
        # Retailer-specific validation
        retailer_domains = {
            'aritzia': ['aritzia.com', 'media.aritzia.com'],
            'urban_outfitters': ['urbanoutfitters.com', 'images.urbanoutfitters.com'],
            'abercrombie': ['abercrombie.com', 'anf.scene7.com'],
            'anthropologie': ['anthropologie.com', 'assets.anthropologie.com'],
            'nordstrom': ['nordstrom.com', 'nordstrommedia.com']
        }
        
        valid_domains = retailer_domains.get(retailer, [retailer + '.com'])
        if not any(domain in url_lower for domain in valid_domains):
            return False
        
        return True
    
    def _rank_image_urls(self, image_urls: List[str], retailer: str) -> List[str]:
        """Rank image URLs by quality indicators"""
        if not image_urls:
            return []
        
        scored_images = []
        
        for url in image_urls:
            score = 0
            url_lower = url.lower()
            
            # Size indicators (higher is better)
            if any(size in url_lower for size in ['1200', '1500', '2000', '1024', '800']):
                score += 30
            elif any(size in url_lower for size in ['600', '500', '400']):
                score += 15
            elif any(size in url_lower for size in ['300', '200', '150']):
                score -= 10
            
            # Quality indicators
            if any(qual in url_lower for qual in ['large', 'big', 'xl', 'high', 'zoom']):
                score += 20
            if any(qual in url_lower for qual in ['small', 'thumb', 'mini']):
                score -= 20
            
            # Product relevance
            if any(prod in url_lower for prod in ['product', 'main', 'front', 'detail']):
                score += 10
            if any(bad in url_lower for bad in ['swatch', 'color', 'fabric']):
                score -= 15
            
            scored_images.append((score, url))
        
        # Sort by score (descending) and return URLs
        scored_images.sort(key=lambda x: x[0], reverse=True)
        return [url for score, url in scored_images]

    async def _perform_enhanced_visual_analysis(self, screenshots: Dict[str, bytes], image_urls: List[str], 
                                              retailer: str, url: str) -> Dict[str, Any]:
        """Enhanced visual analysis with smart text + image analysis"""
        
        try:
            # Step 1: Primary analysis with screenshots (includes text analysis)
            primary_data = await self._analyze_with_gemini(screenshots, url, retailer)
            
            # Step 2: Check if visual details were found in text/screenshots
            neckline = getattr(primary_data, 'neckline', '') or ''
            sleeve_length = getattr(primary_data, 'sleeve_length', '') or ''
            
            # Step 3: If visual details missing and we have good product images, do focused image analysis
            if (neckline in ['', 'unknown'] or sleeve_length in ['', 'unknown']) and image_urls:
                logger.info(f"Visual details incomplete for {retailer}, performing focused image analysis")
                
                # Download and analyze the best product image
                focused_analysis = await self._analyze_product_images_for_details(image_urls, retailer, url)
                
                # Merge results with confidence tracking
                if focused_analysis:
                    if neckline in ['', 'unknown'] and focused_analysis.get('neckline'):
                        neckline = focused_analysis['neckline']
                    if sleeve_length in ['', 'unknown'] and focused_analysis.get('sleeve_length'):
                        sleeve_length = focused_analysis['sleeve_length']
                    
                    # Set confidence and source
                    visual_confidence = focused_analysis.get('confidence', 0.5)
                    visual_source = "combined" if (getattr(primary_data, 'neckline', '') not in ['', 'unknown'] or 
                                                  getattr(primary_data, 'sleeve_length', '') not in ['', 'unknown']) else "image_analysis"
                else:
                    visual_confidence = 0.7 if (neckline not in ['', 'unknown'] or sleeve_length not in ['', 'unknown']) else 0.3
                    visual_source = "webpage_text"
            else:
                # Found in text/screenshots
                visual_confidence = 0.8
                visual_source = "webpage_text"
            
            # Step 4: Update primary data with enhanced visual analysis
            enhanced_data = primary_data.__dict__.copy()
            enhanced_data.update({
                'neckline': neckline,
                'sleeve_length': sleeve_length,
                'visual_analysis_confidence': visual_confidence,
                'visual_analysis_source': visual_source
            })
            
            logger.info(f"Enhanced visual analysis complete: neckline={neckline}, sleeve_length={sleeve_length}, confidence={visual_confidence}")
            return enhanced_data
            
        except Exception as e:
            logger.error(f"Enhanced visual analysis failed: {e}")
            # Return basic data without visual enhancements
            return primary_data.__dict__ if hasattr(primary_data, '__dict__') else {}

    async def _analyze_product_images_for_details(self, image_urls: List[str], retailer: str, url: str) -> Optional[Dict]:
        """Focused image analysis for neckline and sleeve details"""
        
        try:
            # Select best image for analysis (prefer main product shots)
            best_image_url = self._select_best_image_for_analysis(image_urls, retailer)
            if not best_image_url:
                return None
            
            # Download and prepare image
            import aiohttp
            from PIL import Image
            import io
            
            async with aiohttp.ClientSession() as session:
                async with session.get(best_image_url) as response:
                    if response.status == 200:
                        image_data = await response.read()
                        image = Image.open(io.BytesIO(image_data))
                        
                        # Resize if too large (cost optimization)
                        max_size = (800, 800)
                        if image.size[0] > max_size[0] or image.size[1] > max_size[1]:
                            image.thumbnail(max_size, Image.Resampling.LANCZOS)
                        
                        # Focused prompt for visual details only
                        focused_prompt = f"""
Analyze this clothing product image and identify ONLY the neckline and sleeve length.

Return JSON format:
{{
    "neckline": "crew/v-neck/scoop/off-shoulder/halter/strapless/boat/square/sweetheart/mock/turtleneck/cowl/other/unknown",
    "sleeve_length": "sleeveless/cap/short/3-quarter/long/other/unknown",
    "confidence": 0.0-1.0
}}

Focus only on what you can clearly see. Use "unknown" if unclear.
Valid necklines: crew, v-neck, scoop, off-shoulder, halter, strapless, boat, square, sweetheart, mock, turtleneck, cowl, other, unknown
Valid sleeve lengths: sleeveless, cap, short, 3-quarter, long, other, unknown
"""
                        
                        # Call Gemini with single image
                        response = await self._call_gemini_with_images(focused_prompt, [image])
                        
                        # Parse focused response
                        return self._parse_focused_visual_response(response)
            
        except Exception as e:
            logger.error(f"Focused image analysis failed: {e}")
            return None

    def _select_best_image_for_analysis(self, image_urls: List[str], retailer: str) -> Optional[str]:
        """Select the best image for visual analysis"""
        
        if not image_urls:
            return None
        
        # Scoring criteria for best analysis image
        scored_images = []
        
        for url in image_urls[:3]:  # Limit to first 3 to control costs
            score = 0
            url_lower = url.lower()
            
            # Prefer main/front product shots
            if any(keyword in url_lower for keyword in ['main', 'front', 'primary', 'hero']):
                score += 10
            
            # Prefer high-res images
            if any(keyword in url_lower for keyword in ['large', 'xl', 'full', 'zoom', '800', '1000']):
                score += 5
            
            # Avoid detail shots that might not show full garment
            if any(keyword in url_lower for keyword in ['detail', 'close', 'fabric', 'texture']):
                score -= 5
            
            # Retailer-specific preferences
            if retailer == 'asos' and '$XXL$' in url:
                score += 3
            elif retailer == 'uniqlo' and 'goods' in url:
                score += 3
            elif retailer == 'aritzia' and any(dim in url for dim in ['800', '1000']):
                score += 3
            
            scored_images.append((score, url))
        
        # Return highest scoring image
        if scored_images:
            scored_images.sort(reverse=True)
            return scored_images[0][1]
        
        return image_urls[0]  # Fallback to first image

    def _parse_focused_visual_response(self, response: str) -> Optional[Dict]:
        """Parse focused visual analysis response"""
        
        try:
            # Extract JSON from response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                return None
            
            json_str = response[json_start:json_end]
            data = json.loads(json_str)
            
            # Validate fields
            valid_necklines = ['crew', 'v-neck', 'scoop', 'off-shoulder', 'halter', 'strapless', 
                             'boat', 'square', 'sweetheart', 'mock', 'turtleneck', 'cowl', 'other', 'unknown']
            valid_sleeves = ['sleeveless', 'cap', 'short', '3-quarter', 'long', 'other', 'unknown']
            
            neckline = data.get('neckline', 'unknown')
            sleeve_length = data.get('sleeve_length', 'unknown')
            confidence = float(data.get('confidence', 0.5))
            
            # Validate values
            if neckline not in valid_necklines:
                neckline = 'unknown'
            if sleeve_length not in valid_sleeves:
                sleeve_length = 'unknown'
            
            return {
                'neckline': neckline,
                'sleeve_length': sleeve_length,
                'confidence': max(0.0, min(1.0, confidence))
            }
            
        except Exception as e:
            logger.error(f"Failed to parse focused visual response: {e}")
            return None


# Integration with existing system
    async def _extract_catalog_product_links_from_dom(self, retailer: str) -> List[Dict]:
        """
        Extract product URLs, codes, AND validation data from DOM
        - URLs/codes: Critical for deduplication (Gemini can't read these)
        - Titles/prices: Optional validation data to double-check Gemini's visual extraction
        Returns list of {url, product_code, position, dom_title, dom_price}
        """
        try:
            product_links = []
            
            # Retailer-specific product link selectors (learned patterns + common patterns)
            selectors = []
            
            # Get learned patterns first
            learned_patterns = self.structure_learner.get_best_patterns(retailer, element_type='product_link')
            if learned_patterns:
                selectors.extend([p['pattern_data'] for p in learned_patterns if p['confidence_score'] > 0.7])
            
            # Add common catalog product link patterns
            selectors.extend([
                # Abercrombie specific
                'a[data-testid="product-card-link"]',
                # Generic patterns
                'a[href*="/product"]', 'a[href*="/p/"]', 'a[href*="/dp/"]',
                '.product-card a', '.product-item a', '[data-product-id]',
                'a.product-link', 'a.product-tile', 'a[data-product-url]',
                'a[href*="/shop/"]', 'a[href*="/item/"]', 'a[href*="/goods/"]'
            ])
            
            # Try each selector
            for selector in selectors:
                try:
                    links = await self.page.query_selector_all(selector)
                    if links and len(links) > 5:  # If we found a good set of product links
                        logger.debug(f"Found {len(links)} product links with selector: {selector}")
                        
                        for idx, link in enumerate(links[:100]):  # Limit to 100 products per page
                            href = await link.get_attribute('href')
                            if href:
                                # Make absolute URL if relative
                                if href.startswith('/'):
                                    parsed = urlparse(await self.page.url)
                                    href = f"{parsed.scheme}://{parsed.netloc}{href}"
                                elif not href.startswith('http'):
                                    continue  # Skip invalid URLs
                                
                                # Extract product code from URL
                                from markdown_extractor import MarkdownExtractor
                                extractor = MarkdownExtractor()
                                product_code = extractor._extract_product_code_from_url(href)
                                
                                # ENHANCEMENT: Try to extract title and price from DOM for validation
                                dom_title = None
                                dom_price = None
                                
                                try:
                                    # Try to find parent product card container
                                    parent = link
                                    for _ in range(3):  # Search up to 3 levels
                                        parent = await parent.evaluate_handle('el => el.parentElement')
                                        if parent:
                                            # Try common title selectors within card
                                            title_selectors = ['.title', '.product-title', '.name', 'h2', 'h3', '[data-testid*="title"]']
                                            for title_sel in title_selectors:
                                                try:
                                                    title_el = await parent.query_selector(title_sel)
                                                    if title_el:
                                                        dom_title = (await title_el.inner_text()).strip()
                                                        if len(dom_title) > 5:
                                                            break
                                                except:
                                                    continue
                                            
                                            # Try common price selectors within card
                                            price_selectors = ['.price', '.product-price', '[data-testid*="price"]', '.cost']
                                            for price_sel in price_selectors:
                                                try:
                                                    price_el = await parent.query_selector(price_sel)
                                                    if price_el:
                                                        price_text = (await price_el.inner_text()).strip()
                                                        if '$' in price_text or price_text.replace('.', '').replace(',', '').isdigit():
                                                            dom_price = price_text
                                                            break
                                                except:
                                                    continue
                                            
                                            # If we found both, stop searching
                                            if dom_title and dom_price:
                                                break
                                except Exception as e:
                                    logger.debug(f"Failed to extract validation data for URL {href}: {e}")
                                
                                product_links.append({
                                    'url': href.split('?')[0],  # Remove query params for cleaner URLs
                                    'product_code': product_code,
                                    'position': idx + 1,
                                    'dom_title': dom_title,  # For validation (optional)
                                    'dom_price': dom_price   # For validation (optional)
                                })
                        
                        # Record successful selector for learning
                        if product_links:
                            self.structure_learner.record_successful_extraction(
                                retailer, 'product_link', selector
                            )
                        
                        break  # Found good results, stop trying selectors
                        
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")
                    continue
            
            # Deduplicate by URL
            seen_urls = set()
            unique_links = []
            for link in product_links:
                if link['url'] not in seen_urls:
                    seen_urls.add(link['url'])
                    unique_links.append(link)
            
            # Log validation data statistics
            with_titles = sum(1 for l in unique_links if l.get('dom_title'))
            with_prices = sum(1 for l in unique_links if l.get('dom_price'))
            logger.debug(f"DOM validation data: {with_titles}/{len(unique_links)} titles, {with_prices}/{len(unique_links)} prices")
            
            return unique_links
            
        except Exception as e:
            logger.warning(f"Failed to extract catalog product links from DOM: {e}")
            return []
    
    def _merge_catalog_dom_with_gemini(self, dom_links: List[Dict], gemini_products: List[Dict], retailer: str) -> tuple[List[Dict], Dict]:
        """
        Merge DOM URLs/codes with Gemini visual data + VALIDATE Gemini with DOM
        Strategy: 
        1. Match by position or title similarity
        2. Validate Gemini's title/price against DOM data
        3. Flag mismatches for review
        
        Returns: (merged_products, validation_stats)
        """
        try:
            merged = []
            validations_performed = 0
            mismatches_found = 0
            title_validations = 0
            price_validations = 0
            
            # If counts match, do positional matching (simplest)
            if len(dom_links) == len(gemini_products):
                logger.debug(f"Counts match ({len(dom_links)}), doing positional merge with validation")
                for dom_link, gemini_product in zip(dom_links, gemini_products):
                    # Base merge
                    merged_product = {
                        'url': dom_link['url'],
                        'product_code': dom_link['product_code'],
                        'title': gemini_product.get('title', ''),
                        'price': gemini_product.get('price', 0),
                        'original_price': gemini_product.get('original_price'),
                        'image_urls': gemini_product.get('image_urls', []),
                        'sale_status': gemini_product.get('sale_status', 'regular'),
                        'availability': gemini_product.get('availability', 'in_stock')
                    }
                    
                    # VALIDATION: Compare Gemini vs DOM data
                    validation_result = {}
                    
                    # Validate title
                    if dom_link.get('dom_title') and gemini_product.get('title'):
                        title_similarity = self._calculate_similarity(
                            dom_link['dom_title'].lower(),
                            gemini_product['title'].lower()
                        )
                        validation_result['title_match'] = title_similarity > 0.7
                        validation_result['title_similarity'] = title_similarity
                        validations_performed += 1
                        title_validations += 1
                        
                        if title_similarity < 0.7:
                            mismatches_found += 1
                            logger.warning(f"⚠️ Title mismatch: DOM='{dom_link['dom_title'][:30]}' vs Gemini='{gemini_product['title'][:30]}' ({title_similarity:.0%})")
                            merged_product['validation_warning'] = 'title_mismatch'
                            # Use DOM title if confidence is very low
                            if title_similarity < 0.5:
                                merged_product['title'] = dom_link['dom_title']
                                merged_product['title_source'] = 'dom_override'
                    
                    # Validate price
                    if dom_link.get('dom_price') and gemini_product.get('price'):
                        # Extract numeric price from DOM text
                        import re
                        dom_price_match = re.search(r'[\d,]+\.?\d*', dom_link['dom_price'].replace(',', ''))
                        if dom_price_match:
                            try:
                                dom_price_num = float(dom_price_match.group(0))
                                gemini_price_num = float(gemini_product['price'])
                                price_diff = abs(dom_price_num - gemini_price_num)
                                validation_result['price_match'] = price_diff < 1.0
                                validations_performed += 1
                                price_validations += 1
                                
                                if price_diff >= 1.0:
                                    mismatches_found += 1
                                    logger.warning(f"⚠️ Price mismatch: DOM=${dom_price_num} vs Gemini=${gemini_price_num}")
                                    merged_product['validation_warning'] = merged_product.get('validation_warning', '') + '_price_mismatch'
                                    # Use DOM price if significant difference
                                    if price_diff >= 5.0:
                                        merged_product['price'] = dom_price_num
                                        merged_product['price_source'] = 'dom_override'
                            except:
                                pass
                    
                    if validation_result:
                        merged_product['validation'] = validation_result
                    
                    merged.append(merged_product)
            
            # If counts don't match, do fuzzy title matching
            else:
                logger.debug(f"Counts differ (DOM:{len(dom_links)}, Gemini:{len(gemini_products)}), doing title matching")
                
                # First, try to match by title similarity
                for gemini_product in gemini_products:
                    gemini_title = gemini_product.get('title', '').lower()
                    
                    best_match = None
                    best_similarity = 0
                    
                    for dom_link in dom_links:
                        # Try to extract title from URL for matching
                        url_parts = dom_link['url'].lower().split('/')
                        url_title = url_parts[-1] if url_parts else ''
                        
                        # Simple similarity check
                        similarity = self._calculate_similarity(gemini_title, url_title)
                        if similarity > best_similarity and similarity > 0.5:
                            best_similarity = similarity
                            best_match = dom_link
                    
                    if best_match:
                        merged_product = {
                            'url': best_match['url'],
                            'product_code': best_match['product_code'],
                            'title': gemini_product.get('title', ''),
                            'price': gemini_product.get('price', 0),
                            'original_price': gemini_product.get('original_price'),
                            'image_urls': gemini_product.get('image_urls', []),
                            'sale_status': gemini_product.get('sale_status', 'regular'),
                            'availability': gemini_product.get('availability', 'in_stock'),
                            'match_confidence': best_similarity
                        }
                        merged.append(merged_product)
                    else:
                        # No match found, add Gemini product without URL
                        gemini_product['url'] = None
                        gemini_product['product_code'] = None
                        merged.append(gemini_product)
                
                # Add any DOM links that weren't matched (with placeholder data)
                matched_urls = {p['url'] for p in merged if p.get('url')}
                for dom_link in dom_links:
                    if dom_link['url'] not in matched_urls:
                        merged.append({
                            'url': dom_link['url'],
                            'product_code': dom_link['product_code'],
                            'title': f"[URL only: {dom_link['url'].split('/')[-1]}]",
                            'price': 0,
                            'needs_reprocessing': True
                        })
            
            logger.debug(f"Merged {len(merged)} products (DOM URLs + Gemini visual data)")
            
            # Build validation stats
            validation_stats = {
                'validations_performed': validations_performed,
                'mismatches_found': mismatches_found,
                'title_validations': title_validations,
                'price_validations': price_validations,
                'total_products': len(merged)
            }
            
            # Log validation summary
            if validations_performed > 0:
                validation_rate = ((validations_performed - mismatches_found) / validations_performed * 100)
                logger.info(f"✅ Validation: {validations_performed} checks, {mismatches_found} mismatches ({validation_rate:.0%} accuracy)")
                if mismatches_found > 0:
                    logger.info(f"   💡 {mismatches_found} products corrected using DOM data")
            
            return merged, validation_stats
            
        except Exception as e:
            logger.error(f"Failed to merge catalog DOM and Gemini data: {e}")
            # Fallback: return Gemini products as-is with empty validation stats
            return gemini_products, {'validations_performed': 0, 'mismatches_found': 0}
class PlaywrightAgentWrapper:
    """
    Wrapper to integrate Playwright agent with existing agent_extractor.py
    Maintains same interface as Browser Use
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.agent = PlaywrightMultiScreenshotAgent(config)
    
    async def extract_product_data(self, url: str, retailer: str) -> ExtractionResult:
        """Main interface method - replaces Browser Use extraction"""
        async with self.agent:
            return await self.agent.extract_product(url, retailer)
    
    async def extract_catalog_products(self, catalog_url: str, retailer: str,
                                      catalog_prompt: str) -> Dict[str, Any]:
        """
        Extract ALL products from a catalog/listing page using Patchright screenshots
        
        This method is specifically for catalog pages (multi-product listings).
        For single product pages, use extract_product_data() instead.
        
        Args:
            catalog_url: URL of the catalog/listing page
            retailer: Retailer identifier
            catalog_prompt: Pre-built catalog-specific prompt from catalog_extractor
            
        Returns:
            Dict containing:
            - success: bool
            - products: List[Dict] - Array of product summaries
            - total_found: int
            - method_used: str ('patchright_gemini')
            - processing_time: float
            - warnings: List[str]
            - errors: List[str]
        """
        async with self.agent:
            return await self.agent.extract_catalog(catalog_url, retailer, catalog_prompt)


# Performance monitoring
class PlaywrightPerformanceMonitor:
    """Monitor performance improvements vs Browser Use"""
    
    def __init__(self):
        self.metrics = {
            'extraction_times': [],
            'success_rates': {},
            'cost_savings': 0,
            'verification_challenges_solved': 0
        }
    
    def log_extraction(self, retailer: str, time_taken: float, success: bool, cost: float):
        """Log extraction metrics"""
        self.metrics['extraction_times'].append(time_taken)
        
        if retailer not in self.metrics['success_rates']:
            self.metrics['success_rates'][retailer] = {'success': 0, 'total': 0}
        
        self.metrics['success_rates'][retailer]['total'] += 1
        if success:
            self.metrics['success_rates'][retailer]['success'] += 1
    
    def get_performance_summary(self) -> Dict:
        """Get performance summary vs Browser Use baseline"""
        avg_time = sum(self.metrics['extraction_times']) / len(self.metrics['extraction_times']) if self.metrics['extraction_times'] else 0
        
        overall_success = 0
        overall_total = 0
        for retailer_stats in self.metrics['success_rates'].values():
            overall_success += retailer_stats['success']
            overall_total += retailer_stats['total']
        
        success_rate = (overall_success / overall_total * 100) if overall_total > 0 else 0
        
        return {
            'average_extraction_time': avg_time,
            'success_rate_percent': success_rate,
            'improvement_vs_browser_use': {
                'speed': f"{max(0, 60 - avg_time):.1f}s faster" if avg_time < 60 else f"{avg_time - 60:.1f}s slower",
                'success_rate': f"{max(0, success_rate - 40):.1f}% better" if success_rate > 40 else f"{40 - success_rate:.1f}% worse",
                'cost_savings': "~50% less expensive (no multiple LLM calls)"
            }
        } 
    async def _gemini_analyze_page_structure(self, screenshots: Dict[str, bytes], 
                                             url: str, retailer: str) -> Dict:
        """
        STEP 2: Gemini analyzes page structure to GUIDE DOM extraction
        Provides visual hints and likely CSS selectors for DOM to use
        """
        try:
            first_screenshot = next(iter(screenshots.values()))
            image = Image.open(io.BytesIO(first_screenshot))
            
            prompt = f"""Analyze this {retailer} product page and provide DOM guidance.

Look at the page visually and tell the DOM scraper WHERE to look and WHAT selectors to try.

For each element, provide:
1. Visual location (top/middle/bottom, left/center/right)
2. Visual style (color, size, prominence)
3. Likely CSS selectors or classes you can see
4. Likely HTML tags

Return ONLY valid JSON:
{{
    "visual_hints": {{
        "title": {{
            "location": "top-left corner",
            "style": "large bold black text, 24px+",
            "prominence": "most prominent text"
        }},
        "price": {{
            "location": "top-right or near title",
            "style": "red or bold, dollar sign visible",
            "prominence": "second most prominent"
        }},
        "images": {{
            "location": "left side or center",
            "count": "3-5 images visible",
            "layout": "carousel or grid"
        }},
        "description": {{
            "location": "middle-right or below images",
            "style": "paragraph text, smaller font"
        }}
    }},
    "dom_hints": {{
        "title_selectors": ["h1", ".product-title", ".product-name", "[data-product-title]"],
        "price_selectors": [".price", ".product-price", ".sale-price", "[data-price]"],
        "image_selectors": [".product-images img", ".image-gallery img", ".carousel img"],
        "description_selectors": [".product-description", ".description", "[data-description]"]
    }},
    "layout_type": "two-column | single-column | grid",
    "page_complexity": "simple | moderate | complex"
}}

Focus on providing actionable CSS selectors that DOM can immediately use."""
            
            api_key = os.getenv("GOOGLE_API_KEY") or self.config.get("llm_providers", {}).get("google", {}).get("api_key")
            genai.configure(api_key=api_key)
            
            model = genai.GenerativeModel('gemini-2.0-flash-exp')
            response = model.generate_content([prompt, image])
            
            import re
            json_match = re.search(r'\{[\s\S]*\}', response.text)
            if json_match:
                result = json.loads(json_match.group(0))
                logger.info(f"✅ Gemini provided DOM guidance: {result.get('layout_type', 'unknown')} layout, {len(result.get('dom_hints', {}))} hint sets")
                return result
            
            logger.warning("Gemini structure analysis returned no JSON")
            return {'visual_hints': {}, 'dom_hints': {}}
        except Exception as e:
            logger.warning(f"⚠️ Page structure analysis failed: {e}")
            return {'visual_hints': {}, 'dom_hints': {}}
    
    async def _guided_dom_extraction(self, retailer: str, product_data: ProductData, gemini_visual_hints: Dict) -> Dict:
        """
        STEP 3: DOM fills gaps & validates Gemini's work (guided by Gemini Vision)
        Only extracts what Gemini missed or validates suspicious data
        """
        result = {
            'title': None, 
            'price': None, 
            'images': [], 
            'selectors_used': {},
            'validations': {},
            'gaps_filled': []
        }
        
        try:
            learned_patterns = self.structure_learner.get_best_patterns(retailer)
            
            # TITLE: Only extract if Gemini missed it or for validation
            if not product_data.title or len(product_data.title) < 5:
                logger.debug("Title missing from Gemini, DOM extracting...")
                title_selectors = []
                
                # 1. Try learned patterns first (highest confidence)
                title_selectors.extend([p['pattern_data'] for p in learned_patterns 
                                       if p['element_type'] == 'title' and p['confidence_score'] > 0.7])
                
                # 2. Add Gemini's visual hints (DOM guidance from Step 2)
                dom_hints = gemini_visual_hints.get('dom_hints', {})
                gemini_title_selectors = dom_hints.get('title_selectors', [])
                if gemini_title_selectors:
                    logger.debug(f"Using Gemini's DOM hints: {gemini_title_selectors}")
                    title_selectors.extend(gemini_title_selectors)
                
                # 3. Fallback generic selectors
                title_selectors.extend(['h1', '.product-title', '.product-name', '[data-testid="product-title"]'])
                
                for selector in title_selectors:
                    try:
                        element = await self.page.query_selector(selector)
                        if element:
                            dom_title = await element.inner_text()
                            if dom_title and len(dom_title) > 5:
                                result['title'] = dom_title.strip()
                                result['selectors_used']['title'] = selector
                                result['gaps_filled'].append('title')
                                self.structure_learner.record_successful_extraction(retailer, 'title', selector)
                                logger.info(f"✅ DOM filled gap: title")
                                break
                    except:
                        continue
            else:
                # Gemini has title, validate it with DOM
                try:
                    validation_selectors = [p['pattern_data'] for p in learned_patterns 
                                          if p['element_type'] == 'title' and p['confidence_score'] > 0.8][:2]
                    for selector in validation_selectors:
                        element = await self.page.query_selector(selector)
                        if element:
                            dom_title = (await element.inner_text()).strip()
                            similarity = self._calculate_similarity(product_data.title, dom_title)
                            result['validations']['title'] = {
                                'gemini': product_data.title[:50],
                                'dom': dom_title[:50],
                                'similarity': similarity,
                                'validated': similarity > 0.8
                            }
                            if similarity > 0.8:
                                logger.debug(f"✅ DOM validated title ({similarity:.0%} match)")
                            else:
                                logger.warning(f"⚠️ Title mismatch: Gemini vs DOM ({similarity:.0%})")
                            break
                except:
                    pass
            
            # PRICE: Only extract if missing
            if not product_data.price or product_data.price == 0:
                logger.debug("Price missing from Gemini, DOM extracting...")
                price_selectors = []
                
                # 1. Learned patterns first
                price_selectors.extend([p['pattern_data'] for p in learned_patterns 
                                       if p['element_type'] == 'price' and p['confidence_score'] > 0.7])
                
                # 2. Gemini's DOM hints
                gemini_price_selectors = gemini_visual_hints.get('dom_hints', {}).get('price_selectors', [])
                if gemini_price_selectors:
                    logger.debug(f"Using Gemini's price hints: {gemini_price_selectors}")
                    price_selectors.extend(gemini_price_selectors)
                
                # 3. Fallback generic
                price_selectors.extend(['.price', '.product-price', '[data-testid="price"]', 
                                      '.sale-price', '.current-price'])
                
                for selector in price_selectors:
                    try:
                        element = await self.page.query_selector(selector)
                        if element:
                            price_text = await element.inner_text()
                            if price_text and '$' in price_text:
                                result['price'] = price_text.strip()
                                result['selectors_used']['price'] = selector
                                result['gaps_filled'].append('price')
                                self.structure_learner.record_successful_extraction(retailer, 'price', selector)
                                logger.info(f"✅ DOM filled gap: price")
                                break
                    except:
                        continue
            
            # IMAGES: Only extract if Gemini found < 2 images
            if not product_data.image_urls or len(product_data.image_urls) < 2:
                logger.debug(f"Images missing from Gemini ({len(product_data.image_urls or [])}), DOM extracting...")
                image_selectors = []
                
                # Add Gemini's image selector hints
                gemini_image_selectors = gemini_visual_hints.get('dom_hints', {}).get('image_selectors', [])
                if gemini_image_selectors:
                    logger.debug(f"Using Gemini's image hints: {gemini_image_selectors}")
                    image_selectors.extend(gemini_image_selectors)
                
                # Fallback generic selectors
                image_selectors.extend(['img.product-image', '.product-images img', 
                                       '.image-gallery img', '[data-testid="product-image"]'])
                
                for selector in image_selectors:
                    try:
                        images = await self.page.query_selector_all(selector)
                        for img in images[:5]:
                            src = await img.get_attribute('src') or await img.get_attribute('data-src')
                            if src and 'http' in src and 'icon' not in src.lower():
                                result['images'].append(src)
                        
                        if result['images']:
                            result['selectors_used']['images'] = selector
                            result['gaps_filled'].append('images')
                            logger.info(f"✅ DOM filled gap: {len(result['images'])} images")
                            break
                    except:
                        continue
            
            gaps_msg = f"{len(result['gaps_filled'])} gaps filled" if result['gaps_filled'] else "no gaps"
            val_msg = f"{len(result['validations'])} validations" if result['validations'] else "no validations"
            logger.info(f"🎯 DOM complete: {gaps_msg}, {val_msg}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Guided DOM extraction failed: {e}")
            return result
    
    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate string similarity (0.0-1.0)"""
        try:
            from difflib import SequenceMatcher
            return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()
        except:
            return 0.0
    
    def _merge_extraction_results(self, product_data: ProductData, dom_result: Dict, gemini_analysis: Dict) -> ProductData:
        """
        STEP 4: Merge results - Gemini PRIMARY, DOM fills gaps/validates
        DOM only overwrites if Gemini missed something
        """
        try:
            # Title: Use DOM only if Gemini missed it
            if dom_result.get('title') and (not product_data.title or len(product_data.title) < 5):
                product_data.title = dom_result['title']
                logger.debug("Using DOM title (Gemini missed it)")
            elif product_data.title:
                logger.debug("Using Gemini title (primary)")
            
            # Price: Use DOM only if Gemini missed it
            if dom_result.get('price') and (not product_data.price or product_data.price == 0):
                # Parse DOM price text to float
                price_text = dom_result['price']
                try:
                    import re
                    price_match = re.search(r'\$?(\d+\.?\d*)', price_text)
                    if price_match:
                        product_data.price = float(price_match.group(1))
                        logger.debug("Using DOM price (Gemini missed it)")
                except:
                    pass
            elif product_data.price:
                logger.debug(f"Using Gemini price: ${product_data.price}")
            
            # Images: Merge both, Gemini first, then DOM fills gaps
            gemini_images = product_data.image_urls or []
            dom_images = dom_result.get('images', [])
            
            if len(gemini_images) < 2 and dom_images:
                # Gemini didn't find enough, use DOM
                all_images = []
                seen_bases = set()
                
                # Add Gemini images first (higher quality from screenshots)
                for img in gemini_images:
                    base = img.split('?')[0]
                    if base not in seen_bases:
                        all_images.append(img)
                        seen_bases.add(base)
                
                # Fill with DOM images
                for img in dom_images:
                    base = img.split('?')[0]
                    if base not in seen_bases:
                        all_images.append(img)
                        seen_bases.add(base)
                
                product_data.image_urls = all_images[:5]
                logger.debug(f"Merged images: {len(gemini_images)} Gemini + {len(dom_images)} DOM = {len(product_data.image_urls)} total")
            else:
                logger.debug(f"Using Gemini images: {len(gemini_images)} found")
            
            # Log what happened
            gaps_filled = dom_result.get('gaps_filled', [])
            if gaps_filled:
                logger.info(f"✅ DOM filled gaps: {', '.join(gaps_filled)}")
            else:
                logger.info("✅ Gemini extracted everything (DOM not needed)")
            
            # Log validations if any
            validations = dom_result.get('validations', {})
            if validations:
                for field, val_data in validations.items():
                    if not val_data.get('validated', True):
                        logger.warning(f"⚠️ {field} validation issue: {val_data.get('similarity', 0):.0%} match")
            
            return product_data
            
        except Exception as e:
            logger.error(f"❌ Result merging failed: {e}")
            return product_data
    
    async def _learn_from_extraction(self, retailer: str, dom_result: Dict, gemini_analysis: Dict, final_product_data: ProductData, url: str):
        """STEP 5: Learn from extraction"""
        try:
            import hashlib
            selectors_str = json.dumps(dom_result.get('selectors_used', {}), sort_keys=True)
            dom_hash = hashlib.md5(selectors_str.encode()).hexdigest()
            
            self.structure_learner.save_page_snapshot(
                retailer=retailer,
                dom_structure_hash=dom_hash,
                visual_layout_hash=dom_hash,
                key_selectors=dom_result.get('selectors_used', {}),
                layout_description="learned",
                screenshot_metadata={'url': url}
            )
            logger.info(f"✅ Learned from extraction")
        except Exception as e:
            logger.debug(f"Learning failed: {e}")
    
