# Catalog Extraction - Design Decisions & Trade-offs

**Last Updated**: November 6, 2025  
**Purpose**: Track all design decisions, trade-offs, debugging lessons, and rationale for catalog extraction architecture

---

## 🎯 Current Architecture (As of Nov 6, 2025)

### Patchright Catalog Extraction Flow:
1. **Gemini Vision** extracts ALL visual product data from screenshot(s)
2. **DOM** extracts product URLs + optionally validates Gemini data  
3. **Merge** combines Gemini's visual data with DOM's URLs
4. **Result**: Products with complete data (title, price, images, URL)

---

## 📊 Historical Decisions & Rationale

### Decision #1: Gemini Vision Primary, DOM Secondary (Oct 2025)

**Context**: Initial implementation had DOM as primary extractor

**Problem**: 
- DOM extraction on catalog pages is "messy" with hundreds of product cards
- Different retailers have wildly different HTML structures
- Selectors break frequently when sites update
- Difficult to extract clean titles/prices from complex card layouts

**Decision**: Make Gemini Vision the primary extractor for catalog pages

**Rationale**:
```
✅ Gemini can "see" products like a human
✅ No selector brittleness
✅ Works across any retailer's HTML structure
✅ Can extract visual details (sale badges, colors, etc.)
❌ But: Cannot read URLs from screenshots
❌ But: Expensive for large catalogs (multiple API calls)
```

**Implementation**:
- Gemini extracts: titles, prices, images, sale status
- DOM extracts: URLs, product codes (from `href` attributes)
- Merge matches them by position or fuzzy title matching

**Files**: 
- `Shared/playwright_agent.py` - `extract_catalog()` method
- `Catalog Crawler/catalog_extractor.py` - routing logic

---

### Decision #2: Full-Page Screenshot with Resize (Nov 6, 2025)

**Context**: Testing Abercrombie revealed issues with 3-viewport screenshots

**Problem**:
- Taking 3 separate viewport screenshots (top/middle/bottom)
- Products split across screenshot boundaries
- Unnecessary scrolling for paginated sites
- Complex to manage multiple screenshot descriptions

**Decision**: Take ONE full-page screenshot, resize if needed

**Rationale**:
```
✅ Captures ALL products on page at once
✅ No boundary issues (products split in half)
✅ Simpler logic (one screenshot, one Gemini call)
✅ Works for both infinite scroll AND pagination
❌ But: Very tall pages (33,000+ pixels) must be resized
❌ But: Resizing loses detail (compression artifacts)
```

**Limitations Discovered**:
- Gemini converts images to WebP internally (16,383px height limit)
- Screenshots taller than 16,000px must be resized
- Resizing from 33,478px → 16,000px loses ~52% of detail
- **Result**: Gemini can only extract 4 products from 71 visible

**Files**:
- `Shared/playwright_agent.py` lines 312-323 (screenshot capture)
- `Shared/playwright_agent.py` lines 369-379 (resize logic)

---

### Decision #3: Natural Page Load Wait After Verification (Nov 6, 2025)

**Context**: Anthropologie loaded but DOM found 0 products initially

**Problem**:
- After bypassing PerimeterX verification, page was still loading
- JavaScript-heavy SPAs need time to render product grids
- Previous logic waited only 3 seconds total
- DOM extraction happened before products fully rendered

**Decision**: Implement human-like wait strategy

**Rationale**:
```
✅ Wait for networkidle (15s timeout)
✅ Additional 4s human viewing delay
✅ Try learned selectors to confirm products loaded
✅ Fallback to fixed 2s animation wait
✅ Total: ~20 seconds of natural waiting
❌ But: Slower crawling (20s vs 3s per page)
✅ But: Higher success rate (71 URLs vs 0 URLs found)
```

**Implementation**:
```python
await self.page.wait_for_load_state('networkidle', timeout=15000)
await asyncio.sleep(4)  # Human page viewing time
# Try selectors...
await asyncio.sleep(2)  # Animation completion
```

**Files**:
- `Shared/playwright_agent.py` lines 254-307

---

## 🔄 Current Issue: Gemini Vision Limitations (Nov 6, 2025)

### The Problem

**Anthropologie Test Results**:
- Full-page screenshot: 2400x33,478 pixels
- Resized to: 1147x16,000 pixels (52% compression)
- Gemini extracted: **4 products** (visual data)
- DOM found: **71 URLs** (complete URLs)
- Merged result: **4 complete products** (only what Gemini saw)
- **Lost: 67 products** (DOM URLs with no visual match)

### Why This Happens

1. **Screenshot Compression**:
   - Original: 33,478px tall (all 71 products visible)
   - Resized: 16,000px tall (to fit Gemini's WebP limit)
   - Compression: 52% smaller (products become tiny)
   - Result: Gemini can only confidently read 4 products at full detail

2. **Merge Logic**:
   - Matches Gemini's visual data with DOM's URLs
   - If Gemini didn't extract a product, it's discarded
   - DOM found 67 additional URLs with no matching Gemini data
   - Those 67 URLs are thrown away

### Proposed Solutions & Trade-offs

#### **Option A: Split Screenshot into Tiles** 

**Approach**: Split 33,478px screenshot into 3 chunks of ~11,000px each

**Pros**:
- ✅ Full resolution for each tile (no compression)
- ✅ Gemini can read all products clearly
- ✅ Extract all 71 products

**Cons**:
- ❌ 3x API cost ($0.009 vs $0.003 per page)
- ❌ Products split at tile boundaries (cut in half)
- ❌ More complex merging logic

**Cost Impact**:
- Current: 1 Gemini call per page
- Proposed: 3 Gemini calls per page
- For baseline (100 pages): $0.30 → $0.90

---

#### **Option B: DOM-First for Long Catalog Pages** ⭐ (RECOMMENDED)

**Approach**: Use DOM as primary extractor when screenshot must be heavily resized

**Flow**:
```
1. Check screenshot height
2. If > 16,000px → DOM-FIRST mode
   - DOM extracts ALL URLs + titles + prices
   - Gemini validates SAMPLE (5-10 products)
   - Use Gemini's validation to verify DOM quality
   - Keep ALL DOM products
3. If < 16,000px → GEMINI-FIRST mode (current)
   - Gemini extracts visual data
   - DOM adds URLs
```

**Pros**:
- ✅ Extract ALL 71 products (no loss)
- ✅ Low cost (still 1 Gemini call, just for validation)
- ✅ DOM URLs are 100% accurate (we proved this: 71/71 found)
- ✅ DOM titles/prices are ~80%+ accurate for most retailers
- ✅ Gemini validates quality (catches DOM extraction issues)

**Cons**:
- ⚠️ DOM extraction can be "messy" (different selectors per retailer)
- ⚠️ Requires good pattern learning (track which selectors work)
- ⚠️ May miss visual-only data (sale badges, colors)

**Why This Works Now**:
- ✅ Pattern learning system exists (track successful selectors)
- ✅ We've proven DOM URL extraction works (71/71 URLs found)
- ✅ Most retailers have predictable HTML structures
- ✅ Gemini validation catches DOM failures
- ✅ For short pages (<16K), Gemini is still primary

**Implementation Strategy**:
```python
# In extract_catalog():
screenshot_height = image.height

if screenshot_height > 16000:
    logger.info(f"📏 Page too tall for full Gemini extraction ({screenshot_height}px)")
    logger.info("🔄 Switching to DOM-primary mode with Gemini validation")
    
    # DOM extracts everything
    dom_products = await self._extract_catalog_products_from_dom(retailer)
    
    # Gemini validates a sample (resize screenshot for sample)
    gemini_sample = await self._gemini_validate_sample(screenshots, retailer, sample_size=10)
    
    # Merge: Keep ALL DOM products, enhance with Gemini validation
    final_products = self._merge_dom_primary(dom_products, gemini_sample)
    
else:
    # Current flow: Gemini primary
    gemini_products = await self._gemini_extract_all(screenshots)
    dom_urls = await self._extract_catalog_product_links_from_dom(retailer)
    final_products = self._merge_catalog_dom_with_gemini(dom_urls, gemini_products)
```

---

#### **Option C: Hybrid Chunking (Smart Tiles)** 

**Approach**: Only tile the screenshots that need it

**Implementation**:
- If height < 16,000px: Single screenshot (Gemini primary)
- If height 16,000-25,000px: 2 tiles with overlap
- If height > 25,000px: DOM primary mode

**Pros**:
- ✅ Balances cost and quality
- ✅ No compression for short pages
- ✅ Controlled cost increase

**Cons**:
- ⚠️ Most complex implementation
- ⚠️ Still has boundary issues
- ⚠️ Variable cost (hard to predict)

---

## 🎓 Lessons Learned

### From Abercrombie Test (Nov 6, 2025):
1. **JavaScript href properties** > HTML attributes
   - `get_attribute('href')` returned `None` for all 90 links
   - `evaluate('el => el.href')` worked perfectly
   - **Lesson**: Always try JS property as fallback

2. **Wait for dynamic content** explicitly
   - `wait_for_selector()` with product card selectors
   - Don't rely on `networkidle` alone
   - **Lesson**: Confirm products loaded before extracting

3. **Full-page screenshot** > Multiple viewport screenshots
   - No boundary issues
   - Simpler logic
   - **Lesson**: One good screenshot beats three fragmented ones

### From Anthropologie Test (Nov 6, 2025):
1. **PerimeterX bypass** requires keyboard navigation
   - Mouse clicks don't work (detected as bot)
   - TAB + SPACE hold bypasses successfully
   - **Lesson**: Keyboard events harder to fingerprint

2. **Natural waiting** mimics human behavior
   - 4s page viewing delay
   - 2s animation completion
   - **Lesson**: Slower = more reliable + less bot-like

3. **Screenshot compression** loses information
   - 52% compression = only 6% of products readable
   - Resizing huge pages makes them unreadable
   - **Lesson**: DOM extraction needed for tall pages

---

## ✅ Recommended Decision (Nov 6, 2025)

### **Implement Option B: DOM-First for Long Pages**

**Rationale**:
1. **Cost-effective**: No 3x API cost increase
2. **Complete data**: Extract ALL 71 products, not just 4
3. **Proven working**: DOM found 71/71 URLs successfully
4. **Validated quality**: Gemini validates sample for accuracy
5. **Best of both**: Gemini for short pages, DOM for long pages
6. **Pattern learning**: System improves over time

**Implementation Plan**:
1. Add height check in `extract_catalog()`
2. Implement `_extract_catalog_products_from_dom()` (full extraction)
3. Implement `_gemini_validate_sample()` (sample validation)
4. Implement `_merge_dom_primary()` (keep all DOM products)
5. Update pattern learning to track DOM extraction success
6. Test on Anthropologie (71 products expected)

**Success Criteria**:
- ✅ Extract 71/71 products from Anthropologie
- ✅ Cost remains ~$0.003 per page
- ✅ Gemini validation catches DOM errors
- ✅ Pattern learning improves accuracy over time

---

## 📝 Next Steps

**Immediate**:
1. Get user approval for Option B (DOM-first for long pages)
2. Implement the height-based routing logic
3. Test on Anthropologie (current failure case)
4. Verify 71 products extracted successfully

**Future**:
1. Monitor DOM extraction quality across retailers
2. Improve pattern learning for DOM selectors
3. Consider Option C (hybrid chunking) if Option B has issues
4. Document per-retailer DOM patterns

---

## 📚 Related Documents
- `PERIMETERX_BREAKTHROUGH.md` - PerimeterX keyboard bypass solution
- `PATCHRIGHT_CATALOG_TEST_LOG.md` - Test history and results
- `SYSTEM_OVERVIEW.md` - Overall system architecture
- `Shared/page_structure_learner.py` - Pattern learning implementation

---

**Status**: Awaiting user decision on Option B implementation

