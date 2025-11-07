# New Product Importer Guide

## Overview
The New Product Importer processes lists of product URLs, extracts full product details, assesses modesty, and uploads approved items to Shopify. It handles manual URL imports and assessment pipeline outputs.

**Purpose**: Import new products discovered manually or via catalog monitoring.

**Key Point**: Includes in-batch deduplication, modesty assessment, and Shopify upload in one workflow.

---

## When to Use
- **Manual Discovery**: Found products manually on retailer websites
- **Assessment Pipeline Output**: Import approved products from modesty reviews
- **Bulk Import**: Adding new retailer catalogs
- **One-Off Additions**: Special requests or seasonal items

---

## How It Works

### Process Flow
1. **Load URL Batch**: Read URLs from JSON batch file
2. **In-Batch Deduplication**: Remove duplicate URLs within batch
3. **Extract Product Data**: Scrape each product page for full details
4. **Modesty Assessment**: 
   - Auto-assess based on visual details (neckline, sleeves)
   - OR send to manual assessment queue
5. **Shopify Upload**: Upload modest/moderately modest products
6. **Database Storage**: Save ALL products to DB (including not-modest)
7. **Download Images**: Fetch product images for Shopify

### Data Extracted
- Full product details (title, brand, price, description)
- Visual modesty attributes (neckline, sleeve length, clothing type)
- Images (up to 5 per product)
- Product code
- Stock availability
- Sale status

---

## Usage

### Command Line
```bash
cd Workflows
python new_product_importer.py --batch path/to/batch.json
```

### Batch File Format
```json
{
  "urls": [
    "https://www.revolve.com/product1/dp/ABC123/",
    "https://www.revolve.com/product2/dp/DEF456/",
    "https://www.anthropologie.com/shop/product3"
  ],
  "modesty_level": "modest",
  "retailer": "revolve"
}
```

**Required Fields**:
- `urls`: Array of product URLs
- `modesty_level`: "modest" or "moderately_modest" (for sorting/organization)
- `retailer`: Retailer name (optional, auto-detected from URLs)

---

## In-Batch Deduplication

### Purpose
Prevents wasting API calls on duplicate URLs within the same batch.

### How It Works
```
Input: 150 URLs
  ↓
Normalize URLs (strip query params)
  ↓
Remove duplicates
  ↓
Output: 142 unique URLs
```

### URL Normalization
- Strips query parameters (`?color=red&size=M`)
- Keeps core URL structure
- Case-insensitive matching

**Example**:
```
Before:
  - https://revolve.com/dress/dp/ABC/?color=red
  - https://revolve.com/dress/dp/ABC/?size=M
  - https://revolve.com/dress/dp/ABC/

After:
  - https://revolve.com/dress/dp/ABC/ (1 unique URL)
```

---

## Modesty Assessment

### Auto-Assessment (Current)
Products are auto-assessed based on extracted visual details:
- **Modest**: Long sleeves + high neckline
- **Moderately Modest**: 3/4 sleeves OR crew neck
- **Not Modest**: Short sleeves, low necklines, etc.

### Manual Assessment (Optional)
If auto-assessment confidence is low:
1. Product sent to `assessment_queue` table
2. Human reviews via `web_assessment` interface
3. Approved products imported separately

---

## Shopify Upload

### What Gets Uploaded
- ✅ Modest products
- ✅ Moderately modest products
- ❌ Not modest products (saved to DB only)

### Shopify Product Data
- Title, brand, price, description
- Product type (Dress, Top, etc.)
- Tags: modesty level, retailer, attributes
- Images (downloaded and uploaded)
- Variants (if applicable)
- Metafields (neckline, sleeves, source URL)

### Product Type Mapping
```python
'dress' → 'Dresses'
'top' → 'Tops'
'bottom' → 'Bottoms'
'outerwear' → 'Outerwear'
```

---

## Output & Results

### Success Response
```json
{
  "success": true,
  "batch_file": "batch_modest_dresses.json",
  "total_urls": 150,
  "processed": 150,
  "successful": 142,
  "failed": 8,
  "uploaded_to_shopify": 128,
  "saved_to_db": 142,
  "processing_time": 1850.2,
  "total_cost": 1.45
}
```

### Individual Results
```json
{
  "url": "https://www.revolve.com/...",
  "success": true,
  "shopify_id": 14818258551154,
  "modesty_assessment": "modest",
  "uploaded_to_shopify": true,
  "processing_time": 12.3
}
```

### Result Breakdown
- `successful`: Extraction succeeded
- `failed`: Extraction failed (network, API, etc.)
- `uploaded_to_shopify`: Modest items uploaded
- `saved_to_db`: All extracted items saved locally

---

## Performance Metrics

### Markdown Retailers (Fast)
- **Speed**: ~10-15s per product
- **Batch of 100**: ~20-25 minutes
- **Cost**: ~$0.01 per product (DeepSeek)
- **Success Rate**: 95-98%

### Patchright Retailers (Slower)
- **Speed**: ~60-70s per product
- **Batch of 100**: ~110-120 minutes
- **Cost**: ~$0.05 per product (Gemini Vision)
- **Success Rate**: 90-95%

### Image Downloads
- **Time**: +2-3s per product (5 images max)
- **Storage**: Local temp directory → Shopify CDN

---

## Error Handling

### Common Errors

**"LLM extraction failed"**
- **Cause**: DeepSeek/Gemini couldn't parse page
- **Fallback**: System tries Gemini → Patchright cascade
- **Solution**: Check API balances, review URL validity

**"Shopify upload failed"**
- **Cause**: Shopify API limit, invalid data, auth issues
- **Product Saved**: Still saved to local DB
- **Solution**: Can retry Shopify upload separately

**"Image download failed"**
- **Cause**: Image URL invalid, network timeout
- **Impact**: Product uploaded without some images
- **Solution**: Can manually add images later in Shopify

**"Duplicate product"**
- **Cause**: Product already exists in Shopify
- **Action**: Skipped (not uploaded again)
- **Note**: Still saved to DB

---

## Best Practices

1. **Batch Size**:
   - **Markdown**: 100-250 products
   - **Patchright**: 20-50 products
   - Keep batches manageable for checkpointing

2. **URL Quality**:
   - Verify URLs are valid before batching
   - Remove obvious duplicates manually
   - Use direct product URLs (not catalog pages)

3. **Modesty Level**:
   - Separate batches by modesty level
   - "modest" vs "moderately_modest"
   - Helps with Shopify organization and collections

4. **Timing**:
   - Run during off-peak hours
   - Stagger large batches
   - Monitor API costs

5. **Cost Management**:
   - Use DeepSeek for Markdown retailers (cheaper)
   - Test with small batch first (10-20 URLs)
   - Check cost in final report

6. **Quality Control**:
   - Spot-check first 10 imports in Shopify
   - Verify modesty assessments are accurate
   - Check images uploaded correctly

---

## Checkpoint System

### Auto-Save
Progress saved every 10 products:
```json
{
  "batch_file": "batch_modest_dresses.json",
  "total_urls": 150,
  "processed_urls": ["url1", "url2", ...],
  "successful_count": 85,
  "failed_count": 3
}
```

### Resume
If interrupted, automatically resumes from checkpoint:
```bash
python new_product_importer.py --batch batch_modest_dresses.json
# Resumes from last checkpoint
```

---

## Creating Batch Files

### Manual Creation
```json
{
  "urls": [
    "https://www.revolve.com/dress1/",
    "https://www.revolve.com/dress2/"
  ],
  "modesty_level": "modest",
  "retailer": "revolve"
}
```

### From Catalog Monitor Output
After assessment pipeline approval:
1. Export approved URLs from `assessment_queue`
2. Create batch file
3. Run importer

### From Spreadsheet
```python
import json
import pandas as pd

df = pd.read_csv('products.csv')
batch = {
    "urls": df['url'].tolist(),
    "modesty_level": "modest",
    "retailer": "revolve"
}

with open('batch_from_spreadsheet.json', 'w') as f:
    json.dump(batch, f, indent=2)
```

---

## Notifications

### Batch Completion
```
New Product Importer - Batch Complete

Batch: batch_modest_dresses.json
Total URLs: 150
Successful: 142 (94.7%)
Failed: 8
Uploaded to Shopify: 128
Saved to Database: 142
Processing Time: 30.8 minutes
Total Cost: $1.45
```

### Per-Product Logging
Check logs for detailed per-product status:
```
[INFO] ✅ Successfully imported: Product Title ($99.99)
[INFO] 📤 Uploaded to Shopify: ID 14818258551154
[WARNING] ⚠️ Failed to extract: https://invalid-url.com/
```

---

## Troubleshooting

### High Failure Rate
1. Check if URLs are valid (test manually in browser)
2. Verify API balances (DeepSeek, Gemini, Jina AI)
3. Check retailer website accessibility
4. Review logs for error patterns

### Products Not in Shopify
1. Check modesty assessment (only modest items uploaded)
2. Verify Shopify credentials configured
3. Check Shopify API rate limits
4. Review notification/logs for upload errors

### Slow Performance
1. Reduce batch size
2. For Patchright: Expect longer times (verification)
3. Check internet speed
4. Run during off-peak hours

### Missing Images
1. Check if image URLs were extracted
2. Verify image URLs are accessible
3. Check Shopify storage limits
4. Can manually add images later in Shopify admin

---

## Database Storage

### Products Table
All products saved to `products` table:
```sql
- url (unique)
- retailer
- title, brand, price
- description
- modesty_status (modest, moderately_modest, not_modest)
- clothing_type
- neckline, sleeve_length
- shopify_id (if uploaded)
- first_seen, last_updated
```

### Benefits
- Historical record of all products
- Can re-upload to Shopify later
- Analytics and reporting
- Deduplication for future imports

---

## Integration with Other Workflows

### After Catalog Monitor
```
1. Catalog Monitor detects new products
   ↓
2. Assessment Pipeline (human review)
   ↓
3. Export approved URLs
   ↓
4. New Product Importer (this workflow)
   ↓
5. Products live in Shopify!
```

### Manual Discovery
```
1. Find products manually on retailer sites
   ↓
2. Create batch file with URLs
   ↓
3. New Product Importer
   ↓
4. Products in Shopify
```

---

## Related Documentation
- `CATALOG_MONITOR_GUIDE.md` - Automated new product detection
- `PRODUCT_UPDATER_GUIDE.md` - Updating existing products
- `CATALOG_BASELINE_SCANNER_GUIDE.md` - Initial setup
- `DUAL_TOWER_MIGRATION_PLAN.md` - System architecture

