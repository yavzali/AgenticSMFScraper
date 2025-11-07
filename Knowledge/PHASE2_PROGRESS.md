# PHASE 2: MARKDOWN TOWER IMPLEMENTATION - PROGRESS TRACKER

**Started**: 2025-11-07  
**Status**: IN PROGRESS (Session 1)

---

## COMPLETED

### ✅ Analysis (phase2-1)
- Read and analyzed `Shared/markdown_extractor.py` (1,144 lines)
- Identified all methods and their responsibilities
- Mapped logic to new tower files

### ✅ Retailer Logic (phase2-4 - Done first)
- **File**: `Extraction/Markdown/markdown_retailer_logic.py`
- **Status**: COMPLETE (198 lines)
- **Contains**:
  - Product code extraction patterns (10 retailers)
  - Price parsing (handles CAD, EUR, USD)
  - Title cleaning
  - Brand validation
  - Size/color parsing

---

## IN PROGRESS

### 🔄 Catalog Extractor (phase2-2)
**File**: `Extraction/Markdown/markdown_catalog_extractor.py`

**What needs to be implemented** (from lines 232-415 of v1.0):
1. `extract_catalog_products()` - Main entry point
   - Fetch markdown (reuse `_fetch_markdown`)
   - Smart chunking (40K char limit, extract product section)
   - LLM cascade (DeepSeek → Gemini)
   - Parse pipe-separated text response
   - Extract product codes from URLs

2. `_fetch_markdown()` - Jina AI fetch with caching
   - From v1.0 lines 417-492
   - Cache management (2-day expiry)
   - Retry logic (3 attempts)

3. `_parse_catalog_text_response()` - Parse LLM output
   - From v1.0 lines 750-829
   - Pipe-separated format: `PRODUCT | URL=... | TITLE=... | PRICE=...`
   - Extract and clean fields

**Dependencies**:
- Needs LLM client setup (DeepSeek + Gemini)
- Needs Jina AI client
- Needs caching logic

---

### 🔄 Product Extractor (phase2-3)
**File**: `Extraction/Markdown/markdown_product_extractor.py`

**What needs to be implemented** (from lines 124-231 of v1.0):
1. `extract_product()` - Main entry point for single products
   - Fetch markdown
   - Extract product section (optional smart chunking)
   - LLM cascade with EARLY VALIDATION (key v1.0 improvement)
   - Parse JSON response
   - Validate completeness

2. `_extract_with_llm_cascade()` - Lines 564-592
   - Try DeepSeek first
   - **Validate immediately** (if incomplete, try Gemini)
   - If still fails, signal Patchright fallback

3. `_extract_with_deepseek()` / `_extract_with_gemini()` - Lines 594-640
   - LLM-specific extraction logic

4. `_validate_product_data()` - Lines 991-1052
   - Check required fields
   - Generate warnings

**Key Improvement from v1.0**:
- Early validation after DeepSeek
- Prevents unnecessary Patchright fallbacks

---

### 🔄 Pattern Learner (phase2-5)
**File**: `Extraction/Markdown/markdown_pattern_learner.py`

**What needs to be implemented** (NEW - not in v1.0):
1. Database schema for markdown patterns
2. `record_extraction_performance()` - Track LLM success rates
3. `get_best_llm_for_retailer()` - Learn which LLM works best
4. `record_chunking_strategy()` - Track chunking patterns
5. `get_extraction_stats()` - Reporting

**Purpose**: Learn over time which LLM (DeepSeek vs Gemini) works best per retailer

---

### 🔄 Dedup Helper (phase2-6)
**File**: `Extraction/Markdown/markdown_dedup_helper.py`

**What needs to be implemented**:
1. `deduplicate_urls()` - In-batch URL deduplication
2. `normalize_url()` - Strip query params, fragments
3. `fuzzy_title_match()` - For Revolve-style dedup (90% threshold)
4. `title_price_match()` - Combined matching

**Reuses**: `MarkdownRetailerLogic.extract_product_code()` for quick code extraction

---

## REMAINING TASKS

### Testing (phase2-7)
- Test catalog extraction with Revolve dresses (baseline scan)
- Test single product extraction with sample Revolve URL
- Verify all methods work end-to-end

### Validation (phase2-8)
- Compare results with v1.0 system
- Ensure no data loss
- Check performance metrics

### Commit (phase2-9)
- Git commit all Markdown Tower files
- Tag: Phase 2 complete
- Push to GitHub

---

## KEY CODE SECTIONS TO EXTRACT

### From `Shared/markdown_extractor.py`:

**Init & Setup** (lines 51-122):
- LLM client initialization (DeepSeek + Gemini)
- Config loading
- Cache setup

**Catalog** (lines 232-415):
- `extract_catalog_products()`
- Smart chunking logic
- LLM cascade for catalog

**Single Product** (lines 124-231):
- `extract_product_data()`
- Product section extraction
- Validation

**Fetch & Cache** (lines 417-492, 1069-1123):
- `_fetch_markdown()` - Jina AI integration
- `_get_markdown_cache()` / `_save_markdown_cache()`
- Cache expiry logic (2 days)

**Parsing** (lines 750-829, 904-990):
- `_parse_catalog_text_response()` - Pipe-separated format
- `_parse_json_response()` - JSON with repair
- `_repair_json()` - Attempt to fix malformed JSON

**Prompts** (lines 641-748):
- `_create_extraction_prompt()` - Build LLM prompts
- `_get_retailer_instructions()` - Retailer-specific guidance
- `_get_image_guidance()` - Image extraction instructions

**Validation** (lines 991-1052):
- `_validate_extracted_data()` - Check completeness

---

## SHARED DEPENDENCIES

**Required by all Markdown Tower files**:
1. `Shared/logger_config.py` - Logging
2. `Shared/cost_tracker.py` - Cost tracking
3. `Shared/config.json` - System config
4. `Knowledge/RETAILER_CONFIG.json` - Retailer strategies
5. `.env` - API keys (DEEPSEEK_API_KEY, GOOGLE_API_KEY, JINA_API_KEY)

**Python packages needed**:
- `openai` - For DeepSeek V3 client
- `langchain_google_genai` - For Gemini Flash 2.0
- `requests` - For Jina AI API

---

## ESTIMATED REMAINING TIME

- **Catalog Extractor**: 1-1.5 hours (most complex)
- **Product Extractor**: 1-1.5 hours (similar to catalog)
- **Pattern Learner**: 0.5-1 hour (new, simpler)
- **Dedup Helper**: 0.5 hour (simple utility)
- **Testing**: 1 hour
- **Total**: 4-6 hours

---

## SESSION NOTES

**Session 1** (Current):
- Completed retailer logic
- Analyzed all v1.0 code
- Token limit approaching, will continue in next session

**Next Session**:
- Implement catalog extractor (highest priority - tested with Revolve)
- Then product extractor
- Then helpers
- Test everything with Revolve

---

**Last Updated**: 2025-11-07 (Session 1)  
**Next Update**: After catalog extractor complete

