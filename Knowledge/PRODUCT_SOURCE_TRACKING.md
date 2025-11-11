# Product Source Tracking

**Added**: November 11, 2025  
**Status**: ✅ Implemented

---

## Overview

Added `source` field to track how products entered the system. This provides data provenance and helps distinguish between:
- Bulk baseline imports
- Organic catalog monitoring discoveries
- Manual imports

---

## Database Schema

### New Column

```sql
ALTER TABLE products ADD COLUMN source VARCHAR(50);
```

**Values**:
- `'baseline_scan'` - From initial bulk import/baseline establishment
- `'monitor'` - Discovered by catalog monitoring workflow
- `'new_product_import'` - Manually imported product

**Default**: `NULL` (for existing products pre-dating this feature)

---

## Current State

**Existing Products** (1,362 Revolve):
- `source` = `NULL`
- These were imported before source tracking was added
- All are in Shopify (have `shopify_id`)
- NOT backfilled per user request

**New Products** (going forward):
- Will have explicit `source` value
- Set automatically by workflows

---

## Implementation

### 1. Database Manager (`db_manager.py`)

**Updated `save_product()` function**:
```python
async def save_product(
    ...
    source: Optional[str] = None  # NEW parameter
) -> bool:
    """
    Args:
        source: 'baseline_scan', 'monitor', or 'new_product_import'
    """
```

### 2. Catalog Monitor (`catalog_monitor.py`)

**Sets `source='monitor'` for new products**:
```python
await self.db_manager.save_product(
    ...
    source='monitor'  # Discovered by monitoring
)
```

### 3. Future: Baseline Scanner

**Should set `source='baseline_scan'` for bulk imports**:
```python
await self.db_manager.save_product(
    ...
    source='baseline_scan'  # Bulk import
)
```

### 4. Future: Manual Import

**Should set `source='new_product_import'` for manual adds**:
```python
await self.db_manager.save_product(
    ...
    source='new_product_import'  # Manually added
)
```

---

## Use Cases

### Analytics Queries

**Count by source**:
```sql
SELECT source, COUNT(*) as count
FROM products
GROUP BY source;
```

**Find monitored products**:
```sql
SELECT * FROM products 
WHERE source = 'monitor'
ORDER BY first_seen DESC;
```

**Products from baseline (legacy)**:
```sql
SELECT * FROM products
WHERE source IS NULL  -- Legacy baseline products
   OR source = 'baseline_scan';
```

### Workflow Logic

**Re-run monitoring on non-baseline products**:
```python
# Get only products discovered by monitoring
cursor.execute("""
    SELECT url FROM products 
    WHERE source = 'monitor'
""")
```

**Distinguish new discoveries from baseline**:
```python
# Count organic growth
cursor.execute("""
    SELECT COUNT(*) 
    FROM products 
    WHERE source = 'monitor'
      AND first_seen > '2025-11-11'
""")
```

---

## Data Provenance

### Before This Feature (NULL source)

All 1,362 existing products have `source = NULL`:
- Imported before source tracking
- Assumed to be baseline
- All in Shopify
- NOT backfilled to preserve original state

### After This Feature

All new products have explicit source:
- `'monitor'` - From catalog monitoring
- `'baseline_scan'` - From bulk imports
- `'new_product_import'` - From manual adds

---

## Decision Rationale

### Why NOT backfill existing products?

**User Decision**: Keep NULL for existing products

**Reasons**:
1. Preserves historical state
2. Clear distinction: NULL = pre-tracking, explicit value = post-tracking
3. Can infer: NULL + has shopify_id = baseline
4. Avoids assumptions about historical data

---

## Future Considerations

### If Baseline Re-scan Needed

When running baseline scanner on new retailers:
```python
# In baseline import workflow
await db_manager.save_product(
    ...
    source='baseline_scan'
)
```

### If Manual Import Tool Added

When manually adding products:
```python
# In manual import interface
await db_manager.save_product(
    ...
    source='new_product_import'
)
```

### Analytics Dashboard

Can now show:
- Total products by source
- Organic growth rate (monitor discoveries per day)
- Baseline coverage vs monitored additions

---

## Migration Path (If Needed Later)

If backfill becomes necessary:

```sql
-- Mark NULL products as baseline (if desired)
UPDATE products 
SET source = 'baseline_scan'
WHERE source IS NULL;
```

**Note**: User explicitly chose NOT to do this now.

---

## Files Modified

1. **Database**: `Shared/products.db` - Added `source` column
2. **DB Manager**: `Shared/db_manager.py` - Added `source` parameter
3. **Catalog Monitor**: `Workflows/catalog_monitor.py` - Sets `source='monitor'`

---

**Status**: ✅ Fully implemented and ready for use  
**Current Catalog Monitors**: Running with source tracking enabled
