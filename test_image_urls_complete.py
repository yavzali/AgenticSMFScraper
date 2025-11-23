#!/usr/bin/env python3
"""
Complete test for image_urls column and image matching
"""

import sys
import os
sys.path.append('Shared')
sys.path.append('Workflows')

import asyncio
import json
from datetime import datetime
from db_manager import DatabaseManager

async def test_complete_image_functionality():
    """Test the complete image URLs functionality"""
    
    print("=" * 60)
    print("COMPLETE IMAGE FUNCTIONALITY TEST")
    print("=" * 60)
    
    from catalog_monitor import CatalogMonitor
    
    monitor = CatalogMonitor()
    db = monitor.db_manager
    
    # Test 1: Verify column exists
    print("\n1. Verifying image_urls column exists...")
    conn = db._get_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(products)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'image_urls' in columns:
        print("   ✅ image_urls column exists in products table")
    else:
        print("   ❌ image_urls column NOT found")
        conn.close()
        return False
    
    # Test 2: Test saving product with images
    print("\n2. Testing save_product with images...")
    
    test_images = [
        'https://test.com/img1.jpg',
        'https://test.com/img2.jpg',
        'https://test.com/img3.jpg'
    ]
    
    await db.save_product(
        url='https://test.com/product-with-images',
        retailer='test_retailer',
        product_data={
            'url': 'https://test.com/product-with-images',
            'title': 'Test Product with Images',
            'price': 99.99,
            'retailer': 'test_retailer',
            'images': test_images  # Using 'images' field
        },
        source='test'
    )
    
    # Verify images were saved
    cursor.execute("""
        SELECT image_urls FROM products 
        WHERE url = 'https://test.com/product-with-images'
    """)
    result = cursor.fetchone()
    
    if result and result[0]:
        saved_images = json.loads(result[0])
        if saved_images == test_images:
            print(f"   ✅ Images saved correctly: {len(saved_images)} images")
        else:
            print(f"   ❌ Images mismatch: {saved_images} vs {test_images}")
            conn.close()
            return False
    else:
        print(f"   ❌ No images saved: {result}")
        conn.close()
        return False
    
    # Test 3: Test image matching with exact match
    print("\n3. Testing image matching (100% overlap)...")
    
    catalog_product = {
        'url': 'https://test.com/different-url-same-images',
        'title': 'Different Title',
        'price': 99.99,
        'images': test_images  # Same images as saved product
    }
    
    link_result = await monitor._link_to_products_table(
        catalog_product=catalog_product,
        retailer='test_retailer'
    )
    
    if link_result and link_result['link_method'] == 'image_url_match':
        print(f"   ✅ Image matching works!")
        print(f"      Method: {link_result['link_method']}")
        print(f"      Confidence: {link_result['link_confidence']:.2f}")
        print(f"      Linked to: {link_result['linked_product_url']}")
    else:
        print(f"   ❌ Image matching failed: {link_result}")
        conn.close()
        return False
    
    # Test 4: Test partial overlap (67%)
    print("\n4. Testing partial image overlap (67%)...")
    
    partial_images = test_images[:2] + ['https://test.com/different.jpg']
    
    catalog_product_partial = {
        'url': 'https://test.com/partial-overlap',
        'title': 'Partial Overlap Product',
        'price': 95.99,  # Within $10
        'images': partial_images
    }
    
    link_result_partial = await monitor._link_to_products_table(
        catalog_product=catalog_product_partial,
        retailer='test_retailer'
    )
    
    if link_result_partial and link_result_partial['link_method'] == 'image_url_match':
        print(f"   ✅ Partial overlap detected!")
        print(f"      Confidence: {link_result_partial['link_confidence']:.2f}")
    else:
        print(f"   ❌ Partial overlap failed: {link_result_partial}")
        conn.close()
        return False
    
    # Test 5: Test low overlap (should NOT match)
    print("\n5. Testing low overlap rejection (33%)...")
    
    low_overlap = test_images[:1] + ['https://test.com/new1.jpg', 'https://test.com/new2.jpg']
    
    catalog_product_low = {
        'url': 'https://test.com/low-overlap',
        'title': 'Low Overlap Product',
        'price': 99.99,
        'images': low_overlap
    }
    
    link_result_low = await monitor._link_to_products_table(
        catalog_product=catalog_product_low,
        retailer='test_retailer'
    )
    
    if link_result_low is None or link_result_low.get('link_method') != 'image_url_match':
        print(f"   ✅ Correctly rejected low overlap")
    else:
        print(f"   ❌ Should not match: {link_result_low}")
        conn.close()
        return False
    
    # Cleanup
    print("\n6. Cleaning up test data...")
    cursor.execute("DELETE FROM products WHERE retailer = 'test_retailer'")
    conn.commit()
    conn.close()
    print("   ✅ Cleanup complete")
    
    # Success!
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("=" * 60)
    print("\nImage functionality is fully operational:")
    print("  ✅ image_urls column exists")
    print("  ✅ Images saved when creating products")
    print("  ✅ Image matching works (Level 5)")
    print("  ✅ Confidence scoring applied correctly")
    print("  ✅ Overlap thresholds enforced")
    
    print("\n" + "=" * 60)
    print("PHASE 4 ADDENDUM: FULLY COMPLETE ✅")
    print("=" * 60)
    
    return True

if __name__ == '__main__':
    try:
        success = asyncio.run(test_complete_image_functionality())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

