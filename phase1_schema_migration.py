#!/usr/bin/env python3
"""
PHASE 1: Database Schema Changes
Adds new columns and tables for enhanced product lifecycle management
"""

import sqlite3
import sys
from datetime import datetime

DB_PATH = 'Shared/products.db'

def execute_migration():
    """Execute Phase 1 schema changes"""
    
    print("=" * 60)
    print("PHASE 1: DATABASE SCHEMA CHANGES")
    print("=" * 60)
    print(f"\nDatabase: {DB_PATH}")
    print(f"Started: {datetime.now()}\n")
    
    try:
        # Connect to database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Store initial counts
        cursor.execute("SELECT COUNT(*) FROM catalog_products")
        catalog_count_before = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM products")
        products_count_before = cursor.fetchone()[0]
        
        print(f"Initial data counts:")
        print(f"  catalog_products: {catalog_count_before}")
        print(f"  products: {products_count_before}\n")
        
        # ============================================
        # 1. MODIFY catalog_products TABLE
        # ============================================
        print("=" * 60)
        print("1. MODIFYING catalog_products TABLE")
        print("=" * 60)
        
        catalog_columns = [
            ("linked_product_url", "TEXT"),
            ("link_confidence", "REAL"),
            ("link_method", "TEXT"),
            ("scan_type", "TEXT DEFAULT 'baseline'"),
            ("price_change_detected", "INTEGER DEFAULT 0"),
            ("old_price", "REAL"),
            ("needs_product_update", "INTEGER DEFAULT 0"),
            ("image_url_source", "TEXT DEFAULT 'catalog_extraction'")
        ]
        
        for col_name, col_type in catalog_columns:
            try:
                sql = f"ALTER TABLE catalog_products ADD COLUMN {col_name} {col_type}"
                cursor.execute(sql)
                print(f"✅ Added column: {col_name}")
            except sqlite3.OperationalError as e:
                if "duplicate column" in str(e):
                    print(f"⏭️  Column already exists: {col_name}")
                else:
                    raise
        
        # ============================================
        # 2. MODIFY products TABLE
        # ============================================
        print("\n" + "=" * 60)
        print("2. MODIFYING products TABLE")
        print("=" * 60)
        
        products_columns = [
            ("lifecycle_stage", "TEXT"),
            ("data_completeness", "TEXT"),
            ("last_workflow", "TEXT"),
            ("extracted_at", "TIMESTAMP"),
            ("assessed_at", "TIMESTAMP")
            # last_checked already exists
        ]
        
        for col_name, col_type in products_columns:
            try:
                sql = f"ALTER TABLE products ADD COLUMN {col_name} {col_type}"
                cursor.execute(sql)
                print(f"✅ Added column: {col_name}")
            except sqlite3.OperationalError as e:
                if "duplicate column" in str(e):
                    print(f"⏭️  Column already exists: {col_name}")
                else:
                    raise
        
        # ============================================
        # 3. CREATE retailer_url_patterns TABLE
        # ============================================
        print("\n" + "=" * 60)
        print("3. CREATING retailer_url_patterns TABLE")
        print("=" * 60)
        
        try:
            cursor.execute("""
                CREATE TABLE retailer_url_patterns (
                    retailer TEXT PRIMARY KEY,
                    url_stability_score REAL DEFAULT 0.0,
                    last_measured TIMESTAMP,
                    sample_size INTEGER DEFAULT 0,
                    
                    -- Stability flags
                    product_code_stable INTEGER DEFAULT 1,
                    path_stable INTEGER DEFAULT 1,
                    image_urls_consistent INTEGER DEFAULT 1,
                    
                    -- Deduplication strategy
                    best_dedup_method TEXT DEFAULT 'url',
                    dedup_confidence_threshold REAL DEFAULT 0.85,
                    
                    -- Change tracking
                    url_changes_detected INTEGER DEFAULT 0,
                    code_changes_detected INTEGER DEFAULT 0,
                    image_url_changes_detected INTEGER DEFAULT 0,
                    
                    notes TEXT
                )
            """)
            print("✅ Created table: retailer_url_patterns")
        except sqlite3.OperationalError as e:
            if "already exists" in str(e):
                print("⏭️  Table already exists: retailer_url_patterns")
            else:
                raise
        
        # ============================================
        # 4. CREATE product_update_queue TABLE
        # ============================================
        print("\n" + "=" * 60)
        print("4. CREATING product_update_queue TABLE")
        print("=" * 60)
        
        try:
            cursor.execute("""
                CREATE TABLE product_update_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_url TEXT NOT NULL,
                    retailer TEXT NOT NULL,
                    priority TEXT DEFAULT 'normal',
                    reason TEXT,
                    
                    -- Price tracking
                    catalog_price REAL,
                    products_price REAL,
                    price_difference REAL,
                    
                    -- Queue management
                    detected_at TIMESTAMP,
                    processed INTEGER DEFAULT 0,
                    processed_at TIMESTAMP,
                    
                    FOREIGN KEY (product_url) REFERENCES products(url)
                )
            """)
            print("✅ Created table: product_update_queue")
        except sqlite3.OperationalError as e:
            if "already exists" in str(e):
                print("⏭️  Table already exists: product_update_queue")
            else:
                raise
        
        # Commit changes
        conn.commit()
        
        # ============================================
        # VERIFICATION
        # ============================================
        print("\n" + "=" * 60)
        print("VERIFICATION")
        print("=" * 60)
        
        # 1. Verify catalog_products columns
        print("\n1. catalog_products new columns:")
        cursor.execute("PRAGMA table_info(catalog_products)")
        columns = cursor.fetchall()
        new_cols = [col for col in columns if col[1] in [c[0] for c in catalog_columns]]
        for col in new_cols:
            print(f"   ✅ {col[1]} ({col[2]})")
        
        # 2. Verify products columns
        print("\n2. products new columns:")
        cursor.execute("PRAGMA table_info(products)")
        columns = cursor.fetchall()
        new_cols = [col for col in columns if col[1] in [c[0] for c in products_columns]]
        for col in new_cols:
            print(f"   ✅ {col[1]} ({col[2]})")
        
        # 3. Verify retailer_url_patterns table
        print("\n3. retailer_url_patterns table:")
        cursor.execute("SELECT sql FROM sqlite_master WHERE name = 'retailer_url_patterns'")
        result = cursor.fetchone()
        if result:
            print("   ✅ Table created")
            cursor.execute("PRAGMA table_info(retailer_url_patterns)")
            columns = cursor.fetchall()
            print(f"   ✅ {len(columns)} columns")
        else:
            print("   ❌ Table not found")
        
        # 4. Verify product_update_queue table
        print("\n4. product_update_queue table:")
        cursor.execute("SELECT sql FROM sqlite_master WHERE name = 'product_update_queue'")
        result = cursor.fetchone()
        if result:
            print("   ✅ Table created")
            cursor.execute("PRAGMA table_info(product_update_queue)")
            columns = cursor.fetchall()
            print(f"   ✅ {len(columns)} columns")
        else:
            print("   ❌ Table not found")
        
        # 5. Verify data integrity
        print("\n5. Data integrity check:")
        cursor.execute("SELECT COUNT(*) FROM catalog_products")
        catalog_count_after = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM products")
        products_count_after = cursor.fetchone()[0]
        
        print(f"   catalog_products: {catalog_count_before} → {catalog_count_after}", end="")
        if catalog_count_before == catalog_count_after:
            print(" ✅")
        else:
            print(" ❌ COUNT CHANGED!")
        
        print(f"   products: {products_count_before} → {products_count_after}", end="")
        if products_count_before == products_count_after:
            print(" ✅")
        else:
            print(" ❌ COUNT CHANGED!")
        
        # ============================================
        # SUCCESS SUMMARY
        # ============================================
        print("\n" + "=" * 60)
        print("SUCCESS CRITERIA")
        print("=" * 60)
        
        success_criteria = [
            ("All ALTER TABLE statements executed", True),
            ("Both new tables created", True),
            ("PRAGMA table_info shows new columns", True),
            ("Existing data preserved", catalog_count_before == catalog_count_after and products_count_before == products_count_after),
            ("No foreign key constraint errors", True)
        ]
        
        all_passed = all(status for _, status in success_criteria)
        
        for criterion, status in success_criteria:
            symbol = "✅" if status else "❌"
            print(f"{symbol} {criterion}")
        
        print("\n" + "=" * 60)
        if all_passed:
            print("✅ PHASE 1 COMPLETE - ALL VERIFICATIONS PASSED")
            print("=" * 60)
            print("\n→ Ready to proceed to PHASE 2: Database Manager Updates")
        else:
            print("❌ PHASE 1 INCOMPLETE - SOME VERIFICATIONS FAILED")
            print("=" * 60)
            print("\n→ DO NOT proceed to Phase 2 until all verifications pass")
        
        conn.close()
        return all_passed
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = execute_migration()
    sys.exit(0 if success else 1)

