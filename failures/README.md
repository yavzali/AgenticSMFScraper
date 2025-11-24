# Failures Tracking

This folder contains records of product imports that failed during workflow execution.

## Purpose

- **Track failed product URLs** for later investigation or retry
- **Provide context** about what workflow, product type, and modesty level was being processed
- **Enable easy retries** by using failure files as input for new batches

## File Structure

Each failure file is named: `{batch_id}_failures.json`

### Example: `anthropologie_modest_dresses_failures.json`

```json
{
  "batch_id": "anthropologie_modest_dresses",
  "workflow": "new_product_importer",
  "retailer": "anthropologie",
  "product_type": "dress",
  "modesty_level": "modest",
  "run_date": "2025-11-24T12:00:00",
  "total_failed": 3,
  "failures": [
    {
      "url": "https://www.anthropologie.com/shop/...",
      "reason": "Shopify API error: 422 - title can't be blank",
      "action": "failed",
      "method_used": "patchright_gemini_dom_hybrid",
      "attempted_at": "2025-11-24T11:45:23"
    },
    {
      "url": "https://www.anthropologie.com/shop/...",
      "reason": "Product no longer available at retailer",
      "action": "skipped_delisted",
      "method_used": "patchright_gemini_dom_hybrid",
      "attempted_at": "2025-11-24T11:47:15"
    }
  ]
}
```

## Metadata Fields

| Field | Description |
|-------|-------------|
| `batch_id` | Unique identifier for the batch run |
| `workflow` | Which workflow generated the failures (e.g., `new_product_importer`) |
| `retailer` | Retailer name (anthropologie, revolve, etc.) |
| `product_type` | Type of product (dress, dress_top, etc.) |
| `modesty_level` | Modesty classification (modest, moderately_modest, etc.) |
| `run_date` | When the batch was executed |
| `total_failed` | Number of failures in this batch |
| `failures` | Array of individual failure records |

## Failure Record Fields

| Field | Description |
|-------|-------------|
| `url` | Product URL that failed |
| `reason` | Error message or reason for failure |
| `action` | What action was attempted (`failed`, `skipped_delisted`, etc.) |
| `method_used` | Which extraction method was used |
| `attempted_at` | Timestamp of the failure |

## Common Failure Reasons

1. **`Shopify API error: 422 - title can't be blank`**
   - Product extraction failed to retrieve title
   - Likely "no longer available" product with incomplete data

2. **`Product no longer available at retailer`**
   - Product was delisted/discontinued
   - Detected by extraction layer

3. **`Extraction failed: [error details]`**
   - General extraction failure
   - Could be network, anti-bot, or parsing issues

## How to Use Failure Files

### Option 1: Manual Investigation
Review the failure file to understand patterns:
```bash
cat failures/anthropologie_modest_dresses_failures.json
```

### Option 2: Retry Failed URLs
Create a new batch file from failures:
```python
import json

# Load failures
with open('failures/anthropologie_modest_dresses_failures.json') as f:
    data = json.load(f)

# Extract URLs
failed_urls = [f['url'] for f in data['failures']]

# Create retry batch
retry_batch = {
    "batch_name": f"{data['batch_id']}_retry",
    "retailer": data['retailer'],
    "modesty_level": data['modesty_level'],
    "product_type": data['product_type'],
    "urls": failed_urls
}

# Save as new batch
with open(f"batches/{data['batch_id']}_retry.json", 'w') as f:
    json.dump(retry_batch, f, indent=2)
```

Then run:
```bash
python3 new_product_importer.py batches/{batch_id}_retry.json \
  --modesty-level {modesty_level} \
  --product-type {product_type}
```

## Cleanup

Failure files can be safely deleted once:
- Issues have been investigated
- Retries have been attempted
- Products confirmed as permanently unavailable

Keep failure files for:
- Pattern analysis (recurring extraction issues)
- Retailer-specific problem tracking
- Historical record of import attempts

