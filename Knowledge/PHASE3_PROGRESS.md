# PHASE 3: PATCHRIGHT TOWER IMPLEMENTATION - PROGRESS TRACKER

**Started**: 2025-11-07  
**Status**: IN PROGRESS (Session 1)

---

## OBJECTIVE

Extract and refactor `Shared/playwright_agent.py` (3,194 lines) into 6 clean, maintainable files within the Patchright Tower.

**Target**: Each file <800 lines (stretch goal <600)

---

## COMPLETED

### Phase 2 Recap (for reference)
- ✅ Markdown Tower: 5 files, 1,657 lines, fully implemented
- ✅ Clean architecture achieved
- ✅ Pattern learner for self-improvement
- ✅ All v1.0 improvements preserved

---

## IN PROGRESS

### 🔄 Analysis (phase3-1)
**File**: `Shared/playwright_agent.py`

**What needs to be analyzed**:
- 3,194 lines total (significantly larger than markdown_extractor.py at 1,144)
- Multiple classes:
  - `PlaywrightMultiScreenshotAgent` - Main extraction class
  - `PlaywrightPerformanceMonitor` - Performance tracking
  - `PageStructureLearner` - Pattern learning (DOM selectors, visual hints)
- Key methods to identify:
  - Verification handling (PerimeterX, Cloudflare)
  - Catalog extraction (DOM + Gemini hybrid)
  - Single product extraction (Gemini→DOM collaboration)
  - Multi-screenshot capture
  - DOM extraction and validation
  - Pattern learning and storage

**Method counting needed**: Will identify all methods and map to new files

---

## PLANNED ARCHITECTURE

### 1. `patchright_verification.py` (<600 lines)
**Purpose**: Handle all anti-bot verification challenges

**Methods to extract**:
- `_handle_verification_challenges()` - Main verification orchestrator
- `_gemini_handle_verification()` - Visual verification detection
- `handle_press_and_hold()` - PerimeterX keyboard solution (Anthropologie/Urban Outfitters)
- Cloudflare handling logic (Aritzia)
- Generic popup dismissal

**Key retailers**:
- Anthropologie: PerimeterX "Press & Hold" (TAB 10x + SPACE 10s)
- Urban Outfitters: PerimeterX
- Aritzia: Cloudflare (extended wait + scroll)

**Dependencies**:
- Gemini Vision for visual detection
- Patchright keyboard/mouse automation
- Pattern learner for verification strategy tracking

---

### 2. `patchright_catalog_extractor.py` (<800 lines)
**Purpose**: Extract multiple products from catalog pages

**Methods to extract**:
- `extract_catalog()` - Main entry point
- Multi-screenshot capture logic
- `_extract_catalog_product_links_from_dom()` - DOM URL extraction
- `_merge_catalog_dom_with_gemini()` - Hybrid DOM + Gemini
- DOM-first mode for tall pages (>20,000px)
- Gemini visual extraction
- Pattern learning integration

**Two extraction modes**:
1. **Gemini-first** (default): Gemini extracts all, DOM validates
2. **DOM-first** (tall pages): DOM extracts URLs, Gemini validates sample

**Key retailers**:
- Anthropologie: DOM-first mode (71 products via DOM, Gemini validates)
- Abercrombie: Gemini-first (explicit `wait_for_selector` for dynamic JS)
- Aritzia: Extended wait + scroll for SPA API loading

---

### 3. `patchright_product_extractor.py` (<700 lines)
**Purpose**: Extract single product data (Gemini→DOM collaboration)

**Methods to extract**:
- `extract_product()` - Main entry point
- Multi-screenshot capture (header, mid, footer)
- `_gemini_analyze_page_structure()` - Visual hints for DOM
- DOM extraction with Gemini guidance
- `_validate_with_dom()` - DOM validation of Gemini data
- Performance tracking

**5-Step Process** (from v1.0):
1. Capture multi-region screenshots
2. Gemini analyzes page structure (provides visual hints)
3. DOM extraction guided by Gemini hints
4. Gemini validates DOM data (cross-check)
5. Pattern learner records what worked

---

### 4. `patchright_dom_validator.py` (<500 lines)
**Purpose**: DOM-based extraction and validation utilities

**Methods to extract**:
- `_extract_from_dom()` - Core DOM extraction
- `_validate_with_dom()` - Validate Gemini data
- `_wait_for_dynamic_content()` - JS wait strategies
- Selector matching logic
- `element.evaluate('el => el.href')` - JS property extraction

**Key patterns**:
- Wait for selectors: `page.wait_for_selector(selector, timeout=10000, state='visible')`
- JS property extraction: Fallback from `get_attribute()` to `evaluate('el => el.href')`
- Dynamic content handling: `domcontentloaded` vs `networkidle`

---

### 5. `patchright_retailer_strategies.py` (<400 lines)
**Purpose**: Retailer-specific strategies and quirks

**What to extract**:
- Verification methods per retailer
- Wait strategies per retailer
- Selector priorities
- Anti-bot complexity levels
- Page structure hints

**Data structure**:
```python
RETAILER_STRATEGIES = {
    'anthropologie': {
        'verification': 'perimeterx_press_hold',
        'wait_strategy': 'domcontentloaded',
        'extended_wait': 4,  # seconds after verification
        'catalog_mode': 'dom_first',  # tall pages
        'popup_selectors': [...],
        'product_selectors': ["a[href*='/shop/']"]
    },
    'aritzia': {
        'verification': 'cloudflare',
        'extended_wait': 15,
        'scroll_trigger': True,
        'catalog_mode': 'gemini_first'
    }
}
```

---

### 6. `patchright_dedup_helper.py` (<300 lines)
**Purpose**: Patchright-specific deduplication (lighter than markdown version)

**Methods**:
- `extract_product_code()` - From URLs (reuse retailer logic)
- `normalize_url()` - Strip query params
- Basic deduplication utilities

**Note**: Most deduplication logic is in `Shared/deduplication_manager.py` (not tower-specific)

---

## KEY CODE SECTIONS TO EXTRACT

### From `Shared/playwright_agent.py`:

**Verification** (lines TBD):
- `_handle_verification_challenges()`
- `_gemini_handle_verification()`
- Keyboard automation for PerimeterX

**Catalog** (lines TBD):
- `extract_catalog()`
- `_extract_catalog_product_links_from_dom()`
- `_merge_catalog_dom_with_gemini()`
- DOM-first conditional logic

**Product** (lines TBD):
- `extract_product()`
- `_gemini_analyze_page_structure()`
- Multi-screenshot capture

**DOM** (lines TBD):
- `_extract_from_dom()`
- `_validate_with_dom()`
- Selector wait logic

**Pattern Learning** (lines TBD):
- `PageStructureLearner` class (may stay separate)
- Performance tracking
- Selector confidence scoring

---

## SHARED DEPENDENCIES

**Required by all Patchright Tower files**:
1. `Shared/logger_config.py` - Logging
2. `Shared/cost_tracker.py` - Cost tracking
3. `Shared/config.json` - System config
4. `Knowledge/RETAILER_CONFIG.json` - Retailer strategies (to be created)
5. `.env` - API keys (GOOGLE_API_KEY for Gemini Vision)

**Python packages needed**:
- `patchright.sync_api` - Stealth browser automation
- `google.generativeai` - Gemini Vision for screenshots
- `PIL` (Pillow) - Image resizing for Gemini WebP limit

---

## ESTIMATED TIME

- **Analysis**: 1-2 hours (file is 2.8x larger than markdown_extractor.py)
- **Verification**: 1.5 hours (most critical, complex logic)
- **Catalog Extractor**: 2 hours (hybrid modes, DOM-first logic)
- **Product Extractor**: 1.5 hours (Gemini→DOM collaboration)
- **DOM Validator**: 1 hour (utility functions)
- **Retailer Strategies**: 0.5 hours (data extraction)
- **Dedup Helper**: 0.5 hours (simple utilities)
- **Testing**: 2 hours (Anthropologie - most complex)
- **Total**: 10-12 hours (vs 4-6 for Markdown Tower due to complexity)

---

## CHALLENGES & RISKS

### 1. **File Size Management**
- `playwright_agent.py` is 3,194 lines (vs 1,144 for markdown)
- Risk: Files exceed 800-line target
- Mitigation: Aggressive refactoring, move pattern learner to separate class

### 2. **Verification Logic Preservation**
- PerimeterX "Press & Hold" breakthrough is critical
- Cloudflare extended wait + scroll is fragile
- Risk: Breaking working verification
- Mitigation: Copy exact code, extensive testing

### 3. **Gemini→DOM Collaboration**
- Complex 5-step process with visual hints
- Risk: Breaking the collaboration between Gemini and DOM
- Mitigation: Keep process intact, test with Anthropologie

### 4. **Pattern Learner Integration**
- `PageStructureLearner` class is 500+ lines
- Risk: Duplication with Markdown pattern learner
- Mitigation: Consider shared base class or keep separate

---

## SESSION NOTES

**Session 1** (Current):
- Created Phase 3 progress tracker
- Analyzed migration plan
- Defined 6-file architecture
- Identified key challenges

**Next Session**:
- Read and analyze `playwright_agent.py`
- Count all methods
- Map methods to new files
- Start with verification (most critical)

---

**Last Updated**: 2025-11-07 (Session 1)  
**Next Update**: After analysis complete

---

## PHASE 3 STATUS: 0% COMPLETE (0/6 files done, analysis in progress)

