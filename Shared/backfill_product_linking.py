"""
Backfill Product Linking
Links existing catalog_products entries to products table entries
Also initializes retailer_url_patterns with baseline data

Run manually AFTER schema changes are applied
"""

import asyncio
import sqlite3
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from difflib import SequenceMatcher
import logging
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ProductLinker:
    """Links catalog_products to products table using multi-level matching"""
    
    def __init__(self, db_path: str = 'Shared/products.db'):
        self.db_path = db_path
        self.stats = {
            'total_catalog_products': 0,
            'linked': 0,
            'high_confidence': 0,  # >95%
            'medium_confidence': 0,  # 85-95%
            'unlinked': 0,  # <85%, not confident enough
            'by_method': {},
            'by_retailer': {}
        }
        self.retailer_stats = {}  # Track per-retailer patterns
    
    def get_connection(self):
        """Get database connection"""
        return sqlite3.connect(self.db_path)
    
    async def backfill_all(self):
        """Main backfill process"""
        logger.info("="*60)
        logger.info("🔗 STARTING PRODUCT LINKING BACKFILL")
        logger.info("="*60)
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get all catalog products not yet linked
        cursor.execute("""
            SELECT id, catalog_url, retailer, title, price, product_code, image_urls
            FROM catalog_products
            WHERE linked_product_url IS NULL
        """)
        catalog_products = cursor.fetchall()
        self.stats['total_catalog_products'] = len(catalog_products)
        
        logger.info(f"\n📊 Found {len(catalog_products):,} catalog products to link\n")
        
        # Initialize retailer stats tracking
        cursor.execute("SELECT DISTINCT retailer FROM catalog_products")
        retailers = [r[0] for r in cursor.fetchall()]
        for retailer in retailers:
            self.retailer_stats[retailer] = {
                'total': 0,
                'linked': 0,
                'url_changes': 0,
                'method_counts': {},
                'confidences': []
            }
        
        # Process each one
        processed = 0
        for cp in catalog_products:
            cp_id, catalog_url, retailer, title, price, product_code, image_urls = cp
            
            match = await self._find_matching_product(
                cursor, catalog_url, retailer, title, price, product_code, image_urls
            )
            
            # Track retailer stats
            self.retailer_stats[retailer]['total'] += 1
            
            if match:
                product_url, confidence, method = match
                
                # Track method usage
                self.retailer_stats[retailer]['method_counts'][method] = \
                    self.retailer_stats[retailer]['method_counts'].get(method, 0) + 1
                self.retailer_stats[retailer]['confidences'].append(confidence)
                
                # Track URL changes
                normalized_catalog = catalog_url.split('?')[0].rstrip('/')
                normalized_product = product_url.split('?')[0].rstrip('/')
                if normalized_catalog != normalized_product:
                    self.retailer_stats[retailer]['url_changes'] += 1
                
                # Only link if confidence >= 85%
                if confidence >= 0.85:
                    # Update catalog_products
                    cursor.execute("""
                        UPDATE catalog_products
                        SET linked_product_url = ?,
                            link_confidence = ?,
                            link_method = ?
                        WHERE id = ?
                    """, (product_url, confidence, method, cp_id))
                    
                    self.stats['linked'] += 1
                    self.stats['by_method'][method] = self.stats['by_method'].get(method, 0) + 1
                    self.stats['by_retailer'][retailer] = self.stats['by_retailer'].get(retailer, 0) + 1
                    self.retailer_stats[retailer]['linked'] += 1
                    
                    if confidence >= 0.95:
                        self.stats['high_confidence'] += 1
                    else:
                        self.stats['medium_confidence'] += 1
                else:
                    self.stats['unlinked'] += 1
            else:
                self.stats['unlinked'] += 1
            
            processed += 1
            if processed % 100 == 0:
                logger.info(f"⏳ Processed {processed:,}/{len(catalog_products):,} ({processed/len(catalog_products)*100:.1f}%)")
                conn.commit()  # Commit periodically
        
        conn.commit()
        
        # Initialize retailer_url_patterns table with learned data
        await self._initialize_retailer_patterns(cursor)
        
        conn.commit()
        conn.close()
        
        self._print_stats()
    
    async def _find_matching_product(
        self, 
        cursor, 
        catalog_url: str, 
        retailer: str, 
        title: str, 
        price: float, 
        product_code: str, 
        image_urls: str
    ) -> Optional[Tuple[str, float, str]]:
        """
        Try to match catalog product to products table
        Returns: (product_url, confidence, method) or None
        """
        
        # Check if this retailer prefers fuzzy matching (would be empty initially)
        cursor.execute("""
            SELECT best_dedup_method, url_stability_score 
            FROM retailer_url_patterns 
            WHERE retailer = ?
        """, (retailer,))
        pattern_result = cursor.fetchone()
        
        prefer_fuzzy = False
        if pattern_result:
            best_method, stability = pattern_result
            prefer_fuzzy = (stability < 0.50 or best_method == 'fuzzy_title_price')
        
        # Level 1: Exact URL match (skip if prefer fuzzy)
        if not prefer_fuzzy:
            cursor.execute("""
                SELECT url FROM products 
                WHERE url = ? AND retailer = ?
            """, (catalog_url, retailer))
            result = cursor.fetchone()
            if result:
                return (result[0], 1.0, 'exact_url')
        
        # Level 2: Normalized URL match
        if not prefer_fuzzy:
            normalized = catalog_url.split('?')[0].rstrip('/')
            cursor.execute("""
                SELECT url FROM products 
                WHERE RTRIM(SUBSTR(url, 1, INSTR(url || '?', '?') - 1), '/') = ?
                AND retailer = ?
            """, (normalized, retailer))
            result = cursor.fetchone()
            if result:
                return (result[0], 0.95, 'normalized_url')
        
        # Level 3: Product code match
        if product_code and not prefer_fuzzy:
            cursor.execute("""
                SELECT url FROM products 
                WHERE product_code = ? AND retailer = ?
            """, (product_code, retailer))
            result = cursor.fetchone()
            if result:
                return (result[0], 0.90, 'product_code')
        
        # Level 4: Exact title + price
        if title and price:
            cursor.execute("""
                SELECT url FROM products 
                WHERE title = ? AND ABS(price - ?) < 1.0 AND retailer = ?
            """, (title, price, retailer))
            result = cursor.fetchone()
            if result:
                return (result[0], 0.95, 'exact_title_price')
        
        # Level 5: Fuzzy title + price (ALWAYS try, especially for unstable retailers)
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
                return (best_match, confidence, 'fuzzy_title_price')
        
        # No match found with sufficient confidence
        return None
    
    async def _initialize_retailer_patterns(self, cursor):
        """Initialize retailer_url_patterns table with backfill data"""
        logger.info("\n" + "="*60)
        logger.info("🌱 INITIALIZING RETAILER PATTERNS")
        logger.info("="*60)
        
        for retailer, stats in self.retailer_stats.items():
            if stats['linked'] == 0:
                logger.warning(f"⚠️  {retailer}: No linked products, skipping")
                continue
            
            # Calculate metrics
            total = stats['total']
            linked = stats['linked']
            url_changes = stats['url_changes']
            
            url_stability = 1.0 - (url_changes / linked) if linked > 0 else 1.0
            path_stable = 1 if url_stability > 0.80 else 0
            
            # Determine best method
            if stats['method_counts']:
                best_method = max(stats['method_counts'].items(), key=lambda x: x[1])[0]
            else:
                best_method = 'url'
            
            # Calculate average confidence
            avg_confidence = sum(stats['confidences']) / len(stats['confidences']) if stats['confidences'] else 0.85
            
            # Generate notes
            notes = (
                f"Initialized from backfill: {linked} products linked "
                f"({linked/total*100:.1f}% success rate). "
                f"URL stability: {url_stability:.1%}. "
                f"Primary method: {best_method}."
            )
            
            # Insert into retailer_url_patterns
            cursor.execute("""
                INSERT OR REPLACE INTO retailer_url_patterns
                (retailer, url_stability_score, last_measured, sample_size,
                 product_code_stable, path_stable, image_urls_consistent,
                 best_dedup_method, dedup_confidence_threshold,
                 url_changes_detected, code_changes_detected, image_url_changes_detected,
                 notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                retailer,
                url_stability,
                datetime.now().isoformat(),
                linked,
                1,  # Will learn over time
                path_stable,
                1,  # Will learn over time
                best_method,
                avg_confidence,
                url_changes,
                0,  # Will learn over time
                0,  # Will learn over time
                notes
            ))
            
            logger.info(f"✅ {retailer}:")
            logger.info(f"   Linked: {linked:,}/{total:,} ({linked/total*100:.1f}%)")
            logger.info(f"   URL stability: {url_stability:.1%}")
            logger.info(f"   URL changes: {url_changes:,}")
            logger.info(f"   Best method: {best_method}")
            logger.info(f"   Method breakdown: {stats['method_counts']}")
    
    def _print_stats(self):
        """Print summary statistics"""
        total = self.stats['total_catalog_products']
        linked = self.stats['linked']
        unlinked = self.stats['unlinked']
        
        logger.info("\n" + "="*60)
        logger.info("📊 BACKFILL RESULTS")
        logger.info("="*60)
        logger.info(f"Total catalog products: {total:,}")
        logger.info(f"Successfully linked: {linked:,} ({linked/total*100:.1f}%)")
        logger.info(f"  High confidence (≥95%): {self.stats['high_confidence']:,}")
        logger.info(f"  Medium confidence (85-95%): {self.stats['medium_confidence']:,}")
        logger.info(f"Not linked (low confidence): {unlinked:,} ({unlinked/total*100:.1f}%)")
        
        logger.info(f"\n📈 By Method:")
        for method, count in sorted(self.stats['by_method'].items(), key=lambda x: -x[1]):
            logger.info(f"  {method}: {count:,}")
        
        logger.info(f"\n🏪 By Retailer:")
        for retailer, count in sorted(self.stats['by_retailer'].items(), key=lambda x: -x[1]):
            logger.info(f"  {retailer}: {count:,}")
        
        logger.info("="*60 + "\n")


async def main():
    """Main entry point"""
    linker = ProductLinker()
    await linker.backfill_all()


if __name__ == '__main__':
    asyncio.run(main())

