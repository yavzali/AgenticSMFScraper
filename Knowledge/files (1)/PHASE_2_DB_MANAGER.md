# PHASE 2: DATABASE MANAGER UPDATES

**Duration**: 10-15 minutes  
**Risk**: LOW (foundation for other changes)  
**Prerequisites**: Phase 1 completed successfully  
**Can rollback**: Yes (git revert)

---

## OBJECTIVE

Update `db_manager.py` to support new database fields:
- Accept lifecycle_stage, data_completeness parameters
- Accept scan_type, image_url_source parameters
- Update INSERT/UPDATE statements with new fields

**WHY THIS FIRST**: All workflows depend on db_manager. Must update this before touching workflows.

---

## FILE TO MODIFY

`Shared/db_manager.py`

---

## CHANGES REQUIRED

### Change 1: Update save_product Method

**Location**: Find the `save_product` method (around line 200-300)

**Add these parameters to method signature**:
```python
async def save_product(
    self,
    url: str,
    product_data: Dict,
    source: str = None,
    lifecycle_stage: str = None,  # NEW
    data_completeness: str = None,  # NEW
    last_workflow: str = None,  # NEW
    extracted_at: str = None,  # NEW
    assessed_at: str = None,  # NEW
    # ... other existing parameters
) -> bool:
```

**Update the INSERT statement** to include new fields:
```python
cursor.execute("""
    INSERT INTO products (
        url, retailer, title, price, description,
        modesty_status, clothing_type, neckline, sleeve_length,
        shopify_id, shopify_status, source,
        lifecycle_stage, data_completeness, last_workflow,
        extracted_at, assessed_at,
        first_seen, last_updated,
        -- ... other existing fields
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ...)
    ON CONFLICT(url) DO UPDATE SET
        title = excluded.title,
        price = excluded.price,
        last_updated = excluded.last_updated,
        lifecycle_stage = COALESCE(excluded.lifecycle_stage, lifecycle_stage),
        data_completeness = COALESCE(excluded.data_completeness, data_completeness),
        last_workflow = COALESCE(excluded.last_workflow, last_workflow),
        -- ... other existing update fields
""", (
    url,
    # ... existing parameters
    lifecycle_stage,
    data_completeness,
    last_workflow,
    extracted_at,
    assessed_at,
    # ... existing parameters
))
```

**IMPORTANT**: Use `COALESCE` in UPDATE to prevent overwriting existing values with NULL.

---

### Change 2: Update save_catalog_product Method

**Location**: Find the `save_catalog_product` method (around line 400-500)

**Add these parameters**:
```python
async def save_catalog_product(
    self,
    product: Dict,
    scan_type: str = 'baseline',  # NEW
    review_status: str = 'baseline',
    image_url_source: str = 'catalog_extraction'  # NEW
) -> bool:
```

**Update the INSERT statement**:
```python
cursor.execute("""
    INSERT INTO catalog_products (
        catalog_url, retailer, category, title, price, product_code,
        image_urls, discovered_date, review_status,
        scan_type, image_url_source
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (
    product.get('url') or product.get('catalog_url'),
    product.get('retailer'),
    product.get('category'),
    product.get('title'),
    product.get('price'),
    product.get('product_code'),
    product.get('image_urls'),
    datetime.utcnow().isoformat(),
    review_status,
    scan_type,  # NEW
    image_url_source  # NEW
))
```

---

### Change 3: Add Required Import

**Location**: Top of file

**Add**:
```python
from datetime import datetime
```

If already imported, verify it's present.

---

## VERIFICATION

Create a test script to verify db_manager changes:

**Create**: `test_db_manager.py`

```python
import asyncio
import sys
sys.path.append('Shared')
from db_manager import DatabaseManager

async def test():
    db = DatabaseManager()
    
    # Test save_product with new parameters
    test_product = {
        'url': 'https://test.com/test-product',
        'retailer': 'test_retailer',
        'title': 'Test Product',
        'price': 99.99,
        'description': 'Test description',
        'modesty_status': 'modest',
        'clothing_type': 'dress'
    }
    
    result = await db.save_product(
        url=test_product['url'],
        product_data=test_product,
        source='test',
        lifecycle_stage='imported_direct',
        data_completeness='full',
        last_workflow='test_script',
        extracted_at='2025-11-23T12:00:00'
    )
    
    print(f"save_product result: {result}")
    
    # Test save_catalog_product with new parameters
    test_catalog_product = {
        'url': 'https://test.com/test-catalog-product',
        'retailer': 'test_retailer',
        'category': 'dresses',
        'title': 'Test Catalog Product',
        'price': 89.99,
        'product_code': 'TEST-001'
    }
    
    result2 = await db.save_catalog_product(
        product=test_catalog_product,
        scan_type='monitor',
        review_status='baseline',
        image_url_source='catalog_extraction'
    )
    
    print(f"save_catalog_product result: {result2}")
    
    # Verify data saved correctly
    conn = db._get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT lifecycle_stage, data_completeness, last_workflow FROM products WHERE url = ?", 
                   (test_product['url'],))
    product_result = cursor.fetchone()
    print(f"Product saved with: {product_result}")
    
    cursor.execute("SELECT scan_type, image_url_source FROM catalog_products WHERE catalog_url = ?",
                   (test_catalog_product['url'],))
    catalog_result = cursor.fetchone()
    print(f"Catalog product saved with: {catalog_result}")
    
    # Cleanup
    cursor.execute("DELETE FROM products WHERE url = ?", (test_product['url'],))
    cursor.execute("DELETE FROM catalog_products WHERE catalog_url = ?", (test_catalog_product['url'],))
    conn.commit()
    conn.close()
    
    print("\n✅ All tests passed!")

if __name__ == '__main__':
    asyncio.run(test())
```

**Run**:
```bash
cd "/Users/yav/Agent Modest Scraper System"
python3 test_db_manager.py
```

---

## SHOW ME

After execution, show me:
1. ✅ Confirmation that save_product method updated
2. ✅ Confirmation that save_catalog_product method updated
3. ✅ Test script output (all tests should pass)
4. ✅ Any errors encountered

---

## SUCCESS CRITERIA

✅ save_product accepts new parameters without errors  
✅ save_catalog_product accepts new parameters without errors  
✅ Test product saves with lifecycle_stage correctly  
✅ Test catalog product saves with scan_type correctly  
✅ No syntax errors in modified code  
✅ Existing workflows still work (no breaking changes)

---

## IF ERRORS OCCUR

**Error: "no such column: lifecycle_stage"**  
- Phase 1 not completed
- Go back and run Phase 1 schema changes

**Error: "wrong number of bindings"**  
- Mismatch between number of ? placeholders and parameters
- Count placeholders vs values carefully

**Error: "ambiguous column name"**  
- Use table aliases in queries with JOINs
- Specify table.column explicitly

---

## COMMIT

After successful verification:
```bash
git add Shared/db_manager.py
git commit -m "Phase 2: Update db_manager for lifecycle tracking"
```

---

## NEXT STEP

After Phase 2 completes successfully:
→ Proceed to **Phase 3: Baseline Scanner Updates**

DO NOT proceed until test script passes.
