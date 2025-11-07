"""
Database Manager Facade
Provides unified interface for workflows to access database operations

This facade wraps existing database managers and provides
the methods that workflows expect.
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))
sys.path.append(os.path.join(os.path.dirname(__file__), "../Catalog Crawler"))

import sqlite3
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from logger_config import setup_logging

# Import existing DB manager
try:
    from catalog_db_manager import CatalogDatabaseManager
except ImportError:
    # Fallback if import fails
    CatalogDatabaseManager = None

logger = setup_logging(__name__)


class DatabaseManager:
    """
    Unified database manager for workflows
    
    Provides access to:
    - products table (main product database)
    - catalog_products table (catalog baseline)
    - catalog_baselines table (baseline metadata)
    - assessment_queue table (human review queue)
    """
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.path.join(os.path.dirname(__file__), 'products.db')
        
        self.db_path = db_path
        
        # Try to use catalog DB manager if available
        if CatalogDatabaseManager:
            try:
                self.catalog_db = CatalogDatabaseManager(db_path)
                logger.debug("Using CatalogDatabaseManager")
            except:
                self.catalog_db = None
                logger.warning("Could not initialize CatalogDatabaseManager, using direct SQL")
        else:
            self.catalog_db = None
        
        logger.info(f"✅ Database Manager initialized: {db_path}")
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    # =================== PRODUCT QUERIES (for Product Updater) ===================
    
    async def get_product_by_url(self, url: str) -> Optional[Dict]:
        """Get product by URL from products table"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM products WHERE url = ?
            ''', (url,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return dict(row)
            return None
            
        except Exception as e:
            logger.error(f"Failed to get product by URL: {e}")
            return None
    
    async def query_products(
        self,
        retailer: Optional[str] = None,
        modesty_status: Optional[str] = None,
        has_shopify_id: bool = False,
        min_age_days: Optional[int] = None,
        sale_status: Optional[str] = None,
        stock_status: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """Query products from products table with filters (async wrapper for sync DB)"""
        import asyncio
        
        def _query():
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                
                query = 'SELECT * FROM products WHERE 1=1'
                params = []
                
                if retailer:
                    query += ' AND retailer = ?'
                    params.append(retailer)
                
                if modesty_status:
                    query += ' AND modesty_status = ?'
                    params.append(modesty_status)
                
                if has_shopify_id:
                    query += ' AND shopify_id IS NOT NULL'
                
                if sale_status:
                    query += ' AND sale_status = ?'
                    params.append(sale_status)
                
                if stock_status:
                    query += ' AND stock_status = ?'
                    params.append(stock_status)
                
                if min_age_days:
                    query += ' AND julianday("now") - julianday(last_updated) > ?'
                    params.append(min_age_days)
                
                query += f' ORDER BY last_updated ASC LIMIT ?'
                params.append(limit)
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                conn.close()
                
                return [dict(row) for row in rows]
                
            except Exception as e:
                logger.error(f"Failed to query products: {e}")
                return []
        
        return await asyncio.to_thread(_query)
    
    async def update_product_record(
        self,
        url: str,
        product_data: Dict,
        last_updated: Optional[datetime] = None
    ) -> bool:
        """Update product record in products table"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            if last_updated is None:
                last_updated = datetime.utcnow()
            
            # Update fields
            cursor.execute('''
                UPDATE products 
                SET title = ?,
                    price = ?,
                    sale_status = ?,
                    stock_status = ?,
                    last_updated = ?
                WHERE url = ?
            ''', (
                product_data.get('title'),
                product_data.get('price'),
                product_data.get('sale_status', 'regular'),
                product_data.get('stock_status', 'in_stock'),
                last_updated.isoformat(),
                url
            ))
            
            conn.commit()
            affected = cursor.rowcount
            conn.close()
            
            return affected > 0
            
        except Exception as e:
            logger.error(f"Failed to update product record: {e}")
            return False
    
    async def save_product(
        self,
        url: str,
        retailer: str,
        product_data: Dict,
        shopify_id: Optional[int] = None,
        modesty_status: Optional[str] = None,
        first_seen: Optional[datetime] = None
    ) -> bool:
        """Save new product to products table"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            if first_seen is None:
                first_seen = datetime.utcnow()
            
            cursor.execute('''
                INSERT INTO products 
                (url, retailer, title, price, brand, description, images, 
                 shopify_id, modesty_status, first_seen, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                url,
                retailer,
                product_data.get('title'),
                product_data.get('price'),
                product_data.get('brand'),
                product_data.get('description'),
                json.dumps(product_data.get('images', [])),
                shopify_id,
                modesty_status,
                first_seen.isoformat(),
                datetime.utcnow().isoformat()
            ))
            
            conn.commit()
            conn.close()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to save product: {e}")
            return False
    
    # =================== CATALOG OPERATIONS (for Catalog workflows) ===================
    
    async def create_catalog_baseline(
        self,
        retailer: str,
        category: str,
        modesty_level: str,
        products: List[Dict],
        catalog_url: str,
        scan_date: datetime
    ) -> str:
        """Create catalog baseline"""
        if self.catalog_db:
            # Use existing manager if available
            try:
                from datetime import date
                # Build crawl_config as expected by old create_baseline
                crawl_config = {
                    'catalog_url': catalog_url,
                    'extraction_method': 'markdown' if retailer in ['revolve', 'asos'] else 'patchright',
                    'crawl_pages': 1,
                    'crawl_depth_reached': 1,
                    'sort_by_newest_url': catalog_url,
                    'pagination_type': 'infinite_scroll' if retailer in ['revolve', 'asos'] else 'pagination',
                    'has_sort_by_newest': True,
                    'early_stop_threshold': 3
                }
                
                baseline_id = await self.catalog_db.create_baseline(
                    retailer=retailer,
                    category=category,
                    baseline_date=scan_date.date(),
                    total_products=len(products),
                    crawl_config=crawl_config
                )
                
                # Store products
                # TODO: Convert products to CatalogProduct format
                logger.info(f"Baseline created: {baseline_id}")
                return str(baseline_id)
                
            except Exception as e:
                logger.error(f"Failed to use catalog_db: {e}")
        
        # Fallback: direct SQL
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Create baseline record
            cursor.execute('''
                INSERT INTO catalog_baselines 
                (retailer, category, baseline_date, total_products_seen, catalog_url)
                VALUES (?, ?, ?, ?, ?)
            ''', (retailer, category, scan_date.date(), len(products), catalog_url))
            
            baseline_id = cursor.lastrowid
            
            # Store products
            for product in products:
                cursor.execute('''
                    INSERT INTO catalog_products 
                    (catalog_url, retailer, category, title, price, image_urls, 
                     discovered_date, discovery_run_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    product.get('url'),
                    retailer,
                    category,
                    product.get('title'),
                    product.get('price'),
                    json.dumps(product.get('images', [])),
                    scan_date.date(),
                    str(baseline_id)
                ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Baseline created (direct SQL): {baseline_id}")
            return str(baseline_id)
            
        except Exception as e:
            logger.error(f"Failed to create baseline: {e}")
            return None
    
    async def record_monitoring_run(
        self,
        retailer: str,
        category: str,
        modesty_level: str,
        products_scanned: int,
        new_found: int,
        duplicates: int,
        run_time: datetime
    ) -> bool:
        """Record catalog monitoring run"""
        if self.catalog_db:
            try:
                # Old create_monitoring_run generates run_id internally (doesn't accept it as param)
                run_id = await self.catalog_db.create_monitoring_run(
                    run_type='monitoring',
                    retailer=retailer,
                    category=category
                )
                
                await self.catalog_db.update_monitoring_run(run_id, {
                    'total_products_crawled': products_scanned,
                    'new_products_found': new_found,
                    'run_status': 'completed'
                })
                
                return True
                
            except Exception as e:
                logger.error(f"Failed to record monitoring run: {e}")
        
        return False
    
    # =================== DEDUPLICATION (for Catalog Monitor) ===================
    
    async def find_product_by_url(self, url: str, retailer: str) -> Optional[Dict]:
        """Find product by exact URL in products table"""
        return await self.get_product_by_url(url)
    
    async def find_product_by_normalized_url(self, normalized_url: str, retailer: str) -> Optional[Dict]:
        """Find product by normalized URL (async wrapper for sync DB)"""
        import asyncio
        
        def _query():
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT * FROM products 
                    WHERE retailer = ? AND url LIKE ?
                    LIMIT 1
                ''', (retailer, f"%{normalized_url}%"))
                
                row = cursor.fetchone()
                conn.close()
                
                if row:
                    return dict(row)
                return None
                
            except Exception as e:
                logger.error(f"Failed to find by normalized URL: {e}")
                return None
        
        return await asyncio.to_thread(_query)
    
    async def find_product_by_code(self, product_code: str, retailer: str) -> Optional[Dict]:
        """Find product by product code (async wrapper for sync DB)"""
        import asyncio
        
        def _query():
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                
                # Search in URL or product_code field
                cursor.execute('''
                    SELECT * FROM products 
                    WHERE retailer = ? AND (
                        url LIKE ? OR
                        product_code = ?
                    )
                    LIMIT 1
                ''', (retailer, f"%{product_code}%", product_code))
                
                row = cursor.fetchone()
                conn.close()
                
                if row:
                    return dict(row)
                return None
                
            except Exception as e:
                logger.error(f"Failed to find by product code: {e}")
                return None
        
        return await asyncio.to_thread(_query)
    
    async def find_product_by_title_price(
        self,
        title: str,
        price: str,
        retailer: str
    ) -> Optional[Dict]:
        """Find product by title and price (async wrapper for sync DB)"""
        import asyncio
        
        def _query():
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT * FROM products 
                    WHERE retailer = ? AND title = ? AND price = ?
                    LIMIT 1
                ''', (retailer, title, price))
                
                row = cursor.fetchone()
                conn.close()
                
                if row:
                    return dict(row)
                return None
                
            except Exception as e:
                logger.error(f"Failed to find by title/price: {e}")
                return None
        
        return await asyncio.to_thread(_query)
    
    async def find_products_by_retailer(self, retailer: str, limit: int = 1000) -> List[Dict]:
        """Find products by retailer"""
        return await self.query_products(retailer=retailer, limit=limit)
    
    async def find_product_by_image(self, image_url: str, retailer: str) -> Optional[Dict]:
        """Find product by image URL (async wrapper for sync DB)"""
        import asyncio
        
        def _query():
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT * FROM products 
                    WHERE retailer = ? AND images LIKE ?
                    LIMIT 1
                ''', (retailer, f"%{image_url}%"))
                
                row = cursor.fetchone()
                conn.close()
                
                if row:
                    return dict(row)
                return None
                
            except Exception as e:
                logger.error(f"Failed to find by image: {e}")
                return None
        
        return await asyncio.to_thread(_query)
    
    async def find_baseline_product_by_url(self, url: str, retailer: str) -> Optional[Dict]:
        """Find product in catalog baseline by URL (async)"""
        if not self.catalog_db:
            return None
            
        try:
            import aiosqlite
            await self.catalog_db._ensure_db_initialized()
            
            async with aiosqlite.connect(self.catalog_db.db_path) as conn:
                conn.row_factory = aiosqlite.Row
                cursor = await conn.execute('''
                    SELECT * FROM catalog_products 
                    WHERE retailer = ? AND catalog_url = ?
                    LIMIT 1
                ''', (retailer, url))
                
                row = await cursor.fetchone()
                
                if row:
                    return dict(row)
                return None
            
        except Exception as e:
            logger.error(f"Failed to find baseline product: {e}")
            return None
    
    async def find_baseline_product_by_code(self, product_code: str, retailer: str) -> Optional[Dict]:
        """Find product in catalog baseline by product code (async)"""
        if not self.catalog_db:
            return None
            
        try:
            import aiosqlite
            await self.catalog_db._ensure_db_initialized()
            
            async with aiosqlite.connect(self.catalog_db.db_path) as conn:
                conn.row_factory = aiosqlite.Row
                cursor = await conn.execute('''
                    SELECT * FROM catalog_products 
                    WHERE retailer = ? AND (
                        catalog_url LIKE ? OR
                        product_code = ?
                    )
                    LIMIT 1
                ''', (retailer, f"%{product_code}%", product_code))
                
                row = await cursor.fetchone()
                
                if row:
                    return dict(row)
                return None
            
        except Exception as e:
            logger.error(f"Failed to find baseline by code: {e}")
            return None
    
    async def find_baseline_product_by_title_price(
        self,
        title: str,
        price: str,
        retailer: str
    ) -> Optional[Dict]:
        """Find product in catalog baseline by title and price (async)"""
        if not self.catalog_db:
            return None
            
        try:
            import aiosqlite
            await self.catalog_db._ensure_db_initialized()
            
            async with aiosqlite.connect(self.catalog_db.db_path) as conn:
                conn.row_factory = aiosqlite.Row
                cursor = await conn.execute('''
                    SELECT * FROM catalog_products 
                    WHERE retailer = ? AND LOWER(title) = ? AND price = ?
                    LIMIT 1
                ''', (retailer, title.lower(), price))
                
                row = await cursor.fetchone()
                
                if row:
                    return dict(row)
                return None
            
        except Exception as e:
            logger.error(f"Failed to find baseline by title/price: {e}")
            return None


# Singleton instance
_db_manager = None

def get_db_manager(db_path: str = None) -> DatabaseManager:
    """Get singleton database manager instance"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager(db_path)
    return _db_manager

