# Failures Tracking

This folder contains records of product imports that failed during workflow execution.

## Purpose

- **Track failed operations** across all workflows for later investigation or retry
- **Provide context** about what workflow, product type, modesty level, and stage was being processed
- **Enable easy retries** by using failure files as input for new batches
- **Pattern analysis** to identify recurring issues with specific retailers or extraction methods

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
| `workflow` | Which workflow generated the failures (see Workflows section below) |
| `retailer` | Retailer name (anthropologie, revolve, etc.) |
| `category` | Product category (dresses, tops, etc.) - used in catalog workflows |
| `product_type` | Type of product (dress, dress_top, etc.) - used in import workflows |
| `modesty_level` | Modesty classification (modest, moderately_modest, etc.) |
| `run_date` | When the batch was executed |
| `total_failed` | Number of failures in this batch |
| `failures` | Array of individual failure records |

**Note**: Not all fields are present in all failure files. Fields vary by workflow type.

## Failure Record Fields

| Field | Description |
|-------|-------------|
| `url` | Product URL that failed |
| `reason` | **Detailed error message** - captures actual exception text, API errors, or specific failure reasons |
| `certainty` | **`known_error`** (we know exactly why it failed) or **`uncertain`** (no clear error details) |
| `stage` | Which stage failed (`extraction`, `shopify_upload`, `image_extraction`, `update`, `database_lookup`) |
| `action` | What action was attempted (`failed`, `skipped_delisted`, etc.) - import workflow only |
| `method_used` | Which extraction method was used - updater workflow only |
| `method_attempted` | Which extraction method was attempted - catalog monitor only |
| `product_type` | Type classification (`new`, `suspected_duplicate`) - catalog monitor only |
| `product_title` | Product title if available |
| `suspected_match` | URL of suspected duplicate match - catalog monitor duplicates only |
| `shopify_status_code` | HTTP status code from Shopify API if available |
| `processing_time` | How long the operation took before failing - updater only |
| `has_price` / `has_title` | Whether basic fields were present - baseline scanner only |
| `attempted_at` | Timestamp of the failure |

**Note**: Not all fields are present in all failure records. Fields vary by workflow and failure stage.

### Understanding `certainty`

- **`known_error`**: The system captured specific error details (e.g., "Gemini API quota exceeded", "Shopify 422: title can't be blank", "Product marked as no longer available")
- **`uncertain`**: The system knows it failed but doesn't have specific error details (e.g., "Unknown error - no error details provided by extractor")

Use `certainty: uncertain` failures as indicators of potential bugs or missing error handling in the extraction layers.

## What Gets Captured in Failure Records

The system now captures **full error context** for all failures:

### Extraction Failures
- **Exact error messages** from Markdown/Patchright extractors
- **Exception text** if extraction throws an error
- **API errors** (e.g., "Gemini analysis failed: 429 You exceeded your current quota")
- **Method used** (markdown, patchright, hybrid)
- **Fallback attempts** (e.g., "Markdown failed, tried Patchright, also failed")

### Shopify Failures
- **HTTP status codes** (422, 500, etc.)
- **Shopify error messages** (e.g., "title can't be blank", "image download failed")
- **Which product fields** were successfully extracted before Shopify upload failed

### Image Failures
- **Why images are missing** (field empty vs field not present)
- **Whether other fields** were successfully extracted (title, price)
- **Catalog-level vs product-level** extraction context

### Uncertain Failures
When `certainty: uncertain`, the failure record includes:
- What was attempted
- Where it failed (stage)
- That no specific error details were available
- This indicates potential bugs in error handling that should be investigated

## Common Failure Reasons

1. **`Shopify API error: 422 - title can't be blank`** (certainty: `known_error`)
   - Product extraction failed to retrieve title
   - Likely "no longer available" product with incomplete data

2. **`Product no longer available at retailer`** (certainty: `known_error`)
   - Product was delisted/discontinued
   - Detected by extraction layer

3. **`Gemini analysis failed: 429 You exceeded your current quota`** (certainty: `known_error`)
   - API quota limit reached
   - Need to wait for quota reset or upgrade plan

4. **`No images extracted from catalog - Images field present but empty`** (certainty: `known_error`)
   - Extractor successfully processed product but found no images at source
   - Product page may not have images loaded

5. **`Unknown error - no error details provided by extractor`** (certainty: `uncertain`)
   - Extraction failed but no specific error was captured
   - Indicates potential bug in error handling
   - Investigate extractor logs for this URL

## Workflows

This system tracks failures across all major workflows:

### 1. **new_product_importer** (`Workflows/new_product_importer.py`)
- **Purpose**: Import new products from URLs into Shopify
- **Batch ID Format**: `{batch_name}_{timestamp}`
- **Typical Failures**:
  - Product extraction failures
  - Shopify API errors (422, 500, etc.)
  - Product no longer available
  - Image download/upload failures
- **Metadata Included**: `workflow`, `retailer`, `product_type`, `modesty_level`, `run_date`
- **Failure Fields**: `url`, `reason`, `action`, `method_used`, `attempted_at`

### 2. **catalog_monitor** (`Workflows/catalog_monitor.py`)
- **Purpose**: Monitor retailer catalogs for new products and duplicates
- **Batch ID Format**: `catalog_monitor_{retailer}_{category}_{modesty_level}_{timestamp}`
- **Typical Failures**:
  - Product extraction failures (new products)
  - Product extraction failures (suspected duplicates)
  - Shopify upload failures for drafts
- **Metadata Included**: `workflow`, `retailer`, `category`, `modesty_level`, `run_date`
- **Failure Fields**: `url`, `reason`, `stage`, `product_type`, `product_title`, `attempted_at`
- **Product Types**: `new` (newly discovered), `suspected_duplicate` (similar to existing)

### 3. **product_updater** (`Workflows/product_updater.py`)
- **Purpose**: Update existing Shopify products with fresh data
- **Batch ID Format**: `{batch_file_name}` or `filter_{timestamp}`
- **Typical Failures**:
  - Product extraction failures (markdown or patchright)
  - Product not found in database
  - Shopify update failures
  - Image processing failures
- **Metadata Included**: `workflow`, `run_date`
- **Failure Fields**: `url`, `reason`, `stage`, `method_used`, `attempted_at`

### 4. **catalog_baseline_scanner** (`Workflows/catalog_baseline_scanner.py`)
- **Purpose**: Establish initial catalog snapshots for change detection
- **Batch ID Format**: `baseline_{retailer}_{category}_{modesty_level}_{timestamp}`
- **Typical Failures**:
  - Products missing images (catalog-level extraction)
  - Image extraction failures
- **Metadata Included**: `workflow`, `retailer`, `category`, `modesty_level`, `run_date`
- **Failure Fields**: `url`, `reason`, `stage`, `product_title`, `attempted_at`

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

