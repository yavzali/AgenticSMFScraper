# RETAILER PLAYBOOK
**Consolidated Debugging Solutions & Working Strategies**

**Created**: 2025-11-07  
**Purpose**: Single source of truth for all retailer-specific solutions  
**Status**: Production-ready strategies documented

---

## TABLE OF CONTENTS
1. [Anthropologie](#anthropologie)
2. [Abercrombie](#abercrombie)
3. [Urban Outfitters](#urban-outfitters)
4. [Revolve](#revolve)
5. [Aritzia](#aritzia)
6. [Nordstrom](#nordstrom)
7. [Quick Reference Matrix](#quick-reference-matrix)

---

## ANTHROPOLOGIE

### **Anti-Bot System**: PerimeterX "Press & Hold"
**Status**: ✅ **SOLVED**  
**Complexity**: Very High  
**Solution Date**: Nov 6, 2025

### The Challenge
- Uses PerimeterX sophisticated verification
- Displays: "Press & Hold to confirm you are a human (and not a bot)"
- Button element: `<div class="px-captcha-error-button">`
- Contains hidden `<iframe>` for verification logic
- Resistant to ALL mouse-based automation

### What DIDN'T Work ❌
1. **Mouse coordinates with press & hold**
   - `page.mouse.move(x, y)` + `mouse.down()` + 10s wait + `mouse.up()`
   - Button visual never changed

2. **Dispatching mouse events to element**
   - `element.dispatch_event('mousedown')` + wait + `dispatch_event('mouseup')`
   - No response from verification system

3. **Human-like mouse movements**
   - Random starting positions, gradual movements with delays
   - Still detected as bot

4. **Clicking iframe coordinates**
   - Iframe is `display: none` and not interactive

### The SOLUTION ✅

**Method**: Keyboard Navigation (TAB + SPACE Hold)

```python
# 1. Press TAB multiple times to focus the button
for i in range(10):
    await page.keyboard.press('Tab')
    await page.wait_for_timeout(300)

# 2. Hold SPACE for 10 seconds
await page.keyboard.down('Space')
await page.wait_for_timeout(10000)
await page.keyboard.up('Space')

# 3. Wait for page to load
await page.wait_for_timeout(3000)
```

**Why It Works**:
- Keyboard events harder to detect as bot behavior
- TAB navigation is standard browser behavior
- SPACE key triggers button activation naturally
- No coordinate detection needed

### Page Structure
**Type**: JavaScript SPA with lazy loading  
**Wait Strategy**: `domcontentloaded` (NOT `networkidle`)  
**Reason**: Continuous network activity, `networkidle` times out

### Catalog Extraction
**Mode**: DOM-first (automatic fallback)  
**Issue**: Screenshot too tall (33,478px → 16,000px compression)  
**Solution**: DOM extracts URLs, Gemini validates sample  
**Result**: 71 products extracted

### Product Selectors
```python
# Learned selectors (highest success rate)
product_links = 'a[href*="/shop/"]'
title = 'h1.product-title'
price = '.product-price'
images = 'img[src*="anthropologie.com"]'
```

### Key Configuration
```json
{
  "extraction_method": "patchright",
  "anti_bot": "perimeterx_press_hold",
  "verification_solution": "keyboard_tab_space",
  "wait_strategy": "domcontentloaded",
  "additional_wait_seconds": 4,
  "catalog_extraction_override": "dom_first",
  "popup_types": ["email_signup", "cookie_banner"]
}
```

### Success Metrics
- ✅ Verification bypass: 100% (20/20 tests)
- ✅ Products extracted: 71/71
- ✅ Cost per page: $0.003
- ✅ Total time: ~3 minutes

### Code Locations
- Verification: `patchright_verification.py::handle_press_and_hold()`
- Catalog: `patchright_catalog_extractor.py` (lines 486-503)
- Selectors: Pattern learner database

---

## ABERCROMBIE

### **Anti-Bot System**: Medium Complexity
**Status**: ✅ **WORKING**  
**Complexity**: Medium  
**Test Date**: Nov 6, 2025

### Page Structure
**Type**: JavaScript SPA with dynamic rendering  
**Wait Strategy**: `networkidle` + explicit selector wait  
**Products Load**: AFTER `networkidle` (JavaScript-rendered)

### Catalog Extraction
**Mode**: Gemini-first (normal operation)  
**Result**: 90 products extracted (perfect match)  
**Gemini**: 90 products  
**DOM**: 90 URLs

### Key Learnings
1. **JavaScript href properties > HTML attributes**
   ```python
   # Try attribute first
   href = await link.get_attribute('href')
   if not href:
       # Fallback to JavaScript property
       href = await link.evaluate('el => el.href')
   ```

2. **Explicit wait for dynamic content**
   ```python
   await page.wait_for_selector(
       'a[data-testid="product-card-link"]',
       timeout=10000,
       state='visible'
   )
   ```

3. **Full-page screenshot works perfectly**
   - Single PNG screenshot captures all products
   - No need for multiple scrolls or tiled screenshots

### Product Selectors
```python
product_links = 'a[data-testid="product-card-link"]'
title = 'h2[data-testid="product-title"]'
price = '[data-testid="product-price"]'
```

### Key Configuration
```json
{
  "extraction_method": "patchright",
  "anti_bot": "medium",
  "wait_strategy": "networkidle",
  "product_selector_wait": "a[data-testid=\"product-card-link\"]",
  "wait_timeout_ms": 10000,
  "catalog_extraction": "gemini_first"
}
```

### Success Metrics
- ✅ Products extracted: 90/90 (100%)
- ✅ DOM-Gemini match: Perfect
- ✅ Cost per page: $0.003
- ✅ Time: ~2 minutes

---

## URBAN OUTFITTERS

### **Anti-Bot System**: PerimeterX (Different Implementation)
**Status**: ✅ **WORKING**  
**Complexity**: High  
**Test Date**: Nov 7, 2025

### The Challenge
- Uses PerimeterX but with DIFFERENT verification
- Shows "CONTINUE" button (not "Press & Hold")
- Simpler than Anthropologie's implementation

### The SOLUTION ✅

**Method**: Gemini Vision Click (not keyboard)

```python
# Gemini detects CONTINUE button visually
# Gemini clicks it directly (no hold required)
verification_handled = await self._gemini_handle_verification()
```

**Why Different from Anthropologie**:
- Urban Outfitters: Simple button click
- Anthropologie: Press & hold requirement
- Same PerimeterX provider, different configuration

### Catalog Extraction
**Mode**: Gemini-first (normal operation)  
**Result**: 74 products extracted  
**Gemini**: 6 products visually (page layout issue)  
**DOM**: 74 URLs  
**Merge**: Successful

### Key Learnings
1. **PerimeterX has multiple implementations**
   - Anthropologie: Press & hold → Keyboard
   - Urban Outfitters: Button click → Gemini Vision

2. **Gemini Vision correctly identifies verification type**
   - Detects "CONTINUE" vs "Press & Hold"
   - Applies appropriate interaction method

3. **Method placement matters**
   - Bug: `_calculate_similarity` was in wrong class
   - Fix: Moved to `PlaywrightMultiScreenshotAgent`

### Product Selectors
```python
product_links = 'a[href*="/product"]'
title = '.product-title'
price = '.product-price'
```

### Key Configuration
```json
{
  "extraction_method": "patchright",
  "anti_bot": "perimeterx_button_click",
  "verification_solution": "gemini_vision_click",
  "wait_strategy": "load",
  "catalog_extraction": "gemini_first"
}
```

### Success Metrics
- ✅ Verification bypass: 100%
- ✅ Products extracted: 74/74
- ✅ Cost per page: $0.003
- ✅ Time: 142s (~2.4 minutes)

---

## REVOLVE

### **Anti-Bot System**: None
**Status**: ✅ **WORKING (Markdown)**  
**Complexity**: Low (no anti-bot)  
**Special Challenge**: URL Instability

### Extraction Method
**Primary**: Markdown (Jina AI → DeepSeek/Gemini)  
**Fallback**: None needed  
**Success Rate**: 98%

### The Critical Issue: URL/Product Code Changes

**Discovery Date**: Nov 1, 2025

**Problem**: Revolve changes product URLs and codes without warning

**Example**:
```
ORIGINAL (Earlier 2025):
URL: .../selfportrait-burgundy-rhinestone-fishnet-midi-dress-in-burgundy/dp/SELF-WD318/
Code: SELF-WD318

CHANGED (Nov 2025):
URL: .../burgundy-rhinestone-fishnet-midi-dress/dp/SELF-WD101/
Code: SELF-WD101

SAME PRODUCT:
Title: "Burgundy Rhinestone Fishnet Midi Dress"
Price: $895
Brand: self-portrait
```

**Impact**:
- 3x false "new product" alerts in initial tests
- 363 "products" detected → Actually 105 unique (71% duplication)
- Primary deduplication (URL/code) fails completely

### The SOLUTION ✅

**Method**: Multi-Level Deduplication with Fuzzy Matching

```python
# Level 1: URL match (normalized - strip query params)
# Level 2: Product code match (extracted from URL)
# Level 3: Fuzzy title + price (CRITICAL for Revolve)
# Level 4: Image URL match (future enhancement)

# Level 3 Example (catches URL changes):
if title_similarity > 0.90 and abs(price_diff) < 1.0:
    # High confidence match despite different URL/code
    match_type = 'title_fuzzy_price'
    confidence = 0.85 + (title_similarity - 0.90) * 0.5
```

**Why Level 3 is Critical**:
- Title stays mostly consistent ("Dress" vs "Dress in Color")
- Price stays identical ($895 = $895)
- 90%+ title similarity + exact price = high confidence match
- Catches URL/code changes that Level 1/2 miss

### Product Code Extraction
**Pattern**: `r'dp/([A-Z]{4}-[A-Z]{2}\d+)'`

```python
# Example URLs:
'https://www.revolve.com/.../dp/AFFM-WD514/' → 'AFFM-WD514'
'https://www.revolve.com/.../dp/SELF-WD101/' → 'SELF-WD101'
```

**Reliability**: 100% extraction accuracy (but code itself changes)

### Catalog Extraction
**Method**: Markdown (infinite scroll site)  
**Limitation**: Only captures initially visible products (~105)  
**Reason**: Markdown can't simulate scrolling

### Key Configuration
```json
{
  "extraction_method": "markdown",
  "pagination_type": "infinite_scroll",
  "items_per_page": 48,
  "catalog_urls": {
    "dresses_modest": "https://www.revolve.com/r/Brands.jsp?sortBy=newest&...",
    "tops_modest": "https://www.revolve.com/tops?sortBy=newest&..."
  },
  "product_code_pattern": "dp/([A-Z]{4}-[A-Z]{2}\\d+)",
  "deduplication_strategy": "fuzzy_title_price",
  "deduplication_threshold": 0.90
}
```

### Success Metrics
- ✅ Markdown extraction: 105 products per page
- ✅ Deduplication: Reduced 363 → 105 (71% caught)
- ✅ Fuzzy matching: 90%+ accuracy
- ✅ Cost: ~$0.002/product (very cheap)

### Recommendations
1. **Always use fuzzy title+price matching** for Revolve
2. **Monitor URL stability** (track changes over time)
3. **Refresh baselines** more frequently (weekly vs monthly)
4. **Don't rely solely on product codes** - they change

---

## ARITZIA

### **Anti-Bot System**: Cloudflare
**Status**: ⚠️ **IN PROGRESS**  
**Complexity**: Very High  
**Test Date**: Nov 7, 2025 (ongoing)

### The Challenge
- Cloudflare verification passes successfully
- Page loads completely (title, header visible)
- **Products don't render** (0 products found)
- API delay after Cloudflare challenge

### Current Strategy

**Approach**: Extended Wait + Scroll Trigger

```python
# 1. Wait for Cloudflare + API (extended)
await asyncio.sleep(15)

# 2. Scroll to trigger lazy loading
await page.evaluate("window.scrollTo(0, 1000)")
await asyncio.sleep(2)
await page.evaluate("window.scrollTo(0, 0)")
await asyncio.sleep(2)

# 3. Wait for product elements (long timeout)
await page.wait_for_selector(
    'a[href*="/product"], a[class*="product"]',
    timeout=30000,
    state='attached'  # Just attached, not visible
)
```

### Why Products Don't Load
**Root Cause**: SPA (Single Page Application) architecture with Cloudflare

**Timeline of Events**:
```
1. Page navigation starts
2. Cloudflare challenge appears
3. Cloudflare verification completes ✅
4. Page HTML loads (skeleton structure) ✅
5. JavaScript makes API call for products (AFTER Cloudflare)
6. API response delayed 5-15 seconds ⏱️
7. Products render dynamically from API data
8. Our code runs at step 4-5, products render at step 7 ❌
```

**Why Standard Waits Fail**:
- `wait_for_load_state('networkidle')` - Fires before API call completes
- `wait_for_load_state('domcontentloaded')` - Fires when HTML loads, not when products render
- `wait_for_selector()` - Times out because products don't exist in DOM yet

**Technical Details**:
- **Library**: Patchright (`patchright.async_api.async_playwright`)
- **Key Limitation**: Some Playwright methods don't exist (e.g., `wait_for_response`, `page.on()`)
- **Product Selectors Tried**: `'a[href*="/product/"]'`, `'a[class*="ProductCard"]'`, `'[class*="ProductCard"]'`
- **URL**: `https://www.aritzia.com/us/en/clothing/dresses?srule=production_ecommerce_aritzia__Aritzia_US__products__en_US__newest`

### Attempted Solutions

**Solution #1: `page.wait_for_response()`** ❌
```python
await page.wait_for_response(
    lambda response: 'products' in response.url and response.status == 200,
    timeout=30000
)
```
- **Error**: `AttributeError: 'Page' object has no attribute 'wait_for_response'`
- **Reason**: Patchright doesn't support this Playwright method
- **Status**: Not available in Patchright API

**Solution #2: Event Listener** ❌
```python
product_api_detected = False

def on_response(response):
    if 'products' in response.url or 'api' in response.url:
        if response.status == 200:
            product_api_detected = True

page.on("response", on_response)
await asyncio.sleep(30)
```
- **Error**: `AttributeError: 'Page' object has no attribute 'on'`
- **Reason**: Patchright's event listener API differs from Playwright
- **Status**: Not available in Patchright API

**Solution #3: Extended Wait + Scroll** ⏳ (Current - Not Working)
- **Implementation**: `patchright_catalog_extractor.py` lines 157-181
- **Strategy**: 15s wait → scroll trigger → 30s `wait_for_selector()` timeout
- **Result**: Still finds 0 products (timeout after 30 seconds)
- **Status**: Testing (not working)

### Key Configuration
```json
{
  "extraction_method": "patchright",
  "anti_bot": "cloudflare",
  "solution_method": "extended_wait_scroll",
  "wait_duration_seconds": 15,
  "scroll_trigger": true,
  "wait_for_selector_timeout": 30000,
  "product_selectors": [
    "a[href*='/product']",
    "a[class*='product']",
    "[data-testid*='product']",
    "[class*='ProductCard']"
  ]
}
```

### Next Steps
1. Test extended wait + scroll approach
2. If fails: Try network traffic inspection
3. If fails: Consider markdown extraction instead
4. Document final solution when found

---

## NORDSTROM

### **Anti-Bot System**: Advanced (Multiple Layers)
**Status**: ❓ **NOT TESTED**  
**Complexity**: Very High  
**Expected Challenges**: IP blocking, browser fingerprinting, rate limiting

### Expected Anti-Bot Features
- **IP Blocking**: May block data center IPs
- **Browser Fingerprinting**: Advanced detection
- **Rate Limiting**: Strict request limits
- **Dynamic Challenges**: May change per session

### Planned Strategy
1. **Test basic navigation first** - See what challenges appear
2. **Patchright stealth mode** - Enhanced anti-detection
3. **Residential proxies** - If IP blocking occurs
4. **Human-like delays** - Variable timing between actions

### Key Configuration (Preliminary)
```json
{
  "extraction_method": "patchright",
  "anti_bot": "very_high",
  "stealth_required": true,
  "rate_limit_strict": true,
  "challenges_expected": [
    "ip_blocking",
    "browser_fingerprinting",
    "rate_limiting"
  ]
}
```

### Note
**Will test LAST** - Most complex retailer  
**Backup plan**: Markdown extraction if Patchright blocked

---

## QUICK REFERENCE MATRIX

| Retailer | Method | Anti-Bot | Solution | Status | Products |
|----------|--------|----------|----------|--------|----------|
| **Anthropologie** | Patchright | PerimeterX (Press & Hold) | Keyboard TAB+SPACE | ✅ Working | 71 |
| **Abercrombie** | Patchright | Medium | Wait for dynamic load | ✅ Working | 90 |
| **Urban Outfitters** | Patchright | PerimeterX (Button) | Gemini click | ✅ Working | 74 |
| **Revolve** | Markdown | None | Fuzzy deduplication | ✅ Working | 105 |
| **Aritzia** | Patchright | Cloudflare | Extended wait+scroll | ⏳ Testing | 0 |
| **Nordstrom** | Patchright | Very High | TBD | ❓ Not tested | ? |

### Extraction Method Summary

**Markdown (Cheap, Fast)**:
- Revolve ✅
- ASOS
- Mango
- H&M
- Uniqlo

**Patchright (Powerful, Handles Anti-Bot)**:
- Anthropologie ✅
- Abercrombie ✅
- Urban Outfitters ✅
- Aritzia ⏳
- Nordstrom ❓

---

## PATTERN LEARNING STATUS

### Auto-Learned Selectors (High Confidence)
- Anthropologie: `a[href*="/shop/"]` (0.95 confidence)
- Abercrombie: `a[data-testid="product-card-link"]` (0.92 confidence)
- Urban Outfitters: `a[href*="/product"]` (0.88 confidence)

### Verification Solutions (Production-Ready)
- PerimeterX Press & Hold: Keyboard TAB+SPACE (100% success)
- PerimeterX Button: Gemini Vision click (100% success)
- Cloudflare: Extended wait+scroll (testing)

### Deduplication Strategies
- Standard: URL + Product code (95% accuracy)
- Revolve: Fuzzy title+price (90% threshold, catches URL changes)

---

**Last Updated**: 2025-11-07  
**Next Update**: After Aritzia/Nordstrom testing complete

**Document Status**: Production-ready strategies documented  
**Success Rate**: 3/5 Patchright retailers working (60%)  
**Overall System**: 8/10 retailers fully functional (80%)

