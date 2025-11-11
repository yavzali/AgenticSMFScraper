"""
Catalog Baseline Scanner Workflow
Establishes initial catalog snapshot for change detection using Dual Tower Architecture

Replaces:
- Part of Catalog Crawler/catalog_orchestrator.py (baseline establishment)
- Catalog Crawler/catalog_extractor.py (routing logic)

Keeps:
- In-memory deduplication for baseline
- Baseline metadata tracking
"""

# Add paths for imports
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../Shared"))
sys.path.append(os.path.join(os.path.dirname(__file__), "../Extraction/Markdown"))
sys.path.append(os.path.join(os.path.dirname(__file__), "../Extraction/Patchright"))

import asyncio
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass
import logging

from logger_config import setup_logging
from cost_tracker import cost_tracker
from notification_manager import NotificationManager
from db_manager import DatabaseManager

# Tower imports
from markdown_catalog_extractor import MarkdownCatalogExtractor
from patchright_catalog_extractor import PatchrightCatalogExtractor

logger = setup_logging(__name__)

# Retailer classification
MARKDOWN_RETAILERS = [
    'revolve', 'asos', 'mango', 'hm', 'uniqlo'
]

PATCHRIGHT_RETAILERS = [
    'anthropologie', 'urban_outfitters', 'abercrombie',
    'aritzia', 'nordstrom'
]

# Retailer catalog URL templates (copied from old retailer_crawlers.py)
# These are the EXACT URLs that worked in the old system
CATALOG_URLS = {
    'revolve': {
        'dresses': 'https://www.revolve.com/dresses/br/a8e981/?navsrc=subDresses&sortBy=newest&vnitems=length_and_midi&vnitems=length_and_maxi&vnitems=cut_and_straight&vnitems=cut_and_flared&vnitems=neckline_and_jewel-neck&vnitems=neckline_and_bardot-neck&vnitems=neckline_and_collar&vnitems=neckline_and_v-neck&vnitems=neckline_and_turtleneck&vnitems=sleeve_and_long&vnitems=sleeve_and_3_4&loadVisNav=true&pageNumVisNav=1',
        'tops': 'https://www.revolve.com/tops/br/db773d/?navsrc=left&sortBy=newest&vnitems=length_and_mid&vnitems=length_and_long-top&vnitems=neckline_and_round-neck&vnitems=neckline_and_jewel-neck&vnitems=neckline_and_collar&vnitems=neckline_and_v-neck&vnitems=neckline_and_sweetheart&vnitems=neckline_and_turtleneck&vnitems=neckline_and_cowl-neck&vnitems=sleeve_and_long&vnitems=sleeve_and_3_4&loadVisNav=true&pageNumVisNav=1'
    },
    'asos': {
        'dresses': 'https://www.asos.com/us/women/dresses/cat/?cid=8799&currentpricerange=10-790&sort=freshness',
        'tops': 'https://www.asos.com/us/women/tops/cat/?cid=4169&currentpricerange=10-425&sort=freshness'
    },
    'mango': {
        'dresses': 'https://shop.mango.com/us/women/dresses_c93966903?page=1',
        'tops': 'https://shop.mango.com/us/women/tops_c23915209?page=1'
    },
    'hm': {
        'dresses': 'https://www2.hm.com/en_us/ladies/shop-by-product/dresses.html?sort=newProduct',
        'tops': 'https://www2.hm.com/en_us/ladies/shop-by-product/tops.html?sort=newProduct'
    },
    'uniqlo': {
        'dresses': 'https://www.uniqlo.com/us/en/women/dresses-and-jumpsuits?quickView=false&page=1&sort=ranking_asc',
        'tops': 'https://www.uniqlo.com/us/en/women/tops?quickView=false&page=1&sort=ranking_asc'
    },
    'aritzia': {
        'dresses': 'https://www.aritzia.com/us/en/clothing/dresses?srule=production_ecommerce_aritzia__Aritzia_US__products__en_US__newest',
        'tops': 'https://www.aritzia.com/us/en/clothing/tops?srule=production_ecommerce_aritzia__Aritzia_US__products__en_US__newest'
    },
    'anthropologie': {
        'dresses': 'https://www.anthropologie.com/dresses?order=Descending&sleevelength=Long%20Sleeve%2C3%2F4%20Sleeve%2CShort%20Sleeve&sort=tile.product.newestColorDate',
        'tops': 'https://www.anthropologie.com/tops?sort=tile.product.newestColorDate&order=Descending'
    },
    'abercrombie': {
        'dresses': 'https://www.abercrombie.com/shop/us/womens-dresses-and-jumpsuits?pagefm=navigation-left+nav&rows=90&sort=newest&start=0',
        'tops': 'https://www.abercrombie.com/shop/us/womens-tops--1?rows=90&sort=newest&start=0'
    },
    'urban_outfitters': {
        'dresses': 'https://www.urbanoutfitters.com/womens-dresses?sort=newest',
        'tops': 'https://www.urbanoutfitters.com/womens-tops?sort=newest'
    },
    'nordstrom': {
        'dresses': 'https://www.nordstrom.com/browse/women/clothing/dresses?breadcrumb=Home%2FWomen%2FDresses&origin=topnav&sort=Newest',
        'tops': 'https://www.nordstrom.com/browse/women/clothing/tops?breadcrumb=Home%2FWomen%2FTops&origin=topnav&sort=Newest'
    }
}


@dataclass
class BaselineResult:
    """Result of establishing a baseline"""
    success: bool
    baseline_id: Optional[str]
    retailer: str
    category: str
    modesty_level: str
    products_found: int
    products_stored: int
    duplicates_removed: int
    method_used: str
    processing_time: float
    error: Optional[str] = None


class CatalogBaselineScanner:
    """
    Establishes catalog baselines for change detection using Dual Tower Architecture
    
    Process:
    1. Get catalog URL from config (retailer + category + modesty + sort=newest)
    2. Route to appropriate tower CATALOG extractor
    3. In-memory deduplication (within crawl session)
    4. Store baseline in catalog_products table
    5. Record metadata in catalog_baselines table
    6. Send notification
    
    No Assessment Pipeline: Just cataloging what exists
    No DB Deduplication: Does not check against main products table
    """
    
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.notification_manager = NotificationManager()
        
        # Initialize towers
        self.markdown_tower = None
        self.patchright_tower = None
        
        logger.info("✅ Catalog Baseline Scanner initialized (Dual Tower)")
    
    async def establish_baseline(
        self,
        retailer: str,
        category: str,
        modesty_level: str,
        custom_url: Optional[str] = None,
        max_pages: int = 10
    ) -> BaselineResult:
        """
        Establish baseline for a specific retailer/category/modesty combination
        
        Args:
            retailer: Retailer name (e.g., 'revolve', 'anthropologie')
            category: Product category (e.g., 'dresses', 'tops')
            modesty_level: Modesty level (e.g., 'modest', 'moderately_modest')
            custom_url: Custom catalog URL (optional, overrides default)
            max_pages: Maximum pages to crawl (default 10)
            
        Returns:
            BaselineResult
        """
        start_time = datetime.utcnow()
        
        try:
            # Step 1: Get catalog URL
            if custom_url:
                catalog_url = custom_url
                logger.info(f"Using custom URL: {catalog_url}")
            else:
                catalog_url = self._get_catalog_url(retailer, category)
                if not catalog_url:
                    return BaselineResult(
                        success=False,
                        baseline_id=None,
                        retailer=retailer,
                        category=category,
                        modesty_level=modesty_level,
                        products_found=0,
                        products_stored=0,
                        duplicates_removed=0,
                        method_used='none',
                        processing_time=0,
                        error=f'No catalog URL configured for {retailer}/{category}'
                    )
            
            logger.info(f"📊 Establishing baseline: {retailer}/{category}/{modesty_level}")
            logger.info(f"   URL: {catalog_url}")
            
            # Step 2: Initialize towers
            await self._initialize_towers()
            
            # Step 3: Route to appropriate tower
            if retailer in MARKDOWN_RETAILERS:
                logger.info("🔄 Using Markdown Tower")
                extraction_result = await self.markdown_tower.extract_catalog(
                    catalog_url,
                    retailer,
                    max_pages=max_pages
                )
                method_used = 'markdown'
            elif retailer in PATCHRIGHT_RETAILERS:
                logger.info("🔄 Using Patchright Tower")
                extraction_result = await self.patchright_tower.extract_catalog(
                    catalog_url,
                    retailer,
                    max_pages=max_pages
                )
                method_used = 'patchright'
            else:
                return BaselineResult(
                    success=False,
                    baseline_id=None,
                    retailer=retailer,
                    category=category,
                    modesty_level=modesty_level,
                    products_found=0,
                    products_stored=0,
                    duplicates_removed=0,
                    method_used='none',
                    processing_time=0,
                    error=f'Unknown retailer: {retailer}'
                )
            
            # Handle both dict and object return types
            if isinstance(extraction_result, dict):
                success = extraction_result.get('success', False)
                products = extraction_result.get('products', [])
                errors = extraction_result.get('errors', [])
            else:
                success = extraction_result.success
                products = extraction_result.data.get('products', [])
                errors = extraction_result.errors
            
            if not success:
                return BaselineResult(
                    success=False,
                    baseline_id=None,
                    retailer=retailer,
                    category=category,
                    modesty_level=modesty_level,
                    products_found=0,
                    products_stored=0,
                    duplicates_removed=0,
                    method_used=method_used,
                    processing_time=(datetime.utcnow() - start_time).total_seconds(),
                    error=str(errors)
                )
            logger.info(f"📦 Extracted {len(products)} products from catalog")
            
            # Step 4: In-memory deduplication (within this crawl session)
            unique_products, duplicates_removed = self._deduplicate_in_memory(products)
            logger.info(f"🔍 After deduplication: {len(unique_products)} unique products ({duplicates_removed} duplicates removed)")
            
            # Step 5: Store baseline in database
            baseline_id = await self.db_manager.create_catalog_baseline(
                retailer=retailer,
                category=category,
                modesty_level=modesty_level,
                products=unique_products,
                catalog_url=catalog_url,
                scan_date=start_time
            )
            
            logger.info(f"✅ Baseline stored: {baseline_id}")
            
            # Step 6: Send notification
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            total_cost = cost_tracker.get_session_cost()
            
            await self.notification_manager.send_baseline_summary(
                retailer=retailer,
                category=category,
                modesty_level=modesty_level,
                baseline_id=baseline_id,
                products_count=len(unique_products),
                processing_time=processing_time,
                total_cost=total_cost
            )
            
            return BaselineResult(
                success=True,
                baseline_id=baseline_id,
                retailer=retailer,
                category=category,
                modesty_level=modesty_level,
                products_found=len(products),
                products_stored=len(unique_products),
                duplicates_removed=duplicates_removed,
                method_used=method_used,
                processing_time=processing_time
            )
            
        except Exception as e:
            logger.error(f"Failed to establish baseline: {e}")
            return BaselineResult(
                success=False,
                baseline_id=None,
                retailer=retailer,
                category=category,
                modesty_level=modesty_level,
                products_found=0,
                products_stored=0,
                duplicates_removed=0,
                method_used='error',
                processing_time=(datetime.utcnow() - start_time).total_seconds(),
                error=str(e)
            )
    
    def _deduplicate_in_memory(self, products: List[Dict]) -> tuple[List[Dict], int]:
        """
        Deduplicate products within the same crawl session
        
        Uses multiple strategies:
        1. URL (normalized)
        2. Product code
        3. Title + Price fuzzy match
        
        Returns:
            (unique_products, duplicates_removed_count)
        """
        seen = {}  # identifier -> product
        unique_products = []
        duplicates = 0
        
        for product in products:
            # Try multiple deduplication strategies
            identifiers = []
            
            # Strategy 1: URL
            if product.get('url'):
                normalized_url = self._normalize_url(product['url'])
                identifiers.append(('url', normalized_url))
            
            # Strategy 2: Product code
            if product.get('product_code'):
                identifiers.append(('code', product['product_code']))
            
            # Strategy 3: Title + Price
            if product.get('title') and product.get('price'):
                title_price = f"{product['title'].lower().strip()}:{product['price']}"
                identifiers.append(('title_price', title_price))
            
            # Check if we've seen this product
            is_duplicate = False
            for strategy, identifier in identifiers:
                if identifier in seen:
                    duplicates += 1
                    is_duplicate = True
                    logger.debug(f"Duplicate found ({strategy}): {product.get('title', 'N/A')}")
                    break
            
            if not is_duplicate:
                # Store all identifiers
                for strategy, identifier in identifiers:
                    seen[identifier] = product
                unique_products.append(product)
        
        return unique_products, duplicates
    
    def _normalize_url(self, url: str) -> str:
        """Normalize URL by removing query parameters"""
        from urllib.parse import urlparse
        
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    
    def _get_catalog_url(self, retailer: str, category: str) -> Optional[str]:
        """Get catalog URL from configuration"""
        retailer_lower = retailer.lower()
        category_lower = category.lower()
        
        if retailer_lower in CATALOG_URLS:
            return CATALOG_URLS[retailer_lower].get(category_lower)
        
        return None
    
    async def _initialize_towers(self):
        """Initialize extraction towers"""
        if not self.markdown_tower:
            self.markdown_tower = MarkdownCatalogExtractor()
            logger.debug("Markdown Tower initialized")
        
        if not self.patchright_tower:
            self.patchright_tower = PatchrightCatalogExtractor()
            logger.debug("Patchright Tower initialized")


# CLI entry point
async def main():
    """CLI entry point for Catalog Baseline Scanner"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Establish catalog baseline for change detection')
    parser.add_argument('retailer', help='Retailer name (e.g., revolve, anthropologie)')
    parser.add_argument('category', help='Product category (e.g., dresses, tops)')
    parser.add_argument('modesty_level', help='Modesty level (modest, moderately_modest)')
    parser.add_argument('--url', help='Custom catalog URL (overrides default)')
    parser.add_argument('--max-pages', type=int, default=10, help='Maximum pages to crawl')
    
    args = parser.parse_args()
    
    scanner = CatalogBaselineScanner()
    result = await scanner.establish_baseline(
        retailer=args.retailer,
        category=args.category,
        modesty_level=args.modesty_level,
        custom_url=args.url,
        max_pages=args.max_pages
    )
    
    print(json.dumps({
        'success': result.success,
        'baseline_id': result.baseline_id,
        'products_stored': result.products_stored,
        'duplicates_removed': result.duplicates_removed,
        'method_used': result.method_used,
        'processing_time': result.processing_time,
        'error': result.error
    }, indent=2))


if __name__ == "__main__":
    asyncio.run(main())

