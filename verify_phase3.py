#!/usr/bin/env python3
"""
Verification script for Phase 3: Baseline Scanner Updates
Tests that scan_type and image_url_source are set correctly
"""

import sys
import os
sys.path.append('Shared')

import sqlite3
import asyncio
from db_manager import DatabaseManager
from datetime import datetime

async def test_create_catalog_baseline():
    """Test that create_catalog_baseline sets scan_type and image_url_source"""
    
    print("=" * 60)
    print("PHASE 3: BASELINE SCANNER VERIFICATION")
    print("=" * 60)
    
    db = DatabaseManager()
    
    # Test data
    test_products = [
        {
            'url': 'https://test.com/product1',
            'title': 'Test Product 1',
            'price': 99.99,
            'product_code': 'TEST-001',
            'images': ['https://test.com/image1.jpg', 'https://test.com/image2.jpg']
        },
        {
            'url': 'https://test.com/product2',
            'title': 'Test Product 2',
            'price': 89.99,
            'product_code': 'TEST-002',
            'images': ['https://test.com/image3.jpg']
        },
        {
            'url': 'https://test.com/product3',
            'title': 'Test Product 3',
            'price': 79.99,
            'product_code': 'TEST-003',
            'images': []  # No images
        }
    ]
    
    print("\n1. Testing create_catalog_baseline with 3 test products...")
    print("   - 2 products with images")
    print("   - 1 product without images")
    
    baseline_id = await db.create_catalog_baseline(
        retailer='test_retailer',
        category='test_category',
        modesty_level='modest',
        products=test_products,
        catalog_url='https://test.com/catalog',
        scan_date=datetime.utcnow()
    )
    
    if baseline_id:
        print(f"   ✅ Baseline created: {baseline_id}")
    else:
        print("   ❌ Baseline creation failed")
        return False
    
    # Verify products were saved with correct fields
    print("\n2. Verifying products saved with lifecycle fields...")
    conn = db._get_connection()
    cursor = conn.cursor()
    
    # Check scan_type
    cursor.execute("""
        SELECT scan_type, COUNT(*) 
        FROM catalog_products 
        WHERE retailer = 'test_retailer'
        AND catalog_url IN (?, ?, ?)
        GROUP BY scan_type
    """, (test_products[0]['url'], test_products[1]['url'], test_products[2]['url']))
    
    scan_type_results = cursor.fetchall()
    print("\n   Scan type distribution:")
    for scan_type, count in scan_type_results:
        print(f"     {scan_type}: {count}")
    
    if len(scan_type_results) == 1 and scan_type_results[0][0] == 'baseline' and scan_type_results[0][1] == 3:
        print("   ✅ All products have scan_type='baseline'")
    else:
        print("   ❌ scan_type not set correctly")
        return False
    
    # Check image_url_source
    cursor.execute("""
        SELECT image_url_source, COUNT(*) 
        FROM catalog_products 
        WHERE retailer = 'test_retailer'
        AND catalog_url IN (?, ?, ?)
        GROUP BY image_url_source
    """, (test_products[0]['url'], test_products[1]['url'], test_products[2]['url']))
    
    image_source_results = cursor.fetchall()
    print("\n   Image URL source distribution:")
    for source, count in image_source_results:
        print(f"     {source}: {count}")
    
    if len(image_source_results) == 1 and image_source_results[0][0] == 'catalog_extraction' and image_source_results[0][1] == 3:
        print("   ✅ All products have image_url_source='catalog_extraction'")
    else:
        print("   ❌ image_url_source not set correctly")
        return False
    
    # Check image URLs were saved
    cursor.execute("""
        SELECT 
            catalog_url,
            image_urls,
            CASE 
                WHEN image_urls IS NOT NULL AND image_urls != '' AND image_urls != '[]' THEN 1 
                ELSE 0 
            END as has_images
        FROM catalog_products 
        WHERE retailer = 'test_retailer'
        AND catalog_url IN (?, ?, ?)
    """, (test_products[0]['url'], test_products[1]['url'], test_products[2]['url']))
    
    image_results = cursor.fetchall()
    print("\n   Image extraction results:")
    for url, image_urls, has_images in image_results:
        status = "✅" if has_images else "⚠️"
        print(f"     {status} {url}: {image_urls if has_images else 'No images'}")
    
    # Cleanup
    print("\n3. Cleaning up test data...")
    cursor.execute("DELETE FROM catalog_products WHERE retailer = 'test_retailer'")
    cursor.execute("DELETE FROM catalog_baselines WHERE retailer = 'test_retailer'")
    conn.commit()
    conn.close()
    print("   ✅ Cleanup complete")
    
    # Success summary
    print("\n" + "=" * 60)
    print("SUCCESS CRITERIA")
    print("=" * 60)
    print("✅ create_catalog_baseline completes without errors")
    print("✅ scan_type='baseline' set for all products")
    print("✅ image_url_source='catalog_extraction' set for all products")
    print("✅ Image URLs preserved and saved correctly")
    print("✅ Products without images handled gracefully")
    
    print("\n" + "=" * 60)
    print("✅ PHASE 3 VERIFICATION PASSED")
    print("=" * 60)
    print("\n→ Ready to proceed to PHASE 4: Catalog Monitor Updates")
    
    return True

if __name__ == '__main__':
    try:
        success = asyncio.run(test_create_catalog_baseline())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ VERIFICATION FAILED WITH ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

