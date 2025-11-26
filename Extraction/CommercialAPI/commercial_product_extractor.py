"""
Commercial API Product Extractor

Extracts full product details using Bright Data + BeautifulSoup
Falls back to LLM if parsing fails, then to Patchright if all else fails
Integrates with image_processor.py for image URL enhancement
"""

import logging
import asyncio
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from Shared.logger_config import setup_logging
from Shared.image_processor import ImageProcessor
from commercial_config import CommercialAPIConfig
from Extraction.CommercialAPI.commercial_api_client import get_client
from html_cache_manager import HTMLCacheManager
from html_parser import HTMLParser
from llm_fallback_parser import LLMFallbackParser

logger = setup_logging(__name__)

@dataclass
class ProductExtractionResult:
    """Result of product extraction"""
    success: bool
    product_data: Optional[Dict]
    method_used: str  # 'beautifulsoup', 'llm', 'patchright', or 'failed'
    processing_time: float
    error: Optional[str] = None
    api_cost: float = 0.0
    llm_cost: float = 0.0
    cache_hit: bool = False
    images_enhanced: bool = False

class CommercialProductExtractor:
    """
    Product extractor using Commercial API tower (Bright Data + BeautifulSoup)
    
    Process:
    1. Check HTML cache (1-day)
    2. If not cached, fetch HTML via Bright Data
    3. Parse with BeautifulSoup + CSS selectors
    4. Enhance image URLs (Anthropologie, Revolve, Aritzia patterns)
    5. If parsing fails, fall back to LLM
    6. If LLM fails, fall back to Patchright (if enabled)
    7. Cache HTML for debugging
    8. Return extracted product data
    
    Usage:
        extractor = CommercialProductExtractor()
        await extractor.initialize()
        result = await extractor.extract_product(url, 'nordstrom')
        await extractor.cleanup()
    """
    
    def __init__(self):
        self.config = CommercialAPIConfig()
        
        # Initialize components
        self.api_client = None
        self.html_cache = None
        self.html_parser = None
        self.llm_parser = None
        self.image_processor = ImageProcessor()
        
        logger.info("✅ Commercial Product Extractor initialized")
    
    async def initialize(self):
        """Initialize all components"""
        try:
            # Initialize Bright Data client
            self.api_client = BrightDataClient()
            
            # Initialize HTML cache
            if self.config.HTML_CACHING_ENABLED:
                self.html_cache = HTMLCacheManager()
                await self.html_cache.initialize()
            
            # Initialize HTML parser
            self.html_parser = HTMLParser()
            
            # Initialize LLM parser (for fallback)
            parsing_strategy = self.config.PARSING_STRATEGY.get('nordstrom', 'beautifulsoup_first')
            if parsing_strategy != 'llm_only':
                self.llm_parser = LLMFallbackParser()
            
            logger.info("✅ Commercial Product Extractor ready")
        
        except Exception as e:
            logger.error(f"❌ Failed to initialize product extractor: {e}")
            raise
    
    async def extract_product(
        self,
        url: str,
        retailer: str,
        category: Optional[str] = None
    ) -> ProductExtractionResult:
        """
        Extract full product details from product page
        
        Args:
            url: Product URL
            retailer: Retailer name
            category: Optional product category (for context)
        
        Returns:
            ProductExtractionResult with product data and metadata
        """
        start_time = asyncio.get_event_loop().time()
        
        logger.info("=" * 60)
        logger.info(f"🛍️ PRODUCT EXTRACTION: {retailer}")
        logger.info(f"🔗 URL: {url}")
        logger.info("=" * 60)
        
        try:
            # Step 1: Try to get HTML from cache
            html = None
            cache_hit = False
            
            if self.html_cache:
                html = await self.html_cache.get(url, retailer)
                if html:
                    cache_hit = True
                    logger.info("💾 Using cached HTML")
            
            # Step 2: If not cached, fetch via Bright Data
            if not html:
                try:
                    html = await self.api_client.fetch_html(
                        url, retailer, 'product'
                    )
                    
                    # Cache the HTML
                    if self.html_cache and html:
                        await self.html_cache.set(url, retailer, html)
                
                except Exception as e:
                    logger.error(f"❌ Bright Data fetch failed: {e}")
                    
                    # Fall back to Patchright if enabled
                    if self.config.FALLBACK_TO_PATCHRIGHT:
                        return await self._fallback_to_patchright(
                            url, retailer, start_time
                        )
                    else:
                        processing_time = asyncio.get_event_loop().time() - start_time
                        return ProductExtractionResult(
                            success=False,
                            product_data=None,
                            method_used='failed',
                            processing_time=processing_time,
                            error=str(e)
                        )
            
            # Step 3: Parse HTML with BeautifulSoup
            product_data, parsing_success = await self.html_parser.parse_product(
                html, retailer, url
            )
            
            if parsing_success and product_data:
                # Success with BeautifulSoup!
                
                # Step 4: Enhance image URLs
                images_enhanced = await self._enhance_images(product_data, retailer)
                
                # Add URL to product data
                product_data['url'] = url
                product_data['catalog_url'] = url
                
                processing_time = asyncio.get_event_loop().time() - start_time
                
                logger.info(
                    f"✅ PRODUCT EXTRACTED: {product_data.get('title', 'Unknown')[:50]}... "
                    f"(method: BeautifulSoup, time: {processing_time:.1f}s)"
                )
                
                return ProductExtractionResult(
                    success=True,
                    product_data=product_data,
                    method_used='beautifulsoup',
                    processing_time=processing_time,
                    api_cost=self.api_client.total_cost if not cache_hit else 0.0,
                    cache_hit=cache_hit,
                    images_enhanced=images_enhanced
                )
            
            # Step 5: BeautifulSoup failed, try LLM fallback
            logger.warning("⚠️ BeautifulSoup parsing failed, trying LLM fallback...")
            
            if self.llm_parser:
                product_data = await self.llm_parser.parse_product(
                    html, retailer, url
                )
                
                if product_data:
                    # Success with LLM!
                    
                    # Enhance image URLs
                    images_enhanced = await self._enhance_images(product_data, retailer)
                    
                    # Add URL
                    product_data['url'] = url
                    product_data['catalog_url'] = url
                    
                    processing_time = asyncio.get_event_loop().time() - start_time
                    
                    logger.info(
                        f"✅ PRODUCT EXTRACTED: {product_data.get('title', 'Unknown')[:50]}... "
                        f"(method: LLM fallback, time: {processing_time:.1f}s)"
                    )
                    
                    return ProductExtractionResult(
                        success=True,
                        product_data=product_data,
                        method_used='llm',
                        processing_time=processing_time,
                        api_cost=self.api_client.total_cost if not cache_hit else 0.0,
                        llm_cost=self.llm_parser.total_llm_cost,
                        cache_hit=cache_hit,
                        images_enhanced=images_enhanced
                    )
            
            # Step 6: Both BeautifulSoup and LLM failed, try Patchright fallback
            if self.config.FALLBACK_TO_PATCHRIGHT:
                logger.warning("⚠️ LLM parsing failed, falling back to Patchright...")
                return await self._fallback_to_patchright(
                    url, retailer, start_time
                )
            
            # All methods failed
            processing_time = asyncio.get_event_loop().time() - start_time
            
            logger.error("❌ PRODUCT EXTRACTION FAILED: All methods exhausted")
            
            return ProductExtractionResult(
                success=False,
                product_data=None,
                method_used='failed',
                processing_time=processing_time,
                error="All extraction methods failed (BeautifulSoup, LLM, Patchright)"
            )
        
        except Exception as e:
            processing_time = asyncio.get_event_loop().time() - start_time
            
            logger.error(f"❌ PRODUCT EXTRACTION ERROR: {e}")
            
            return ProductExtractionResult(
                success=False,
                product_data=None,
                method_used='failed',
                processing_time=processing_time,
                error=str(e)
            )
    
    async def _enhance_images(
        self,
        product_data: Dict,
        retailer: str
    ) -> bool:
        """
        Enhance image URLs using ImageProcessor
        
        Applies retailer-specific image URL transformations:
        - Anthropologie: _330_430 → _1094_1405
        - Revolve: Detect and fix thumbnail patterns
        - Aritzia: _small → _large
        
        Args:
            product_data: Product data with 'image_urls' field
            retailer: Retailer name
        
        Returns:
            True if images were enhanced, False otherwise
        """
        try:
            image_urls = product_data.get('image_urls', [])
            
            if not image_urls:
                return False
            
            # Enhance URLs
            enhanced_urls = []
            for url in image_urls:
                enhanced_url = self.image_processor.enhance_image_url(url, retailer)
                enhanced_urls.append(enhanced_url)
            
            # Update product data
            product_data['image_urls'] = enhanced_urls
            
            # Also store as 'images' for compatibility
            product_data['images'] = enhanced_urls
            
            # Check if any URLs were actually enhanced
            enhanced_count = sum(
                1 for orig, enh in zip(image_urls, enhanced_urls)
                if orig != enh
            )
            
            if enhanced_count > 0:
                logger.info(
                    f"🖼️ Enhanced {enhanced_count}/{len(image_urls)} image URLs"
                )
                return True
            
            return False
        
        except Exception as e:
            logger.warning(f"⚠️ Image enhancement failed: {e}")
            return False
    
    async def _fallback_to_patchright(
        self,
        url: str,
        retailer: str,
        start_time: float
    ) -> ProductExtractionResult:
        """
        Fall back to Patchright tower if Commercial API fails
        
        Args:
            url: Product URL
            retailer: Retailer name
            start_time: Extraction start time
        
        Returns:
            ProductExtractionResult from Patchright extraction
        """
        try:
            logger.info("🔄 Falling back to Patchright tower...")
            
            # Import Patchright product extractor
            from Extraction.Patchright.patchright_product_extractor import PatchrightProductExtractor
            
            # Initialize and use Patchright extractor
            patchright_extractor = PatchrightProductExtractor()
            await patchright_extractor.initialize()
            
            # Extract using Patchright
            # Note: Patchright extractor has different interface, adapt as needed
            patchright_result = await patchright_extractor.extract_product(
                url, retailer
            )
            
            await patchright_extractor.cleanup()
            
            processing_time = asyncio.get_event_loop().time() - start_time
            
            if patchright_result and patchright_result.get('success'):
                product_data = patchright_result.get('product_data')
                
                logger.info(
                    f"✅ PRODUCT EXTRACTED via Patchright fallback: "
                    f"{product_data.get('title', 'Unknown')[:50]}..."
                )
                
                return ProductExtractionResult(
                    success=True,
                    product_data=product_data,
                    method_used='patchright',
                    processing_time=processing_time
                )
            else:
                return ProductExtractionResult(
                    success=False,
                    product_data=None,
                    method_used='failed',
                    processing_time=processing_time,
                    error="Patchright fallback also failed"
                )
        
        except Exception as e:
            processing_time = asyncio.get_event_loop().time() - start_time
            
            logger.error(f"❌ Patchright fallback error: {e}")
            
            return ProductExtractionResult(
                success=False,
                product_data=None,
                method_used='failed',
                processing_time=processing_time,
                error=f"Patchright fallback error: {e}"
            )
    
    def _validate_product_data(self, product_data: Dict) -> bool:
        """
        Validate extracted product data meets requirements
        
        Args:
            product_data: Extracted product data
        
        Returns:
            True if valid, False otherwise
        """
        required_fields = self.config.REQUIRED_PRODUCT_FIELDS
        
        for field, is_required in required_fields.items():
            if is_required:
                value = product_data.get(field)
                if not value:
                    logger.warning(f"⚠️ Missing required field: {field}")
                    return False
        
        # Check minimum image count
        image_urls = product_data.get('image_urls', [])
        if len(image_urls) < self.config.MIN_PRODUCT_IMAGES:
            logger.warning(
                f"⚠️ Insufficient images: {len(image_urls)} "
                f"(minimum: {self.config.MIN_PRODUCT_IMAGES})"
            )
            return False
        
        return True
    
    async def extract_batch(
        self,
        urls: List[str],
        retailer: str,
        category: Optional[str] = None,
        max_concurrent: int = 3
    ) -> List[ProductExtractionResult]:
        """
        Extract multiple products concurrently
        
        Args:
            urls: List of product URLs
            retailer: Retailer name
            category: Optional product category
            max_concurrent: Maximum concurrent extractions
        
        Returns:
            List of ProductExtractionResults
        """
        logger.info(f"🔄 Batch extraction: {len(urls)} products ({retailer})")
        
        results = []
        
        # Process in batches to avoid overwhelming APIs
        for i in range(0, len(urls), max_concurrent):
            batch = urls[i:i + max_concurrent]
            
            # Extract batch concurrently
            tasks = [
                self.extract_product(url, retailer, category)
                for url in batch
            ]
            
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Handle exceptions
            for url, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    logger.error(f"❌ Batch extraction error for {url}: {result}")
                    results.append(ProductExtractionResult(
                        success=False,
                        product_data=None,
                        method_used='failed',
                        processing_time=0.0,
                        error=str(result)
                    ))
                else:
                    results.append(result)
            
            # Log progress
            logger.info(
                f"📊 Batch progress: {min(i + max_concurrent, len(urls))}/{len(urls)} "
                f"products extracted"
            )
        
        # Log summary
        successful = sum(1 for r in results if r.success)
        logger.info(
            f"✅ Batch extraction complete: "
            f"{successful}/{len(urls)} successful "
            f"({successful/len(urls)*100:.1f}%)"
        )
        
        return results
    
    async def cleanup(self):
        """Clean up resources and log statistics"""
        try:
            # Close Bright Data client
            if self.api_client:
                await self.api_client.close()
            
            # Log HTML cache stats
            if self.html_cache:
                await self.html_cache.log_stats()
            
            # Log LLM stats
            if self.llm_parser:
                self.llm_parser.log_llm_stats()
            
            # Log pattern learning stats
            if self.html_parser and self.html_parser.pattern_learner:
                await self.html_parser.pattern_learner.log_pattern_stats()
            
            logger.info("✅ Commercial Product Extractor cleanup complete")
        
        except Exception as e:
            logger.warning(f"⚠️ Cleanup error: {e}")
