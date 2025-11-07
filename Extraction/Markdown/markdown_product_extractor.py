"""
Markdown Tower - Single Product Extractor
Extract detailed product data from markdown-converted single product pages

Extracted from: Shared/markdown_extractor.py (product logic, lines 124-231, 564-640, 991-1052)
Target: <900 lines
"""

# Add shared path for imports
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../../Shared"))

import asyncio
import json
import re
from typing import Dict, Optional, List, Any
from dotenv import load_dotenv
import logging

from logger_config import setup_logging
from cost_tracker import cost_tracker
from markdown_retailer_logic import MarkdownRetailerLogic
from markdown_catalog_extractor import MarkdownCatalogExtractor

logger = setup_logging(__name__)

# Return type for extraction
class MarkdownExtractionResult:
    """Result object for markdown extraction"""
    def __init__(
        self,
        success: bool,
        data: Dict,
        method_used: str,
        processing_time: float,
        warnings: List[str],
        errors: List[str],
        should_fallback: bool
    ):
        self.success = success
        self.data = data
        self.method_used = method_used
        self.processing_time = processing_time
        self.warnings = warnings
        self.errors = errors
        self.should_fallback = should_fallback


# Supported retailers for markdown extraction
MARKDOWN_RETAILERS = [
    'revolve', 'asos', 'mango', 'hm', 'uniqlo',
    'aritzia', 'anthropologie', 'abercrombie',
    'urban_outfitters', 'nordstrom'
]


class MarkdownProductExtractor:
    """
    Extract single product data from markdown-converted product pages
    
    Process:
    1. Convert product HTML to markdown (via Jina AI)
    2. Optional smart chunking for large pages
    3. LLM extraction with EARLY VALIDATION (DeepSeek V3 → Gemini Flash 2.0)
    4. Parse JSON response
    5. Validate completeness (price, images, title required)
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
            with open(config_path, 'r') as f:
                config = json.load(f)
        
        self.config = config
        self.retailer_logic = MarkdownRetailerLogic(config)
        
        # Reuse catalog extractor for LLM clients and markdown fetching
        self.catalog_extractor = MarkdownCatalogExtractor(config)
        
        logger.info(f"✅ Markdown Product Extractor initialized for: {', '.join(MARKDOWN_RETAILERS)}")
    
    async def extract_product(self, url: str, retailer: str) -> MarkdownExtractionResult:
        """
        Wrapper method for workflow compatibility
        Calls extract_product_data() internally
        """
        return await self.extract_product_data(url, retailer)
    
    async def extract_product_data(self, url: str, retailer: str) -> MarkdownExtractionResult:
        """Main extraction method for single product pages"""
        start_time = asyncio.get_event_loop().time()
        
        # Validate retailer
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
            logger.info(f"🔍 Starting markdown extraction for {retailer}: {url}")
            
            # Step 1: Fetch markdown content (reuse from catalog extractor)
            markdown_content, final_url = await self.catalog_extractor._fetch_markdown(url, retailer)
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
            
            # Step 3: Extract with LLM cascade + EARLY VALIDATION
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
            
            # Step 4: Final validation
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
    
    async def _extract_with_llm_cascade(self, markdown_content: str, retailer: str, url: str) -> Optional[Dict[str, Any]]:
        """
        Extract with LLM cascade + EARLY VALIDATION
        
        Key improvement from v1.0:
        - Validate DeepSeek immediately
        - If incomplete, try Gemini
        - Prevents unnecessary Patchright fallbacks
        """
        
        # Step 1: Try DeepSeek V3 first
        if self.catalog_extractor.deepseek_enabled:
            deepseek_result = await self._extract_with_deepseek(markdown_content, retailer)
            if deepseek_result:
                # EARLY VALIDATION - validate before accepting
                validation_issues = self._validate_extracted_data(deepseek_result, retailer, url)
                if not validation_issues:
                    logger.debug(f"DeepSeek V3 extraction successful for {retailer}")
                    return deepseek_result
                else:
                    logger.debug(f"DeepSeek V3 returned data but validation failed: {', '.join(validation_issues)}")
                    logger.debug(f"Falling back to Gemini Flash 2.0 for {retailer}")
        
        # Step 2: Fallback to Gemini Flash 2.0
        gemini_result = await self._extract_with_gemini(markdown_content, retailer)
        if gemini_result:
            # Validate Gemini result
            validation_issues = self._validate_extracted_data(gemini_result, retailer, url)
            if not validation_issues:
                logger.debug(f"Gemini Flash 2.0 extraction successful for {retailer}")
                return gemini_result
            else:
                logger.debug(f"Gemini Flash 2.0 returned data but validation failed: {', '.join(validation_issues)}")
        
        logger.warning(f"Both DeepSeek V3 and Gemini Flash 2.0 failed for {retailer}")
        return None
    
    async def _extract_with_deepseek(self, markdown_content: str, retailer: str) -> Optional[Dict[str, Any]]:
        """Extract using DeepSeek V3"""
        
        try:
            prompt = self._create_extraction_prompt(markdown_content, retailer)
            
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.catalog_extractor.deepseek_client.chat.completions.create(
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
                lambda: self.catalog_extractor.gemini_client.invoke(prompt)
            )
            
            if response and hasattr(response, 'content'):
                return self._parse_json_response(response.content)
                
        except Exception as e:
            logger.warning(f"Gemini Flash 2.0 extraction failed: {e}")
        
        return None
    
    def _create_extraction_prompt(self, markdown_content: str, retailer: str) -> str:
        """Build LLM extraction prompt (matching old working version)"""
        
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
   - If visual details aren't explicitly mentioned, set to "unknown"

2. PRICE EXTRACTION:
   - Extract numerical price value only
   - Remove currency symbols ($ £ €)
   - If on sale, include both current and original price
   - Set sale_status to "on sale" if original_price exists

3. IMAGE URLS:
   - Extract up to 5 high-quality product images
   - Full URLs only (not relative paths)
   - Primary product images (not thumbnails if possible)

4. PRODUCT CODE:
   - Look for: SKU, product ID, style number, model number
   - Often found in URL, near price, or in product details

5. STOCK STATUS:
   - Default to "in stock" unless explicitly stated otherwise
   - Look for: "out of stock", "sold out", "unavailable"
   - "low in stock" if mentioned

MARKDOWN CONTENT:
{markdown_content}

Return ONLY the JSON object, no additional text or markdown formatting."""
        
        return prompt
    
    def _get_retailer_instructions(self, retailer: str) -> str:
        """Retailer-specific extraction instructions"""
        
        instructions = {
            'revolve': "Revolve products: Extract brand from title if present.",
            'asos': "ASOS products: Price may be in GBP. Product code in URL.",
            'mango': "Mango products: Price may be in EUR. Extract care instructions if available.",
            'hm': "H&M products: Look for 'Conscious' or sustainability info in description.",
            'aritzia': "Aritzia products: Price in CAD. Look for 'Made in' information."
        }
        
        return instructions.get(retailer, "Extract all available product information.")
    
    def _parse_json_response(self, content: str) -> Optional[Dict[str, Any]]:
        """Parse JSON response from LLM"""
        
        try:
            # Remove markdown code blocks if present
            content = content.strip()
            if content.startswith('```'):
                content = re.sub(r'```json\s*\n?', '', content)
                content = re.sub(r'```\s*$', '', content)
            
            # Parse JSON
            data = json.loads(content)
            return data
            
        except json.JSONDecodeError as e:
            logger.debug(f"JSON parse failed: {e}")
            return None
    
    def _validate_extracted_data(self, data: Dict, retailer: str, url: str) -> List[str]:
        """
        Validate extracted product data
        
        Returns:
            List of validation issues (empty if valid)
        """
        issues = []
        
        # Required fields
        if not data.get('title'):
            issues.append("Missing title")
        if not data.get('price'):
            issues.append("Missing price")
        if not data.get('image_urls') or len(data.get('image_urls', [])) == 0:
            issues.append("Missing images")
        
        # Price validation
        try:
            price = float(data.get('price', 0))
            if price <= 0:
                issues.append("Invalid price")
        except (ValueError, TypeError):
            issues.append("Price is not a number")
        
        return issues
    
    def _is_too_large(self, markdown_content: str) -> bool:
        """Check if markdown is too large"""
        token_estimate = len(markdown_content) // 4
        return token_estimate > 15000
    
    async def _extract_product_section(self, markdown_content: str, retailer: str) -> Optional[str]:
        """Extract product section from large markdown"""
        
        # Simple chunking: look for product-related keywords
        keywords = ['product', 'price', 'add to cart', 'buy now', 'description']
        
        # Find first keyword
        start_idx = -1
        for keyword in keywords:
            idx = markdown_content.lower().find(keyword)
            if idx != -1 and (start_idx == -1 or idx < start_idx):
                start_idx = idx
        
        if start_idx > 0:
            # Extract section around keyword (10K chars)
            start_idx = max(0, start_idx - 1000)
            return markdown_content[start_idx:start_idx + 10000]
        
        # Fallback: return first 10K
        return markdown_content[:10000]
    
    def is_supported_retailer(self, retailer: str) -> bool:
        """Check if retailer is supported"""
        return retailer in MARKDOWN_RETAILERS
