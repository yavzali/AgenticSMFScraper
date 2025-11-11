# System-Wide Propagation & Verification Checklist

**Created**: November 11, 2025  
**Context**: After fixing Product Updater image upload issues  
**Status**: Review & verify in morning

---

## 📋 Executive Summary

We fixed critical bugs in Product Updater (image upload, tracking, cleanup). Most fixes are centralized and automatically propagate, but some areas need verification.

---

## ✅ What Was Fixed (Product Updater)

1. **Image Upload Tracking**
   - Added `images_uploaded` parameter to `db_manager.save_product()`
   - Set flag ONLY after Shopify confirms upload (not after local download)
   - Track both download and upload failures separately

2. **Revolve URL Transformations**
   - Removed bad `/n/z/` → `/n/f/` conversion (caused 404s)
   - Added missing patterns: `/n/dp/`, `/n/d5/`, `/n/dX/`
   - All now correctly transform to `/n/z/` (zoom)

3. **Actual Shopify Upload**
   - Product Updater now calls `shopify._upload_images()` after download
   - Validates dimensions (640x640 to 4472x4472)
   - Optimizes size (<20MB)
   - Base64 encodes and uploads

4. **File Cleanup**
   - Added cleanup in `shopify_manager._upload_images()`
   - Deletes downloaded files after successful upload
   - Prevents disk accumulation

---

## ✅ Already Propagated (No Action Needed)

### Image Upload Tracking ✅
- `db_manager.save_product()` - Takes `images_uploaded` parameter
- `catalog_monitor._upload_to_shopify_as_draft()` - Passes parameter
- `product_updater._update_single_product()` - Sets after Shopify confirms

### Revolve URL Fixes ✅
- Centralized in `image_processor.py`
- Used by ALL workflows automatically:
  - Catalog Monitor
  - Product Updater
  - Any future workflows

### File Cleanup ✅
- Added to `shopify_manager._upload_images()`
- Called by:
  - `shopify.create_product()` (Catalog Monitor uses this)
  - `product_updater._update_single_product()` (Product Updater)

---

## ⚠️ VERIFICATION NEEDED (Morning Tasks)

### 🔴 High Priority

#### Task 1: Verify Catalog Monitor Cleanup Works
**File**: `Workflows/catalog_monitor.py` (line 823-856)

**Current Flow**:
```python
downloaded_images = await image_proc.process_images(...)  # Downloads to disk
result = await shopify.create_product(..., downloaded_images=...)  # Uploads
```

**Question**: Does `create_product()` clean up files?

**Verification**:
1. Check `shopify_manager.create_product()` line 100
2. Confirm it calls `_upload_images()` (which we added cleanup to)
3. **Test**: Run Catalog Monitor on 1 new product
4. **Verify**: Check `Shared/downloads/` directory is empty after

**Expected**: Should be fixed (shared function), but test to confirm.

---

#### Task 2: Test Other Retailers' URL Transformations
**Files**: `Shared/image_processor.py` (lines 269-439)

**Issue**: Revolve had broken transformations. Other retailers might too.

**Retailers to Test**:

| Retailer | CDN | Current Transformations | Status |
|----------|-----|------------------------|--------|
| Revolve | revolveassets.com | /n/z/, /n/dp/, /n/d5/ | ✅ FIXED |
| Anthropologie | Adobe Scene7 | $product$ → $zoom$, wid/hei params | ❓ UNKNOWN |
| H&M | Azure CDN | hmgoepprod.azureedge.net | ❓ UNKNOWN |
| Aritzia | media.aritzia.com | _small → _large | ❓ UNKNOWN |
| Uniqlo | Images CDN | /300w/ → /1200w/ | ❓ UNKNOWN |
| Abercrombie | Scene7 | wid/hei params | ❓ UNKNOWN |
| Urban Outfitters | Similar to Anthropologie | Size transformations | ❓ UNKNOWN |
| Nordstrom | nordstrommedia.com | /300/ → /1200/ | ❓ UNKNOWN |

**Verification Steps** (for each retailer):
1. Find 1 product from that retailer in DB
2. Extract image URLs from product page
3. Check what `image_processor._transform_X_url()` does
4. Test if transformed URL returns HTTP 200 (not 404)
5. If 404: Investigate correct pattern

**How to Test**:
```python
# Example test script
import requests
from Shared.image_processor import ImageProcessor

proc = ImageProcessor()

# Test Anthropologie
original_url = "https://anthropologie.scene7.com/is/image/Anthropologie/12345_sw.jpg"
enhanced_url = proc._enhance_urls([original_url], 'anthropologie')[0]

response = requests.head(enhanced_url)
print(f"Anthropologie: {response.status_code}")  # Should be 200, not 404
```

---

### 🟡 Medium Priority

#### Task 3: Add Image Upload Validation Tests
**Location**: Create `Shared/tests/test_image_upload.py`

**Tests to Add**:
1. **Download → Upload → Cleanup**
   - Download images
   - Upload to Shopify
   - Verify files deleted from disk

2. **Upload Failure → Flag Not Set**
   - Mock Shopify API failure
   - Verify `images_uploaded` stays 0

3. **Each Retailer URL Transformations**
   - For each retailer, test sample URLs
   - Verify transformations return 200

**Example Test Structure**:
```python
async def test_full_image_upload_cycle():
    # Setup
    image_urls = ["https://revolveassets.com/images/p4/n/ct/PROD-123.jpg"]
    
    # Download
    paths = await image_proc.process_images(image_urls, 'revolve', 'Test')
    assert len(paths) > 0
    assert all(os.path.exists(p) for p in paths)
    
    # Upload
    uploaded = await shopify._upload_images(session, product_id, paths, 'Test')
    assert len(uploaded) > 0
    
    # Verify Cleanup
    assert all(not os.path.exists(p) for p in paths)
```

---

#### Task 4: Review All "External State" Flags
**Question**: Are there other flags that represent "successfully uploaded to external system"?

**Known Flags**:
- `images_uploaded` ✅ Fixed (set after Shopify confirms)
- `shopify_status` ❓ Check: Set after Shopify API confirms?
- `shopify_id` ❓ Check: Set after Shopify API confirms?
- Others?

**Verification**:
1. Search codebase for `shopify_id =`, `shopify_status =`
2. Verify they're set AFTER Shopify API returns success
3. Not set prematurely (before external confirmation)

**Pattern to Follow**:
```python
# ❌ BAD - Set before external confirmation
data['uploaded'] = True
result = await external_api.upload(data)

# ✅ GOOD - Set after external confirmation
result = await external_api.upload(data)
if result['success']:
    data['uploaded'] = True
```

---

### 🟢 Low Priority

#### Task 5: Consider Direct URL Upload Option
**Context**: We have `shopify._upload_image_from_url()` that's unused.

**Trade-offs**:

**Download + Upload (Current)**:
- ✅ Validation (dimensions, file size)
- ✅ Optimization (resize, compress)
- ✅ More reliable (control headers, retries)
- ❌ Slower (2-step process)
- ❌ Disk usage, cleanup needed

**Direct URL Upload (Alternative)**:
- ✅ Faster (1-step process)
- ✅ No disk usage, no cleanup
- ❌ No validation/optimization
- ❌ Shopify might fail to fetch from retailer

**Recommendation**: 
- Keep current approach for most retailers
- Consider direct URL for:
  - Very reliable CDNs (large retailers)
  - When validation/optimization not critical
  - Batch imports where speed matters

**Implementation** (if desired):
```python
# Add parameter to image processing
async def process_images(..., use_direct_url=False):
    if use_direct_url:
        return image_urls  # Return URLs, don't download
    else:
        # Current logic: download, validate, optimize
```

---

## 📚 Lessons Learned (Apply to Future Work)

### Lesson 1: Track State AFTER External Confirmation ⭐⭐⭐
**Rule**: Any flag representing "successfully uploaded to external system" should only be set AFTER that system confirms.

**Bad**:
```python
data['uploaded'] = True  # Set before external call
await external_api.upload(data)
```

**Good**:
```python
result = await external_api.upload(data)
if result['success']:
    data['uploaded'] = True  # Set after confirmation
```

---

### Lesson 2: Clean Up Temporary Files ⭐⭐⭐
**Rule**: Any temporary download should be cleaned up after use.

**Bad**:
```python
downloaded_files = await download_files(urls)
await upload_to_external(downloaded_files)
# Files left on disk forever!
```

**Good**:
```python
downloaded_files = await download_files(urls)
try:
    await upload_to_external(downloaded_files)
finally:
    for file in downloaded_files:
        os.remove(file)  # Always cleanup
```

---

### Lesson 3: Validate Retailer-Specific Transformations ⭐⭐
**Rule**: Test that transformed URLs actually work (return 200, not 404).

**Process**:
1. Get sample URL from retailer
2. Apply transformation
3. Test transformed URL (HTTP HEAD request)
4. If 404: Investigate correct pattern
5. Don't assume "bigger is better" (like /n/f/ vs /n/z/)

**Example**:
```python
# Test transformation
original = "https://revolveassets.com/images/p4/n/dp/PROD-123.jpg"
transformed = transform_url(original)
response = requests.head(transformed)
assert response.status_code == 200, f"Transformation failed: {transformed}"
```

---

### Lesson 4: Separate Failure Types ⭐⭐
**Rule**: Distinguish between different failure points for better debugging.

**Types of Failures**:
1. **External Data Source** (retailer down, 403, rate limit)
2. **Our Processing** (validation failed, optimization failed)
3. **External Upload** (Shopify API failed, quota exceeded)

**Implementation**:
```python
try:
    downloaded = await download_from_retailer(url)
except Exception as e:
    error = f"Retailer download failed: {e}"
    
try:
    validated = validate_image(downloaded)
except Exception as e:
    error = f"Validation failed: {e}"
    
try:
    uploaded = await upload_to_shopify(validated)
except Exception as e:
    error = f"Shopify upload failed: {e}"
```

---

## 🎯 Morning Action Items (Prioritized)

### Immediate (30 minutes)
- [ ] **Task 1**: Run Catalog Monitor on 1 new product, verify cleanup
- [ ] **Task 4**: Review `shopify_status`, `shopify_id` flag setting

### Important (1-2 hours)
- [ ] **Task 2**: Test Anthropologie URL transformations
- [ ] **Task 2**: Test H&M URL transformations
- [ ] **Task 2**: Test Aritzia URL transformations

### If Time Permits (2-3 hours)
- [ ] **Task 2**: Test remaining retailers (Uniqlo, Abercrombie, Urban Outfitters, Nordstrom)
- [ ] **Task 3**: Create basic image upload validation tests
- [ ] **Task 5**: Evaluate direct URL upload for specific use cases

---

## 📝 Notes & Context

### Why These Fixes Were Needed
1. Product Updater was downloading images but never uploading to Shopify
2. `images_uploaded=1` was set prematurely (before Shopify upload)
3. Files accumulated on disk (99+ files found)
4. Revolve URLs had broken transformations (404s)

### What We Fixed
1. Added Shopify upload call in Product Updater
2. Moved flag setting to after Shopify confirmation
3. Added file cleanup after successful upload
4. Fixed Revolve URL transformations

### Why Propagation is Important
1. Other retailers might have similar URL issues
2. Other workflows might have similar state tracking issues
3. Lessons apply to any future external integrations

---

## 🔗 Related Documentation

- `Knowledge/PRODUCT_UPDATER_IMAGE_UPLOAD_FIX.md` - Detailed fix documentation
- `Knowledge/IMAGE_UPLOAD_TRACKING_FIX.md` - Database tracking fix
- `Shared/image_processor.py` - Retailer-specific URL transformations

---

**Status**: ⏰ Pending morning review & verification  
**Priority**: High (affects data quality and system efficiency)  
**Estimated Time**: 2-4 hours for thorough verification

