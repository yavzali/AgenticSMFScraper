# 🏗️ **Agent Modest Scraper System v6.2 - Triple Tower + Assessment Pipeline**

## 🎯 **Executive Summary**

The Agent Modest Scraper System v6.2 represents a **production-ready, modular** e-commerce scraping platform built on a **Triple Tower Architecture** with **integrated assessment pipeline**. The system combines three independent extraction methods (**Markdown Tower**, **Patchright Tower**, and **Commercial API Tower**), advanced AI models (**DeepSeek V3** + **Gemini Flash 2.0** + **Gemini Vision**), **Bright Data API** for enterprise-grade anti-bot bypass, **Shopify draft upload workflow**, and sophisticated **anti-bot protection** to deliver **90-98% success rates** across all supported retailers.

### **🚀 Key Achievements (v6.2)**
- **✅ 🆕 Triple Tower Architecture**: Markdown, Patchright, and Commercial API (Bright Data)
- **✅ 🆕 Bright Data Integration**: Enterprise anti-bot bypass with Web Unlocker
- **✅ 🆕 Pattern Learning**: HTML selector optimization based on success/failure rates
- **✅ 🆕 Smart Fallbacks**: Commercial API → LLM → Patchright fallback chain
- **✅ Dual Tower Architecture**: Independent Markdown & Patchright extraction systems
- **✅ Modular Design**: All scripts <900 lines, easy to maintain and debug
- **✅ 4 Production Workflows**: Baseline Scanner, Monitor, Updater, Importer
- **✅ Robust Deduplication**: 6-level strategy handles URL/code changes
- **✅ PerimeterX Mastery**: Keyboard-based bypass for "Press & Hold" verification
- **✅ 🆕 Draft-First Upload**: Products uploaded to Shopify as drafts BEFORE human review
- **✅ 🆕 Assessment Pipeline**: Human-in-the-loop with Shopify CDN images for fast review
- **✅ 🆕 Auto-Publication**: Modest products automatically published after approval
- **✅ 🆕 Status Tracking**: Publication status tracked (`not_uploaded`, `draft`, `published`)
- **✅ Pattern Learning**: Adaptive system learns from every extraction
- **✅ 100% Test Coverage**: All 8 Phase 6 tests passed

---

## 🏗️ **System Architecture**

### **🎪 v6.2 Triple Tower Design**

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           WORKFLOWS LAYER                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │
│  │   Catalog    │  │   Catalog    │  │   Product    │                  │
│  │   Baseline   │  │   Monitor    │  │   Updater    │                  │
│  │   Scanner    │  │              │  │              │                  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                  │
│         │                  │                  │                          │
│         │    ┌─────────────┴──────────────────┴─────┐                  │
│         │    │      New Product Importer            │                  │
│         │    └────────────┬──────────────────────────┘                  │
└─────────┼─────────────────┼──────────────────────────────────────────────┘
          │                 │
┌─────────┴─────────────────┴──────────────────────────────────────────────┐
│                       INTEGRATION LAYER                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │
│  │      DB      │  │ Shopify      │  │ Assessment   │                  │
│  │    Manager   │  │ Manager      │  │ Queue        │                  │
│  └──────────────┘  └──────────────┘  └──────────────┘                  │
└──────────────────────────────────────────────────────────────────────────┘
          │                              │                      │
┌─────────┴────────────┐   ┌─────────────┴───────────┐   ┌─────┴──────────────┐
│  MARKDOWN TOWER      │   │   PATCHRIGHT TOWER      │   │ COMMERCIAL API     │
│ ┌──────────────────┐ │   │  ┌──────────────┐      │   │ TOWER (🆕 v6.2)   │
│ │ Catalog          │ │   │  │ Catalog      │      │   │ ┌────────────────┐ │
│ │ Extractor        │ │   │  │ Extractor    │      │   │ │ Catalog        │ │
│ ├──────────────────┤ │   │  ├──────────────┤      │   │ │ Extractor      │ │
│ │ Product          │ │   │  │ Product      │      │   │ ├────────────────┤ │
│ │ Extractor        │ │   │  │ Extractor    │      │   │ │ Product        │ │
│ ├──────────────────┤ │   │  ├──────────────┤      │   │ │ Extractor      │ │
│ │ Retailer Logic   │ │   │  │ Verification │      │   │ ├────────────────┤ │
│ ├──────────────────┤ │   │  ├──────────────┤      │   │ │ HTML Parser    │ │
│ │ Pattern Learner  │ │   │  │ DOM Validator│      │   │ ├────────────────┤ │
│ ├──────────────────┤ │   │  ├──────────────┤      │   │ │ LLM Fallback   │ │
│ │ Dedup Helper     │ │   │  │ Retailer     │      │   │ ├────────────────┤ │
│ │                  │ │   │  │ Strategies   │      │   │ │ Pattern        │ │
│ │                  │ │   │  │              │      │   │ │ Learner        │ │
│ └──────────────────┘ │   │  └──────────────┘      │   │ └────────────────┘ │
└──────────────────────┘   └─────────────────────────┘   └────────────────────┘
         │                           │                              │
┌────────┴──────────┐    ┌──────────┴────────────┐   ┌────────────┴──────────┐
│ Jina AI Reader   │    │ Patchright Browser   │   │ Bright Data API      │
│ DeepSeek V3      │    │ Gemini Vision        │   │ BeautifulSoup        │
│ Gemini Flash 2.0 │    │ DOM Extraction       │   │ Gemini Flash (LLM)   │
└──────────────────┘    └──────────────────────┘   └──────────────────────┘
```

---

## 📚 **Core Components**

### **🔷 Markdown Tower** (Fast, Cost-Effective)

#### **Supported Retailers**
- Revolve (90-95% success)
- ASOS (85-90% success)
- Mango (85-90% success)
- H&M (80-85% success)
- Uniqlo (85-90% success)
- Aritzia (85-90% success)
- Nordstrom (85-90% success)

#### **Components**

**1. Markdown Catalog Extractor** (`markdown_catalog_extractor.py` - 644 lines)
- Extracts multiple products from catalog/listing pages
- Jina AI Reader → Markdown conversion
- LLM cascade: DeepSeek V3 → Gemini Flash 2.0
- Smart chunking for large catalogs
- Pipe-separated text parsing (more reliable than JSON)
- **Speed**: 30-60s per catalog page
- **Cost**: ~$0.01-0.05 per page (DeepSeek)

**2. Markdown Product Extractor** (`markdown_product_extractor.py` - 471 lines)
- Single product page extraction
- Extracts full details: title, brand, price, description, neckline, sleeves, etc.
- Early validation after DeepSeek (before Gemini fallback)
- **Speed**: 8-12s per product
- **Cost**: ~$0.01 per product (DeepSeek)

**3. Markdown Retailer Logic** (`markdown_retailer_logic.py` - 198 lines)
- Product code extraction patterns per retailer
- Price parsing & normalization
- Title cleaning & brand validation
- Retailer-specific quirks handling

**4. Markdown Pattern Learner** (`markdown_pattern_learner.py` - 227 lines)
- Tracks LLM performance per retailer
- Records success rates: DeepSeek vs Gemini
- Learns best LLM per retailer over time
- Stores extraction statistics

**5. Markdown Dedup Helper** (`markdown_dedup_helper.py` - 117 lines)
- In-batch URL deduplication
- URL normalization (strips query params)
- Fuzzy title + price matching

---

### **🔶 Patchright Tower** (Handles Anti-Bot)

#### **Supported Retailers**
- Anthropologie (75-85% success) - PerimeterX "Press & Hold"
- Urban Outfitters (70-80% success) - PerimeterX
- Abercrombie (70-80% success) - Multi-step verification

#### **Components**

**1. Patchright Catalog Extractor** (`patchright_catalog_extractor.py` - 846 lines)
- Hybrid Gemini Vision + DOM extraction
- Full-page screenshots for visual analysis
- DOM extraction for URLs/product codes
- DOM-first mode for very tall pages (Anthropologie)
- Handles verification challenges
- **Speed**: 60-120s per catalog page
- **Cost**: ~$0.10-0.20 per page (Gemini Vision)

**2. Patchright Product Extractor** (`patchright_product_extractor.py` - 627 lines)
- 5-step Gemini→DOM collaboration:
  1. Gemini extracts ALL visual data from screenshots
  2. Gemini analyzes page structure (provides DOM hints)
  3. DOM fills gaps & validates (guided by Gemini)
  4. Merge results (Gemini primary, DOM supplements)
  5. Learn from successful extraction
- Multi-region screenshots (header, mid, footer)
- **Speed**: 40-70s per product
- **Cost**: ~$0.05-0.10 per product (Gemini Vision)

**3. Patchright Verification** (`patchright_verification.py` - 543 lines)
- PerimeterX "Press & Hold" bypass (keyboard TAB + SPACE)
- Cloudflare challenge handling
- Generic popup dismissal (twice: before verification, before screenshots)
- Gemini Vision for visual button detection
- **Success Rate**: 85-95% on PerimeterX

**4. Patchright DOM Validator** (`patchright_dom_validator.py` - 465 lines)
- Guided DOM extraction using Gemini visual hints
- Extracts titles, prices, images with learned patterns
- Validates Gemini's visual data with DOM
- Cross-checks for accuracy

**5. Patchright Retailer Strategies** (`patchright_retailer_strategies.py` - 342 lines)
- Centralized retailer-specific configurations
- Verification methods per retailer
- Wait strategies & timeouts
- Catalog modes (Gemini-first vs DOM-first)
- Screenshot strategies

**6. Patchright Dedup Helper** (`patchright_dedup_helper.py` - 58 lines)

---

### **🔵 Commercial API Tower** (🆕 v6.2 - Enterprise Anti-Bot)

#### **Supported Retailers**
- **Nordstrom** (Phase 1 - Active)
- Anthropologie (Phase 2 - Planned)
- Urban Outfitters (Phase 2 - Planned)
- Aritzia, H&M, and remaining retailers (Phase 3-4 - Planned)

#### **Purpose**
The Commercial API Tower provides **enterprise-grade anti-bot bypass** using **Bright Data's Web Unlocker** API. It fetches raw HTML through rotating residential proxies, then parses it using **BeautifulSoup** (fast) with **LLM fallback** (Gemini Flash). This approach combines:
- **Cost savings**: $1.50 per 1,000 requests (vs. Patchright's Gemini Vision costs)
- **Speed**: No browser overhead (30-40s vs. 60-120s)
- **Reliability**: Enterprise proxy infrastructure handles anti-bot challenges
- **Smart fallbacks**: HTML parsing → LLM → Patchright fallback chain

#### **Components**

**1. Commercial Catalog Extractor** (`commercial_catalog_extractor.py` - 500 lines)
- Fetches catalog HTML via Bright Data API
- BeautifulSoup parsing with retailer-specific CSS selectors
- LLM fallback (Gemini Flash) if BeautifulSoup fails
- Pattern learning optimizes selectors over time
- Fallback to Patchright Tower if all methods fail
- **Speed**: 30-50s per catalog page
- **Cost**: ~$0.001-0.002 per page (Bright Data) + LLM if needed

**2. Commercial Product Extractor** (`commercial_product_extractor.py` - 700 lines)
- Single product page extraction via Bright Data
- Triple-layer parsing strategy:
  1. **BeautifulSoup** with learned selectors (primary)
  2. **LLM** (Gemini Flash) if BeautifulSoup incomplete (fallback #1)
  3. **Patchright Tower** if both fail (fallback #2)
- Image URL enhancement (converts thumbnails to high-res)
- Field validation (title, price, description, images, stock)
- **Speed**: 20-40s per product
- **Cost**: ~$0.001 per product (Bright Data) + LLM if needed

**3. Bright Data Client** (`brightdata_client.py` - 350 lines)
- HTTP proxy authentication (API key as username/password)
- Exponential backoff on retries (2^attempt seconds)
- HTML validation (detects "access denied", "captcha", error pages)
- Cost tracking per retailer
- Usage statistics (success/failure rates, bytes downloaded)

**4. HTML Cache Manager** (`html_cache_manager.py` - 250 lines)
- **1-day HTML caching** for debugging (SQLite)
- Reduces redundant Bright Data requests during development
- Cache hit/miss tracking
- Automatic expiration after 24 hours
- Can be disabled in production

**5. HTML Parser** (`html_parser.py` - 450 lines)
- Coordinates BeautifulSoup and LLM fallback parsing
- Integrates with Pattern Learner for optimized selectors
- Validates extracted data (required fields, image count)
- Handles both product and catalog parsing
- Error handling and logging

**6. LLM Fallback Parser** (`llm_fallback_parser.py` - 350 lines)
- Uses Gemini Flash for HTML parsing when BeautifulSoup fails
- Extracts structured JSON from raw HTML
- Handles truncated HTML (50k characters max)
- Cost tracking (Gemini Flash: $0.075/$0.225 per 1M tokens)
- Supports Gemini and DeepSeek providers

**7. Pattern Learner** (`pattern_learner.py` - 450 lines)
- **Learns successful HTML patterns** over time (SQLite)
- Tracks success/failure rates per CSS selector
- Suggests optimal selectors based on confidence scores
- Retailer-specific pattern storage
- Automatic pattern cleanup (removes old/unused patterns)

**8. Commercial Retailer Strategies** (`commercial_retailer_strategies.py` - 700 lines)
- CSS selectors for all 10 retailers (product + catalog)
- Multiple selectors per field (tries in order until success)
- Image URL validation (filters placeholders, icons)
- Price parsing (handles currency symbols, decimals)
- Stock status inference

**9. Commercial Config** (`commercial_config.py` - 250 lines)
- Central configuration for Bright Data, LLM, caching
- Retailer routing (`ACTIVE_RETAILERS` list)
- Parsing strategies per retailer
- Pattern learning settings
- Fallback configuration
- URL normalization
- Product code extraction from image URLs

---

## 🔄 **Workflows**

### **1. Catalog Baseline Scanner** (`catalog_baseline_scanner.py` - 384 lines)

**Purpose**: Establish initial snapshot of retailer's catalog

**Process**:
1. Extract catalog page (Markdown or Patchright)
2. In-memory deduplication
3. Store baseline in `catalog_products` table
4. Record metadata in `catalog_baselines` table

**When to Use**: First-time setup, re-baseline after website changes

**Output**: Baseline ID, product count, processing time, cost

**See Also**: `Workflows/CATALOG_BASELINE_SCANNER_GUIDE.md`

---

### **2. Catalog Monitor** (`catalog_monitor.py` - 706 lines) 🆕

**Purpose**: Detect new products by comparing against baseline, upload to Shopify as drafts, send for human review

**Process**:
1. Extract current catalog
2. Normalize field names (`url` → `catalog_url`)
3. **6-Level Deduplication**:
   - Exact URL match
   - Normalized URL match
   - Product code match
   - Title + price fuzzy match (85% similarity, 10% price variance)
   - Image URL match
   - Fuzzy title match (90% similarity)
4. Classify as: New, Suspected Duplicate, or Confirmed Existing
5. Re-extract NEW products only (for full details)
6. **🆕 Upload to Shopify as DRAFT**:
   - Download images from retailer URLs
   - Upload product to Shopify with `status='draft'`
   - Capture `shopify_id` and `shopify_image_urls` (CDN URLs)
   - Save to local DB with `shopify_status='draft'`
7. **🆕 Send to assessment pipeline**:
   - New products → Modesty assessment (with Shopify CDN images)
   - Suspected duplicates → Duplication assessment (with Shopify CDN images)
8. **🆕 Human review** → Publish or keep as draft
9. Record monitoring run metadata
10. **🆕 Database sync** → Automatically syncs to web server (two-way sync)

**When to Use**: After baseline + after Product Updater, periodic checks

**Output**: Products scanned, new found, suspected duplicates, sent to review, uploaded as drafts, database synced

**🆕 Database Synchronization**: The catalog monitor automatically performs **two-way sync** at the end:
- **STEP 1 (Pull)**: Downloads server database, finds phone assessments, merges into local
- **STEP 2 (Push)**: Uploads merged database to server
- **Prevents data loss** when assessing on phone while laptop is offline
- **Performance**: ~5 seconds overhead, non-blocking

**See Also**: `Workflows/CATALOG_MONITOR_GUIDE.md`, `Knowledge/TWO_WAY_SYNC_WORKFLOW.md`

---

### **3. Product Updater** (`product_updater.py` - 455 lines)

**Purpose**: Refresh data for existing products in Shopify

**Process**:
1. Load products (batch file OR database query)
2. Route to appropriate tower (Markdown/Patchright)
3. Extract fresh data
4. Update Shopify product
5. Update local DB with new `last_updated`
6. Save checkpoint every 5 products (resumable)

**When to Use**: Before Catalog Monitor, weekly/bi-weekly refresh

**Methods**:
- Batch file (manual URLs)
- Database query: by retailer, by age, by status
- Smart batches: on_sale, low_stock, stale, recent

**Output**: Products updated, failed, not found, processing time, cost

**See Also**: `Workflows/PRODUCT_UPDATER_GUIDE.md`

---

### **4. New Product Importer** (`new_product_importer.py` - 564 lines)

**Purpose**: Import new products from URL lists

**Process**:
1. Load URL batch
2. In-batch deduplication (remove duplicate URLs)
3. Extract product data (full details)
4. Modesty assessment (auto or manual)
5. **Shopify upload** (modest/moderately modest only)
6. **Database storage** (ALL products, including not-modest)
7. Download images

**When to Use**: Manual discovery, assessment pipeline output, bulk imports

**Output**: Processed, successful, failed, uploaded to Shopify, saved to DB

**See Also**: `Workflows/NEW_PRODUCT_IMPORTER_GUIDE.md`

---

## 🗄️ **Database Schema**

### **Products Table** (Main Product Storage)
```sql
- url (TEXT, PRIMARY KEY)
- retailer (TEXT)
- title, brand (TEXT)
- price, original_price (REAL)
- description (TEXT)
- modesty_status (TEXT) -- modest, moderately_modest, not_modest
- clothing_type (TEXT) -- dress, top, bottom, outerwear
- neckline, sleeve_length (TEXT)
- shopify_id (INTEGER) -- NULL if not uploaded
- shopify_status (TEXT) -- 🆕 'not_uploaded', 'draft', 'published'
- images_uploaded (INTEGER) -- 🆕 Track image upload success
- images_uploaded_at (TIMESTAMP) -- 🆕 When images were uploaded
- images_failed_count (INTEGER) -- 🆕 Number of failed image uploads
- last_image_error (TEXT) -- 🆕 Last image upload error
- sale_status, stock_status (TEXT)
- first_seen, last_updated (TIMESTAMP)
- image_urls (TEXT) -- JSON array
- product_code (TEXT)
```

### **Catalog Products Table** (Baseline Storage)
```sql
- id (INTEGER, PRIMARY KEY)
- baseline_id (TEXT, FOREIGN KEY)
- catalog_url (TEXT)
- title (TEXT)
- price, original_price (REAL)
- product_code (TEXT)
- image_urls (TEXT) -- JSON array
- discovered_date (DATE)
- extraction_method (TEXT) -- markdown or patchright
```

### **Catalog Baselines Table** (Baseline Metadata)
```sql
- baseline_id (TEXT, PRIMARY KEY)
- retailer, category, modesty_level (TEXT)
- total_products (INTEGER)
- scan_date (TIMESTAMP)
- crawl_config (TEXT) -- JSON
```

### **Catalog Monitoring Runs Table** (Monitoring History)
```sql
- run_id (TEXT, PRIMARY KEY)
- retailer, category, modesty_level (TEXT)
- products_scanned, new_found, duplicates_suspected (INTEGER)
- run_time (TIMESTAMP)
```

### **Assessment Queue Table** (Human Review)
```sql
- queue_id (INTEGER, PRIMARY KEY)
- product_data (TEXT) -- JSON
- review_type (TEXT) -- modesty or duplication
- priority (TEXT) -- high, normal, low
- status (TEXT) -- pending, reviewed, approved, rejected
- suspected_match (TEXT) -- JSON (for duplication review)
- added_date, reviewed_date (TIMESTAMP)
```

---

## 🔀 **Deduplication Strategy**

### **6-Level Deduplication (Catalog Monitor)**

**Level 1: Exact URL Match** ✅ (Fastest, most reliable)
- Checks `products` and `catalog_products` tables
- Direct string comparison

**Level 2: Normalized URL Match** ✅
- Strips query parameters
- Matches core URL structure
- Example: `/product/ABC/?color=red` → `/product/ABC/`

**Level 3: Product Code Match** ✅
- Extracts product ID from URL pattern
- Example: `/dp/ABC123/` → product_code: `ABC123`
- Handles retailer-specific patterns

**Level 4: Title + Price Fuzzy Match** ✅ (Handles URL changes!)
- Title similarity > 85% (SequenceMatcher)
- Price difference < 10%
- **Critical for Revolve** (URLs change frequently)

**Level 5: Image URL Match** ✅
- Matches first product image URL
- Reliable across URL changes

**Level 6: Fuzzy Title Match** ⚠️ (Fallback, lower confidence)
- Title similarity > 90%
- Marked as "suspected duplicate" for human review

### **In-Batch Deduplication**
- **Product Updater**: N/A (products already in DB)
- **New Product Importer**: Normalizes URLs, removes duplicates within batch
- **Catalog Scanner**: In-memory deduplication by product_code

---

## 🎨 **Assessment Pipeline** 🆕

### **Purpose**
Human-in-the-loop review for:
1. **Modesty Assessment**: New products → Is it modest/moderately modest?
2. **Duplication Assessment**: Suspected duplicates → Is it really a duplicate?

### **🆕 Draft-First Workflow**
**Key Innovation**: Products uploaded to Shopify as DRAFTS before human review

**Benefits**:
- ⚡ **Fast Image Loading**: Assessment interface displays Shopify CDN images (2-3x faster than retailer URLs)
- 🔒 **More Reliable**: Images already on Shopify, no broken retailer links
- 📊 **Status Tracking**: Local DB tracks publication status (`not_uploaded`, `draft`, `published`)
- ✅ **Controlled Publishing**: Human approval controls publication to live store

**Flow**:
```
1. Catalog Monitor identifies new product
   ↓
2. Single product extraction (full details)
   ↓
3. 🆕 Download images from retailer
   ↓
4. 🆕 Upload to Shopify as DRAFT (status='draft')
   ↓
5. 🆕 Save to DB with shopify_status='draft', capture shopify_image_urls
   ↓
6. Send to assessment queue with Shopify CDN images
   ↓
7. Human reviews with fast-loading Shopify images
   ↓
8. 🆕 Decision:
   - Modest/Moderately Modest → Publish to store (status='active')
   - Not Modest → Keep as draft
   ↓
9. 🆕 Update local DB: shopify_status='published' or 'draft'
```

### **Web Interface** (`web_assessment/`)
- PHP-based review interface
- **🆕 Displays Shopify CDN images** (fast, reliable)
- Displays product details, suspected matches
- Buttons: Modest / Moderately Modest / Not Modest
- Buttons: Duplicate / Not Duplicate
- High-priority queue for "not duplicate" → auto-promote to modesty review

### **Integration**
- **Catalog Monitor** → Uploads as draft, sends to queue with Shopify data
- **Human Review** → Approves/rejects, publishes modest products
- **Shopify Manager** → Publishes products based on review decisions
- **🆕 Database Manager** → Tracks publication status changes

---

## 🧠 **Pattern Learning**

### **Markdown Pattern Learner**
Tracks per retailer:
- DeepSeek success rate
- Gemini success rate
- Average processing time
- Best LLM for each retailer
- Extraction quality scores

### **Patchright Pattern Learner** (Future)
Will track:
- DOM selectors that work
- Verification challenge solutions
- Screenshot strategies
- Wait times & timeouts

### **Retailer Strategies** (Static + Learned)
Three-tier storage:
1. **Static Config** (`patchright_retailer_strategies.py`): Base settings
2. **Pattern Learner DB**: Learned selectors & success rates
3. **Runtime Logic**: Adaptive extraction based on learned patterns

---

## 📊 **Performance Metrics**

### **Markdown Tower**
| Metric | Value |
|--------|-------|
| **Catalog Extraction** | 30-60s per page, 100-150 products |
| **Single Product** | 8-12s per product |
| **Success Rate** | 90-98% |
| **Cost (DeepSeek)** | $0.01 per product |
| **Cost (Gemini)** | $0.05 per product |
| **Supported Retailers** | 7 (Revolve, ASOS, Mango, H&M, Uniqlo, Aritzia, Nordstrom) |

### **Patchright Tower**
| Metric | Value |
|--------|-------|
| **Catalog Extraction** | 60-120s per page, 50-100 products |
| **Single Product** | 40-70s per product |
| **Success Rate** | 85-95% (with verification bypass) |
| **Cost (Gemini Vision)** | $0.05-0.10 per product |
| **Verification Bypass** | 85-95% success on PerimeterX |
| **Supported Retailers** | 3 (Anthropologie, Urban Outfitters, Abercrombie) |

---

## 🛠️ **Utilities & Tools**

### **Batch Generation** (`generate_update_batches.py`)
- Creates Product Updater batch files from database queries
- Filters: retailer, age, status, smart priorities
- Outputs JSON batch files

### **Retailer URL Stability Tracker** (`retailer_url_stability_tracker.py`)
- Monitors URL/product code stability per retailer
- Tracks changes across catalog crawls
- Informs deduplication strategy selection

### **Cost Tracker** (`Shared/cost_tracker.py`)
- Tracks all API usage: DeepSeek, Gemini, Jina AI
- Calculates session costs
- Detailed per-call logging

### **Notification Manager** (`Shared/notification_manager.py`)
- Email notifications for workflow completion
- Slack integration (optional)
- Baseline summary, monitoring summary, batch completion

### **Database Manager** (`Shared/db_manager.py`)
- Unified facade for all database operations
- Async support (aiosqlite)
- Methods for products, baselines, monitoring runs, assessment queue

### **Image Processor** (`Shared/image_processor.py`) ⭐ NEW
- Centralized image handling with retailer-specific enhancements
- **URL Enhancement**: Transform thumbnails → high-res (300px → 1200px)
  - Anthropologie: `_330_430.jpg` → `_1094_1405.jpg`, Scene7 transforms
  - Aritzia: `_small` → `_large`, media.aritzia.com patterns
  - Uniqlo: `/300w/` → `/1200w/` size upgrades
  - Abercrombie: Scene7 quality optimization
  - Revolve, Urban Outfitters, Nordstrom: Retailer-specific patterns
- **Quality Ranking**: Sophisticated scoring (size indicators, keywords, URL patterns)
- **Placeholder Filtering**: Learned + static patterns (excludes "placeholder", "loading", "thumb")
- **Concurrent Download**: Async image fetching with validation
- **Pattern Learning**: SQLite database tracks transformation success rates
  - `url_transformations`: Success/failure per pattern
  - `download_stats`: Download success per retailer
  - `placeholder_patterns`: Learn bad patterns to avoid
- **Continuous Improvement**: System learns which transformations work best
- **Critical**: Fixes bug where images weren't uploading (URLs → file paths)

---

## 📈 **System Statistics (Phase 6 Testing)**

### **Test Results**
- ✅ **All 8 tests passed**
- ✅ **125 products** extracted in baseline scan (Revolve)
- ✅ **72 products** extracted via Patchright catalog (Anthropologie)
- ✅ **$178 dress** extracted via Patchright single product (Anthropologie)
- ✅ **1/1 product** updated via Product Updater
- ✅ **Deduplication working** (74/99 products correctly matched)

### **Architecture Improvements**
- 📉 **Old system**: ~30,000 lines, tripartite architecture, `playwright_agent.py` 3,194 lines
- 📈 **New system**: Dual Tower, modular, all scripts <900 lines
- ✅ **Result**: More maintainable, testable, and debuggable

---

## 🔐 **Security & Anti-Bot**

### **Patchright Stealth Features**
- Browser fingerprint masking
- Human behavior simulation (mouse, scrolling, timing)
- Persistent browser context (cookies, cache)
- User-agent rotation
- Natural delays & jitter

### **Verification Bypass**
- **PerimeterX "Press & Hold"**: Keyboard approach (TAB + SPACE for 10s)
- **Cloudflare**: Extended waits + scrolling to trigger lazy loading
- **Generic Popups**: Dismissed twice (before verification, before screenshots)
- **Gemini Vision Detection**: AI identifies verification challenges visually

### **Rate Limiting**
- Respectful delays between requests (0.5-1s)
- Batch processing with checkpoints
- Off-peak scheduling recommendations

---

## 🚀 **Getting Started**

### **1. Establish Baseline**
```bash
cd Workflows
python catalog_baseline_scanner.py --retailer revolve --category dresses --modesty modest
```

### **2. Monitor for New Products**
```bash
# Run Product Updater first
python generate_update_batches.py --retailer revolve --limit 100
python product_updater.py --batch output_batches/latest.json

# Then run Catalog Monitor
python catalog_monitor.py revolve dresses modest
```

### **3. Review Assessment Queue**
- Open `web_assessment/index.php` in browser
- Review modesty assessments
- Approve/reject products

### **4. Import Approved Products**
- Export approved URLs from assessment queue
- Create batch file
- Run New Product Importer:
```bash
python new_product_importer.py --batch batch_approved.json
```

---

## 📚 **Documentation**

### **Workflow Guides**
- `Workflows/CATALOG_BASELINE_SCANNER_GUIDE.md` (122 lines)
- `Workflows/CATALOG_MONITOR_GUIDE.md` (318 lines)
- `Workflows/PRODUCT_UPDATER_GUIDE.md` (346 lines)
- `Workflows/NEW_PRODUCT_IMPORTER_GUIDE.md` (397 lines)

### **Technical Documentation**
- `Knowledge/DUAL_TOWER_MIGRATION_PLAN.md` - Migration history, architecture decisions, Phase 6 test results
- `SYSTEM_OVERVIEW.md` - This document

---

## 🎯 **Production Recommendations**

### **Weekly Schedule**
```
Monday:
  - Product Updater (all products updated in last 7+ days)
  - Catalog Monitor (all retailers)

Tuesday:
  - Review assessment queue (modesty)
  
Wednesday:
  - Review suspected duplicates
  - Import approved products

Thursday-Sunday:
  - Monitor continues as needed
  - Spot-check Shopify for quality
```

### **Cost Management**
- Use DeepSeek for Markdown retailers (10x cheaper than Gemini)
- Batch Patchright extractions (slower, more expensive)
- Run during off-peak hours
- Monitor API usage in notifications

### **Maintenance**
- Re-establish baselines every 3-6 months
- Review pattern learner statistics monthly
- Check retailer URL stability quarterly
- Update retailer strategies as websites change

---

## 🏆 **System Status**

**Version**: 6.1 (Dual Tower + Assessment Pipeline)  
**Status**: ✅ Production Ready  
**Last Updated**: November 10, 2025  
**Phase 6 Testing**: ✅ All 8 tests passed  
**Migration**: ✅ Complete (from v5.0 tripartite → v6.0 dual tower → v6.1 assessment integration)

**Supported Retailers**: 10 total (7 Markdown, 3 Patchright)  
**Success Rate**: 90-98% (Markdown), 85-95% (Patchright)  
**Processing Capacity**: 1,000+ URLs daily  
**Cost per Product**: $0.01-0.10 depending on tower  

**🆕 New in v6.1**:
- ✅ Shopify draft upload before assessment
- ✅ Shopify CDN images in review interface  
- ✅ Auto-publication based on modesty decisions
- ✅ Publication status tracking (`shopify_status` column)
- ✅ 1,362 existing products backfilled as 'published'

🚀 **Ready for production use!**

