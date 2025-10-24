# Product Type Override Implementation - October 23, 2025

## Problem Identified

Dress tops were being uploaded with the tag "Dress" instead of "Dress Top" because:

1. **"Dress Tops" is NOT a real product category on retailer websites** - AI naturally extracts "dress"
2. **URLs were manually curated** - The user handpicked dress tops URLs, but AI couldn't know they were dress tops
3. **No way to override AI extraction** - System lacked parameter to specify product type

## Root Cause

The system was trying to make AI extract "dress top" which doesn't naturally exist on websites. The correct approach is to let the user specify product type as a parameter when importing manually curated batches.

## Solution Implemented

Added `--product-type` parameter to allow manual override of AI-extracted clothing type.

### How It Works Now

```bash
python new_product_importer.py \
  --batch-file "batch_modest_dress_tops.json" \
  --modesty-level modest \
  --product-type "Dress Tops" \
  --force-run-now
```

**Process:**
1. AI extracts whatever it finds naturally (probably "dress")
2. System **overrides** with specified `--product-type "Dress Tops"`
3. Shopify Product Type = "Dress Tops" (plural)
4. Tag = "Dress Top" (singular, auto-converted)

## Files Modified

### 1. `Shared/markdown_extractor.py`
- **Reverted** misguided changes that tried to make AI extract "dress top"
- Prompt now correctly asks for natural categories only

### 2. `New Product Importer/new_product_importer.py`
- Added `--product-type` parameter
- Passes override through to import processor

### 3. `New Product Importer/import_processor.py`
- Added `product_type_override` parameter to batch processing
- Passes override to Shopify Manager

### 4. `Shared/shopify_manager.py`
- `create_product()` now accepts `product_type_override`
- `_build_product_payload()` uses override when provided
- `_build_product_tags()` converts plural product types to singular tags
- Added `_convert_product_type_to_singular_tag()` method

**Singular Tag Mapping:**
- "Dress Tops" → "Dress Top"
- "Dresses" → "Dress"
- "Tops" → "Top"
- "Bottoms" → "Bottom"
- etc.

## Tag Strategy

**NO redundancy** - Product type is NOT added as a separate tag because:
- Shopify Product Type is already searchable/filterable
- Tags are for: Modesty Level, Retailer, Auto-Scraped, Brand, Sale status

## Usage Examples

### Dress Tops (Override Required)
```bash
python new_product_importer.py \
  --batch-file "batch_modest_dress_tops.json" \
  --modesty-level modest \
  --product-type "Dress Tops" \
  --force-run-now
```

Result:
- Shopify Product Type: "Dress Tops"
- Tag: "Dress Top"

### Regular Dresses (No Override Needed)
```bash
python new_product_importer.py \
  --batch-file "batch_modest_dresses.json" \
  --modesty-level modest \
  --force-run-now
```

Result:
- AI extracts: "dress"
- Shopify Product Type: "Dresses" (auto-pluralized)
- Tag: "Dress" (auto-singularized)

## Benefits

✅ Flexible - User can override when needed
✅ Natural - AI extracts what actually exists on websites
✅ Consistent - Automatic singular/plural conversion
✅ Clean - No redundant tags

## Migration Note

The 35 dress tops already uploaded with "Dress" tag (from Batch 2 and Batch 4) will need to be:
1. Re-imported with `--product-type "Dress Tops"`, OR
2. Manually updated in Shopify

Going forward, all dress tops batches should use `--product-type "Dress Tops"`.

