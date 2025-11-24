# "No Longer Available" Product Detection

**Date**: 2025-11-24  
**Status**: ✅ Implemented  
**Version**: 1.0

---

## OVERVIEW

Added detection and handling for products that are permanently delisted/discontinued by retailers (not just temporarily out of stock).

## PROBLEM

Previously, the system treated "no longer available" the same as "out of stock":
- Would keep attempting to extract/update delisted products
- Wasted API calls and resources on products that will never return
- No visual indicator in Shopify that product is discontinued (not coming back)

## SOLUTION

### 1. **Extraction Layer**: Detect Delisting

Both extraction towers now distinguish between:
- `"out_of_stock"` - Temporarily unavailable (sold out, restocking)
- `"no_longer_available"` - Permanently removed/discontinued

**Detection signals**:
- Text patterns: "no longer available", "discontinued", "item not found", "removed", "product no longer exists"
- Missing critical fields (title + price both empty)
- Redirect to category page (captured by pattern learner)

**Files modified**:
- `Extraction/Markdown/markdown_product_extractor.py`
  - Updated `stock_status` field definition (line 335)
  - Added delisting detection instructions (lines 367-372)
  
- `Extraction/Patchright/patchright_product_extractor.py`
  - Updated `availability` field definition (line 396)
  - Added delisting detection instructions (lines 397-402)
  - Added field mapping: `availability` → `stock_status` (lines 155-159)

---

### 2. **Shopify Layer**: Delist Products

New method to gracefully handle delisted products in Shopify:
- Change status: `active` → `draft` (hide from storefront)
- Add tag: `"No Longer Available"` (for admin visibility/filtering)

**File modified**:
- `Shared/shopify_manager.py`
  - Added `delist_product()` method (lines 291-357)

**API workflow**:
1. Fetch current product to get existing tags
2. Add "No Longer Available" tag to tag list
3. Update product: set `status=draft` + updated tags
4. Return success/error

---

### 3. **Workflow Layer**: Handle Delisted Products

#### **Product Updater**
When updating existing products:
- ✅ Check `stock_status == 'no_longer_available'` after extraction
- ✅ Call `shopify_manager.delist_product()` if product has `shopify_id`
- ✅ Update database `stock_status` to prevent future API calls
- ✅ Log delisting action

**File modified**:
- `Workflows/product_updater.py`
  - Updated delisting detection (lines 304-340)
  - Changed from checking `extraction_result.is_delisted` (doesn't exist) to checking `extracted_data['stock_status']`

#### **New Product Importer**
When importing new products:
- ✅ Check `stock_status == 'no_longer_available'` after extraction
- ✅ Skip import entirely (don't upload to Shopify)
- ✅ Return `ImportResult` with `action='skipped_delisted'`
- ✅ Log warning

**File modified**:
- `Workflows/new_product_importer.py`
  - Added delisting check (lines 343-355)

---

## DATABASE

Uses existing `stock_status` field in `products` table.

**Values**:
- `"in_stock"` - Available for purchase
- `"low_in_stock"` - Limited availability
- `"out_of_stock"` - Temporarily unavailable
- `"no_longer_available"` - **NEW** Permanently delisted

**No schema migration required** ✅

---

## PATTERN LEARNING INTEGRATION

The existing `pattern_learning_manager.py` will naturally learn retailer-specific delisting patterns:
- Text variations per retailer
- Redirect behaviors (e.g., Anthropologie redirects to category page)
- Missing field patterns (e.g., Revolve shows blank title + price)

**No code changes needed** - pattern learner already records extraction attempts.

---

## BENEFITS

1. **Resource Efficiency**: Stop attempting to extract/update products that no longer exist
2. **Shopify Clarity**: "No Longer Available" tag makes it clear product is discontinued (not just out of stock)
3. **Pattern Learning**: System learns retailer-specific delisting signals over time
4. **API Cost Reduction**: Avoid repeated failed API calls to Shopify for delisted products

---

## TESTING CHECKLIST

- [ ] **Markdown Extraction**: Test with delisted Revolve product URL
- [ ] **Patchright Extraction**: Test with delisted Anthropologie product URL
- [ ] **Product Updater**: Run update on delisted product, verify Shopify tag + draft status
- [ ] **New Product Importer**: Import batch with 1 delisted URL, verify it's skipped
- [ ] **Database**: Verify `stock_status='no_longer_available'` saved correctly

---

## RELATED DOCS

- `Knowledge/DEBUGGING_LESSONS.md` - Anti-scraping techniques
- `Knowledge/PRODUCT_LIFECYCLE_MANAGEMENT.md` - Lifecycle stages
- `Workflows/PRODUCT_UPDATER_GUIDE.md` - Update workflow

