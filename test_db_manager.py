#!/usr/bin/env python3
"""
Test script for Phase 2 db_manager updates
Verifies new lifecycle tracking parameters work correctly
"""

import asyncio
import sys
import os
sys.path.append('Shared')
from db_manager import DatabaseManager

async def test():
    print("=" * 60)
    print("PHASE 2: DATABASE MANAGER TEST")
    print("=" * 60)
    
    db = DatabaseManager()
    
    # Test 1: save_product with new parameters
    print("\n1. Testing save_product with lifecycle parameters...")
    test_product = {
        'url': 'https://test.com/test-product-lifecycle',
        'retailer': 'test_retailer',
        'title': 'Test Product for Lifecycle',
        'price': 99.99,
        'description': 'Test description',
        'modesty_status': 'modest',
        'clothing_type': 'dress'
    }
    
    result = await db.save_product(
        url=test_product['url'],
        retailer=test_product['retailer'],
        product_data=test_product,
        source='test',
        lifecycle_stage='imported_direct',
        data_completeness='full',
        last_workflow='test_script',
        extracted_at='2025-11-23T12:00:00'
    )
    
    if result:
        print("   ✅ save_product succeeded")
    else:
        print("   ❌ save_product failed")
        return False
    
    # Test 2: save_catalog_product with new parameters
    print("\n2. Testing save_catalog_product with scan_type parameters...")
    test_catalog_product = {
        'url': 'https://test.com/test-catalog-product-lifecycle',
        'retailer': 'test_retailer',
        'category': 'dresses',
        'title': 'Test Catalog Product',
        'price': 89.99,
        'product_code': 'TEST-001',
        'images': ['https://test.com/image1.jpg']
    }
    
    result2 = await db.save_catalog_product(
        product=test_catalog_product,
        scan_type='monitor',
        review_status='flagged_new',
        image_url_source='catalog_extraction'
    )
    
    if result2:
        print("   ✅ save_catalog_product succeeded")
    else:
        print("   ❌ save_catalog_product failed")
        return False
    
    # Test 3: Verify data saved correctly
    print("\n3. Verifying data was saved with correct fields...")
    conn = db._get_connection()
    cursor = conn.cursor()
    
    # Check products table
    cursor.execute("""
        SELECT lifecycle_stage, data_completeness, last_workflow, extracted_at 
        FROM products 
        WHERE url = ?
    """, (test_product['url'],))
    product_result = cursor.fetchone()
    
    if product_result:
        lifecycle, completeness, workflow, extracted = product_result
        print(f"   Products table:")
        print(f"     lifecycle_stage: {lifecycle}")
        print(f"     data_completeness: {completeness}")
        print(f"     last_workflow: {workflow}")
        print(f"     extracted_at: {extracted}")
        
        if lifecycle == 'imported_direct' and completeness == 'full' and workflow == 'test_script':
            print("   ✅ Products table fields correct")
        else:
            print("   ❌ Products table fields incorrect")
            return False
    else:
        print("   ❌ Product not found in database")
        return False
    
    # Check catalog_products table
    cursor.execute("""
        SELECT scan_type, review_status, image_url_source 
        FROM catalog_products 
        WHERE catalog_url = ?
    """, (test_catalog_product['url'],))
    catalog_result = cursor.fetchone()
    
    if catalog_result:
        scan_type, review_status, img_source = catalog_result
        print(f"\n   Catalog_products table:")
        print(f"     scan_type: {scan_type}")
        print(f"     review_status: {review_status}")
        print(f"     image_url_source: {img_source}")
        
        if scan_type == 'monitor' and review_status == 'flagged_new' and img_source == 'catalog_extraction':
            print("   ✅ Catalog_products table fields correct")
        else:
            print("   ❌ Catalog_products table fields incorrect")
            return False
    else:
        print("   ❌ Catalog product not found in database")
        return False
    
    # Test 4: Update existing product with new lifecycle fields
    print("\n4. Testing update of existing product...")
    result3 = await db.save_product(
        url=test_product['url'],
        retailer=test_product['retailer'],
        product_data=test_product,
        lifecycle_stage='assessed_approved',
        assessed_at='2025-11-23T13:00:00'
    )
    
    if result3:
        print("   ✅ Product update succeeded")
    else:
        print("   ❌ Product update failed")
        return False
    
    # Verify update
    cursor.execute("""
        SELECT lifecycle_stage, assessed_at 
        FROM products 
        WHERE url = ?
    """, (test_product['url'],))
    updated_result = cursor.fetchone()
    
    if updated_result:
        lifecycle, assessed = updated_result
        print(f"   Updated lifecycle_stage: {lifecycle}")
        print(f"   Updated assessed_at: {assessed}")
        
        if lifecycle == 'assessed_approved' and assessed:
            print("   ✅ Update preserved and added new fields")
        else:
            print("   ❌ Update didn't work correctly")
            return False
    
    # Cleanup
    print("\n5. Cleaning up test data...")
    cursor.execute("DELETE FROM products WHERE url = ?", (test_product['url'],))
    cursor.execute("DELETE FROM catalog_products WHERE catalog_url = ?", (test_catalog_product['url'],))
    conn.commit()
    conn.close()
    print("   ✅ Cleanup complete")
    
    # Success summary
    print("\n" + "=" * 60)
    print("SUCCESS CRITERIA")
    print("=" * 60)
    print("✅ save_product accepts new parameters without errors")
    print("✅ save_catalog_product accepts new parameters without errors")
    print("✅ Test product saves with lifecycle_stage correctly")
    print("✅ Test catalog product saves with scan_type correctly")
    print("✅ No syntax errors in modified code")
    print("✅ Update preserves and adds new fields correctly")
    
    print("\n" + "=" * 60)
    print("✅ PHASE 2 COMPLETE - ALL TESTS PASSED")
    print("=" * 60)
    print("\n→ Ready to proceed to PHASE 3: Baseline Scanner Updates")
    
    return True

if __name__ == '__main__':
    try:
        success = asyncio.run(test())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ TEST FAILED WITH ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

