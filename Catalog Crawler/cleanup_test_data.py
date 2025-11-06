"""
Cleanup Test Data - Remove test catalog entries from database
Use this after verifying test results to clean up test data
"""

import sqlite3
import sys
import os
from datetime import datetime

# Add shared path
sys.path.append(os.path.join(os.path.dirname(__file__), "../Shared"))
from logger_config import setup_logging

logger = setup_logging(__name__)

def cleanup_test_crawl(retailer: str, category: str, run_id: str = None, dry_run: bool = True):
    """
    Remove test catalog data from database
    
    Args:
        retailer: Retailer name (e.g., 'anthropologie')
        category: Category (e.g., 'dresses')
        run_id: Specific run ID to delete (optional, will prompt if not provided)
        dry_run: If True, show what would be deleted without deleting
    """
    
    db_path = os.path.join(os.path.dirname(__file__), "../Shared/products.db")
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Get catalog products for this retailer/category
            cursor.execute("""
                SELECT id, catalog_url, title, price, first_seen, baseline_id
                FROM catalog_products
                WHERE retailer = ? AND category = ?
                ORDER BY first_seen DESC
            """, (retailer, category))
            
            catalog_products = cursor.fetchall()
            
            if not catalog_products:
                logger.info(f"No catalog products found for {retailer}/{category}")
                return
            
            logger.info(f"\n📋 Found {len(catalog_products)} catalog products for {retailer}/{category}")
            logger.info("=" * 80)
            
            # Show first 10 products
            for idx, (prod_id, url, title, price, first_seen, baseline_id) in enumerate(catalog_products[:10], 1):
                logger.info(f"{idx}. {title[:50]}")
                logger.info(f"   URL: {url[:70]}...")
                logger.info(f"   Price: ${price} | First seen: {first_seen} | Baseline: {baseline_id}")
            
            if len(catalog_products) > 10:
                logger.info(f"... and {len(catalog_products) - 10} more products")
            
            logger.info("=" * 80)
            
            # Get monitoring runs
            cursor.execute("""
                SELECT run_id, run_date, crawl_type, total_products_found, new_products_found
                FROM catalog_monitoring_runs
                WHERE retailer = ? AND category = ?
                ORDER BY run_date DESC
            """, (retailer, category))
            
            runs = cursor.fetchall()
            
            if runs:
                logger.info(f"\n📊 Found {len(runs)} monitoring runs:")
                for run_id, run_date, crawl_type, total, new in runs:
                    logger.info(f"   - {run_id}: {crawl_type} | {total} total, {new} new | {run_date}")
            
            # Get baseline
            cursor.execute("""
                SELECT id, created_at, total_products, crawl_type
                FROM catalog_baselines
                WHERE retailer = ? AND category = ?
            """, (retailer, category))
            
            baseline = cursor.fetchone()
            
            if baseline:
                baseline_id, created, total, crawl_type = baseline
                logger.info(f"\n📸 Baseline: ID={baseline_id}, {total} products, created {created}")
            
            logger.info("=" * 80)
            
            if dry_run:
                logger.info("\n🔍 DRY RUN - Nothing deleted. Here's what WOULD be deleted:")
                logger.info(f"   ❌ {len(catalog_products)} catalog_products entries")
                logger.info(f"   ❌ {len(runs)} catalog_monitoring_runs entries")
                if baseline:
                    logger.info(f"   ❌ 1 catalog_baselines entry")
                logger.info("\n💡 Run with --confirm to actually delete")
            else:
                # Confirm deletion
                print(f"\n⚠️  WARNING: This will DELETE {len(catalog_products)} products and all related data!")
                print("Type 'DELETE' to confirm: ", end='')
                confirmation = input().strip()
                
                if confirmation != 'DELETE':
                    logger.info("❌ Deletion cancelled")
                    return
                
                # Delete in correct order (foreign key constraints)
                logger.info("\n🗑️  Deleting data...")
                
                # Delete monitoring runs
                cursor.execute("""
                    DELETE FROM catalog_monitoring_runs
                    WHERE retailer = ? AND category = ?
                """, (retailer, category))
                deleted_runs = cursor.rowcount
                logger.info(f"   ✅ Deleted {deleted_runs} monitoring runs")
                
                # Delete catalog products
                cursor.execute("""
                    DELETE FROM catalog_products
                    WHERE retailer = ? AND category = ?
                """, (retailer, category))
                deleted_products = cursor.rowcount
                logger.info(f"   ✅ Deleted {deleted_products} catalog products")
                
                # Delete baseline
                cursor.execute("""
                    DELETE FROM catalog_baselines
                    WHERE retailer = ? AND category = ?
                """, (retailer, category))
                deleted_baselines = cursor.rowcount
                logger.info(f"   ✅ Deleted {deleted_baselines} baseline entries")
                
                conn.commit()
                logger.info("\n✅ Cleanup complete!")
                
                # Show what remains
                cursor.execute("SELECT COUNT(*) FROM catalog_products WHERE retailer = ?", (retailer,))
                remaining = cursor.fetchone()[0]
                logger.info(f"   {remaining} catalog products remain for {retailer} (other categories)")
    
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        raise

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Cleanup test catalog data")
    parser.add_argument('--retailer', required=True, help='Retailer name (e.g., anthropologie)')
    parser.add_argument('--category', required=True, help='Category (e.g., dresses)')
    parser.add_argument('--confirm', action='store_true', help='Actually delete (not just dry run)')
    
    args = parser.parse_args()
    
    cleanup_test_crawl(
        retailer=args.retailer,
        category=args.category,
        dry_run=not args.confirm
    )

