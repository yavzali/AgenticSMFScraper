#!/usr/bin/env python3
"""
Migration Script: Old Catalog Products to New Assessment Queue

Migrates pending products from catalog_products table to assessment_queue table
to unify the assessment workflow under the new system.
"""

import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Any

class QueueMigrator:
    def __init__(self, db_path: str = '/var/www/html/web_assessment/data/products.db'):
        self.db_path = db_path
        self.migrated_count = 0
        self.errors = []
        
    def connect_db(self) -> sqlite3.Connection:
        """Connect to the database"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def build_product_data(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Build product_data JSON from catalog_products row"""
        product_data = {}
        
        # Core fields
        if row['catalog_url']:
            product_data['url'] = row['catalog_url']
            product_data['catalog_url'] = row['catalog_url']
        
        if row['title']:
            product_data['title'] = row['title']
            
        if row['price']:
            product_data['price'] = str(row['price'])
            
        if row['original_price']:
            product_data['original_price'] = str(row['original_price'])
            
        if row['sale_status']:
            product_data['sale_status'] = row['sale_status']
            
        if row['retailer']:
            product_data['retailer'] = row['retailer']
            
        if row['product_code']:
            product_data['product_code'] = row['product_code']
            
        # Handle images
        if row['image_urls']:
            try:
                # Try to parse as JSON array
                images = json.loads(row['image_urls'])
                if isinstance(images, list):
                    product_data['image_urls'] = images
                else:
                    product_data['image_urls'] = [str(images)]
            except (json.JSONDecodeError, TypeError):
                # Fallback: treat as single URL string
                product_data['image_urls'] = [str(row['image_urls'])]
        
        # Shopify fields if available
        if row['shopify_draft_id']:
            product_data['shopify_id'] = row['shopify_draft_id']
            
        if row['shopify_image_urls']:
            try:
                shopify_images = json.loads(row['shopify_image_urls'])
                product_data['shopify_image_urls'] = shopify_images
            except (json.JSONDecodeError, TypeError):
                product_data['shopify_image_urls'] = []
        else:
            product_data['shopify_image_urls'] = []
            
        # Additional fields
        if row['availability']:
            product_data['stock_status'] = row['availability']
            
        if row['confidence_score']:
            product_data['confidence_score'] = float(row['confidence_score'])
            
        # Set clothing type based on category
        if row['category']:
            category = row['category'].lower()
            if 'dress' in category:
                product_data['clothing_type'] = 'dress'
            elif 'top' in category:
                product_data['clothing_type'] = 'top'
            else:
                product_data['clothing_type'] = 'unknown'
                
        # Set extraction source
        product_data['extraction_method'] = row['extraction_method'] or 'catalog_scan'
        
        return product_data
    
    def migrate_products(self) -> bool:
        """Main migration function"""
        print("🚀 Starting migration from catalog_products to assessment_queue")
        print("=" * 70)
        
        try:
            conn = self.connect_db()
            cursor = conn.cursor()
            
            # Step 1: Query old system for pending products
            print("📋 Querying catalog_products for pending items...")
            cursor.execute("""
                SELECT * FROM catalog_products 
                WHERE review_status = 'pending'
                ORDER BY discovered_date DESC
            """)
            
            pending_products = cursor.fetchall()
            total_to_migrate = len(pending_products)
            
            print(f"Found {total_to_migrate} products to migrate")
            
            if total_to_migrate == 0:
                print("✅ No products to migrate")
                return True
            
            # Step 2: Migrate each product
            print("\n📦 Migrating products...")
            
            for i, row in enumerate(pending_products, 1):
                try:
                    # Build product data JSON
                    product_data = self.build_product_data(row)
                    product_data_json = json.dumps(product_data)
                    
                    # Determine URL for assessment queue
                    product_url = row['catalog_url'] or row['normalized_url']
                    if not product_url:
                        self.errors.append(f"Product {row['id']} has no URL")
                        continue
                    
                    # Insert into assessment_queue
                    cursor.execute("""
                        INSERT INTO assessment_queue (
                            product_url,
                            retailer,
                            category,
                            review_type,
                            priority,
                            status,
                            product_data,
                            suspected_match_data,
                            source_workflow,
                            added_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """, (
                        product_url,
                        row['retailer'],
                        row['category'],
                        'modesty',
                        'normal',
                        'pending',
                        product_data_json,
                        None,
                        'migration_from_catalog_products'
                    ))
                    
                    self.migrated_count += 1
                    
                    if i <= 3:  # Show progress for first 3
                        title = product_data.get('title', 'N/A')[:50]
                        print(f"  {i:2d}. {row['retailer']}: {title}...")
                    elif i % 10 == 0:  # Show progress every 10 items
                        print(f"  ... migrated {i}/{total_to_migrate} products")
                        
                except Exception as e:
                    error_msg = f"Failed to migrate product {row.get('id', 'unknown')}: {e}"
                    self.errors.append(error_msg)
                    print(f"❌ {error_msg}")
            
            # Step 3: Update old records
            print(f"\n🔄 Updating {self.migrated_count} old records...")
            cursor.execute("""
                UPDATE catalog_products 
                SET review_status = 'migrated_to_new_system'
                WHERE review_status = 'pending'
            """)
            
            updated_count = cursor.rowcount
            
            # Commit changes
            conn.commit()
            conn.close()
            
            # Step 4: Print summary
            print("\n" + "=" * 70)
            print("📊 MIGRATION SUMMARY")
            print("=" * 70)
            print(f"✅ Products migrated: {self.migrated_count}")
            print(f"🔄 Old records updated: {updated_count}")
            print(f"❌ Errors encountered: {len(self.errors)}")
            
            if self.errors:
                print("\nErrors:")
                for error in self.errors:
                    print(f"  - {error}")
            
            return len(self.errors) == 0
            
        except Exception as e:
            print(f"💥 Migration failed: {e}")
            return False
    
    def verify_migration(self):
        """Verify the migration was successful"""
        print("\n" + "=" * 70)
        print("🔍 VERIFYING MIGRATION")
        print("=" * 70)
        
        try:
            conn = self.connect_db()
            cursor = conn.cursor()
            
            # Check assessment_queue counts
            cursor.execute("""
                SELECT COUNT(*) as total, source_workflow 
                FROM assessment_queue 
                GROUP BY source_workflow
            """)
            
            queue_results = cursor.fetchall()
            print("Assessment queue by source:")
            for row in queue_results:
                source = row['source_workflow'] or 'NULL'
                print(f"  {source}: {row['total']} products")
            
            # Check old system status
            cursor.execute("""
                SELECT review_status, COUNT(*) as count
                FROM catalog_products 
                GROUP BY review_status
            """)
            
            catalog_results = cursor.fetchall()
            print("\nCatalog products by status:")
            for row in catalog_results:
                status = row['review_status'] or 'NULL'
                print(f"  {status}: {row['count']} products")
            
            # Sample migrated products
            cursor.execute("""
                SELECT 
                  product_url,
                  retailer,
                  json_extract(product_data, '$.title') as title,
                  source_workflow,
                  added_at
                FROM assessment_queue 
                WHERE source_workflow = 'migration_from_catalog_products'
                LIMIT 5
            """)
            
            samples = cursor.fetchall()
            print("\nSample migrated products:")
            for i, row in enumerate(samples, 1):
                url = row['product_url'][:50] + '...' if len(row['product_url']) > 53 else row['product_url']
                title = row['title'][:40] + '...' if row['title'] and len(row['title']) > 43 else (row['title'] or 'N/A')
                print(f"  {i}. {row['retailer']}: {title}")
                print(f"     URL: {url}")
                print(f"     Added: {row['added_at']}")
            
            conn.close()
            
        except Exception as e:
            print(f"❌ Verification failed: {e}")

def main():
    """Main entry point"""
    print("🔄 Catalog Products → Assessment Queue Migration")
    print("=" * 70)
    
    migrator = QueueMigrator()
    
    # Run migration
    success = migrator.migrate_products()
    
    # Verify results
    migrator.verify_migration()
    
    if success:
        print("\n🎉 Migration completed successfully!")
    else:
        print("\n💥 Migration completed with errors!")
    
    return success

if __name__ == '__main__':
    main()
