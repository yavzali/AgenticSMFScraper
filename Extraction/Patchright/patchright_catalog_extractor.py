"""
Patchright Tower - Catalog Extractor
Extract multiple products from catalog pages using Patchright + Gemini Vision

Extracted from: Shared/playwright_agent.py (catalog logic, lines 214-558, 2464-2610, 2611-2774)
Target: <1000 lines
"""

# Add shared path for imports
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../../Shared"))

import asyncio
import time
import json
import re
import io
from typing import List, Dict, Optional, Any
from urllib.parse import urlparse
from PIL import Image
from patchright.async_api import async_playwright
import google.generativeai as genai
from dotenv import load_dotenv
from difflib import SequenceMatcher
import logging

from logger_config import setup_logging
from patchright_verification import PatchrightVerificationHandler
from patchright_retailer_strategies import PatchrightRetailerStrategies

logger = setup_logging(__name__)


class PatchrightCatalogExtractor:
    """
    Extract multiple products from catalog/listing pages
    
    Two extraction modes:
    1. **Gemini-first** (default): Gemini extracts visual data, DOM adds URLs
    2. **DOM-first** (tall pages): DOM extracts URLs, Gemini validates sample
    
    Key features:
    - Full-page screenshot capture
    - Hybrid DOM + Gemini Vision
    - Verification handling (PerimeterX, Cloudflare)
    - DOM validation of Gemini data
    - Pattern learning integration
    """
    
    def __init__(self, config: Dict = None):
        """Initialize catalog extractor"""
        # Load environment
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.join(script_dir, '../..')
        env_path = os.path.join(project_root, '.env')
        load_dotenv(env_path, override=True)
        
        # Load config
        if config is None:
            config_path = os.path.join(project_root, 'Shared/config.json')
            with open(config_path, 'r') as f:
                config = json.load(f)
        
        self.config = config
        self.strategies = PatchrightRetailerStrategies()
        
        # Browser state
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        
        # Setup Gemini
        self._setup_gemini()
        
        logger.info("✅ Patchright Catalog Extractor initialized")
    
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
    
    async def extract_catalog(
        self,
        catalog_url: str,
        retailer: str,
        catalog_prompt: str
    ) -> Dict[str, Any]:
        """
        Extract ALL products from catalog page
        
        Process:
        1. Navigate to catalog page
        2. Handle verification (PerimeterX, Cloudflare)
        3. Wait for products to load (retailer-specific)
        4. Take full-page screenshot
        5. Gemini extracts visual data
        6. DOM extracts URLs + validates
        7. Merge and return
        
        Args:
            catalog_url: Catalog page URL
            retailer: Retailer name
            catalog_prompt: Pre-built extraction prompt
            
        Returns:
            Dict with success, products, total_found, method_used, etc.
        """
        start_time = time.time()
        
        try:
            logger.info(f"🎭 Starting Patchright catalog extraction for {retailer}: {catalog_url}")
            
            # Step 1: Setup browser
            await self._setup_stealth_browser()
            
            # Step 2: Navigate with retailer-specific wait strategy
            strategy = self.strategies.get_strategy(retailer)
            wait_until = strategy.get('wait_strategy', 'domcontentloaded')
            
            logger.debug(f"Navigating with wait_until='{wait_until}'")
            await self.page.goto(catalog_url, wait_until=wait_until, timeout=60000)
            await asyncio.sleep(3)
            
            # Step 3: Handle verification
            verification_handler = PatchrightVerificationHandler(self.page, self.config)
            verification_strategy = {
                'domain': self._extract_domain(catalog_url),
                'retailer': retailer,
                'special_notes': 'cloudflare_verification' if retailer.lower() == 'aritzia' else ''
            }
            await verification_handler.handle_verification_challenges(verification_strategy)
            
            # Step 4: Wait for page to fully render
            logger.info("⏱️ Waiting for page to fully render...")
            
            try:
                await self.page.wait_for_load_state('networkidle', timeout=15000)
                logger.info("✅ Page network idle")
            except:
                logger.info("⏱️ Network still active, continuing...")
            
            await asyncio.sleep(10)
            
            # Step 5: Retailer-specific extended waits
            # For Aritzia specifically
            if retailer.lower() == 'aritzia':
                logger.info("⏱️ Starting Aritzia product detection (polling mode)")
                
                max_attempts = 30
                attempt = 0
                products_found = False
                
                selectors_to_try = [
                    'a[href*="/product/"]',
                    'a[class*="ProductCard"]',
                    '[data-product-id]'
                ]
                
                while attempt < max_attempts and not products_found:
                    attempt += 1
                    
                    for selector in selectors_to_try:
                        try:
                            elements = await self.page.query_selector_all(selector)
                            if len(elements) > 0:
                                logger.info(f"✅ Found {len(elements)} products with selector '{selector}' after {attempt} seconds")
                                products_found = True
                                break
                        except:
                            continue
                    
                    if not products_found:
                        await asyncio.sleep(1)
                
                if not products_found:
                    logger.warning(f"⚠️ No products detected after {max_attempts} seconds")
            elif 'cloudflare' in verification_strategy.get('special_notes', '').lower():
                logger.info("🔍 Cloudflare detected - extended wait...")
                await asyncio.sleep(15)
                
                # Scroll to trigger lazy loading
                logger.info("📜 Scrolling to trigger product loading...")
                await self.page.evaluate("window.scrollTo(0, 1000)")
                await asyncio.sleep(2)
                await self.page.evaluate("window.scrollTo(0, 0)")
                await asyncio.sleep(2)
                
                # Wait for product elements
                product_selectors = strategy.get('product_selectors', [])
                if product_selectors:
                    selector_str = ', '.join(product_selectors)
                    try:
                        await self.page.wait_for_selector(
                            selector_str,
                            timeout=30000,
                            state='attached'
                        )
                        logger.info("✅ Product elements found")
                        await asyncio.sleep(3)
                    except Exception as e:
                        logger.warning(f"⚠️ Products not found: {e}")
            
            # Step 6: Try to detect products with learned patterns
            await self._wait_for_products(retailer, strategy)
            
            await asyncio.sleep(2)
            
            # Step 6.5: Dismiss popups again (they may appear after page loads)
            logger.info("🧹 Dismissing any late-appearing popups...")
            await verification_handler._dismiss_popups()
            await asyncio.sleep(1)  # Let DOM settle after popup dismissal
            
            # Step 7: Take full-page screenshot
            logger.debug("📸 Taking full-page screenshot...")
            await self.page.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(1)
            
            full_page_screenshot = await self.page.screenshot(full_page=True, type='png')
            screenshots = [full_page_screenshot]
            screenshot_descriptions = ["Full catalog page showing all products"]
            
            logger.info("✅ Captured full-page screenshot")
            
            # Step 8: Gemini extracts visual data
            logger.info("🔍 Step 1: Gemini Vision extracting product data...")
            
            screenshot_list = "\n".join([f"{i+1}. {desc}" for i, desc in enumerate(screenshot_descriptions)])
            
            full_prompt = f"""CATALOG EXTRACTION - CRITICAL INSTRUCTIONS

You are analyzing a {retailer} catalog page with a product grid.

YOUR PRIMARY TASK: Extract EVERY SINGLE PRODUCT visible on this page.

IMPORTANT RULES:
1. DO NOT skip products just because their images haven't loaded yet
2. EXTRACT products even if you only see:
   - Product title (text visible in product card)
   - Price (text visible in product card)
   - Placeholder image, loading spinner, or blank image area
3. Images are OPTIONAL - your focus is on title and price
4. Count all product cards/tiles in the grid, not just ones with fully loaded images

REQUIRED FIELDS (extract if visible):
- title: Product name/title (REQUIRED - extract from any visible text in product card)
- price: Current price (REQUIRED - extract visible price number)

OPTIONAL FIELDS (extract if visible and readable):
- original_price: Original price if product shows sale pricing
- sale_status: "on_sale" or "regular" (only if clearly visible)
- image_urls: Product image URLs if visible in the screenshot (extract if you can read them)

NOTE ON EXTRACTION LIMITATIONS:
- Product URLs and product codes are typically NOT visible in screenshots - these will be extracted separately via DOM
- If you CAN see image URLs in the screenshot, extract them
- But if URLs/codes are not visible, do not make them up - DOM will handle this

CRITICAL RULES - WHAT NOT TO DO:
- NEVER create fake or placeholder titles like "[URL only: ...]" or "Unknown Product"
- NEVER create fake or placeholder prices like 0 or "N/A"
- NEVER make up data that you cannot see in the screenshot
- IF you cannot read a product's title or price, SKIP that product entirely

CRITICAL SUCCESS CRITERIA:
- If you see 50+ product cards in the grid, your response should have 50+ products
- If a product card shows title and price but image is loading, INCLUDE IT
- Even products with placeholder images or loading icons should be extracted
- Every product you return must have a REAL title (actual product name) and REAL price (actual number)

SCREENSHOT ANALYSIS INSTRUCTIONS:
You are viewing {len(screenshots)} screenshot(s) of this catalog page.
Analyze ALL visible products across all screenshots.

Screenshots show:
{screenshot_list}

Return a JSON array with ALL products found across all screenshots.
Each product should be a JSON object with title and price at minimum.

DO NOT include products where you cannot read the title or price - skip them instead of making up data."""
            
            # Step 9: Call Gemini Vision
            image_parts = []
            for screenshot_bytes in screenshots:
                image = Image.open(io.BytesIO(screenshot_bytes))
                
                # Resize if exceeds Gemini's WebP limit
                max_height = 16000
                if image.height > max_height:
                    scale_factor = max_height / image.height
                    new_width = int(image.width * scale_factor)
                    logger.info(f"📐 Resizing from {image.width}x{image.height} to {new_width}x{max_height}")
                    image = image.resize((new_width, max_height), Image.Resampling.LANCZOS)
                
                image_parts.append(image)
            
            model = genai.GenerativeModel('gemini-2.0-flash-exp')
            response = model.generate_content([full_prompt] + image_parts)
            
            # Parse Gemini response (robust JSON extraction - matches old system)
            extraction_result = None
            if response and hasattr(response, 'text'):
                content = response.text
                
                # Strategy 1: Try to find JSON using regex (old system approach)
                json_pattern = r"```json\s*([\s\S]*?)\s*```|```\s*([\s\S]*?)\s*```|(\{[\s\S]*\}|\[[\s\S]*\])"
                json_match = re.search(json_pattern, content)
                
                if json_match:
                    # Get the first non-None group
                    json_str = next((g for g in json_match.groups() if g is not None), None)
                    
                    if json_str:
                        try:
                            extraction_result = json.loads(json_str)
                        except json.JSONDecodeError as e:
                            # Strategy 2: Try to find just the first valid JSON structure
                            logger.debug(f"Initial parse failed: {e}, trying to find valid JSON")
                            
                            # Find start of JSON ([ or {)
                            for start_char in ['[', '{']:
                                idx = json_str.find(start_char)
                                if idx != -1:
                                    try:
                                        # Use JSONDecoder to parse and find where valid JSON ends
                                        decoder = json.JSONDecoder()
                                        result, end_idx = decoder.raw_decode(json_str, idx)
                                        extraction_result = result
                                        break
                                    except json.JSONDecodeError:
                                        continue
            
            processing_time = time.time() - start_time
            
            if not extraction_result:
                logger.warning("⚠️ Failed to extract catalog products")
                return {
                    'success': False,
                    'products': [],
                    'total_found': 0,
                    'method_used': 'patchright_gemini',
                    'processing_time': processing_time,
                    'warnings': ['Failed to parse Gemini response'],
                    'errors': ['Could not extract product array']
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
            
            if not isinstance(products, list):
                return {
                    'success': False,
                    'products': [],
                    'total_found': 0,
                    'method_used': 'patchright_gemini',
                    'processing_time': processing_time,
                    'warnings': [f'Expected array, got {type(products)}'],
                    'errors': ['Not in array format']
                }
            
            logger.info(f"✅ Gemini extracted {len(products)} products visually")
            
            # Step 10: DOM extracts URLs + validates
            logger.info("🔗 Step 2: DOM extracting URLs and validating...")
            dom_product_links = await self._extract_catalog_product_links_from_dom(retailer, strategy)
            logger.info(f"✅ DOM found {len(dom_product_links)} product URLs")
            
            # NEW: Validate extraction quality BEFORE merge
            validation_result = self._validate_extraction_quality(
                gemini_products=products,
                dom_product_links=dom_product_links,
                retailer=retailer
            )
            
            # Log validation results
            logger.info(f"📊 Extraction Ratio: {validation_result['extraction_ratio']:.1%} "
                       f"(Gemini: {validation_result['gemini_count']}, DOM: {validation_result['dom_count']})")
            
            # If extraction is critically bad, trigger DOM-first mode
            if not validation_result['valid']:
                logger.warning("⚠️ Extraction validation failed, considering DOM-first fallback...")
                # The existing DOM-first logic will handle this below
            
            # Step 11: DOM-first override for tall pages or when Gemini extraction is poor
            use_dom_first = False
            dom_first_reason = None
            
            # Check if retailer is configured for DOM-first mode
            if strategy.get('catalog_mode') == 'dom_first':
                use_dom_first = True
                dom_first_reason = 'retailer_configured_dom_first'
            
            # Anthropologie: Screenshot too tall/compressed
            elif retailer.lower() == 'anthropologie' and len(dom_product_links) > len(products) * 2:
                use_dom_first = True
                dom_first_reason = 'screenshot_too_tall'
            
            # Nordstrom: Gemini fails to extract prices (ads mixed in)
            elif retailer.lower() == 'nordstrom':
                products_with_price = sum(1 for p in products if p.get('price') and p.get('price') != 0)
                if products_with_price < len(products) * 0.5:  # Less than 50% have prices
                    use_dom_first = True
                    dom_first_reason = 'gemini_price_extraction_failed'
            
            if use_dom_first:
                logger.info(f"🔄 DOM-FIRST MODE: Using DOM URLs (Gemini only found {len(products)}/{len(dom_product_links)})")
                logger.info(f"   Reason: {dom_first_reason}")
                
                merged_products = []
                for link_data in dom_product_links:
                    merged_products.append({
                        'url': link_data['url'],
                        'product_code': link_data.get('product_code', ''),
                        'title': link_data.get('dom_title', 'Unknown Product'),
                        'price': self._parse_price_from_text(link_data.get('dom_price', '')) if link_data.get('dom_price') else 0,
                        'image_url': link_data.get('image_url'),
                        'sale_status': 'unknown',
                        'extraction_source': 'dom_only'
                    })
                validation_stats = {'dom_only_mode': True, 'reason': dom_first_reason}
                logger.info(f"✅ Using all {len(merged_products)} DOM-extracted products")
            else:
                # Step 12: Normal merge - DOM URLs + Gemini visual data
                logger.info("🔗 Step 3: Merging DOM URLs with Gemini visual data...")
                merged_products, validation_stats = self._merge_catalog_dom_with_gemini(
                    dom_product_links, products, retailer
                )
                logger.info(f"✅ Merged: {len(merged_products)} products with complete data")
            
            products = merged_products
            
            logger.info(f"✅ Patchright catalog extraction successful: {len(products)} products")
            
            return {
                'success': True,
                'products': products,
                'total_found': len(products),
                'method_used': 'patchright_catalog_gemini_dom_hybrid',
                'processing_time': processing_time,
                'validation_stats': validation_stats,
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
        """Setup Patchright stealth browser"""
        try:
            self.playwright = await async_playwright().start()
            
            user_data_dir = os.path.join(os.path.expanduser('~'), '.patchright_data')
            os.makedirs(user_data_dir, exist_ok=True)
            
            self.context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir,
                headless=False,
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                locale='en-US',
                permissions=[]  # Deny all permissions (notifications, geolocation, etc.)
            )
            
            self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
            
            logger.info("✅ Stealth browser initialized")
            
        except Exception as e:
            logger.error(f"Failed to setup browser: {e}")
            raise
    
    async def _wait_for_products(self, retailer: str, strategy: Dict):
        """Wait for products to appear using learned patterns + common selectors"""
        selectors_to_try = []
        
        # Add retailer-specific selectors
        product_selectors = strategy.get('product_selectors', [])
        selectors_to_try.extend(product_selectors)
        
        # Add common fallbacks
        selectors_to_try.extend([
            'a[href*="/shop/"]',
            'a[data-testid="product-card-link"]',
            'a[href*="/p/"]',
            'a[href*="/product/"]',
            '.product-card a',
            '[data-product-id]'
        ])
        
        product_loaded = False
        for selector in selectors_to_try:
            try:
                await self.page.wait_for_selector(selector, timeout=3000, state='visible')
                logger.info(f"✅ Products detected: {selector}")
                product_loaded = True
                break
            except:
                continue
        
        if not product_loaded:
            logger.info("⚠️ No standard selectors detected, relying on Gemini")
    
    async def _extract_catalog_product_links_from_dom(
        self,
        retailer: str,
        strategy: Dict
    ) -> List[Dict]:
        """
        Extract URLs, codes, and validation data from DOM
        
        Returns:
            List of {url, product_code, position, dom_title, dom_price}
        """
        try:
            product_links = []
            
            # SPECIAL CASE: Revolve needs container-first extraction
            if retailer.lower() == 'revolve':
                return await self._extract_revolve_from_containers(retailer, strategy)
            
            # Get selectors from strategy
            selectors = strategy.get('product_selectors', [])
            
            # Add common patterns (order matters - more specific first!)
            selectors.extend([
                'a[href*="/s/"]',  # Nordstrom-specific pattern
                'a[data-testid="product-card-link"]',
                'a[href*="/product"]', 'a[href*="/p/"]', 'a[href*="/dp/"]',
                '.product-card a', '.product-item a', '[data-product-id]',
                'a.product-link', 'a.product-tile', 'a[data-product-url]',
                'a[href*="/shop/"]', 'a[href*="/item/"]'
            ])
            
            # Try to find product container first for better scoping
            product_container = None
            container_selectors = [
                '#plp-prod-list',  # Revolve
                '.products-grid',  # Revolve, Anthropologie
                '#product-search-results',  # Common
                '[data-testid="product-results"]',  # Common
                'main',  # Fallback
            ]
            
            for cont_sel in container_selectors:
                try:
                    cont = await self.page.query_selector(cont_sel)
                    if cont:
                        product_container = cont
                        logger.debug(f"✅ Using product container: {cont_sel}")
                        break
                except:
                    continue
            
            # If no container found, use page
            if not product_container:
                product_container = self.page
                logger.debug("Using entire page for link extraction")
            
            # Try each selector (scoped to product container)
            for selector in selectors:
                try:
                    if product_container == self.page:
                        links = await self.page.query_selector_all(selector)
                    else:
                        links = await product_container.query_selector_all(selector)
                    
                    if links and len(links) > 0:
                        logger.info(f"✅ Found {len(links)} links with: {selector}")
                        
                        for idx, link in enumerate(links[:100]):
                            try:
                                # Try attribute first, then JS property
                                href = await link.get_attribute('href')
                                if not href:
                                    href = await link.evaluate('el => el.href')
                            except Exception as e:
                                logger.warning(f"Failed to get href for link {idx}: {e}")
                                continue
                            
                            if not href:
                                continue
                            
                            # Make absolute URL
                            if href.startswith('/'):
                                parsed = urlparse(await self.page.url)
                                href = f"{parsed.scheme}://{parsed.netloc}{href}"
                            elif not href.startswith('http'):
                                continue
                            
                            # Extract product code
                            product_code = self._extract_product_code_from_url(href, retailer)
                            
                            # Try to extract title/price from DOM for validation
                            dom_title = None
                            dom_price = None
                            
                            try:
                                # Get retailer-specific DOM extraction config
                                dom_config = strategy.get('dom_extraction', {})
                                title_selectors = dom_config.get('title_selectors', ['.title', '.product-title', 'img[alt]', 'h2', 'h3'])
                                price_selectors = dom_config.get('price_selectors', ['.price', '.product-price', '[data-testid*="price"]'])
                                extract_price_from_text = dom_config.get('extract_price_from_text', False)
                                max_parent_levels = dom_config.get('max_parent_levels', 3)
                                
                                parent = link
                                for _ in range(max_parent_levels):
                                    parent = await parent.evaluate_handle('el => el.parentElement')
                                    if parent:
                                        # Try title selectors (retailer-specific)
                                        for title_sel in title_selectors:
                                            try:
                                                # Handle img[alt] and a[aria-label] specially
                                                if title_sel == 'img[alt]':
                                                    title_el = await parent.query_selector('img[alt]')
                                                    if title_el:
                                                        dom_title = await title_el.get_attribute('alt')
                                                        if dom_title and len(dom_title.strip()) > 5 and 'revolve' not in dom_title.lower():
                                                            dom_title = dom_title.strip()
                                                            break
                                                elif title_sel == 'a[aria-label]':
                                                    title_el = await parent.query_selector('a[aria-label]')
                                                    if title_el:
                                                        dom_title = await title_el.get_attribute('aria-label')
                                                        if dom_title and len(dom_title.strip()) > 5:
                                                            dom_title = dom_title.strip()
                                                            break
                                                else:
                                                    title_el = await parent.query_selector(title_sel)
                                                    if title_el:
                                                        dom_title = (await title_el.inner_text()).strip()
                                                        if len(dom_title) > 5:
                                                            break
                                            except:
                                                continue
                                        
                                        # Try price selectors (retailer-specific)
                                        for price_sel in price_selectors:
                                            try:
                                                price_el = await parent.query_selector(price_sel)
                                                if price_el:
                                                    price_text = (await price_el.inner_text()).strip()
                                                    if '$' in price_text:
                                                        dom_price = price_text
                                                        break
                                            except:
                                                continue
                                        
                                        # Fallback 1: Extract price from plain text (Revolve-style or generic)
                                        if not dom_price:
                                            try:
                                                parent_text = await parent.inner_text()
                                                lines = [l.strip() for l in parent_text.split('\n') if l.strip()]
                                                
                                                # Strategy A: Look for $ in short lines
                                                for line in lines:
                                                    if '$' in line and len(line) < 30:
                                                        price_match = re.search(r'\$\s*(\d+\.?\d*)', line)
                                                        if price_match:
                                                            dom_price = f"${price_match.group(1)}"
                                                            logger.debug(f"💰 Found price in text (strategy A): {dom_price}")
                                                            break
                                                
                                                # Strategy B: Look for standalone numbers that could be prices
                                                if not dom_price:
                                                    for line in lines:
                                                        if re.match(r'^\$?\d{2,4}\.?\d{0,2}$', line):
                                                            price_match = re.search(r'(\d+\.?\d*)', line)
                                                            if price_match:
                                                                price_val = float(price_match.group(1))
                                                                if 20 <= price_val <= 9999:
                                                                    dom_price = f"${price_val:.2f}" if '.' in price_match.group(1) else f"${int(price_val)}"
                                                                    logger.debug(f"💰 Found price as number (strategy B): {dom_price}")
                                                                    break
                                            except Exception as e:
                                                logger.debug(f"Text price extraction failed: {e}")
                                        
                                        # Fallback 2: Look for any element with price-like text
                                        if not dom_price:
                                            try:
                                                # Search for spans/divs containing $ within parent
                                                price_candidates = await parent.query_selector_all('span, div, p')
                                                for candidate in price_candidates[:10]:  # Limit search
                                                    try:
                                                        text = (await candidate.inner_text()).strip()
                                                        if text.startswith('$') and len(text) < 20:
                                                            dom_price = text
                                                            break
                                                    except:
                                                        continue
                                            except:
                                                pass
                                        
                                        if dom_title and dom_price:
                                            break
                            except Exception as e:
                                logger.debug(f"Failed validation extraction: {e}")
                            
                            product_links.append({
                                'url': href.split('?')[0],
                                'product_code': product_code,
                                'position': idx + 1,
                                'dom_title': dom_title,
                                'dom_price': dom_price
                            })
                        
                        logger.info(f"📦 Extracted {len(product_links)} URLs from DOM")
                        break
                        
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")
                    continue
            
            # Deduplicate by URL (keep first occurrence)
            seen_urls = set()
            deduped_links = []
            for link in product_links:
                url = link['url']
                if url not in seen_urls:
                    seen_urls.add(url)
                    deduped_links.append(link)
            
            if len(deduped_links) < len(product_links):
                logger.info(f"🧹 Deduplicated: {len(product_links)} → {len(deduped_links)} unique URLs")
            
            return deduped_links
            
        except Exception as e:
            logger.error(f"DOM extraction failed: {e}")
            return []
    
    def _validate_extraction_quality(
        self,
        gemini_products: List[Dict],
        dom_product_links: List[Dict],
        retailer: str
    ) -> Dict[str, Any]:
        """
        Validate extraction quality to catch common mistakes
        
        Checks for:
        1. Gemini extracted reasonable number of products vs DOM
        2. No fake/placeholder titles or prices
        3. Products have valid data structure
        
        Args:
            gemini_products: Products extracted by Gemini Vision
            dom_product_links: Product URLs extracted by DOM
            retailer: Retailer name
        
        Returns:
            {
                'valid': bool,
                'warnings': List[str],
                'errors': List[str],
                'gemini_count': int,
                'dom_count': int,
                'extraction_ratio': float
            }
        """
        validation_result = {
            'valid': True,
            'warnings': [],
            'errors': [],
            'gemini_count': len(gemini_products),
            'dom_count': len(dom_product_links),
            'extraction_ratio': 0.0
        }
        
        # Calculate extraction ratio
        if len(dom_product_links) > 0:
            validation_result['extraction_ratio'] = len(gemini_products) / len(dom_product_links)
        
        # Check 1: Gemini found significantly fewer products than DOM
        # This indicates Gemini may have missed products
        if len(dom_product_links) > 20 and validation_result['extraction_ratio'] < 0.3:
            validation_result['warnings'].append(
                f"Low extraction ratio: Gemini found {len(gemini_products)} products "
                f"but DOM found {len(dom_product_links)} URLs. May have missed products without loaded images."
            )
            logger.warning(f"⚠️ Low extraction ratio: {validation_result['extraction_ratio']:.1%}")
        
        # Check 2: Validate each product has real data (not fake/placeholder)
        fake_title_patterns = [
            r'\[url only',
            r'unknown product',
            r'product \d+',
            r'^\s*$',  # Empty or whitespace only
            r'^n/a$',
            r'^none$',
            r'^null$'
        ]
        
        products_with_fake_titles = 0
        products_with_invalid_prices = 0
        products_missing_title = 0
        products_missing_price = 0
        
        for i, product in enumerate(gemini_products):
            # Check for missing title
            if not product.get('title'):
                products_missing_title += 1
                continue
            
            # Check for fake/placeholder titles
            title_lower = product['title'].lower().strip()
            is_fake_title = any(
                re.search(pattern, title_lower, re.IGNORECASE) 
                for pattern in fake_title_patterns
            )
            
            if is_fake_title:
                products_with_fake_titles += 1
                logger.warning(f"⚠️ Fake title detected: '{product['title']}'")
            
            # Check for missing or invalid price
            price = product.get('price')
            if price is None:
                products_missing_price += 1
            else:
                # Handle both numeric and string prices
                is_invalid = False
                if isinstance(price, (int, float)):
                    if price <= 0:
                        is_invalid = True
                elif isinstance(price, str):
                    # Try to extract numeric value from string like "$115" or "115.00"
                    try:
                        price_match = re.search(r'\d+\.?\d*', price.replace('$', '').replace(',', ''))
                        if not price_match or float(price_match.group()) <= 0:
                            is_invalid = True
                    except:
                        is_invalid = True
                else:
                    is_invalid = True
                
                if is_invalid:
                    products_with_invalid_prices += 1
                    logger.warning(f"⚠️ Invalid price detected: {price}")
        
        # Add validation errors/warnings
        if products_with_fake_titles > 0:
            validation_result['errors'].append(
                f"Found {products_with_fake_titles} products with fake/placeholder titles. "
                f"LLM should never create fake data."
            )
            validation_result['valid'] = False
        
        if products_missing_title > len(gemini_products) * 0.1:  # More than 10% missing titles
            validation_result['warnings'].append(
                f"{products_missing_title} products missing titles ({products_missing_title/len(gemini_products)*100:.1f}%)"
            )
        
        if products_missing_price > len(gemini_products) * 0.1:  # More than 10% missing prices
            validation_result['warnings'].append(
                f"{products_missing_price} products missing prices ({products_missing_price/len(gemini_products)*100:.1f}%)"
            )
        
        if products_with_invalid_prices > 0:
            validation_result['warnings'].append(
                f"{products_with_invalid_prices} products with invalid prices (0 or negative)"
            )
        
        # Check 3: Minimum product count threshold
        # For retailers we know have many products, ensure we extracted enough
        expected_minimum_by_retailer = {
            'revolve': 40,
            'anthropologie': 50,
            'urban_outfitters': 50,
            'abercrombie': 60,
            'nordstrom': 40,
            'aritzia': 40
        }
        
        expected_min = expected_minimum_by_retailer.get(retailer.lower(), 20)
        
        if len(gemini_products) < expected_min and len(dom_product_links) > expected_min:
            validation_result['errors'].append(
                f"Expected at least {expected_min} products for {retailer}, "
                f"but only extracted {len(gemini_products)}. DOM found {len(dom_product_links)} URLs."
            )
            validation_result['valid'] = False
        
        # Log validation summary
        if validation_result['valid']:
            logger.info(f"✅ Extraction validation passed: {len(gemini_products)} products extracted")
        else:
            logger.error(f"❌ Extraction validation failed: {validation_result['errors']}")
        
        if validation_result['warnings']:
            for warning in validation_result['warnings']:
                logger.warning(f"⚠️ Validation warning: {warning}")
        
        return validation_result
    
    def _merge_catalog_dom_with_gemini(
        self,
        dom_links: List[Dict],
        gemini_products: List[Dict],
        retailer: str
    ) -> tuple[List[Dict], Dict]:
        """
        Merge DOM URLs with Gemini visual data + validate
        
        Returns:
            (merged_products, validation_stats)
        """
        try:
            merged = []
            validations_performed = 0
            mismatches_found = 0
            title_validations = 0
            price_validations = 0
            
            # If counts match, do positional matching
            if len(dom_links) == len(gemini_products):
                logger.debug(f"Counts match ({len(dom_links)}), positional merge")
                
                for dom_link, gemini_product in zip(dom_links, gemini_products):
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
                    
                    # Validate title
                    if dom_link.get('dom_title') and gemini_product.get('title'):
                        similarity = self._calculate_similarity(
                            dom_link['dom_title'].lower(),
                            gemini_product['title'].lower()
                        )
                        validations_performed += 1
                        title_validations += 1
                        
                        if similarity < 0.7:
                            mismatches_found += 1
                            logger.warning(f"⚠️ Title mismatch: {similarity:.0%}")
                            if similarity < 0.5:
                                merged_product['title'] = dom_link['dom_title']
                                merged_product['title_source'] = 'dom_override'
                    
                    # Validate price
                    if dom_link.get('dom_price') and gemini_product.get('price'):
                        dom_price_match = re.search(r'[\d,]+\.?\d*', dom_link['dom_price'].replace(',', ''))
                        if dom_price_match:
                            try:
                                dom_price_num = float(dom_price_match.group(0))
                                gemini_price_num = float(gemini_product['price'])
                                price_diff = abs(dom_price_num - gemini_price_num)
                                validations_performed += 1
                                price_validations += 1
                                
                                if price_diff >= 1.0:
                                    mismatches_found += 1
                                    logger.warning(f"⚠️ Price mismatch: ${price_diff}")
                                    if price_diff >= 5.0:
                                        merged_product['price'] = dom_price_num
                                        merged_product['price_source'] = 'dom_override'
                            except:
                                pass
                    
                    merged.append(merged_product)
            
            else:
                # Fuzzy title matching
                logger.debug(f"Counts differ, fuzzy matching")
                
                for gemini_product in gemini_products:
                    gemini_title = gemini_product.get('title', '').lower()
                    
                    best_match = None
                    best_similarity = 0
                    
                    for dom_link in dom_links:
                        url_parts = dom_link['url'].lower().split('/')
                        url_title = url_parts[-1] if url_parts else ''
                        
                        similarity = self._calculate_similarity(gemini_title, url_title)
                        if similarity > best_similarity and similarity > 0.5:
                            best_similarity = similarity
                            best_match = dom_link
                    
                    if best_match:
                        merged.append({
                            'url': best_match['url'],
                            'product_code': best_match['product_code'],
                            'title': gemini_product.get('title', ''),
                            'price': gemini_product.get('price', 0),
                            'original_price': gemini_product.get('original_price'),
                            'image_urls': gemini_product.get('image_urls', []),
                            'sale_status': gemini_product.get('sale_status', 'regular'),
                            'availability': gemini_product.get('availability', 'in_stock'),
                            'match_confidence': best_similarity
                        })
                    else:
                        # Skip Gemini products that can't be matched to DOM URLs
                        # These are likely:
                        # - Ad tiles / sponsored content
                        # - Products outside main grid
                        # - Duplicate products with slightly different titles
                        logger.debug(f"Skipping unmatched Gemini product: {gemini_product.get('title', 'N/A')}")
                        # DO NOT add products without URLs!
                
                # Add unmatched DOM links (with their DOM-extracted data!)
                matched_urls = {p['url'] for p in merged if p.get('url')}
                for dom_link in dom_links:
                    if dom_link['url'] not in matched_urls:
                        # Use DOM title/price if available
                        dom_title = dom_link.get('dom_title')
                        dom_price_str = dom_link.get('dom_price')
                        
                        # Parse price
                        price = 0
                        if dom_price_str:
                            price_match = re.search(r'[\d,]+\.?\d*', str(dom_price_str).replace(',', ''))
                            if price_match:
                                try:
                                    price = float(price_match.group(0))
                                except:
                                    pass
                        
                        # Use DOM title or fallback to URL-based title
                        title = dom_title if dom_title else f"[URL only: {dom_link['url'].split('/')[-1]}]"
                        
                        merged.append({
                            'url': dom_link['url'],
                            'product_code': dom_link['product_code'],
                            'title': title,
                            'price': price,
                            'needs_reprocessing': not (dom_title and price > 0)  # Only reprocess if missing data
                        })
            
            logger.debug(f"Merged {len(merged)} products")
            
            validation_stats = {
                'validations_performed': validations_performed,
                'mismatches_found': mismatches_found,
                'title_validations': title_validations,
                'price_validations': price_validations,
                'total_products': len(merged)
            }
            
            if validations_performed > 0:
                accuracy = ((validations_performed - mismatches_found) / validations_performed * 100)
                logger.info(f"✅ Validation: {validations_performed} checks, {mismatches_found} mismatches ({accuracy:.0%})")
            
            return merged, validation_stats
            
        except Exception as e:
            logger.error(f"Merge failed: {e}")
            return gemini_products, {'validations_performed': 0, 'mismatches_found': 0}
    
    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate similarity between two strings"""
        return SequenceMatcher(None, str1, str2).ratio()
    
    def _parse_price_from_text(self, price_text: str) -> float:
        """Parse price from text like '$49.99' or '$100'"""
        try:
            # Remove currency symbols and commas
            clean_text = price_text.replace('$', '').replace(',', '').strip()
            # Extract first number found
            match = re.search(r'(\d+\.?\d*)', clean_text)
            if match:
                return float(match.group(1))
        except:
            pass
        return 0.0
    
    async def _extract_revolve_from_containers(self, retailer: str, strategy: Dict) -> List[Dict]:
        """
        Specialized extraction for Revolve - extract from product containers directly
        This avoids the parent traversal issue where we hit the entire page
        """
        product_links = []
        
        try:
            # Find all product containers
            containers = await self.page.query_selector_all('li.plp__product')
            logger.info(f"Found {len(containers)} Revolve product containers")
            
            for idx, container in enumerate(containers[:100], 1):  # Limit to 100
                try:
                    # Extract URL (use JS evaluation, not get_attribute - handles aria-hidden links)
                    url = None
                    link = await container.query_selector('a[href*="/dp/"]')
                    if link:
                        # Try JS property first (works for aria-hidden links)
                        try:
                            href = await link.evaluate('el => el.href')
                        except:
                            # Fallback to attribute
                            href = await link.get_attribute('href')
                        
                        if href:
                            # href from .evaluate() is already absolute
                            if not href.startswith('http'):
                                base_url = await self.page.evaluate('() => window.location.origin')
                                url = f"{base_url}{href}"
                            else:
                                url = href
                            # Normalize
                            url = url.split('?')[0]
                    
                    # Extract title from img alt
                    dom_title = None
                    img = await container.query_selector('img[alt]')
                    if img:
                        alt = await img.get_attribute('alt')
                        if alt and alt.strip() and 'revolve' not in alt.lower():
                            dom_title = alt.strip()
                    
                    # Extract price from container text (use textContent to avoid getting entire page)
                    dom_price = None
                    try:
                        # Use textContent via JS to get ONLY this container's text (not child frames)
                        container_text = await container.evaluate('(el) => el.textContent')
                        lines = [l.strip() for l in container_text.split('\n') if l.strip()]
                        
                        if idx <= 3:  # Debug first 3
                            logger.debug(f"Container {idx}: {len(lines)} text lines, first 10: {lines[:10]}")
                        
                        # Look for price in short lines
                        for line in lines:
                            if '$' in line and len(line) < 30:
                                price_match = re.search(r'\$\s*(\d+\.?\d*)', line)
                                if price_match:
                                    price_val = float(price_match.group(1))
                                    # Validate price range (avoid extracting random $1 or $99999)
                                    if 15 <= price_val <= 2000:
                                        dom_price = f"${price_match.group(1)}"
                                        logger.debug(f"💰 Container {idx}: Found price {dom_price}")
                                        break
                    except Exception as e:
                        logger.debug(f"Container {idx} price extraction failed: {e}")
                    
                    # Extract product code
                    product_code = self._extract_product_code_from_url(url, retailer) if url else None
                    
                    # Only add if we have URL
                    if url:
                        product_links.append({
                            'url': url,
                            'product_code': product_code,
                            'position': idx,
                            'dom_title': dom_title,
                            'dom_price': dom_price
                        })
                        
                        if dom_price:
                            logger.debug(f"✅ Product {idx}: title={bool(dom_title)}, price={dom_price}")
                    
                except Exception as e:
                    logger.debug(f"Failed to extract from container {idx}: {e}")
                    continue
            
            logger.info(f"📦 Extracted {len(product_links)} products from Revolve containers")
            
            # Deduplicate by URL
            seen_urls = set()
            deduplicated = []
            for product in product_links:
                if product['url'] not in seen_urls:
                    seen_urls.add(product['url'])
                    deduplicated.append(product)
            
            if len(deduplicated) < len(product_links):
                logger.info(f"🧹 Deduplicated: {len(product_links)} → {len(deduplicated)} unique URLs")
            
            return deduplicated
            
        except Exception as e:
            logger.error(f"Revolve container extraction failed: {e}")
            return []
    
    def _extract_product_code_from_url(self, url: str, retailer: str) -> str:
        """Extract product code from URL"""
        patterns = {
            'revolve': r'/dp/([A-Z0-9\-]+)/?',
            'anthropologie': r'/shopop/([A-Z0-9\-]+)',
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
        
        # Fallback
        parts = url.rstrip('/').split('/')
        return parts[-1].split('?')[0] if parts else ""
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
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
