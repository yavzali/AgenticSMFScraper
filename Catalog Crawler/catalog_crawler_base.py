"""
Base Catalog Crawler - Foundation for all retailer-specific crawlers
Provides common functionality for pagination, infinite scroll, and new product detection
"""

# Add shared path for imports
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../Shared"))
sys.path.append(os.path.dirname(__file__))

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, date
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse

from logger_config import setup_logging
from catalog_extractor import CatalogExtractor, CatalogExtractionResult
from catalog_db_manager import CatalogDatabaseManager, CatalogProduct, MatchResult

logger = setup_logging(__name__)

@dataclass
class CrawlConfig:
    """Configuration for catalog crawling"""
    retailer: str
    category: str
    base_url: str
    sort_by_newest_url: str
    pagination_type: str  # 'pagination', 'infinite_scroll', 'hybrid'
    has_sort_by_newest: bool = True
    early_stop_threshold: int = 5
    max_pages: int = 50
    crawl_strategy: str = 'newest_first'  # 'newest_first', 'full_catalog', 'baseline_establishment'

@dataclass
class CrawlResult:
    """Result of catalog crawling operation"""
    success: bool
    total_products_crawled: int
    new_products_found: int
    existing_products_encountered: int
    pages_crawled: int
    processing_time: float
    early_stopped: bool
    errors: List[str]
    warnings: List[str]
    crawl_metadata: Dict[str, Any]

class BaseCatalogCrawler(ABC):
    """
    Abstract base class for all retailer-specific catalog crawlers
    Provides common pagination/scrolling logic and new product detection
    """
    
    def __init__(self, crawl_config: CrawlConfig):
        self.config = crawl_config
        self.catalog_extractor = CatalogExtractor()
        self.db_manager = CatalogDatabaseManager()
        
        # Tracking variables
        self.consecutive_existing_count = 0
        self.total_products_seen = 0
        self.new_products_found = 0
        
        logger.info(f"✅ {self.config.retailer} catalog crawler initialized")
    
    # =================== MAIN CRAWLING INTERFACE ===================
    
    async def crawl_catalog(self, run_id: str, crawl_type: str = 'monitoring') -> CrawlResult:
        """
        Main crawling interface - handles full catalog crawling workflow
        
        Args:
            run_id: Unique identifier for this crawling run
            crawl_type: 'baseline_establishment', 'monitoring', 'manual_refresh'
        """
        start_time = time.time()
        
        logger.info(f"🕷️ Starting {crawl_type} crawl for {self.config.retailer} {self.config.category}")
        
        try:
            # Reset tracking variables
            self.consecutive_existing_count = 0
            self.total_products_seen = 0
            self.new_products_found = 0
            
            # Get baseline for new product detection (if not baseline establishment)
            baseline = None
            if crawl_type != 'baseline_establishment':
                baseline = await self.db_manager.get_active_baseline(
                    self.config.retailer, self.config.category)
                
                if not baseline:
                    logger.warning(f"No baseline found for {self.config.retailer} {self.config.category} - "
                                 f"treating as baseline establishment")
                    crawl_type = 'baseline_establishment'
            
            # Execute crawling strategy
            if self.config.pagination_type == 'pagination':
                crawl_result = await self._crawl_paginated_catalog(run_id, crawl_type, baseline)
            elif self.config.pagination_type == 'infinite_scroll':
                crawl_result = await self._crawl_infinite_scroll_catalog(run_id, crawl_type, baseline)
            elif self.config.pagination_type == 'hybrid':
                crawl_result = await self._crawl_hybrid_catalog(run_id, crawl_type, baseline)
            else:
                raise ValueError(f"Unknown pagination type: {self.config.pagination_type}")
            
            # Post-crawl processing
            processing_time = time.time() - start_time
            crawl_result.processing_time = processing_time
            
            logger.info(f"✅ {crawl_type} crawl completed: {crawl_result.total_products_crawled} products, "
                       f"{crawl_result.new_products_found} new, {crawl_result.pages_crawled} pages, "
                       f"{processing_time:.1f}s")
            
            return crawl_result
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"❌ Crawl failed for {self.config.retailer} {self.config.category}: {e}")
            
            return CrawlResult(
                success=False,
                total_products_crawled=self.total_products_seen,
                new_products_found=self.new_products_found,
                existing_products_encountered=self.total_products_seen - self.new_products_found,
                pages_crawled=0,
                processing_time=processing_time,
                early_stopped=False,
                errors=[str(e)],
                warnings=[],
                crawl_metadata={'error': str(e)}
            )
    
    # =================== PAGINATION STRATEGIES ===================
    
    async def _crawl_paginated_catalog(self, run_id: str, crawl_type: str, 
                                     baseline: Optional[Dict]) -> CrawlResult:
        """Crawl paginated catalog (Revolve, Anthropologie, Abercrombie, etc.)"""
        
        pages_crawled = 0
        total_products = []
        errors = []
        warnings = []
        early_stopped = False
        
        # Determine starting URL
        start_url = self.config.sort_by_newest_url if (
            self.config.has_sort_by_newest and crawl_type != 'baseline_establishment'
        ) else self.config.base_url
        
        current_page = 1
        
        while current_page <= self.config.max_pages:
            try:
                # Get page URL using retailer-specific logic
                page_url = await self._get_page_url(start_url, current_page)
                
                logger.info(f"📄 Crawling page {current_page}: {page_url}")
                
                # Extract products from this page
                extraction_result = await self.catalog_extractor.extract_catalog_page(
                    page_url, self.config.retailer, self.config.category,
                    {'pagination_type': self.config.pagination_type, 'page_number': current_page}
                )
                
                if not extraction_result.success:
                    errors.extend(extraction_result.errors)
                    warnings.extend(extraction_result.warnings)
                    break
                
                # Process products for new product detection
                page_products = extraction_result.products
                if not page_products:
                    logger.info(f"No products found on page {current_page}, stopping crawl")
                    break
                
                # Convert to CatalogProduct objects
                catalog_products = [self._dict_to_catalog_product(p) for p in page_products]
                
                # Detect new products vs existing
                if crawl_type == 'baseline_establishment':
                    # For baseline, all products are "seen" but not necessarily new
                    total_products.extend(catalog_products)
                    self.total_products_seen += len(catalog_products)
                else:
                    # For monitoring, detect truly new products
                    new_products, early_stop = await self._process_page_for_new_products(
                        catalog_products, run_id)
                    
                    total_products.extend(new_products)
                    
                    if early_stop:
                        logger.info(f"🛑 Early stopping: {self.consecutive_existing_count} consecutive existing products")
                        early_stopped = True
                        break
                
                pages_crawled += 1
                current_page += 1
                
                # Rate limiting between pages
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error crawling page {current_page}: {e}")
                errors.append(f"Page {current_page}: {str(e)}")
                break
        
        # Store results
        if crawl_type == 'baseline_establishment':
            stored_count = await self.db_manager.store_baseline_products(total_products, run_id)
        else:
            stored_count = await self.db_manager.store_new_products(
                [(p, MatchResult(True, 0.95, 'new_product')) for p in total_products], run_id)
        
        return CrawlResult(
            success=len(errors) == 0,
            total_products_crawled=self.total_products_seen,
            new_products_found=len(total_products),
            existing_products_encountered=self.total_products_seen - len(total_products),
            pages_crawled=pages_crawled,
            processing_time=0,  # Will be set by caller
            early_stopped=early_stopped,
            errors=errors,
            warnings=warnings,
            crawl_metadata={
                'stored_products': stored_count,
                'crawl_type': crawl_type,
                'pagination_type': 'pagination'
            }
        )
    
    async def _crawl_infinite_scroll_catalog(self, run_id: str, crawl_type: str,
                                           baseline: Optional[Dict]) -> CrawlResult:
        """Crawl infinite scroll catalog (Uniqlo, Aritzia, Mango)"""
        
        # For infinite scroll, we'll simulate by extracting multiple "scroll positions"
        # The actual scrolling would be handled by Playwright-based crawlers
        
        scroll_iterations = 0
        total_products = []
        errors = []
        warnings = []
        early_stopped = False
        
        # Start with main catalog URL
        start_url = self.config.sort_by_newest_url if (
            self.config.has_sort_by_newest and crawl_type != 'baseline_establishment'
        ) else self.config.base_url
        
        # For infinite scroll, we extract once and rely on the extractor to get all visible products
        # In a full implementation, this would involve actual scrolling with Playwright
        
        try:
            logger.info(f"🔄 Crawling infinite scroll catalog: {start_url}")
            
            extraction_result = await self.catalog_extractor.extract_catalog_page(
                start_url, self.config.retailer, self.config.category,
                {'pagination_type': self.config.pagination_type, 'scroll_iteration': 1}
            )
            
            if not extraction_result.success:
                errors.extend(extraction_result.errors)
                warnings.extend(extraction_result.warnings)
            else:
                page_products = extraction_result.products
                catalog_products = [self._dict_to_catalog_product(p) for p in page_products]
                
                if crawl_type == 'baseline_establishment':
                    total_products.extend(catalog_products)
                    self.total_products_seen += len(catalog_products)
                else:
                    new_products, early_stop = await self._process_page_for_new_products(
                        catalog_products, run_id)
                    total_products.extend(new_products)
                
                scroll_iterations = 1
                
        except Exception as e:
            logger.error(f"Error crawling infinite scroll catalog: {e}")
            errors.append(str(e))
        
        # Store results
        if crawl_type == 'baseline_establishment':
            stored_count = await self.db_manager.store_baseline_products(total_products, run_id)
        else:
            stored_count = await self.db_manager.store_new_products(
                [(p, MatchResult(True, 0.95, 'new_product')) for p in total_products], run_id)
        
        return CrawlResult(
            success=len(errors) == 0,
            total_products_crawled=self.total_products_seen,
            new_products_found=len(total_products),
            existing_products_encountered=self.total_products_seen - len(total_products),
            pages_crawled=scroll_iterations,
            processing_time=0,
            early_stopped=early_stopped,
            errors=errors,
            warnings=warnings,
            crawl_metadata={
                'stored_products': stored_count,
                'crawl_type': crawl_type,
                'pagination_type': 'infinite_scroll'
            }
        )
    
    async def _crawl_hybrid_catalog(self, run_id: str, crawl_type: str,
                                  baseline: Optional[Dict]) -> CrawlResult:
        """Crawl hybrid catalog (H&M - pagination + load more button)"""
        
        # H&M has both pagination and "Load More" - we'll treat it as pagination
        # but with special handling for the Load More functionality
        
        return await self._crawl_paginated_catalog(run_id, crawl_type, baseline)
    
    # =================== NEW PRODUCT DETECTION ===================
    
    async def _process_page_for_new_products(self, catalog_products: List[CatalogProduct], 
                                           run_id: str) -> Tuple[List[CatalogProduct], bool]:
        """
        Process page products for new product detection with early stopping
        Returns (new_products, should_early_stop)
        """
        
        new_products = []
        
        # Detect new vs existing products
        detection_results = await self.db_manager.detect_new_products(
            catalog_products, self.config.retailer, self.config.category)
        
        consecutive_existing = 0
        
        for product, match_result in detection_results:
            self.total_products_seen += 1
            
            if match_result.is_new_product:
                # This is a new product
                new_products.append(product)
                self.new_products_found += 1
                consecutive_existing = 0  # Reset counter
                
                logger.info(f"🆕 NEW PRODUCT: {product.title[:50]}... "
                          f"(confidence: {match_result.confidence_score:.2f})")
            else:
                # This is an existing product
                consecutive_existing += 1
                
                logger.debug(f"⚪ Existing product: {product.title[:50]}... "
                           f"(match: {match_result.match_type})")
        
        # Update consecutive existing counter for early stopping
        if consecutive_existing > 0:
            self.consecutive_existing_count += consecutive_existing
        else:
            self.consecutive_existing_count = 0
        
        # Check for early stopping
        early_stop = (
            self.config.has_sort_by_newest and 
            self.consecutive_existing_count >= self.config.early_stop_threshold
        )
        
        return new_products, early_stop
    
    # =================== UTILITY METHODS ===================
    
    def _dict_to_catalog_product(self, product_dict: Dict) -> CatalogProduct:
        """Convert product dictionary to CatalogProduct object"""
        return CatalogProduct(
            catalog_url=product_dict.get('url', ''),
            retailer=product_dict.get('retailer', self.config.retailer),
            category=product_dict.get('category', self.config.category),
            title=product_dict.get('title'),
            price=product_dict.get('price'),
            original_price=product_dict.get('original_price'),
            sale_status=product_dict.get('sale_status'),
            image_urls=product_dict.get('image_urls'),
            availability=product_dict.get('availability'),
            product_code=product_dict.get('product_code'),
            normalized_url=product_dict.get('normalized_url'),
            discovered_date=product_dict.get('discovered_date', date.today()),
            extraction_method=product_dict.get('extraction_method')
        )
    
    # =================== ABSTRACT METHODS ===================
    
    @abstractmethod
    async def _get_page_url(self, base_url: str, page_number: int) -> str:
        """
        Get URL for specific page number (retailer-specific implementation)
        
        Args:
            base_url: Base catalog URL
            page_number: Page number to retrieve
            
        Returns:
            Complete URL for the specified page
        """
        pass
    
    @abstractmethod
    async def _handle_special_pagination(self, current_url: str) -> Optional[str]:
        """
        Handle special pagination logic (e.g., ASOS "Load More" button)
        
        Args:
            current_url: Current page URL
            
        Returns:
            Next page URL or None if no more pages
        """
        pass
    
    # =================== COMMON URL UTILITIES ===================
    
    def _add_page_to_url(self, url: str, page_number: int, 
                        page_param: str = 'page') -> str:
        """Add page parameter to URL"""
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        query_params[page_param] = [str(page_number)]
        
        new_query = urlencode(query_params, doseq=True)
        return urlunparse((
            parsed.scheme, parsed.netloc, parsed.path,
            parsed.params, new_query, parsed.fragment
        ))
    
    def _add_offset_to_url(self, url: str, offset: int, 
                          items_per_page: int = 50) -> str:
        """Add offset parameter to URL (for offset-based pagination)"""
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        query_params['start'] = [str(offset)]
        
        new_query = urlencode(query_params, doseq=True)
        return urlunparse((
            parsed.scheme, parsed.netloc, parsed.path,
            parsed.params, new_query, parsed.fragment
        ))
    
    async def get_crawler_stats(self) -> Dict:
        """Get crawler statistics and configuration"""
        return {
            'retailer': self.config.retailer,
            'category': self.config.category,
            'pagination_type': self.config.pagination_type,
            'has_sort_by_newest': self.config.has_sort_by_newest,
            'early_stop_threshold': self.config.early_stop_threshold,
            'max_pages': self.config.max_pages,
            'crawl_strategy': self.config.crawl_strategy,
            'total_products_seen': self.total_products_seen,
            'new_products_found': self.new_products_found,
            'consecutive_existing_count': self.consecutive_existing_count
        }