# Deduplication & NULL Title Issues - Full Diagnosis

## Issue 1: NULL Title Bug in Product Updater ❌ NOT FIXED

### Current Code (`db_manager.py` lines 435-452)
```python
# Full update
cursor.execute('''
    UPDATE products 
    SET title = ?,
        price = ?,
        sale_status = ?,
        stock_status = ?,
        last_updated = ?,
        last_checked = ?
    WHERE url = ?
''', (
    data.get('title'),        # ⚠️ CAN BE NULL!
    data.get('price'),         # ⚠️ CAN BE NULL!
    data.get('sale_status', 'regular'),
    data.get('stock_status', 'in_stock'),
    datetime.utcnow().isoformat(),
    datetime.utcnow().isoformat(),
    url
))
```

### The Problem
- `data.get('title')` returns `None` if the `'title'` key is missing or has a `None` value
- SQL `UPDATE SET title = NULL` overwrites the existing title with NULL
- This happened to 1,350 products during Product Updater run

### Root Cause
The Product Updater batch commit code passes incomplete `data` dicts to `batch_update_products()`. When extraction succeeds but certain fields aren't populated, those fields become NULL in the database.

### Fix Required
**Option A:** Only update non-NULL fields
```python
# Build dynamic UPDATE query
update_fields = []
update_values = []

if data.get('title'):
    update_fields.append('title = ?')
    update_values.append(data.get('title'))

if data.get('price'):
    update_fields.append('price = ?')
    update_values.append(data.get('price'))

# ... etc

query = f"UPDATE products SET {', '.join(update_fields)} WHERE url = ?"
cursor.execute(query, update_values + [url])
```

**Option B:** Ensure Product Updater always provides complete data
- Product Updater should validate extraction results before calling batch_update
- If required fields are missing, log error and skip that product

---

## Issue 2: Deduplication Completely Failing ❌ BROKEN

### What Should Have Happened
- Catalog Monitor scanned 106 Revolve products
- 1,362 Revolve products exist in database
- Should have matched most as "confirmed_existing"
- **Actual result:** 0 matches, all 106 marked as "NEW"

### Root Cause Analysis

#### **Strategy 1: Exact URL Match** ❌
- **Incoming:** `https://www.revolve.com/.../dp/CODE/` (clean, from catalog extraction)
- **Stored:** `https://www.revolve.com/.../dp/CODE/?d=Womens&page=1&lc=3&plpSrc=...` (with params)
- **Result:** No match (different strings)

#### **Strategy 2: Normalized URL Match** ❌ BROKEN CODE
**Current code (`db_manager.py` lines 608-611):**
```python
cursor.execute('''
    SELECT * FROM products 
    WHERE retailer = ? AND url LIKE ?
    LIMIT 1
''', (retailer, f"%{normalized_url}%"))
```

**The Bug:**
- Query: `url LIKE '%https://www.revolve.com/.../dp/CODE/%'`
- Stored URL: `https://www.revolve.com/.../dp/CODE/?d=Womens&page=1...`
- **FAILS** because LIKE expects the normalized URL to be a substring
- But the trailing `%` in the LIKE pattern expects MORE content after the normalized URL
- The stored URL has `/?params...` not just `/`

**Why It's Broken:**
The LIKE pattern `'%normalized_url%'` will match if the stored URL contains the normalized URL **anywhere**. But:
1. Normalized URL: `https://www.revolve.com/.../dp/CODE/` (ends with `/`)
2. Stored URL: `https://www.revolve.com/.../dp/CODE/?params` (has `?` after `/`)
3. `LIKE '%...CODE/%'` won't match `...CODE/?params` because the `?` breaks the pattern

**Correct Fix:**
```python
# Strip everything after '?' from stored URL, then compare
cursor.execute('''
    SELECT * FROM products 
    WHERE retailer = ? 
    AND (
        CASE 
            WHEN INSTR(url, '?') > 0 
            THEN SUBSTR(url, 1, INSTR(url, '?') - 1)
            ELSE url 
        END
    ) = ?
    LIMIT 1
''', (retailer, normalized_url.rstrip('/')))
```

OR store a `normalized_url` column (like old architecture did).

#### **Strategy 3: Product Code Match** ❓ SHOULD WORK
- Product codes ARE stored: `RUNR-WD126`, `CELR-WD169`, etc. ✅
- Extraction function exists and works for Revolve ✅
- **But:** Need to verify catalog extractor is actually populating `product_code` field

**Likely Issue:** Catalog extraction returns products with URLs but **without** `product_code` field populated. The `_extract_product_code()` function is only called in `_check_product_code_match` if `product.get('product_code')` is None, which should work... but need to verify.

---

## Comparison with Old Architecture

### Old Architecture (Hash: 621349b)
The old system had a `catalog_db_manager.py` with:
1. **Stored `normalized_url` as a separate column** in the database
2. Direct equality comparison on `normalized_url` column (not LIKE pattern matching)
3. Simpler, more reliable deduplication

### Current Architecture
- Tries to be clever with LIKE patterns
- Doesn't store normalized URLs
- More complex multi-strategy deduplication (6 levels)
- **But the fundamental URL normalization comparison is broken**

---

## Recommended Fixes (In Order of Priority)

### 1. Fix `batch_update_products` NULL title bug
**Priority:** HIGH (prevents data corruption)
**Effort:** Low
**Action:** Only update fields that are present and non-NULL in `data` dict

### 2. Fix `find_product_by_normalized_url` LIKE query bug
**Priority:** CRITICAL (dedup completely broken)
**Effort:** Low
**Action:** Use SUBSTR/INSTR to normalize stored URLs before comparison

### 3. Add `normalized_url` column to `products` table (like old architecture)
**Priority:** MEDIUM (performance + reliability)
**Effort:** Medium
**Action:** 
- Add column
- Backfill for existing products
- Update all save/update operations to populate it
- Change dedup query to use column directly

### 4. Verify catalog extraction populates `product_code`
**Priority:** HIGH (backup dedup strategy)
**Effort:** Low
**Action:** Add logging to verify product codes are extracted during catalog scan

---

## Testing Plan

### After Fixes:
1. Run Catalog Monitor on Revolve with 10 products
2. Verify deduplication finds existing products
3. Verify NULL titles don't get created
4. Run full Catalog Monitor on Revolve dresses + tops
5. Verify ~1,300 products are matched as "confirmed_existing"
6. Verify only truly NEW products are sent to assessment pipeline

---

**Status:** Both issues diagnosed, fixes identified, awaiting user approval to proceed.

