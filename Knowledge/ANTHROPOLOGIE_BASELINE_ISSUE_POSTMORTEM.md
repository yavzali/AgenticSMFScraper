# Anthropologie Baseline Migration Issue - Postmortem

**Date**: November 22, 2025  
**Issue**: 71 Anthropologie baseline products incorrectly migrated to assessment queue  
**Resolution**: All 71 removed from assessment queue  
**Status**: RESOLVED

---

## Summary

All 71 Anthropologie products in the assessment queue were baseline products from catalog scans, not genuinely new product detections. They were incorrectly migrated from the old system to the new assessment pipeline.

---

## Timeline

### Nov 6, 2025
- **Baseline scan performed** for Anthropologie
- Created 79 products with `review_status = 'baseline'`
- These are reference products for change detection, NOT for assessment

### Nov 13, 2025
- **Second scan performed** (likely another baseline, not a monitor scan)
- Created 71 products with `review_status = 'pending'`
- **BUG**: These should have been marked 'baseline', not 'pending'

### Nov 22, 2025 (During system consolidation)
- Migration script moved products with `review_status = 'pending'` to assessment_queue
- This included the 71 Nov 13 baseline products
- Initial cleanup removed 24 products (correctly identified as baseline)
- **Incorrectly concluded** 47 were "genuinely new"

### Nov 22, 2025 (Final cleanup)
- User correctly identified that NO catalog monitor was ever run for Anthropologie
- Verification confirmed: 0 products from `source='monitor'` in products table
- **All 71 removed** from assessment queue

---

## Root Cause Analysis

### What Went Wrong

1. **Baseline Scan Mislabeled Products**
   - Nov 13 baseline scan created products with `review_status = 'pending'`
   - Should have been `review_status = 'baseline'`
   - Likely caused by:
     - Bug in baseline scanner
     - Wrong parameters passed to baseline scan
     - Old system confusion between baseline and monitoring

2. **Migration Script Trusted Status Field**
   - Migration script assumed `review_status = 'pending'` meant "needs human review"
   - Did not verify if products were genuinely new or baseline
   - Did not check if catalog monitor had ever run for that retailer

3. **Initial Analysis Error**
   - Concluded 47 products were "genuinely new" based on:
     - Discovery date (Nov 13) different from Nov 6 baseline
     - No duplicate entries for same URLs
   - **Failed to verify**: Was Nov 13 a baseline scan or monitor scan?
   - **Failed to check**: Products table for `source='monitor'`

---

## How It Should Work

### Baseline Scan (catalog_baseline_scanner.py)
**Purpose**: Create reference snapshot for change detection  
**Action**:
1. Scan catalog (lightweight: URL, title, price)
2. Insert into `catalog_products` with `review_status = 'baseline'`
3. **NEVER** send to assessment queue
4. **NEVER** upload to Shopify

### Catalog Monitor (catalog_monitor.py)
**Purpose**: Detect NEW products not in baseline  
**Action**:
1. Scan catalog (lightweight)
2. Deduplicate against `catalog_products` baseline
3. For products NOT in baseline:
   - Full extraction (complete data)
   - Upload to Shopify as draft
   - Send to assessment queue with `source_workflow = 'catalog_monitor'`
4. Save to `products` table with `source = 'monitor'`

### Key Verification Points
- Products from monitor: `products.source = 'monitor'`
- Products in queue from monitor: `assessment_queue.source_workflow = 'catalog_monitor'`
- Baseline products: `catalog_products.review_status = 'baseline'`

---

## Verification Results

### Evidence No Monitor Was Run

```sql
-- Products table check
SELECT COUNT(*) FROM products 
WHERE retailer = 'anthropologie' AND source = 'monitor';
-- Result: 0

-- Assessment queue check  
SELECT COUNT(*) FROM assessment_queue
WHERE retailer = 'anthropologie' AND source_workflow = 'catalog_monitor';
-- Result: 0

-- All queue entries were from migration
SELECT source_workflow, COUNT(*) FROM assessment_queue
WHERE retailer = 'anthropologie' AND status = 'pending'
GROUP BY source_workflow;
-- Result: migration_from_catalog_products: 47 (now removed)
```

### Catalog Products Timeline

```
Nov 6:  79 products (review_status='baseline')
Nov 13: 71 products (review_status='migrated_to_new_system')
```

**Conclusion**: Nov 13 was another baseline scan (or re-scan), not a monitoring run.

---

## Cleanup Actions Taken

### Phase 1: Initial Cleanup
- Removed 24 products with `review_status = 'baseline'` AND `discovered_date = '2025-11-06'`

### Phase 2: Final Cleanup
- Verified no catalog monitor ever run for Anthropologie
- **Removed all 47 remaining products** (all were baseline)
- **Total removed**: 71 products

### Final State
- Assessment queue: 71 products (all Revolve)
- Anthropologie products: 0 (correctly removed)

---

## Prevention Measures

### 1. Baseline Scanner Fixes

**Add validation in catalog_baseline_scanner.py:**

```python
def _save_baseline_products(self, products, retailer):
    """Save baseline products with correct status"""
    for product in products:
        self.db.execute("""
            INSERT INTO catalog_products 
            (catalog_url, retailer, title, price, 
             review_status, discovered_date)
            VALUES (?, ?, ?, ?, 'baseline', CURRENT_TIMESTAMP)
        """, (product['url'], retailer, product['title'], product['price']))
    
    # Verify: NEVER set review_status to 'pending' in baseline scanner
    assert all(p['review_status'] == 'baseline' for p in products)
```

### 2. Migration Script Verification

**Add checks before migrating:**

```python
def migrate_pending_to_queue(retailer):
    # Check if catalog monitor was ever run
    monitor_count = db.execute(
        "SELECT COUNT(*) FROM products WHERE retailer=? AND source='monitor'",
        (retailer,)
    ).fetchone()[0]
    
    if monitor_count == 0:
        print(f"WARNING: No monitor run for {retailer}, skipping migration")
        return
    
    # Only migrate products from actual monitor runs
    # ...
```

### 3. Assessment Queue Validation

**Add to assessment_queue_manager.py:**

```python
def add_to_queue(self, product, retailer, source_workflow, **kwargs):
    # Verify source workflow is legitimate
    assert source_workflow in [
        'catalog_monitor',  # From catalog monitoring
        'new_product_importer',  # From manual import
        # NOT 'migration_from_catalog_products' (migration only)
    ]
    
    # Verify product is not baseline
    if self._is_baseline_product(product['url'], retailer):
        raise ValueError(f"Cannot queue baseline product: {product['url']}")
```

### 4. Catalog Monitor Source Tracking

**Ensure products table tracks source:**

```python
# In catalog_monitor.py
await self.db_manager.save_product(
    product_data,
    source='monitor',  # ✅ Always set for catalog monitor
    source_workflow='catalog_monitor'
)
```

---

## Lessons Learned

### ✅ What Worked
1. Multi-phase investigation approach
2. Verification queries to check data consistency
3. User's domain knowledge caught the error

### ❌ What Went Wrong
1. **Assumption without verification**: Assumed different discovery dates meant genuinely new
2. **Failed to check source fields**: Should have verified `products.source` and `assessment_queue.source_workflow`
3. **Trusted status field blindly**: Did not validate if 'pending' status was legitimate

### 🔧 Process Improvements
1. **Always verify source tracking**: Check `source` field before concluding products are new
2. **Question high numbers**: 47 "new" products is unusually high, should have raised red flag
3. **Test hypotheses**: When user suggests alternative explanation, verify with data
4. **Document assumptions**: Make explicit what we're assuming vs. what we've verified

---

## Related Documentation

- `PRODUCT_LIFECYCLE_MANAGEMENT.md` - Updated with correct baseline handling
- `CATALOG_BASELINE_SCANNER_GUIDE.md` - Baseline creation process
- `CATALOG_MONITOR_GUIDE.md` - Monitoring workflow

---

## Action Items

- [ ] Add validation to catalog_baseline_scanner.py (prevent 'pending' status)
- [ ] Add source verification to migration scripts
- [ ] Add baseline check to assessment_queue_manager.py
- [ ] Update PRODUCT_LIFECYCLE_MANAGEMENT.md with prevention measures
- [ ] Test baseline + monitor workflow for Anthropologie (when ready)

