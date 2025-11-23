# PHASE 3: BASELINE SCANNER UPDATES

**Duration**: 15-20 minutes  
**Risk**: LOW (simpler workflow, fewer changes)  
**Prerequisites**: Phase 1 & 2 completed successfully  
**Can rollback**: Yes (git revert)

---

## OBJECTIVE

Update `catalog_baseline_scanner.py` to:
- Set scan_type='baseline' when saving products
- Set image_url_source='catalog_extraction'
- Verify image extraction is working

**WHY THIS BEFORE MONITOR**: Baseline scanner is simpler, tests db_manager integration with fewer dependencies.

---

## FILE TO MODIFY

`Workflows/catalog_baseline_scanner.py`

---

## CHANGES REQUIRED

### Change 1: Update Product Saving Logic

**Location**: Find where products are saved to catalog_products (around line 300-350)

**Look for code similar to**:
```python
# Save products to catalog_products
for product in unique_products:
    await self.db_manager.save_catalog_product(product, ...)
```

**Modify to include new parameters**:
```python
# Save baseline products with scan_type='baseline'
for product in unique_products:
    await self.db_manager.save_catalog_product(
        product,
        scan_type='baseline',  # NEW - marks as baseline scan
        review_status='baseline',  # existing
        image_url_source='catalog_extraction'  # NEW - tracks source
    )
```

---

### Change 2: Add Image Extraction Verification

**Location**: After catalog extraction, before saving (around line 250-280)

**Add logging to verify images extracted**:
```python
# Verify image extraction
images_extracted = 0
images_missing = 0

for product in catalog_products:
    if product.get('image_urls'):
        images_extracted += 1
        logger.debug(f"✅ {len(product['image_urls'])} images for {product.get('title', 'Unknown')[:50]}")
    else:
        images_missing += 1
        logger.warning(f"⚠️ No images for {product.get('title', 'Unknown')[:50]} - {product.get('url', 'No URL')}")

logger.info(f"📸 Image extraction: {images_extracted} with images, {images_missing} without")

if images_missing > images_extracted * 0.5:  # More than 50% missing
    logger.warning(f"⚠️ HIGH IMAGE MISS RATE: {images_missing}/{images_extracted + images_missing} products missing images")
```

---

### Change 3: Verify Tower Image Extraction

**Check if catalog extractors are capturing images**:

**For Markdown retailers** (Revolve, ASOS, etc.):
- Verify `markdown_catalog_extractor.py` extracts image_urls
- Should already be working

**For Patchright retailers** (Anthropologie, Urban Outfitters, etc.):
- Verify `patchright_catalog_extractor.py` extracts image_urls  
- Should already be working

**Add to baseline scanner after tower initialization**:
```python
# Log extraction configuration
logger.info(f"📋 Extraction method for {retailer}: {'Markdown' if retailer in MARKDOWN_RETAILERS else 'Patchright'}")
logger.info(f"📸 Image extraction: Enabled (catalog-level)")
```

---

## TESTING

Run baseline scan on small retailer to verify:

```bash
cd "/Users/yav/Agent Modest Scraper System"
python3 -m Workflows.catalog_baseline_scanner revolve dresses modest
```

**What to look for**:
1. Log messages showing image extraction counts
2. No errors during save_catalog_product calls
3. Products saved with scan_type='baseline'

---

## VERIFICATION QUERIES

After test run, verify in database:

```sql
-- 1. Check scan_type set correctly
SELECT scan_type, COUNT(*) 
FROM catalog_products 
WHERE retailer = 'revolve'
AND discovered_date >= date('now', '-1 hour')
GROUP BY scan_type;
-- Expected: Should show scan_type='baseline' for new entries

-- 2. Check image_url_source set
SELECT image_url_source, COUNT(*)
FROM catalog_products
WHERE retailer = 'revolve'
AND discovered_date >= date('now', '-1 hour')
GROUP BY image_url_source;
-- Expected: Should show image_url_source='catalog_extraction'

-- 3. Check image extraction rate
SELECT 
    COUNT(*) as total,
    COUNT(CASE WHEN image_urls IS NOT NULL AND image_urls != '' AND image_urls != '[]' THEN 1 END) as with_images,
    ROUND(COUNT(CASE WHEN image_urls IS NOT NULL AND image_urls != '' AND image_urls != '[]' THEN 1 END) * 100.0 / COUNT(*), 1) as percentage
FROM catalog_products
WHERE retailer = 'revolve'
AND discovered_date >= date('now', '-1 hour');
-- Expected: >80% should have images

-- 4. Sample image URLs
SELECT catalog_url, image_urls
FROM catalog_products
WHERE retailer = 'revolve'
AND discovered_date >= date('now', '-1 hour')
AND image_urls IS NOT NULL
AND image_urls != ''
LIMIT 3;
-- Expected: Should show actual image URL arrays
```

---

## SHOW ME

After execution, show me:
1. ✅ Modified code sections (scan_type, image_url_source)
2. ✅ Test run output (especially image extraction counts)
3. ✅ Results of all 4 verification queries
4. ✅ Any warnings about missing images
5. ✅ Confirmation no errors occurred

---

## SUCCESS CRITERIA

✅ Baseline scan completes without errors  
✅ scan_type='baseline' set for all new entries  
✅ image_url_source='catalog_extraction' set for all new entries  
✅ >80% of products have images extracted  
✅ Image URLs are actual URLs (not empty/null)  
✅ Logging shows image extraction working

---

## IF ERRORS OCCUR

**Error: "save_catalog_product() got unexpected keyword argument"**  
- Phase 2 not completed correctly
- Go back and verify db_manager.py updated

**Error: "No images extracted"**  
- Check which tower is being used (Markdown vs Patchright)
- Verify tower's catalog extractor includes image_urls in response
- May need to check tower extraction code

**Warning: "HIGH IMAGE MISS RATE"**  
- Some retailers may not have images on catalog pages
- Acceptable if <50% missing
- If >50% missing, need to investigate tower extraction

---

## COMMIT

After successful verification:
```bash
git add Workflows/catalog_baseline_scanner.py
git commit -m "Phase 3: Update baseline scanner for lifecycle tracking"
```

---

## NEXT STEP

After Phase 3 completes successfully:
→ Proceed to **Phase 4: Catalog Monitor Updates**

DO NOT proceed until verification queries confirm scan_type working.
