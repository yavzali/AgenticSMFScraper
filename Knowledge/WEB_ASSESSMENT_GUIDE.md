# WEB ASSESSMENT PIPELINE GUIDE

**Created**: 2025-11-07  
**Purpose**: Comprehensive documentation for the manual product assessment workflow  
**Scope**: CATALOG CRAWLER ONLY (not used by Product Updater or New Product Importer)

---

## TABLE OF CONTENTS
1. [Overview](#overview)
2. [When Assessment Pipeline is Used](#when-assessment-pipeline-is-used)
3. [Two Assessment Types](#two-assessment-types)
4. [Workflow Integration](#workflow-integration)
5. [Database Tables](#database-tables)
6. [Web Interface](#web-interface)
7. [Assessment Criteria](#assessment-criteria)
8. [Batch Processing](#batch-processing)

---

## OVERVIEW

### What Is It?
The Web Assessment Pipeline is a manual review system where products identified by the Catalog Crawler are reviewed by a human before being imported into Shopify.

### Why Does It Exist?
- **Modesty Filtering**: Determine if new products meet modesty standards (Modest, Moderately Modest, or Not Modest)
- **Deduplication Validation**: Confirm if suspected duplicates are truly duplicates or genuinely new products

### Key Characteristic
- **CATALOG CRAWLER EXCLUSIVE**: Only used in the Catalog Crawler workflow
- **NOT USED**: Product Updater (updates existing Shopify products directly)
- **NOT USED**: New Product Importer (URLs pre-filtered, imported directly)

---

## WHEN ASSESSMENT PIPELINE IS USED

### Catalog Crawler Workflow 2 (Monitoring for New Products)

**Step-by-Step Flow**:

```
1. Catalog Crawler extracts products from retailer's "newest" page
   ↓
2. Deduplication checks against baseline and Shopify products
   ↓
3. CASE A: Clearly New Product
   │  ↓
   │  Re-extract full details (single product extraction)
   │  ↓
   │  Send to Assessment Pipeline for MODESTY ASSESSMENT
   │  ↓
   │  Human reviews on web interface
   │  ↓
   │  If "Modest" or "Moderately Modest" → Import to Shopify
   │  If "Not Modest" → Store in database, don't import
   │
4. CASE B: Suspected Duplicate (fuzzy title+price match, but not 100% certain)
   │  ↓
   │  Send to Assessment Pipeline for DUPLICATION ASSESSMENT
   │  ↓
   │  Human reviews on web interface
   │  ↓
   │  If "Duplicate" → Mark as duplicate, don't import
   │  If "Not Duplicate" → Treat as new product, proceed to modesty assessment
```

---

## TWO ASSESSMENT TYPES

### Type 1: Modesty Assessment

**Purpose**: Determine if a new product meets modesty standards

**When Triggered**:
- Catalog Crawler identifies a genuinely new product (not in baseline, not in Shopify)
- Product has been fully extracted (re-scraped for complete data)

**Assessment Options**:
1. **Modest** - Fully modest, ready for import
2. **Moderately Modest** - Mostly modest, ready for import
3. **Not Modest** - Does not meet standards, do NOT import

**Database Status Flow**:
```
review_status: 'pending_modesty_review'
   ↓ (human reviews)
review_status: 'approved_for_scraping' (if Modest/Moderately Modest)
review_status: 'rejected_not_modest' (if Not Modest)
   ↓
modesty_level: 'modest' or 'moderately_modest'
clothing_type: determined from product category
```

**Shopify Import**:
- ✅ Approved products are imported to Shopify
- ❌ Rejected products are stored in database but NOT imported

---

### Type 2: Duplication Assessment

**Purpose**: Confirm if a suspected duplicate is truly a duplicate or a new product

**When Triggered**:
- Catalog Crawler finds a product with similar title+price to existing product
- Fuzzy matching confidence is high (>90%) but not 100% certain
- Needs human verification (e.g., different color, different style, same name)

**Assessment Options**:
1. **Duplicate** - Same product, URL/code changed, don't import
2. **Not Duplicate** - Different product, proceed to modesty assessment

**Database Status Flow**:
```
review_status: 'pending_duplication_check'
   ↓ (human reviews)
   ├─→ If DUPLICATE:
   │   review_status: 'duplicate_confirmed'
   │   duplicate_of: <existing_product_id>
   │   Don't import, don't re-assess
   │
   └─→ If NOT DUPLICATE:
       review_status: 'pending_modesty_review'
       Proceed to modesty assessment (see Type 1)
```

**Example: Revolve URL Change**
```
Existing Product:
  URL: .../dp/SELF-WD318/
  Title: "self-portrait Burgundy Rhinestone Fishnet Midi Dress"
  Price: $895

Suspected Duplicate:
  URL: .../dp/SELF-WD101/
  Title: "Burgundy Rhinestone Fishnet Midi Dress"
  Price: $895

Human Review: "Same dress, URL changed" → Mark as DUPLICATE
```

---

## WORKFLOW INTEGRATION

### Catalog Crawler Baseline (Workflow 1)
**Assessment Pipeline**: ❌ NOT USED

**Reason**: Baseline establishment only stores product snapshots for change detection. No import decisions made.

**Database**: Products stored in `catalog_products` table with `review_status = NULL`

---

### Catalog Crawler Monitoring (Workflow 2)
**Assessment Pipeline**: ✅ USED

**Trigger Points**:

1. **New Product Detected**:
   ```python
   # In catalog_crawler_base.py
   if match_result.is_new_product:
       # Re-extract full details
       full_product = await self.extractor.extract_single_product(url)
       
       # Send to assessment pipeline
       await self.db_manager.save_product_for_review(
           full_product,
           review_status='pending_modesty_review'
       )
   ```

2. **Suspected Duplicate Detected**:
   ```python
   # In change_detector.py
   if fuzzy_match_confidence > 0.90 and fuzzy_match_confidence < 0.98:
       # Not 100% certain, needs human check
       await self.db_manager.save_product_for_review(
           product,
           review_status='pending_duplication_check',
           suspected_duplicate_of=existing_product_id
       )
   ```

---

### Product Updater
**Assessment Pipeline**: ❌ NOT USED

**Reason**: Updates existing Shopify products. No modesty assessment or deduplication needed (products already in Shopify).

**Flow**:
```
Batch File (URLs) → Extract Updates → Shopify Manager → Update Shopify
```

---

### New Product Importer
**Assessment Pipeline**: ❌ NOT USED

**Reason**: URLs are pre-filtered and manually curated. User has already determined these are modest products.

**Flow**:
```
Batch File (URLs) → Extract Full Details → Shopify Manager → Import to Shopify
```

---

## DATABASE TABLES

### Primary Table: `catalog_products`

**Relevant Columns**:
```sql
id INTEGER PRIMARY KEY
retailer TEXT
category TEXT
url TEXT
title TEXT
price REAL
product_code TEXT
image_urls TEXT
review_status TEXT  -- Key field for assessment pipeline
modesty_level TEXT
suspected_duplicate_of INTEGER
first_seen TEXT
last_seen TEXT
```

**`review_status` Values**:
- `NULL` - Baseline product (no review needed)
- `'pending_modesty_review'` - Awaiting modesty assessment
- `'pending_duplication_check'` - Awaiting duplication assessment
- `'approved_for_scraping'` - Approved, ready for import
- `'rejected_not_modest'` - Not modest, don't import
- `'duplicate_confirmed'` - Confirmed duplicate, don't import

**Queries**:

```sql
-- Get products pending modesty review
SELECT * FROM catalog_products 
WHERE review_status = 'pending_modesty_review'
ORDER BY first_seen DESC;

-- Get products pending duplication check
SELECT * FROM catalog_products 
WHERE review_status = 'pending_duplication_check'
ORDER BY first_seen DESC;

-- Get approved products ready for import
SELECT * FROM catalog_products 
WHERE review_status = 'approved_for_scraping'
ORDER BY first_seen DESC;
```

---

### Related Table: `products`

**Purpose**: Main product database (includes imported Shopify products)

**When Product Moves from `catalog_products` to `products`**:
```python
# After human approval and Shopify import
if product.review_status == 'approved_for_scraping':
    # Import to Shopify
    shopify_id = await shopify_manager.create_product(product)
    
    # Move to main products table
    await db_manager.move_to_main_products(
        product,
        shopify_id=shopify_id,
        modesty_level=product.modesty_level
    )
```

---

## WEB INTERFACE

### Access
**URL**: (To be provided - hosted assessment interface)

**Authentication**: (To be determined)

---

### Modesty Assessment Interface

**Page Layout**:
```
┌─────────────────────────────────────────────────────────┐
│  Product Review - Modesty Assessment                   │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  [Product Image]    Title: "Dress Name"                 │
│                     Brand: "Brand Name"                 │
│                     Price: $89                          │
│                     Retailer: Revolve                   │
│                     Category: Dresses                   │
│                                                         │
│  [View More Images] [View on Retailer Site]             │
│                                                         │
│  Modesty Assessment:                                    │
│  ○ Modest                                               │
│  ○ Moderately Modest                                    │
│  ○ Not Modest                                           │
│                                                         │
│  [Previous] [Skip] [Submit] [Next]                      │
└─────────────────────────────────────────────────────────┘
```

**Actions**:
- **Submit**: Saves assessment, marks `review_status = 'approved_for_scraping'` or `'rejected_not_modest'`
- **Skip**: Keeps `review_status = 'pending_modesty_review'`, shows next product
- **Previous/Next**: Navigate between pending products

---

### Duplication Assessment Interface

**Page Layout**:
```
┌─────────────────────────────────────────────────────────┐
│  Product Review - Duplication Check                    │
├─────────────────────────────────────────────────────────┤
│  NEW PRODUCT                   EXISTING PRODUCT         │
│  [Image]                       [Image]                  │
│  Title: "Dress Name"           Title: "Dress in Color"  │
│  Price: $89                    Price: $89               │
│  URL: .../dp/ABC-123           URL: .../dp/XYZ-789      │
│                                                         │
│  Similarity: 92%                                        │
│                                                         │
│  Is this the same product?                              │
│  ○ Yes, Duplicate (don't import)                        │
│  ○ No, Different Product (proceed to modesty review)    │
│                                                         │
│  [Previous] [Skip] [Submit] [Next]                      │
└─────────────────────────────────────────────────────────┘
```

**Actions**:
- **Yes, Duplicate**: Marks `review_status = 'duplicate_confirmed'`, sets `duplicate_of = <existing_id>`
- **No, Different Product**: Changes `review_status = 'pending_modesty_review'`, proceeds to modesty assessment
- **Skip**: Keeps `review_status = 'pending_duplication_check'`

---

## ASSESSMENT CRITERIA

### Modesty Standards

**Modest**:
- ✅ Long sleeves (full or 3/4)
- ✅ High neckline (jewel neck, turtleneck, collar, v-neck)
- ✅ Midi or maxi length
- ✅ Not sheer or overly tight
- ✅ Straight or flared cut

**Moderately Modest**:
- ✅ Most modesty features present
- ⚠️ May have one minor compromise (e.g., slightly lower neckline but still covered)
- ✅ Could be layered to be fully modest

**Not Modest**:
- ❌ Short sleeves or sleeveless
- ❌ Low neckline (deep v, scoop, off-shoulder)
- ❌ Short length (mini, short)
- ❌ Sheer, see-through, or overly revealing
- ❌ Cut-outs or backless

---

### Duplication Indicators

**Likely Duplicate**:
- ✅ 90%+ title similarity
- ✅ Exact same price
- ✅ Same brand
- ✅ Similar images (if available)
- ⚠️ Different product code (Revolve changes codes)
- ⚠️ Different URL slug

**Likely Different Product**:
- ❌ Different color variant
- ❌ Different style (e.g., "Midi Dress" vs "Maxi Dress")
- ❌ Different price point
- ❌ Completely different images

**Edge Cases** (Requires Human Judgment):
- Same name, different color ("Dress in Blue" vs "Dress in Red")
- Same style, updated version ("2024 Collection" vs "2025 Collection")
- Same design, different brand collaboration

---

## BATCH PROCESSING

### Generating Assessment Batches

**For Modesty Review**:
```bash
cd "/Users/yav/Agent Modest Scraper System/Catalog Crawler"
python generate_assessment_batch.py --type modesty --retailer revolve --limit 50
```

**Output**: JSON file with products pending modesty review

**Format**:
```json
{
  "batch_id": "modesty_revolve_2025-11-07",
  "batch_type": "modesty_assessment",
  "total_products": 50,
  "products": [
    {
      "id": 123,
      "url": "https://...",
      "title": "Dress Name",
      "price": 89.00,
      "image_url": "https://...",
      "retailer": "revolve",
      "category": "dresses",
      "first_seen": "2025-11-07"
    }
  ]
}
```

---

### Importing Assessment Results

**After human review in web interface**:
```bash
cd "/Users/yav/Agent Modest Scraper System/Catalog Crawler"
python process_assessment_results.py --batch-id modesty_revolve_2025-11-07
```

**Actions**:
1. Read approved products from database (`review_status = 'approved_for_scraping'`)
2. Import to Shopify via Shopify Manager
3. Move to main `products` table
4. Update `review_status` and `shopify_id`

---

## INTEGRATION WITH NEW ARCHITECTURE

### Dual Tower Architecture

**Where Assessment Pipeline Fits**:
```
Catalog Crawler Workflow 2 (Monitoring)
   ↓
Extraction Towers (Markdown or Patchright)
   ↓
Shared Components (Deduplicator)
   ↓
ASSESSMENT PIPELINE ← YOU ARE HERE
   ↓
Shared Components (Shopify Manager)
   ↓
Shopify Store
```

**Tower-Specific Behavior**:
- **Markdown Tower**: Extracts catalog, identifies new products, sends to assessment
- **Patchright Tower**: Extracts catalog, identifies new products, sends to assessment
- **Assessment Pipeline**: Tower-agnostic (doesn't care which tower extracted the product)

---

### Files Involved

**Current Architecture**:
- `Catalog Crawler/catalog_orchestrator.py` - Sends products to assessment
- `Catalog Crawler/change_detector.py` - Identifies duplicates
- `Shared/db_manager.py` - Database operations for assessment status

**New Architecture** (Post-Migration):
- `Workflows/catalog_monitoring_workflow.py` - Orchestrates monitoring
- `Assessment_Pipeline/assessment_manager.py` - Manages review queue
- `Assessment_Pipeline/web_interface/` - Flask/FastAPI web app
- `Shared/db_manager.py` - Database operations (same)

---

## FUTURE ENHANCEMENTS

### Semi-Automated Modesty Assessment
**Idea**: Use Gemini Vision to pre-assess modesty, flag borderline cases for human review

**Flow**:
```
New Product → Gemini Vision Analysis → Confidence Score
   ↓
   ├─→ Confidence > 95% "Modest" → Auto-approve
   ├─→ Confidence > 95% "Not Modest" → Auto-reject
   └─→ Confidence 50-95% → Human review
```

**Benefit**: Reduce human review workload by 60-70%

---

### Duplicate Image Matching
**Idea**: Compare product images to detect duplicates even when title/code/URL all change

**Implementation**: Image similarity hashing (perceptual hash)

**Benefit**: Catch 100% of duplicates, even complete re-listings

---

### Bulk Assessment Actions
**Idea**: Allow bulk approval/rejection for multiple products at once

**Use Case**: 10 dresses from same collection, all clearly modest → Approve all

---

**Last Updated**: 2025-11-07  
**Status**: Production-ready documentation  
**Next Update**: After web interface is developed

