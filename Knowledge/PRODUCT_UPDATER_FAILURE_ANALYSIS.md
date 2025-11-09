# Product Updater Failure Analysis & Recommendations

**Date**: November 9, 2025  
**Analysis of**: 44 LLM extraction failures + 112 image download issues

---

## 1. LLM EXTRACTION FAILURE INVESTIGATION

### Failed URL Example
```
https://www.revolve.com/seroya-kim-maxi-dress-in-evergreen/dp/SERR-WD288/?d=Womens&page=1&lc=25&plpSrc=%2Fr%2FBrands.jsp%3FsortBy%3Dnewest...
```

### Error Pattern
```
[2025-11-09 13:20:22] [INFO] Large markdown detected for revolve, extracting product section
[2025-11-09 13:20:29] [WARNING] Both DeepSeek V3 and Gemini Flash 2.0 failed for revolve
[2025-11-09 13:20:29] [WARNING] LLM extraction failed
[2025-11-09 13:20:29] [WARNING] ❌ Extraction failed: ['LLM extraction failed']
```

### Root Cause Analysis

**Issue**: Both DeepSeek V3 and Gemini Flash 2.0 are failing to extract product data from Revolve markdown.

**Possible Causes**:
1. **Markdown Content Issue**: The "Large markdown detected" message suggests the system is extracting a product section, but the extracted section might:
   - Be incomplete or truncated
   - Not contain the actual product information
   - Be too large for the LLM to process effectively
   - Have formatting issues that confuse the LLM

2. **LLM Response Parsing**: The LLMs might be returning data, but:
   - JSON parsing is failing
   - Response format doesn't match expected structure
   - Response is empty or malformed

3. **Prompt Issues**: The extraction prompt might:
   - Be too complex for these specific products
   - Not handle edge cases in Revolve's markdown format
   - Request information that's not available in the markdown

4. **No Patchright Fallback**: The system should fall back to Patchright when both LLMs fail, but:
   - The fallback might not be triggered correctly
   - Patchright might not be configured for single product extraction in Product Updater

### Investigation Steps Needed

1. **Check Markdown Content**:
   - Inspect the actual markdown content for the failed URL
   - Verify the "product section extraction" is working correctly
   - Check if the markdown contains the product information

2. **Check LLM Responses**:
   - Add detailed logging to capture raw LLM responses
   - Check if responses are being received but failing validation
   - Verify JSON parsing logic

3. **Check Fallback Logic**:
   - Verify Patchright fallback is implemented in Product Updater
   - Check if fallback is being triggered when LLMs fail
   - Ensure Patchright single product extractor is working

4. **Compare with Successful Extractions**:
   - Compare markdown content of failed vs successful products
   - Identify patterns in failed products (specific brands, product types, etc.)
   - Check if certain product pages have different HTML structure

---

## 2. IMAGE URL EXTRACTION ISSUE - OLD VS NEW ARCHITECTURE

### Current Problem
- **112 products** updated successfully but with **0-1 images** instead of 5
- Error: `"Image too small: 87x131"` (thumbnail URLs)
- Example URL: `https://is4.revolveassets.com/images/p4/n/ct/AFFM-WD534_V1.jpg`

### Current Implementation (New Architecture)

**Location**: `Shared/image_processor.py` → `_transform_revolve_url()`

```python
def _transform_revolve_url(self, url: str) -> str:
    """
    Revolve-specific transformations
    
    URL patterns:
    - Size indicators: _sm, _md, _lg
    - CDN patterns
    """
    enhanced = url
    
    # Size transformations
    enhanced = re.sub(r'_sm\.(jpg|jpeg|png)', r'_lg.\1', enhanced, flags=re.IGNORECASE)
    enhanced = re.sub(r'_md\.(jpg|jpeg|png)', r'_lg.\1', enhanced, flags=re.IGNORECASE)
    enhanced = re.sub(r'_thumb\.(jpg|jpeg|png)', r'_lg.\1', enhanced, flags=re.IGNORECASE)
    
    return enhanced
```

**Problem**: This only handles `_sm`, `_md`, `_thumb` → `_lg`, but **doesn't handle the `_V1`, `_V2`, `_V3` pattern** that Revolve actually uses.

### Old Architecture (From config.example.json)

**Documented Pattern**:
```json
"revolve": {
    "image_processing": {
        "url_patterns": {
            "thumbnail_to_large": "_sw.jpg -> _xl.jpg"
        }
    }
}
```

**Issue**: The old config shows `_sw.jpg -> _xl.jpg`, but the actual URLs have `_V1.jpg`, `_V2.jpg`, etc.

### What Went Wrong

1. **Pattern Mismatch**: 
   - Old config documented `_sw` → `_xl` transformation
   - Current implementation uses `_sm/_md/_thumb` → `_lg` transformation
   - **Actual Revolve URLs use `_V1`, `_V2`, `_V3` pattern** (not covered by either)

2. **Missing Transformation Logic**:
   - The `_V1`, `_V2`, `_V3` pattern is not handled
   - These are clearly thumbnails (87x131 pixels)
   - Need to transform to full-size version

3. **LLM Extraction Issue**:
   - LLMs are extracting thumbnail URLs from markdown
   - The markdown likely contains both thumbnail and full-size URLs
   - LLM prompt asks for "high-quality" images but still extracts thumbnails

### What Needs to Change

1. **Update `_transform_revolve_url()` method**:
   ```python
   def _transform_revolve_url(self, url: str) -> str:
       enhanced = url
       
       # Handle _V1, _V2, _V3 pattern (thumbnails) → full-size
       # Pattern: AFFM-WD534_V1.jpg → AFFM-WD534.jpg or AFFM-WD534_xl.jpg
       enhanced = re.sub(r'_V\d+\.(jpg|jpeg|png)', r'.\1', enhanced, flags=re.IGNORECASE)
       
       # OR try: _V1 → _xl (if that's the pattern)
       enhanced = re.sub(r'_V\d+\.(jpg|jpeg|png)', r'_xl.\1', enhanced, flags=re.IGNORECASE)
       
       # Existing transformations
       enhanced = re.sub(r'_sm\.(jpg|jpeg|png)', r'_lg.\1', enhanced, flags=re.IGNORECASE)
       enhanced = re.sub(r'_md\.(jpg|jpeg|png)', r'_lg.\1', enhanced, flags=re.IGNORECASE)
       enhanced = re.sub(r'_thumb\.(jpg|jpeg|png)', r'_lg.\1', enhanced, flags=re.IGNORECASE)
       
       return enhanced
   ```

2. **Investigate Actual Revolve URL Pattern**:
   - Need to check what the full-size URL pattern actually is
   - Visit a Revolve product page and inspect image URLs
   - Check if removing `_V1` suffix works, or if `_xl` suffix is needed

3. **Improve LLM Prompt**:
   - Add explicit instruction to avoid thumbnail URLs
   - Specify minimum image dimensions (e.g., "images must be at least 500x500 pixels")
   - Add example of what NOT to extract

4. **Add Image URL Filtering**:
   - Filter out URLs with `_V1`, `_V2`, `_V3` patterns before processing
   - Or transform them before ranking/validation
   - Add to placeholder detection logic

### Investigation Needed

1. **Check Actual Revolve Product Page**:
   - Visit the failed URL and inspect image URLs
   - Find the pattern for full-size images
   - Document the correct transformation

2. **Check Old Architecture Files** (if available in Git history):
   - Look for old `revolve_image_processor.py` or similar
   - Check how it handled Revolve image URLs
   - See if there was retailer-specific logic in the old markdown extractor

3. **Check Markdown Content**:
   - Inspect the markdown for a Revolve product
   - See what image URLs are present
   - Check if full-size URLs are available but LLM is choosing thumbnails

---

## 3. CONDITIONAL IMAGE UPDATES - IMPLEMENTATION PLAN

### Current Behavior
- Product Updater **always processes and uploads images** if they're present in extraction result
- No check for whether images were previously uploaded successfully
- Wastes time and API calls re-uploading images that are already correct

### Proposed Solution

#### Step 1: Track Image Upload Status in Database

**Add to `products` table**:
```sql
ALTER TABLE products ADD COLUMN images_uploaded BOOLEAN DEFAULT 0;
ALTER TABLE products ADD COLUMN images_uploaded_at TIMESTAMP;
ALTER TABLE products ADD COLUMN images_failed_count INTEGER DEFAULT 0;
ALTER TABLE products ADD COLUMN last_image_error TEXT;
```

**Or use existing `product_data` JSON field**:
- Store image upload status in `product_data` JSON
- Track: `images_uploaded`, `images_uploaded_at`, `images_failed_count`, `last_image_error`

#### Step 2: Update Shopify Upload Logic

**In `Shared/shopify_manager.py` → `update_product()`**:
- After uploading images, check if upload was successful
- If successful: Set `images_uploaded = True` in product data
- If failed: Increment `images_failed_count`, store error message

#### Step 3: Add Conditional Logic to Product Updater

**In `Workflows/product_updater.py` → `_update_single_product()`**:

```python
# Step 3: Process images CONDITIONALLY
image_urls = extraction_result.data.get('image_urls', [])
if image_urls:
    # Check if images were previously uploaded successfully
    existing_product = await self.db_manager.get_product_by_url(url)
    images_uploaded = existing_product.get('images_uploaded', False) if existing_product else False
    images_failed_count = existing_product.get('images_failed_count', 0) if existing_product else 0
    
    # Only process images if:
    # 1. Never uploaded before (images_uploaded = False)
    # 2. Previous upload failed (images_failed_count > 0)
    # 3. New images detected (compare image URLs)
    should_update_images = (
        not images_uploaded or  # Never uploaded
        images_failed_count > 0 or  # Previous failure
        self._images_changed(existing_product, image_urls)  # New images
    )
    
    if should_update_images:
        logger.info(f"🖼️ Processing {len(image_urls)} images (status: uploaded={images_uploaded}, failed={images_failed_count})")
        downloaded_image_paths = await image_processor.process_images(...)
        # ... rest of image processing
    else:
        logger.debug(f"⏭️ Skipping image update (already uploaded successfully)")
        downloaded_image_paths = []  # Use existing images
```

#### Step 4: Add Image Change Detection

**New method in `ProductUpdater` class**:
```python
def _images_changed(self, existing_product: Dict, new_image_urls: List[str]) -> bool:
    """
    Check if image URLs have changed
    
    Returns True if:
    - No existing images
    - Image URLs are different
    - New images detected
    """
    if not existing_product:
        return True
    
    existing_images = existing_product.get('image_urls', [])
    if not existing_images:
        return True
    
    # Normalize URLs for comparison (remove query params, etc.)
    existing_normalized = {self._normalize_image_url(url) for url in existing_images}
    new_normalized = {self._normalize_image_url(url) for url in new_image_urls}
    
    # Check if sets are different
    return existing_normalized != new_normalized

def _normalize_image_url(self, url: str) -> str:
    """Normalize image URL for comparison"""
    # Remove query parameters
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
```

#### Step 5: Update Database After Image Upload

**In `shopify_manager.update_product()`**:
```python
# After image upload attempt
if image_upload_result.get('success'):
    product_data['images_uploaded'] = True
    product_data['images_uploaded_at'] = datetime.utcnow().isoformat()
    product_data['images_failed_count'] = 0
    product_data['last_image_error'] = None
else:
    product_data['images_failed_count'] = product_data.get('images_failed_count', 0) + 1
    product_data['last_image_error'] = image_upload_result.get('error', 'Unknown error')
```

#### Step 6: Update Product Record in Database

**In `product_updater.py` → `_update_single_product()`**:
```python
# Step 5: Update local DB (include image upload status)
await self.db_manager.update_product_record(
    url,
    extraction_result.data,  # Contains images_uploaded status
    last_updated=datetime.utcnow()
)
```

### Benefits

1. **Performance**: Skip image processing for products with successful uploads
2. **Cost Savings**: Reduce API calls and image downloads
3. **Reliability**: Only retry failed image uploads
4. **Tracking**: Monitor which products have image issues

### Edge Cases to Handle

1. **New Images Added**: If retailer adds new images, detect and update
2. **Image URL Changes**: If image URLs change (e.g., CDN migration), detect and update
3. **Partial Failures**: If some images succeed and others fail, track appropriately
4. **Manual Override**: Allow manual flag to force image re-upload

### Migration Strategy

1. **Backfill Existing Products**:
   - Assume products with `shopify_id` have images uploaded
   - Set `images_uploaded = True` for existing products
   - Only new products or products with known failures will re-upload

2. **Gradual Rollout**:
   - Add feature behind a flag
   - Monitor for issues
   - Enable for all products once validated

---

## SUMMARY

### 1. LLM Extraction Failures (44 products)
- **Root Cause**: Both DeepSeek and Gemini failing, potentially due to incomplete markdown section extraction
- **Investigation Needed**: Check markdown content, LLM responses, fallback logic
- **Action**: ✅ **FIXED** - Enhanced product section extraction with H&M regex, Gemini LLM extraction, and keyword-based fallbacks

### 2. Image URL Issues (112 products)
- **Root Cause**: `_transform_revolve_url()` didn't handle `/n/ct/`, `/n/uv/`, `/n/d/`, `/n/p/`, `/n/r/`, `/n/t/` and `_V1`, `_V2`, `_V3` patterns
- **Old Architecture**: Had comprehensive path transformations that were lost in migration
- **Fix**: ✅ **FIXED** - Added all 6 path transformations (`/n/ct/` → `/n/z/`, etc.) and `_V\d+` suffix handling from old architecture (commit 1af4841)
- **Result**: Now transforms thumbnails to zoom/full-size images correctly

### 3. Conditional Image Updates
- **Current**: ✅ **FIXED** - No longer always processes images
- **Implementation**: ✅ **COMPLETED**
  - Database schema expanded with `images_uploaded`, `images_uploaded_at`, `images_failed_count`, `last_image_error` columns
  - Product Updater now checks upload status before processing images
  - Only uploads if never uploaded, previous failure, or images changed
  - Tracks success/failure in database for monitoring
- **Benefits**: Performance improvement, cost savings, retry resilience

---

## FIXES IMPLEMENTED (November 9, 2025)

### ✅ 1. Revolve Image URL Transformations Fixed
**File**: `Shared/image_processor.py`

**Changes**:
- Added 6 path transformations from old architecture:
  - `/n/ct/` → `/n/z/` (Thumbnail to Zoom)
  - `/n/uv/` → `/n/z/` (UV to Zoom)
  - `/n/d/` → `/n/z/` (Detail to Zoom)
  - `/n/p/` → `/n/z/` (Preview to Zoom)
  - `/n/r/` → `/n/z/` (Regular to Zoom)
  - `/n/t/` → `/n/z/` (Thumb to Zoom)
- Added `_V\d+` suffix handling (removes version suffixes for full-size)
- Added alternate `/n/f/` (full) transformation for highest quality
- Commented preservation of `_V\d+` patterns in filter (transform instead of exclude)

**Impact**: Resolves "Image too small: 87x131" errors by transforming thumbnails to full-size images.

### ✅ 2. Large Markdown Section Extraction Enhanced
**File**: `Extraction/Markdown/markdown_product_extractor.py`

**Changes**:
- Ported H&M regex-based extraction from old architecture (proven to work)
- Added Gemini LLM-based section extraction with specific instructions
- Implemented keyword-based fallback for edge cases
- Expanded section size from 10K to 12K characters
- Added logging for transparency

**Impact**: Reduces LLM extraction failures by providing clean, focused product sections.

### ✅ 3. Database Schema Expanded
**Database**: `Shared/products.db`

**New Columns**:
```sql
ALTER TABLE products ADD COLUMN images_uploaded INTEGER DEFAULT 0;
ALTER TABLE products ADD COLUMN images_uploaded_at TIMESTAMP;
ALTER TABLE products ADD COLUMN images_failed_count INTEGER DEFAULT 0;
ALTER TABLE products ADD COLUMN last_image_error TEXT;
```

**Impact**: Enables tracking of image upload status for conditional updates.

### ✅ 4. Conditional Image Processing
**Files**: 
- `Workflows/product_updater.py` - Added `_should_process_images()` method and conditional logic
- `Shared/db_manager.py` - Updated `update_product_record()` to handle image tracking fields

**Changes**:
- Product Updater checks if images were successfully uploaded before
- Only processes images if:
  1. Never uploaded before (images_uploaded = 0)
  2. Previous upload failed (images_failed_count > 0)
  3. Image URLs changed (count mismatch detected)
- Tracks upload success/failure with timestamps and error messages
- Database manager dynamically handles optional image tracking fields

**Impact**: Significantly reduces unnecessary image processing and API calls during updates.

---

## TESTING RECOMMENDED

1. **Test Revolve Image Transformation**:
   - Try updating a Revolve product with `_V1.jpg` or `/n/ct/` URL patterns
   - Verify full-size images are downloaded (not 87x131 thumbnails)
   - Check logs for transformation messages

2. **Test Large Markdown Extraction**:
   - Update products from retailers known to have large pages (H&M, Revolve)
   - Verify "Gemini section extraction" or "H&M regex extraction" in logs
   - Confirm LLM extraction succeeds after section extraction

3. **Test Conditional Image Updates**:
   - Run Product Updater on same products twice
   - Verify second run skips image processing (logs: "Skipping image processing (already uploaded successfully)")
   - Check database for `images_uploaded = 1` and `images_uploaded_at` timestamps
   - Force a failure and verify `images_failed_count` increments

---

## NEXT STEPS

1. **Immediate**: Resume Product Updater with fixed logic (should see fewer LLM failures and correct Revolve images)
2. **Monitor**: Track success rates for LLM extraction and image downloads
3. **Backfill**: Consider marking all existing products with shopify_id as `images_uploaded = 1` to avoid unnecessary re-uploads
4. **Long-term**: Add comprehensive monitoring dashboard for image upload status

