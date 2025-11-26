"""
Catalog Monitor Workflow
Detects new products in retailer catalogs using Dual Tower Architecture

Replaces:
- Part of Catalog Crawler/catalog_orchestrator.py (monitoring workflow)
- Catalog Crawler/change_detector.py (routing logic)
- Catalog Crawler/catalog_extractor.py (routing logic)

Keeps:
- Multi-level deduplication (URL, code, title+price, image)
- Assessment pipeline integration
- Change detection logic
"""

# Add paths for imports
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../Shared"))
sys.path.append(os.path.join(os.path.dirname(__file__), "../Extraction/Markdown"))
sys.path.append(os.path.join(os.path.dirname(__file__), "../Extraction/Patchright"))
sys.path.append(os.path.join(os.path.dirname(__file__), "../Extraction/CommercialAPI"))

import asyncio
import json
import re
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
from urllib.parse import urlparse
from difflib import SequenceMatcher
import logging

from logger_config import setup_logging
from cost_tracker import cost_tracker
from notification_manager import NotificationManager
from db_manager import DatabaseManager
from assessment_queue_manager import AssessmentQueueManager
from database_sync import sync_database_async

# Pattern Learning (optional, non-critical)
try:
    from pattern_learning_manager import get_pattern_learning_manager
    PATTERN_LEARNING_AVAILABLE = True
except ImportError:
    PATTERN_LEARNING_AVAILABLE = False
    logger_temp = logging.getLogger(__name__)
    logger_temp.warning("⚠️ Pattern learning manager not available - will use defaults")

# Tower imports
from markdown_catalog_extractor import MarkdownCatalogExtractor
from markdown_product_extractor import MarkdownProductExtractor
from patchright_catalog_extractor import PatchrightCatalogExtractor
from patchright_product_extractor import PatchrightProductExtractor

# Commercial API Tower (Third Tower - Bright Data)
try:
    from commercial_config import CommercialAPIConfig
    from commercial_catalog_extractor import CommercialCatalogExtractor
    from commercial_product_extractor import CommercialProductExtractor
    COMMERCIAL_API_AVAILABLE = True
except ImportError:
    COMMERCIAL_API_AVAILABLE = False
    logger_temp = logging.getLogger(__name__)
    logger_temp.warning("⚠️ Commercial API tower not available - will use Patchright/Markdown")

logger = setup_logging(__name__)

# Retailer classification for CATALOG scanning
# ALL retailers use Patchright for catalog (JavaScript-loaded product URLs)
PATCHRIGHT_CATALOG_RETAILERS = [
    'revolve', 'asos', 'mango', 'hm', 'uniqlo',
    'anthropologie', 'urban_outfitters', 'abercrombie',
    'aritzia', 'nordstrom'
]

# Retailers that use Markdown for SINGLE PRODUCT extraction
MARKDOWN_SINGLE_PRODUCT_RETAILERS = [
    'revolve', 'asos', 'mango', 'hm', 'uniqlo'
]

# Retailer catalog URL templates (copied from old retailer_crawlers.py - MUST match baseline scanner!)
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
        'dresses': 'https://www.urbanoutfitters.com/dresses?sort=tile.product.newestColorDate&order=Descending&sleeve=Short+Sleeve,Long+Sleeve,3/4+Sleeve',
        'tops': 'https://www.urbanoutfitters.com/tops?sort=tile.product.newestColorDate&order=Descending&sleeve=Short+Sleeve,Long+Sleeve,3/4+Sleeve'
    },
    'nordstrom': {
        'dresses': 'https://www.nordstrom.com/browse/women/clothing/dresses?breadcrumb=Home%2FWomen%2FDresses&origin=topnav&sort=Newest',
        'tops': 'https://www.nordstrom.com/browse/women/clothing/tops?breadcrumb=Home%2FWomen%2FTops&origin=topnav&sort=Newest'
    }
}


@dataclass
class MonitorResult:
    """Result of monitoring a catalog for new products"""
    success: bool
    retailer: str
    category: str
    modesty_level: str
    products_scanned: int
    new_products_found: int
    suspected_duplicates: int
    confirmed_existing: int
    sent_to_modesty_review: int
    sent_to_duplicate_review: int
    processing_time: float
    method_used: str
    error: Optional[str] = None


class CatalogMonitor:
    """
    Monitors retailer catalogs for new products using Dual Tower Architecture
    
    Process:
    0. PREREQUISITE: Product Updater must run first!
    1. Get catalog URL (sorted by newest)
    2. Scan catalog with tower CATALOG extractor
    3. Deduplicate against:
       - catalog_products table (baseline)
       - products table (Shopify-synced items)
       - Use multi-level dedup (URL, code, title+price, image)
    4. For CONFIRMED_NEW products:
       - Re-extract with SINGLE product extractor
       - Send to Assessment Pipeline for MODESTY review
    5. For SUSPECTED_DUPLICATE products:
       - Send to Assessment Pipeline for DUPLICATION review (human confirmation)
    6. Notifications
    
    Deduplication: Most complex - multi-level matching
    Assessment Pipeline Integration: Both modesty and duplication reviews
    """
    
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.notification_manager = NotificationManager()
        self.assessment_queue = AssessmentQueueManager()
        
        # Initialize pattern learning (optional, non-critical)
        self.pattern_learner = None
        if PATTERN_LEARNING_AVAILABLE:
            try:
                self.pattern_learner = get_pattern_learning_manager()
                logger.info("✅ Pattern learning enabled")
            except Exception as e:
                logger.warning(f"⚠️ Pattern learning initialization failed: {e}")
        
        # Initialize towers
        self.markdown_catalog_tower = None
        self.markdown_product_tower = None
        self.patchright_catalog_tower = None
        self.patchright_product_tower = None
        self.commercial_catalog_tower = None
        self.commercial_product_tower = None
        
        # Tower count
        tower_count = "Dual Tower"
        if COMMERCIAL_API_AVAILABLE:
            tower_count = "Triple Tower (Markdown, Patchright, Commercial API)"
        
        logger.info(f"✅ Catalog Monitor initialized ({tower_count})")
    
    async def _save_catalog_snapshot(
        self,
        catalog_products: List[Dict],
        retailer: str,
        category: str,
        modesty_level: str
    ) -> None:
        """
        Save ALL catalog products as historical snapshot
        Called on EVERY monitor run to track catalog changes over time
        
        This creates new entries in catalog_products table with scan_type='monitor'
        to maintain historical log of what was in catalog on each scan date.
        """
        logger.info(f"📸 Saving catalog snapshot: {len(catalog_products)} products")
        
        conn = self.db_manager._get_connection()
        cursor = conn.cursor()
        
        saved = 0
        for product in catalog_products:
            try:
                # Extract fields
                url = product.get('url') or product.get('catalog_url')
                title = product.get('title')
                price = product.get('price')
                product_code = product.get('product_code')
                image_urls = product.get('image_urls') or product.get('images', [])
                
                # Convert image_urls to JSON string if it's a list
                if isinstance(image_urls, list):
                    image_urls = json.dumps(image_urls)
                
                # Insert into catalog_products
                cursor.execute("""
                    INSERT INTO catalog_products 
                    (catalog_url, retailer, category, title, price, product_code, 
                     image_urls, discovered_date, review_status, scan_type, image_url_source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    url,
                    retailer,
                    category,
                    title,
                    price,
                    product_code,
                    image_urls,
                    datetime.utcnow().isoformat(),
                    'baseline',  # All catalog snapshots are marked 'baseline'
                    'monitor',   # This distinguishes from baseline scanner
                    'catalog_extraction'
                ))
                saved += 1
                
            except Exception as e:
                logger.error(f"Failed to save catalog snapshot for {url}: {e}")
                continue
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Catalog snapshot saved: {saved}/{len(catalog_products)} products")
        
        # Learn from linking attempts if pattern learning available
        if self.pattern_learner:
            try:
                # Get linked products from this snapshot
                conn = self.db_manager._get_connection()
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT linked_product_url, link_method, link_confidence, catalog_url
                    FROM catalog_products
                    WHERE retailer = ?
                    AND discovered_date >= datetime('now', '-1 hour')
                    AND linked_product_url IS NOT NULL
                """, (retailer,))
                
                linked_products = cursor.fetchall()
                conn.close()
                
                # Record each linking attempt for learning
                for linked_url, method, confidence, catalog_url in linked_products:
                    # Check if URL changed
                    normalized_catalog = catalog_url.split('?')[0].rstrip('/')
                    normalized_linked = linked_url.split('?')[0].rstrip('/')
                    url_changed = (normalized_catalog != normalized_linked)
                    
                    await self.pattern_learner.record_linking_attempt(
                        retailer=retailer,
                        method=method,
                        success=True,  # It was linked
                        confidence=confidence,
                        url_changed=url_changed
                    )
                
                if linked_products:
                    logger.debug(f"📚 Recorded {len(linked_products)} linking attempts for pattern learning")
                    
            except Exception as e:
                logger.warning(f"⚠️ Pattern learning failed (non-critical): {e}")
    
    async def _detect_price_changes(
        self,
        catalog_products: List[Dict],
        retailer: str
    ) -> int:
        """
        Compare catalog prices to products table
        Flag products where price changed for Product Updater priority queue
        
        Returns:
            Number of price changes detected
        """
        conn = self.db_manager._get_connection()
        cursor = conn.cursor()
        
        price_changes = 0
        
        for product in catalog_products:
            try:
                url = product.get('url') or product.get('catalog_url')
                catalog_price = product.get('price')
                
                if not url or not catalog_price:
                    continue
                
                # Check if product exists in products table
                # Try exact match first, then normalized
                cursor.execute("""
                    SELECT url, price FROM products 
                    WHERE (url = ? OR RTRIM(SUBSTR(url, 1, INSTR(url || '?', '?') - 1), '/') = ?)
                    AND retailer = ?
                """, (url, url.split('?')[0].rstrip('/'), retailer))
                
                result = cursor.fetchone()
                
                if result:
                    product_url, product_price = result
                    
                    # Price changed?
                    if product_price and abs(float(catalog_price) - float(product_price)) >= 0.01:
                        price_diff = float(catalog_price) - float(product_price)
                        
                        # Add to priority queue
                        cursor.execute("""
                            INSERT INTO product_update_queue
                            (product_url, retailer, priority, reason, 
                             catalog_price, products_price, price_difference, detected_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            product_url,
                            retailer,
                            'high' if abs(price_diff) > 50 else 'normal',
                            'price_change_detected_in_catalog',
                            catalog_price,
                            product_price,
                            price_diff,
                            datetime.utcnow().isoformat()
                        ))
                        
                        price_changes += 1
                        logger.debug(f"💰 Price change: {product_url[:50]}... ${product_price} → ${catalog_price}")
            
            except Exception as e:
                logger.error(f"Price change detection failed: {e}")
                continue
        
        conn.commit()
        conn.close()
        
        if price_changes > 0:
            logger.info(f"💰 Detected {price_changes} price changes")
        
        return price_changes
    
    async def _link_to_products_table(
        self,
        catalog_product: Dict,
        retailer: str
    ) -> Optional[Dict]:
        """
        Try to link catalog product to products table using multi-level deduplication
        
        Returns:
            dict with linked_product_url, link_confidence, link_method or None
        """
        conn = self.db_manager._get_connection()
        cursor = conn.cursor()
        
        url = catalog_product.get('url') or catalog_product.get('catalog_url')
        title = catalog_product.get('title')
        price = catalog_product.get('price')
        product_code = catalog_product.get('product_code')
        
        # Check retailer URL stability to decide strategy
        cursor.execute("""
            SELECT best_dedup_method, url_stability_score 
            FROM retailer_url_patterns 
            WHERE retailer = ?
        """, (retailer,))
        
        pattern_result = cursor.fetchone()
        
        # If retailer has low URL stability, prefer fuzzy matching
        prefer_fuzzy = False
        if pattern_result:
            best_method, stability = pattern_result
            prefer_fuzzy = (stability < 0.50 or best_method == 'fuzzy_title_price')
        
        # Level 1: Exact URL (unless we prefer fuzzy)
        if not prefer_fuzzy:
            cursor.execute("SELECT url FROM products WHERE url = ? AND retailer = ?", (url, retailer))
            result = cursor.fetchone()
            if result:
                conn.close()
                return {'linked_product_url': result[0], 'link_confidence': 1.0, 'link_method': 'exact_url'}
        
        # Level 2: Normalized URL
        if not prefer_fuzzy:
            normalized = url.split('?')[0].rstrip('/')
            cursor.execute("""
                SELECT url FROM products 
                WHERE RTRIM(SUBSTR(url, 1, INSTR(url || '?', '?') - 1), '/') = ?
                AND retailer = ?
            """, (normalized, retailer))
            result = cursor.fetchone()
            if result:
                conn.close()
                return {'linked_product_url': result[0], 'link_confidence': 0.95, 'link_method': 'normalized_url'}
        
        # Level 3: Product code
        if product_code and not prefer_fuzzy:
            cursor.execute("""
                SELECT url FROM products 
                WHERE product_code = ? AND retailer = ?
            """, (product_code, retailer))
            result = cursor.fetchone()
            if result:
                conn.close()
                return {'linked_product_url': result[0], 'link_confidence': 0.90, 'link_method': 'product_code'}
        
        # Level 4: Fuzzy title + price (ALWAYS try this, especially for low-stability retailers)
        if title and price:
            cursor.execute("""
                SELECT url, title FROM products 
                WHERE ABS(price - ?) < 1.0 AND retailer = ?
            """, (price, retailer))
            
            products = cursor.fetchall()
            
            best_match = None
            best_similarity = 0.0
            
            for product_url, product_title in products:
                similarity = SequenceMatcher(
                    None,
                    title.lower().strip(),
                    product_title.lower().strip()
                ).ratio()
                
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = product_url
            
            if best_similarity > 0.90:
                confidence = 0.85 + (best_similarity - 0.90) * 0.5
                conn.close()
                return {'linked_product_url': best_match, 'link_confidence': confidence, 'link_method': 'fuzzy_title_price'}
        
        # Level 5: Image URL matching (secondary confidence signal)
        catalog_images_raw = catalog_product.get('image_urls') or catalog_product.get('images')
        if catalog_images_raw:
            try:
                # Parse catalog images
                if isinstance(catalog_images_raw, str):
                    catalog_images = set(json.loads(catalog_images_raw)) if catalog_images_raw and catalog_images_raw != '[]' else set()
                elif isinstance(catalog_images_raw, list):
                    catalog_images = set(catalog_images_raw)
                else:
                    catalog_images = set()
                
                if not catalog_images:
                    conn.close()
                    return None
                
                # Get products with images and matching price (within $10 for broader matching)
                cursor.execute("""
                    SELECT url, image_urls FROM products 
                    WHERE ABS(price - ?) < 10.0
                    AND retailer = ?
                    AND image_urls IS NOT NULL
                    AND image_urls != ''
                    AND image_urls != '[]'
                """, (price or 0, retailer))
                
                products_with_images = cursor.fetchall()
                
                best_match = None
                best_overlap_ratio = 0.0
                
                for product_url, product_images_raw in products_with_images:
                    # Parse product images
                    if isinstance(product_images_raw, str):
                        product_images = set(json.loads(product_images_raw)) if product_images_raw else set()
                    elif isinstance(product_images_raw, list):
                        product_images = set(product_images_raw)
                    else:
                        product_images = set()
                    
                    if not product_images:
                        continue
                    
                    # Check for overlapping images (exact URL match)
                    overlap = catalog_images.intersection(product_images)
                    
                    if overlap:
                        overlap_ratio = len(overlap) / len(catalog_images)
                        
                        if overlap_ratio > best_overlap_ratio:
                            best_overlap_ratio = overlap_ratio
                            best_match = product_url
                
                if best_match and best_overlap_ratio >= 0.5:  # At least 50% overlap
                    # Check retailer image consistency for confidence adjustment
                    cursor.execute("""
                        SELECT image_urls_consistent 
                        FROM retailer_url_patterns 
                        WHERE retailer = ?
                    """, (retailer,))
                    consistency_result = cursor.fetchone()
                    
                    # Calculate confidence based on overlap and retailer consistency
                    if consistency_result and consistency_result[0] == 1:
                        # High consistency retailer: images are reliable
                        confidence = 0.75 + (best_overlap_ratio * 0.20)  # 0.75 to 0.95
                    else:
                        # Low consistency retailer: images less reliable
                        confidence = 0.65 + (best_overlap_ratio * 0.15)  # 0.65 to 0.80
                    
                    conn.close()
                    logger.debug(f"Image match: {best_overlap_ratio:.0%} overlap, confidence {confidence:.2f}")
                    return {'linked_product_url': best_match, 'link_confidence': confidence, 'link_method': 'image_url_match'}
            
            except Exception as e:
                logger.error(f"Image matching failed: {e}")
        
        conn.close()
        return None
    
    async def monitor_catalog(
        self,
        retailer: str,
        category: str,
        modesty_level: str,
        custom_url: Optional[str] = None,
        max_pages: int = 5
    ) -> MonitorResult:
        """
        Monitor catalog for new products
        
        Args:
            retailer: Retailer name
            category: Product category
            modesty_level: Modesty level to monitor
            custom_url: Custom catalog URL (optional)
            max_pages: Maximum pages to scan (default 5 for monitoring)
            
        Returns:
            MonitorResult
        """
        start_time = datetime.utcnow()
        failures = []  # Track all failures for this run
        
        try:
            logger.info("⚠️ PREREQUISITE CHECK: Product Updater should run before monitoring")
            logger.info(f"📊 Monitoring catalog: {retailer}/{category}/{modesty_level}")
            
            # Step 1: Get catalog URL
            if custom_url:
                catalog_url = custom_url
            else:
                catalog_url = self._get_catalog_url(retailer, category, workflow='monitoring')
                if not catalog_url:
                    return self._error_result(
                        retailer, category, modesty_level, start_time,
                        f'No catalog URL configured for {retailer}/{category}'
                    )
            
            logger.info(f"   URL: {catalog_url}")
            
            # Step 2: Initialize towers
            await self._initialize_towers()
            
            # Step 3: Scan catalog with appropriate tower
            # Check if retailer should use Commercial API tower
            if COMMERCIAL_API_AVAILABLE and CommercialAPIConfig.should_use_commercial_api(retailer):
                logger.info(f"🌐 Using Commercial API Tower for {retailer} catalog (Bright Data + BeautifulSoup)")
                extraction_result = await self.commercial_catalog_tower.extract_catalog(
                    catalog_url,
                    retailer,
                    category,
                    max_products=100
                )
                method_used = 'commercial_api'
                
                # Handle Commercial API result format
                if extraction_result.success:
                    success = True
                    catalog_products = extraction_result.products
                    errors = []
                else:
                    success = False
                    catalog_products = []
                    errors = [extraction_result.error] if extraction_result.error else ['Unknown error']
            else:
                # ALL other retailers use Patchright for catalog (JavaScript-loaded product URLs)
                logger.info(f"🔄 Using Patchright Tower for {retailer} catalog (DOM extraction)")
                catalog_prompt = f"Extract all products from this {retailer} {category} catalog page"
                extraction_result = await self.patchright_catalog_tower.extract_catalog(
                    catalog_url,
                    retailer,
                    catalog_prompt
                )
                method_used = 'patchright'
                
                # Handle Patchright result format (dict or object)
                if isinstance(extraction_result, dict):
                    success = extraction_result.get('success', False)
                    catalog_products = extraction_result.get('products', [])
                    errors = extraction_result.get('errors', [])
                else:
                    success = extraction_result.success
                    catalog_products = extraction_result.data.get('products', [])
                    errors = extraction_result.errors
            
            if not success:
                return self._error_result(
                    retailer, category, modesty_level, start_time,
                    str(errors)
                )
            logger.info(f"📦 Scanned {len(catalog_products)} products from catalog")
            
            # Normalize field names: 'url' → 'catalog_url' (following old system pattern)
            for product in catalog_products:
                if 'url' in product and 'catalog_url' not in product:
                    product['catalog_url'] = product['url']
            
            # Step 4: Deduplication against DB (multi-level)
            dedup_results = await self._deduplicate_catalog_products(
                catalog_products,
                retailer,
                category
            )
            
            logger.info(f"🔍 Deduplication results:")
            logger.info(f"   New: {len(dedup_results['new'])}")
            logger.info(f"   Suspected duplicates: {len(dedup_results['suspected_duplicate'])}")
            logger.info(f"   Confirmed existing: {len(dedup_results['confirmed_existing'])}")
            
            # Step 4.5: Save catalog snapshot (ALL products, every run)
            await self._save_catalog_snapshot(
                catalog_products=catalog_products,
                retailer=retailer,
                category=category,
                modesty_level=modesty_level
            )
            
            # Step 4.6: Detect price changes
            price_changes = await self._detect_price_changes(
                catalog_products=catalog_products,
                retailer=retailer
            )
            
            # Step 5: Process new products
            sent_to_modesty = 0
            for product in dedup_results['new']:
                product_url = product.get('url') or product.get('catalog_url')
                if not product_url:
                    logger.warning(f"Product missing URL, skipping: {product}")
                    continue
                
                # Re-extract with SINGLE product extractor for full details (now passes category parameter)
                # Use Markdown for retailers that support it (fast & cheap), Patchright for others
                single_product_method = 'markdown' if retailer in MARKDOWN_SINGLE_PRODUCT_RETAILERS else 'patchright'
                full_product = await self._extract_single_product(
                    product_url,
                    retailer,
                    single_product_method,
                    category  # Pass category for override logic
                )
                
                # Check if extraction failed (returns dict with _extraction_error key)
                if full_product and '_extraction_error' in full_product:
                    # Track extraction failure with full error details
                    failures.append({
                        'url': product_url,
                        'reason': full_product['_extraction_error'],
                        'stage': 'extraction',
                        'product_type': 'new',
                        'method_attempted': full_product.get('_method_used', single_product_method),
                        'attempted_at': datetime.utcnow().isoformat(),
                        'certainty': 'known_error' if 'Unknown' not in full_product['_extraction_error'] else 'uncertain'
                    })
                    full_product = None  # Treat as failed
                elif not full_product:
                    # Unexpected None return (shouldn't happen with new code, but handle it)
                    failures.append({
                        'url': product_url,
                        'reason': 'Product extraction returned None unexpectedly - possible unhandled exception in extractor',
                        'stage': 'extraction',
                        'product_type': 'new',
                        'method_attempted': single_product_method,
                        'attempted_at': datetime.utcnow().isoformat(),
                        'certainty': 'uncertain'
                    })
                    full_product = None
                
                if full_product:
                    # Add source URL (extractor doesn't include it)
                    full_product['url'] = product_url
                    full_product['catalog_url'] = product_url  # For consistency
                    
                    # MANGO-SPECIFIC FILTERING
                    if retailer.lower() == 'mango':
                        clothing_type = full_product.get('clothing_type', 'other')
                        
                        # Only allow dress, top, and dress_top to assessment pipeline
                        if clothing_type not in ['dress', 'top', 'dress_top']:
                            logger.info(f"⏭️ Skipping {clothing_type} (Mango filter): {full_product.get('title', 'N/A')}")
                            
                            # Upload to Shopify as draft (unpublished)
                            await self._upload_non_assessed_product(
                                full_product,
                                retailer,
                                status='draft'
                            )
                            continue
                    
                    # NEW: Upload to Shopify as DRAFT before assessment
                    shopify_result = await self._upload_to_shopify_as_draft(
                        full_product,
                        retailer,
                        category
                    )
                    
                    if shopify_result['success']:
                        # Add Shopify data to product for assessment queue
                        full_product['shopify_id'] = shopify_result['shopify_id']
                        full_product['shopify_image_urls'] = shopify_result['shopify_image_urls']
                        full_product['shopify_status'] = 'draft'
                        
                        # Send to Assessment Pipeline for MODESTY review
                        await self._send_to_modesty_assessment(full_product, retailer, category, modesty_level)
                        sent_to_modesty += 1
                    else:
                        # Track Shopify upload failure with full error details
                        shopify_error = shopify_result.get('error', 'Unknown error - no error details provided by Shopify')
                        failures.append({
                            'url': product_url,
                            'reason': f"Shopify upload failed: {shopify_error}",
                            'stage': 'shopify_upload',
                            'product_type': 'new',
                            'product_title': full_product.get('title', 'Unknown'),
                            'retailer': retailer,
                            'attempted_at': datetime.utcnow().isoformat(),
                            'certainty': 'known_error' if 'Unknown' not in shopify_error else 'uncertain',
                            'shopify_status_code': shopify_result.get('status_code') if 'status_code' in shopify_result else None
                        })
                        logger.error(f"❌ Skipping assessment for {full_product.get('title')} - Shopify upload failed")
                
                # Respectful delay
                await asyncio.sleep(0.5)
            
            # Step 6: Process suspected duplicates
            sent_to_duplicate_review = 0
            for product in dedup_results['suspected_duplicate']:
                product_url = product.get('url') or product.get('catalog_url')
                if not product_url:
                    logger.warning(f"Suspected duplicate missing URL, skipping: {product}")
                    continue
                
                # Extract full product data (needed if promoted to modesty review later)
                # Use Markdown for retailers that support it (fast & cheap), Patchright for others
                single_product_method = 'markdown' if retailer in MARKDOWN_SINGLE_PRODUCT_RETAILERS else 'patchright'
                full_product = await self._extract_single_product(
                    product_url,
                    retailer,
                    single_product_method,
                    category
                )
                
                # Check if extraction failed (returns dict with _extraction_error key)
                if full_product and '_extraction_error' in full_product:
                    # Track extraction failure with full error details
                    failures.append({
                        'url': product_url,
                        'reason': full_product['_extraction_error'],
                        'stage': 'extraction',
                        'product_type': 'suspected_duplicate',
                        'method_attempted': full_product.get('_method_used', single_product_method),
                        'suspected_match': product.get('suspected_match', {}).get('url') if product.get('suspected_match') else None,
                        'attempted_at': datetime.utcnow().isoformat(),
                        'certainty': 'known_error' if 'Unknown' not in full_product['_extraction_error'] else 'uncertain'
                    })
                    full_product = None  # Treat as failed
                elif not full_product:
                    # Unexpected None return (shouldn't happen with new code, but handle it)
                    failures.append({
                        'url': product_url,
                        'reason': 'Product extraction returned None unexpectedly - possible unhandled exception in extractor',
                        'stage': 'extraction',
                        'product_type': 'suspected_duplicate',
                        'method_attempted': single_product_method,
                        'attempted_at': datetime.utcnow().isoformat(),
                        'certainty': 'uncertain'
                    })
                    full_product = None
                
                if full_product:
                    # Add source URL
                    full_product['url'] = product_url
                    full_product['catalog_url'] = product_url
                    
                    # Upload to Shopify as DRAFT (in case it's "not duplicate" and needs modesty review)
                    shopify_result = await self._upload_to_shopify_as_draft(
                        full_product,
                        retailer,
                        category
                    )
                    
                    if shopify_result['success']:
                        # Add Shopify data
                        full_product['shopify_id'] = shopify_result['shopify_id']
                        full_product['shopify_image_urls'] = shopify_result['shopify_image_urls']
                        full_product['shopify_status'] = 'draft'
                        
                        # Preserve suspected match data from deduplication
                        full_product['suspected_match'] = product.get('suspected_match')
                        full_product['confidence_score'] = product.get('confidence_score')
                        
                        # Send to Assessment Pipeline for DUPLICATION review
                        await self._send_to_duplicate_assessment(full_product, retailer, category)
                        sent_to_duplicate_review += 1
                    else:
                        # Track Shopify upload failure with full error details
                        shopify_error = shopify_result.get('error', 'Unknown error - no error details provided by Shopify')
                        failures.append({
                            'url': product_url,
                            'reason': f"Shopify upload failed: {shopify_error}",
                            'stage': 'shopify_upload',
                            'product_type': 'suspected_duplicate',
                            'product_title': full_product.get('title', 'Unknown'),
                            'suspected_match': product.get('suspected_match', {}).get('url') if product.get('suspected_match') else None,
                            'retailer': retailer,
                            'attempted_at': datetime.utcnow().isoformat(),
                            'certainty': 'known_error' if 'Unknown' not in shopify_error else 'uncertain',
                            'shopify_status_code': shopify_result.get('status_code') if 'status_code' in shopify_result else None
                        })
                        logger.error(f"❌ Skipping duplicate assessment - Shopify upload failed for {full_product.get('title')}")
                
                # Respectful delay
                await asyncio.sleep(0.5)
            
            # Step 7: Record monitoring run
            await self.db_manager.record_monitoring_run(
                retailer=retailer,
                category=category,
                modesty_level=modesty_level,
                products_scanned=len(catalog_products),
                new_found=len(dedup_results['new']),
                duplicates=len(dedup_results['suspected_duplicate']),
                run_time=datetime.utcnow()
            )
            
            # Step 8: Save failures if any
            if failures:
                from pathlib import Path
                import json
                
                # Create batch ID
                batch_id = f"catalog_monitor_{retailer}_{category}_{modesty_level}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
                
                failures_data = {
                    'batch_id': batch_id,
                    'workflow': 'catalog_monitor',
                    'retailer': retailer,
                    'category': category,
                    'modesty_level': modesty_level,
                    'run_date': start_time.isoformat(),
                    'total_failed': len(failures),
                    'failures': failures
                }
                
                # Save to failures folder
                failures_dir = Path("failures")
                failures_dir.mkdir(exist_ok=True)
                failures_file = failures_dir / f"{batch_id}_failures.json"
                
                with open(failures_file, 'w') as f:
                    json.dump(failures_data, f, indent=2)
                
                logger.warning(f"⚠️  {len(failures)} failures saved to {failures_file}")
            
            # Step 9: Notifications
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            total_cost = cost_tracker.get_session_cost()
            
            await self.notification_manager.send_monitoring_summary(
                retailer=retailer,
                category=category,
                modesty_level=modesty_level,
                products_scanned=len(catalog_products),
                new_found=len(dedup_results['new']),
                suspected_duplicates=len(dedup_results['suspected_duplicate']),
                processing_time=processing_time,
                total_cost=total_cost
            )
            
            # Cleanup Commercial API towers if used
            if COMMERCIAL_API_AVAILABLE and self.commercial_catalog_tower:
                await self.commercial_catalog_tower.cleanup()
            if COMMERCIAL_API_AVAILABLE and self.commercial_product_tower:
                await self.commercial_product_tower.cleanup()
            
            return MonitorResult(
                success=True,
                retailer=retailer,
                category=category,
                modesty_level=modesty_level,
                products_scanned=len(catalog_products),
                new_products_found=len(dedup_results['new']),
                suspected_duplicates=len(dedup_results['suspected_duplicate']),
                confirmed_existing=len(dedup_results['confirmed_existing']),
                sent_to_modesty_review=sent_to_modesty,
                sent_to_duplicate_review=sent_to_duplicate_review,
                processing_time=processing_time,
                method_used=method_used
            )
            
        except Exception as e:
            logger.error(f"Catalog monitoring failed: {e}")
            
            # Cleanup Commercial API towers if used
            try:
                if COMMERCIAL_API_AVAILABLE and self.commercial_catalog_tower:
                    await self.commercial_catalog_tower.cleanup()
                if COMMERCIAL_API_AVAILABLE and self.commercial_product_tower:
                    await self.commercial_product_tower.cleanup()
            except:
                pass  # Don't fail on cleanup errors
            
            return self._error_result(retailer, category, modesty_level, start_time, str(e))
    
    async def _deduplicate_catalog_products(
        self,
        catalog_products: List[Dict],
        retailer: str,
        category: str
    ) -> Dict[str, List[Dict]]:
        """
        Deduplicate catalog products against both baseline and main products DB
        
        Uses multi-level matching:
        1. Exact URL match
        2. Normalized URL match (no query params)
        3. Product code match
        4. Title + Price exact match
        5. Title fuzzy match (>85% similarity) + price within 10%
        6. Image URL match
        
        Returns:
            {
                'new': [...],
                'suspected_duplicate': [...],
                'confirmed_existing': [...]
            }
        """
        results = {
            'new': [],
            'suspected_duplicate': [],
            'confirmed_existing': []
        }
        
        for product in catalog_products:
            match_result = await self._find_matching_product(product, retailer, category)
            
            if match_result['status'] == 'confirmed_new':
                results['new'].append(product)
            elif match_result['status'] == 'suspected_duplicate':
                product['suspected_match'] = match_result
                results['suspected_duplicate'].append(product)
            else:
                results['confirmed_existing'].append(product)
        
        return results
    
    async def _find_matching_product(
        self,
        product: Dict,
        retailer: str,
        category: str
    ) -> Dict[str, Any]:
        """
        Find matching product using multi-level deduplication strategies
        
        Returns:
            {
                'status': 'confirmed_new' | 'suspected_duplicate' | 'confirmed_existing',
                'match_method': str,
                'confidence': float,
                'matched_product': Dict (if found)
            }
        """
        # Strategy 1: Exact URL match
        match = await self._check_exact_url_match(product, retailer)
        if match and match['confidence'] >= 0.95:
            return {
                'status': 'confirmed_existing',
                'match_method': 'exact_url',
                'confidence': match['confidence'],
                'matched_product': match['product']
            }
        
        # Strategy 2: Normalized URL match
        match = await self._check_normalized_url_match(product, retailer)
        if match and match['confidence'] >= 0.90:
            return {
                'status': 'confirmed_existing',
                'match_method': 'normalized_url',
                'confidence': match['confidence'],
                'matched_product': match['product']
            }
        
        # Strategy 3: Product code match
        match = await self._check_product_code_match(product, retailer)
        if match and match['confidence'] >= 0.90:
            return {
                'status': 'confirmed_existing',
                'match_method': 'product_code',
                'confidence': match['confidence'],
                'matched_product': match['product']
            }
        
        # Strategy 4: Title + Price exact match
        match = await self._check_title_price_match(product, retailer)
        if match and match['confidence'] >= 0.95:
            return {
                'status': 'confirmed_existing',
                'match_method': 'title_price',
                'confidence': match['confidence'],
                'matched_product': match['product']
            }
        
        # Strategy 5: Fuzzy title match + price similarity
        match = await self._check_fuzzy_title_match(product, retailer)
        if match:
            if match['confidence'] >= 0.85:
                return {
                    'status': 'suspected_duplicate',
                    'match_method': 'fuzzy_title',
                    'confidence': match['confidence'],
                    'matched_product': match['product']
                }
        
        # Strategy 6: Image URL match
        match = await self._check_image_url_match(product, retailer)
        if match and match['confidence'] >= 0.90:
            return {
                'status': 'suspected_duplicate',
                'match_method': 'image_url',
                'confidence': match['confidence'],
                'matched_product': match['product']
            }
        
        # No match found - confirmed new
        return {
            'status': 'confirmed_new',
            'match_method': 'none',
            'confidence': 0.0,
            'matched_product': None
        }
    
    async def _check_exact_url_match(self, product: Dict, retailer: str) -> Optional[Dict]:
        """Check for exact URL match in both baseline and products tables"""
        # Try both field names (url from extraction, catalog_url from baseline)
        url = product.get('url') or product.get('catalog_url')
        if not url:
            return None
        
        # Check main products table
        existing = await self.db_manager.find_product_by_url(url, retailer)
        if existing:
            return {'confidence': 1.0, 'product': existing}
        
        # Check baseline (catalog_products table)
        baseline = await self.db_manager.find_baseline_product_by_url(url, retailer)
        if baseline:
            return {'confidence': 1.0, 'product': baseline}
        
        return None
    
    async def _check_normalized_url_match(self, product: Dict, retailer: str) -> Optional[Dict]:
        """Check for normalized URL match (without query params)"""
        # Try both field names
        url = product.get('url') or product.get('catalog_url')
        if not url:
            return None
        
        normalized = self._normalize_url(url)
        
        # Check main products table
        existing = await self.db_manager.find_product_by_normalized_url(normalized, retailer)
        if existing:
            return {'confidence': 0.95, 'product': existing}
        
        # Check baseline (catalog_products table)
        baseline = await self.db_manager.find_baseline_product_by_url(url, retailer)
        if baseline:
            return {'confidence': 0.95, 'product': baseline}
        
        return None
    
    async def _check_product_code_match(self, product: Dict, retailer: str) -> Optional[Dict]:
        """Check for product code match"""
        url = product.get('url') or product.get('catalog_url')
        product_code = product.get('product_code') or self._extract_product_code(url, retailer)
        if not product_code:
            return None
        
        # Check main products table
        existing = await self.db_manager.find_product_by_code(product_code, retailer)
        if existing:
            return {'confidence': 0.95, 'product': existing}
        
        # Check baseline (catalog_products table) - search by product code in URL
        baseline = await self.db_manager.find_baseline_product_by_code(product_code, retailer)
        if baseline:
            return {'confidence': 0.95, 'product': baseline}
        
        return None
    
    async def _check_title_price_match(self, product: Dict, retailer: str) -> Optional[Dict]:
        """Check for exact title + price match"""
        title = product.get('title')
        price = product.get('price')
        if not title or not price:
            return None
        
        # Normalize title for comparison (defensive against None)
        title_normalized = (title or '').lower().strip()
        if not title_normalized:
            return None
        
        # Check main products table
        existing = await self.db_manager.find_product_by_title_price(title_normalized, price, retailer)
        if existing:
            return {'confidence': 1.0, 'product': existing}
        
        # Check baseline (catalog_products table)
        baseline = await self.db_manager.find_baseline_product_by_title_price(title_normalized, price, retailer)
        if baseline:
            return {'confidence': 1.0, 'product': baseline}
        
        return None
    
    async def _check_fuzzy_title_match(self, product: Dict, retailer: str) -> Optional[Dict]:
        """Check for fuzzy title match with price similarity"""
        title = product.get('title')
        price = product.get('price')
        if not title or not price:
            return None
        
        # Defensive: Handle None titles
        title_normalized = (title or '').lower().strip()
        if not title_normalized:
            return None
        
        # Get similar products from DB
        candidates = await self.db_manager.find_products_by_retailer(retailer, limit=1000)
        
        best_match = None
        best_similarity = 0.0
        
        for candidate in candidates:
            # Defensive: Handle None titles (db can have NULL values)
            candidate_title = (candidate.get('title') or '').lower().strip()
            candidate_price = candidate.get('price')
            
            if not candidate_title or not candidate_price:
                continue
            
            # Calculate title similarity
            similarity = SequenceMatcher(None, title_normalized, candidate_title).ratio()
            
            # Calculate price difference
            try:
                price_val = float(str(price).replace('$', '').replace(',', ''))
                candidate_price_val = float(str(candidate_price).replace('$', '').replace(',', ''))
                price_diff = abs(price_val - candidate_price_val) / price_val
            except:
                price_diff = 1.0
            
            # If title >85% similar and price within 10%
            if similarity > 0.85 and price_diff < 0.10:
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = candidate
        
        if best_match:
            return {'confidence': best_similarity, 'product': best_match}
        
        return None
    
    async def _check_image_url_match(self, product: Dict, retailer: str) -> Optional[Dict]:
        """Check for image URL match"""
        images = product.get('images', [])
        if not images:
            return None
        
        # Check first image
        first_image = images[0] if isinstance(images, list) else images
        
        # Check main products table
        existing = await self.db_manager.find_product_by_image(first_image, retailer)
        if existing:
            return {'confidence': 0.90, 'product': existing}
        
        return None
    
    def _normalize_clothing_type(self, raw_type: str) -> str:
        """
        Normalize clothing type names to standard format
        
        Maps various inputs to: dress, top, dress_top, bottom, outerwear, other
        """
        if not raw_type:
            return 'other'
        
        raw_lower = raw_type.lower().strip()
        
        # Normalization mapping
        type_map = {
            # Dresses
            'dress': 'dress',
            'dresses': 'dress',
            'gown': 'dress',
            'gowns': 'dress',
            'maxi dress': 'dress',
            'midi dress': 'dress',
            'mini dress': 'dress',
            
            # Tops (excluding dress tops)
            'top': 'top',
            'tops': 'top',
            'shirt': 'top',
            'shirts': 'top',
            'blouse': 'top',
            'blouses': 'top',
            'tee': 'top',
            't-shirt': 'top',
            'tshirt': 'top',
            'sweater': 'top',
            'cardigan': 'top',
            'hoodie': 'top',
            
            # Dress Tops (NEW CATEGORY)
            'dress top': 'dress_top',
            'dress tops': 'dress_top',
            'dress-top': 'dress_top',
            'dress-tops': 'dress_top',
            'dress_top': 'dress_top',
            'dress_tops': 'dress_top',
            'tunic': 'dress_top',
            'tunics': 'dress_top',
            'long top': 'dress_top',
            'oversized top': 'dress_top',
            
            # Bottoms
            'bottom': 'bottom',
            'bottoms': 'bottom',
            'pants': 'bottom',
            'pant': 'bottom',
            'jeans': 'bottom',
            'skirt': 'bottom',
            'skirts': 'bottom',
            'shorts': 'bottom',
            'trousers': 'bottom',
            
            # Outerwear
            'outerwear': 'outerwear',
            'jacket': 'outerwear',
            'jackets': 'outerwear',
            'coat': 'outerwear',
            'coats': 'outerwear',
            'blazer': 'outerwear',
            'blazers': 'outerwear',
            
            # Other/Unknown
            'other': 'other',
            'unknown': 'other',
            'accessory': 'other',
            'accessories': 'other',
            'swimwear': 'other',
            'lingerie': 'other',
        }
        
        return type_map.get(raw_lower, 'other')
    
    async def _extract_single_product(
        self,
        url: str,
        retailer: str,
        method: str,
        category: str  # NEW parameter
    ) -> Optional[Dict]:
        """Extract full product details and apply clothing_type logic
        
        Returns:
            Dict with product data on success, or Dict with '_extraction_error' key on failure
        """
        try:
            commercial_api_error = None  # Track Commercial API failures for error reporting
            
            # Check if retailer should use Commercial API tower
            if COMMERCIAL_API_AVAILABLE and CommercialAPIConfig.should_use_commercial_api(retailer):
                logger.debug(f"🌐 Using Commercial API Tower for product: {url[:70]}...")
                result = await self.commercial_product_tower.extract_product(url, retailer, category)
                
                # Handle Commercial API result format
                if result.success:
                    # Convert to expected format
                    result_obj = type('obj', (object,), {
                        'success': True,
                        'data': result.product_data
                    })()
                    result = result_obj
                else:
                    # Capture Commercial API error for later reporting
                    commercial_api_error = result.error or "Commercial API extraction failed (no specific error)"
                    
                    # Fallback to Patchright if Commercial API fails
                    logger.warning(f"Commercial API extraction failed for {url}: {commercial_api_error}, falling back to Patchright")
                    result = await self.patchright_product_tower.extract_product(url, retailer)
            elif method == 'markdown':
                result = await self.markdown_product_tower.extract_product(url, retailer)
                
                # FALLBACK: If markdown fails, try Patchright
                if not result.success and result.should_fallback:
                    logger.warning(f"Markdown extraction failed for {url}, falling back to Patchright")
                    result = await self.patchright_product_tower.extract_product(url, retailer)
            else:
                result = await self.patchright_product_tower.extract_product(url, retailer)
            
            if result.success:
                product_data = result.data
                
                # CLOTHING TYPE DETERMINATION LOGIC
                if retailer.lower() != 'mango':
                    # NORMAL RETAILERS: Category parameter overrides extracted clothing_type
                    clothing_type_from_category = self._normalize_clothing_type(category)
                    product_data['clothing_type'] = clothing_type_from_category
                    product_data['clothing_type_source'] = 'category_override'
                    logger.debug(f"Category override: {category} → {clothing_type_from_category}")
                else:
                    # MANGO ONLY: Use extracted clothing_type (no override)
                    extracted_type = product_data.get('clothing_type', 'unknown')
                    normalized_type = self._normalize_clothing_type(extracted_type)
                    product_data['clothing_type'] = normalized_type
                    product_data['clothing_type_source'] = 'extraction'
                    logger.debug(f"Mango extracted type: {extracted_type} → {normalized_type}")
                
                return product_data
            else:
                # Return error details for failure tracking
                error_details = str(result.errors) if result.errors else "Unknown extraction error - no error details provided by extractor"
                
                # If Commercial API was tried first and failed, include that in error details
                if commercial_api_error:
                    error_details = f"Commercial API failed: {commercial_api_error}. Then Patchright fallback failed: {error_details}"
                
                logger.error(f"Failed to extract product {url}: {error_details}")
                return {
                    '_extraction_error': error_details,
                    '_method_used': result.method_used if hasattr(result, 'method_used') else method,
                    '_url': url,
                    '_commercial_api_attempted': commercial_api_error is not None
                }
                
        except Exception as e:
            logger.error(f"Error extracting product {url}: {e}")
            return None
    
    async def _upload_to_shopify_as_draft(
        self,
        product: Dict,
        retailer: str,
        category: str
    ) -> Dict:
        """
        Upload product to Shopify as draft for assessment
        
        Returns:
            Dict with success status, shopify_id, and shopify_image_urls
        """
        try:
            from shopify_manager import ShopifyManager
            from image_processor import ImageProcessor
            
            shopify = ShopifyManager()
            image_proc = ImageProcessor()
            
            # Process images (download from retailer URLs)
            image_urls = product.get('image_urls', [])
            downloaded_images = []
            
            if image_urls:
                logger.debug(f"🖼️ Processing {len(image_urls)} images for draft upload")
                downloaded_images = await image_proc.process_images(
                    image_urls=image_urls,
                    retailer=retailer,
                    product_title=product.get('title', 'Product')
                )
                logger.info(f"✅ Downloaded {len(downloaded_images)} images")
            
            # Upload to Shopify as DRAFT (published=False)
            result = await shopify.create_product(
                extracted_data=product,
                retailer_name=retailer,
                modesty_level='pending_review',  # Will be determined by human
                source_url=product.get('url'),
                downloaded_images=downloaded_images,
                product_type_override=None,
                published=False  # KEY: Create as draft
            )
            
            if result['success']:
                shopify_id = result['product_id']
                shopify_image_urls = result.get('shopify_image_urls', [])
                
                logger.info(f"✅ Uploaded as draft to Shopify: {shopify_id}")
                
                # Save to local DB with image upload tracking
                # Extract integer product_id from Shopify response
                shopify_product_id = shopify_id.get('product_id') if isinstance(shopify_id, dict) else shopify_id
                
                await self.db_manager.save_product(
                    url=product['url'],
                    retailer=retailer,
                    product_data=product,
                    shopify_id=shopify_product_id,
                    modesty_status='pending_review',
                    shopify_status='draft',  # Mark as draft in DB
                    images_uploaded=1 if downloaded_images else 0,  # Track image upload success
                    source='monitor',  # Track as discovered by catalog monitoring
                    lifecycle_stage='pending_assessment',  # NEW - lifecycle tracking
                    data_completeness='full',  # NEW - has full product details
                    last_workflow='catalog_monitor',  # NEW - workflow attribution
                    extracted_at=datetime.utcnow().isoformat()  # NEW - extraction timestamp
                )
                
                return {
                    'success': True,
                    'shopify_id': shopify_id,
                    'shopify_image_urls': shopify_image_urls
                }
            else:
                logger.error(f"❌ Failed to upload to Shopify: {result.get('error')}")
                return {
                    'success': False,
                    'error': result.get('error')
                }
                
        except Exception as e:
            logger.error(f"Exception uploading to Shopify as draft: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _upload_non_assessed_product(
        self,
        product: Dict,
        retailer: str,
        status: str = 'draft'
    ):
        """
        Upload product to Shopify as draft (unpublished)
        Used for Mango products that don't match dress/top/dress_top categories
        """
        try:
            from shopify_manager import ShopifyManager
            
            shopify = ShopifyManager()
            
            # Set as not assessed
            product['modesty_status'] = 'not_assessed'
            
            result = await shopify.upload_product(
                product_data=product,
                retailer_name=retailer,
                modesty_level='not_assessed',
                publish_status='draft'  # Keep unpublished
            )
            
            if result['success']:
                logger.info(f"✅ Uploaded as draft (non-assessed): {product.get('title', 'N/A')}")
                
                # Save to database
                await self.db_manager.save_product(
                    url=product['url'],
                    retailer=retailer,
                    product_data=product,
                    shopify_id=result.get('product_id'),
                    modesty_status='not_assessed',
                    lifecycle_stage='imported_direct',  # NEW - bypassed assessment
                    data_completeness='full',  # NEW - has full product details
                    last_workflow='catalog_monitor',  # NEW - workflow attribution
                    extracted_at=datetime.utcnow().isoformat()  # NEW - extraction timestamp
                )
            else:
                logger.warning(f"❌ Draft upload failed: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"Error uploading non-assessed product: {e}")
    
    async def _send_to_modesty_assessment(
        self,
        product: Dict,
        retailer: str,
        category: str,
        modesty_level: str
    ):
        """Send product to Assessment Pipeline for MODESTY review"""
        await self.assessment_queue.add_to_queue(
            product=product,
            retailer=retailer,
            category=category,
            review_type='modesty',
            priority='normal',
            source_workflow='catalog_monitor'
        )
        logger.debug(f"Sent to modesty assessment: {product.get('title', 'N/A')}")
    
    async def _send_to_duplicate_assessment(
        self,
        product: Dict,
        retailer: str,
        category: str
    ):
        """Send product to Assessment Pipeline for DUPLICATION review"""
        suspected_match = product.get('suspected_match')
        
        await self.assessment_queue.add_to_queue(
            product=product,
            retailer=retailer,
            category=category,
            review_type='duplication',
            priority='low',
            source_workflow='catalog_monitor',
            suspected_match=suspected_match
        )
        logger.debug(f"Sent to duplication assessment: {product.get('title', 'N/A')}")
    
    def _normalize_url(self, url: str) -> str:
        """Normalize URL by removing query parameters"""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    
    def _extract_product_code(self, url: str, retailer: str) -> Optional[str]:
        """Extract product code from URL"""
        if not url:
            return None
        
        retailer_lower = retailer.lower()
        
        # Revolve: /dp/CODE/
        if retailer_lower == 'revolve':
            match = re.search(r'/dp/([A-Z0-9\-]+)/?', url, re.IGNORECASE)
            if match:
                return match.group(1)
        
        # Add other retailer patterns as needed
        
        return None
    
    def _get_catalog_url(self, retailer: str, category: str, workflow: str = 'monitoring') -> Optional[str]:
        """
        Get catalog URL from configuration
        
        Args:
            retailer: Retailer name
            category: Product category (dresses, tops)
            workflow: 'monitoring' or 'baseline' (affects Mango URLs only)
        
        Returns:
            Catalog URL or None
        """
        retailer_lower = retailer.lower()
        category_lower = category.lower()
        
        # MANGO SPECIAL CASE: Different URLs for monitoring vs baseline
        if retailer_lower == 'mango' and workflow == 'monitoring':
            # Use What's New section for monitoring (regardless of category)
            return "https://shop.mango.com/us/en/c/women/new-now_56b5c5ed"
        
        # All other retailers + Mango baseline: use standard CATALOG_URLS
        if retailer_lower in CATALOG_URLS:
            return CATALOG_URLS[retailer_lower].get(category_lower)
        
        return None
    
    async def _initialize_towers(self):
        """Initialize all extraction towers"""
        if not self.markdown_catalog_tower:
            self.markdown_catalog_tower = MarkdownCatalogExtractor()
        if not self.markdown_product_tower:
            self.markdown_product_tower = MarkdownProductExtractor()
        if not self.patchright_catalog_tower:
            self.patchright_catalog_tower = PatchrightCatalogExtractor()
        if not self.patchright_product_tower:
            self.patchright_product_tower = PatchrightProductExtractor()
        
        # Initialize Commercial API towers if available
        if COMMERCIAL_API_AVAILABLE:
            if not self.commercial_catalog_tower:
                self.commercial_catalog_tower = CommercialCatalogExtractor()
                await self.commercial_catalog_tower.initialize()
                logger.debug("✅ Commercial API catalog tower initialized")
            if not self.commercial_product_tower:
                self.commercial_product_tower = CommercialProductExtractor()
                await self.commercial_product_tower.initialize()
                logger.debug("✅ Commercial API product tower initialized")
        
        logger.debug("All towers initialized")
    
    def _error_result(
        self,
        retailer: str,
        category: str,
        modesty_level: str,
        start_time: datetime,
        error: str
    ) -> MonitorResult:
        """Create error result"""
        return MonitorResult(
            success=False,
            retailer=retailer,
            category=category,
            modesty_level=modesty_level,
            products_scanned=0,
            new_products_found=0,
            suspected_duplicates=0,
            confirmed_existing=0,
            sent_to_modesty_review=0,
            sent_to_duplicate_review=0,
            processing_time=(datetime.utcnow() - start_time).total_seconds(),
            method_used='error',
            error=error
        )


# CLI entry point
async def main():
    """CLI entry point for Catalog Monitor"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Monitor catalog for new products')
    parser.add_argument('retailer', help='Retailer name')
    parser.add_argument('category', help='Product category')
    parser.add_argument('modesty_level', help='Modesty level to monitor')
    parser.add_argument('--url', help='Custom catalog URL')
    parser.add_argument('--max-pages', type=int, default=5, help='Maximum pages to scan')
    
    args = parser.parse_args()
    
    print("⚠️ IMPORTANT: Run Product Updater first to ensure DB is up-to-date!")
    print("   This prevents false positives from URL/product code changes.\n")
    
    monitor = CatalogMonitor()
    result = await monitor.monitor_catalog(
        retailer=args.retailer,
        category=args.category,
        modesty_level=args.modesty_level,
        custom_url=args.url,
        max_pages=args.max_pages
    )
    
    # Sync database to web server if products were added to assessment queue
    if result.sent_to_modesty_review > 0 or result.sent_to_duplicate_review > 0:
        logger.info("\n" + "=" * 60)
        logger.info("SYNCING DATABASE TO WEB SERVER")
        logger.info("=" * 60)
        
        try:
            sync_success = await sync_database_async()
            
            if sync_success:
                logger.info("✅ Database synced to assessmodesty.com")
                logger.info("Assessment pipeline will show updated products")
            else:
                logger.warning("⚠️  Database sync failed - assessment pipeline may show stale data")
                logger.warning("Run 'python3 Shared/database_sync.py' manually to sync")
        
        except Exception as e:
            logger.error(f"❌ Database sync error: {e}")
            logger.warning("Assessment pipeline may show stale data until manual sync")
    else:
        logger.info("ℹ️  No products added to assessment queue - skipping database sync")
    
    print(json.dumps({
        'success': result.success,
        'products_scanned': result.products_scanned,
        'new_products_found': result.new_products_found,
        'suspected_duplicates': result.suspected_duplicates,
        'sent_to_modesty_review': result.sent_to_modesty_review,
        'sent_to_duplicate_review': result.sent_to_duplicate_review,
        'processing_time': result.processing_time,
        'error': result.error
    }, indent=2))


if __name__ == "__main__":
    asyncio.run(main())

