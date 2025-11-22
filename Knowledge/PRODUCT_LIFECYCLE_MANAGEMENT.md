# Product Lifecycle Management

## Overview

This document defines the complete product lifecycle from detection to publication, establishing clear rules for when products should enter the assessment pipeline.

**Date Created**: Nov 22, 2025  
**Related**: `catalog_monitor.py`, `catalog_baseline_scanner.py`, `assessment_queue_manager.py`

---

## Product Lifecycle Stages

### 1. **Baseline Discovery** (`catalog_products.review_status = 'baseline'`)
- **Source**: Initial catalog baseline scan
- **Purpose**: Establish snapshot for change detection
- **Data**: Lightweight (URL, title, price only)
- **Action**: **NEVER send to assessment queue** - these are reference data

### 2. **New Product Detection** (`catalog_products.review_status = NULL → 'pending'`)
- **Source**: Catalog monitor detects product NOT in baseline
- **Trigger**: Deduplication returns `'confirmed_new'` status
- **Data**: Still lightweight at this stage
- **Action**: Proceed to full extraction

### 3. **Full Extraction** (In-memory, not yet in DB)
- **Source**: Catalog monitor re-extracts with single product extractor
- **Data**: Complete (description, neckline, sleeves, etc.)
- **Action**: Upload to Shopify as draft

### 4. **Draft Upload** (`products` table, `shopify_status = 'draft'`)
- **Source**: Shopify API after draft creation
- **Fields**: `shopify_id`, `shopify_variant_id`, `shopify_image_urls`
- **Data**: Full + Shopify metadata
- **Action**: Send to assessment queue

### 5. **Pending Assessment** (`assessment_queue.status = 'pending'`)
- **Source**: Catalog monitor or new product importer
- **Review Types**: 'modesty' or 'duplication'
- **Wait**: Human review required
- **Action**: Display in web interface

### 6A. **Approved** (`products.modesty_status = 'modest'`)
- **Source**: Human reviewer approval
- **Action**: Publish to Shopify, update `shopify_status = 'published'`
- **Final State**: Live product in store

### 6B. **Rejected** (`products.modesty_status = 'not_modest'`)
- **Source**: Human reviewer rejection
- **Action**: Keep as draft, update `shopify_status = 'rejected'`
- **Final State**: Tracked for analytics, not published

### 7. **Baseline Update** (`catalog_products` updated on next baseline scan)
- **Source**: Next baseline scan includes approved product
- **Action**: Deduplication recognizes as existing, skips

---

## Database Schema Additions

### products table

```sql
ALTER TABLE products ADD COLUMN lifecycle_stage TEXT;
```

**Values**:
- `'baseline_only'` - In catalog_products, never extracted
- `'pending_extraction'` - Flagged as new, needs full extraction (NOT USED - extraction happens immediately)
- `'pending_assessment'` - Extracted, in assessment_queue
- `'assessed_rejected'` - Assessed as not modest
- `'assessed_approved'` - Assessed as modest, published
- `'imported_direct'` - Imported via new_product_importer (bypassed catalog monitor)

```sql
ALTER TABLE products ADD COLUMN data_completeness TEXT;
```

**Values**:
- `'lightweight'` - Only catalog data (URL, title, price)
- `'full'` - Complete extraction (description, neckline, sleeves)
- `'enriched'` - Full + Shopify data

### catalog_products table

**Current values** (clarified):
- `NULL` or `'baseline'` - Baseline snapshot, no action needed
- `'pending'` or `'pending_modesty_review'` - Detected as new, needs extraction
- `'pending_duplication_check'` - Suspected duplicate, needs review
- `'confirmed_duplicate'` - Human confirmed duplicate
- `'promoted_to_extraction'` - Moved to extraction workflow (NOT USED - happens immediately)
- `'migrated_to_new_system'` - Migrated from old system

**Recommendation**: Standardize to clearer values:
- `'baseline'` (instead of NULL)
- `'flagged_new'` (instead of 'pending')
- `'flagged_duplicate'` (instead of 'pending_duplication_check')
- `'confirmed_duplicate'` (keep)
- `'confirmed_existing'` (when re-scanned in later baseline)

---

## Workflow Decision Trees

### Catalog Monitor Flow

```
Product detected in catalog
│
├─ Is it in products table?
│  └─ YES → Skip (confirmed_existing) ✅
│
├─ Is it in catalog_products baseline?
│  ├─ YES with review_status='baseline' → Skip (baseline product, not new) ✅
│  ├─ YES with review_status='flagged_new' → Continue to extraction
│  └─ NO → Mark as CONFIRMED_NEW
│
├─ Deduplication (multi-level matching)
│  ├─ Confidence >= 95% → confirmed_existing ✅
│  ├─ Confidence 85-94% → suspected_duplicate → Duplication Review ⚠️
│  └─ Confidence < 85% → confirmed_new
│
├─ Full extraction (single product)
│  └─ Retailer-specific filtering (e.g., Mango dress/top only)
│
├─ Upload to Shopify as draft
│  ├─ Success → Get shopify_id, shopify_image_urls
│  └─ Failure → Log error, skip assessment
│
└─ Send to assessment_queue
   ├─ Review type: 'modesty' (for confirmed_new)
   └─ Review type: 'duplication' (for suspected_duplicate)
```

### Baseline Scanner Flow

```
Catalog scan (sorted by newest)
│
├─ Extract lightweight data (URL, title, price)
│
├─ For each product:
│  ├─ URL already in catalog_products? → Update (price/stock only)
│  └─ URL NOT in catalog_products? → Insert with review_status='baseline'
│
└─ Done (NO assessment queue, NO Shopify upload)
```

### New Product Importer Flow

```
User provides URL list
│
├─ For each URL:
│  ├─ Check if exists in products table → Skip if exists
│  ├─ Full extraction (single product)
│  ├─ Modesty classification (AI-based)
│  │  ├─ Modest → Upload to Shopify as published
│  │  └─ Not modest → Skip
│  └─ Save to products table (NOT assessment_queue)
│
└─ Done (bypasses human assessment)
```

---

## Key Rules

### ✅ SEND to Assessment Queue

1. **Confirmed New Products** (catalog monitor)
   - Deduplication confidence < 85%
   - NOT in baseline
   - NOT in products table
   - Successfully uploaded to Shopify as draft

2. **Suspected Duplicates** (catalog monitor)
   - Deduplication confidence 85-94%
   - Needs human confirmation

### ❌ NEVER Send to Assessment Queue

1. **Baseline Products**
   - `catalog_products.review_status = 'baseline'`
   - Part of initial snapshot, not new detections

2. **Confirmed Existing**
   - Exact URL match in products table
   - Exact URL match in catalog_products (any status)
   - High confidence match (>95%)

3. **New Product Importer Items**
   - These are manually classified
   - Uploaded directly as published (if modest)

4. **Price/Stock Updates**
   - Existing products with only price/stock changes
   - Handled by product_updater, not catalog_monitor

---

## Anthropologie Baseline Cleanup (Nov 22, 2025)

**Issue Found**: 71 Anthropologie products migrated from old system to assessment_queue

**Investigation Results**:
- 24 products: `review_status = 'baseline'` (discovered Nov 6) → **REMOVED**
- 47 products: `review_status = 'migrated_to_new_system'` (discovered Nov 13) → **KEPT**

**Rationale**:
- Nov 6 products were part of baseline scan, incorrectly flagged
- Nov 13 products were genuinely new detections (no baseline scan on that date)
- Nov 13 products do NOT exist in earlier baseline entries

**Final State**:
- Assessment queue: 47 genuine Anthropologie products
- Removed: 24 baseline duplicates

---

## Future Enhancements

1. **Automated Lifecycle Tracking**
   - Add triggers to update `lifecycle_stage` automatically
   - Log state transitions with timestamps

2. **Baseline Verification**
   - Flag products marked 'baseline' if later detected as 'new' on same scan
   - Prevent baseline products from entering assessment

3. **Price Change Thresholds**
   - Define when price changes warrant re-assessment
   - Current: All price changes skip assessment (correct)

4. **Catalog vs Products Table Sync**
   - Approved products should be marked in catalog_products
   - Prevent re-flagging on subsequent scans

---

## Related Documentation

- `DEDUPLICATION_EXPLAINED.md` - Multi-level matching logic
- `WEB_ASSESSMENT_GUIDE.md` - Human review interface
- `CATALOG_MONITOR_GUIDE.md` - Monitoring workflow details
- `CATALOG_BASELINE_SCANNER_GUIDE.md` - Baseline creation

