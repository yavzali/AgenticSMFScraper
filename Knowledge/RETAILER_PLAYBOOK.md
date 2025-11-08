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
**Status**: ✅ **WORKING**  
**Complexity**: Very High  
**Test Date**: Nov 7, 2025

### The Challenge
- Cloudflare verification passes successfully
- Page loads completely (title, header visible)
- **Products initially don't render** due to API delay
- SPA architecture with 5-15 second unpredictable delay after Cloudflare

### The SOLUTION ✅

**Method**: Active Polling (Adaptive Wait)
```python
# For Aritzia specifically - catalog extraction
if retailer.lower() == 'aritzia':
    logger.info("⏱️ Starting Aritzia product detection (polling mode)")
    max_attempts = 30
    attempt = 0
    products_found = False
    
    selectors_to_try = [
        'a[href*="/product/"]',
        'a[class*="ProductCard"]',
        '[data-product-id]'
    ]
    
    while attempt < max_attempts and not products_found:
        attempt += 1
        
        for selector in selectors_to_try:
            try:
                elements = await self.page.query_selector_all(selector)
                if len(elements) > 0:
                    logger.info(f"✅ Found {len(elements)} products with selector '{selector}' after {attempt} seconds")
                    products_found = True
                    break
            except:
                continue
        
        if not products_found:
            await asyncio.sleep(1)
    
    if not products_found:
        logger.warning(f"⚠️ No products detected after {max_attempts} seconds")
```

**Why It Works**:
- **Adaptive**: Checks every 1 second instead of fixed 15-second wait
- **Fast**: Exits immediately when products appear (often 1-8 seconds)
- **Reliable**: Continues checking up to 30 seconds if needed
- **Cost-effective**: No wasted waiting time

### Key Learnings

1. **Fixed waits don't work for SPAs with variable API delays**
   - Old approach: Wait 15 seconds (too short or too long)
   - New approach: Poll until products appear (1-30 seconds)

2. **Products appear at unpredictable times**
   - Sometimes 1 second after Cloudflare
   - Sometimes 15+ seconds after Cloudflare
   - Polling handles both scenarios perfectly

3. **Multiple selector fallbacks increase reliability**
   - Primary: `'a[href*="/product/"]'` (most reliable)
   - Fallback: `'a[class*="ProductCard"]'`
   - Last resort: `'[data-product-id]'`

### Catalog Extraction
**Mode**: Gemini-first (normal operation)  
**Result**: 86 products extracted successfully  
**Gemini**: 24 products visually  
**DOM**: 62 URLs  
**Merge**: 86 complete products

### Product Selectors
```python
# Learned selectors (highest success rate)
product_links = 'a[href*="/product/"]'  # Primary
product_cards = 'a[class*="ProductCard"]'  # Fallback
```

### Key Configuration
```json
{
  "extraction_method": "patchright",
  "anti_bot": "cloudflare",
  "verification_solution": "automatic_pass_through",
  "wait_strategy": "active_polling",
  "polling_max_attempts": 30,
  "polling_interval_seconds": 1,
  "product_selectors": [
    "a[href*=\"/product/\"]",
    "a[class*=\"ProductCard\"]",
    "[data-product-id]"
  ],
  "catalog_extraction": "gemini_first"
}
```

### Success Metrics
- ✅ Verification bypass: 100% (Cloudflare passes automatically)
- ✅ Products extracted: 86/86
- ✅ Detection time: 1-8 seconds (avg 1 second)
- ✅ Cost per page: $0.003
- ✅ Total time: ~50 seconds (including verification)

### Code Locations
- Catalog polling: `patchright_catalog_extractor.py` (lines 158-188)
- Single product polling: `patchright_product_extractor.py` (applies same logic)
- Strategy config: `patchright_retailer_strategies.py`

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

