# Product Updater Guide

## Overview
The Product Updater refreshes data for products already in your Shopify store. It re-scrapes product pages, extracts current information (price, availability, images), and updates both Shopify and the local database.

**Purpose**: Keep existing product data fresh and accurate.

**Key Point**: Only processes products that have a `shopify_id`. Does NOT import new products.

---

## When to Use
- **Before Catalog Monitoring**: Update existing products first to avoid false positives
- **Periodic Refresh**: Weekly or bi-weekly to catch price/stock changes
- **After Sale Events**: Capture updated prices and sale status
- **Manual Triggers**: When you notice stale data in Shopify

---

## How It Works

### Process Flow
1. **Load Products**: From batch file OR database query
2. **Route to Tower**: Markdown or Patchright based on retailer
3. **Extract Fresh Data**: Re-scrape product page for current info
4. **Image Processing**: 
   - Enhance image URLs (retailer-specific transformations)
   - Download updated images (high-res versions)
5. **Update Shopify**: Push changes to Shopify product (including new images)
6. **Update Local DB**: Save to `products` table with new `last_updated` timestamp
7. **Checkpoint**: Track progress for resumability

### Data Updated
- Price (current and original)
- Sale status
- Stock availability
- **Images** (enhanced, high-quality versions)
- Description
- Sizes/colors/materials
- Product metadata

### What It Doesn't Do
- ❌ Does NOT add new products
- ❌ Does NOT assess modesty (products already approved)
- ❌ Does NOT deduplicate (products already in Shopify)

---

## Usage

### Method 1: Batch File (Manual URLs)
```bash
cd Workflows
python product_updater.py --batch path/to/batch.json
```

**Batch File Format**:
```json
{
  "urls": [
    "https://www.revolve.com/product1/...",
    "https://www.revolve.com/product2/...",
    "https://www.anthropologie.com/product3/..."
  ]
}
```

### Method 2: Database Query (Automated)
Use `generate_update_batches.py` to create batches based on criteria:

```bash
# All products from a retailer
python generate_update_batches.py --retailer revolve --limit 100

# Products by age (oldest first)
python generate_update_batches.py --by-age --days 30 --limit 50

# Products on sale
python generate_update_batches.py --smart --priority on_sale --limit 100

# Low stock items
python generate_update_batches.py --smart --priority low_stock --limit 50
```

Then run the generated batch:
```bash
python product_updater.py --batch output_batches/update_batch_revolve_20251107.json
```

---

## Batch Generation Options

### By Retailer
```bash
python generate_update_batches.py --retailer revolve --limit 100
```
Updates all Revolve products (up to 100).

### By Age
```bash
python generate_update_batches.py --by-age --days 30 --limit 50
```
Updates products not refreshed in 30+ days (oldest first).

### By Status
```bash
python generate_update_batches.py --by-status --sale-status on_sale --limit 100
```
Updates only products currently on sale.

### Smart Batches (Priority-Based)
```bash
python generate_update_batches.py --smart --priority <TYPE> --limit <N>
```

**Priority Types**:
- `on_sale`: Products on sale (check for price drops)
- `low_stock`: Low inventory (check if restocked)
- `stale`: Not updated in 60+ days
- `recent`: Added in last 7 days (verify initial data)

---

## Checkpoint System

### Auto-Save
Progress is saved every 5 products to `checkpoint_<batch_id>.json`:
```json
{
  "batch_id": "update_batch_revolve_20251107",
  "total_urls": 100,
  "processed_urls": ["url1", "url2", ...],
  "successful_count": 45,
  "failed_count": 2,
  "last_checkpoint": "2025-11-07T14:30:00"
}
```

### Resume from Checkpoint
If interrupted, Product Updater automatically resumes from last checkpoint:
```bash
python product_updater.py --batch path/to/batch.json
# Detects existing checkpoint and resumes
```

### Manual Checkpoint Cleanup
```bash
rm Product\ Updater/checkpoint_*.json
```

---

## Output & Results

### Success Response
```json
{
  "success": true,
  "batch_id": "update_batch_revolve_20251107",
  "total_products": 100,
  "processed": 100,
  "updated": 98,
  "failed": 2,
  "not_found": 0,
  "processing_time": 1250.5,
  "total_cost": 0.85
}
```

### Individual Results
Each product update tracked:
```json
{
  "url": "https://www.revolve.com/...",
  "success": true,
  "shopify_id": 14818258551154,
  "method_used": "markdown_extractor",
  "processing_time": 10.5,
  "action": "updated"
}
```

### Actions
- `updated`: Successfully updated in Shopify + DB
- `failed`: Extraction or Shopify update failed
- `not_found`: Product not in DB or missing `shopify_id`

---

## Performance Metrics

### Markdown Retailers
- **Speed**: ~10s per product
- **Batch of 100**: ~15-20 minutes
- **Cost**: ~$0.01 per product (DeepSeek)
- **Success Rate**: 95-98%

### Patchright Retailers
- **Speed**: ~60s per product (includes verification)
- **Batch of 100**: ~100-120 minutes
- **Cost**: ~$0.05 per product (Gemini Vision)
- **Success Rate**: 90-95%

---

## Error Handling

### Common Errors

**"Product not in DB or missing shopify_id"**
- **Cause**: Product never imported OR import failed
- **Solution**: Use New Product Importer instead

**"Extraction failed"**
- **Cause**: Product page changed, API limits, network issues
- **Solution**: Check logs, retry later, verify URL still works

**"Shopify update failed"**
- **Cause**: Shopify API rate limit, invalid data, auth issues
- **Solution**: Check Shopify credentials, retry after delay

**"Both DeepSeek V3 and Gemini Flash 2.0 failed"**
- **Cause**: Markdown unavailable, API balance low
- **Solution**: Top up API balance, check Jina AI accessibility

---

## Best Practices

1. **Run Before Catalog Monitor**: Always update existing products first
   - Prevents false "new product" detections
   - Ensures deduplication has fresh data

2. **Batch Size**:
   - **Markdown**: 100-200 products per batch (fast)
   - **Patchright**: 20-50 products per batch (slow)
   - Smaller batches = easier to resume if interrupted

3. **Frequency**:
   - **High-priority** (sale items): Daily or every 2-3 days
   - **Regular products**: Weekly
   - **Stable products**: Bi-weekly or monthly

4. **Smart Batching**:
   - Prioritize on-sale products (prices change frequently)
   - Update low-stock items (availability changes)
   - Rotate through all products over time

5. **Cost Management**:
   - Use DeepSeek for Markdown retailers (10x cheaper)
   - Batch similar retailers together
   - Monitor API costs in notifications

6. **Timing**:
   - Run during off-peak hours (nights/weekends)
   - Avoid during retailer sale events (higher traffic)
   - Stagger Patchright updates (slower)

---

## Notifications

### Batch Completion
Sent via notification system:
```
Product Updater - Batch Complete

Batch: update_batch_revolve_20251107
Total: 100 products
Updated: 98 (98%)
Failed: 2
Processing Time: 20.8 minutes
Total Cost: $0.85
```

### Email Not Configured?
System still works! Results shown in:
- Terminal output (JSON)
- Log files (`logs/`)
- Checkpoint files

---

## Troubleshooting

### High Failure Rate (>10%)
1. Check API balances (DeepSeek, Gemini, Jina AI)
2. Verify retailer websites accessible
3. Check if retailer changed page structure
4. Review logs for patterns

### Slow Performance
1. Check internet speed
2. For Patchright: Verification challenges taking long?
3. Reduce batch size
4. Run during off-peak hours

### Checkpoint Not Resuming
1. Verify checkpoint file exists in `Product Updater/`
2. Check `batch_id` matches between file and checkpoint
3. Delete old checkpoints if conflicting

### "Not Found" Products
1. Product may have been deleted from Shopify
2. Product URL may have changed (check retailer site)
3. Database sync issue (check `products` table)

---

## Integration with Other Workflows

### Recommended Order
```
1. Product Updater (this workflow)
   ↓ Ensures existing products are fresh
2. Catalog Monitor
   ↓ Detects new products accurately
3. Assessment Pipeline
   ↓ Human review of new products
4. New Product Importer
   ↓ Import approved products
```

### Automation Potential
```bash
# Weekly update script
#!/bin/bash

# Monday: Update existing products
python generate_update_batches.py --by-age --days 7 --limit 200
python product_updater.py --batch output_batches/latest.json

# Tuesday: Monitor for new
python catalog_monitor.py revolve dresses modest
python catalog_monitor.py revolve tops modest

# Wednesday: Review queue + import
# (Manual via web_assessment interface)
```

---

## Related Documentation
- `CATALOG_MONITOR_GUIDE.md` - Detecting new products
- `NEW_PRODUCT_IMPORTER_GUIDE.md` - Importing new products
- `CATALOG_BASELINE_SCANNER_GUIDE.md` - Initial baseline setup
- `DUAL_TOWER_MIGRATION_PLAN.md` - System architecture

