"""
Duplicate Detector - Handles database operations and sophisticated duplicate detection
"""

# Add shared path for imports
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../Shared"))
sys.path.append(os.path.dirname(__file__))

import os
import aiosqlite
import asyncio
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import difflib
import re

from logger_config import setup_logging

logger = setup_logging(__name__)

class DuplicateDetector:
    def __init__(self, db_path: str = None):
        if db_path is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(script_dir, '../Shared/products.db')
        self.db_path = db_path
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database with required tables"""
        try:
            # Check if we're already in an event loop
            try:
                loop = asyncio.get_running_loop()
                # If we're in a running loop, we can't use asyncio.run()
                # Instead, we'll defer initialization until first use
                self._db_initialized = False
                logger.info("Database initialization deferred (running in event loop)")
                return
            except RuntimeError:
                # No running loop, safe to use asyncio.run()
                asyncio.run(self._async_init_database())
                self._db_initialized = True
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            self._db_initialized = False
    
    async def _async_init_database(self):
        """Async database initialization"""
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                cursor = await conn.cursor()
                
                # Products table
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS products (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        product_code VARCHAR(100),
                        title VARCHAR(500),
                        url VARCHAR(1000) UNIQUE,
                        retailer VARCHAR(100),
                        brand VARCHAR(200),
                        price DECIMAL(10,2),
                        original_price DECIMAL(10,2),
                        clothing_type VARCHAR(100),
                        sale_status VARCHAR(50),
                        modesty_status VARCHAR(50),
                        stock_status VARCHAR(50),
                        shopify_id INTEGER,
                        shopify_variant_id INTEGER,
                        first_seen TIMESTAMP,
                        last_seen TIMESTAMP,
                        last_updated TIMESTAMP,
                        scraping_method VARCHAR(50),
                        status VARCHAR(50),
                        image_count INTEGER DEFAULT 0,
                        processing_notes TEXT,
                        neckline VARCHAR(50),
                        sleeve_length VARCHAR(50),
                        visual_analysis_confidence DECIMAL(3,2),
                        visual_analysis_source VARCHAR(50)
                    )
                """)
                
                # Create indexes for performance
                await cursor.execute("CREATE INDEX IF NOT EXISTS idx_url ON products(url)")
                await cursor.execute("CREATE INDEX IF NOT EXISTS idx_product_code ON products(product_code, retailer)")
                await cursor.execute("CREATE INDEX IF NOT EXISTS idx_brand_type ON products(brand, clothing_type)")
                await cursor.execute("CREATE INDEX IF NOT EXISTS idx_shopify ON products(shopify_id)")
                await cursor.execute("CREATE INDEX IF NOT EXISTS idx_last_updated ON products(last_updated)")
                
                await conn.commit()
                logger.info("Database initialized successfully")
        
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    async def _ensure_db_initialized(self):
        """Ensure database is initialized before use"""
        if not getattr(self, '_db_initialized', False):
            await self._async_init_database()
            self._db_initialized = True
    
    async def check_duplicate(self, url: str, retailer: str) -> Dict:
        """Check if URL or similar product already exists"""
        
        await self._ensure_db_initialized()
        
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                cursor = await conn.cursor()
                
                # 1. Exact URL match
                await cursor.execute("SELECT * FROM products WHERE url = ?", (url,))
                exact_match = await cursor.fetchone()
                
                if exact_match:
                    # Convert row to dict for named access
                    columns = [description[0] for description in cursor.description]
                    exact_match_dict = dict(zip(columns, exact_match))
                    
                    return {
                        'is_duplicate': True,
                        'action': 'update',
                        'existing_id': exact_match_dict['shopify_id'],
                        'match_type': 'exact_url',
                        'confidence': 1.0
                    }
                
                # 2. Extract product code from URL for code-based matching
                product_code = self._extract_product_code_from_url(url, retailer)
                
                if product_code:
                    await cursor.execute(
                        "SELECT * FROM products WHERE product_code = ? AND retailer = ?", 
                        (product_code, retailer)
                    )
                    code_match = await cursor.fetchone()
                    
                    if code_match:
                        # Convert row to dict for named access
                        columns = [description[0] for description in cursor.description]
                        code_match_dict = dict(zip(columns, code_match))
                        
                        return {
                            'is_duplicate': True,
                            'action': 'update',
                            'existing_id': code_match_dict['shopify_id'],
                            'match_type': 'product_code',
                            'confidence': 0.95
                        }
                
                # 3. URL similarity check (for variants)
                similar_urls = await self._find_similar_urls(cursor, url, retailer)
                
                if similar_urls:
                    # Convert first similar result to dict for named access
                    columns = [description[0] for description in cursor.description]
                    similar_match_dict = dict(zip(columns, similar_urls[0]))
                    
                    # Analyze if it's a size/color variant
                    variant_type = self._analyze_variant_type(url, similar_match_dict['url'])
                    
                    if variant_type == 'size_variant':
                        return {
                            'is_duplicate': True,
                            'action': 'add_variant',
                            'existing_id': similar_match_dict['shopify_id'],
                            'match_type': 'size_variant',
                            'confidence': 0.8
                        }
                    elif variant_type == 'color_variant':
                        return {
                            'is_duplicate': False,
                            'action': 'create_new',
                            'match_type': 'color_variant',
                            'confidence': 0.7
                        }
                    else:
                        return {
                            'is_duplicate': True,
                            'action': 'manual_review',
                            'existing_id': similar_match_dict['shopify_id'],
                            'match_type': 'uncertain_variant',
                            'confidence': 0.6
                        }
                
                # 4. No duplicates found
                return {
                    'is_duplicate': False,
                    'action': 'create_new',
                    'match_type': 'none',
                    'confidence': 0.0
                }
        
        except Exception as e:
            logger.error(f"Error checking duplicates for {url}: {e}")
            return {
                'is_duplicate': False,
                'action': 'create_new',
                'match_type': 'error',
                'confidence': 0.0
            }
    
    def _extract_product_code_from_url(self, url: str, retailer: str) -> Optional[str]:
        """Extract product code from URL using retailer-specific patterns"""
        
        patterns = {
            'aritzia': [
                r'/products/([a-z0-9-]+)/',
                r'/([a-z0-9-]+)-\d+\.html',
                r'product/([A-Z0-9]+)'
            ],
            'asos': [
                r'/prd/(\d+)',
                r'product-(\d+)',
                r'/(\d{7,})'
            ],
            'hm': [
                r'product\.([a-z0-9]+)',
                r'/([0-9]{10})',
                r'productpage\.([0-9]+)'
            ],
            'uniqlo': [
                r'/products/([A-Z0-9-]+)',
                r'product-detail/([A-Z0-9]+)',
                r'/([A-Z]{2}\d{4})'
            ],
            'revolve': [
                r'/dp/([A-Z0-9-]+)',
                r'product/([a-z0-9-]+)',
                r'/([A-Z]{4}\d{4})'
            ],
            'mango': [
                r'product/([a-z0-9-]+)',
                r'/(\d{8})',
                r'code-([A-Z0-9]+)'
            ],
            'anthropologie': [
                r'product/([a-z0-9-]+)',
                r'/([0-9]{8})',
                r'style-([A-Z0-9]+)'
            ],
            'abercrombie': [
                r'product/([a-z0-9-]+)',
                r'/(\d{6,8})',
                r'style-([A-Z0-9]+)'
            ],
            'nordstrom': [
                r'product/([a-z0-9-]+)',
                r'/(\d{7})',
                r'style-([A-Z0-9]+)'
            ],
            'urban_outfitters': [
                r'product/([a-z0-9-]+)',
                r'/(\d{8})',
                r'style-([A-Z0-9]+)'
            ]
        }
        
        retailer_patterns = patterns.get(retailer, patterns['asos'])  # Default to ASOS patterns
        
        for pattern in retailer_patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    async def _find_similar_urls(self, cursor, url: str, retailer: str, threshold: float = 0.8) -> List:
        """Find URLs with high similarity scores - smart comparison based on retailer"""
        
        await cursor.execute(
            "SELECT * FROM products WHERE retailer = ? ORDER BY last_updated DESC LIMIT 100",
            (retailer,)
        )
        
        recent_products = await cursor.fetchall()
        similar_urls = []
        
        # For Revolve, strip query params because they use identical filter strings in batch URLs
        # For other retailers, keep full URL comparison for better variant detection
        if retailer.lower() == 'revolve':
            # Extract base URL without query parameters
            url_base = url.split('?')[0] if '?' in url else url
            
            for product in recent_products:
                existing_url = product[3]  # url column
                existing_url_base = existing_url.split('?')[0] if '?' in existing_url else existing_url
                
                # Compare only base URLs to avoid false positives from identical query strings
                similarity = difflib.SequenceMatcher(None, url_base, existing_url_base).ratio()
                
                if similarity >= threshold:
                    similar_urls.append(product)
            
            # Sort by similarity (highest first)
            similar_urls.sort(key=lambda x: difflib.SequenceMatcher(None, url_base, x[3].split('?')[0] if '?' in x[3] else x[3]).ratio(), reverse=True)
        else:
            # Original logic for other retailers - full URL comparison for better variant detection
            for product in recent_products:
                existing_url = product[3]  # url column
                similarity = difflib.SequenceMatcher(None, url, existing_url).ratio()
                
                if similarity >= threshold:
                    similar_urls.append(product)
            
            # Sort by similarity (highest first)
            similar_urls.sort(key=lambda x: difflib.SequenceMatcher(None, url, x[3]).ratio(), reverse=True)
        
        return similar_urls[:3]  # Return top 3 most similar
    
    def _analyze_variant_type(self, new_url: str, existing_url: str) -> str:
        """Analyze if URLs represent size vs color variants"""
        
        # Size indicators
        size_keywords = [
            'xs', 's', 'm', 'l', 'xl', 'xxl', 'small', 'medium', 'large',
            'size-', '/s/', '/m/', '/l/', 'petite', 'plus'
        ]
        
        # Color indicators  
        color_keywords = [
            'black', 'white', 'blue', 'red', 'green', 'yellow', 'pink', 'purple',
            'navy', 'cream', 'beige', 'brown', 'grey', 'gray', 'color-', '/black/', '/white/'
        ]
        
        new_url_lower = new_url.lower()
        existing_url_lower = existing_url.lower()
        
        # Check for size differences
        new_has_size = any(keyword in new_url_lower for keyword in size_keywords)
        existing_has_size = any(keyword in existing_url_lower for keyword in size_keywords)
        
        # Check for color differences
        new_has_color = any(keyword in new_url_lower for keyword in color_keywords)
        existing_has_color = any(keyword in existing_url_lower for keyword in color_keywords)
        
        # Logic for variant detection
        if new_has_size and existing_has_size and not (new_has_color or existing_has_color):
            return 'size_variant'
        elif new_has_color and existing_has_color and not (new_has_size and existing_has_size):
            return 'color_variant'
        elif (new_has_size or existing_has_size) and not (new_has_color or existing_has_color):
            return 'size_variant'
        elif (new_has_color or existing_has_color) and not (new_has_size or existing_has_size):
            return 'color_variant'
        else:
            return 'uncertain'
    
    async def store_product(self, **product_data) -> bool:
        """Store a new product in the database"""
        
        await self._ensure_db_initialized()
        
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                cursor = await conn.cursor()
                
                now = datetime.utcnow().isoformat()
                
                await cursor.execute("""
                    INSERT INTO products (
                        product_code, title, url, retailer, brand, price, original_price,
                        clothing_type, sale_status, modesty_status, stock_status,
                        shopify_id, shopify_variant_id, first_seen, last_seen, last_updated,
                        scraping_method, status, image_count, processing_notes,
                        neckline, sleeve_length, visual_analysis_confidence, visual_analysis_source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    product_data.get('product_code'),
                    product_data.get('title'),
                    product_data.get('url'),
                    product_data.get('retailer'),
                    product_data.get('brand'),
                    product_data.get('price'),
                    product_data.get('original_price'),
                    product_data.get('clothing_type'),
                    product_data.get('sale_status'),
                    product_data.get('modesty_status'),
                    product_data.get('stock_status'),
                    product_data.get('shopify_id'),
                    product_data.get('shopify_variant_id'),
                    now,  # first_seen
                    now,  # last_seen
                    now,  # last_updated
                    product_data.get('scraping_method'),
                    'active',  # status
                    product_data.get('image_count', 0),
                    product_data.get('processing_notes'),
                    product_data.get('neckline'),
                    product_data.get('sleeve_length'),
                    product_data.get('visual_analysis_confidence'),
                    product_data.get('visual_analysis_source')
                ))
                
                await conn.commit()
                logger.debug(f"Stored product: {product_data.get('url')}")
                return True
        
        except Exception as e:
            logger.error(f"Failed to store product: {e}")
            return False
    
    async def update_product(self, shopify_id: int, **update_data) -> bool:
        """Update existing product in database"""
        
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                cursor = await conn.cursor()
                
                now = datetime.utcnow().isoformat()
                
                # Build dynamic update query
                update_fields = []
                values = []
                
                for field, value in update_data.items():
                    if field in ['price', 'original_price', 'sale_status', 'stock_status']:
                        update_fields.append(f"{field} = ?")
                        values.append(value)
                
                update_fields.append("last_seen = ?")
                update_fields.append("last_updated = ?")
                values.extend([now, now])
                values.append(shopify_id)
                
                query = f"UPDATE products SET {', '.join(update_fields)} WHERE shopify_id = ?"
                
                await cursor.execute(query, values)
                await conn.commit()
                
                logger.debug(f"Updated product: {shopify_id}")
                return True
        
        except Exception as e:
            logger.error(f"Failed to update product {shopify_id}: {e}")
            return False
    
    async def get_product_by_shopify_id(self, shopify_id: int) -> Optional[Dict]:
        """Get product by Shopify ID"""
        
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                cursor = await conn.cursor()
                await cursor.execute("SELECT * FROM products WHERE shopify_id = ?", (shopify_id,))
                row = await cursor.fetchone()
                
                if row:
                    # Convert to dictionary
                    columns = [description[0] for description in cursor.description]
                    return dict(zip(columns, row))
                
                return None
        
        except Exception as e:
            logger.error(f"Failed to get product {shopify_id}: {e}")
            return None
    
    async def get_statistics(self) -> Dict:
        """Get database statistics"""
        
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                cursor = await conn.cursor()
                
                # Total products
                await cursor.execute("SELECT COUNT(*) FROM products")
                total_result = await cursor.fetchone()
                total_products = total_result[0] if total_result else 0
                
                # Products by retailer
                await cursor.execute("SELECT retailer, COUNT(*) FROM products GROUP BY retailer")
                retailer_results = await cursor.fetchall()
                by_retailer = dict(retailer_results) if retailer_results else {}
                
                # Products by modesty level
                await cursor.execute("SELECT modesty_status, COUNT(*) FROM products GROUP BY modesty_status")
                modesty_results = await cursor.fetchall()
                by_modesty = dict(modesty_results) if modesty_results else {}
                
                # Recent activity (last 7 days)
                await cursor.execute("""
                    SELECT COUNT(*) FROM products 
                    WHERE last_updated >= datetime('now', '-7 days')
                """)
                recent_result = await cursor.fetchone()
                recent_activity = recent_result[0] if recent_result else 0
                
                return {
                    'total_products': total_products,
                    'by_retailer': by_retailer,
                    'by_modesty': by_modesty,
                    'recent_activity': recent_activity
                }
        
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {
                'total_products': 0,
                'by_retailer': {},
                'by_modesty': {},
                'recent_activity': 0
            }
    
    async def update_existing_product(self, existing_id: int, **product_data) -> bool:
        """Update existing product in database - helper method for Product Updater"""
        
        await self._ensure_db_initialized()
        
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                cursor = await conn.cursor()
                
                now = datetime.utcnow().isoformat()
                
                await cursor.execute("""
                    UPDATE products SET
                        title = ?, price = ?, original_price = ?, sale_status = ?, 
                        stock_status = ?, last_updated = ?, scraping_method = ?,
                        neckline = ?, sleeve_length = ?, visual_analysis_confidence = ?,
                        visual_analysis_source = ?
                    WHERE shopify_id = ?
                """, (
                    product_data.get('title'),
                    product_data.get('price'),
                    product_data.get('original_price'),
                    product_data.get('sale_status'),
                    product_data.get('stock_status'),
                    now,
                    product_data.get('scraping_method'),
                    product_data.get('neckline'),
                    product_data.get('sleeve_length'),
                    product_data.get('visual_analysis_confidence'),
                    product_data.get('visual_analysis_source'),
                    existing_id
                ))
                
                await conn.commit()
                logger.debug(f"Updated existing product: {existing_id}")
                return True
        
        except Exception as e:
            logger.error(f"Failed to update existing product {existing_id}: {e}")
            return False
    
    async def cleanup_old_records(self, days: int = 90):
        """Clean up old inactive records"""
        
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                cursor = await conn.cursor()
                
                # First, count how many records will be deleted
                await cursor.execute("""
                    SELECT COUNT(*) FROM products 
                    WHERE status = 'inactive' 
                    AND last_updated < datetime('now', '-{} days')
                """.format(days))
                
                count_result = await cursor.fetchone()
                deleted_count = count_result[0] if count_result else 0
                
                # Now delete the records
                await cursor.execute("""
                    DELETE FROM products 
                    WHERE status = 'inactive' 
                    AND last_updated < datetime('now', '-{} days')
                """.format(days))
                
                await conn.commit()
                
                logger.info(f"Cleaned up {deleted_count} old records")
                return deleted_count
        
        except Exception as e:
            logger.error(f"Failed to cleanup old records: {e}")
            return 0