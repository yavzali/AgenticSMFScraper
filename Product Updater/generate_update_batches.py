#!/usr/bin/env python3
"""
Batch Generator - Automatically generates update batches from database
Creates properly formatted batch files for Product Updater based on various criteria
"""

# Add shared path for imports
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../Shared"))
sys.path.append(os.path.dirname(__file__))

import sqlite3
import json
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pathlib import Path

from logger_config import setup_logging

logger = setup_logging(__name__)

class UpdateBatchGenerator:
    """
    Generates update batches from database based on intelligent criteria
    Ensures proper format for Product Updater compatibility
    """
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(script_dir, '../Shared/products.db')
        self.db_path = db_path
        logger.info("✅ Batch generator initialized")
    
    def generate_batch_by_retailer(self, retailer: str, 
                                   modesty_level: str = "modest",
                                   output_dir: str = None) -> Optional[str]:
        """
        Generate batch file for all products from a specific retailer in Shopify
        
        Args:
            retailer: Retailer name (e.g., 'revolve', 'asos')
            modesty_level: Default modesty level for batch
            output_dir: Directory to save batch file (defaults to current directory)
        
        Returns:
            Path to generated batch file, or None if no products found
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Query products in Shopify for this retailer
            cursor.execute("""
                SELECT url, modesty_status, COUNT(*) OVER() as total_count
                FROM products 
                WHERE retailer = ? AND shopify_id IS NOT NULL 
                ORDER BY last_updated ASC
            """, (retailer,))
            
            rows = cursor.fetchall()
            conn.close()
            
            if not rows:
                logger.warning(f"No products found for retailer '{retailer}' in Shopify")
                return None
            
            urls = [row[0] for row in rows]
            total_count = rows[0][2]
            
            # Determine actual modesty level (use most common from results)
            modesty_counts = {}
            for row in rows:
                modesty = row[1]
                modesty_counts[modesty] = modesty_counts.get(modesty, 0) + 1
            dominant_modesty = max(modesty_counts, key=modesty_counts.get)
            
            logger.info(f"Found {total_count} {retailer} products in Shopify")
            logger.info(f"Modesty breakdown: {modesty_counts}")
            
            # Create batch file
            batch_file = self._create_batch_file(
                urls=urls,
                batch_name=f"{retailer.title()} Product Update - {datetime.now().strftime('%B %d, %Y')}",
                batch_id=f"{retailer}_update_{datetime.now().strftime('%Y%m%d_%H%M')}",
                modesty_level=dominant_modesty,
                metadata={
                    'retailer': retailer,
                    'generation_method': 'by_retailer',
                    'modesty_breakdown': modesty_counts
                },
                output_dir=output_dir
            )
            
            logger.info(f"✅ Generated batch file: {batch_file}")
            return batch_file
            
        except Exception as e:
            logger.error(f"Error generating batch for retailer '{retailer}': {e}")
            return None
    
    def generate_batch_by_age(self, days_old: int = 7,
                             retailer: Optional[str] = None,
                             modesty_level: str = "modest",
                             max_products: int = 200,
                             output_dir: str = None) -> Optional[str]:
        """
        Generate batch file for products not updated in X days
        
        Args:
            days_old: Number of days since last update
            retailer: Optional retailer filter
            modesty_level: Default modesty level
            max_products: Maximum products per batch
            output_dir: Directory to save batch file
        
        Returns:
            Path to generated batch file, or None if no products found
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cutoff_date = datetime.now() - timedelta(days=days_old)
            
            if retailer:
                cursor.execute("""
                    SELECT url FROM products 
                    WHERE shopify_id IS NOT NULL 
                    AND retailer = ?
                    AND (last_updated IS NULL OR last_updated < ?)
                    ORDER BY last_updated ASC
                    LIMIT ?
                """, (retailer, cutoff_date, max_products))
            else:
                cursor.execute("""
                    SELECT url FROM products 
                    WHERE shopify_id IS NOT NULL 
                    AND (last_updated IS NULL OR last_updated < ?)
                    ORDER BY last_updated ASC
                    LIMIT ?
                """, (cutoff_date, max_products))
            
            urls = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            if not urls:
                logger.info(f"No products found older than {days_old} days")
                return None
            
            logger.info(f"Found {len(urls)} products not updated in {days_old}+ days")
            
            # Create batch file
            retailer_suffix = f"_{retailer}" if retailer else "_all"
            batch_file = self._create_batch_file(
                urls=urls,
                batch_name=f"Stale Products Update ({days_old}+ days) - {datetime.now().strftime('%B %d, %Y')}",
                batch_id=f"stale{retailer_suffix}_{days_old}days_{datetime.now().strftime('%Y%m%d_%H%M')}",
                modesty_level=modesty_level,
                metadata={
                    'generation_method': 'by_age',
                    'days_old_threshold': days_old,
                    'retailer_filter': retailer or 'all'
                },
                output_dir=output_dir
            )
            
            logger.info(f"✅ Generated batch file: {batch_file}")
            return batch_file
            
        except Exception as e:
            logger.error(f"Error generating batch by age: {e}")
            return None
    
    def generate_batch_by_status(self, status_filter: str,
                                modesty_level: str = "modest",
                                output_dir: str = None) -> Optional[str]:
        """
        Generate batch file based on product status
        
        Args:
            status_filter: Status to filter by ('on_sale', 'low_stock', 'out_of_stock')
            modesty_level: Default modesty level
            output_dir: Directory to save batch file
        
        Returns:
            Path to generated batch file, or None if no products found
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Map status filters to database queries
            if status_filter == 'on_sale':
                cursor.execute("""
                    SELECT url FROM products 
                    WHERE shopify_id IS NOT NULL 
                    AND sale_status = 'on_sale'
                    ORDER BY last_updated ASC
                """)
            elif status_filter == 'low_stock':
                cursor.execute("""
                    SELECT url FROM products 
                    WHERE shopify_id IS NOT NULL 
                    AND stock_status = 'low_stock'
                    ORDER BY last_updated ASC
                """)
            elif status_filter == 'out_of_stock':
                cursor.execute("""
                    SELECT url FROM products 
                    WHERE shopify_id IS NOT NULL 
                    AND stock_status = 'out_of_stock'
                    ORDER BY last_updated ASC
                """)
            else:
                logger.error(f"Unknown status filter: {status_filter}")
                return None
            
            urls = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            if not urls:
                logger.info(f"No products found with status '{status_filter}'")
                return None
            
            logger.info(f"Found {len(urls)} products with status '{status_filter}'")
            
            # Create batch file
            batch_file = self._create_batch_file(
                urls=urls,
                batch_name=f"{status_filter.replace('_', ' ').title()} Products Update - {datetime.now().strftime('%B %d, %Y')}",
                batch_id=f"{status_filter}_{datetime.now().strftime('%Y%m%d_%H%M')}",
                modesty_level=modesty_level,
                metadata={
                    'generation_method': 'by_status',
                    'status_filter': status_filter
                },
                output_dir=output_dir
            )
            
            logger.info(f"✅ Generated batch file: {batch_file}")
            return batch_file
            
        except Exception as e:
            logger.error(f"Error generating batch by status: {e}")
            return None
    
    def generate_smart_batch(self, retailer: Optional[str] = None,
                           priority: str = "balanced",
                           max_products: int = 150,
                           modesty_level: str = "modest",
                           output_dir: str = None) -> Optional[str]:
        """
        Generate smart batch based on priority heuristics
        
        Args:
            retailer: Optional retailer filter
            priority: 'stale' (oldest first), 'sale' (on sale first), 'balanced' (mix)
            max_products: Maximum products per batch
            modesty_level: Default modesty level
            output_dir: Directory to save batch file
        
        Returns:
            Path to generated batch file, or None if no products found
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Build smart query based on priority
            if priority == 'stale':
                # Prioritize oldest updates
                order_clause = "last_updated ASC NULLS FIRST"
            elif priority == 'sale':
                # Prioritize on-sale items (prices change frequently)
                order_clause = "CASE WHEN sale_status = 'on_sale' THEN 0 ELSE 1 END, last_updated ASC"
            else:  # balanced
                # Mix of sale items and stale items
                order_clause = """
                    CASE 
                        WHEN sale_status = 'on_sale' THEN 0
                        WHEN stock_status = 'low_stock' THEN 1
                        WHEN last_updated IS NULL THEN 2
                        WHEN last_updated < datetime('now', '-7 days') THEN 3
                        ELSE 4
                    END, last_updated ASC
                """
            
            if retailer:
                query = f"""
                    SELECT url FROM products 
                    WHERE shopify_id IS NOT NULL AND retailer = ?
                    ORDER BY {order_clause}
                    LIMIT ?
                """
                cursor.execute(query, (retailer, max_products))
            else:
                query = f"""
                    SELECT url FROM products 
                    WHERE shopify_id IS NOT NULL
                    ORDER BY {order_clause}
                    LIMIT ?
                """
                cursor.execute(query, (max_products,))
            
            urls = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            if not urls:
                logger.info("No products found for smart batch")
                return None
            
            logger.info(f"Generated smart batch with {len(urls)} products (priority: {priority})")
            
            # Create batch file
            retailer_suffix = f"_{retailer}" if retailer else "_all"
            batch_file = self._create_batch_file(
                urls=urls,
                batch_name=f"Smart Update ({priority}) - {datetime.now().strftime('%B %d, %Y')}",
                batch_id=f"smart{retailer_suffix}_{priority}_{datetime.now().strftime('%Y%m%d_%H%M')}",
                modesty_level=modesty_level,
                metadata={
                    'generation_method': 'smart_batch',
                    'priority': priority,
                    'retailer_filter': retailer or 'all'
                },
                output_dir=output_dir
            )
            
            logger.info(f"✅ Generated batch file: {batch_file}")
            return batch_file
            
        except Exception as e:
            logger.error(f"Error generating smart batch: {e}")
            return None
    
    def _create_batch_file(self, urls: List[str], batch_name: str, batch_id: str,
                          modesty_level: str, metadata: Dict,
                          output_dir: str = None) -> str:
        """
        Create properly formatted batch file for Product Updater
        
        Returns:
            Path to created batch file
        """
        if output_dir is None:
            output_dir = os.path.dirname(os.path.abspath(__file__))
        
        batch_data = {
            "batch_name": batch_name,
            "created_date": datetime.now().strftime('%Y-%m-%d'),
            "created_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "batch_id": batch_id,
            "modesty_level": modesty_level,
            "total_urls": len(urls),
            "generation_metadata": metadata,
            "urls": urls  # Simple list of URL strings (correct format)
        }
        
        # Save batch file
        filename = f"{batch_id}.json"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'w') as f:
            json.dump(batch_data, f, indent=2)
        
        return filename
    
    def get_update_statistics(self) -> Dict:
        """Get statistics about products needing updates"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Total products in Shopify
            cursor.execute("SELECT COUNT(*) FROM products WHERE shopify_id IS NOT NULL")
            total_in_shopify = cursor.fetchone()[0]
            
            # By retailer
            cursor.execute("""
                SELECT retailer, COUNT(*) FROM products 
                WHERE shopify_id IS NOT NULL 
                GROUP BY retailer
            """)
            by_retailer = dict(cursor.fetchall())
            
            # Not updated in 7+ days
            cutoff = datetime.now() - timedelta(days=7)
            cursor.execute("""
                SELECT COUNT(*) FROM products 
                WHERE shopify_id IS NOT NULL 
                AND (last_updated IS NULL OR last_updated < ?)
            """, (cutoff,))
            stale_7_days = cursor.fetchone()[0]
            
            # On sale
            cursor.execute("""
                SELECT COUNT(*) FROM products 
                WHERE shopify_id IS NOT NULL AND sale_status = 'on_sale'
            """)
            on_sale = cursor.fetchone()[0]
            
            # Low stock
            cursor.execute("""
                SELECT COUNT(*) FROM products 
                WHERE shopify_id IS NOT NULL AND stock_status = 'low_stock'
            """)
            low_stock = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                'total_in_shopify': total_in_shopify,
                'by_retailer': by_retailer,
                'stale_7_days': stale_7_days,
                'on_sale': on_sale,
                'low_stock': low_stock
            }
            
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {}

def main():
    """CLI interface for batch generator"""
    
    parser = argparse.ArgumentParser(
        description="Generate update batches for Product Updater",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate batch for all Revolve products
  python generate_update_batches.py --retailer revolve
  
  # Generate batch for products not updated in 7+ days
  python generate_update_batches.py --by-age 7
  
  # Generate smart batch (balanced priority)
  python generate_update_batches.py --smart --priority balanced
  
  # Generate batch for on-sale products
  python generate_update_batches.py --by-status on_sale
  
  # Show statistics about products needing updates
  python generate_update_batches.py --stats
        """
    )
    
    # Generation methods
    parser.add_argument('--retailer', type=str, help='Generate batch for specific retailer')
    parser.add_argument('--by-age', type=int, metavar='DAYS', 
                       help='Generate batch for products not updated in X days')
    parser.add_argument('--by-status', type=str, choices=['on_sale', 'low_stock', 'out_of_stock'],
                       help='Generate batch by product status')
    parser.add_argument('--smart', action='store_true',
                       help='Generate smart batch with priority heuristics')
    
    # Options
    parser.add_argument('--priority', type=str, choices=['stale', 'sale', 'balanced'],
                       default='balanced', help='Priority for smart batch (default: balanced)')
    parser.add_argument('--max-products', type=int, default=200,
                       help='Maximum products per batch (default: 200)')
    parser.add_argument('--modesty-level', type=str, choices=['modest', 'moderately_modest'],
                       default='modest', help='Default modesty level (default: modest)')
    parser.add_argument('--output-dir', type=str, help='Output directory for batch files')
    
    # Utilities
    parser.add_argument('--stats', action='store_true',
                       help='Show statistics about products needing updates')
    parser.add_argument('--auto-run', action='store_true',
                       help='Automatically run Product Updater after generating batch')
    
    args = parser.parse_args()
    
    # Validate arguments
    if not any([args.retailer, args.by_age, args.by_status, args.smart, args.stats]):
        parser.print_help()
        return
    
    generator = UpdateBatchGenerator()
    
    # Show statistics
    if args.stats:
        stats = generator.get_update_statistics()
        print("\n" + "="*60)
        print("📊 PRODUCT UPDATE STATISTICS")
        print("="*60)
        print(f"Total products in Shopify: {stats.get('total_in_shopify', 0)}")
        print(f"\nBy Retailer:")
        for retailer, count in stats.get('by_retailer', {}).items():
            print(f"  {retailer}: {count}")
        print(f"\nProducts needing attention:")
        print(f"  Not updated in 7+ days: {stats.get('stale_7_days', 0)}")
        print(f"  On sale: {stats.get('on_sale', 0)}")
        print(f"  Low stock: {stats.get('low_stock', 0)}")
        print("="*60)
        return
    
    # Generate batch
    batch_file = None
    
    if args.retailer:
        batch_file = generator.generate_batch_by_retailer(
            retailer=args.retailer,
            modesty_level=args.modesty_level,
            output_dir=args.output_dir
        )
    elif args.by_age:
        batch_file = generator.generate_batch_by_age(
            days_old=args.by_age,
            retailer=None,
            modesty_level=args.modesty_level,
            max_products=args.max_products,
            output_dir=args.output_dir
        )
    elif args.by_status:
        batch_file = generator.generate_batch_by_status(
            status_filter=args.by_status,
            modesty_level=args.modesty_level,
            output_dir=args.output_dir
        )
    elif args.smart:
        batch_file = generator.generate_smart_batch(
            retailer=None,
            priority=args.priority,
            max_products=args.max_products,
            modesty_level=args.modesty_level,
            output_dir=args.output_dir
        )
    
    if batch_file:
        print(f"\n✅ Batch file generated: {batch_file}")
        print(f"\nTo run Product Updater:")
        print(f"  python product_updater.py --batch-file {batch_file} --force-run-now")
        
        # Auto-run if requested
        if args.auto_run:
            import subprocess
            print(f"\n🚀 Auto-running Product Updater...")
            subprocess.run([
                'python', 'product_updater.py',
                '--batch-file', batch_file,
                '--force-run-now'
            ])
    else:
        print("\n❌ No batch file generated (no products found matching criteria)")
        sys.exit(1)

if __name__ == "__main__":
    main()

