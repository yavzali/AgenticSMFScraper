"""
Markdown Tower - Catalog Extractor
Multi-product extraction from markdown-converted catalog pages

Extracted from: Shared/markdown_extractor.py (catalog logic, lines 232-415, 417-492, 750-829)
Target: <800 lines
"""

# Add shared path for imports
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../../Shared"))

import asyncio
import time
import random
import pickle
import requests
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime, timedelta
from dotenv import load_dotenv
import logging

from logger_config import setup_logging
from cost_tracker import cost_tracker
from markdown_retailer_logic import MarkdownRetailerLogic

logger = setup_logging(__name__)

# Configuration
JINA_ENDPOINT = "https://r.jina.ai/"
CACHE_EXPIRY_DAYS = 2  # Cache for 2 days
MARKDOWN_CACHE_FILE = "markdown_cache.pkl"


class MarkdownCatalogExtractor:
    """
    Extracts multiple products from catalog pages using markdown conversion
    
    Process:
    1. Convert catalog HTML to markdown (via Jina AI)
    2. Smart chunking (extract product listing section)
    3. LLM extraction (DeepSeek V3 → Gemini Flash 2.0)
    4. Parse pipe-separated text format
    5. Extract product codes via regex patterns
    """
    
    def __init__(self, config: Dict = None):
        # Load environment variables
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
        self.retailer_logic = MarkdownRetailerLogic(config)
        
        # Initialize LLM clients
        self._setup_llm_clients()
        
        # Cache file path
        self.cache_file = os.path.join(project_root, 'Extraction/Markdown', MARKDOWN_CACHE_FILE)
        
        logger.info("✅ Markdown Catalog Extractor initialized")
    
    def _setup_llm_clients(self):
        """Initialize DeepSeek and Gemini clients"""
        try:
            # DeepSeek V3 setup
            try:
                from openai import OpenAI
                
                deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
                if not deepseek_api_key:
                    deepseek_api_key = self.config.get("llm_providers", {}).get("deepseek", {}).get("api_key")
                
                if deepseek_api_key:
                    self.deepseek_client = OpenAI(
                        api_key=deepseek_api_key,
                        base_url="https://api.deepseek.com"
                    )
                    self.deepseek_enabled = True
                    logger.info("✅ DeepSeek V3 client initialized")
                else:
                    self.deepseek_enabled = False
                    logger.debug("ℹ️ DeepSeek API key not found - using Gemini only")
            except ImportError:
                self.deepseek_enabled = False
                logger.warning("⚠️ OpenAI client not available for DeepSeek")
            
            # Gemini Flash 2.0 setup
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                
                google_api_key = os.getenv("GOOGLE_API_KEY")
                if not google_api_key:
                    google_api_key = self.config.get("llm_providers", {}).get("google", {}).get("api_key")
                
                if not google_api_key:
                    raise ValueError("No Google API key found in environment or config")
                
                self.gemini_client = ChatGoogleGenerativeAI(
                    model="gemini-2.0-flash-exp",
                    temperature=0.1,
                    max_output_tokens=8000,  # Increased for large catalog arrays
                    google_api_key=google_api_key
                )
                logger.info("✅ Gemini Flash 2.0 client initialized")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Gemini client: {e}")
                raise
                
        except Exception as e:
            logger.error(f"Failed to setup LLM clients: {e}")
            raise
    
    async def extract_catalog(
        self,
        catalog_url: str,
        retailer: str,
        max_pages: int = 10
    ):
        """
        Wrapper method for workflow compatibility
        Calls extract_catalog_products() internally
        """
        return await self.extract_catalog_products(catalog_url, retailer, max_pages)
    
    async def extract_catalog_products(
        self,
        catalog_url: str,
        retailer: str,
        catalog_prompt: str,
        max_products: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Extract ALL products from a catalog/listing page
        
        Args:
            catalog_url: URL of catalog page
            retailer: Retailer name (e.g., 'revolve')
            catalog_prompt: Pre-built catalog-specific prompt
            max_products: Optional limit on products to extract
            
        Returns:
            Dict containing:
            - success: bool
            - products: List[Dict] - Array of product summaries
            - total_found: int
            - method_used: str ('deepseek_v3' or 'gemini_flash_2.0')
            - processing_time: float
            - warnings: List[str]
            - errors: List[str]
        """
        start_time = time.time()
        
        try:
            logger.info(f"🔍 Starting catalog markdown extraction for {retailer}: {catalog_url}")
            
            # Step 1: Fetch markdown content
            markdown_content, final_url = await self._fetch_markdown(catalog_url, retailer)
            if not markdown_content:
                return {
                    'success': False,
                    'products': [],
                    'total_found': 0,
                    'method_used': 'markdown_fetch_failed',
                    'processing_time': time.time() - start_time,
                    'warnings': [],
                    'errors': ['Failed to fetch markdown content']
                }
            
            # Step 2: Smart chunking for large markdown
            if len(markdown_content) > 40000:
                logger.info(f"Large markdown detected ({len(markdown_content)} chars), extracting product section")
                # Look for product listing markers
                product_markers = ['product-card', 'ProductCard', 'product-item', 'data-product', 'class="product']
                
                start_idx = -1
                for marker in product_markers:
                    idx = markdown_content.find(marker)
                    if idx != -1 and (start_idx == -1 or idx < start_idx):
                        start_idx = idx
                
                if start_idx > 0:
                    start_idx = max(0, start_idx - 500)  # Context
                    markdown_chunk = markdown_content[start_idx:start_idx + 40000]
                    logger.info(f"Extracted product section: {len(markdown_chunk)} chars")
                else:
                    markdown_chunk = markdown_content[:40000]
            else:
                markdown_chunk = markdown_content[:50000]
            
            # Step 3: Build full prompt
            full_prompt = f"""{catalog_prompt}

MARKDOWN CONTENT TO ANALYZE:
{markdown_chunk}

Remember: Extract ALL products as pipe-separated format specified above."""
            
            # Step 4: Try DeepSeek V3 first
            extraction_result = None
            method_used = None
            
            if self.deepseek_enabled:
                try:
                    logger.debug(f"Attempting catalog extraction with DeepSeek V3")
                    response = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: self.deepseek_client.chat.completions.create(
                            model="deepseek-chat",
                            messages=[
                                {"role": "system", "content": "You are a specialized AI designed to extract structured product information from catalog pages. Extract ALL products visible and return them in pipe-separated format."},
                                {"role": "user", "content": full_prompt}
                            ],
                            temperature=0.1,
                            max_tokens=8000
                        )
                    )
                    
                    if response and response.choices:
                        content = response.choices[0].message.content
                        extraction_result = self._parse_catalog_text_response(content)
                        method_used = 'deepseek_v3'
                        if extraction_result and extraction_result.get('products'):
                            logger.info(f"✅ DeepSeek V3: {len(extraction_result['products'])} products")
                        
                except Exception as e:
                    logger.warning(f"DeepSeek V3 failed: {e}")
            
            # Step 5: Fallback to Gemini Flash 2.0
            if not extraction_result:
                try:
                    logger.debug(f"Attempting catalog extraction with Gemini Flash 2.0")
                    response = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: self.gemini_client.invoke(full_prompt)
                    )
                    
                    if response and hasattr(response, 'content'):
                        extraction_result = self._parse_catalog_text_response(response.content)
                        method_used = 'gemini_flash_2.0'
                        if extraction_result and extraction_result.get('products'):
                            logger.info(f"✅ Gemini Flash 2.0: {len(extraction_result['products'])} products")
                        
                except Exception as e:
                    logger.warning(f"Gemini Flash 2.0 failed: {e}")
            
            # Step 6: Process results
            processing_time = time.time() - start_time
            
            if not extraction_result:
                return {
                    'success': False,
                    'products': [],
                    'total_found': 0,
                    'method_used': 'all_llms_failed',
                    'processing_time': processing_time,
                    'warnings': [],
                    'errors': ['Both DeepSeek V3 and Gemini Flash 2.0 failed']
                }
            
            # Step 7: Extract products array
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
                    'method_used': method_used,
                    'processing_time': processing_time,
                    'warnings': [f'Expected array, got {type(products)}'],
                    'errors': ['Extraction result was not in array format']
                }
            
            logger.info(f"✅ Catalog extraction successful: {len(products)} products found")
            
            return {
                'success': True,
                'products': products,
                'total_found': len(products),
                'method_used': method_used,
                'processing_time': processing_time,
                'warnings': [],
                'errors': []
            }
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Catalog markdown extraction error: {e}")
            return {
                'success': False,
                'products': [],
                'total_found': 0,
                'method_used': 'error',
                'processing_time': processing_time,
                'warnings': [],
                'errors': [str(e)]
            }
    
    async def _fetch_markdown(self, url: str, retailer: str, max_retries: int = 3) -> Tuple[Optional[str], Optional[str]]:
        """Fetch markdown content using Jina AI with caching"""
        
        # Check cache first
        cached_markdown, cached_final_url = self._get_markdown_cache(url)
        if cached_markdown:
            token_estimate = self._estimate_token_count(cached_markdown)
            threshold = 15000 if retailer == "hm" else 25000
            
            if token_estimate > threshold:
                logger.info(f"Large cached content ({token_estimate} tokens), clearing cache for {url}")
                self._remove_url_from_cache(url)
            else:
                logger.debug(f"Using cached markdown for {url}")
                return cached_markdown, cached_final_url
        
        # Fetch fresh content
        for retry in range(max_retries + 1):
            try:
                clean_url = url.replace("https://r.jina.ai/", "").strip()
                
                # Progressive timeout increase on retries
                base_timeout = 45 + (retry * 20)
                jitter = random.uniform(0.7, 1.3)
                timeout_seconds = base_timeout * jitter
                
                # Browser-like headers
                headers = self._get_jina_headers(retailer)
                
                # Anti-detection delay for certain retailers
                if retailer in ["abercrombie", "hm"]:
                    await asyncio.sleep(random.uniform(1.5, 3.0))
                
                # Make request
                jina_url = f"{JINA_ENDPOINT}{clean_url}"
                logger.debug(f"Fetching markdown from Jina AI: {jina_url}")
                
                response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: requests.get(
                        jina_url,
                        headers=headers,
                        timeout=timeout_seconds,
                        allow_redirects=True
                    )
                )
                
                if response.status_code == 200:
                    fresh_content = response.text
                    fresh_token_estimate = self._estimate_token_count(fresh_content)
                    
                    if fresh_token_estimate > 30000:
                        logger.warning(f"Fetched content very large ({fresh_token_estimate} tokens)")
                    
                    # Cache the result
                    self._save_markdown_cache(url, fresh_content, clean_url)
                    logger.debug(f"Successfully fetched markdown ({fresh_token_estimate} tokens)")
                    return fresh_content, clean_url
                else:
                    logger.warning(f"Jina AI returned status {response.status_code}")
                    
            except requests.exceptions.Timeout:
                sleep_time = (2**retry) + random.uniform(0, 2)
                logger.warning(f"Jina AI timeout (attempt {retry + 1}), sleeping {sleep_time:.1f}s")
                await asyncio.sleep(sleep_time)
            except Exception as e:
                if retry < max_retries:
                    sleep_time = retry * 2 + random.uniform(1, 3)
                    logger.warning(f"Jina AI error (attempt {retry + 1}): {e}, sleeping {sleep_time:.1f}s")
                    await asyncio.sleep(sleep_time)
                else:
                    logger.error(f"Jina AI failed after all retries: {e}")
        
        return None, url
    
    def _get_jina_headers(self, retailer: str) -> Dict[str, str]:
        """Get Jina AI request headers"""
        headers = {
            'Accept': 'text/plain, */*',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
        }
        
        # Add API key if available
        jina_api_key = os.getenv("JINA_API_KEY")
        if jina_api_key:
            headers['Authorization'] = f'Bearer {jina_api_key}'
        
        return headers
    
    def _parse_catalog_text_response(self, content: str) -> Optional[Dict[str, Any]]:
        """Parse pipe-separated text format - NO JSON parsing!"""
        try:
            products = []
            lines = content.split('\n')
            
            for line in lines:
                line = line.strip()
                
                # Look for product lines starting with "PRODUCT |"
                if not line.startswith('PRODUCT |'):
                    continue
                
                # Remove prefix
                line = line[9:].strip()
                
                # Parse pipe-separated fields
                product = {}
                fields = line.split('|')
                
                for field in fields:
                    field = field.strip()
                    if '=' not in field:
                        continue
                    
                    key, value = field.split('=', 1)
                    key = key.strip().upper()
                    value = value.strip()
                    
                    if key == 'URL':
                        product['url'] = value
                        # Extract product code
                        product['product_code'] = self.retailer_logic.extract_product_code(value, '')
                    elif key == 'TITLE':
                        product['title'] = value
                    elif key == 'PRICE':
                        try:
                            price_str = value.replace('$', '').replace(',', '').strip()
                            if price_str:
                                product['price'] = float(price_str)
                        except:
                            pass
                    elif key == 'ORIGINAL_PRICE':
                        try:
                            price_str = value.replace('$', '').replace(',', '').strip()
                            if price_str:
                                product['original_price'] = float(price_str)
                                product['sale_status'] = 'on_sale'
                        except:
                            pass
                    elif key == 'IMAGE':
                        if value:
                            product['image_urls'] = [value]
                
                # Only add if we got essential data
                if product.get('url') and product.get('title'):
                    if 'sale_status' not in product:
                        product['sale_status'] = 'regular'
                    if 'availability' not in product:
                        product['availability'] = 'in_stock'
                    
                    products.append(product)
            
            if products:
                logger.info(f"📦 Parsed {len(products)} products from pipe-separated format")
            else:
                logger.warning(f"⚠️ No products found. Response preview: {content[:500]}")
            
            return {
                'products': products,
                'total_found': len(products)
            }
            
        except Exception as e:
            logger.error(f"Failed to parse catalog text response: {e}")
            return None
    
    def _estimate_token_count(self, text: str) -> int:
        """Rough token count estimation"""
        return len(text) // 4
    
    def _get_markdown_cache(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """Get markdown from cache if not expired"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'rb') as f:
                    cache = pickle.load(f)
                
                if url in cache:
                    cached_data = cache[url]
                    timestamp = cached_data.get('timestamp')
                    markdown = cached_data.get('markdown')
                    final_url = cached_data.get('final_url')
                    
                    if timestamp and markdown:
                        age_days = (datetime.now() - timestamp).days
                        if age_days < CACHE_EXPIRY_DAYS:
                            return markdown, final_url
        except Exception as e:
            logger.debug(f"Cache read error: {e}")
        
        return None, None
    
    def _save_markdown_cache(self, url: str, markdown: str, final_url: str):
        """Save markdown to cache"""
        try:
            cache = {}
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'rb') as f:
                    cache = pickle.load(f)
            
            cache[url] = {
                'markdown': markdown,
                'final_url': final_url,
                'timestamp': datetime.now()
            }
            
            with open(self.cache_file, 'wb') as f:
                pickle.dump(cache, f)
                
        except Exception as e:
            logger.debug(f"Cache write error: {e}")
    
    def _remove_url_from_cache(self, url: str) -> bool:
        """Remove URL from cache"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'rb') as f:
                    cache = pickle.load(f)
                
                if url in cache:
                    del cache[url]
                    with open(self.cache_file, 'wb') as f:
                        pickle.dump(cache, f)
                    return True
        except Exception as e:
            logger.debug(f"Cache removal error: {e}")
        
        return False
