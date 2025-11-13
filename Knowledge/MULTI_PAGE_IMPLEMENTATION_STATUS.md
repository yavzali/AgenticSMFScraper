# Multi-Page Catalog Scanning Implementation Status

**Date:** November 12, 2025  
**Status:** Part 1 of 3 Complete

---

## CONTEXT

**Problem Identified:**
1. Gemini Vision only extracting 8 out of 50+ products on Revolve (missing products without loaded images)
2. Paginated retailers (Anthropologie, Urban Outfitters, Nordstrom, Abercrombie) only scanning page 1
3. No validation to catch incomplete extractions

**Solution Approach:**
- **Part 1:** Fix Gemini prompt + Add validation ✅ COMPLETE
- **Part 2:** Add multi-page scanning to `catalog_monitor.py` ⏳ TODO
- **Part 3:** Add multi-page scanning to `catalog_baseline_scanner.py` + Update docs ⏳ TODO

---

## ✅ PART 1 COMPLETE (Committed: 8eb5201)

### 1. Enhanced Gemini Catalog Prompt
**File:** `Extraction/Patchright/patchright_catalog_extractor.py` (lines 241-292)

**Changes:**
- Explicitly instructs Gemini to extract ALL products (even with placeholder images)
- Focuses on title + price as required fields (images optional)
- Strict rules against creating fake/placeholder data
- Clear success criteria: "If you see 50+ product cards, extract 50+ products"

**Expected Impact:**
- Revolve should extract 50-60 products (not just 8)
- Products with loading images will be included

### 2. Extraction Validation
**File:** `Extraction/Patchright/patchright_catalog_extractor.py` (lines 648-793)

**New Method:** `_validate_extraction_quality()`

**Validation Checks:**
1. **Extraction Ratio** - Warns if Gemini < 30% of DOM URLs
2. **Fake Data Detection** - Flags fake titles like "[URL only: ...]"
3. **Invalid Prices** - Detects 0 or negative prices
4. **Minimum Thresholds** - Enforces expected product counts by retailer

**Integration:**
- Called after Gemini extraction, before merge (lines 387-401)
- Logs actionable warnings and errors
- Triggers DOM-first fallback if validation fails critically

### 3. Pagination URL Helper
**File:** `Shared/pagination_url_helper.py` (NEW FILE)

**Functions:**
- `get_pagination_urls(retailer, category)` - Returns [page1_url, page2_url] or None
- `should_use_pagination(retailer)` - Returns True for paginated retailers

**Retailers Configured:**
- ✅ Anthropologie (dresses, tops) - `page` parameter
- ✅ Urban Outfitters (dresses, tops) - `page` parameter  
- ✅ Nordstrom (dresses, tops) - `page` parameter
- ✅ Abercrombie (dresses, tops) - `start` offset parameter

**Infinite Scroll Retailers (1 page):**
- Revolve, ASOS, Mango, Uniqlo, H&M, Aritzia

---

## ⏳ PART 2 TODO: Multi-Page Logic in catalog_monitor.py

**File:** `Workflows/catalog_monitor.py`

**Required Changes:**

1. **Add Import** (top of file):
```python
from pagination_url_helper import get_pagination_urls, should_use_pagination
```

2. **Modify `run_monitoring()` method** (~line 200):
   - Check `should_use_pagination(retailer)`
   - If True: Loop through `get_pagination_urls()`, extract each page
   - Combine results from all pages
   - Perform cross-page deduplication

3. **Add Cross-Page Deduplication Method:**
   - `_deduplicate_in_memory(products)` method
   - Uses URL, product code, and title+price for matching
   - Returns (unique_products, duplicates_removed_count)

4. **Add URL Normalization Helper:**
   - `_normalize_url_for_dedup(url)` method
   - Strips query parameters for consistent matching

**Expected Result:**
- Paginated retailers scan 2 pages automatically
- ~140-180 products per scan (vs ~70-90 single page)
- Cross-page duplicates removed
- Clear logging: "📄 {retailer} uses pagination - scanning 2 pages"

---

## ⏳ PART 3 TODO: Multi-Page Logic in catalog_baseline_scanner.py

**File:** `Workflows/catalog_baseline_scanner.py`

**Required Changes:**
- Nearly identical to Part 2, but in `establish_baseline()` method
- Same pagination logic, cross-page deduplication
- Works with both Markdown and Patchright towers

**Documentation Updates:**

**File:** `Knowledge/RETAILER_CONFIG.json`

Add pagination configuration section:
```json
"pagination_config": {
  "paginated_retailers": ["anthropologie", "urban_outfitters", "nordstrom", "abercrombie"],
  "pages_per_scan": 2,
  "validation_thresholds": {
    "minimum_products_by_retailer": {
      "revolve": 40,
      "anthropologie": 50,
      "urban_outfitters": 50,
      "abercrombie": 60,
      "nordstrom": 40,
      "aritzia": 40
    }
  }
}
```

---

## TESTING PLAN (After Parts 2 & 3)

### Test 1: Gemini Prompt Fix (Part 1 Only)
```bash
python -m Workflows.catalog_monitor revolve tops modest --max-pages 1
```
**Expected:** 50-60 products (not 8), validation passes

### Test 2: Multi-Page Scanning (Abercrombie)
```bash
python -m Workflows.catalog_baseline_scanner abercrombie dresses modest
```
**Expected:** ~180 products across 2 pages, cross-page deduplication logs

### Test 3: Full Workflow (Urban Outfitters)
```bash
python -m Workflows.catalog_monitor urban_outfitters dresses modest
```
**Expected:** 2 pages scanned, new products identified, sent to assessment

---

## CURRENT SYSTEM STATE

**Last Successful Runs:**
- Revolve dresses: 61 products (0 new) - 11/12/2025 12:47
- Revolve tops: 57 products (31 new) - 11/12/2025 13:12

**Database:**
- Total Revolve products: 1,454 (1,362 assessed + 92 queued)
- Assessment queue: 92 products pending modesty review

**Known Issues (Resolved):**
- ✅ Catalog duplicate URLs bug (fixed 11/12)
- ✅ Database schema "images column" bug (fixed 11/12)
- ✅ Duplicate Shopify uploads (49 removed 11/12)

**Commits:**
- `8eb5201` - Part 1: Gemini prompt + validation (11/12/2025)
- `8bad42e` - Catalog deduplication fix (11/12/2025)
- `c3e8054` - Assessment status tracking (11/12/2025)

---

## NEXT STEPS

1. Implement Part 2: Multi-page logic in `catalog_monitor.py`
2. Implement Part 3: Multi-page logic in `catalog_baseline_scanner.py` + docs
3. Test Part 1: Run Revolve tops to verify Gemini extracts 50+ products
4. Test Parts 2-3: Run Abercrombie baseline to verify 2-page scanning
5. Commit final implementation

---

## KEY FILES

**Modified:**
- `Extraction/Patchright/patchright_catalog_extractor.py` - Gemini prompt + validation

**Created:**
- `Shared/pagination_url_helper.py` - URL management for pagination

**To Modify (Parts 2-3):**
- `Workflows/catalog_monitor.py` - Add multi-page scanning
- `Workflows/catalog_baseline_scanner.py` - Add multi-page scanning
- `Knowledge/RETAILER_CONFIG.json` - Document pagination config

