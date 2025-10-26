"""
Markdown Extractor - Jina AI + LLM extraction for specific retailers
Handles ASOS, Mango, Uniqlo, Revolve, H&M with fallback to agent extraction.
"""

# Add shared path for imports
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../Shared"))
sys.path.append(os.path.dirname(__file__))

import json
import re
import asyncio
import pickle
import os
import time
import random
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from urllib.parse import urlparse
from dotenv import load_dotenv

from logger_config import setup_logging
from cost_tracker import cost_tracker

logger = setup_logging(__name__)

# Markdown retailers that this extractor handles
MARKDOWN_RETAILERS = ["asos", "mango", "uniqlo", "revolve", "hm"]

# Configuration
JINA_ENDPOINT = "https://r.jina.ai/"
TOKEN_LIMIT = 120000
CACHE_EXPIRY_DAYS = 5
MARKDOWN_CACHE_FILE = "markdown_cache.pkl"

@dataclass
class MarkdownExtractionResult:
    success: bool
    data: Dict[str, Any]
    method_used: str
    processing_time: float
    warnings: List[str]
    errors: List[str]
    should_fallback: bool = False

class MarkdownExtractor:
    def __init__(self):
        # Load environment variables from .env file
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.join(script_dir, '..')
        env_path = os.path.join(project_root, '.env')
        # Force override any existing environment variables with .env values
        load_dotenv(env_path, override=True)
        
        # Load configuration
        config_path = os.path.join(script_dir, '../Shared/config.json')
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        # Initialize LLM clients
        self._setup_llm_clients()
        
        logger.info("Markdown extractor initialized for retailers: " + ", ".join(MARKDOWN_RETAILERS))
    
    def _setup_llm_clients(self):
        """Initialize DeepSeek and Gemini clients"""
        try:
            # DeepSeek V3 setup
            try:
                from openai import OpenAI
                
                # Get API key from environment variable or config (like Gemini handling)
                deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
                if not deepseek_api_key:
                    # Fallback to config if environment variable not set
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
                    logger.debug("ℹ️ DeepSeek API key not found in environment or config - using Gemini only")
            except ImportError:
                self.deepseek_enabled = False
                logger.warning("⚠️ OpenAI client not available for DeepSeek")
            
            # Gemini Flash 2.0 setup
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                
                # Get API key from environment variable (like other components)
                google_api_key = os.getenv("GOOGLE_API_KEY")
                if not google_api_key:
                    # Fallback to config if environment variable not set
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
    
    async def extract_product_data(self, url: str, retailer: str) -> MarkdownExtractionResult:
        """Main extraction method for markdown-supported retailers"""
        start_time = asyncio.get_event_loop().time()
        
        # Validate retailer is supported
        if retailer not in MARKDOWN_RETAILERS:
            return MarkdownExtractionResult(
                success=False,
                data={},
                method_used="markdown_extractor",
                processing_time=0,
                warnings=[],
                errors=[f"Retailer {retailer} not supported by markdown extractor"],
                should_fallback=True
            )
        
        try:
            logger.info(f"Starting markdown extraction for {retailer}: {url}")
            
            # Step 1: Fetch markdown content
            markdown_content, final_url = await self._fetch_markdown(url, retailer)
            if not markdown_content:
                logger.warning(f"Failed to fetch markdown for {url}")
                return MarkdownExtractionResult(
                    success=False,
                    data={},
                    method_used="markdown_extractor",
                    processing_time=asyncio.get_event_loop().time() - start_time,
                    warnings=[],
                    errors=["Failed to fetch markdown content"],
                    should_fallback=True
                )
            
            # Step 2: Handle oversized content
            if self._is_too_large(markdown_content):
                logger.info(f"Large markdown detected for {retailer}, extracting product section")
                product_section = await self._extract_product_section(markdown_content, retailer)
                if product_section:
                    markdown_content = product_section
                else:
                    logger.warning(f"Failed to extract product section for {url}")
                    return MarkdownExtractionResult(
                        success=False,
                        data={},
                        method_used="markdown_extractor",
                        processing_time=asyncio.get_event_loop().time() - start_time,
                        warnings=[],
                        errors=["Markdown too large and section extraction failed"],
                        should_fallback=True
                    )
            
            # Step 3: Extract product information using model cascade
            extracted_data = await self._extract_with_llm_cascade(markdown_content, retailer, url)
            
            if not extracted_data:
                logger.warning(f"LLM extraction failed for {url}")
                return MarkdownExtractionResult(
                    success=False,
                    data={},
                    method_used="markdown_extractor",
                    processing_time=asyncio.get_event_loop().time() - start_time,
                    warnings=[],
                    errors=["LLM extraction failed"],
                    should_fallback=True
                )
            
            # Step 4: Rigorous validation
            validation_issues = self._validate_extracted_data(extracted_data, retailer, url)
            
            processing_time = asyncio.get_event_loop().time() - start_time
            
            if validation_issues:
                logger.warning(f"Validation failed for {retailer}: {', '.join(validation_issues)}")
                return MarkdownExtractionResult(
                    success=False,
                    data=extracted_data,
                    method_used="markdown_extractor",
                    processing_time=processing_time,
                    warnings=validation_issues,
                    errors=["Validation failed"],
                    should_fallback=True
                )
            
            # Success!
            logger.info(f"✅ Markdown extraction successful for {retailer} in {processing_time:.2f}s")
            return MarkdownExtractionResult(
                success=True,
                data=extracted_data,
                method_used="markdown_extractor",
                processing_time=processing_time,
                warnings=[],
                errors=[],
                should_fallback=False
            )
            
        except Exception as e:
            processing_time = asyncio.get_event_loop().time() - start_time
            logger.error(f"Critical error in markdown extraction for {url}: {e}")
            return MarkdownExtractionResult(
                success=False,
                data={},
                method_used="markdown_extractor",
                processing_time=processing_time,
                warnings=[],
                errors=[str(e)],
                should_fallback=True
            )
    
    async def extract_catalog_products(self, catalog_url: str, retailer: str, 
                                      catalog_prompt: str) -> Dict[str, Any]:
        """
        Extract ALL products from a catalog/listing page using markdown extraction
        
        This method is specifically for catalog pages (multi-product listings).
        For single product pages, use extract_product_data() instead.
        
        Args:
            catalog_url: URL of the catalog/listing page
            retailer: Retailer identifier (e.g., 'revolve', 'asos')
            catalog_prompt: Pre-built catalog-specific prompt from catalog_extractor
            
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
            logger.info(f"Starting catalog markdown extraction for {retailer}: {catalog_url}")
            
            # Step 1: Fetch markdown content (reuse existing method)
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
            
            # Step 2: Prepare markdown content with smart chunking
            # If markdown is very large (> 40K chars), extract just the product listing section
            if len(markdown_content) > 40000:
                logger.info(f"Large markdown detected ({len(markdown_content)} chars), extracting product section only")
                # Look for product listing markers (common patterns)
                product_markers = ['product-card', 'ProductCard', 'product-item', 'data-product', 'class="product']
                
                # Find first occurrence of product marker
                start_idx = -1
                for marker in product_markers:
                    idx = markdown_content.find(marker)
                    if idx != -1 and (start_idx == -1 or idx < start_idx):
                        start_idx = idx
                
                if start_idx > 0:
                    # Start from marker, go back a bit for context
                    start_idx = max(0, start_idx - 500)
                    markdown_chunk = markdown_content[start_idx:start_idx + 40000]
                    logger.info(f"Extracted product section: {len(markdown_chunk)} chars")
                else:
                    # No marker found, just take first 40K
                    markdown_chunk = markdown_content[:40000]
            else:
                markdown_chunk = markdown_content[:50000]
            
            # Step 3: Add markdown content to the catalog prompt
            full_prompt = f"""{catalog_prompt}

MARKDOWN CONTENT TO ANALYZE:
{markdown_chunk}

Remember: Extract ALL products as a JSON array in the format specified above."""
            
            # Step 3: Try DeepSeek V3 first
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
                                {"role": "system", "content": "You are a specialized AI designed to extract structured product information from catalog pages. Extract ALL products visible and return them as a JSON array."},
                                {"role": "user", "content": full_prompt}
                            ],
                            temperature=0.1,
                            max_tokens=8000  # Increased for large catalog arrays with 50+ products
                        )
                    )
                    
                    if response and response.choices:
                        content = response.choices[0].message.content
                        extraction_result = self._parse_json_response(content)
                        method_used = 'deepseek_v3'
                        logger.info(f"✅ DeepSeek V3 catalog extraction successful")
                        
                except Exception as e:
                    logger.warning(f"DeepSeek V3 catalog extraction failed: {e}")
            
            # Step 4: Fallback to Gemini Flash 2.0 if needed
            if not extraction_result:
                try:
                    logger.debug(f"Attempting catalog extraction with Gemini Flash 2.0")
                    response = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: self.gemini_client.invoke(full_prompt)
                    )
                    
                    if response and hasattr(response, 'content'):
                        extraction_result = self._parse_json_response(response.content)
                        method_used = 'gemini_flash_2.0'
                        logger.info(f"✅ Gemini Flash 2.0 catalog extraction successful")
                        
                except Exception as e:
                    logger.warning(f"Gemini Flash 2.0 catalog extraction failed: {e}")
            
            # Step 5: Process results
            processing_time = time.time() - start_time
            
            if not extraction_result:
                return {
                    'success': False,
                    'products': [],
                    'total_found': 0,
                    'method_used': 'all_llms_failed',
                    'processing_time': processing_time,
                    'warnings': [],
                    'errors': ['Both DeepSeek V3 and Gemini Flash 2.0 failed to extract catalog']
                }
            
            # Step 6: Extract products array from result
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
                logger.info(f"Large cached content detected ({token_estimate} tokens), clearing cache for {url}")
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
                
                # Browser-like headers with retailer-specific handling
                headers = self._get_jina_headers(retailer)
                
                # Anti-detection delay for certain retailers
                if retailer in ["abercrombie", "hm"]:
                    await asyncio.sleep(random.uniform(1.5, 3.0))
                
                # Make request
                jina_url = f"{JINA_ENDPOINT}{clean_url}"
                logger.debug(f"Fetching markdown from Jina AI: {jina_url}")
                
                # Use asyncio-compatible request method
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
                    logger.debug(f"Successfully fetched markdown for {url} ({fresh_token_estimate} tokens)")
                    return fresh_content, clean_url
                else:
                    logger.warning(f"Jina AI returned status {response.status_code} for {url}")
                    
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
        """Get retailer-specific headers for Jina AI requests"""
        
        base_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/markdown, text/html",
            "Referer": "https://www.google.com/",
            "Accept-Language": "en-US,en;q=0.9",
        }
        
        # Retailer-specific header modifications
        if retailer == "abercrombie":
            base_headers.update({
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
            })
        
        return base_headers
    
    async def _extract_product_section(self, markdown_text: str, retailer: str) -> Optional[str]:
        """Extract product section from large markdown using LLM"""
        
        # Special regex handling for H&M
        if retailer == "hm":
            try:
                title_match = re.search(r"# (.*?)\n", markdown_text)
                title = title_match.group(1) if title_match else ""
                
                price_match = re.search(r"(\$\d+\.\d+|\$\d+)", markdown_text)
                price_section = f"Price: {price_match.group(1)}\n\n" if price_match else ""
                
                image_urls = re.findall(r"(https?://lp2\.hm\.com/hmgoepprod\?[^\s\)]+)", markdown_text)
                image_section = "Images:\n" + "\n".join(image_urls[:10]) + "\n\n" if image_urls else ""
                
                extracted_section = f"# {title}\n\n{price_section}{image_section}"
                if len(extracted_section) > 200:
                    return extracted_section
            except Exception as e:
                logger.warning(f"H&M regex extraction failed: {e}")
        
        # Use Gemini for general section extraction
        try:
            prompt = f"""Extract ONLY the section containing the main product information from this markdown:

1. Product title, description, and pricing details
2. Product images (URLs) 
3. Size, color, and variant information
4. Product features, materials, or specifications
5. Stock status and availability
6. Product ID or SKU if available

DO NOT include navigation menus, footers, related products, or unrelated sections.
Focus on the PRIMARY product being viewed.

Markdown Content (first 15000 chars):
{markdown_text[:15000]}"""

            response = self.gemini_client.invoke(prompt)
            
            if response and hasattr(response, 'content'):
                extracted_content = response.content
                if len(extracted_content) > 200:  # Ensure we got meaningful content
                    return extracted_content
                    
        except Exception as e:
            logger.warning(f"Gemini section extraction failed: {e}")
        
        return None
    
    async def _extract_with_llm_cascade(self, markdown_content: str, retailer: str, url: str) -> Optional[Dict[str, Any]]:
        """Extract product data using DeepSeek V3 -> Gemini Flash 2.0 cascade"""
        
        # Step 1: Try DeepSeek V3 first
        if self.deepseek_enabled:
            deepseek_result = await self._extract_with_deepseek(markdown_content, retailer)
            if deepseek_result:
                logger.debug(f"DeepSeek V3 extraction successful for {retailer}")
                return deepseek_result
        
        # Step 2: Fallback to Gemini Flash 2.0
        gemini_result = await self._extract_with_gemini(markdown_content, retailer)
        if gemini_result:
            logger.debug(f"Gemini Flash 2.0 extraction successful for {retailer}")
            return gemini_result
        
        logger.warning(f"Both DeepSeek V3 and Gemini Flash 2.0 failed for {retailer}")
        return None
    
    async def _extract_with_deepseek(self, markdown_content: str, retailer: str) -> Optional[Dict[str, Any]]:
        """Extract using DeepSeek V3"""
        
        try:
            prompt = self._create_extraction_prompt(markdown_content, retailer)
            
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.deepseek_client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": "You are a specialized AI designed to extract structured product information from website markdown content. Extract accurate product details into a JSON format. Follow all guidelines precisely. Be thorough and precise. Only extract information explicitly present in the content."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    max_tokens=2000
                )
            )
            
            if response and response.choices:
                content = response.choices[0].message.content
                return self._parse_json_response(content)
                
        except Exception as e:
            logger.warning(f"DeepSeek V3 extraction failed: {e}")
        
        return None
    
    async def _extract_with_gemini(self, markdown_content: str, retailer: str) -> Optional[Dict[str, Any]]:
        """Extract using Gemini Flash 2.0"""
        
        try:
            prompt = self._create_extraction_prompt(markdown_content, retailer)
            
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.gemini_client.invoke(prompt)
            )
            
            if response and hasattr(response, 'content'):
                return self._parse_json_response(response.content)
                
        except Exception as e:
            logger.warning(f"Gemini Flash 2.0 extraction failed: {e}")
        
        return None
    
    def _create_extraction_prompt(self, markdown_content: str, retailer: str) -> str:
        """Create extraction prompt with retailer-specific instructions"""
        
        retailer_instructions = self._get_retailer_instructions(retailer)
        
        prompt = f"""Extract comprehensive product data from this e-commerce markdown content.

{retailer_instructions}

REQUIRED OUTPUT (JSON format only - no explanations):
{{
    "title": "",
    "brand": "",
    "price": "",
    "original_price": "",  // Previous price if on sale, null if not applicable
    "description": "",
    "stock_status": "",  // "in stock", "low in stock", or "out of stock"
    "sale_status": "",   // "on sale" or "not on sale"
    "clothing_type": "", // e.g., "dress", "top", "bottom", "outerwear"
    "product_code": "",  // Product ID, SKU, or model number
    "image_urls": [],    // Array of high-quality product image URLs (max 5)
    "neckline": "",      // "crew", "v-neck", "scoop", "off-shoulder", "halter", "strapless", "boat", "square", "sweetheart", "mock", "turtleneck", "cowl", "other", "unknown"
    "sleeve_length": "", // "sleeveless", "cap", "short", "3-quarter", "long", "other", "unknown"
    "retailer": "{retailer}"
}}

CRITICAL REQUIREMENTS:
1. VISUAL DETAILS EXTRACTION:
   - Look for neckline descriptions in product title, description, or specifications
   - Look for sleeve length mentions (sleeveless, short sleeve, long sleeve, etc.)
   - Check for style details, fit descriptions, or feature lists
   - Use "unknown" if not mentioned in the text

2. IMAGE PRIORITY - Extract high-quality product images:
   - Look for URLs containing: 'large', 'full', 'original', 'main', 'front', 'zoom'
   - Avoid: 'thumb', 'small', 'preview' in URLs
   - For {retailer}: {self._get_image_guidance(retailer)}

3. PRICING - Be precise:
   - Extract exact price format (e.g., "$29.99")
   - If on sale: current price in "price", original price in "original_price"
   - If not on sale: current price in "price", null in "original_price"

4. VALIDATION - Ensure all fields are populated with meaningful data

Valid necklines: crew, v-neck, scoop, off-shoulder, halter, strapless, boat, square, sweetheart, mock, turtleneck, cowl, other, unknown
Valid sleeve lengths: sleeveless, cap, short, 3-quarter, long, other, unknown

Markdown Content:
{markdown_content}"""

        return prompt
    
    def _get_retailer_instructions(self, retailer: str) -> str:
        """Get retailer-specific extraction instructions"""
        
        instructions = {
            "uniqlo": """FOR UNIQLO:
- Images typically at https://image.uniqlo.com/ domain
- Look for URLs with "/goods/" or "/item/" patterns
- Product codes often in URL structure
- Limited availability = "low in stock"
- Handle collaboration brands (e.g., "Uniqlo x Disney")""",
            
            "mango": """FOR MANGO:
- Handle "US$ XX.XX" price format
- Images from shop.mango.com domain
- Look for high-res patterns like "imwidth=2048"
- Currency variations (USD/EUR)
- Size charts indicate clothing type""",
            
            "revolve": """FOR REVOLVE:
- Look for image URLs with "/n/z/" for high-res (convert from "/n/ct/")
- Designer brand names are important
- Handle "Revolve exclusive" indicators
- Crossed-out prices indicate sales
- Look for detailed product descriptions""",
            
            "asos": """FOR ASOS:
- Images from asos-media.com domain
- Look for "$XXL$" in URLs for high-res
- Multi-brand retailer - extract actual brand name
- Handle size guides for clothing type
- "Limited stock" = "low in stock" """,
            
            "hm": """FOR H&M:
- Images from lp2.hm.com/hmgoepprod domain
- Look for "imwidth=2160" or "width[2000]" parameters
- H&M brand unless otherwise specified
- European sizing references
- "Few items left" = "low in stock"
- Handle "Conscious" collection indicators"""
        }
        
        return instructions.get(retailer, "Extract standard product data focusing on accuracy and completeness.")
    
    def _get_image_guidance(self, retailer: str) -> str:
        """Get retailer-specific image extraction guidance"""
        
        guidance = {
            "uniqlo": "URLs typically contain '/goods/' and end with '.jpg'",
            "mango": "Look for 'imwidth=2048' or high numeric dimensions",
            "revolve": "Convert '/n/ct/' to '/n/z/' for high-res versions",
            "asos": "Look for '$XXL$' markers in URLs",
            "hm": "Look for 'imwidth=2160' or 'width[2000]' parameters"
        }
        
        return guidance.get(retailer, "Focus on largest available image dimensions")
    
    def _parse_json_response(self, content: str) -> Optional[Dict[str, Any]]:
        """Parse JSON from LLM response with robust repair logic"""
        
        try:
            # Look for JSON pattern (object or array)
            json_pattern = r"(\{[\s\S]*\}|\[[\s\S]*\])"
            json_match = re.search(json_pattern, content)
            
            if json_match:
                json_str = json_match.group(1)
                
                # Try parsing first (might already be valid)
                try:
                    data = json.loads(json_str)
                    return data
                except json.JSONDecodeError:
                    pass  # Continue to repair logic
                
                # Apply aggressive JSON repair
                json_str = self._repair_json(json_str)
                
                # Try parsing again after repair
                try:
                    data = json.loads(json_str)
                    logger.info("✅ JSON successfully repaired and parsed")
                    return data
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON parsing failed even after repair: {e}")
                    return None
                
        except Exception as e:
            logger.warning(f"Response parsing error: {e}")
        
        return None
    
    def _repair_json(self, json_str: str) -> str:
        """Aggressively repair common JSON formatting issues from LLMs"""
        
        # 1. Remove trailing commas in objects
        json_str = re.sub(r",\s*}", "}", json_str)
        
        # 2. Remove trailing commas in arrays
        json_str = re.sub(r",\s*\]", "]", json_str)
        
        # 3. Fix missing commas between objects in arrays (common LLM error)
        json_str = re.sub(r'}\s*{', '},{', json_str)
        
        # 4. Fix missing commas between array items
        json_str = re.sub(r'\]\s*\[', '],[', json_str)
        
        # 5. Normalize whitespace
        json_str = json_str.replace("\n", " ").replace("\r", " ")
        json_str = re.sub(r"(\s+)", " ", json_str)
        
        # 6. Fix truncated JSON (missing closing brackets)
        open_braces = json_str.count('{')
        close_braces = json_str.count('}')
        if open_braces > close_braces:
            json_str += '}' * (open_braces - close_braces)
        
        open_brackets = json_str.count('[')
        close_brackets = json_str.count(']')
        if open_brackets > close_brackets:
            json_str += ']' * (open_brackets - close_brackets)
        
        # 7. Fix common quote escaping issues
        json_str = json_str.replace('\\"', '"').replace("\\'", "'")
        
        # 8. Remove any trailing text after final closing bracket
        last_close = max(json_str.rfind('}'), json_str.rfind(']'))
        if last_close > 0:
            json_str = json_str[:last_close + 1]
        
        return json_str
    
    def _validate_extracted_data(self, data: Dict[str, Any], retailer: str, url: str) -> List[str]:
        """Rigorous validation of extracted product data"""
        
        issues = []
        
        # Required fields validation
        required_fields = ["title", "price", "image_urls"]
        for field in required_fields:
            if not data.get(field):
                issues.append(f"Missing required field: {field}")
        
        # Title validation
        title = data.get("title", "")
        if title:
            if len(title) < 5 or len(title) > 200:
                issues.append(f"Title length suspicious: {len(title)} characters")
            if any(phrase in title.lower() for phrase in ["extracted by", "no title", "not found"]):
                issues.append("Title appears to be placeholder text")
        
        # Price validation  
        price = data.get("price", "")
        if price:
            if not re.search(r'[\$£€]?\d+([.,]\d{2})?', str(price)):
                issues.append(f"Invalid price format: '{price}'")
        
        # Image URLs validation
        image_urls = data.get("image_urls", [])
        if not image_urls:
            issues.append("No image URLs found")
        elif len(image_urls) < 2 and retailer != "hm":  # H&M sometimes has limited images
            issues.append(f"Only {len(image_urls)} images found, expected multiple")
        
        # Retailer-specific validation
        if retailer == "revolve" and image_urls:
            if all("/n/ct/" in url for url in image_urls) and not any("/n/z/" in url for url in image_urls):
                issues.append("Only thumbnail URLs found for Revolve, missing high-res")
        
        elif retailer == "asos" and image_urls:
            if not any(("XXL" in url or "wid=1000" in url) for url in image_urls):
                issues.append("No high-res ASOS images found")
        
        elif retailer == "uniqlo":
            if not any("image.uniqlo.com" in url for url in image_urls):
                issues.append("Image URLs don't match Uniqlo CDN pattern")
        
        # Stock status validation
        stock_status = data.get("stock_status", "")
        valid_stock_statuses = ["in stock", "low in stock", "out of stock"]
        if stock_status and stock_status not in valid_stock_statuses:
            issues.append(f"Invalid stock status: '{stock_status}'")
        
        # Sale status validation
        sale_status = data.get("sale_status", "")
        valid_sale_statuses = ["on sale", "not on sale"]
        if sale_status and sale_status not in valid_sale_statuses:
            issues.append(f"Invalid sale status: '{sale_status}'")
        
        # Quality threshold for H&M (sometimes works)
        if retailer == "hm" and len(issues) > 2:
            issues.append("H&M extraction quality below threshold (expected for some products)")
        
        return issues
    
    def _estimate_token_count(self, text: str) -> int:
        """Estimate token count for text"""
        if not text:
            return 0
        words = text.split()
        estimated_tokens = int(len(words) * 1.3)  # Average English word ~1.3 tokens
        return int(estimated_tokens * 1.085)  # Add 8.5% buffer
    
    def _is_too_large(self, markdown_text: str) -> bool:
        """Check if markdown content is too large for processing"""
        if not markdown_text:
            return False
        token_estimate = self._estimate_token_count(markdown_text)
        return token_estimate > TOKEN_LIMIT * 0.8  # 80% of token limit
    
    def _get_markdown_cache(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """Get cached markdown if available and not expired"""
        if not os.path.exists(MARKDOWN_CACHE_FILE):
            return None, None
        
        try:
            with open(MARKDOWN_CACHE_FILE, "rb") as f:
                cache = pickle.load(f)
            
            if url in cache:
                timestamp, markdown, final_url = cache[url]
                # Check if cache is valid (less than CACHE_EXPIRY_DAYS old)
                if datetime.now() - timestamp < timedelta(days=CACHE_EXPIRY_DAYS):
                    return markdown, final_url
        except Exception as e:
            logger.error(f"Error reading markdown cache: {e}")
        
        return None, None
    
    def _save_markdown_cache(self, url: str, markdown: str, final_url: str):
        """Save markdown to cache with timestamp"""
        try:
            cache = {}
            if os.path.exists(MARKDOWN_CACHE_FILE):
                with open(MARKDOWN_CACHE_FILE, "rb") as f:
                    cache = pickle.load(f)
            
            cache[url] = (datetime.now(), markdown, final_url)
            
            # Remove old entries (older than CACHE_EXPIRY_DAYS)
            cutoff = datetime.now() - timedelta(days=CACHE_EXPIRY_DAYS)
            keys_to_remove = [k for k, v in cache.items() if v[0] < cutoff]
            for k in keys_to_remove:
                del cache[k]
            
            with open(MARKDOWN_CACHE_FILE, "wb") as f:
                pickle.dump(cache, f)
        except Exception as e:
            logger.error(f"Error saving markdown cache: {e}")
    
    def _remove_url_from_cache(self, url: str) -> bool:
        """Remove a specific URL from the markdown cache"""
        if not os.path.exists(MARKDOWN_CACHE_FILE):
            return False
        try:
            with open(MARKDOWN_CACHE_FILE, "rb") as f:
                cache = pickle.load(f)
            if url in cache:
                del cache[url]
                with open(MARKDOWN_CACHE_FILE, "wb") as f:
                    pickle.dump(cache, f)
                return True
        except Exception as e:
            logger.error(f"Error removing URL from markdown cache: {e}")
        return False
    
    def is_supported_retailer(self, retailer: str) -> bool:
        """Check if retailer is supported by markdown extractor"""
        return retailer in MARKDOWN_RETAILERS
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get markdown extractor statistics"""
        cache_size = 0
        if os.path.exists(MARKDOWN_CACHE_FILE):
            try:
                with open(MARKDOWN_CACHE_FILE, "rb") as f:
                    cache = pickle.load(f)
                cache_size = len(cache)
            except:
                cache_size = 0
        
        return {
            "supported_retailers": MARKDOWN_RETAILERS,
            "cache_size": cache_size,
            "deepseek_enabled": self.deepseek_enabled,
            "cache_expiry_days": CACHE_EXPIRY_DAYS
        } 