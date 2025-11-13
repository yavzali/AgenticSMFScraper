# 25 Revolve Dresses - Deleted Due to Image Failure

**Date**: November 13, 2024  
**Issue**: Image transformation bug (thumbnails → 404s)  
**Status**: Deleted from Shopify and assessment queue, still in catalog baseline

---

## **Background**

During the first Revolve dresses catalog monitor run, 25 new products were:
- ✅ Successfully extracted (titles, prices, URLs)
- ❌ Failed image download (URL transformation bug)
- ✅ Uploaded to Shopify with 0 images
- ✅ Added to assessment queue

After fixing the image transformation bug, these 25 products were deleted from:
- Shopify (drafts removed)
- Assessment queue (queue entries removed)

**However**, they remain in:
- `catalog_products` baseline (still marked as "existing")

---

## **Impact**

The catalog monitor will **NOT** naturally re-discover these products because:
1. They're in the catalog baseline (245 total Revolve dresses)
2. Deduplication sees them as "existing" products
3. Only "new" products trigger single product extraction

---

## **Products List**

The 25 products have Shopify IDs ranging from approximately:
- `14835893453170` to `14835896731890` (based on deletion log)

**Note**: We don't have the exact product URLs stored separately. They can be identified from:
- Shopify deletion logs (if available)
- Assessment queue deletion script output
- Manual inspection of catalog baseline for products with `first_seen` around Nov 13, 02:00 UTC

---

## **Options for Re-extraction**

### Option 1: Manual Single Product Extraction
- Extract product URLs from catalog baseline
- Run single product extraction for each URL
- Upload to Shopify with corrected images

### Option 2: Remove from Baseline and Re-scan
- Delete the 25 products from `catalog_products` table
- Run catalog monitor again
- System will naturally re-discover them as "new"

### Option 3: Ignore (Low Priority)
- These 25 products are already in Revolve's catalog
- They'll naturally be discovered again if they become "new" again
- Focus on genuinely new products instead

---

## **Recommendation**

**Low Priority (P3)** - These are not newly released products, just ones we failed to process correctly once. 

**Suggested approach**: Option 3 (Ignore)
- Not worth the manual effort
- May come up again naturally in future scans
- Focus on new product discovery instead

---

## **Related Files**
- `Knowledge/DEBUGGING_LESSONS.md` (Image URL Transformations section)
- `DISPOSABLE_delete_25_revolve_dresses.py` (deletion script)
- `Shared/image_processor.py` (`_transform_revolve_url` fix)

---

## **Prevention**

✅ Fixed in commit `bb65469`:
- Corrected Revolve URL transformation logic
- Preserved `_V1`, `_V2`, `_V3` suffixes (different angles)
- Convert thumbnails to full-size while keeping working patterns
- All future Revolve products will have correct images


