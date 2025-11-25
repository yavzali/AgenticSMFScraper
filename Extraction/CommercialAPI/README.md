# Commercial API Extraction Tower (Third Tower)

**Status**: ✅ Phase 2 Complete - Full extraction tower operational  
**Active Retailers**: Nordstrom (Phase 1), expanding to all 10 retailers  
**Date**: November 25, 2025

---

## 🎯 Purpose

Third extraction tower using **Bright Data API** for anti-bot bypass, enabling scraping of retailers with advanced anti-bot protection (Perim

eterX, Cloudflare, etc.).

### Why This Tower?

1. **Patchright Tower** - Headless browser, works great but vulnerable to advanced anti-bot (Anthropologie, Nordstrom failing)
2. **Markdown Tower** - API-based markdown extraction, fast but limited HTML structure
3. **Commercial API Tower** (NEW) - Bright Data proxy for anti-bot bypass, BeautifulSoup parsing, LLM fallback

---

## 📂 Architecture

```
Extraction/CommercialAPI/
├── __init__.py                          ✅ Package initialization
├── commercial_config.py                 ✅ Configuration (250 lines)
├── brightdata_client.py                 ✅ Bright Data API wrapper (350 lines)
├── html_cache_manager.py                ✅ 1-day HTML caching (250 lines)
├── commercial_retailer_strategies.py    ✅ CSS selectors per retailer (700 lines)
├── html_parser.py                       ✅ BeautifulSoup coordinator (450 lines)
├── llm_fallback_parser.py               ✅ LLM parsing fallback (350 lines)
├── pattern_learner.py                   ✅ Pattern learning (450 lines)
├── commercial_catalog_extractor.py      ✅ Catalog extraction (500 lines)
├── commercial_product_extractor.py      ✅ Product extraction (700 lines)
└── README.md                            ✅ This file
```

**Total Lines**: ~4,000 lines (all files under 800-line limit ✅)

---

## ✅ Phase 1: Foundation (COMPLETE - Nov 25, 2025)

### Implemented Files

1. **`commercial_config.py`** - Central configuration
   - Bright Data credentials and endpoint
   - Retailer routing (which retailers use this tower)
   - HTML caching config (1-day for debugging)
   - Parsing strategy (BeautifulSoup first, LLM fallback)
   - Pattern learning settings
   - Error handling and fallback to Patchright

2. **`brightdata_client.py`** - Bright Data HTTP client
   - Fetch HTML via proxy with API key auth
   - Automatic retry with exponential backoff
   - Request logging and cost tracking ($1.50 per 1,000 requests)
   - Error detection (CAPTCHA, blocked pages)
   - Session management

3. **`html_cache_manager.py`** - HTML caching for debugging
   - SQLite-based 1-day cache
   - Automatic expiration
   - Cache statistics (hit rate, most accessed URLs)
   - Saves costs during development

4. **`commercial_retailer_strategies.py`** - CSS selectors
   - Product page selectors (title, price, description, images, stock)
   - Catalog page selectors (product links, titles, prices)
   - Multi-selector fallback (try selectors in order)
   - Image URL validation (filter placeholders)
   - All 10 retailers covered: Nordstrom, Anthropologie, Revolve, Aritzia, H&M, Abercrombie, Urban Outfitters, Mango, Uniqlo, ASOS

---

## ✅ Phase 2: Extractors (COMPLETE - Nov 25, 2025)

### Implemented Files

1. **`html_parser.py`** (~450 lines) ✅
   - BeautifulSoup coordinator
   - Try CSS selectors from strategies
   - Record pattern successes/failures
   - Fall back to LLM if parsing fails

2. **`llm_fallback_parser.py`** (~350 lines) ✅
   - LLM-based HTML parsing when selectors fail
   - Gemini Flash (fast & cheap)
   - Structured JSON output for product/catalog data
   - Cost tracking per LLM call

3. **`pattern_learner.py`** (~450 lines) ✅
   - Learn which CSS selectors work best
   - Track success/failure rates per retailer
   - SQLite database for pattern storage
   - Auto-cleanup of old attempts
   - Identify failing patterns for optimization

4. **`commercial_catalog_extractor.py`** (~500 lines) ✅
   - Fetch catalog HTML (Bright Data)
   - Parse with BeautifulSoup + CSS selectors
   - LLM fallback if parsing fails
   - Patchright fallback if LLM fails
   - Return list of product URLs

5. **`commercial_product_extractor.py`** (~700 lines) ✅
   - Fetch product HTML (Bright Data)
   - Parse with BeautifulSoup + CSS selectors
   - LLM fallback if parsing fails
   - Patchright fallback if LLM fails
   - Image enhancement (Anthropologie, Revolve, Aritzia patterns)
   - Batch extraction support
   - Return full product data

---

## 🔧 Configuration

### Environment Variables (.env)

Add to your `.env` file:

```bash
# Bright Data API Configuration
BRIGHTDATA_API_KEY=your_api_key_here

# Existing keys (unchanged)
GEMINI_API_KEY=your_gemini_key
DEEPSEEK_API_KEY=your_deepseek_key
```

### Retailer Routing

Edit `commercial_config.py` to activate retailers:

```python
# Start with Nordstrom only (Phase 1)
ACTIVE_RETAILERS = [
    'nordstrom',
]

# Expand gradually (Phase 2-4)
ACTIVE_RETAILERS = [
    'nordstrom',
    'anthropologie',  # Add when ready
    'urban_outfitters',  # Add when ready
    # ... etc
]
```

---

## 💰 Cost Tracking

### Bright Data Pricing

- **Cost**: $1.50 per 1,000 requests
- **Per Request**: $0.0015
- **Example**: 100 products = 100 requests = $0.15

### Cost Optimization

1. **HTML Caching** - 1-day cache for debugging (avoid repeated requests)
2. **Pattern Learning** - CSS selectors get faster over time (fewer LLM fallbacks)
3. **Fallback to Patchright** - If Bright Data fails, use free Patchright tower

---

## 🧪 Testing

### Manual Test (Product Extraction)

```python
import asyncio
from Extraction.CommercialAPI import CommercialProductExtractor

async def test():
    extractor = CommercialProductExtractor()
    await extractor.initialize()
    
    # Test Nordstrom product
    result = await extractor.extract_product(
        url="https://www.nordstrom.com/s/some-product",
        retailer="nordstrom"
    )
    
    print(f"Success: {result.success}")
    print(f"Method: {result.method_used}")
    print(f"Product: {result.product_data.get('title')}")
    print(f"Cost: ${result.brightdata_cost + result.llm_cost:.4f}")
    
    await extractor.cleanup()

asyncio.run(test())
```

### Manual Test (Catalog Extraction)

```python
import asyncio
from Extraction.CommercialAPI import CommercialCatalogExtractor

async def test():
    extractor = CommercialCatalogExtractor()
    await extractor.initialize()
    
    # Test Nordstrom catalog
    result = await extractor.extract_catalog(
        url="https://www.nordstrom.com/browse/women/clothing/dresses",
        retailer="nordstrom",
        category="dresses"
    )
    
    print(f"Success: {result.success}")
    print(f"Products: {len(result.products)}")
    print(f"Method: {result.method_used}")
    print(f"Cost: ${result.brightdata_cost + result.llm_cost:.4f}")
    
    await extractor.cleanup()

asyncio.run(test())
```

---

## 📊 Logging

All operations logged to `commercial_api.log` with:
- Bright Data requests (URL, cost, size)
- HTML cache hits/misses
- CSS selector successes/failures
- Pattern learning updates
- LLM fallback usage

---

## 🔄 Integration with Workflows

### Automatic Routing (once complete)

Workflows will automatically route to Commercial API tower for configured retailers:

```python
# In catalog_monitor.py, product_updater.py, new_product_importer.py
if CommercialAPIConfig.should_use_commercial_api(retailer):
    # Use Commercial API tower
    extractor = CommercialCatalogExtractor()
else:
    # Use Patchright or Markdown tower
    extractor = PatchrightCatalogExtractor()
```

---

## ⚠️ Known Limitations

1. **No workflow integration yet** - Manual testing only (Phase 3)
2. **CSS selectors need real-world testing** - May require adjustments per retailer
3. **Bright Data API key required** - Must be configured in .env
4. **Pattern learning needs data** - Improves over time with usage

---

## 📚 Related Documentation

- `Extraction/Patchright/patchright_retailer_strategies.py` - Patchright selectors (reference for Commercial API)
- `Shared/image_processor.py` - Image URL enhancement (Anthropologie, Revolve, Aritzia patterns)
- `Knowledge/PRODUCT_UPDATER_FAILURE_ANALYSIS.md` - Lessons learned on image extraction
- `Knowledge/SYSTEM_WIDE_PROPAGATION_CHECKLIST.md` - Best practices

---

## 🚀 Roadmap

### Phase 1: Foundation ✅ (COMPLETE - Nov 25, 2025)
- [x] Configuration module
- [x] Bright Data client
- [x] HTML cache manager
- [x] Retailer strategies (CSS selectors)
- [x] Package structure

### Phase 2: Extractors ✅ (COMPLETE - Nov 25, 2025)
- [x] HTML parser with BeautifulSoup
- [x] LLM fallback parser
- [x] Pattern learning
- [x] Catalog extractor
- [x] Product extractor
- [x] Image enhancement integration

### Phase 3: Integration (NEXT)
- [ ] Workflow routing logic in catalog_monitor.py
- [ ] Workflow routing logic in product_updater.py
- [ ] Workflow routing logic in new_product_importer.py
- [ ] Test with Nordstrom (real extraction)
- [ ] Verify cost tracking accuracy
- [ ] Pattern learning validation with real data

### Phase 4: Expansion
- [ ] Activate Anthropologie, Urban Outfitters (PerimeterX bypass)
- [ ] Activate Aritzia, H&M (Cloudflare bypass)
- [ ] Gradual migration of all retailers
- [ ] CSS selector optimization based on pattern learning

---

## 🤝 Contributing

When adding new retailers or updating selectors:

1. **Test selectors manually** - Use browser DevTools to verify CSS selectors
2. **Add multiple fallbacks** - Always provide 2-3 selector options per field
3. **Document patterns** - Add comments for complex selectors
4. **Update both extractors** - Keep catalog and product selectors in sync

---

**Phase 1 & 2 Complete** ✅  
**Next**: Integrate with workflows (catalog_monitor, product_updater, new_product_importer)

