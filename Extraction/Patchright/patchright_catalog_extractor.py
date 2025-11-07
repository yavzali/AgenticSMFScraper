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
            if 'cloudflare' in verification_strategy.get('special_notes', '').lower():
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
            
            # Step 11: DOM-first override for tall pages (Anthropologie)
            if retailer.lower() == 'anthropologie' and len(dom_product_links) > len(products) * 2:
                logger.info(f"🔄 DOM-FIRST MODE: Using DOM URLs (Gemini only found {len(products)}/{len(dom_product_links)})")
                logger.info("   Reason: Screenshot compression made products unreadable")
                
                merged_products = []
                for link_data in dom_product_links:
                    merged_products.append({
                        'url': link_data['url'],
                        'product_code': link_data.get('product_code', ''),
                        'title': link_data.get('title', 'Unknown Product'),
                        'price': link_data.get('price'),
                        'image_url': link_data.get('image_url'),
                        'sale_status': 'unknown',
                        'extraction_source': 'dom_only'
                    })
                validation_stats = {'dom_only_mode': True, 'reason': 'screenshot_too_tall'}
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
                locale='en-US'
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
            
            # Get selectors from strategy
            selectors = strategy.get('product_selectors', [])
            
            # Add common patterns
            selectors.extend([
                'a[data-testid="product-card-link"]',
                'a[href*="/product"]', 'a[href*="/p/"]', 'a[href*="/dp/"]',
                '.product-card a', '.product-item a', '[data-product-id]',
                'a.product-link', 'a.product-tile', 'a[data-product-url]',
                'a[href*="/shop/"]', 'a[href*="/item/"]'
            ])
            
            # Try each selector
            for selector in selectors:
                try:
                    links = await self.page.query_selector_all(selector)
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
                                parent = link
                                for _ in range(3):
                                    parent = await parent.evaluate_handle('el => el.parentElement')
                                    if parent:
                                        # Try title selectors
                                        title_selectors = ['.title', '.product-title', '.name', 'h2', 'h3']
                                        for title_sel in title_selectors:
                                            try:
                                                title_el = await parent.query_selector(title_sel)
                                                if title_el:
                                                    dom_title = (await title_el.inner_text()).strip()
                                                    if len(dom_title) > 5:
                                                        break
                                            except:
                                                continue
                                        
                                        # Try price selectors
                                        price_selectors = ['.price', '.product-price', '[data-testid*="price"]']
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
            
            return product_links
            
        except Exception as e:
            logger.error(f"DOM extraction failed: {e}")
            return []
    
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
                        gemini_product['url'] = None
                        gemini_product['product_code'] = None
                        merged.append(gemini_product)
                
                # Add unmatched DOM links
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
    
    def _extract_product_code_from_url(self, url: str, retailer: str) -> str:
        """Extract product code from URL"""
        patterns = {
            'revolve': r'/dp/([A-Z0-9\-]+)/?',
            'anthropologie': r'/shopop/([A-Z0-9\-]+)',
            'abercrombie': r'/shop/([A-Za-z0-9\-]+)/?$',
            'urban_outfitters': r'/([A-Za-z0-9\-]+)/?$',
            'aritzia': r'/([A-Z0-9\-]+)/?$'
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
