# Catalog Baseline Scanner Guide

## Overview
The Catalog Baseline Scanner establishes the initial snapshot of a retailer's catalog. It extracts product data (URLs, titles, prices) from catalog/listing pages and stores them as a baseline for future change detection.

**Purpose**: Create a reference point to identify new products over time.

**Key Point**: Does NOT scrape individual product pages. Only extracts catalog-level data.

---

## When to Use
- **First-time setup**: When adding a new retailer or category
- **Re-baseline**: After major retailer website changes
- **Periodic refresh**: Every 3-6 months to clean up stale baselines

---

## How It Works

### Process Flow
1. **Catalog Extraction**: Scrapes catalog page using appropriate tower (Markdown or Patchright)
2. **In-Memory Deduplication**: Removes duplicate products within the scan
3. **Baseline Storage**: Saves unique products to `catalog_products` table
4. **Metadata Recording**: Stores scan date, product count, and configuration

### Data Extracted
- Product URLs
- Titles
- Prices (current and original if on sale)
- Product codes (extracted from URLs)
- Image URLs
- Sale status

### What It Doesn't Do
- ❌ Does NOT scrape individual product pages for full details
- ❌ Does NOT assess modesty
- ❌ Does NOT upload to Shopify
- ❌ Does NOT check for duplicates against existing products

---

## Usage

### Command Line
```bash
cd Workflows
python catalog_baseline_scanner.py --retailer <RETAILER> --category <CATEGORY> --modesty <LEVEL>
```

### Examples
```bash
# Scan Revolve modest dresses
python catalog_baseline_scanner.py --retailer revolve --category dresses --modesty modest

# Scan Anthropologie tops
python catalog_baseline_scanner.py --retailer anthropologie --category tops --modesty modest
```

### Parameters
- `--retailer`: Retailer name (revolve, anthropologie, asos, etc.)
- `--category`: Product category (dresses, tops)
- `--modesty`: Modesty level (modest, moderately_modest)

---

## Supported Retailers

### Markdown Tower (Fast)
- Revolve
- ASOS
- Mango
- H&M
- Uniqlo
- Aritzia
- Nordstrom

### Patchright Tower (Slower, handles anti-bot)
- Anthropologie (PerimeterX verification)
- Urban Outfitters (PerimeterX verification)
- Abercrombie

---

## Configuration

### Catalog URLs
URLs are configured in `catalog_baseline_scanner.py` (lines 51-91):

```python
CATALOG_URLS = {
    'revolve': {
        'dresses': 'https://www.revolve.com/dresses/br/a8e981/?sortBy=newest&...',
        'tops': 'https://www.revolve.com/tops/br/db773d/?sortBy=newest&...'
    },
    # ... other retailers
}
```

**Important**: URLs MUST be sorted by newest products and filtered for modesty attributes.

---

## Output & Storage

### Database Storage
Products are stored in `catalog_products` table:
- `catalog_url`: Product URL
- `title`: Product name
- `price`: Current price
- `original_price`: Pre-sale price (if applicable)
- `product_code`: Extracted from URL
- `baseline_id`: Links to `catalog_baselines` table
- `discovered_date`: Scan date

### Baseline Metadata
Stored in `catalog_baselines` table:
- `baseline_id`: Unique identifier
- `retailer`, `category`, `modesty_level`
- `total_products`: Count of products found
- `scan_date`: When baseline was created
- `crawl_config`: JSON with catalog URL and settings

### Notifications
System sends notification with:
- Products found
- Baseline ID
- Processing time
- Total cost (API usage)

---

## Typical Results

### Markdown Retailers
- **Speed**: 30-60 seconds
- **Products**: 100-150 per baseline
- **Cost**: ~$0.01 (DeepSeek) or $0.05 (Gemini)

### Patchright Retailers
- **Speed**: 60-120 seconds (includes verification bypass)
- **Products**: 50-100 per baseline
- **Cost**: ~$0.10 (Gemini Vision + DOM)

---

## Troubleshooting

### "No products found"
- Check if catalog URL is correct
- Verify URL is sorted by newest
- Check if retailer website changed structure

### "Extraction failed"
- For Markdown: Check if Jina AI is accessible
- For Patchright: Check if browser can launch
- Check logs for specific error

### "Duplicate baseline exists"
- Delete old baseline first, or
- Use Catalog Monitor to detect changes instead

---

## Best Practices

1. **Run Baseline Once**: Only needed for initial setup or re-baseline
2. **Use Catalog Monitor After**: For ongoing new product detection
3. **Check Retailer Website**: Ensure catalog page hasn't changed
4. **Verify Product Count**: Compare with manual count on website
5. **Run During Off-Peak**: Avoid retailer rate limiting

---

## Next Steps

After establishing baseline:
1. **Wait 24-48 hours** for new products to be added by retailer
2. **Run Product Updater** to refresh existing product data
3. **Run Catalog Monitor** to detect new products since baseline

---

## Related Documentation
- `CATALOG_MONITOR_GUIDE.md` - For ongoing monitoring
- `PRODUCT_UPDATER_GUIDE.md` - For updating existing products
- `DUAL_TOWER_MIGRATION_PLAN.md` - System architecture details

