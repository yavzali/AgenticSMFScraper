# Revolve Missing URL Products - Investigation Needed

**Date**: 2024-11-13  
**Discovered During**: Revolve Dresses catalog monitor (after fixing image transformation)

---

## **Issue Summary**

During Revolve dresses catalog monitor run, 12 products were identified as "new" but had no extractable URLs.

### **Symptoms:**
```
Product missing URL, skipping: {
  'title': 'superdown',
  'price': '78',  # or '88'
  'url': None,
  'product_code': None,
  'catalog_url': None
}
```

All 12 products showed same pattern:
- Title: "superdown" (brand name, not product name)
- Price: Either $78 or $88
- URL: None
- Product Code: None

---

## **Context:**

**Catalog Scan Results:**
- Total scanned: 112 products
- New products identified: 12
- Confirmed existing: 100
- **Sent to review: 0** (all 12 skipped due to missing URLs)

**Timing:**
- This happened AFTER we deleted 25 imageless products
- These might be the same products re-detected
- Or could be ad tiles / broken listings on Revolve's page

---

## **Possible Root Causes:**

### **1. Ad Tiles / Sponsored Content** (Most Likely)
- Revolve might have sponsored brand tiles that aren't actual products
- DOM structure different from regular products
- Title extraction gets brand name instead of product name
- No product URL exists (just brand landing page)

### **2. JavaScript-Loaded URLs Not Captured**
- URLs might load even later than our wait strategy
- Container exists but href not populated yet
- Title/price visible but URL still null

### **3. Recent Deletion Side Effect**
- These might be the exact 25 products we just deleted
- System re-detected them as "new" (not in DB anymore)
- But URL extraction mysteriously failing now

### **4. DOM Selector Issue**
- Selector might be matching non-product elements
- Getting brand cards or promotional tiles
- Need to refine product container selector

---

## **What's Working:**

✅ **System handled gracefully** - Skipped bad products instead of crashing  
✅ **Deduplication working** - Recognized 100 existing products correctly  
✅ **Validation working** - Caught missing URLs before processing  
✅ **No bad data created** - Didn't upload products without URLs

---

## **Investigation Steps (TODO):**

1. **Manual Page Inspection:**
   - Visit https://www.revolve.com/womens-clothing-dresses/br/3699fc/
   - Count actual products vs what we extracted (112 vs real count)
   - Look for "superdown" brand tiles or ads
   - Screenshot any non-product elements

2. **DOM Analysis:**
   - Check Revolve's HTML structure for promotional tiles
   - See if "superdown" appears in non-product containers
   - Compare product container vs ad container structure

3. **Selector Refinement:**
   - Update `patchright_retailer_strategies.py` Revolve selectors
   - Add exclusion for promotional/ad containers
   - Test if filtering reduces false positives

4. **Re-run Test:**
   - After selector improvements, re-run Revolve dresses
   - See if 12 products disappear (confirming they're ads)
   - Or if they extract correctly (confirming timing issue)

---

## **Temporary Workaround:**

✅ **Current behavior is acceptable:**
- System correctly skips products without URLs
- No bad data created
- Logs clearly show what was skipped

**No immediate fix needed** - System is working defensively

---

## **RESOLVED** ✅ (Nov 13, 2024)

**Root Cause Found:**
The issue was NOT with product extraction - it was a **configuration bug**:

1. **`patchright_retailer_strategies.py`** configured Revolve as `'catalog_mode': 'dom_first'`
2. **`patchright_catalog_extractor.py`** IGNORED this configuration
3. System still ran Gemini Vision (found 12 products in viewport)
4. DOM extraction found 100 products (correct)
5. Merge logic couldn't match some Gemini products to DOM
6. **Bug:** Unmatched Gemini products were added with `url: None`

**Fix Applied:**
- ✅ Check `strategy.get('catalog_mode')` before retailer-specific checks
- ✅ Revolve now properly uses DOM-first mode (skips Gemini merge issues)
- ✅ Never add products without URLs to merged results
- ✅ Skip unmatched Gemini products (ads, duplicates, edge cases)

**Result:**
- Revolve will extract 100 products (all from DOM with URLs)
- No more `url: None` products entering workflow
- 0 products skipped during single product extraction

**Commit:** bc9c5ad "FIX: Respect catalog_mode=dom_first configuration & never add URL-less products"

---

## **Related Files:**
- `Extraction/Patchright/patchright_catalog_extractor.py` (Revolve extraction logic)
- `Extraction/Patchright/patchright_retailer_strategies.py` (Revolve selectors)
- `Workflows/catalog_monitor.py` (validation and skipping logic)

## **Related Commits:**
- `bb65469` - Fixed Revolve image transformation (thumbnails → full-size)
- `a7c9072` - Deleted 25 imageless products and re-ran

---

**Status**: 📝 Documented, Low Priority  
**Next Action**: Monitor if issue persists or worsens

