# Catalog Monitor NULL Title Bug - Root Cause & Fix

**Date**: November 11, 2025  
**Severity**: Critical  
**Status**: ✅ Fixed

---

## 🐛 The Bug

**Symptom**: Both catalog monitors (dresses & tops) crashed with:
```
'NoneType' object has no attribute 'lower'
```

**Impact**: Catalog monitoring completely non-functional

---

## 🔍 Root Cause Analysis

### The Complete Bug Chain

1. **Product Updater** extracted titles correctly ✅
   - DeepSeek returned: "Runaway The Label Willem Maxi Dress in Zebra", etc.
   
2. **Batch Commit Bug** ❌
   - Line 698 in `product_updater.py`:
   ```python
   self.db_write_queue.append({
       'url': result.url,
       'data': result.__dict__,  # BUG!
       'action': result.action
   })
   ```
   - `result.__dict__` contains UpdateResult metadata (url, success, shopify_id, processing_time)
   - Does NOT contain product data (title, price, description, images)

3. **Database Update Failed** ❌
   - `batch_update_products()` tries: `data.get('title')` → Returns `None`
   - 1,360 out of 1,362 products end up with `title=NULL`

4. **Catalog Monitor Crash** ❌
   - Queries database, gets products with `title=None`
   - Line 634 in `catalog_monitor.py`:
   ```python
   candidate_title = candidate.get('title', '').lower().strip()
   ```
   - `candidate.get('title', '')` returns `None` (not empty string!)
     - **Why?** `.get(key, default)` only uses default if key doesn't exist
     - If key exists with value `None`, it returns `None`
   - `None.lower()` → `AttributeError: 'NoneType' object has no attribute 'lower'`

---

## 🔧 The Fixes

### Fix 1: Product Updater - Store Actual Product Data ✅

**File**: `Workflows/product_updater.py`

**Added field to UpdateResult**:
```python
@dataclass
class UpdateResult:
    ...
    product_data: Optional[Dict] = None  # NEW: Store extracted product data
```

**Updated successful return** (line 445):
```python
return UpdateResult(
    ...
    product_data=extraction_result.data  # CRITICAL: Include actual product data
)
```

**Fixed batch queue** (line 701):
```python
self.db_write_queue.append({
    'url': result.url,
    'data': result.product_data or {},  # FIXED: Use actual product data
    'action': result.action
})
```

---

### Fix 2: Catalog Monitor - Defensive None Handling ✅

**File**: `Workflows/catalog_monitor.py`

**Pattern used** (lines 604, 628, 635):
```python
# Before (vulnerable):
title_normalized = title.lower().strip()

# After (defensive):
title_normalized = (title or '').lower().strip()
if not title_normalized:
    return None
```

**Why this works**:
```python
# If title is None:
title or ''  # Returns ''
''.lower()   # Returns '' (no error!)

# If title exists:
title or ''  # Returns title
title.lower()  # Works normally
```

---

## 📊 Database State

**Current State**:
- 1,360 products have `title=NULL`
- 2 products have titles (from test data)
- Products updated on Nov 11, 2025 have NULL titles despite successful extraction

**Why Titles Are NULL**:
- Product Updater batch commit didn't pass actual product data
- Database UPDATE ran with `title=None`

---

## ✅ Verification

**Test 1: Manual Update Works**:
```python
cursor.execute("UPDATE products SET title=? WHERE url=?", (new_title, url))
# ✅ Works fine - DB column is functional
```

**Test 2: update_product_record() Works**:
```python
await db.update_product_record(url, {'title': 'Test'}, datetime.utcnow())
# ✅ Works fine - Function is correct
```

**Test 3: Batch Update Failed**:
```python
data = result.__dict__  # Has: url, success, shopify_id, processing_time
data.get('title')  # Returns None - no title in UpdateResult!
```

---

## 🔄 Backfill Strategy

**Option A: Re-run Product Updater** (Preferred)
- With fix in place, titles will now save correctly
- Natural backfill through normal workflow

**Option B: Extract from Shopify**
- Query Shopify API for all product titles
- Update local DB to match
- More complex, but faster

**Option C: Parse from URLs**
- Some title info in product URLs
- Unreliable, not recommended

**Recommendation**: Option A - Re-run Product Updater on affected products

---

## 🎯 Lessons Learned

### 1. Batch Operations Need Explicit Data Passing
**Problem**: Assumed `result.__dict__` would have product data  
**Solution**: Explicitly store and pass product data

### 2. Defensive Programming for Database Values
**Problem**: Assumed `.get(key, default)` would handle None values  
**Reality**: Default only applies if key doesn't exist, not if value is None  
**Solution**: Use `value or default` pattern

### 3. Test Batch Operations Separately
**Problem**: Individual updates worked, batch updates didn't  
**Solution**: Test both code paths independently

---

## 📁 Files Modified

1. **`Workflows/product_updater.py`**
   - Added `product_data` field to UpdateResult
   - Updated successful returns to include extraction data
   - Fixed batch queue to use product_data instead of __dict__

2. **`Workflows/catalog_monitor.py`**
   - Added defensive None handling in 3 places
   - Pattern: `(value or '').lower()` with empty check

---

## 🧪 Testing Required

**Before Production**:
1. Run Product Updater on 10-20 products
2. Verify titles are saved to database
3. Run Catalog Monitor to confirm no crashes
4. Check database: `SELECT url, title FROM products LIMIT 10`

**Success Criteria**:
- ✅ Product Updater saves titles to DB
- ✅ Catalog Monitor doesn't crash on None titles
- ✅ New products discovered correctly

---

**Status**: ✅ Fixes implemented, ready for testing  
**Next Step**: Test with small batch, then full backfill
