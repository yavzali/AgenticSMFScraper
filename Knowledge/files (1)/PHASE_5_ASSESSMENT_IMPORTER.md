# PHASE 5: ASSESSMENT & IMPORTER UPDATES

**Duration**: 20-25 minutes  
**Risk**: LOW (isolated changes, independent workflows)  
**Prerequisites**: Phase 1, 2 completed  
**Can rollback**: Yes (git revert)

---

## OBJECTIVE

Update assessment interface and new product importer to set lifecycle_stage:
1. Assessment approval → lifecycle_stage='assessed_approved'
2. Assessment rejection → lifecycle_stage='assessed_rejected'
3. New product import → lifecycle_stage='imported_direct'

**WHY SEPARATE**: These workflows are independent, can be done separately from monitor.

---

## FILES TO MODIFY

1. `web_assessment/api/submit_review.php`
2. `Workflows/new_product_importer.py`

---

## PART A: ASSESSMENT INTERFACE

### File: `web_assessment/api/submit_review.php`

### Change 1: Update Approved Products

**Location**: Find where products are approved (around line 50-100)

**Look for code like**:
```php
if ($decision === 'modest' || $decision === 'moderately_modest') {
    // Update products table
    $sql = "UPDATE products 
            SET modesty_status = ?,
                shopify_status = 'published'
            WHERE url = ?";
    // ...
}
```

**Modify to include lifecycle fields**:
```php
if ($decision === 'modest' || $decision === 'moderately_modest') {
    // Product approved - publish to Shopify and mark as assessed
    $sql = "UPDATE products 
            SET modesty_status = ?,
                shopify_status = 'published',
                lifecycle_stage = 'assessed_approved',
                assessed_at = ?
            WHERE url = ?";
    
    $stmt = $pdo->prepare($sql);
    $stmt->execute([
        $decision, 
        date('Y-m-d H:i:s'), 
        $product_url
    ]);
}
```

---

### Change 2: Update Rejected Products

**Location**: Same file, rejection branch (around line 100-150)

**Look for code like**:
```php
else {
    // Product rejected
    $sql = "UPDATE products 
            SET modesty_status = 'not_modest',
                shopify_status = 'draft'
            WHERE url = ?";
    // ...
}
```

**Modify to include lifecycle fields**:
```php
else {
    // Product rejected - keep as draft and mark as assessed
    $sql = "UPDATE products 
            SET modesty_status = 'not_modest',
                shopify_status = 'draft',
                lifecycle_stage = 'assessed_rejected',
                assessed_at = ?
            WHERE url = ?";
    
    $stmt = $pdo->prepare($sql);
    $stmt->execute([
        date('Y-m-d H:i:s'), 
        $product_url
    ]);
}
```

---

## PART B: NEW PRODUCT IMPORTER

### File: `Workflows/new_product_importer.py`

### Change: Modify Product Creation

**Location**: Find where products are saved (around line 400-500)

**Look for code like**:
```python
await self.db_manager.save_product(
    url=url,
    product_data=extraction_result.product_data,
    source='new_product_import',
    # ... other fields
)
```

**Modify to include lifecycle tracking**:
```python
await self.db_manager.save_product(
    url=url,
    product_data=extraction_result.product_data,
    source='new_product_import',
    lifecycle_stage='imported_direct',  # NEW - bypassed assessment
    data_completeness='full',  # NEW - has complete data
    last_workflow='new_product_importer',  # NEW - track source
    extracted_at=datetime.utcnow().isoformat(),  # NEW - timestamp
    # ... other existing fields
)
```

**Also add import at top if needed**:
```python
from datetime import datetime
```

---

## TESTING

### Test A: Assessment Interface

1. **Go to assessment interface**: http://assessmodesty.com/assess.php
2. **Review and approve one product** (select "Modest" or "Moderately Modest")
3. **Review and reject one product** (select "Not Modest")

**Verify in database**:
```sql
-- Check approved product
SELECT url, modesty_status, shopify_status, lifecycle_stage, assessed_at
FROM products
WHERE lifecycle_stage = 'assessed_approved'
ORDER BY assessed_at DESC
LIMIT 1;
-- Expected: lifecycle_stage='assessed_approved', assessed_at has timestamp

-- Check rejected product
SELECT url, modesty_status, shopify_status, lifecycle_stage, assessed_at
FROM products
WHERE lifecycle_stage = 'assessed_rejected'
ORDER BY assessed_at DESC
LIMIT 1;
-- Expected: lifecycle_stage='assessed_rejected', assessed_at has timestamp
```

---

### Test B: New Product Importer

Create a test batch file:

**Create**: `test_importer_batch.json`
```json
{
  "urls": [
    "https://www.revolve.com/test-product-lifecycle/dp/TEST-001/"
  ],
  "modesty_level": "modest",
  "retailer": "revolve"
}
```

**Run**:
```bash
cd "/Users/yav/Agent Modest Scraper System"
python3 -m Workflows.new_product_importer --batch test_importer_batch.json
```

**Verify**:
```sql
SELECT url, source, lifecycle_stage, data_completeness, last_workflow, extracted_at
FROM products
WHERE url LIKE '%TEST-001%';
-- Expected: lifecycle_stage='imported_direct', source='new_product_import'
```

---

## VERIFICATION QUERIES

After both tests:

```sql
-- 1. Lifecycle distribution
SELECT lifecycle_stage, COUNT(*) as count
FROM products
WHERE lifecycle_stage IS NOT NULL
GROUP BY lifecycle_stage;
-- Expected: Should show assessed_approved, assessed_rejected, imported_direct

-- 2. Recent assessments
SELECT 
    lifecycle_stage,
    COUNT(*) as count,
    MAX(assessed_at) as last_assessed
FROM products
WHERE assessed_at IS NOT NULL
GROUP BY lifecycle_stage;
-- Expected: Recent timestamps for assessed products

-- 3. Imported products
SELECT COUNT(*) as imported_direct
FROM products
WHERE lifecycle_stage = 'imported_direct';
-- Expected: Count of manually imported products

-- 4. Data completeness check
SELECT lifecycle_stage, data_completeness, COUNT(*)
FROM products
WHERE lifecycle_stage IN ('assessed_approved', 'assessed_rejected', 'imported_direct')
GROUP BY lifecycle_stage, data_completeness;
-- Expected: All should have data_completeness set
```

---

## SHOW ME

After execution, show me:
1. ✅ submit_review.php modifications (both approval and rejection)
2. ✅ new_product_importer.py modifications
3. ✅ Test A results (assessment interface test)
4. ✅ Test B results (importer test)
5. ✅ Results of all 4 verification queries
6. ✅ Any errors encountered

---

## SUCCESS CRITERIA

✅ Assessment approval sets lifecycle_stage='assessed_approved'  
✅ Assessment rejection sets lifecycle_stage='assessed_rejected'  
✅ assessed_at timestamp populated correctly  
✅ New product import sets lifecycle_stage='imported_direct'  
✅ No errors in PHP error log  
✅ No errors in Python execution

---

## IF ERRORS OCCUR

**Error: "no such column: lifecycle_stage" (PHP)**  
- Phase 1 not completed
- Go back and run schema changes

**Error: "no such column: lifecycle_stage" (Python)**  
- Phase 2 not completed
- db_manager.py doesn't accept new parameters

**Error: "Cannot modify header information" (PHP)**  
- Check for whitespace before <?php
- Check for echo statements before headers

**Error: "Undefined variable: pdo" (PHP)**  
- Database connection not established
- Check connection code earlier in file

---

## COMMIT

After successful verification:
```bash
git add web_assessment/api/submit_review.php
git add Workflows/new_product_importer.py
git commit -m "Phase 5: Update assessment and importer for lifecycle tracking"
```

---

## NEXT STEP

After Phase 5 completes successfully:
→ Proceed to **Phase 6: Backfill Existing Data**

DO NOT proceed until verification queries show lifecycle_stage working.
