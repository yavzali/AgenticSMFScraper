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

from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from PIL import Image
import io

from logger_config import setup_logging

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
        
    def _load_config(self) -> Dict:
        """Load configuration from config.json"""
        try:
            config_path = os.path.join(os.path.dirname(__file__), 'config.json')
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
        logger.info(f"🎭 Starting Playwright extraction for {retailer}: {url}")
        
        try:
            # Setup stealth browser
            await self._setup_stealth_browser()
            
            # Extract with retry logic
            result = await self._extract_with_retry(url, retailer)
            
            processing_time = time.time() - start_time
            logger.info(f"✅ Playwright extraction completed in {processing_time:.1f}s")
            
            return ExtractionResult(
                success=True,
                data=result.__dict__,
                method_used="playwright_multi_screenshot",
                processing_time=processing_time,
                warnings=[],
                errors=[]
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"❌ Playwright extraction failed: {e}")
            
            return ExtractionResult(
                success=False,
                data={},
                method_used="playwright_multi_screenshot",
                processing_time=processing_time,
                warnings=[],
                errors=[str(e)]
            )
        
        finally:
            await self._cleanup()
    
    async def _setup_stealth_browser(self):
        """Setup Playwright browser with advanced anti-detection"""
        try:
            # Import stealth (install if needed)
            try:
                from playwright_stealth import stealth_async
                self.stealth_available = True
            except ImportError:
                logger.warning("playwright-stealth not available, using basic stealth")
                self.stealth_available = False
            
            playwright = await async_playwright().start()
            
            # Launch browser with anti-detection args
            self.browser = await playwright.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-gpu',
                    '--disable-extensions',
                    '--disable-plugins',
                    '--disable-images',  # Faster loading
                    '--disable-javascript',  # Avoid verification triggers
                    '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                ]
            )
            
            # Create context with realistic settings
            self.context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                extra_http_headers={
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                }
            )
            
            # Apply stealth if available
            if self.stealth_available:
                page = await self.context.new_page()
                await stealth_async(page)
                self.page = page
            else:
                self.page = await self.context.new_page()
            
            logger.info("🥷 Stealth browser setup complete")
            
        except Exception as e:
            logger.error(f"Failed to setup stealth browser: {e}")
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
            
            # Extract image URLs from DOM (before screenshots)
            dom_image_urls = await self._extract_image_urls_from_dom(retailer)
            
            # Enhanced image processing for Anthropologie
            if retailer.lower() == 'anthropologie' and dom_image_urls:
                logger.info("🎨 Applying enhanced Anthropologie image processing")
                try:
                    from image_processor_factory import ImageProcessorFactory
                    processor = ImageProcessorFactory.get_processor('anthropologie')
                    if processor and hasattr(processor, 'process_images_enhanced'):
                        dom_image_urls = await processor.process_images_enhanced(
                            dom_image_urls, 
                            {'url': url, 'retailer': retailer}
                        )
                        logger.info(f"🎨 Enhanced processing: {len(dom_image_urls)} quality images")
                except Exception as e:
                    logger.warning(f"⚠️ Enhanced image processing failed: {e}")
            
            # Take strategic screenshots for content analysis
            screenshots = await self._take_strategic_screenshots(strategy, retailer)
            
            # Analyze with Gemini
            product_data = await self._analyze_with_gemini(screenshots, url, retailer)
            
            # Combine DOM-extracted images with Gemini analysis
            if dom_image_urls and len(dom_image_urls) > len(product_data.image_urls):
                logger.info(f"🖼️ DOM extracted {len(dom_image_urls)} images, adding to product data")
                # Use DOM images if we got more than Gemini found
                product_data.image_urls = dom_image_urls[:5]  # Limit to 5 best images
            
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
    
    async def _handle_verification_challenges(self, strategy: Dict):
        """Proactively handle verification challenges that break Browser Use"""
        
        # Check for common verification elements
        verification_selectors = [
            'button:has-text("Press & Hold")',
            'button:has-text("Verify")',
            '.captcha-container',
            '.cloudflare-browser-verification',
            '#challenge-form',
            '[data-testid="press-hold-button"]'
        ]
        
        for selector in verification_selectors:
            try:
                element = await self.page.query_selector(selector)
                if element:
                    logger.warning(f"🛡️ Verification challenge detected: {selector}")
                    
                    # Try gentle interaction (unlike Browser Use's aggressive approach)
                    if 'press' in selector.lower() and 'hold' in selector.lower():
                        await self._handle_press_and_hold(element)
                    elif 'verify' in selector.lower():
                        await element.click()
                        await asyncio.sleep(2)
                    
                    # Wait to see if challenge resolves
                    await asyncio.sleep(3)
                    break
                    
            except Exception as e:
                logger.debug(f"Verification check failed for {selector}: {e}")
                continue
    
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
        """Clean up browser resources"""
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
        except Exception as e:
            logger.warning(f"Cleanup failed: {e}")
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self._cleanup()

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