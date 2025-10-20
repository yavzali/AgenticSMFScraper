"""
Catalog Database Manager - Handles all catalog-specific database operations
Extends existing duplicate_detector functionality with catalog monitoring features
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
import uuid
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, date
from dataclasses import dataclass
import difflib
import re

from logger_config import setup_logging

logger = setup_logging(__name__)

@dataclass
class CatalogProduct:
    """Data structure for catalog-discovered products"""
    catalog_url: str
    retailer: str
    category: str
    title: Optional[str] = None
    price: Optional[float] = None
    original_price: Optional[float] = None
    sale_status: Optional[str] = None
    image_urls: Optional[List[str]] = None
    availability: Optional[str] = None
    product_code: Optional[str] = None
    normalized_url: Optional[str] = None
    discovered_date: Optional[date] = None
    extraction_method: Optional[str] = None

@dataclass
class MatchResult:
    """Result of new product detection"""
    is_new_product: bool
    confidence_score: float
    match_type: str
    existing_product_id: Optional[int] = None
    similarity_details: Optional[Dict] = None

class CatalogDatabaseManager:
    """
    Manages all catalog monitoring database operations
    Integrates with existing products.db and extends duplicate detection
    """
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(script_dir, '../Shared/products.db')
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize catalog extensions to existing database"""
        try:
            # Check if we're already in an event loop
            try:
                loop = asyncio.get_running_loop()
                self._db_initialized = False
                logger.info("Catalog database initialization deferred (running in event loop)")
                return
            except RuntimeError:
                # No running loop, safe to use asyncio.run()
                asyncio.run(self._async_init_database())
                self._db_initialized = True
        except Exception as e:
            logger.error(f"Catalog database initialization failed: {e}")
            self._db_initialized = False
    
    async def _async_init_database(self):
        """Initialize catalog tables in existing products.db"""
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                # Read and execute the schema
                schema_file = os.path.join(os.path.dirname(__file__), 'catalog_schema.sql')
                if os.path.exists(schema_file):
                    with open(schema_file, 'r') as f:
                        schema_sql = f.read()
                    await conn.executescript(schema_sql)
                else:
                    # Inline schema if file doesn't exist
                    await self._create_catalog_tables(conn)
                
                await conn.commit()
                logger.info("Catalog database extensions initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize catalog database: {e}")
            raise
    
    async def _create_catalog_tables(self, conn):
        """Create catalog tables inline"""
        # This contains the same SQL from the schema artifact
        # Including here for reliability
        tables_sql = """
        -- Catalog Products Table
        CREATE TABLE IF NOT EXISTS catalog_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_code VARCHAR(100),
            catalog_url VARCHAR(1000) NOT NULL,
            normalized_url VARCHAR(1000),
            retailer VARCHAR(100) NOT NULL,
            category VARCHAR(100) NOT NULL,
            title VARCHAR(500),
            price DECIMAL(10,2),
            original_price DECIMAL(10,2),
            sale_status VARCHAR(50),
            image_urls TEXT,
            availability VARCHAR(50),
            discovered_date DATE NOT NULL,
            discovery_run_id VARCHAR(100),
            extraction_method VARCHAR(50),
            review_status VARCHAR(50) DEFAULT 'pending',
            review_type VARCHAR(50) DEFAULT 'modesty_assessment',
            reviewed_by VARCHAR(100),
            reviewed_date TIMESTAMP,
            review_notes TEXT,
            is_new_product BOOLEAN DEFAULT 1,
            similarity_matches TEXT,
            confidence_score DECIMAL(3,2),
            approved_for_scraping BOOLEAN DEFAULT 0,
            batch_created BOOLEAN DEFAULT 0,
            batch_file VARCHAR(200),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Catalog Baselines Table
        CREATE TABLE IF NOT EXISTS catalog_baselines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            retailer VARCHAR(100) NOT NULL,
            category VARCHAR(100) NOT NULL,
            baseline_date DATE NOT NULL,
            total_products_seen INTEGER NOT NULL,
            crawl_pages INTEGER,
            crawl_depth_reached VARCHAR(100),
            extraction_method VARCHAR(50),
            catalog_url VARCHAR(1000),
            sort_by_newest_url VARCHAR(1000),
            pagination_type VARCHAR(50),
            has_sort_by_newest BOOLEAN DEFAULT 1,
            early_stop_threshold INTEGER DEFAULT 5,
            baseline_status VARCHAR(50) DEFAULT 'active',
            last_validated TIMESTAMP,
            validation_notes TEXT,
            baseline_crawl_time DECIMAL(8,2),
            avg_products_per_page DECIMAL(5,1),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(retailer, category, baseline_date)
        );
        
        -- Monitoring Runs Table
        CREATE TABLE IF NOT EXISTS catalog_monitoring_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id VARCHAR(100) UNIQUE NOT NULL,
            run_type VARCHAR(50) NOT NULL,
            retailer VARCHAR(100),
            category VARCHAR(100),
            scheduled_time TIMESTAMP,
            actual_start_time TIMESTAMP,
            crawl_strategy VARCHAR(50),
            max_pages INTEGER,
            early_stop_enabled BOOLEAN DEFAULT 1,
            total_products_crawled INTEGER DEFAULT 0,
            new_products_found INTEGER DEFAULT 0,
            existing_products_encountered INTEGER DEFAULT 0,
            pages_crawled INTEGER DEFAULT 0,
            total_runtime DECIMAL(8,2),
            avg_time_per_page DECIMAL(5,2),
            api_calls_made INTEGER DEFAULT 0,
            total_cost DECIMAL(8,4),
            run_status VARCHAR(50),
            error_count INTEGER DEFAULT 0,
            completion_percentage DECIMAL(5,2),
            products_for_review INTEGER DEFAULT 0,
            batch_files_created TEXT,
            completed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Errors Table
        CREATE TABLE IF NOT EXISTS catalog_errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id VARCHAR(100),
            retailer VARCHAR(100),
            category VARCHAR(100),
            crawler_type VARCHAR(50),
            error_type VARCHAR(100),
            error_message TEXT,
            error_traceback TEXT,
            url_attempted VARCHAR(1000),
            page_number INTEGER,
            retry_attempt INTEGER DEFAULT 1,
            severity VARCHAR(50),
            impact_on_run VARCHAR(100),
            resolved BOOLEAN DEFAULT 0,
            resolution_notes TEXT,
            occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP
        );
        """
        
        await conn.executescript(tables_sql)
        
        # Create indexes
        indexes_sql = """
        CREATE INDEX IF NOT EXISTS idx_catalog_products_retailer_category ON catalog_products(retailer, category);
        CREATE INDEX IF NOT EXISTS idx_catalog_products_discovery_run ON catalog_products(discovery_run_id);
        CREATE INDEX IF NOT EXISTS idx_catalog_products_review_status ON catalog_products(review_status);
        CREATE INDEX IF NOT EXISTS idx_catalog_products_normalized_url ON catalog_products(normalized_url);
        CREATE INDEX IF NOT EXISTS idx_catalog_products_product_code ON catalog_products(product_code, retailer);
        CREATE INDEX IF NOT EXISTS idx_catalog_baselines_retailer_category ON catalog_baselines(retailer, category);
        CREATE INDEX IF NOT EXISTS idx_catalog_runs_run_id ON catalog_monitoring_runs(run_id);
        """
        
        await conn.executescript(indexes_sql)
    
    async def _ensure_db_initialized(self):
        """Ensure database is initialized before use"""
        if not getattr(self, '_db_initialized', False):
            await self._async_init_database()
            self._db_initialized = True
    
    # =================== BASELINE MANAGEMENT ===================
    
    async def create_baseline(self, retailer: str, category: str, baseline_date: date,
                            total_products: int, crawl_config: Dict) -> str:
        """Create a new catalog baseline"""
        await self._ensure_db_initialized()
        
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                baseline_id = str(uuid.uuid4())[:8]
                
                await conn.execute("""
                    INSERT INTO catalog_baselines (
                        retailer, category, baseline_date, total_products_seen,
                        crawl_pages, crawl_depth_reached, extraction_method,
                        catalog_url, sort_by_newest_url, pagination_type,
                        has_sort_by_newest, early_stop_threshold, baseline_crawl_time
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    retailer, category, baseline_date, total_products,
                    crawl_config.get('crawl_pages'),
                    crawl_config.get('crawl_depth_reached'),
                    crawl_config.get('extraction_method'),
                    crawl_config.get('catalog_url'),
                    crawl_config.get('sort_by_newest_url'),
                    crawl_config.get('pagination_type'),
                    crawl_config.get('has_sort_by_newest', True),
                    crawl_config.get('early_stop_threshold', 3),
                    crawl_config.get('baseline_crawl_time')
                ))
                
                await conn.commit()
                logger.info(f"Created baseline for {retailer} {category}: {total_products} products")
                return baseline_id
                
        except Exception as e:
            logger.error(f"Failed to create baseline for {retailer} {category}: {e}")
            raise
    
    async def get_active_baseline(self, retailer: str, category: str) -> Optional[Dict]:
        """Get active baseline for retailer/category"""
        await self._ensure_db_initialized()
        
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                cursor = await conn.cursor()
                await cursor.execute("""
                    SELECT * FROM catalog_baselines 
                    WHERE retailer = ? AND category = ? AND baseline_status = 'active'
                    ORDER BY baseline_date DESC LIMIT 1
                """, (retailer, category))
                
                row = await cursor.fetchone()
                if row:
                    columns = [desc[0] for desc in cursor.description]
                    return dict(zip(columns, row))
                return None
                
        except Exception as e:
            logger.error(f"Failed to get baseline for {retailer} {category}: {e}")
            return None
    
    async def store_baseline_products(self, products: List[CatalogProduct], 
                                    run_id: str) -> int:
        """Store baseline products (all products seen, including immodest)"""
        await self._ensure_db_initialized()
        
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                stored_count = 0
                
                for product in products:
                    # For baseline products, is_new_product = 0
                    await conn.execute("""
                        INSERT INTO catalog_products (
                            catalog_url, normalized_url, retailer, category,
                            title, price, original_price, sale_status, image_urls,
                            availability, product_code, discovered_date,
                            discovery_run_id, extraction_method, is_new_product,
                            review_status, review_type
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        product.catalog_url,
                        product.normalized_url,
                        product.retailer,
                        product.category,
                        product.title,
                        product.price,
                        product.original_price,
                        product.sale_status,
                        json.dumps(product.image_urls) if product.image_urls else None,
                        product.availability,
                        product.product_code,
                        product.discovered_date,
                        run_id,
                        product.extraction_method,
                        0,  # baseline products are not new
                        'baseline',  # special status for baseline products
                        'modesty_assessment'  # default review type
                    ))
                    stored_count += 1
                
                await conn.commit()
                logger.info(f"Stored {stored_count} baseline products for run {run_id}")
                return stored_count
                
        except Exception as e:
            logger.error(f"Failed to store baseline products: {e}")
            raise
    
    # =================== NEW PRODUCT DETECTION ===================
    
    async def detect_new_products(self, products: List[CatalogProduct], 
                                retailer: str, category: str) -> List[Tuple[CatalogProduct, MatchResult]]:
        """
        Detect which products are truly new using comprehensive matching
        Returns list of (product, match_result) tuples
        """
        await self._ensure_db_initialized()
        
        results = []
        
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                for product in products:
                    match_result = await self._comprehensive_product_matching(
                        conn, product, retailer, category)
                    results.append((product, match_result))
                    
                    # Log detection results
                    if match_result.is_new_product:
                        logger.info(f"NEW PRODUCT detected: {product.title[:50]}... "
                                  f"(confidence: {match_result.confidence_score:.2f})")
                    else:
                        logger.debug(f"Existing product found: {product.title[:50]}... "
                                   f"(match: {match_result.match_type})")
        
        except Exception as e:
            logger.error(f"Failed to detect new products: {e}")
            raise
        
        return results
    
    async def _comprehensive_product_matching(self, conn, product: CatalogProduct, 
                                            retailer: str, category: str) -> MatchResult:
        """
        Multi-factor matching: URL + Product ID + Title + Price + Images
        Returns confidence-scored match result
        """
        cursor = await conn.cursor()
        
        # 1. EXACT URL MATCH (highest confidence)
        await cursor.execute("""
            SELECT id, url, title, price FROM products 
            WHERE url = ? AND retailer = ?
        """, (product.catalog_url, retailer))
        exact_match = await cursor.fetchone()
        
        if exact_match:
            return MatchResult(
                is_new_product=False,
                confidence_score=1.0,
                match_type='exact_url',
                existing_product_id=exact_match[0]
            )
        
        # 2. NORMALIZED URL MATCH
        normalized_url = self._normalize_product_url(product.catalog_url, retailer)
        if normalized_url and normalized_url != product.catalog_url:
            await cursor.execute("""
                SELECT id, url, title, price FROM products 
                WHERE url LIKE ? AND retailer = ?
            """, (f"%{normalized_url.split('/')[-1]}%", retailer))
            url_matches = await cursor.fetchall()
            
            for match in url_matches:
                if self._urls_are_similar(normalized_url, match[1], retailer):
                    return MatchResult(
                        is_new_product=False,
                        confidence_score=0.95,
                        match_type='normalized_url',
                        existing_product_id=match[0]
                    )
        
        # 3. PRODUCT CODE MATCH
        if product.product_code:
            await cursor.execute("""
                SELECT id, url, title, price FROM products 
                WHERE product_code = ? AND retailer = ?
            """, (product.product_code, retailer))
            code_match = await cursor.fetchone()
            
            if code_match:
                return MatchResult(
                    is_new_product=False,
                    confidence_score=0.93,
                    match_type='product_code',
                    existing_product_id=code_match[0]
                )
        
        # 4. TITLE + PRICE MATCH (for variations)
        if product.title and product.price:
            await cursor.execute("""
                SELECT id, url, title, price FROM products 
                WHERE retailer = ? AND ABS(price - ?) < 0.01
            """, (retailer, product.price))
            price_matches = await cursor.fetchall()
            
            for match in price_matches:
                title_similarity = difflib.SequenceMatcher(
                    None, product.title.lower(), match[2].lower()).ratio()
                
                if title_similarity > 0.85:  # High title similarity
                    confidence = 0.80 + (title_similarity - 0.85) * 0.8  # Scale 0.80-0.88
                    return MatchResult(
                        is_new_product=False,
                        confidence_score=min(confidence, 0.88),
                        match_type='title_price',
                        existing_product_id=match[0],
                        similarity_details={'title_similarity': title_similarity}
                    )
        
        # 5. IMAGE URL MATCH (if available)
        if product.image_urls:
            # Check for similar image URLs in existing products
            await cursor.execute("""
                SELECT id, url, title, price FROM products 
                WHERE retailer = ? AND image_count > 0
            """, (retailer,))
            
            products_with_images = await cursor.fetchall()
            # Note: This would require extending the existing products table
            # to store image URLs for comparison. For now, we'll skip this
            # and implement it when we extend the main products schema.
        
        # 6. CHECK CATALOG BASELINE (including immodest products)
        await cursor.execute("""
            SELECT id, catalog_url, title, price FROM catalog_products 
            WHERE retailer = ? AND category = ? AND review_status = 'baseline'
        """, (retailer, category))
        baseline_products = await cursor.fetchall()
        
        for baseline_product in baseline_products:
            # Check URL similarity against baseline
            if self._urls_are_similar(product.catalog_url, baseline_product[1], retailer):
                return MatchResult(
                    is_new_product=False,
                    confidence_score=0.90,
                    match_type='baseline_url',
                    existing_product_id=baseline_product[0]
                )
            
            # Check title similarity against baseline
            if product.title and baseline_product[2]:
                title_similarity = difflib.SequenceMatcher(
                    None, product.title.lower(), baseline_product[2].lower()).ratio()
                
                if title_similarity > 0.90:
                    return MatchResult(
                        is_new_product=False,
                        confidence_score=0.85,
                        match_type='baseline_title',
                        existing_product_id=baseline_product[0]
                    )
        
        # If we get here, it's likely a new product
        return MatchResult(
            is_new_product=True,
            confidence_score=0.95,  # High confidence it's new
            match_type='no_match_found'
        )
    
    def _normalize_product_url(self, url: str, retailer: str) -> str:
        """Normalize URLs for better matching"""
        # Remove tracking parameters
        tracking_params = ['navsrc', 'origin', 'breadcrumb', 'pagefm', 'src', 'pos', 
                          'campaign', 'utm_source', 'utm_medium', 'utm_campaign']
        
        normalized = url
        for param in tracking_params:
            normalized = re.sub(f'[?&]{param}=[^&]*', '', normalized)
        
        # Retailer-specific normalization
        if retailer == 'revolve':
            # Keep core product URL, remove navigation tracking
            normalized = re.sub(r'\?.*', '', normalized)
        elif retailer == 'asos':
            # Remove price filters and sort parameters
            normalized = re.sub(r'[?&](currentpricerange|sort)=[^&]*', '', normalized)
        elif retailer == 'aritzia':
            # Keep only essential product identifiers
            normalized = re.sub(r'\?.*', '', normalized)
        
        return normalized.rstrip('?&')
    
    def _urls_are_similar(self, url1: str, url2: str, retailer: str) -> bool:
        """Check if two URLs represent the same product"""
        # Extract product identifiers based on retailer patterns
        PRODUCT_ID_PATTERNS = {
            'revolve': r'/([A-Z0-9-]+)\.html',
            'asos': r'/prd/(\d+)',
            'aritzia': r'/product/[^/]+/(\d+)\.html',
            'hm': r'productpage\.(\d+)\.html',
            'uniqlo': r'/products/([A-Z0-9]+)-',
            'anthropologie': r'/products/([^?]+)',
            'abercrombie': r'/products/([^?]+)',
            'nordstrom': r'/s/([^?]+)',
            'urban_outfitters': r'/products/([^?]+)',
            'mango': r'/([0-9]+)\.html'
        }
        
        pattern = PRODUCT_ID_PATTERNS.get(retailer)
        if pattern:
            match1 = re.search(pattern, url1)
            match2 = re.search(pattern, url2)
            
            if match1 and match2:
                return match1.group(1) == match2.group(1)
        
        # Fallback: basic URL similarity
        return difflib.SequenceMatcher(None, url1, url2).ratio() > 0.85
    
    # =================== CATALOG PRODUCT STORAGE ===================
    
    async def store_new_products(self, products_with_results: List[Tuple[CatalogProduct, MatchResult]], 
                               run_id: str) -> int:
        """Store newly discovered products for review"""
        await self._ensure_db_initialized()
        
        new_products_stored = 0
        
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                for product, match_result in products_with_results:
                    if match_result.is_new_product:
                        # Store for modesty review
                        # Determine review_type based on confidence score
                        review_type = 'modesty_assessment'  # Default for high confidence new products
                        if 0.70 <= match_result.confidence_score <= 0.85:
                            review_type = 'duplicate_uncertain'  # Uncertain duplicates
                        
                        await conn.execute("""
                            INSERT INTO catalog_products (
                                catalog_url, normalized_url, retailer, category,
                                title, price, original_price, sale_status, image_urls,
                                availability, product_code, discovered_date,
                                discovery_run_id, extraction_method, is_new_product,
                                confidence_score, similarity_matches, review_status, review_type
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            product.catalog_url,
                            product.normalized_url,
                            product.retailer,
                            product.category,
                            product.title,
                            product.price,
                            product.original_price,
                            product.sale_status,
                            json.dumps(product.image_urls) if product.image_urls else None,
                            product.availability,
                            product.product_code,
                            product.discovered_date,
                            run_id,
                            product.extraction_method,
                            1,  # is_new_product
                            match_result.confidence_score,
                            json.dumps(match_result.similarity_details) if match_result.similarity_details else None,
                            'pending',  # needs modesty review
                            review_type  # modesty_assessment or duplicate_uncertain
                        ))
                        new_products_stored += 1
                
                await conn.commit()
                logger.info(f"Stored {new_products_stored} new products for review")
                return new_products_stored
                
        except Exception as e:
            logger.error(f"Failed to store new products: {e}")
            raise
    
    # =================== MONITORING RUN MANAGEMENT ===================
    
    async def create_monitoring_run(self, run_type: str, retailer: str = None, 
                                  category: str = None, config: Dict = None) -> str:
        """Create new monitoring run record"""
        await self._ensure_db_initialized()
        
        run_id = str(uuid.uuid4())
        
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                await conn.execute("""
                    INSERT INTO catalog_monitoring_runs (
                        run_id, run_type, retailer, category, scheduled_time,
                        actual_start_time, crawl_strategy, max_pages, early_stop_enabled,
                        run_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    run_id, run_type, retailer, category,
                    config.get('scheduled_time') if config else None,
                    datetime.utcnow(),
                    config.get('crawl_strategy', 'newest_first') if config else 'newest_first',
                    config.get('max_pages') if config else None,
                    config.get('early_stop_enabled', True) if config else True,
                    'running'
                ))
                
                await conn.commit()
                logger.info(f"Created monitoring run: {run_id} ({run_type})")
                return run_id
                
        except Exception as e:
            logger.error(f"Failed to create monitoring run: {e}")
            raise
    
    async def update_monitoring_run(self, run_id: str, updates: Dict):
        """Update monitoring run with progress/results"""
        await self._ensure_db_initialized()
        
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                # Build dynamic update query
                update_fields = []
                values = []
                
                for field, value in updates.items():
                    update_fields.append(f"{field} = ?")
                    values.append(value)
                
                if update_fields:
                    values.append(run_id)
                    query = f"UPDATE catalog_monitoring_runs SET {', '.join(update_fields)} WHERE run_id = ?"
                    await conn.execute(query, values)
                    await conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to update monitoring run {run_id}: {e}")
            raise
    
    # =================== REVIEW & APPROVAL MANAGEMENT ===================
    
    async def get_products_for_review(self, retailer: str = None, 
                                    category: str = None, limit: int = 50) -> List[Dict]:
        """Get products pending modesty review"""
        await self._ensure_db_initialized()
        
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                cursor = await conn.cursor()
                
                query = """
                    SELECT * FROM catalog_products 
                    WHERE review_status = 'pending'
                """
                params = []
                
                if retailer:
                    query += " AND retailer = ?"
                    params.append(retailer)
                
                if category:
                    query += " AND category = ?"
                    params.append(category)
                
                query += " ORDER BY discovered_date DESC, confidence_score ASC LIMIT ?"
                params.append(limit)
                
                await cursor.execute(query, params)
                rows = await cursor.fetchall()
                
                if rows:
                    columns = [desc[0] for desc in cursor.description]
                    return [dict(zip(columns, row)) for row in rows]
                
                return []
                
        except Exception as e:
            logger.error(f"Failed to get products for review: {e}")
            return []
    
    async def update_review_status(self, product_id: int, review_status: str, 
                                 reviewed_by: str, review_notes: str = None):
        """Update product review status"""
        await self._ensure_db_initialized()
        
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                await conn.execute("""
                    UPDATE catalog_products 
                    SET review_status = ?, reviewed_by = ?, reviewed_date = ?, 
                        review_notes = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (review_status, reviewed_by, datetime.utcnow(), review_notes, product_id))
                
                await conn.commit()
                logger.info(f"Updated review status for product {product_id}: {review_status}")
                
        except Exception as e:
            logger.error(f"Failed to update review status for product {product_id}: {e}")
            raise
    
    async def get_approved_products_for_batch(self, retailer: str = None) -> List[Dict]:
        """Get approved products ready for batch creation"""
        await self._ensure_db_initialized()
        
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                cursor = await conn.cursor()
                
                query = """
                    SELECT * FROM catalog_products 
                    WHERE review_status IN ('modest', 'moderately_modest') 
                    AND approved_for_scraping = 0
                """
                params = []
                
                if retailer:
                    query += " AND retailer = ?"
                    params.append(retailer)
                
                query += " ORDER BY reviewed_date DESC"
                
                await cursor.execute(query, params)
                rows = await cursor.fetchall()
                
                if rows:
                    columns = [desc[0] for desc in cursor.description]
                    return [dict(zip(columns, row)) for row in rows]
                
                return []
                
        except Exception as e:
            logger.error(f"Failed to get approved products: {e}")
            return []
    
    async def mark_products_as_batched(self, product_ids: List[int], batch_file: str):
        """Mark products as included in batch file"""
        await self._ensure_db_initialized()
        
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                placeholders = ','.join(['?'] * len(product_ids))
                await conn.execute(f"""
                    UPDATE catalog_products 
                    SET approved_for_scraping = 1, batch_created = 1, 
                        batch_file = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id IN ({placeholders})
                """, [batch_file] + product_ids)
                
                await conn.commit()
                logger.info(f"Marked {len(product_ids)} products as batched in {batch_file}")
                
        except Exception as e:
            logger.error(f"Failed to mark products as batched: {e}")
            raise
    
    # =================== UTILITY METHODS ===================
    
    async def get_system_stats(self) -> Dict:
        """Get catalog monitoring system statistics"""
        await self._ensure_db_initialized()
        
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                cursor = await conn.cursor()
                
                # Pending reviews
                await cursor.execute("SELECT COUNT(*) FROM catalog_products WHERE review_status = 'pending'")
                pending_reviews = await cursor.fetchone()
                
                # Active baselines
                await cursor.execute("SELECT COUNT(*) FROM catalog_baselines WHERE baseline_status = 'active'")
                active_baselines = await cursor.fetchone()
                
                # Recent runs (last 7 days)
                await cursor.execute("""
                    SELECT COUNT(*) FROM catalog_monitoring_runs 
                    WHERE actual_start_time > date('now', '-7 days')
                """)
                recent_runs = await cursor.fetchone()
                
                # Approved products awaiting batch creation
                await cursor.execute("""
                    SELECT COUNT(*) FROM catalog_products 
                    WHERE review_status IN ('modest', 'moderately_modest') AND approved_for_scraping = 0
                """)
                approved_pending = await cursor.fetchone()
                
                return {
                    'pending_reviews': pending_reviews[0] if pending_reviews else 0,
                    'active_baselines': active_baselines[0] if active_baselines else 0,
                    'recent_runs': recent_runs[0] if recent_runs else 0,
                    'approved_pending_batch': approved_pending[0] if approved_pending else 0
                }
                
        except Exception as e:
            logger.error(f"Failed to get system stats: {e}")
            return {}
    
    async def close(self):
        """Cleanup resources"""
        # Note: aiosqlite connections are closed automatically in context managers
        logger.debug("Catalog database manager closed")

# =================== HELPER FUNCTIONS ===================

def extract_product_code_from_url(url: str, retailer: str) -> Optional[str]:
    """Extract product code from URL using retailer-specific patterns"""
    PRODUCT_ID_PATTERNS = {
        'revolve': r'/([A-Z0-9-]+)\.html',
        'asos': r'/prd/(\d+)',
        'aritzia': r'/product/[^/]+/(\d+)\.html',
        'hm': r'productpage\.(\d+)\.html',
        'uniqlo': r'/products/([A-Z0-9]+)-',
        'anthropologie': r'/products/([^?]+)',
        'abercrombie': r'/products/([^?]+)',
        'nordstrom': r'/s/([^?]+)',
        'urban_outfitters': r'/products/([^?]+)',
        'mango': r'/([0-9]+)\.html'
    }
    
    pattern = PRODUCT_ID_PATTERNS.get(retailer)
    if pattern:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None