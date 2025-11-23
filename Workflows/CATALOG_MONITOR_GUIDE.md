# Catalog Monitor Guide

## Overview
The Catalog Monitor detects new products by comparing current catalog scans against the established baseline. It identifies truly new items, re-extracts them for full details, and sends them to the assessment pipeline for modesty review.

**Purpose**: Continuously discover new modest apparel as retailers add them.

**Key Point**: Only re-scrapes products confidently identified as NEW. Does NOT re-scrape existing or suspected duplicates.

---

## When to Use
- **After Baseline**: Once baseline is established via Baseline Scanner
- **After Updates**: After running Product Updater on existing items
- **Periodic Checks**: Daily, weekly, or as needed

---

## How It Works

### Process Flow
1. **Catalog Scan**: Extracts current catalog (uses monitoring URLs for Mango)
2. **Field Normalization**: Converts `url` → `catalog_url` for consistency
3. **Multi-Level Deduplication**: Checks 6 strategies against baseline + products DB
   - Exact URL match
   - Normalized URL match
   - Product code match
   - Title + price fuzzy match (85% similarity, 10% price variance)
   - Image URL match
   - Fuzzy title match (fallback)
4. **Classification**: Products are marked as:
   - **New**: Not found in DB (HIGH CONFIDENCE)
   - **Suspected Duplicate**: Fuzzy match found (LOW CONFIDENCE)
   - **Confirmed Existing**: Exact/strong match found
5. **Re-Extraction**: NEW products only are re-scraped for full details
6. **Product Type Determination**: 🆕 Clothing type is set based on retailer:
   - **Normal Retailers**: Category parameter overrides extracted type
     - Example: `category=dresses` → `clothing_type=dress`
   - **Mango Only**: Uses extracted clothing_type (no override)
     - Allows mixed types from "What's New" section
7. **Mango Filtering**: 🆕 If retailer is Mango:
   - **dress/top/dress_top** → Continue to assessment pipeline
   - **bottom/outerwear/other** → Upload to Shopify as DRAFT (not assessed)
8. **🆕 Shopify Draft Upload**: Before sending to assessment:
   - **Images Downloaded**: Process and download images from retailer URLs
   - **Upload to Shopify as DRAFT**: Product created in Shopify with `status='draft'`
   - **Shopify Data Captured**: `shopify_id` and `shopify_image_urls` (CDN URLs) stored
   - **Local DB Updated**: Product saved with `shopify_status='draft'`
   - **Benefit**: Assessment interface displays fast Shopify CDN images instead of retailer URLs
9. **Assessment Queue**: Products sent for human review:
   - New products → Modesty assessment (already on Shopify as draft)
   - Suspected duplicates → Duplication assessment (also uploaded as draft)
10. **Publication on Approval**: 🆕 When human reviewer approves:
    - **Modest/Moderately Modest** → Shopify status changed to `'active'` (published live)
    - **Not Modest** → Remains as `'draft'` in Shopify
    - **Local DB Updated**: `shopify_status` changed to `'published'` or kept as `'draft'`
11. **Monitoring Run**: Metadata recorded in `catalog_monitoring_runs` table

---

## Deduplication Strategies (6 Levels)

### Level 1: Exact URL Match ✅
Fastest, most reliable. Checks `products` and `catalog_products` tables.

### Level 2: Normalized URL Match ✅
Strips query parameters, matches core URL.

### Level 3: Product Code Match ✅
Extracts product ID from URL pattern (e.g., `/dp/ABC123/`).

### Level 4: Title + Price Fuzzy Match ✅
- Title similarity >85%
- Price difference <10%
- **Handles URL/code changes** (e.g., Revolve)

### Level 5: Image URL Match ✅
Matches first product image URL.

### Level 6: Fuzzy Title Match (Fallback) ⚠️
- Title similarity >90%
- Lower confidence, marked as "suspected duplicate"

---

## Product Type Classification 🆕

### Overview
The system now includes intelligent clothing type classification to ensure accurate product categorization in Shopify.

### Normal Retailers (Revolve, ASOS, H&M, Uniqlo, Anthropologie, etc.)

**Category Override Logic**:
- The `category` parameter (dresses, tops) **overrides** the extracted clothing type
- Ensures consistency when monitoring specific categories
- Example: `python catalog_monitor.py revolve dresses modest`
  - All products get `clothing_type = "dress"`
  - Even if extractor detects "tunic" or "maxi dress"

**Why This Works**:
- These retailers have reliable category separation
- Monitoring specific catalog URLs for dresses ensures all products are dresses
- Prevents extraction errors from misclassifying products

### Mango Special Case

**Extraction-Based Logic**:
- Uses the **extracted clothing_type** from single product extraction
- NO category override applied
- Enables monitoring the "What's New" section with mixed product types

**Dual-URL Strategy**:

#### Baseline Scanning
Uses category-specific URLs:
- Dresses: `https://shop.mango.com/us/en/c/women/dresses-and-jumpsuits/dresses_b4864b2e`
- Tops: `https://shop.mango.com/us/en/c/women/tops_227371cd`

#### Monitoring (This Workflow)
Uses "What's New" section:
- **Both categories**: `https://shop.mango.com/us/en/c/women/new-now_56b5c5ed`
- Extracts mixed product types (dresses, tops, bottoms, outerwear, etc.)

**Intelligent Filtering**:

Products are filtered based on extracted clothing_type:

✅ **Assessment Pipeline** (dress/top/dress_top):
- Goes through human modesty review
- Full workflow continues normally

⏭️ **Shopify as Draft** (bottom/outerwear/other):
- Uploaded to Shopify immediately as DRAFT
- Marked as `modesty_status='not_assessed'`
- Saved in database for future reference
- Skips modesty assessment (saves time and cost)

**Why Mango is Different**:
- No "sort by newest" option on category pages
- "What's New" section is the only reliable way to find new products
- More efficient to filter after extraction than to scan multiple categories

### Clothing Type Normalization

The system normalizes 80+ clothing type variants to 6 standard types:

| Extracted Type | Normalized To | Examples |
|---|---|---|
| dress, dresses, gown, maxi dress, midi dress | **dress** | Most common dress variants |
| top, tops, shirt, blouse, tee, sweater | **top** | Standard tops (excluding dress tops) |
| tunic, dress top, long top, oversized top | **dress_top** 🆕 | Long tops that can be worn as dresses |
| pants, jeans, skirt, shorts, trousers | **bottom** | All bottom wear |
| jacket, coat, blazer, outerwear | **outerwear** | Outer layers |
| other, accessory, swimwear, lingerie | **other** | Non-apparel or edge cases |

### Human Verification

In the **web assessment interface**, reviewers see:
- **Extracted Type**: Shows the initial type and source
  - `category_override` (normal retailers)
  - `extraction` (Mango)
- **Dropdown Selection**: 6-option dropdown to verify/correct type
  - Pre-selected to extracted type
  - Required field (cannot submit without selection)
- **Helper Text**: Guidance on when to select "Dress Top"

**Verified Data**:
- Saved to `product_data` with verification metadata
- Includes timestamp and reviewer attribution
- Used for Shopify upload (Product Type and Tags)

---

## Usage

### Prerequisites
1. ✅ Baseline established via Catalog Baseline Scanner
2. ✅ Product Updater run on existing products (ensures DB is current)

### Command Line
```bash
cd Workflows
python catalog_monitor.py <RETAILER> <CATEGORY> <MODESTY_LEVEL> [OPTIONS]
```

### Examples
```bash
# Monitor Revolve modest dresses (category overrides clothing_type)
python catalog_monitor.py revolve dresses modest

# Monitor Anthropologie tops (with page limit for testing)
python catalog_monitor.py anthropologie tops modest --max-pages 1

# Monitor Mango dresses (uses What's New URL, extraction-based clothing_type)
python catalog_monitor.py mango dresses modest

# Monitor Mango tops (also uses What's New URL, filters by clothing_type)
python catalog_monitor.py mango tops modest
```

### Parameters
- `retailer`: Retailer name (revolve, anthropologie, mango, etc.)
- `category`: Product category (dresses, tops)
  - **Normal retailers**: Overrides clothing_type (e.g., `dresses` → all products get `clothing_type=dress`)
  - **Mango**: Used for reporting only; clothing_type comes from extraction
- `modesty_level`: modest or moderately_modest
- `--max-pages`: Optional, limit pages for testing (default: all)

---

## Assessment Pipeline Integration

### Modesty Assessment (NEW Products)
Products confidently identified as new are:
1. Re-extracted for full details (description, neckline, sleeves, etc.)
2. **Clothing type determined** based on retailer logic
3. **Mango filtering applied** (if applicable - only dress/top/dress_top continue)
4. Sent to assessment queue with `review_type='modesty'`
5. Human reviews via `web_assessment` interface:
   - **Modesty assessment**: Select modest/moderately_modest/not_modest
   - **Clothing type verification**: 🆕 Confirm or change type in dropdown
6. Approved products → Uploaded to Shopify with verified type

**Web Interface Changes** 🆕:
- Each product card now shows:
  - Extracted clothing type with source badge
  - Dropdown to verify/change type (6 options)
  - Helper text for "Dress Top" selection
- Submission requires clothing type selection
- Verified type saved with timestamp and reviewer attribution

### Duplication Assessment (SUSPECTED Duplicates)
Products with fuzzy matches are:
1. **NOT re-extracted** (saves cost)
2. Sent to assessment queue with `review_type='duplication'`
3. Human reviews suspected match
4. If NOT duplicate → Promoted to modesty assessment queue
5. If duplicate → Discarded

### Mango Non-Assessed Products
Products filtered out by Mango logic are:
1. Uploaded to Shopify immediately as **DRAFT**
2. Marked with `modesty_status='not_assessed'`
3. Saved in database for tracking
4. Skip assessment pipeline entirely (cost savings)
5. Can be manually reviewed/published in Shopify later

---

## Output & Storage

### Monitoring Run Metadata
Stored in `catalog_monitoring_runs` table:
- `run_id`: Unique identifier
- `retailer`, `category`, `modesty_level`
- `products_scanned`: Total from catalog
- `new_found`: Count of new products
- `duplicates_suspected`: Count for review
- `run_time`: When monitoring occurred

### Assessment Queue
Products added to `assessment_queue` table:
- `queue_id`: Unique identifier
- `product_data`: Full product JSON
- `review_type`: 'modesty' or 'duplication'
- `priority`: 'high', 'normal', or 'low'
- `status`: 'pending', 'reviewed', etc.
- `suspected_match`: If duplication review, shows match details

---

## Typical Results

### Normal Retailers - Baseline Matches Well (Good)
```
Products Scanned: 125
Confirmed Existing: 120
New Products: 5
Suspected Duplicates: 0
```
**Interpretation**: 5 truly new products, sent for modesty review.

### Normal Retailers - URL/Code Changes (Revolve Issue)
```
Products Scanned: 125
Confirmed Existing: 100
New Products: 3
Suspected Duplicates: 22
```
**Interpretation**: 22 products flagged due to URL changes. Human review needed.

### Normal Retailers - First Run After Baseline (Unusual)
```
Products Scanned: 125
Confirmed Existing: 125
New Products: 0
Suspected Duplicates: 0
```
**Interpretation**: No new products yet. Normal if run immediately after baseline.

### Mango - Mixed Product Types 🆕
```
Products Scanned: 48 (from What's New)
Confirmed Existing: 35
New Products: 13

New Product Breakdown:
  - Dresses: 4 (sent to assessment)
  - Tops: 3 (sent to assessment)
  - Dress Tops: 1 (sent to assessment)
  - Bottoms: 3 (uploaded as draft)
  - Outerwear: 2 (uploaded as draft)

Total to Assessment: 8
Total as Draft: 5
```
**Interpretation**: 
- 8 dress/top/dress_top products go through modesty review
- 5 non-relevant products uploaded as drafts (saves assessment time)
- Efficient filtering reduces human workload by 38%

---

## Performance Metrics

### Markdown Retailers (Fast)
- **Catalog Scan**: 30-60s
- **Re-Extraction**: ~10s per new product
- **Total Time**: 2-5 minutes (depends on new product count)
- **Cost**: ~$0.05 + ($0.01 per new product)

### Patchright Retailers (Slower)
- **Catalog Scan**: 60-120s (includes verification)
- **Re-Extraction**: ~60s per new product
- **Total Time**: 5-10 minutes
- **Cost**: ~$0.15 + ($0.05 per new product)

---

## Troubleshooting

### "0 new products but retailer added items"
- **Check**: Did you run Product Updater first?
- **Reason**: Existing products may have changed URLs
- **Solution**: Run Product Updater, then re-run monitor

### "Too many suspected duplicates"
- **Check**: Is this retailer known for URL changes? (e.g., Revolve)
- **Solution**: Review assessment queue, confirm matches
- **Long-term**: Track URL stability with `retailer_url_stability_tracker.py`

### "Re-extraction failing"
- **Check**: DeepSeek balance, Gemini API key
- **Check**: Network connectivity
- **Solution**: Review logs for specific extractor errors

### "All products marked as new"
- **Check**: Was baseline established correctly?
- **Check**: Is baseline_id linking correctly?
- **Solution**: Verify `catalog_products` table has data

---

## Best Practices

1. **Run Product Updater First**: ALWAYS update existing products before monitoring
   - Prevents false positives from URL/price changes
   - Ensures deduplication has fresh data

2. **Monitor Frequency**:
   - **High-volume retailers** (Revolve, ASOS): Daily or every 2-3 days
   - **Low-volume retailers** (Anthropologie): Weekly
   - **Seasonal**: More frequent during fashion weeks

3. **Review Assessment Queue Promptly**:
   - Modesty assessments: Review within 24-48 hours
   - Duplication assessments: Can wait, lower priority

4. **Check for Patterns**:
   - If many suspected duplicates → Retailer may have changed URLs
   - Consider re-establishing baseline

5. **Cost Management**:
   - Use `--max-pages 1` for testing
   - Monitor during off-peak hours
   - Batch process assessment queue

---

## Workflow Integration

### Recommended Schedule
```
Day 1: Establish Baseline (one-time)
Day 2-7: Wait for new products

Weekly Cycle:
  Monday: Product Updater (refresh existing)
  Monday: Catalog Monitor (detect new)
  Tuesday: Review assessment queue (modesty)
  Wednesday: Review suspected duplicates
  Thursday-Sunday: Monitor continues as needed
```

---

## 🔄 Database Synchronization (Two-Way Sync) 🆕

### **What It Does**
After the catalog monitor completes and sends products to the assessment queue, it **automatically syncs** the local database to the web server, ensuring the assessment interface (AssessModesty.com) has the latest products.

### **How Two-Way Sync Works**

**STEP 1: Pull Assessments from Server** (before pushing)
- Downloads server database to temp file
- Finds products you assessed on phone (lifecycle_stage = 'assessed_approved' or 'assessed_rejected')
- Compares assessed_at timestamps
- Merges newer server assessments into local database
- **Prevents data loss** if you assessed products on phone while laptop was offline

**STEP 2: Push Local Changes to Server** (after merging)
- Creates backup of server database
- Uploads merged local database to server
- Sets correct permissions
- Both your phone assessments AND new products are preserved ✅

### **When It Runs**
- **Automatically**: At the end of catalog_monitor.py (if products were added to queue)
- **Manually**: Run `python3 sync_now.py` anytime
- **Status Check**: Run `python3 check_status.py` to see if sync is needed

### **Manual Commands**

**Check Status (Start of Day)**:
```bash
python3 check_status.py
```
Shows pending reviews on server, recent assessments, and sync status.

**Manual Sync**:
```bash
python3 sync_now.py
```
Pulls assessments from server, merges into local, pushes to server.

### **Typical Workflow**
```
Morning:
  1. python3 check_status.py  # See what happened while laptop was off
  2. python3 sync_now.py      # If sync needed (assessed on phone)

During Day:
  3. Run catalog monitor      # Automatically syncs at end

Evening (On Phone):
  4. Assess products          # Changes saved to server
  5. Next time: Step 1-2 pulls your assessments
```

### **Built On**
The two-way sync uses the lifecycle tracking fields from Phase 1-6:
- `lifecycle_stage` - Track product state (pending_assessment, assessed_approved, assessed_rejected)
- `assessed_at` - Assessment timestamp (for comparing local vs server)
- `last_updated` - Track changes

**Without these fields**, two-way sync would be impossible - we'd have to overwrite everything (data loss!).

### **Performance**
- **Overhead**: ~5 seconds per sync
- **Worth it**: YES - prevents data loss when assessing on phone
- **Non-blocking**: Failures don't crash workflows

### **Troubleshooting**
- Check SSH connectivity: `ssh root@167.172.148.145`
- Verify local database: `ls -lh Shared/products.db`
- Check sync logs in catalog monitor output
- Visit https://assessmodesty.com/assess.php to verify

### **Documentation**
- `Knowledge/TWO_WAY_SYNC_WORKFLOW.md` - Complete workflow walkthrough
- `Knowledge/TWO_WAY_SYNC_INTEGRATION.md` - Architecture integration details
- `Knowledge/DATABASE_PATH_CONSOLIDATION.md` - Database path fix

---

## Related Documentation
- `CATALOG_BASELINE_SCANNER_GUIDE.md` - Initial baseline setup
- `PRODUCT_UPDATER_GUIDE.md` - Updating existing products
- `NEW_PRODUCT_IMPORTER_GUIDE.md` - Manual URL imports
- `DUAL_TOWER_MIGRATION_PLAN.md` - System architecture
- `PRODUCT_TYPE_CLASSIFICATION_IMPLEMENTATION.md` 🆕 - Product type classification feature details
- `RETAILER_CONFIG.json` - Retailer-specific configurations including Mango dual-URL setup
- `Knowledge/TWO_WAY_SYNC_WORKFLOW.md` 🆕 - Database synchronization workflow
- `Knowledge/TWO_WAY_SYNC_INTEGRATION.md` 🆕 - Sync architecture integration
- `Knowledge/DATABASE_PATH_CONSOLIDATION.md` 🆕 - Database path consolidation fix

