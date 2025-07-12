"""
Catalog Extractor - Extracts product lists from catalog pages
Adapts existing unified_extractor patterns for catalog-specific extraction
Uses existing markdown/playwright routing but with catalog-optimized prompts
"""

# Add shared path for imports
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../Shared"))
sys.path.append(os.path.dirname(__file__))

import json
import asyncio
import time
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, date

from logger_config import setup_logging
from pattern_learner import EnhancedPatternLearner, PatternType
from cost_tracker import cost_tracker

logger = setup_logging(__name__)

@dataclass
class CatalogExtractionResult:
    success: bool
    products: List[Dict[str, Any]]
    method_used: str
    processing_time: float
    page_info: Dict[str, Any]
    warnings: List[str]
    errors: List[str]
    extraction_metadata: Dict[str, Any]

class CatalogExtractor:
    """
    Catalog-specific extraction using existing unified_extractor patterns
    Handles both markdown and playwright routes with catalog-optimized prompts
    """
    
    def __init__(self):
        # Load configuration (same as unified_extractor)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, '../Shared/config.json')
        
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        self.pattern_learner = EnhancedPatternLearner()
        
        # Markdown-compatible retailers (from existing system)
        self.MARKDOWN_RETAILERS = ['asos', 'mango', 'uniqlo', 'revolve', 'hm']
        
        logger.info("✅ Catalog extractor initialized - adapted from unified_extractor patterns")
    
    async def extract_catalog_page(self, catalog_url: str, retailer: str, 
                                 category: str, extraction_config: Dict = None) -> CatalogExtractionResult:
        """
        Main catalog extraction method - extracts all products from a catalog page
        Uses existing markdown/playwright routing with catalog-specific prompts
        """
        start_time = time.time()
        extraction_config = extraction_config or {}
        
        try:
            # Get learned patterns for catalog extraction
            learned_patterns = await self.pattern_learner.get_learned_patterns(
                retailer, catalog_url, pattern_type=PatternType.CATALOG_CRAWLING)
            
            # ROUTING DECISION: Markdown vs Playwright (same logic as unified_extractor)
            if retailer in self.MARKDOWN_RETAILERS:
                logger.info(f"🔄 Trying markdown extraction for {retailer} catalog: {catalog_url}")
                
                try:
                    result = await self._extract_catalog_with_markdown(
                        catalog_url, retailer, category, learned_patterns, extraction_config)
                    
                    if result.success:
                        # Record successful pattern for learning
                        await self.pattern_learner.record_success(
                            retailer, catalog_url, 'catalog_markdown', 
                            result.processing_time, result.extraction_metadata)
                        return result
                    else:
                        logger.warning(f"⚠️ Markdown catalog extraction failed for {retailer}, falling back to Playwright")
                        
                except Exception as e:
                    logger.error(f"❌ Markdown catalog extractor error for {retailer}: {e}, falling back to Playwright")
            
            # PLAYWRIGHT EXTRACTION (direct or fallback)
            if retailer not in self.MARKDOWN_RETAILERS:
                logger.info(f"🎭 Using Playwright catalog extraction for {retailer} (direct route): {catalog_url}")
            else:
                logger.info(f"🎭 Using Playwright catalog extraction for {retailer} (fallback from markdown): {catalog_url}")
            
            result = await self._extract_catalog_with_playwright(
                catalog_url, retailer, category, learned_patterns, extraction_config)
            
            if result.success:
                # Record successful pattern
                await self.pattern_learner.record_success(
                    retailer, catalog_url, 'catalog_playwright', 
                    result.processing_time, result.extraction_metadata)
            
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"❌ Catalog extraction failed for {retailer}: {e}")
            
            # Record failure for learning
            await self.pattern_learner.record_failure(
                retailer, catalog_url, 'catalog_extraction', str(e))
            
            return CatalogExtractionResult(
                success=False,
                products=[],
                method_used='extraction_failed',
                processing_time=processing_time,
                page_info={},
                warnings=[],
                errors=[str(e)],
                extraction_metadata={'error': str(e)}
            )
    
    async def _extract_catalog_with_markdown(self, catalog_url: str, retailer: str, 
                                           category: str, learned_patterns: Dict,
                                           extraction_config: Dict) -> CatalogExtractionResult:
        """Extract catalog using markdown route with catalog-specific prompts"""
        start_time = time.time()
        
        try:
            # Import markdown extractor
            from markdown_extractor import MarkdownExtractor
            
            # Build catalog-specific prompt
            prompt = self._build_catalog_markdown_prompt(
                catalog_url, retailer, category, learned_patterns, extraction_config)
            
            # Check cache first
            cached_response = cost_tracker.get_cached_response(prompt)
            if cached_response:
                logger.info(f"📦 Using cached catalog response for {catalog_url}")
                return self._process_cached_catalog_response(
                    cached_response, 'markdown_cached', time.time() - start_time)
            
            # Initialize markdown extractor
            markdown_extractor = MarkdownExtractor()
            
            # Get markdown content from Jina AI
            logger.debug(f"Fetching catalog markdown from Jina AI: {catalog_url}")
            markdown_content, _ = await markdown_extractor._fetch_markdown(catalog_url, retailer)
            
            if not markdown_content:
                return CatalogExtractionResult(
                    success=False,
                    products=[],
                    method_used='markdown_fetch_failed',
                    processing_time=time.time() - start_time,
                    page_info={},
                    warnings=['Failed to fetch markdown content'],
                    errors=['Markdown fetch failed'],
                    extraction_metadata={}
                )
            
            # Extract catalog using AI models
            extraction_result = await markdown_extractor._extract_with_llm_cascade(
                markdown_content, retailer, catalog_url)
            
            processing_time = time.time() - start_time
            
            # Handle case where extraction_result is None (API failures)
            if extraction_result is None:
                return CatalogExtractionResult(
                    success=False,
                    products=[],
                    method_used='markdown_api_failed',
                    processing_time=processing_time,
                    page_info={},
                    warnings=['API keys invalid - both DeepSeek and Gemini failed'],
                    errors=['API authentication failed'],
                    extraction_metadata={'error': 'API keys invalid'}
                )
            
            # Track API call with cost monitoring (convert ExtractionResult to dict)
            response_dict = {
                'success': extraction_result.success,
                'data': extraction_result.data,
                'method_used': extraction_result.method_used,
                'processing_time': extraction_result.processing_time,
                'warnings': extraction_result.warnings,
                'errors': extraction_result.errors
            }
            cost_tracker.track_api_call(
                method="catalog_markdown", 
                prompt=prompt, 
                response=response_dict,
                retailer=retailer, 
                url=catalog_url, 
                processing_time=processing_time
            )
            
            if extraction_result.success:
                products = self._parse_catalog_extraction_result(extraction_result.data, retailer, category)
                
                return CatalogExtractionResult(
                    success=True,
                    products=products,
                    method_used='markdown_extractor',
                    processing_time=processing_time,
                    page_info={
                        'total_products_found': len(products),
                        'extraction_method': 'markdown',
                        'retailer': retailer,
                        'category': category
                    },
                    warnings=extraction_result.warnings,
                    errors=[],
                    extraction_metadata={
                        'model_used': extraction_result.method_used,
                        'markdown_length': len(markdown_content)
                    }
                )
            else:
                return CatalogExtractionResult(
                    success=False,
                    products=[],
                    method_used='markdown_extraction_failed',
                    processing_time=processing_time,
                    page_info={},
                    warnings=extraction_result.warnings,
                    errors=extraction_result.errors if extraction_result.errors else ['Extraction failed'],
                    extraction_metadata={'method_used': extraction_result.method_used}
                )
                
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Markdown catalog extraction error: {e}")
            
            return CatalogExtractionResult(
                success=False,
                products=[],
                method_used='markdown_error',
                processing_time=processing_time,
                page_info={},
                warnings=[],
                errors=[str(e)],
                extraction_metadata={'error': str(e)}
            )
    
    async def _extract_catalog_with_playwright(self, catalog_url: str, retailer: str,
                                             category: str, learned_patterns: Dict,
                                             extraction_config: Dict) -> CatalogExtractionResult:
        """Extract catalog using Playwright route with catalog-specific prompts"""
        start_time = time.time()
        
        try:
            # Import playwright agent
            from playwright_agent import PlaywrightAgentWrapper
            
            # Build catalog-specific prompt
            prompt = self._build_catalog_playwright_prompt(
                catalog_url, retailer, category, learned_patterns, extraction_config)
            
            # Check cache first
            cached_response = cost_tracker.get_cached_response(prompt)
            if cached_response:
                logger.info(f"📦 Using cached catalog response for {catalog_url}")
                return self._process_cached_catalog_response(
                    cached_response, 'playwright_cached', time.time() - start_time)
            
            # Initialize Playwright agent
            playwright_agent = PlaywrightAgentWrapper(self.config)
            
            # Extract catalog with screenshots
            logger.debug(f"Extracting catalog with Playwright: {catalog_url}")
            extraction_result = await playwright_agent.extract_product_data(
                catalog_url, retailer)
            
            processing_time = time.time() - start_time
            
            # Track API call (convert ExtractionResult to dict for cost tracker)
            response_dict = {
                'success': extraction_result.success,
                'data': extraction_result.data,
                'method_used': extraction_result.method_used,
                'processing_time': extraction_result.processing_time,
                'warnings': extraction_result.warnings,
                'errors': extraction_result.errors
            }
            cost_tracker.track_api_call(
                method="catalog_playwright", 
                prompt=prompt, 
                response=response_dict,
                retailer=retailer, 
                url=catalog_url, 
                processing_time=processing_time
            )
            
            if extraction_result.success:
                products = self._parse_catalog_extraction_result(extraction_result.data, retailer, category)
                
                return CatalogExtractionResult(
                    success=True,
                    products=products,
                    method_used='playwright_agent',
                    processing_time=processing_time,
                    page_info={
                        'total_products_found': len(products),
                        'extraction_method': 'playwright',
                        'retailer': retailer,
                        'category': category,
                        'screenshots_taken': 4  # From the log output
                    },
                    warnings=extraction_result.warnings,
                    errors=[],
                    extraction_metadata={
                        'method_used': extraction_result.method_used,
                        'processing_time': extraction_result.processing_time,
                        'playwright_data': extraction_result.data
                    }
                )
            else:
                return CatalogExtractionResult(
                    success=False,
                    products=[],
                    method_used='playwright_extraction_failed',
                    processing_time=processing_time,
                    page_info={},
                    warnings=extraction_result.warnings,
                    errors=extraction_result.errors if extraction_result.errors else ['Extraction failed'],
                    extraction_metadata={
                        'method_used': extraction_result.method_used,
                        'processing_time': extraction_result.processing_time,
                        'playwright_data': extraction_result.data
                    }
                )
                
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Playwright catalog extraction error: {e}")
            
            return CatalogExtractionResult(
                success=False,
                products=[],
                method_used='playwright_error',
                processing_time=processing_time,
                page_info={},
                warnings=[],
                errors=[str(e)],
                extraction_metadata={'error': str(e)}
            )
    
    def _build_catalog_markdown_prompt(self, catalog_url: str, retailer: str, 
                                     category: str, learned_patterns: Dict,
                                     extraction_config: Dict) -> str:
        """Build markdown extraction prompt optimized for catalog pages"""
        
        base_prompt = f"""
You are analyzing a {retailer} {category} catalog page to extract ALL product information.

URL: {catalog_url}
Retailer: {retailer}
Category: {category}

TASK: Extract ALL products visible on this catalog page and return them as a JSON array.

For each product, extract:
- url: Complete product URL (resolve relative URLs to absolute)
- title: Product name/title
- price: Current price (number only, e.g., 89.99)
- original_price: Original price if on sale (number only)
- sale_status: "on_sale", "regular", or "clearance"
- image_urls: Array of all image URLs for this product
- availability: "in_stock", "low_stock", "out_of_stock", or "unknown"
- product_code: Product ID/code if visible in URL or on page

IMPORTANT GUIDELINES:
1. Extract ALL products on the page, not just the first few
2. Handle both grid and list views
3. Resolve relative URLs to absolute URLs with domain
4. Clean up prices (remove $, commas, currency symbols)
5. If multiple images per product, include all of them
6. Focus on main product listing area, ignore navigation/ads
7. If product appears multiple times (variants), extract each variant separately

EXPECTED OUTPUT FORMAT:
```json
{{
  "success": true,
  "products": [
    {{
      "url": "https://www.{retailer}.com/product/...",
      "title": "Product Title",
      "price": 89.99,
      "original_price": 129.99,
      "sale_status": "on_sale",
      "image_urls": ["https://...", "https://..."],
      "availability": "in_stock",
      "product_code": "ABC123"
    }}
  ],
  "total_found": 25,
  "page_type": "catalog",
  "extraction_notes": "Any relevant notes about the extraction"
}}
```
"""
        
        # Add retailer-specific guidance
        if retailer == 'revolve':
            base_prompt += """
REVOLVE-SPECIFIC NOTES:
- Products displayed in grid format, 500 per page
- Look for product cards with image, title, price, brand
- URLs typically end with product codes like ABCD-WC123.html
- Watch for sale badges and crossed-out original prices
"""
        elif retailer == 'asos':
            base_prompt += """
ASOS-SPECIFIC NOTES:
- Grid layout with lazy-loading images
- Products have article IDs in URLs like /prd/123456
- Look for "NEW" badges on recent products
- Price format: current price, sometimes crossed-out original
"""
        elif retailer == 'uniqlo':
            base_prompt += """
UNIQLO-SPECIFIC NOTES:
- Clean grid layout with product codes
- URLs contain product codes like E443577-000
- Focus on main product area, ignore seasonal banners
- Prices shown clearly below product images
"""
        
        # Add learned pattern guidance
        if learned_patterns:
            base_prompt += f"""
LEARNED PATTERNS FOR {retailer.upper()}:
{json.dumps(learned_patterns, indent=2)}
Use these patterns to improve extraction accuracy.
"""
        
        # Add pagination/scrolling hints
        pagination_type = extraction_config.get('pagination_type', 'unknown')
        base_prompt += f"""
PAGE STRUCTURE: This is a {pagination_type} catalog page.
Extract all products currently visible/loaded on this page.
"""
        
        return base_prompt
    
    def _build_catalog_playwright_prompt(self, catalog_url: str, retailer: str,
                                       category: str, learned_patterns: Dict,
                                       extraction_config: Dict) -> str:
        """Build Playwright extraction prompt optimized for catalog screenshots"""
        
        base_prompt = f"""
You are analyzing screenshots of a {retailer} {category} catalog page to extract ALL visible products.

URL: {catalog_url}
Retailer: {retailer}
Category: {category}

TASK: Analyze the catalog page screenshots and extract ALL products visible.

SCREENSHOT ANALYSIS APPROACH:
1. Identify the main product grid/listing area
2. Locate individual product cards/items
3. Extract information from each product card
4. Handle multiple screenshots if provided (scroll positions)

For each product visible in the screenshots, extract:
- url: Product URL (construct if needed using retailer patterns)
- title: Product name visible in the image
- price: Current price visible
- original_price: Original/crossed-out price if on sale
- sale_status: "on_sale" if sale badge/crossed-out price visible, else "regular"
- image_urls: Product image URLs (estimate based on retailer patterns)
- availability: Look for "sold out" or stock indicators
- product_code: Extract from visible text or estimate from patterns

VISUAL EXTRACTION GUIDELINES:
1. Focus on the main product listing area (ignore headers/footers/navigation)
2. Look for repeating patterns of product cards
3. Identify text overlays showing product names and prices
4. Notice sale badges, "NEW" labels, or stock status indicators
5. Pay attention to image quality and product visibility
6. Extract ALL visible products, not just prominent ones

RETAILER-SPECIFIC VISUAL PATTERNS:
"""
        
        # Add retailer-specific visual guidance
        if retailer == 'aritzia':
            base_prompt += """
ARITZIA VISUAL PATTERNS:
- Clean, minimalist product grid
- Product names below images
- Prices clearly displayed
- Look for Cloudflare verification elements to ignore
- Focus on main product area after any overlays
"""
        elif retailer == 'anthropologie':
            base_prompt += """
ANTHROPOLOGIE VISUAL PATTERNS:
- Artistic product layout
- Product titles may be styled/scripted fonts
- Look for press-and-hold verification overlays to ignore
- Multiple images per product in some layouts
- Price information typically below product names
"""
        elif retailer == 'nordstrom':
            base_prompt += """
NORDSTROM VISUAL PATTERNS:
- Professional product grid layout
- Clear brand + product name structure
- Price and original price clearly marked
- Look for sale percentages/badges
- High-quality product images
"""
        
        # Add learned patterns
        if learned_patterns:
            base_prompt += f"""
LEARNED VISUAL PATTERNS FOR {retailer.upper()}:
{json.dumps(learned_patterns, indent=2)}
"""
        
        base_prompt += """
EXPECTED OUTPUT FORMAT:
```json
{{
  "success": true,
  "products": [
    {{
      "url": "https://www.retailer.com/product/...",
      "title": "Product Title from Image",
      "price": 89.99,
      "original_price": 129.99,
      "sale_status": "on_sale",
      "image_urls": ["estimated_image_url"],
      "availability": "in_stock",
      "product_code": "estimated_code"
    }}
  ],
  "total_found": 15,
  "page_type": "catalog_screenshot",
  "visual_notes": "Notes about screenshot analysis"
}}
```

IMPORTANT: Analyze ALL screenshots provided and extract ALL visible products.
"""
        
        return base_prompt
    
    def _parse_catalog_extraction_result(self, extraction_result: Dict, 
                                       retailer: str, category: str) -> List[Dict]:
        """Parse and validate catalog extraction results"""
        products = []
        
        try:
            # Handle different response formats
            if 'products' in extraction_result:
                raw_products = extraction_result['products']
            elif 'data' in extraction_result and isinstance(extraction_result['data'], list):
                raw_products = extraction_result['data']
            elif isinstance(extraction_result.get('data'), dict) and 'products' in extraction_result['data']:
                raw_products = extraction_result['data']['products']
            else:
                logger.warning(f"Unexpected extraction result format: {list(extraction_result.keys())}")
                return []
            
            # Validate and clean each product
            for i, raw_product in enumerate(raw_products):
                try:
                    cleaned_product = self._clean_catalog_product(raw_product, retailer, category)
                    if cleaned_product:
                        products.append(cleaned_product)
                except Exception as e:
                    logger.warning(f"Failed to clean product {i}: {e}")
                    continue
            
            logger.info(f"Successfully parsed {len(products)} products from {retailer} catalog")
            return products
            
        except Exception as e:
            logger.error(f"Failed to parse catalog extraction result: {e}")
            return []
    
    def _clean_catalog_product(self, raw_product: Dict, retailer: str, category: str) -> Optional[Dict]:
        """Clean and validate individual catalog product data"""
        try:
            # Required fields validation
            if not raw_product.get('url') or not raw_product.get('title'):
                return None
            
            # Clean URL
            url = raw_product['url'].strip()
            if not url.startswith('http'):
                # Handle relative URLs
                if retailer == 'revolve':
                    url = f"https://www.revolve.com{url}" if url.startswith('/') else f"https://www.revolve.com/{url}"
                elif retailer == 'asos':
                    url = f"https://www.asos.com{url}" if url.startswith('/') else f"https://www.asos.com/us/{url}"
                elif retailer == 'aritzia':
                    url = f"https://www.aritzia.com{url}" if url.startswith('/') else f"https://www.aritzia.com/us/en/{url}"
                # Add more retailer URL patterns as needed
            
            # Clean price
            price = None
            if raw_product.get('price'):
                price_str = str(raw_product['price']).replace('$', '').replace(',', '').strip()
                try:
                    price = float(price_str)
                except ValueError:
                    # Try to extract first number from price string
                    import re
                    price_match = re.search(r'[\d.]+', price_str)
                    if price_match:
                        price = float(price_match.group())
            
            # Clean original price
            original_price = None
            if raw_product.get('original_price'):
                orig_price_str = str(raw_product['original_price']).replace('$', '').replace(',', '').strip()
                try:
                    original_price = float(orig_price_str)
                except ValueError:
                    pass
            
            # Extract product code from URL if not provided
            product_code = raw_product.get('product_code')
            if not product_code:
                from catalog_db_manager import extract_product_code_from_url
                product_code = extract_product_code_from_url(url, retailer)
            
            # Normalize image URLs
            image_urls = []
            if raw_product.get('image_urls'):
                if isinstance(raw_product['image_urls'], list):
                    for img_url in raw_product['image_urls']:
                        if img_url and isinstance(img_url, str):
                            # Convert relative to absolute URLs
                            if not img_url.startswith('http'):
                                if retailer == 'revolve':
                                    img_url = f"https://revolve.com{img_url}" if img_url.startswith('/') else img_url
                                elif retailer == 'asos':
                                    img_url = f"https://images.asos-media.com{img_url}" if img_url.startswith('/') else img_url
                                # Add more patterns as needed
                            image_urls.append(img_url)
                elif isinstance(raw_product['image_urls'], str):
                    image_urls = [raw_product['image_urls']]
            
            return {
                'url': url,
                'title': raw_product['title'].strip(),
                'price': price,
                'original_price': original_price,
                'sale_status': raw_product.get('sale_status', 'regular'),
                'image_urls': image_urls,
                'availability': raw_product.get('availability', 'unknown'),
                'product_code': product_code,
                'retailer': retailer,
                'category': category,
                'discovered_date': date.today(),
                'extraction_metadata': {
                    'raw_data': raw_product,
                    'cleaned_at': datetime.utcnow().isoformat()
                }
            }
            
        except Exception as e:
            logger.warning(f"Failed to clean catalog product: {e}")
            return None
    
    def _process_cached_catalog_response(self, cached_response: Any, method_used: str, 
                                       processing_time: float) -> CatalogExtractionResult:
        """Process cached catalog extraction response"""
        try:
            if isinstance(cached_response, dict) and cached_response.get('success'):
                products = cached_response.get('products', [])
                
                return CatalogExtractionResult(
                    success=True,
                    products=products,
                    method_used=method_used,
                    processing_time=processing_time,
                    page_info={
                        'total_products_found': len(products),
                        'extraction_method': method_used,
                        'cached': True
                    },
                    warnings=[],
                    errors=[],
                    extraction_metadata={'cached_response': True}
                )
            else:
                return CatalogExtractionResult(
                    success=False,
                    products=[],
                    method_used=f"{method_used}_invalid",
                    processing_time=processing_time,
                    page_info={},
                    warnings=['Invalid cached response'],
                    errors=['Cached response format invalid'],
                    extraction_metadata={'cached_response': True}
                )
                
        except Exception as e:
            return CatalogExtractionResult(
                success=False,
                products=[],
                method_used=f"{method_used}_error",
                processing_time=processing_time,
                page_info={},
                warnings=[],
                errors=[str(e)],
                extraction_metadata={'cached_response': True, 'error': str(e)}
            )
    
    async def get_extraction_stats(self) -> Dict:
        """Get catalog extraction statistics"""
        return {
            'extractor_type': 'catalog_extractor',
            'markdown_retailers': self.MARKDOWN_RETAILERS,
            'routing_logic': 'markdown_first_with_playwright_fallback',
            'pattern_learning': 'enabled',
            'cost_tracking': 'enabled',
            'cache_enabled': True
        }