# Catalog Monitor Bug Investigation
**Date:** 2025-11-11  
**Status:** Bugs identified, fixes in progress

---

## Bugs Found & Status

### ✅ FIXED

1. **Missing `description` Column**
   - **Error:** `table products has no column named description`
   - **Fix:** Added `description TEXT` column to products table
   - **Status:** ✅ COMPLETE

2. **Revolve Image URL Transformation Bug**
   - **Error:** Converting image URLs to `/n/z/` path which returns HTTP 404
   - **Root Cause:** Revolve changed their CDN structure - `/n/z/` (zoom) no longer works
   - **Verified Working:** `/n/d/` (detail) and `/n/c/` (catalog) return HTTP 200
   - **Fix:** Modified `image_processor.py` to convert problematic patterns to `/n/d/` instead
   - **Status:** ✅ COMPLETE

3. **Catalog Monitor Workflow Architecture**
   - **Review:** Confirmed workflow is CORRECT - it does:
     1. Lightweight catalog extraction (MarkdownCatalogExtractor)
     2. Deduplication against baseline + products DB
     3. Full extraction (MarkdownProductExtractor) ONLY for new products
   - **Status:** ✅ VERIFIED CORRECT

---

### ❌ STILL BROKEN

4. **DeepSeek V3 Timeout on Catalog Extraction**
   - **Error:** DeepSeek times out after 60s when extracting catalog pages
   - **Root Cause:** 40K characters of markdown is too large for DeepSeek to process quickly
   - **Log:** `⏱️ DeepSeek V3 catalog extraction timed out after 60s`
   - **Status:** ❌ NEEDS FIX
   - **Possible Solutions:**
     - Reduce markdown chunk size (20K instead of 40K)
     - Increase timeout (90s or 120s)
     - Better product section detection
     - Use Gemini first for catalogs (if we fix Gemini issue)

5. **Gemini Flash 2.0 "Thinking" Field Error**
   - **Error:** `Unknown field for Part: thought`
   - **Root Cause:** `gemini-2.0-flash-exp` model is returning thinking/reasoning tokens that langchain doesn't recognize
   - **Model:** `gemini-2.0-flash-exp` (experimental)
   - **Status:** ❌ NEEDS FIX
   - **Possible Solutions:**
     - Switch to stable `gemini-1.5-flash` or `gemini-1.5-pro`
     - Add thinking mode handling to langchain client
     - Use direct Google AI API instead of langchain wrapper
     - Set model parameters to disable thinking mode

---

## Test Results

### Catalog Monitor Test Run (2025-11-11 16:05:33)

**Test Command:**
```bash
python3 Workflows/catalog_monitor.py revolve dresses modest --max-pages 1
```

**Sequence of Events:**
1. ✅ Initialized all towers successfully
2. ✅ Fetched markdown (41,700 chars)
3. ✅ Detected large markdown, extracted first 40K chars
4. ❌ DeepSeek V3 timed out after 60s
5. ❌ Gemini Flash 2.0 failed with "Unknown field for Part: thought" error after 47s
6. ❌ Catalog extraction failed (both LLMs failed)
7. ❌ Monitor workflow stopped

---

## Comparison with Old Architecture

### Old Architecture (Git Hash: 621349b)

**How it worked:**
1. ✅ Used same pipe-separated text format: `PRODUCT | URL=... | TITLE=... | PRICE=...`
2. ✅ Used markdown extraction for Revolve
3. ✅ Had same prompt structure
4. ❓ Unknown: What model did it use? (need to check)
5. ❓ Unknown: What were the timeout settings?
6. ❓ Unknown: How did it handle large markdown?

**Key Differences:**
- Old: Used `ChatGoogleGenerativeAI` (model unknown)
- New: Using `gemini-2.0-flash-exp` (experimental)

---

## Recommended Fixes (Priority Order)

### HIGH PRIORITY

1. **Fix Gemini "Thinking" Error**
   - Switch from `gemini-2.0-flash-exp` to `gemini-1.5-flash` (stable)
   - OR: Add thinking mode handling
   - **Impact:** Would make catalog extraction work immediately

2. **Reduce Markdown Chunk Size**
   - Current: 40K chars → DeepSeek timeout
   - Proposed: 20K chars (more manageable)
   - Better product marker detection
   - **Impact:** Would make DeepSeek faster/more reliable

### MEDIUM PRIORITY

3. **Increase LLM Timeouts**
   - Current: 60s for both DeepSeek and Gemini
   - Proposed: 90s for catalogs (larger content)
   - **Impact:** Gives models more time to process

4. **Better Product Section Detection**
   - Current: Generic markers like "product-card"
   - Proposed: Retailer-specific markers for Revolve
   - **Impact:** Smaller, more targeted markdown chunks

### LOW PRIORITY

5. **LLM Model Selection Per Task**
   - Use Gemini for catalog extraction (faster)
   - Use DeepSeek for single product extraction (more accurate)
   - **Impact:** Optimize for speed vs accuracy

---

## Files Modified

1. `/Users/yav/Agent Modest Scraper System/Shared/products.db`
   - Added `description TEXT` column

2. `/Users/yav/Agent Modest Scraper System/Shared/image_processor.py`
   - Fixed `_transform_revolve_url()` function
   - Changed `/n/z/` → `/n/d/` transformations

3. `/Users/yav/Agent Modest Scraper System/Extraction/Markdown/markdown_catalog_extractor.py`
   - Added 60s timeouts to DeepSeek and Gemini calls
   - Added timeout logging
   - Added better product section logging

---

## Next Steps

1. ✅ Document all findings (this file)
2. ⏳ Fix Gemini model issue (switch to stable version)
3. ⏳ Test catalog extraction with fixes
4. ⏳ If successful, run full Catalog Monitor test
5. ⏳ Re-run Product Updater to backfill NULL titles (REQUIRES USER PERMISSION)

---

## Open Questions for User

1. **Gemini Model:** Should we switch to `gemini-1.5-flash` (stable) or try to fix the thinking mode issue with `gemini-2.0-flash-exp`?

2. **DeepSeek Timeout:** Should we increase timeout to 90s/120s or reduce markdown size to 20K?

3. **Old Architecture Model:** What Gemini model was the old architecture using? (need to check config)

4. **Performance Trade-off:** Prioritize speed (smaller chunks, faster timeouts) or accuracy (larger chunks, longer timeouts)?

