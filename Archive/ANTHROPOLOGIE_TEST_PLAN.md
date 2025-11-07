# 🧪 Anthropologie Catalog Test Plan

## Test Overview
**Goal**: Test the new Patchright DOM validation system on the most difficult retailer  
**Retailer**: Anthropologie  
**Category**: Dresses  
**URL**: https://www.anthropologie.com/dresses?sort=tile.product.newestColorDate&order=Descending  
**Mode**: Baseline establishment (first crawl)

---

## Why Anthropologie?

**Most Difficult Retailer:**
1. ❌ **Press & hold verification** - Human-like interaction required
2. ⚠️ **Patchright extraction** - Uses browser automation (not markdown)
3. ⚠️ **Complex DOM structure** - Artistic layouts, lazy-loading
4. ⚠️ **Pagination-based** - Must handle multiple pages correctly
5. ⚠️ **Previous issues** - You've had image loading problems here before

**If it works here, it works everywhere!**

---

## Test Command

```bash
cd "/Users/yav/Agent Modest Scraper System/Catalog Crawler"
python catalog_main.py --establish-baseline anthropologie dresses
```

**Logs**: `/tmp/anthropologie_test.log`

---

## What Gets Tested

### 1. **Press & Hold Verification Handling** ✅
- Patchright should automatically detect and handle verification
- Popup dismissal (cookie banners, email signups)
- Human-like interaction patterns

### 2. **DOM URL Extraction** ✅
- Extract product link hrefs from catalog page
- Extract product codes from URLs
- Pattern learning (which selectors work)

### 3. **DOM Validation Data** (Optional) ✅
- Try to extract titles from product cards
- Try to extract prices from product cards
- Expected success rate: 40-60% (complex structure)

### 4. **Gemini Vision Extraction** ✅
- Analyze 3 screenshots (top/middle/bottom)
- Extract ALL visible products
- Get titles, prices, images, sale status

### 5. **Hybrid Merge & Validation** ✅
- Match DOM URLs with Gemini visual data
- Validate Gemini titles against DOM (if available)
- Validate Gemini prices against DOM (if available)
- Auto-correct significant mismatches

### 6. **Pattern Learning** ✅
- Record successful selectors
- Track validation statistics
- Build confidence scores

---

## Expected Results

### ✅ **SUCCESS CRITERIA**

```
🎯 Extraction:
✅ 40-60 products extracted
✅ 100% have URLs (DOM extraction)
✅ 100% have product codes (from URLs)
✅ 95%+ have titles (Gemini + DOM corrections)
✅ 95%+ have prices (Gemini + DOM corrections)

🔍 Validation:
✅ 20-30 validation checks performed (40-60% coverage)
✅ 2-8 mismatches found and auto-corrected
✅ 90%+ validation accuracy

🧠 Learning:
✅ Pattern learner records product link selectors
✅ Validation statistics saved
✅ Baseline created in database
```

### ⚠️ **ACCEPTABLE WARNINGS**

```
⚠️ DOM validation coverage: 40-60% (complex structure is expected)
⚠️ Some product cards have no DOM data (lazy-loading)
⚠️ 2-5 Gemini OCR errors caught and corrected
⚠️ Press & hold verification takes 5-10 seconds
```

### ❌ **RED FLAGS (Test Failed)**

```
❌ DOM finds < 20 URLs (selector completely failed)
❌ Gemini extracts < 20 products (visual analysis failed)
❌ Merge fails (can't match DOM and Gemini)
❌ Validation rate < 20% (DOM extraction too weak)
❌ Press & hold verification fails (can't access site)
```

---

## Monitoring the Test

### Check Progress:
```bash
# Watch live log
tail -f /tmp/anthropologie_test.log

# Check last 50 lines
tail -50 /tmp/anthropologie_test.log

# Search for key indicators
grep "DOM found" /tmp/anthropologie_test.log
grep "Validation:" /tmp/anthropologie_test.log
grep "✅" /tmp/anthropologie_test.log
grep "❌" /tmp/anthropologie_test.log
```

### Key Log Messages to Look For:

```
🔍 DOM Extraction:
"✅ DOM found 48 product URLs with codes"
"DOM validation data: 28/48 titles (58%), 32/48 prices (67%)"

🎨 Gemini Vision:
"✅ Gemini extracted 48 products visually"

🔗 Merge & Validation:
"Counts match (48), doing positional merge with validation"
"✅ Validation: 60 checks, 4 mismatches (93% accuracy)"
"💡 4 products corrected using DOM data"

📊 Final Results:
"✅ Patchright catalog extraction successful: 48 products found"
"✅ Baseline established: 48 products"
```

---

## After Test: Verification Steps

### 1. Check Database
```bash
cd "/Users/yav/Agent Modest Scraper System/Catalog Crawler"

# Dry run to see what was created
python cleanup_test_data.py --retailer anthropologie --category dresses

# Shows:
# - Number of products
# - Sample product titles/URLs
# - Monitoring runs
# - Baseline info
```

### 2. Verify Data Quality

**Check Products:**
- ✅ All have valid URLs
- ✅ All have product codes
- ✅ Titles look accurate (not OCR errors)
- ✅ Prices are numeric and reasonable
- ✅ Images URLs are present

**Check Validation:**
- ✅ Some products have validation data
- ✅ Mismatches were logged
- ✅ Corrections were made (if needed)

**Check Pattern Learning:**
- ✅ Product link selectors recorded
- ✅ Validation stats saved
- ✅ Baseline snapshot created

### 3. Review Logs for Issues

```bash
# Check for errors
grep "ERROR" /tmp/anthropologie_test.log

# Check for warnings
grep "WARNING" /tmp/anthropologie_test.log

# Check validation details
grep "mismatch" /tmp/anthropologie_test.log

# Check pattern learning
grep "Learned" /tmp/anthropologie_test.log
```

---

## Cleanup After Test

### Option 1: Dry Run (See What Would Be Deleted)
```bash
cd "/Users/yav/Agent Modest Scraper System/Catalog Crawler"
python cleanup_test_data.py --retailer anthropologie --category dresses
```

### Option 2: Actually Delete
```bash
cd "/Users/yav/Agent Modest Scraper System/Catalog Crawler"
python cleanup_test_data.py --retailer anthropologie --category dresses --confirm
# Then type 'DELETE' to confirm
```

**What Gets Deleted:**
- ✅ All catalog_products entries for anthropologie/dresses
- ✅ All catalog_monitoring_runs entries
- ✅ Baseline entry

**What Stays:**
- ✅ Pattern learner data (selectors, validation stats)
- ✅ Extraction performance history
- ✅ Page structure snapshots
- ✅ Other retailers/categories unaffected

---

## Success Metrics

### **Extraction Quality**
- **Excellent**: 95%+ complete products with accurate data
- **Good**: 85-95% complete products
- **Acceptable**: 75-85% complete products
- **Failed**: < 75% complete products

### **Validation Coverage**
- **Excellent**: 60%+ validation checks
- **Good**: 40-60% validation checks
- **Acceptable**: 20-40% validation checks
- **Failed**: < 20% validation checks

### **Validation Accuracy**
- **Excellent**: 95%+ accuracy (few mismatches)
- **Good**: 90-95% accuracy
- **Acceptable**: 85-90% accuracy
- **Failed**: < 85% accuracy

---

## Next Steps After Success

1. **Test easier retailers** (Abercrombie, Revolve) to confirm nothing broke
2. **Test other difficult retailers** (Aritzia, Urban Outfitters, Nordstrom)
3. **Run full baseline establishment** for all retailers
4. **Start monitoring runs** to detect new products
5. **Deploy to production** with confidence!

---

## Troubleshooting

### If Press & Hold Fails:
- Check Patchright stealth mode is enabled
- Check popup dismissal is working
- May need to adjust verification timeout

### If DOM Extraction Fails:
- Check product link selectors
- Check page structure (may have changed)
- Try different selector patterns

### If Validation Rate Too Low:
- Expected for Anthropologie (complex structure)
- Check if titles/prices are lazy-loaded
- Consider adding more selector patterns

### If Gemini Extraction Fails:
- Check screenshots are being captured
- Check Gemini API key is valid
- Check image quality and visibility

---

## Timeline

**Estimated Duration**: 3-5 minutes
- Navigation & verification: 30-60s
- DOM extraction: 5-10s
- Screenshot capture: 10-20s
- Gemini analysis: 30-60s
- Merge & validation: 5-10s
- Database save: 5-10s

**If it takes > 10 minutes**: Something is stuck (check logs)

