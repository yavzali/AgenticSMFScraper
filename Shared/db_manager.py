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
import asyncio
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
            
            # Build update query dynamically to handle optional image tracking fields
            update_fields = [
                'title = ?',
                'price = ?',
                'sale_status = ?',
                'stock_status = ?',
                'last_updated = ?'
            ]
            update_values = [
                product_data.get('title'),
                product_data.get('price'),
                product_data.get('sale_status', 'regular'),
                product_data.get('stock_status', 'in_stock'),
                last_updated.isoformat()
            ]
            
            # Add image tracking fields if present
            if 'images_uploaded' in product_data:
                update_fields.append('images_uploaded = ?')
                update_values.append(product_data['images_uploaded'])
            
            if 'images_uploaded_at' in product_data:
                update_fields.append('images_uploaded_at = ?')
                update_values.append(product_data['images_uploaded_at'])
            
            if 'images_failed_count' in product_data:
                update_fields.append('images_failed_count = ?')
                update_values.append(product_data['images_failed_count'])
            
            if 'last_image_error' in product_data:
                update_fields.append('last_image_error = ?')
                update_values.append(product_data['last_image_error'])
            
            # Add URL for WHERE clause
            update_values.append(url)
            
            # Execute update
            cursor.execute(f'''
                UPDATE products 
                SET {', '.join(update_fields)}
                WHERE url = ?
            ''', tuple(update_values))
            
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
        first_seen: Optional[datetime] = None,
        shopify_status: Optional[str] = None,
        images_uploaded: Optional[int] = None,
        source: Optional[str] = None,
        assessment_status: Optional[str] = None
    ) -> bool:
        """
        Save new product to products table
        
        Args:
            shopify_status: 'not_uploaded', 'draft', or 'published'
            images_uploaded: 0 or 1 to track if images were successfully uploaded
            source: 'baseline_scan', 'monitor', or 'new_product_import'
            assessment_status: 'not_assessed', 'queued', 'assessed', or 'not_for_assessment'
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            if first_seen is None:
                first_seen = datetime.utcnow()
            
            # Determine shopify_status if not provided
            if shopify_status is None:
                if shopify_id:
                    # If shopify_id exists but status not specified, assume it's from product_data
                    shopify_status = product_data.get('shopify_status', 'draft')
                else:
                    shopify_status = 'not_uploaded'
            
            # Set images_uploaded based on whether images were provided
            if images_uploaded is None:
                # Auto-detect: if downloaded_images exist in product_data, assume success
                images_uploaded = 1 if product_data.get('downloaded_image_paths') else 0
            
            # Set assessment_status default based on source
            if assessment_status is None:
                if source == 'baseline_scan':
                    assessment_status = 'not_for_assessment'  # Baseline scans don't go to assessment
                else:
                    assessment_status = 'not_assessed'  # Monitor/import start as not_assessed
            
            cursor.execute('''
                INSERT INTO products 
                (url, retailer, title, price, brand, description, 
                 shopify_id, modesty_status, shopify_status, images_uploaded, 
                 images_uploaded_at, source, assessment_status, first_seen, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                url,
                retailer,
                product_data.get('title'),
                product_data.get('price'),
                product_data.get('brand'),
                product_data.get('description'),
                shopify_id,
                modesty_status,
                shopify_status,
                images_uploaded,
                datetime.utcnow().isoformat() if images_uploaded == 1 else None,
                source,
                assessment_status,
                first_seen.isoformat(),
                datetime.utcnow().isoformat()
            ))
            
            conn.commit()
            conn.close()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to save product: {e}")
            return False
    
    async def update_shopify_status(
        self,
        url: str,
        shopify_status: str
    ) -> bool:
        """
        Update just the shopify_status for a product
        
        Args:
            url: Product URL
            shopify_status: 'draft' or 'published'
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE products
                SET shopify_status = ?,
                    last_updated = ?
                WHERE url = ?
            ''', (
                shopify_status,
                datetime.utcnow().isoformat(),
                url
            ))
            
            conn.commit()
            affected = cursor.rowcount
            conn.close()
            
            if affected > 0:
                logger.debug(f"Updated shopify_status to '{shopify_status}' for {url}")
                return True
            else:
                logger.warning(f"No product found with URL: {url}")
                return False
            
        except Exception as e:
            logger.error(f"Failed to update shopify_status: {e}")
            return False
    
    async def update_last_checked(self, url: str) -> bool:
        """
        Update only the last_checked timestamp (no data changes)
        Used when product is extracted but no changes detected
        """
        def _update():
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                
                cursor.execute('''
                    UPDATE products 
                    SET last_checked = ?
                    WHERE url = ?
                ''', (datetime.utcnow().isoformat(), url))
                
                conn.commit()
                affected = cursor.rowcount
                conn.close()
                return affected > 0
            except Exception as e:
                logger.error(f"Failed to update last_checked: {e}")
                return False
        
        return await asyncio.to_thread(_update)
    
    async def mark_product_delisted(self, url: str) -> bool:
        """Mark product as delisted in database"""
        def _update():
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                
                cursor.execute('''
                    UPDATE products 
                    SET stock_status = 'delisted',
                        last_updated = ?,
                        last_checked = ?
                    WHERE url = ?
                ''', (
                    datetime.utcnow().isoformat(),
                    datetime.utcnow().isoformat(),
                    url
                ))
                
                conn.commit()
                affected = cursor.rowcount
                conn.close()
                return affected > 0
            except Exception as e:
                logger.error(f"Failed to mark product delisted: {e}")
                return False
        
        return await asyncio.to_thread(_update)
    
    async def batch_update_products(self, updates: List[Dict]) -> bool:
        """
        Batch update multiple products in a single transaction
        
        Args:
            updates: List of dicts with 'url', 'data', 'action'
        
        Returns:
            True if successful
        """
        def _batch_update():
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                
                # Begin transaction
                cursor.execute('BEGIN TRANSACTION')
                
                for update in updates:
                    url = update['url']
                    action = update['action']
                    data = update.get('data', {})
                    
                    if action == 'unchanged':
                        # Just update last_checked
                        cursor.execute('''
                            UPDATE products 
                            SET last_checked = ?
                            WHERE url = ?
                        ''', (datetime.utcnow().isoformat(), url))
                        
                    elif action == 'delisted':
                        # Mark as delisted
                        cursor.execute('''
                            UPDATE products 
                            SET stock_status = 'delisted',
                                last_updated = ?,
                                last_checked = ?
                            WHERE url = ?
                        ''', (
                            datetime.utcnow().isoformat(),
                            datetime.utcnow().isoformat(),
                            url
                        ))
                        
                    else:
                        # Full update - only update fields that are present and non-NULL
                        # This prevents overwriting valid data with NULL
                        update_fields = []
                        update_values = []
                        
                        # Always update timestamps
                        update_fields.extend(['last_updated = ?', 'last_checked = ?'])
                        update_values.extend([datetime.utcnow().isoformat(), datetime.utcnow().isoformat()])
                        
                        # Only update data fields if they are present and non-NULL
                        if data.get('title'):
                            update_fields.append('title = ?')
                            update_values.append(data.get('title'))
                        
                        if data.get('price'):
                            update_fields.append('price = ?')
                            update_values.append(data.get('price'))
                        
                        # For these fields, allow the value even if empty string (but not None)
                        if 'sale_status' in data and data['sale_status'] is not None:
                            update_fields.append('sale_status = ?')
                            update_values.append(data.get('sale_status', 'regular'))
                        
                        if 'stock_status' in data and data['stock_status'] is not None:
                            update_fields.append('stock_status = ?')
                            update_values.append(data.get('stock_status', 'in_stock'))
                        
                        # Only execute if we have fields to update (beyond timestamps)
                        if len(update_fields) > 2:
                            query = f"UPDATE products SET {', '.join(update_fields)} WHERE url = ?"
                            update_values.append(url)
                            cursor.execute(query, tuple(update_values))
                        else:
                            # Only update timestamps
                            cursor.execute('''
                                UPDATE products 
                                SET last_updated = ?, last_checked = ?
                                WHERE url = ?
                            ''', (datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), url))
                
                # Commit transaction
                conn.commit()
                conn.close()
                
                logger.debug(f"✅ Batch transaction committed: {len(updates)} updates")
                return True
                
            except Exception as e:
                logger.error(f"Batch transaction failed: {e}")
                if 'conn' in locals():
                    try:
                        conn.rollback()
                        conn.close()
                    except:
                        pass
                return False
        
        return await asyncio.to_thread(_batch_update)
    
    async def update_assessment_status(self, url: str, assessment_status: str) -> bool:
        """
        Update assessment_status for a product
        
        Args:
            url: Product URL
            assessment_status: 'not_assessed', 'queued', 'assessed', or 'not_for_assessment'
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE products 
                SET assessment_status = ?, last_updated = ?
                WHERE url = ?
            ''', (assessment_status, datetime.utcnow().isoformat(), url))
            
            conn.commit()
            conn.close()
            
            return cursor.rowcount > 0
            
        except Exception as e:
            logger.error(f"Failed to update assessment_status: {e}")
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
        """
        Find product by normalized URL (async wrapper for sync DB)
        
        Matches OLD ARCHITECTURE approach: strips query parameters from both sides
        """
        import asyncio
        import re
        
        def _query():
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                
                # Normalize the incoming URL (remove query params)
                # This matches old architecture: re.sub(r'\?.*', '', url)
                normalized_search = re.sub(r'\?.*', '', normalized_url).rstrip('/')
                
                # Use SQL to normalize URLs (much faster than Python loop!)
                # SUBSTR(url, 1, INSTR(url || '?', '?') - 1) extracts everything before first '?'
                cursor.execute('''
                    SELECT * FROM products 
                    WHERE retailer = ? 
                    AND RTRIM(SUBSTR(url, 1, INSTR(url || '?', '?') - 1), '/') = ?
                    LIMIT 1
                ''', (retailer, normalized_search))
                
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

