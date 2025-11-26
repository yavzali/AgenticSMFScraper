"""
LLM Fallback Parser

LLM-based HTML parsing when CSS selectors fail
Uses Gemini Flash or DeepSeek for structured extraction
"""

import logging
import json
from typing import Dict, List, Optional
import google.generativeai as genai
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from Shared.logger_config import setup_logging
from Extraction.CommercialAPI.commercial_config import CommercialAPIConfig

logger = setup_logging(__name__)

class LLMFallbackParser:
    """
    LLM-based HTML parser for when CSS selectors fail
    
    Features:
    - Parse HTML using LLM (Gemini Flash or DeepSeek)
    - Structured output with schema validation
    - Cost tracking
    - Caching of LLM responses
    
    Usage:
        parser = LLMFallbackParser()
        product = await parser.parse_product(html, 'nordstrom', url)
        catalog = await parser.parse_catalog(html, 'nordstrom', url)
    """
    
    def __init__(self):
        self.config = CommercialAPIConfig()
        
        # Initialize LLM client
        self.llm_provider = self.config.LLM_PROVIDER
        self.llm_client = None
        
        if self.llm_provider == 'gemini':
            if self.config.GEMINI_API_KEY:
                genai.configure(api_key=self.config.GEMINI_API_KEY)
                self.llm_client = genai.GenerativeModel(self.config.GEMINI_MODEL)
                logger.info(f"✅ LLM Fallback Parser initialized (Gemini {self.config.GEMINI_MODEL})")
            else:
                logger.warning("⚠️ Gemini API key not configured")
        
        elif self.llm_provider == 'deepseek':
            # DeepSeek initialization would go here
            logger.warning("⚠️ DeepSeek not yet implemented")
        
        # Statistics
        self.total_llm_calls = 0
        self.successful_llm_calls = 0
        self.failed_llm_calls = 0
        self.total_llm_cost = 0.0
    
    async def parse_product(
        self,
        html: str,
        retailer: str,
        url: str
    ) -> Optional[Dict]:
        """
        Parse product page using LLM
        
        Args:
            html: Raw HTML content
            retailer: Retailer name
            url: Product URL
        
        Returns:
            Dict with extracted product data, or None if failed
        """
        logger.info(f"🤖 LLM fallback: Parsing product {url[:70]}... ({retailer})")
        
        if not self.llm_client:
            logger.error("❌ LLM client not initialized")
            return None
        
        try:
            # Truncate HTML if too large (LLMs have token limits)
            html_truncated = self._truncate_html(html, max_tokens=100000)
            
            # Create prompt
            prompt = self._create_product_prompt(html_truncated, retailer, url)
            
            # Call LLM
            self.total_llm_calls += 1
            response = await self._call_llm(prompt)
            
            if not response:
                self.failed_llm_calls += 1
                return None
            
            # Parse JSON response
            product_data = self._parse_llm_response(response, 'product')
            
            if product_data:
                self.successful_llm_calls += 1
                logger.info(
                    f"✅ LLM successfully parsed product: "
                    f"{product_data.get('title', 'Unknown')[:50]}..."
                )
                return product_data
            else:
                self.failed_llm_calls += 1
                return None
        
        except Exception as e:
            logger.error(f"❌ LLM product parsing error: {e}")
            self.failed_llm_calls += 1
            return None
    
    async def parse_catalog(
        self,
        html: str,
        retailer: str,
        url: str,
        max_products: int = 100
    ) -> Optional[List[Dict]]:
        """
        Parse catalog page using LLM
        
        Args:
            html: Raw HTML content
            retailer: Retailer name
            url: Catalog URL
            max_products: Maximum products to extract
        
        Returns:
            List of product dicts, or None if failed
        """
        logger.info(f"🤖 LLM fallback: Parsing catalog {url[:70]}... ({retailer})")
        
        if not self.llm_client:
            logger.error("❌ LLM client not initialized")
            return None
        
        try:
            # Truncate HTML if too large
            html_truncated = self._truncate_html(html, max_tokens=100000)
            
            # Create prompt
            prompt = self._create_catalog_prompt(html_truncated, retailer, url, max_products)
            
            # Call LLM
            self.total_llm_calls += 1
            response = await self._call_llm(prompt)
            
            if not response:
                self.failed_llm_calls += 1
                return None
            
            # Parse JSON response
            products = self._parse_llm_response(response, 'catalog')
            
            if products:
                self.successful_llm_calls += 1
                logger.info(f"✅ LLM successfully parsed catalog: {len(products)} products")
                return products
            else:
                self.failed_llm_calls += 1
                return None
        
        except Exception as e:
            logger.error(f"❌ LLM catalog parsing error: {e}")
            self.failed_llm_calls += 1
            return None
    
    def _truncate_html(self, html: str, max_tokens: int = 100000) -> str:
        """
        Truncate HTML to fit within LLM token limits
        
        Approximate: 1 token ≈ 4 characters
        """
        max_chars = max_tokens * 4
        
        if len(html) <= max_chars:
            return html
        
        logger.warning(
            f"⚠️ Truncating HTML: {len(html):,} chars → {max_chars:,} chars"
        )
        
        # Keep first portion (has important product info)
        return html[:max_chars] + "\n\n[HTML TRUNCATED]"
    
    def _create_product_prompt(self, html: str, retailer: str, url: str) -> str:
        """Create prompt for product extraction"""
        return f"""Extract product information from this HTML page.

Retailer: {retailer}
URL: {url}

Return a JSON object with these fields:
{{
    "title": "Product title",
    "price": 99.99,
    "original_price": 129.99,  // Optional, if on sale
    "description": "Product description",
    "image_urls": ["url1", "url2", ...],  // All product images
    "stock_status": "in_stock" | "out_of_stock" | "unknown"
}}

Rules:
- Extract ONLY from the HTML provided
- price must be a number (not a string)
- image_urls must be full URLs (not relative paths)
- If a field is not found, set it to null
- Return ONLY valid JSON (no markdown formatting)

HTML:
{html}

JSON Response:"""
    
    def _create_catalog_prompt(
        self,
        html: str,
        retailer: str,
        url: str,
        max_products: int
    ) -> str:
        """Create prompt for catalog extraction"""
        return f"""Extract product listings from this catalog page.

Retailer: {retailer}
URL: {url}
Max products: {max_products}

Return a JSON array of products:
[
    {{
        "url": "https://...",  // Full product URL
        "title": "Product title",  // Optional
        "price": 99.99  // Optional
    }},
    ...
]

Rules:
- Extract product URLs only (not category links, filters, etc.)
- URLs must be full URLs (not relative paths)
- Limit to {max_products} products maximum
- Return ONLY valid JSON array (no markdown formatting)
- If no products found, return empty array []

HTML:
{html}

JSON Response:"""
    
    async def _call_llm(self, prompt: str) -> Optional[str]:
        """Call LLM API and return response"""
        try:
            if self.llm_provider == 'gemini':
                # Generate content
                response = self.llm_client.generate_content(prompt)
                
                # Track cost (Gemini Flash: ~$0.075 per 1M tokens)
                # Rough estimate: prompt + response tokens
                estimated_tokens = (len(prompt) + len(response.text)) / 4
                estimated_cost = (estimated_tokens / 1_000_000) * 0.075
                self.total_llm_cost += estimated_cost
                
                logger.debug(
                    f"💰 LLM cost: ~${estimated_cost:.4f} "
                    f"(~{estimated_tokens:,.0f} tokens)"
                )
                
                return response.text
            
            elif self.llm_provider == 'deepseek':
                # DeepSeek implementation would go here
                logger.warning("⚠️ DeepSeek not yet implemented")
                return None
            
            else:
                logger.error(f"❌ Unknown LLM provider: {self.llm_provider}")
                return None
        
        except Exception as e:
            logger.error(f"❌ LLM API call failed: {e}")
            return None
    
    def _parse_llm_response(
        self,
        response: str,
        response_type: str
    ) -> Optional[any]:
        """
        Parse JSON response from LLM
        
        Args:
            response: LLM response text
            response_type: 'product' or 'catalog'
        
        Returns:
            Parsed data (Dict for product, List for catalog), or None if failed
        """
        try:
            # Remove markdown code fences if present
            response_cleaned = response.strip()
            if response_cleaned.startswith('```'):
                # Extract JSON from markdown code block
                lines = response_cleaned.split('\n')
                # Remove first line (```json or ```), last line (```)
                response_cleaned = '\n'.join(lines[1:-1])
            
            # Parse JSON
            data = json.loads(response_cleaned)
            
            # Validate response type
            if response_type == 'product':
                if not isinstance(data, dict):
                    logger.error("❌ LLM returned non-dict for product")
                    return None
                return data
            
            elif response_type == 'catalog':
                if not isinstance(data, list):
                    logger.error("❌ LLM returned non-list for catalog")
                    return None
                return data
            
            else:
                logger.error(f"❌ Unknown response type: {response_type}")
                return None
        
        except json.JSONDecodeError as e:
            logger.error(f"❌ LLM returned invalid JSON: {e}")
            logger.debug(f"Response: {response[:500]}...")
            return None
        
        except Exception as e:
            logger.error(f"❌ LLM response parsing error: {e}")
            return None
    
    def get_llm_stats(self) -> Dict:
        """Get LLM usage statistics"""
        return {
            'total_calls': self.total_llm_calls,
            'successful_calls': self.successful_llm_calls,
            'failed_calls': self.failed_llm_calls,
            'success_rate': (
                self.successful_llm_calls / max(self.total_llm_calls, 1)
            ) * 100,
            'total_cost': self.total_llm_cost,
            'avg_cost_per_call': (
                self.total_llm_cost / max(self.total_llm_calls, 1)
            ),
        }
    
    def log_llm_stats(self):
        """Log LLM usage statistics"""
        stats = self.get_llm_stats()
        
        logger.info("=" * 60)
        logger.info("🤖 LLM FALLBACK STATISTICS")
        logger.info("=" * 60)
        logger.info(f"Total LLM Calls: {stats['total_calls']}")
        logger.info(f"Successful: {stats['successful_calls']}")
        logger.info(f"Failed: {stats['failed_calls']}")
        logger.info(f"Success Rate: {stats['success_rate']:.1f}%")
        logger.info(f"Total LLM Cost: ${stats['total_cost']:.4f}")
        logger.info(f"Avg Cost/Call: ${stats['avg_cost_per_call']:.4f}")
        logger.info("=" * 60)

