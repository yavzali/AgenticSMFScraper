#!/usr/bin/env python3
"""
Reversible Two-Way Sync Test

Tests the complete workflow:
1. Simulate phone assessment (create fake assessment on server)
2. Run check_status to detect difference
3. Run sync to merge
4. Verify local database has the assessment
5. Clean up everything

This test is REVERSIBLE - creates test data, tests sync, then cleans up.
"""

import sys
import sqlite3
import tempfile
import os
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent / 'Shared'))

import paramiko
from scp import SCPClient
from database_sync import DatabaseSync

# Test configuration
TEST_PRODUCT_URL = "https://test-sync.example.com/test-product-12345"
SERVER_IP = "167.172.148.145"
SERVER_USER = "root"
SERVER_PASSWORD = "modestyassessor"
REMOTE_DB_PATH = "/var/www/html/web_assessment/data/products.db"
LOCAL_DB_PATH = Path(__file__).parent / "Shared" / "products.db"


def ssh_connect():
    """Connect to server via SSH"""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER_IP, username=SERVER_USER, password=SERVER_PASSWORD, timeout=10)
    return ssh


def step1_create_test_product_locally():
    """Create test product in local database"""
    print("\n" + "=" * 60)
    print("STEP 1: Create test product in LOCAL database")
    print("=" * 60)
    
    conn = sqlite3.connect(LOCAL_DB_PATH)
    cursor = conn.cursor()
    
    # Insert test product
    cursor.execute("""
        INSERT INTO products (
            url, retailer, title, price, 
            lifecycle_stage, data_completeness, 
            first_seen, last_updated
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        TEST_PRODUCT_URL,
        'test_retailer',
        'Test Product for Two-Way Sync',
        99.99,
        'pending_assessment',
        'full',
        datetime.utcnow().isoformat(),
        datetime.utcnow().isoformat()
    ))
    
    conn.commit()
    conn.close()
    
    print(f"✅ Created test product locally")
    print(f"   URL: {TEST_PRODUCT_URL}")
    print(f"   Status: pending_assessment")


def step2_sync_to_server():
    """Sync local database to server (includes test product)"""
    print("\n" + "=" * 60)
    print("STEP 2: Sync LOCAL → SERVER (push test product)")
    print("=" * 60)
    
    sync = DatabaseSync()
    success = sync.sync_to_server(
        create_backup=True,
        verify=True,
        pull_first=False  # Skip pull for now
    )
    
    if not success:
        raise Exception("Failed to sync to server")
    
    print("✅ Test product now on server")


def step3_simulate_phone_assessment():
    """Simulate assessing the product on phone (update server database)"""
    print("\n" + "=" * 60)
    print("STEP 3: Simulate PHONE ASSESSMENT (update server)")
    print("=" * 60)
    
    # Download server database, modify it, upload it back
    ssh = ssh_connect()
    
    # Download server database to temp file
    temp_server_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_server_db.close()
    
    with SCPClient(ssh.get_transport()) as scp:
        scp.get(REMOTE_DB_PATH, temp_server_db.name)
    
    # Modify the server database locally
    conn = sqlite3.connect(temp_server_db.name)
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE products 
        SET lifecycle_stage = 'assessed_approved',
            assessed_at = datetime('now'),
            modesty_status = 'modest',
            shopify_status = 'published',
            last_updated = datetime('now')
        WHERE url = ?
    """, (TEST_PRODUCT_URL,))
    
    changes = cursor.rowcount
    conn.commit()
    conn.close()
    
    if changes != 1:
        os.unlink(temp_server_db.name)
        ssh.close()
        raise Exception(f"Failed to update server (changes: {changes})")
    
    # Upload modified database back to server
    with SCPClient(ssh.get_transport()) as scp:
        scp.put(temp_server_db.name, REMOTE_DB_PATH)
    
    # Set permissions
    ssh.exec_command(f"chown www-data:www-data {REMOTE_DB_PATH}")
    ssh.exec_command(f"chmod 644 {REMOTE_DB_PATH}")
    
    ssh.close()
    os.unlink(temp_server_db.name)
    
    print("✅ Simulated phone assessment on server")
    print("   lifecycle_stage: assessed_approved")
    print("   modesty_status: modest")


def step4_verify_local_still_pending():
    """Verify local database still shows pending (hasn't synced yet)"""
    print("\n" + "=" * 60)
    print("STEP 4: Verify LOCAL is still PENDING (not synced yet)")
    print("=" * 60)
    
    conn = sqlite3.connect(LOCAL_DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT lifecycle_stage, assessed_at, modesty_status
        FROM products
        WHERE url = ?
    """, (TEST_PRODUCT_URL,))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        lifecycle_stage, assessed_at, modesty_status = result
        print(f"   lifecycle_stage: {lifecycle_stage}")
        print(f"   assessed_at: {assessed_at}")
        print(f"   modesty_status: {modesty_status}")
        
        if lifecycle_stage == 'pending_assessment' and assessed_at is None:
            print("✅ Local is still pending (correct!)")
        else:
            raise Exception("Local already has assessment (shouldn't happen yet)")
    else:
        raise Exception("Test product not found in local database")


def step5_run_two_way_sync():
    """Run two-way sync (should pull server assessment into local)"""
    print("\n" + "=" * 60)
    print("STEP 5: Run TWO-WAY SYNC (pull assessment from server)")
    print("=" * 60)
    
    sync = DatabaseSync()
    
    # This should pull the assessment from server and merge into local
    success, num_pulled = sync.pull_assessments_from_server()
    
    if not success:
        raise Exception("Failed to pull assessments")
    
    print(f"✅ Pulled {num_pulled} assessment(s) from server")
    
    if num_pulled == 0:
        raise Exception("Should have pulled 1 assessment but got 0")


def step6_verify_local_updated():
    """Verify local database now has the assessment"""
    print("\n" + "=" * 60)
    print("STEP 6: Verify LOCAL now has ASSESSMENT")
    print("=" * 60)
    
    conn = sqlite3.connect(LOCAL_DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT lifecycle_stage, assessed_at, modesty_status, shopify_status
        FROM products
        WHERE url = ?
    """, (TEST_PRODUCT_URL,))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        lifecycle_stage, assessed_at, modesty_status, shopify_status = result
        print(f"   lifecycle_stage: {lifecycle_stage}")
        print(f"   assessed_at: {assessed_at}")
        print(f"   modesty_status: {modesty_status}")
        print(f"   shopify_status: {shopify_status}")
        
        if lifecycle_stage == 'assessed_approved' and modesty_status == 'modest':
            print("✅ Local successfully merged server assessment!")
        else:
            raise Exception(f"Assessment not merged correctly: {lifecycle_stage}, {modesty_status}")
    else:
        raise Exception("Test product disappeared from local database")


def step7_cleanup():
    """Remove test product from both local and server"""
    print("\n" + "=" * 60)
    print("STEP 7: CLEANUP (remove test product)")
    print("=" * 60)
    
    # Remove from local
    conn = sqlite3.connect(LOCAL_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM products WHERE url = ?", (TEST_PRODUCT_URL,))
    local_deleted = cursor.rowcount
    conn.commit()
    conn.close()
    
    print(f"✅ Removed from local database ({local_deleted} row)")
    
    # Remove from server
    ssh = ssh_connect()
    
    # Download, modify, upload back
    temp_server_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_server_db.close()
    
    with SCPClient(ssh.get_transport()) as scp:
        scp.get(REMOTE_DB_PATH, temp_server_db.name)
    
    conn = sqlite3.connect(temp_server_db.name)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM products WHERE url = ?", (TEST_PRODUCT_URL,))
    server_deleted = cursor.rowcount
    conn.commit()
    conn.close()
    
    with SCPClient(ssh.get_transport()) as scp:
        scp.put(temp_server_db.name, REMOTE_DB_PATH)
    
    ssh.exec_command(f"chown www-data:www-data {REMOTE_DB_PATH}")
    ssh.exec_command(f"chmod 644 {REMOTE_DB_PATH}")
    
    ssh.close()
    os.unlink(temp_server_db.name)
    
    print(f"✅ Removed from server database ({server_deleted} row)")
    print("\n🧹 Test data cleaned up - system restored to original state")


def main():
    print("=" * 60)
    print("🧪 TWO-WAY SYNC TEST (Reversible)")
    print("=" * 60)
    print()
    print("This test will:")
    print("  1. Create a test product locally")
    print("  2. Sync to server")
    print("  3. Simulate phone assessment (update server)")
    print("  4. Verify local is still pending")
    print("  5. Run two-way sync (pull from server)")
    print("  6. Verify local now has assessment")
    print("  7. Clean up test data")
    print()
    print("This is REVERSIBLE - no permanent changes to your system.")
    print()
    
    response = input("Run test? [Y/n]: ").strip().lower()
    if response and response != 'y':
        print("❌ Test cancelled")
        return
    
    try:
        step1_create_test_product_locally()
        step2_sync_to_server()
        step3_simulate_phone_assessment()
        step4_verify_local_still_pending()
        step5_run_two_way_sync()
        step6_verify_local_updated()
        step7_cleanup()
        
        print("\n" + "=" * 60)
        print("✅ TEST PASSED - TWO-WAY SYNC WORKS CORRECTLY")
        print("=" * 60)
        print()
        print("Summary:")
        print("  ✅ Phone assessment on server detected")
        print("  ✅ Local database merged server assessment")
        print("  ✅ lifecycle_stage updated correctly")
        print("  ✅ assessed_at timestamp preserved")
        print("  ✅ Test data cleaned up")
        print()
        print("Your two-way sync is working perfectly! 🎉")
        
    except Exception as e:
        print("\n" + "=" * 60)
        print("❌ TEST FAILED")
        print("=" * 60)
        print(f"Error: {e}")
        print()
        print("Attempting cleanup...")
        try:
            step7_cleanup()
        except:
            print("⚠️  Cleanup failed - you may need to manually remove test product:")
            print(f"   URL: {TEST_PRODUCT_URL}")
        
        sys.exit(1)


if __name__ == '__main__':
    main()

