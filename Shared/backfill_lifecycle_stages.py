"""
Backfill Lifecycle Stages
Sets lifecycle_stage for existing products in products table
Run manually AFTER schema changes are applied
"""

import sqlite3
from datetime import datetime
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LifecycleBackfiller:
    """Backfills lifecycle stages for existing products"""
    
    def __init__(self, db_path: str = 'Shared/products.db'):
        self.db_path = db_path
        self.stats = {
            'total_products': 0,
            'imported_direct': 0,
            'assessed_approved': 0,
            'assessed_rejected': 0,
            'pending_assessment': 0,
            'unknown': 0
        }
    
    def backfill_all(self):
        """Main backfill process"""
        logger.info("="*60)
        logger.info("🔄 STARTING LIFECYCLE BACKFILL")
        logger.info("="*60)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get all products without lifecycle_stage
        cursor.execute("""
            SELECT url, source, shopify_status, modesty_status, assessment_status
            FROM products
            WHERE lifecycle_stage IS NULL
        """)
        products = cursor.fetchall()
        self.stats['total_products'] = len(products)
        
        logger.info(f"\n📊 Found {len(products):,} products to classify\n")
        
        processed = 0
        for product in products:
            url, source, shopify_status, modesty_status, assessment_status = product
            
            # Determine lifecycle_stage
            lifecycle_stage = self._determine_lifecycle_stage(
                source, shopify_status, modesty_status, assessment_status
            )
            
            # Determine data_completeness
            data_completeness = 'full'  # All existing products have full data
            if shopify_status in ['published', 'draft']:
                data_completeness = 'enriched'  # Has Shopify data
            
            # Update product
            cursor.execute("""
                UPDATE products
                SET lifecycle_stage = ?,
                    data_completeness = ?
                WHERE url = ?
            """, (lifecycle_stage, data_completeness, url))
            
            # Track stats
            self.stats[lifecycle_stage] += 1
            
            processed += 1
            if processed % 100 == 0:
                logger.info(f"⏳ Processed {processed:,}/{len(products):,} ({processed/len(products)*100:.1f}%)")
                conn.commit()
        
        conn.commit()
        conn.close()
        
        self._print_stats()
    
    def _determine_lifecycle_stage(
        self, 
        source: str, 
        shopify_status: str, 
        modesty_status: str,
        assessment_status: str
    ) -> str:
        """Determine lifecycle stage based on existing fields"""
        
        # Products from New Product Importer
        if source == 'new_product_import':
            return 'imported_direct'
        
        # Products published to Shopify (approved)
        if shopify_status == 'published':
            return 'assessed_approved'
        
        # Products kept as draft (rejected or pending)
        if shopify_status == 'draft':
            # Check if actually rejected
            if modesty_status == 'not_modest':
                return 'assessed_rejected'
            # Otherwise pending assessment
            return 'pending_assessment'
        
        # Products in assessment queue
        if assessment_status in ['queued', 'pending_modesty_review']:
            return 'pending_assessment'
        
        # Default: unknown
        return 'unknown'
    
    def _print_stats(self):
        """Print summary statistics"""
        total = self.stats['total_products']
        
        logger.info("\n" + "="*60)
        logger.info("📊 LIFECYCLE BACKFILL RESULTS")
        logger.info("="*60)
        logger.info(f"Total products: {total:,}")
        logger.info(f"\nBy Lifecycle Stage:")
        logger.info(f"  imported_direct: {self.stats['imported_direct']:,}")
        logger.info(f"  assessed_approved: {self.stats['assessed_approved']:,}")
        logger.info(f"  assessed_rejected: {self.stats['assessed_rejected']:,}")
        logger.info(f"  pending_assessment: {self.stats['pending_assessment']:,}")
        logger.info(f"  unknown: {self.stats['unknown']:,}")
        logger.info("="*60 + "\n")


if __name__ == '__main__':
    backfiller = LifecycleBackfiller()
    backfiller.backfill_all()

