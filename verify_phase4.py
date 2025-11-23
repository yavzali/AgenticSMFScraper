#!/usr/bin/env python3
"""
Verification script for Phase 4: Catalog Monitor Updates
Tests snapshot saving, price change detection, and lifecycle tracking
"""

import sys
import os
sys.path.append('Shared')
sys.path.append('Workflows')

import sqlite3
import asyncio
from datetime import datetime
from db_manager import DatabaseManager

async def test_phase4_methods():
    """Test the new Phase 4 methods directly"""
    
    print("=" * 60)
    print("PHASE 4: CATALOG MONITOR VERIFICATION")
    print("=" * 60)
    
    # Import catalog monitor
    from catalog_monitor import CatalogMonitor
    
    monitor = CatalogMonitor()
    db = monitor.db_manager
    
    # Test 1: Test _save_catalog_snapshot
    print("\n1. Testing _save_catalog_snapshot method...")
    test_catalog_products = [
        {
            'url': 'https://test.com/snapshot1',
            'title': 'Snapshot Test Product 1',
            'price': 99.99,
            'product_code': 'SNAP-001',
            'images': ['img1.jpg', 'img2.jpg']
        },
        {
            'url': 'https://test.com/snapshot2',
            'title': 'Snapshot Test Product 2',
            'price': 89.99,
            'product_code': 'SNAP-002',
            'images': ['img3.jpg']
        }
    ]
    
    await monitor._save_catalog_snapshot(
        catalog_products=test_catalog_products,
        retailer='test_retailer',
        category='dresses',
        modesty_level='modest'
    )
    
    # Verify snapshots saved
    conn = db._get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT scan_type, COUNT(*) 
        FROM catalog_products 
        WHERE retailer = 'test_retailer' 
        AND catalog_url IN (?, ?)
        GROUP BY scan_type
    """, (test_catalog_products[0]['url'], test_catalog_products[1]['url']))
    
    result = cursor.fetchall()
    if result and result[0][0] == 'monitor' and result[0][1] == 2:
        print("   ✅ Snapshots saved with scan_type='monitor'")
    else:
        print(f"   ❌ Snapshot save failed: {result}")
        return False
    
    # Test 2: Test _detect_price_changes
    print("\n2. Testing _detect_price_changes method...")
    
    # First, add a product to products table with a price
    await db.save_product(
        url='https://test.com/price-test',
        retailer='test_retailer',
        product_data={
            'url': 'https://test.com/price-test',
            'title': 'Price Test Product',
            'price': 100.00,
            'retailer': 'test_retailer'
        },
        source='test'
    )
    
    # Now simulate catalog showing different price
    catalog_with_price_change = [
        {
            'url': 'https://test.com/price-test',
            'title': 'Price Test Product',
            'price': 79.99  # Price changed from 100.00
        }
    ]
    
    price_changes = await monitor._detect_price_changes(
        catalog_products=catalog_with_price_change,
        retailer='test_retailer'
    )
    
    if price_changes == 1:
        print(f"   ✅ Price change detected: {price_changes}")
    else:
        print(f"   ❌ Price change detection failed: {price_changes}")
        return False
    
    # Verify price change in queue
    cursor.execute("""
        SELECT product_url, catalog_price, products_price, price_difference
        FROM product_update_queue
        WHERE product_url = 'https://test.com/price-test'
        ORDER BY detected_at DESC
        LIMIT 1
    """)
    
    queue_result = cursor.fetchone()
    if queue_result:
        print(f"   ✅ Price change queued: ${queue_result[2]} → ${queue_result[1]} (diff: ${queue_result[3]})")
    else:
        print("   ❌ Price change not in queue")
        return False
    
    # Test 3: Test _link_to_products_table
    print("\n3. Testing _link_to_products_table method...")
    
    # Add a product to products table
    await db.save_product(
        url='https://test.com/link-test',
        retailer='test_retailer',
        product_data={
            'url': 'https://test.com/link-test',
            'title': 'Link Test Product',
            'price': 89.99,
            'product_code': 'LINK-001',
            'retailer': 'test_retailer'
        },
        source='test'
    )
    
    # Try to link a catalog product
    catalog_product = {
        'url': 'https://test.com/link-test',
        'title': 'Link Test Product',
        'price': 89.99,
        'product_code': 'LINK-001'
    }
    
    link_result = await monitor._link_to_products_table(
        catalog_product=catalog_product,
        retailer='test_retailer'
    )
    
    if link_result and link_result['link_confidence'] == 1.0:
        print(f"   ✅ Linked via {link_result['link_method']} (confidence: {link_result['link_confidence']})")
    else:
        print(f"   ❌ Linking failed: {link_result}")
        return False
    
    # Test 4: Verify lifecycle fields in save_product
    print("\n4. Testing lifecycle fields in products...")
    
    await db.save_product(
        url='https://test.com/lifecycle-test',
        retailer='test_retailer',
        product_data={
            'url': 'https://test.com/lifecycle-test',
            'title': 'Lifecycle Test',
            'price': 99.99,
            'retailer': 'test_retailer'
        },
        source='monitor',
        lifecycle_stage='pending_assessment',
        data_completeness='full',
        last_workflow='catalog_monitor',
        extracted_at=datetime.utcnow().isoformat()
    )
    
    cursor.execute("""
        SELECT lifecycle_stage, data_completeness, last_workflow, extracted_at
        FROM products
        WHERE url = 'https://test.com/lifecycle-test'
    """)
    
    lifecycle_result = cursor.fetchone()
    if lifecycle_result and lifecycle_result[0] == 'pending_assessment':
        print(f"   ✅ Lifecycle fields set correctly:")
        print(f"      lifecycle_stage: {lifecycle_result[0]}")
        print(f"      data_completeness: {lifecycle_result[1]}")
        print(f"      last_workflow: {lifecycle_result[2]}")
        print(f"      extracted_at: {lifecycle_result[3]}")
    else:
        print(f"   ❌ Lifecycle fields not set: {lifecycle_result}")
        return False
    
    # Cleanup
    print("\n5. Cleaning up test data...")
    cursor.execute("DELETE FROM catalog_products WHERE retailer = 'test_retailer'")
    cursor.execute("DELETE FROM products WHERE retailer = 'test_retailer'")
    cursor.execute("DELETE FROM product_update_queue WHERE retailer = 'test_retailer'")
    conn.commit()
    conn.close()
    print("   ✅ Cleanup complete")
    
    # Success summary
    print("\n" + "=" * 60)
    print("SUCCESS CRITERIA")
    print("=" * 60)
    print("✅ _save_catalog_snapshot saves with scan_type='monitor'")
    print("✅ _detect_price_changes detects and queues price changes")
    print("✅ _link_to_products_table performs multi-level matching")
    print("✅ save_product accepts and stores lifecycle fields")
    print("✅ All new methods work without errors")
    
    print("\n" + "=" * 60)
    print("✅ PHASE 4 VERIFICATION PASSED")
    print("=" * 60)
    print("\n→ Ready for live test with: python3 -m Workflows.catalog_monitor revolve dresses modest --max-pages 1")
    
    return True

if __name__ == '__main__':
    try:
        success = asyncio.run(test_phase4_methods())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ VERIFICATION FAILED WITH ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

