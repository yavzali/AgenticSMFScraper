# Unpropagated Fixes & Knowledge Gap Analysis
**Created**: November 11, 2025 (22:08)  
**Context**: Systematic review of Knowledge folder to identify unpropagated fixes

---

## ✅ ALREADY PROPAGATED (No Action Needed)

### 1. Revolve URL Transformations ✅
- **Source**: `SYSTEM_WIDE_PROPAGATION_CHECKLIST.md` Task 2
- **Fix**: Changed `/n/z/` → `/n/d/` (verified working pattern)
- **Location**: `Shared/image_processor.py`
- **Propagated To**: ALL workflows (centralized)
- **Status**: ✅ COMPLETE (just fixed today)

### 2. Image Upload Tracking ✅
- **Source**: `SYSTEM_WIDE_PROPAGATION_CHECKLIST.md`
- **Fix**: Set `images_uploaded=1` AFTER Shopify confirms upload
- **Location**: `Shared/db_manager.py`, `Product Updater`, `Catalog Monitor`
- **Status**: ✅ COMPLETE

### 3. DeepSeek Logging Enhancement ✅
- **Source**: `PRODUCT_UPDATER_TRUE_ROOT_CAUSE.md`
- **Fix**: Changed `logger.debug()` → `logger.info()/warning()` for visibility
- **Location**: `Extraction/Markdown/markdown_product_extractor.py`
- **Status**: ✅ COMPLETE (implemented during Product Updater debugging)

### 4. DeepSeek → Gemini Cascade ✅
- **Source**: `PRODUCT_UPDATER_TRUE_ROOT_CAUSE.md`
- **Fix**: DeepSeek first, then Gemini fallback (with early validation)
- **Location**: `Extraction/Markdown/markdown_product_extractor.py`
- **Status**: ✅ COMPLETE (section extraction now uses DeepSeek first)

### 5. Validation Strictness ✅
- **Source**: `VALIDATION_COMPARISON.md`, `PRODUCT_UPDATER_TRUE_ROOT_CAUSE.md`
- **Fix**: Reverted to stricter validation (old architecture)
- **Location**: `markdown_product_extractor.py`
- **Status**: ✅ COMPLETE (just fixed today)

### 6. NULL Title Bug ✅
- **Source**: `CATALOG_MONITOR_NULL_TITLE_FIX.md`
- **Fix**: `batch_update_products` only updates non-NULL fields
- **Location**: `Shared/db_manager.py`
- **Status**: ✅ COMPLETE (just fixed today)

### 7. Normalized URL Deduplication ✅
- **Source**: Old architecture comparison
- **Fix**: Strip `?params` from BOTH incoming and stored URLs
- **Location**: `Shared/db_manager.py`
- **Status**: ✅ COMPLETE (just fixed today)

---

## ⚠️ NEEDS VERIFICATION (High Priority)

### 1. File Cleanup in Catalog Monitor ⚠️
**Source**: `SYSTEM_WIDE_PROPAGATION_CHECKLIST.md` Task 1

**Issue**: Catalog Monitor downloads images to disk, uploads to Shopify. Are files cleaned up?

**Current Flow**:
```python
# Workflows/catalog_monitor.py line ~850
downloaded_images = await image_proc.process_images(...)  # Downloads to disk
result = await shopify.create_product(..., downloaded_images=...)  # Uploads
# Files deleted?
```

**Expected**: `shopify_manager.create_product()` calls `_upload_images()` which should delete files

**Verification Needed**:
```bash
# Before test:
ls -la Shared/downloads/

# Run: Catalog Monitor on 1 new product

# After test:
ls -la Shared/downloads/  # Should be empty or only contain that test
```

**Risk**: MEDIUM (disk accumulation)  
**Effort**: 5 minutes to verify

---

### 2. External State Flags (shopify_id, shopify_status) ⚠️
**Source**: `SYSTEM_WIDE_PROPAGATION_CHECKLIST.md` Task 4

**Issue**: Are `shopify_id` and `shopify_status` set AFTER Shopify API confirms, or prematurely?

**Pattern to Check**:
```python
# ❌ BAD
data['shopify_id'] = product_id  # Set before API call
result = await shopify_api.create(data)

# ✅ GOOD
result = await shopify_api.create(data)
if result['success']:
    data['shopify_id'] = result['product_id']  # Set after confirmation
```

**Files to Check**:
1. `Workflows/catalog_monitor.py` - Where `shopify_id` is set after draft upload
2. `Workflows/product_updater.py` - Where `shopify_status` might be updated
3. `Shared/shopify_manager.py` - Where Shopify API returns product ID

**Risk**: MEDIUM (data integrity)  
**Effort**: 15 minutes to review

---

## ⚠️ NOT TESTED (Medium Priority)

### 3. Other Retailer URL Transformations ⚠️
**Source**: `SYSTEM_WIDE_PROPAGATION_CHECKLIST.md` Task 2

**Issue**: Revolve had broken URL transformations. Other retailers might too.

**Retailers NOT Tested**:

| Retailer | CDN | Transformation Pattern | Risk |
|----------|-----|------------------------|------|
| **Anthropologie** | Adobe Scene7 | `$product$` → `$zoom$`, wid/hei params | HIGH (similar to Revolve) |
| **H&M** | Azure CDN | hmgoepprod.azureedge.net | MEDIUM |
| **Aritzia** | media.aritzia.com | `_small` → `_large` | MEDIUM |
| **Uniqlo** | Images CDN | `/300w/` → `/1200w/` | LOW (simple pattern) |
| **Abercrombie** | Scene7 | wid/hei params | MEDIUM |
| **Nordstrom** | nordstrommedia.com | `/300/` → `/1200/` | LOW |

**Verification Process**:
1. Get sample product URL from each retailer
2. Extract image URLs
3. Check transformed URL with HTTP HEAD request
4. If 404: Investigate correct pattern (like we did for Revolve)

**Test Script**:
```python
import requests
from Shared.image_processor import ImageProcessor

proc = ImageProcessor()

# Test each retailer
retailers = {
    'anthropologie': 'https://anthropologie.scene7.com/is/image/Anthropologie/12345_sw.jpg',
    'hm': 'https://image.hm.com/assets/hm/12/34/123456.jpg',
    # ... etc
}

for retailer, url in retailers.items():
    enhanced = proc._enhance_urls([url], retailer)[0]
    response = requests.head(enhanced, timeout=5)
    print(f"{retailer}: {response.status_code} {'✅' if response.status_code == 200 else '❌'}")
```

**Risk**: HIGH (affects image quality for all new products from those retailers)  
**Effort**: 1-2 hours for all retailers

---

## 🟢 PATCHRIGHT-ONLY (Low Priority - Not Used Yet)

### 4. JavaScript Property Extraction
**Source**: `DEBUGGING_LESSONS.md` - JavaScript Property Extraction

**Issue**: SPA sites set hrefs as JS properties, not HTML attributes

**Solution**:
```python
# Try attribute first
href = await link.get_attribute('href')

# Fallback to JS property
if not href:
    href = await link.evaluate('el => el.href')
```

**Applicable To**: Anthropologie, Abercrombie, Urban Outfitters (Patchright tower)

**Status**: NOT NEEDED YET (Patchright tower not actively used)  
**Priority**: LOW (implement when using Patchright)

---

### 5. Dynamic Content Loading Waits
**Source**: `DEBUGGING_LESSONS.md` - Dynamic Content Loading

**Issue**: JavaScript SPAs render content AFTER `networkidle`

**Solution**:
```python
await page.wait_for_selector('.product-card', timeout=10000, state='visible')
await asyncio.sleep(4)  # Human viewing delay
```

**Applicable To**: All Patchright retailers

**Status**: NOT NEEDED YET (Patchright tower not actively used)  
**Priority**: LOW (implement when using Patchright)

---

### 6. Anti-Bot Techniques
**Source**: `DEBUGGING_LESSONS.md` - Anti-Bot Bypass Techniques

**Techniques**:
1. Keyboard navigation for PerimeterX Press & Hold
2. Gemini Vision click for PerimeterX button
3. Extended wait + scroll for Cloudflare

**Applicable To**: Anthropologie, Urban Outfitters, Aritzia (Patchright)

**Status**: NOT NEEDED YET  
**Priority**: LOW

---

## 🔵 ARCHITECTURAL (Future Consideration)

### 7. Direct URL Upload to Shopify
**Source**: `SYSTEM_WIDE_PROPAGATION_CHECKLIST.md` Task 5

**Current**: Download → Validate → Optimize → Upload → Delete
**Alternative**: Direct URL upload (Shopify fetches from retailer)

**Trade-offs**:
- ✅ Faster (1-step)
- ✅ No disk usage
- ❌ No validation/optimization
- ❌ Shopify might fail to fetch

**Recommendation**: Keep current approach (proven reliable)  
**Priority**: LOW (optional optimization)

---

## 📋 ACTION ITEMS (Prioritized)

### IMMEDIATE (Today - 30 minutes)
1. ✅ **Verify File Cleanup** in Catalog Monitor
   - Check if `create_product()` calls `_upload_images()` with cleanup
   - Test: Run Catalog Monitor on 1 product, check `Shared/downloads/` is empty

2. ✅ **Review External State Flags**
   - Verify `shopify_id` set AFTER API confirmation
   - Verify `shopify_status` set AFTER API confirmation

### IMPORTANT (Tomorrow Morning - 2 hours)
3. ⚠️ **Test Anthropologie URL Transformations**
   - High risk (Scene7 CDN similar to Revolve issues)
   - Get sample product, test transformation returns 200

4. ⚠️ **Test H&M URL Transformations**
   - Azure CDN - different pattern than Revolve

5. ⚠️ **Test Aritzia URL Transformations**
   - `_small` → `_large` might be too simple/broken

### IF TIME PERMITS (This Week - 2 hours)
6. 🔵 **Test Remaining Retailers**
   - Uniqlo, Abercrombie, Nordstrom
   - Lower priority (simpler patterns)

7. 🟢 **Document Patchright Patterns**
   - When we activate Patchright tower, implement:
   - JS property extraction
   - Dynamic content waits
   - Anti-bot techniques

---

## 🎯 CRITICAL vs NON-CRITICAL

### CRITICAL (Affects Current Workflows)
1. ✅ File cleanup verification (Catalog Monitor)
2. ✅ External state flags (data integrity)
3. ⚠️ Anthropologie/H&M/Aritzia URL transformations (image quality)

### NON-CRITICAL (Future/Unused Features)
1. 🟢 Patchright-specific techniques (tower not active)
2. 🔵 Direct URL upload (optimization, not fix)

---

## 📚 LESSONS APPLIED

### From Knowledge Folder → Current System

1. **Track State After External Confirmation** ⭐⭐⭐
   - ✅ Applied: `images_uploaded` set after Shopify confirms
   - ⚠️ Verify: `shopify_id`, `shopify_status` follow same pattern

2. **Clean Up Temporary Files** ⭐⭐⭐
   - ✅ Applied: Product Updater cleanup added
   - ⚠️ Verify: Catalog Monitor cleanup works

3. **Validate Retailer-Specific Transformations** ⭐⭐
   - ✅ Applied: Revolve tested and fixed
   - ⚠️ Pending: Other 7 retailers need testing

4. **Separate Failure Types** ⭐⭐
   - ✅ Applied: Image processor distinguishes download/validation/upload failures
   - ✅ Applied: LLM cascade logs each stage

---

## 🚨 HIGH-RISK GAPS

### Gap #1: Unverified Retailer URL Transformations
**Risk**: New products from Anthropologie/H&M/Aritzia might have:
- 404 image URLs (broken transformations)
- Low-res images (transformation not applied)
- Missing images (download failures)

**Mitigation**: Test before next Catalog Monitor run for those retailers

---

### Gap #2: File Cleanup Verification
**Risk**: Disk accumulation if cleanup not working
- 99 files found before (Product Updater)
- Catalog Monitor might accumulate too

**Mitigation**: Verify today before next run

---

## ✅ VERIFICATION CHECKLIST

- [x] Revolve URL transformations (just tested - working)
- [ ] File cleanup in Catalog Monitor
- [ ] External state flags (shopify_id, shopify_status)
- [ ] Anthropologie URL transformations
- [ ] H&M URL transformations
- [ ] Aritzia URL transformations
- [ ] Uniqlo URL transformations
- [ ] Abercrombie URL transformations
- [ ] Nordstrom URL transformations

---

**Status**: 7/15 items verified (47%)  
**Critical Items Remaining**: 2 (file cleanup, state flags)  
**Priority**: Address critical items today, retailers tomorrow


