"""
Commercial API Catalog Extractor

Extracts product listings from catalog pages using Bright Data + BeautifulSoup
Falls back to LLM if parsing fails, then to Patchright if all else fails
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
from Extraction.CommercialAPI.commercial_config import CommercialAPIConfig
from Extraction.CommercialAPI.commercial_api_client import get_client
from Extraction.CommercialAPI.html_cache_manager import HTMLCacheManager
from Extraction.CommercialAPI.html_parser import HTMLParser
from Extraction.CommercialAPI.llm_fallback_parser import LLMFallbackParser

logger = setup_logging(__name__)

@dataclass
class CatalogExtractionResult:
    """Result of catalog extraction"""
    success: bool
    products: List[Dict]
    method_used: str  # 'beautifulsoup', 'llm', 'patchright', or 'failed'
    processing_time: float
    error: Optional[str] = None
    brightdata_cost: float = 0.0
    llm_cost: float = 0.0
    cache_hit: bool = False

class CommercialCatalogExtractor:
    """
    Catalog extractor using Commercial API tower (Bright Data + BeautifulSoup)
    
    Process:
    1. Check HTML cache (1-day)
    2. If not cached, fetch HTML via Bright Data
    3. Parse with BeautifulSoup + CSS selectors
    4. If parsing fails, fall back to LLM
    5. If LLM fails, fall back to Patchright (if enabled)
    6. Cache HTML for debugging
    7. Return extracted products
    
    Usage:
        extractor = CommercialCatalogExtractor()
        await extractor.initialize()
        result = await extractor.extract_catalog(url, 'nordstrom', 'dresses')
        await extractor.cleanup()
    """
    
    def __init__(self):
        self.config = CommercialAPIConfig()
        
        # Initialize components
        self.api_client = None
        self.html_cache = None
        self.html_parser = None
        self.llm_parser = None
        
        logger.info("✅ Commercial Catalog Extractor initialized")
    
    async def initialize(self):
        """Initialize all components"""
        try:
            # Initialize Bright Data client
            self.api_client = get_client(self.config)
            
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
            
            logger.info("✅ Commercial Catalog Extractor ready")
        
        except Exception as e:
            logger.error(f"❌ Failed to initialize catalog extractor: {e}")
            raise
    
    async def extract_catalog(
        self,
        url: str,
        retailer: str,
        category: str,
        max_products: int = 100
    ) -> CatalogExtractionResult:
        """
        Extract product listings from catalog page
        
        Args:
            url: Catalog URL
            retailer: Retailer name
            category: Product category (e.g., 'dresses', 'tops')
            max_products: Maximum products to extract
        
        Returns:
            CatalogExtractionResult with products and metadata
        """
        start_time = asyncio.get_event_loop().time()
        
        logger.info("=" * 60)
        logger.info(f"📋 CATALOG EXTRACTION: {retailer} / {category}")
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
                        url, retailer, 'catalog'
                    )
                    
                    # Cache the HTML
                    if self.html_cache and html:
                        await self.html_cache.set(url, retailer, html)
                
                except Exception as e:
                    logger.error(f"❌ Bright Data fetch failed: {e}")
                    
                    # Fall back to Patchright if enabled
                    if self.config.FALLBACK_TO_PATCHRIGHT:
                        return await self._fallback_to_patchright(
                            url, retailer, category, start_time
                        )
                    else:
                        processing_time = asyncio.get_event_loop().time() - start_time
                        return CatalogExtractionResult(
                            success=False,
                            products=[],
                            method_used='failed',
                            processing_time=processing_time,
                            error=str(e)
                        )
            
            # Step 3: Parse HTML with BeautifulSoup
            products, parsing_success = await self.html_parser.parse_catalog(
                html, retailer, url, max_products
            )
            
            if parsing_success and products:
                # Success with BeautifulSoup!
                processing_time = asyncio.get_event_loop().time() - start_time
                
                logger.info(
                    f"✅ CATALOG EXTRACTED: {len(products)} products "
                    f"(method: BeautifulSoup, time: {processing_time:.1f}s)"
                )
                
                return CatalogExtractionResult(
                    success=True,
                    products=products,
                    method_used='beautifulsoup',
                    processing_time=processing_time,
                    brightdata_cost=self.api_client.total_cost if not cache_hit else 0.0,
                    cache_hit=cache_hit
                )
            
            # Step 4: BeautifulSoup failed, try LLM fallback
            logger.warning("⚠️ BeautifulSoup parsing failed, trying LLM fallback...")
            
            if self.llm_parser:
                products = await self.llm_parser.parse_catalog(
                    html, retailer, url, max_products
                )
                
                if products:
                    # Success with LLM!
                    processing_time = asyncio.get_event_loop().time() - start_time
                    
                    logger.info(
                        f"✅ CATALOG EXTRACTED: {len(products)} products "
                        f"(method: LLM fallback, time: {processing_time:.1f}s)"
                    )
                    
                    return CatalogExtractionResult(
                        success=True,
                        products=products,
                        method_used='llm',
                        processing_time=processing_time,
                        brightdata_cost=self.api_client.total_cost if not cache_hit else 0.0,
                        llm_cost=self.llm_parser.total_llm_cost,
                        cache_hit=cache_hit
                    )
            
            # Step 5: Both BeautifulSoup and LLM failed, try Patchright fallback
            if self.config.FALLBACK_TO_PATCHRIGHT:
                logger.warning("⚠️ LLM parsing failed, falling back to Patchright...")
                return await self._fallback_to_patchright(
                    url, retailer, category, start_time
                )
            
            # All methods failed
            processing_time = asyncio.get_event_loop().time() - start_time
            
            logger.error("❌ CATALOG EXTRACTION FAILED: All methods exhausted")
            
            return CatalogExtractionResult(
                success=False,
                products=[],
                method_used='failed',
                processing_time=processing_time,
                error="All extraction methods failed (BeautifulSoup, LLM, Patchright)"
            )
        
        except Exception as e:
            processing_time = asyncio.get_event_loop().time() - start_time
            
            logger.error(f"❌ CATALOG EXTRACTION ERROR: {e}")
            
            return CatalogExtractionResult(
                success=False,
                products=[],
                method_used='failed',
                processing_time=processing_time,
                error=str(e)
            )
    
    async def _fallback_to_patchright(
        self,
        url: str,
        retailer: str,
        category: str,
        start_time: float
    ) -> CatalogExtractionResult:
        """
        Fall back to Patchright tower if Commercial API fails
        
        Args:
            url: Catalog URL
            retailer: Retailer name
            category: Product category
            start_time: Extraction start time
        
        Returns:
            CatalogExtractionResult from Patchright extraction
        """
        try:
            logger.info("🔄 Falling back to Patchright tower...")
            
            # Import Patchright catalog extractor
            from Extraction.Patchright.patchright_catalog_extractor import PatchrightCatalogExtractor
            
            # Use Patchright extractor (no async initialization needed)
            patchright_extractor = PatchrightCatalogExtractor()
            
            # Extract using Patchright
            # Note: Patchright extractor has different interface, adapt as needed
            patchright_result = await patchright_extractor.extract_catalog(
                url, retailer, category
            )
            
            processing_time = asyncio.get_event_loop().time() - start_time
            
            if patchright_result and patchright_result.get('products'):
                logger.info(
                    f"✅ CATALOG EXTRACTED via Patchright fallback: "
                    f"{len(patchright_result['products'])} products"
                )
                
                return CatalogExtractionResult(
                    success=True,
                    products=patchright_result['products'],
                    method_used='patchright',
                    processing_time=processing_time
                )
            else:
                return CatalogExtractionResult(
                    success=False,
                    products=[],
                    method_used='failed',
                    processing_time=processing_time,
                    error="Patchright fallback also failed"
                )
        
        except Exception as e:
            processing_time = asyncio.get_event_loop().time() - start_time
            
            logger.error(f"❌ Patchright fallback error: {e}")
            
            return CatalogExtractionResult(
                success=False,
                products=[],
                method_used='failed',
                processing_time=processing_time,
                error=f"Patchright fallback error: {e}"
            )
    
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
            
            logger.info("✅ Commercial Catalog Extractor cleanup complete")
        
        except Exception as e:
            logger.warning(f"⚠️ Cleanup error: {e}")
