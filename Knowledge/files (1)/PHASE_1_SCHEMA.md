# PHASE 1: DATABASE SCHEMA CHANGES

**Duration**: 5-10 minutes  
**Risk**: LOW (just adding columns/tables, no code changes)  
**Prerequisites**: None  
**Can rollback**: Yes (easily)

---

## OBJECTIVE

Add new columns and tables to support:
- Cross-table linking (catalog_products ↔ products)
- Lifecycle tracking (product state management)
- URL stability tracking (per retailer)
- Price change detection (priority queue)

---

## EXECUTION

Execute these SQL statements on `Shared/products.db`:

```sql
-- ============================================
-- 1. MODIFY catalog_products TABLE
-- ============================================

-- Cross-table linking fields
ALTER TABLE catalog_products ADD COLUMN linked_product_url TEXT;
ALTER TABLE catalog_products ADD COLUMN link_confidence REAL;
ALTER TABLE catalog_products ADD COLUMN link_method TEXT;

-- Scan type tracking (baseline vs monitor)
ALTER TABLE catalog_products ADD COLUMN scan_type TEXT DEFAULT 'baseline';

-- Price change detection
ALTER TABLE catalog_products ADD COLUMN price_change_detected INTEGER DEFAULT 0;
ALTER TABLE catalog_products ADD COLUMN old_price REAL;
ALTER TABLE catalog_products ADD COLUMN needs_product_update INTEGER DEFAULT 0;

-- Image source tracking
ALTER TABLE catalog_products ADD COLUMN image_url_source TEXT DEFAULT 'catalog_extraction';


-- ============================================
-- 2. MODIFY products TABLE
-- ============================================

-- Lifecycle tracking
ALTER TABLE products ADD COLUMN lifecycle_stage TEXT;
ALTER TABLE products ADD COLUMN data_completeness TEXT;
ALTER TABLE products ADD COLUMN last_workflow TEXT;
ALTER TABLE products ADD COLUMN extracted_at TIMESTAMP;
ALTER TABLE products ADD COLUMN assessed_at TIMESTAMP;
ALTER TABLE products ADD COLUMN last_checked TIMESTAMP;


-- ============================================
-- 3. CREATE retailer_url_patterns TABLE
-- ============================================

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
);


-- ============================================
-- 4. CREATE product_update_queue TABLE
-- ============================================

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
);
```

---

## VERIFICATION

After execution, run these verification queries:

```sql
-- 1. Verify catalog_products new columns
PRAGMA table_info(catalog_products);
-- Expected: Should show all 8 new columns

-- 2. Verify products new columns  
PRAGMA table_info(products);
-- Expected: Should show all 6 new columns

-- 3. Verify retailer_url_patterns table created
SELECT sql FROM sqlite_master WHERE name = 'retailer_url_patterns';
-- Expected: Should return CREATE TABLE statement

-- 4. Verify product_update_queue table created
SELECT sql FROM sqlite_master WHERE name = 'product_update_queue';
-- Expected: Should return CREATE TABLE statement

-- 5. Check existing data still intact
SELECT COUNT(*) FROM catalog_products;
SELECT COUNT(*) FROM products;
-- Expected: Same counts as before schema changes
```

---

## SHOW ME

After execution, show me:
1. ✅ Success message for each ALTER TABLE and CREATE TABLE
2. ✅ Results of all 5 verification queries
3. ✅ Any errors encountered (should be none)
4. ✅ Confirmation that existing data counts unchanged

---

## SUCCESS CRITERIA

✅ All ALTER TABLE statements executed without errors  
✅ Both new tables created successfully  
✅ PRAGMA table_info shows new columns  
✅ Existing data preserved (same row counts)  
✅ No foreign key constraint errors

---

## IF ERRORS OCCUR

**Error: "duplicate column name"**  
- Column already exists from previous attempt
- Safe to ignore, or DROP COLUMN first

**Error: "table already exists"**  
- Table created from previous attempt  
- Safe to DROP TABLE and re-create

**Error: "database is locked"**  
- Close any other connections to products.db
- Stop any running workflows

---

## NEXT STEP

After Phase 1 completes successfully:
→ Proceed to **Phase 2: Database Manager Updates**

DO NOT proceed to Phase 2 until all verifications pass.
