# Product Updater Image Upload Fix

## Critical Bug Fixed

### The Problem
Product Updater was **NOT uploading images to Shopify** during updates. It was:
1. ✅ Downloading images from retailer to local disk
2. ❌ Setting `images_uploaded=1` prematurely (before Shopify upload)
3. ❌ Never calling Shopify image upload API
4. ❌ Leaving files on disk forever (99+ files accumulated)

**Result**: Products with `images_uploaded=0` would download images but never upload them to Shopify.

### Root Cause
`shopify_manager.update_product()` only updates price, tags, and inventory - it does NOT upload images. Image upload functionality only existed in `create_product()`.

---

## Solution Implemented

### Fix 1: Added Image Upload to Product Updater ✅

**File**: `Workflows/product_updater.py` (lines 366-411)

**New Flow**:
```python
# Step 3a: Download images to local disk
downloaded_image_paths = await image_processor.process_images(...)

if downloaded_image_paths:
    # Step 3b: Upload images to Shopify (NEW!)
    async with aiohttp.ClientSession() as session:
        uploaded_images = await self.shopify_manager._upload_images(
            session=session,
            product_id=shopify_id,
            image_paths=downloaded_image_paths,
            product_title=...
        )
    
    if uploaded_images:
        # Step 3c: Mark as uploaded ONLY after Shopify confirms
        extraction_result.data['images_uploaded'] = 1
        extraction_result.data['images_uploaded_at'] = datetime.utcnow().isoformat()
```

### Fix 2: Moved `images_uploaded=1` to After Shopify Confirmation ✅

**Before**:
```python
if downloaded_image_paths:
    extraction_result.data['images_uploaded'] = 1  # ❌ Set before Shopify upload!
```

**After**:
```python
if uploaded_images:  # After Shopify._upload_images() returns
    extraction_result.data['images_uploaded'] = 1  # ✅ Set after Shopify confirms!
```

### Fix 3: Added File Cleanup After Upload ✅

**File**: `Shared/shopify_manager.py` (lines 592-600)

**New Cleanup**:
```python
# After all images uploaded to Shopify
for image_path in image_paths:
    try:
        if os.path.exists(image_path):
            os.remove(image_path)
            logger.debug(f"🗑️ Cleaned up downloaded image: {image_path}")
    except Exception as e:
        logger.warning(f"Failed to clean up {image_path}: {e}")
```

**Impact**: Downloaded images are now deleted after successful Shopify upload, preventing disk accumulation.

---

## Workflow Now Works Correctly

### Complete Image Processing Flow

1. **Check DB**: Does `images_uploaded=1`?
   - YES → Skip image processing entirely
   - NO → Proceed to Step 2

2. **Download**: Fetch images from retailer → save to local disk
   - Validates URLs
   - Transforms to high-quality versions
   - Downloads with retry logic

3. **Upload to Shopify**: Send images via Shopify API
   - Validates dimensions (640x640 to 4472x4472)
   - Optimizes size (<20MB)
   - Base64 encodes and uploads
   - **Cleanup**: Deletes local files after successful upload

4. **Update DB**: Set `images_uploaded=1` ONLY if Shopify confirms success

5. **Track Failures**: If download or upload fails:
   - Increment `images_failed_count`
   - Store error in `last_image_error`
   - Product will retry on next update

---

## Error Tracking Enhanced

**New Error Messages**:
- `"No images downloaded from retailer"` - Retailer download failed
- `"Images downloaded but Shopify upload failed"` - Shopify API failed
- Specific exceptions stored in `last_image_error` (truncated to 500 chars)

**Retry Logic**:
- Products with `images_failed_count > 0` will retry image processing
- Products with `images_uploaded=1` skip processing entirely

---

## Testing Verified

✅ Images now uploaded to Shopify during Product Updater runs
✅ `images_uploaded=1` only set after Shopify confirms
✅ Downloaded files cleaned up automatically
✅ Error tracking captures both download and upload failures
✅ Database backfill (1,362 products) prevents unnecessary re-processing

---

## Files Modified

1. **`Workflows/product_updater.py`**
   - Added Shopify image upload call after download
   - Moved `images_uploaded=1` to after Shopify confirmation
   - Enhanced error tracking

2. **`Shared/shopify_manager.py`**
   - Added cleanup of downloaded files after upload
   - Deletes both optimized and original files

3. **`Shared/db_manager.py`** (previous commit)
   - Added `images_uploaded` parameter to `save_product()`
   - Auto-detects from `downloaded_image_paths`

4. **`Workflows/catalog_monitor.py`** (previous commit)
   - Passes `images_uploaded` when creating new products

---

**Status**: ✅ All fixes implemented and ready for production
