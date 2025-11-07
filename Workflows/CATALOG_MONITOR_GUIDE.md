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
1. **Catalog Scan**: Extracts current catalog (same as baseline scanner)
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
6. **Assessment Queue**: Products sent for human review:
   - New products → Modesty assessment
   - Suspected duplicates → Duplication assessment (no re-scrape)
7. **Monitoring Run**: Metadata recorded in `catalog_monitoring_runs` table

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
# Monitor Revolve modest dresses
python catalog_monitor.py revolve dresses modest

# Monitor Anthropologie tops (with page limit for testing)
python catalog_monitor.py revolve dresses modest --max-pages 1
```

### Parameters
- `retailer`: Retailer name (revolve, anthropologie, etc.)
- `category`: Product category (dresses, tops)
- `modesty_level`: modest or moderately_modest
- `--max-pages`: Optional, limit pages for testing (default: all)

---

## Assessment Pipeline Integration

### Modesty Assessment (NEW Products)
Products confidently identified as new are:
1. Re-extracted for full details (description, neckline, sleeves, etc.)
2. Sent to assessment queue with `review_type='modesty'`
3. Human reviews via `web_assessment` interface
4. Approved products → Uploaded to Shopify

### Duplication Assessment (SUSPECTED Duplicates)
Products with fuzzy matches are:
1. **NOT re-extracted** (saves cost)
2. Sent to assessment queue with `review_type='duplication'`
3. Human reviews suspected match
4. If NOT duplicate → Promoted to modesty assessment queue
5. If duplicate → Discarded

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

### Baseline Matches Well (Good)
```
Products Scanned: 125
Confirmed Existing: 120
New Products: 5
Suspected Duplicates: 0
```
**Interpretation**: 5 truly new products, sent for modesty review.

### URL/Code Changes (Revolve Issue)
```
Products Scanned: 125
Confirmed Existing: 100
New Products: 3
Suspected Duplicates: 22
```
**Interpretation**: 22 products flagged due to URL changes. Human review needed.

### First Run After Baseline (Unusual)
```
Products Scanned: 125
Confirmed Existing: 125
New Products: 0
Suspected Duplicates: 0
```
**Interpretation**: No new products yet. Normal if run immediately after baseline.

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

## Related Documentation
- `CATALOG_BASELINE_SCANNER_GUIDE.md` - Initial baseline setup
- `PRODUCT_UPDATER_GUIDE.md` - Updating existing products
- `NEW_PRODUCT_IMPORTER_GUIDE.md` - Manual URL imports
- `DUAL_TOWER_MIGRATION_PLAN.md` - System architecture

