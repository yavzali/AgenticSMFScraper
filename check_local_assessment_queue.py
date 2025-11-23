#!/usr/bin/env python3
"""
Diagnostic script to check local assessment queue state
Run before syncing to web server to verify what should be uploaded
"""

import sqlite3
import json
from pathlib import Path
import sys


def check_database():
    """Check local database state and report findings"""
    
    # Path to local database
    db_path = Path.home() / "Agent Modest Scraper System" / "Shared" / "products.db"
    
    print(f"Checking database: {db_path}")
    print(f"Database exists: {db_path.exists()}\n")
    
    if not db_path.exists():
        print("❌ ERROR: Database not found!")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check assessment_queue table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='assessment_queue'")
        if not cursor.fetchone():
            print("❌ ERROR: assessment_queue table doesn't exist!")
            conn.close()
            return False
        
        # Count pending items in assessment_queue
        cursor.execute("SELECT COUNT(*) FROM assessment_queue WHERE status = 'pending'")
        pending_count = cursor.fetchone()[0]
        
        print(f"=== LOCAL DATABASE STATE ===")
        print(f"Total products pending review: {pending_count}\n")
        
        if pending_count == 0:
            print("✅ No products pending review - database is clean")
            conn.close()
            return True
        
        # Show breakdown by review_type
        cursor.execute("""
            SELECT review_type, COUNT(*) 
            FROM assessment_queue 
            WHERE status = 'pending' 
            GROUP BY review_type
        """)
        print("Breakdown by review type:")
        for row in cursor.fetchall():
            print(f"  {row[0]}: {row[1]} products")
        
        # Show breakdown by retailer
        cursor.execute("""
            SELECT retailer, COUNT(*) 
            FROM assessment_queue 
            WHERE status = 'pending' 
            GROUP BY retailer
            ORDER BY COUNT(*) DESC
        """)
        print("\nBreakdown by retailer:")
        for row in cursor.fetchall():
            print(f"  {row[0]}: {row[1]} products")
        
        # Show sample products with image data check
        print("\n=== SAMPLE PRODUCTS (checking for images) ===")
        cursor.execute("""
            SELECT id, product_url, retailer, review_type, product_data
            FROM assessment_queue 
            WHERE status = 'pending' 
            LIMIT 5
        """)
        
        for row in cursor.fetchall():
            product_id, url, retailer, review_type, product_data_json = row
            product_data = json.loads(product_data_json)
            
            print(f"\nProduct ID {product_id}:")
            print(f"  Retailer: {retailer}")
            print(f"  Review Type: {review_type}")
            print(f"  Title: {product_data.get('title', 'N/A')[:60]}...")
            print(f"  URL: {url[:80]}...")
            
            # Check for images
            shopify_images = product_data.get('shopify_image_urls', [])
            regular_images = product_data.get('image_urls', [])
            legacy_images = product_data.get('images', [])
            
            print(f"  Image URLs:")
            print(f"    - Shopify CDN: {len(shopify_images)} images")
            print(f"    - Regular URLs: {len(regular_images)} images")
            print(f"    - Legacy field: {len(legacy_images)} images")
            
            if shopify_images:
                print(f"    - First Shopify URL: {shopify_images[0][:60]}...")
            elif regular_images:
                print(f"    - First Regular URL: {regular_images[0][:60]}...")
            elif legacy_images:
                print(f"    - First Legacy URL: {legacy_images[0][:60]}...")
        
        conn.close()
        
        print("\n" + "="*60)
        print(f"✅ Diagnostic complete. Found {pending_count} pending products.")
        print("If this number is correct, proceed to sync the database to the web server.")
        return True
        
    except Exception as e:
        print(f"❌ ERROR during diagnostic: {e}")
        return False


if __name__ == "__main__":
    success = check_database()
    sys.exit(0 if success else 1)

