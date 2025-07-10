"""
Retailer-Specific Catalog Crawlers
Implements concrete crawlers for each retailer with their specific pagination patterns
"""

import asyncio
from typing import Optional, List, Dict
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse

from catalog_crawler_base import BaseCatalogCrawler, CrawlConfig
from logger_config import setup_logging

logger = setup_logging(__name__)

# =================== PAGINATION CRAWLERS ===================

class RevolveCrawler(BaseCatalogCrawler):
    """
    Revolve Crawler - Pagination with 500 items per page
    Sort by newest available, markdown-compatible
    """
    
    async def _get_page_url(self, base_url: str, page_number: int) -> str:
        """Revolve uses simple page parameter"""
        return self._add_page_to_url(base_url, page_number, 'page')
    
    async def _handle_special_pagination(self, current_url: str) -> Optional[str]:
        """Revolve uses standard pagination - no special handling needed"""
        return None

class AnthropologieCrawler(BaseCatalogCrawler):
    """
    Anthropologie Crawler - Pagination with smaller pages
    Sort by newest available, requires Playwright (press & hold verification)
    """
    
    async def _get_page_url(self, base_url: str, page_number: int) -> str:
        """Anthropologie uses page parameter"""
        return self._add_page_to_url(base_url, page_number, 'page')
    
    async def _handle_special_pagination(self, current_url: str) -> Optional[str]:
        """Anthropologie has smaller pagination arrows - standard handling"""
        return None

class AbercrombeCrawler(BaseCatalogCrawler):
    """
    Abercrombie Crawler - Offset-based pagination
    Sort by newest available, requires Playwright
    """
    
    async def _get_page_url(self, base_url: str, page_number: int) -> str:
        """Abercrombie uses offset-based pagination with 'start' parameter"""
        # Assuming 90 items per page based on the provided URL pattern
        offset = (page_number - 1) * 90
        return self._add_offset_to_url(base_url, offset, 90)
    
    async def _handle_special_pagination(self, current_url: str) -> Optional[str]:
        """Abercrombie uses offset pagination - no special handling needed"""
        return None

class NordstromCrawler(BaseCatalogCrawler):
    """
    Nordstrom Crawler - Pagination with advanced anti-bot
    Sort by newest available, requires Playwright
    """
    
    async def _get_page_url(self, base_url: str, page_number: int) -> str:
        """Nordstrom uses page parameter"""
        return self._add_page_to_url(base_url, page_number, 'page')
    
    async def _handle_special_pagination(self, current_url: str) -> Optional[str]:
        """Nordstrom has advanced anti-bot - may need special handling"""
        return None

class UrbanOutfittersCrawler(BaseCatalogCrawler):
    """
    Urban Outfitters Crawler - Pagination
    Sort by newest available, requires Playwright (press & hold verification)
    """
    
    async def _get_page_url(self, base_url: str, page_number: int) -> str:
        """Urban Outfitters uses page parameter"""
        return self._add_page_to_url(base_url, page_number, 'page')
    
    async def _handle_special_pagination(self, current_url: str) -> Optional[str]:
        """Urban Outfitters uses standard pagination"""
        return None

class HMCrawler(BaseCatalogCrawler):
    """
    H&M Crawler - Hybrid pagination + Load More button
    Sort by newest available, markdown-compatible
    """
    
    async def _get_page_url(self, base_url: str, page_number: int) -> str:
        """H&M uses page parameter"""
        return self._add_page_to_url(base_url, page_number, 'page')
    
    async def _handle_special_pagination(self, current_url: str) -> Optional[str]:
        """
        H&M has both pagination and Load More button
        The Load More button essentially goes to the next page
        """
        # For H&M, we can use standard pagination logic
        # The "Load More" functionality is handled by the base crawler
        return None

# =================== INFINITE SCROLL CRAWLERS ===================

class AritziaCrawler(BaseCatalogCrawler):
    """
    Aritzia Crawler - Infinite scroll
    Sort by newest available, requires Playwright (Cloudflare verification)
    """
    
    async def _get_page_url(self, base_url: str, page_number: int) -> str:
        """
        Aritzia uses infinite scroll, but we can simulate with page parameter
        for initial testing. In full implementation, this would handle scroll positions
        """
        return self._add_page_to_url(base_url, page_number, 'page')
    
    async def _handle_special_pagination(self, current_url: str) -> Optional[str]:
        """
        Aritzia infinite scroll would require Playwright scrolling
        For now, return None to indicate no more "pages"
        """
        return None

class UniqlovCrawler(BaseCatalogCrawler):
    """
    Uniqlo Crawler - Infinite scroll
    Sort by newest available (sort=1), markdown-compatible
    """
    
    async def _get_page_url(self, base_url: str, page_number: int) -> str:
        """
        Uniqlo uses infinite scroll - in full implementation,
        this would handle scroll positions or AJAX endpoints
        """
        # For initial implementation, extract all visible products at once
        return base_url
    
    async def _handle_special_pagination(self, current_url: str) -> Optional[str]:
        """Uniqlo infinite scroll - would need AJAX endpoint discovery"""
        return None

class MangoCrawler(BaseCatalogCrawler):
    """
    Mango Crawler - Infinite scroll, NO sort by newest
    Requires full catalog crawl, requires Playwright
    """
    
    async def _get_page_url(self, base_url: str, page_number: int) -> str:
        """
        Mango uses infinite scroll without sort by newest
        This is the most complex case requiring full catalog pattern learning
        """
        return base_url
    
    async def _handle_special_pagination(self, current_url: str) -> Optional[str]:
        """
        Mango requires special handling since there's no "sort by newest"
        Need to crawl the entire catalog and use pattern learning
        """
        return None
    
    async def crawl_catalog(self, run_id: str, crawl_type: str = 'monitoring'):
        """
        Override crawl_catalog for Mango's special case
        Since Mango has no "sort by newest", we need different logic
        """
        logger.info(f"🕷️ Starting Mango special crawl (no sort by newest): {crawl_type}")
        
        if crawl_type == 'monitoring' and not self.config.has_sort_by_newest:
            # For Mango monitoring, we need to:
            # 1. Crawl multiple "screens" of products
            # 2. Use higher early-stop threshold since we can't sort by newest
            # 3. Use pattern learning to identify where new products typically appear
            
            original_threshold = self.config.early_stop_threshold
            self.config.early_stop_threshold = 8  # Higher threshold for unsorted catalogs
            
            try:
                result = await super().crawl_catalog(run_id, crawl_type)
                return result
            finally:
                self.config.early_stop_threshold = original_threshold
        else:
            # For baseline establishment, crawl normally
            return await super().crawl_catalog(run_id, crawl_type)

# =================== SPECIAL CASE CRAWLERS ===================

class ASOSCrawler(BaseCatalogCrawler):
    """
    ASOS Crawler - Infinite scroll + mandatory "Load More" button clicks
    Sort by newest available (sort=freshness), markdown-compatible
    """
    
    async def _get_page_url(self, base_url: str, page_number: int) -> str:
        """
        ASOS uses infinite scroll with Load More buttons
        Each "page" represents a Load More click
        """
        # For ASOS, the base URL loads the first batch
        # Additional content requires "Load More" clicks
        return base_url
    
    async def _handle_special_pagination(self, current_url: str) -> Optional[str]:
        """
        ASOS requires clicking "Load More" buttons to get additional content
        This would need Playwright automation in full implementation
        """
        # In full implementation, this would:
        # 1. Use Playwright to click "Load More" button
        # 2. Wait for new content to load
        # 3. Return updated page state
        
        # For initial implementation, assume single extraction gets initial products
        return None
    
    async def _crawl_infinite_scroll_catalog(self, run_id: str, crawl_type: str, baseline):
        """
        Override infinite scroll handling for ASOS's Load More pattern
        """
        logger.info(f"🔄 ASOS special crawl: infinite scroll + Load More buttons")
        
        # For now, use standard infinite scroll logic
        # In full implementation, this would handle multiple Load More clicks
        return await super()._crawl_infinite_scroll_catalog(run_id, crawl_type, baseline)

# =================== CRAWLER FACTORY ===================

class CatalogCrawlerFactory:
    """
    Factory for creating retailer-specific catalog crawlers
    Similar pattern to ImageProcessorFactory
    """
    
    # Crawler class mapping
    CRAWLER_CLASSES = {
        'revolve': RevolveCrawler,
        'asos': ASOSCrawler,
        'mango': MangoCrawler,
        'aritzia': AritziaCrawler,
        'anthropologie': AnthropologieCrawler,
        'abercrombie': AbercrombeCrawler,
        'nordstrom': NordstromCrawler,
        'uniqlo': UniqlovCrawler,
        'urban_outfitters': UrbanOutfittersCrawler,
        'hm': HMCrawler
    }
    
    # Retailer configuration data from your provided attachment
    RETAILER_CONFIGS = {
        'revolve': {
            'dresses_url': 'https://www.revolve.com/dresses/br/a8e981/?navsrc=subDresses',
            'tops_url': 'https://www.revolve.com/tops/br/db773d/?navsrc=left',
            'sort_dresses_url': 'https://www.revolve.com/dresses/br/a8e981/?navsrc=subDresses&sortBy=newest',
            'sort_tops_url': 'https://www.revolve.com/tops/br/db773d/?navsrc=left&sortBy=newest',
            'pagination_type': 'pagination',
            'has_sort_by_newest': True,
            'items_per_page': 500,
            'extraction_method': 'markdown'
        },
        'asos': {
            'dresses_url': 'https://www.asos.com/us/women/dresses/cat/?cid=8799',
            'tops_url': 'https://www.asos.com/us/women/tops/cat/?cid=4169',
            'sort_dresses_url': 'https://www.asos.com/us/women/dresses/cat/?cid=8799&currentpricerange=10-790&sort=freshness',
            'sort_tops_url': 'https://www.asos.com/us/women/tops/cat/?cid=4169&currentpricerange=5-300&sort=freshness',
            'pagination_type': 'infinite_scroll',
            'has_sort_by_newest': True,
            'special_notes': 'infinite_scroll_with_load_more_button',
            'extraction_method': 'markdown'
        },
        'mango': {
            'dresses_url': 'https://shop.mango.com/us/en/c/women/dresses-and-jumpsuits/dresses_b4864b2e',
            'tops_url': 'https://shop.mango.com/us/en/c/women/tops_227371cd',
            'sort_dresses_url': None,  # No sort by newest available
            'sort_tops_url': None,
            'pagination_type': 'infinite_scroll',
            'has_sort_by_newest': False,
            'special_notes': 'grid_layout_options_no_sort_by_newest',
            'extraction_method': 'playwright'
        },
        'aritzia': {
            'dresses_url': 'https://www.aritzia.com/us/en/clothing/dresses',
            'tops_url': 'https://www.aritzia.com/us/en/clothing/tops',
            'sort_dresses_url': 'https://www.aritzia.com/us/en/clothing/dresses?srule=production_ecommerce_aritzia__Aritzia_US__products__en_US__newest',
            'sort_tops_url': 'https://www.aritzia.com/us/en/clothing/tops?srule=production_ecommerce_aritzia__Aritzia_US__products__en_US__newest',
            'pagination_type': 'infinite_scroll',
            'has_sort_by_newest': True,
            'special_notes': 'cloudflare_verification',
            'extraction_method': 'playwright'
        },
        'anthropologie': {
            'dresses_url': 'https://www.anthropologie.com/dresses',
            'tops_url': 'https://www.anthropologie.com/tops',
            'sort_dresses_url': 'https://www.anthropologie.com/dresses?sort=tile.product.newestColorDate&order=Descending',
            'sort_tops_url': 'https://www.anthropologie.com/tops?sort=tile.product.newestColorDate&order=Descending',
            'pagination_type': 'pagination',
            'has_sort_by_newest': True,
            'special_notes': 'press_and_hold_verification',
            'extraction_method': 'playwright'
        },
        'abercrombie': {
            'dresses_url': 'https://www.abercrombie.com/shop/us/womens-dresses-and-jumpsuits?pagefm=navigation-left+nav',
            'tops_url': 'https://www.abercrombie.com/shop/us/womens-tops--1',
            'sort_dresses_url': 'https://www.abercrombie.com/shop/us/womens-dresses-and-jumpsuits?pagefm=navigation-left+nav&rows=90&sort=newest&start=0',
            'sort_tops_url': 'https://www.abercrombie.com/shop/us/womens-tops--1?rows=90&sort=newest&start=0',
            'pagination_type': 'pagination',
            'has_sort_by_newest': True,
            'special_notes': 'offset_based_pagination',
            'extraction_method': 'playwright'
        },
        'nordstrom': {
            'dresses_url': 'https://www.nordstrom.com/browse/women/clothing/dresses?breadcrumb=Home%2FWomen%2FDresses&origin=topnav',
            'tops_url': 'https://www.nordstrom.com/browse/women/clothing/tops-tees?breadcrumb=Home%2FWomen%2FClothing%2FTops&origin=topnav',
            'sort_dresses_url': 'https://www.nordstrom.com/browse/women/clothing/dresses?breadcrumb=Home%2FWomen%2FDresses&origin=topnav&sort=Newest&postalCodeAvailability=80246',
            'sort_tops_url': 'https://www.nordstrom.com/browse/women/clothing/tops-tees?breadcrumb=Home%2FWomen%2FClothing%2FTops&origin=topnav&sort=Newest&postalCodeAvailability=80246',
            'pagination_type': 'pagination',
            'has_sort_by_newest': True,
            'special_notes': 'advanced_anti_bot',
            'extraction_method': 'playwright'
        },
        'uniqlo': {
            'dresses_url': 'https://www.uniqlo.com/us/en/women/dresses-and-skirts',
            'tops_url': 'https://www.uniqlo.com/us/en/women/tops',
            'sort_dresses_url': 'https://www.uniqlo.com/us/en/women/dresses-and-skirts?sort=1',
            'sort_tops_url': 'https://www.uniqlo.com/us/en/women/tops?sort=1',
            'pagination_type': 'infinite_scroll',
            'has_sort_by_newest': True,
            'special_notes': 'lightweight_scrolling',
            'extraction_method': 'markdown'
        },
        'urban_outfitters': {
            'dresses_url': 'https://www.urbanoutfitters.com/dresses',
            'tops_url': 'https://www.urbanoutfitters.com/womens-tops',
            'sort_dresses_url': 'https://www.urbanoutfitters.com/dresses?sort=tile.product.newestColorDate&order=Descending',
            'sort_tops_url': 'https://www.urbanoutfitters.com/womens-tops?sort=tile.product.newestColorDate&order=Descending',
            'pagination_type': 'pagination',
            'has_sort_by_newest': True,
            'special_notes': 'press_and_hold_verification',
            'extraction_method': 'playwright'
        },
        'hm': {
            'dresses_url': 'https://www2.hm.com/en_us/women/products/dresses.html',
            'tops_url': 'https://www2.hm.com/en_us/women/products/tops.html',
            'sort_dresses_url': 'https://www2.hm.com/en_us/women/products/dresses.html?sort=newProduct',
            'sort_tops_url': 'https://www2.hm.com/en_us/women/products/tops.html?sort=newProduct',
            'pagination_type': 'hybrid',
            'has_sort_by_newest': True,
            'special_notes': 'pagination_plus_load_more_button',
            'extraction_method': 'markdown'
        }
    }
    
    @classmethod
    def create_crawler(cls, retailer: str, category: str) -> Optional[BaseCatalogCrawler]:
        """
        Create appropriate crawler for retailer and category
        
        Args:
            retailer: Retailer name (e.g., 'revolve', 'asos')
            category: Category ('dresses' or 'tops')
            
        Returns:
            Configured crawler instance or None if not supported
        """
        
        if retailer not in cls.CRAWLER_CLASSES:
            logger.error(f"No crawler available for retailer: {retailer}")
            return None
        
        if retailer not in cls.RETAILER_CONFIGS:
            logger.error(f"No configuration available for retailer: {retailer}")
            return None
        
        # Get retailer configuration
        retailer_config = cls.RETAILER_CONFIGS[retailer]
        
        # Build URLs for the category
        if category == 'dresses':
            base_url = retailer_config['dresses_url']
            sort_url = retailer_config.get('sort_dresses_url', base_url)
        elif category == 'tops':
            base_url = retailer_config['tops_url']
            sort_url = retailer_config.get('sort_tops_url', base_url)
        else:
            logger.error(f"Unsupported category: {category}")
            return None
        
        # Create crawl configuration
        crawl_config = CrawlConfig(
            retailer=retailer,
            category=category,
            base_url=base_url,
            sort_by_newest_url=sort_url or base_url,
            pagination_type=retailer_config['pagination_type'],
            has_sort_by_newest=retailer_config['has_sort_by_newest'],
            early_stop_threshold=3 if retailer_config['has_sort_by_newest'] else 8,
            max_pages=50,
            crawl_strategy='newest_first' if retailer_config['has_sort_by_newest'] else 'full_catalog'
        )
        
        # Create and return crawler instance
        crawler_class = cls.CRAWLER_CLASSES[retailer]
        crawler = crawler_class(crawl_config)
        
        logger.info(f"✅ Created {crawler_class.__name__} for {retailer} {category}")
        return crawler
    
    @classmethod
    def get_supported_retailers(cls) -> List[str]:
        """Get list of all supported retailers"""
        return list(cls.CRAWLER_CLASSES.keys())
    
    @classmethod
    def get_retailer_config(cls, retailer: str) -> Optional[Dict]:
        """Get configuration for specific retailer"""
        return cls.RETAILER_CONFIGS.get(retailer)
    
    @classmethod
    def get_extraction_method(cls, retailer: str) -> str:
        """Get recommended extraction method for retailer"""
        config = cls.RETAILER_CONFIGS.get(retailer, {})
        return config.get('extraction_method', 'playwright')
    
    @classmethod
    def requires_special_handling(cls, retailer: str) -> bool:
        """Check if retailer requires special handling"""
        config = cls.RETAILER_CONFIGS.get(retailer, {})
        special_notes = config.get('special_notes', '')
        
        return any(note in special_notes for note in [
            'cloudflare_verification',
            'press_and_hold_verification', 
            'advanced_anti_bot',
            'load_more_button',
            'no_sort_by_newest'
        ])
    
    @classmethod
    def get_factory_stats(cls) -> Dict:
        """Get statistics about the crawler factory"""
        
        markdown_retailers = [r for r, config in cls.RETAILER_CONFIGS.items() 
                            if config.get('extraction_method') == 'markdown']
        playwright_retailers = [r for r, config in cls.RETAILER_CONFIGS.items() 
                              if config.get('extraction_method') == 'playwright']
        
        pagination_retailers = [r for r, config in cls.RETAILER_CONFIGS.items() 
                              if config.get('pagination_type') == 'pagination']
        infinite_scroll_retailers = [r for r, config in cls.RETAILER_CONFIGS.items() 
                                   if config.get('pagination_type') == 'infinite_scroll']
        hybrid_retailers = [r for r, config in cls.RETAILER_CONFIGS.items() 
                          if config.get('pagination_type') == 'hybrid']
        
        sort_by_newest_retailers = [r for r, config in cls.RETAILER_CONFIGS.items() 
                                  if config.get('has_sort_by_newest')]
        
        return {
            'total_supported_retailers': len(cls.CRAWLER_CLASSES),
            'extraction_methods': {
                'markdown': len(markdown_retailers),
                'playwright': len(playwright_retailers)
            },
            'pagination_types': {
                'pagination': len(pagination_retailers),
                'infinite_scroll': len(infinite_scroll_retailers),
                'hybrid': len(hybrid_retailers)
            },
            'sort_by_newest_support': len(sort_by_newest_retailers),
            'special_handling_required': len([r for r in cls.RETAILER_CONFIGS.keys() 
                                            if cls.requires_special_handling(r)]),
            'markdown_retailers': markdown_retailers,
            'playwright_retailers': playwright_retailers,
            'pagination_retailers': pagination_retailers,
            'infinite_scroll_retailers': infinite_scroll_retailers,
            'sort_supported_retailers': sort_by_newest_retailers
        }