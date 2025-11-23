# PHASE 4 ADDENDUM: IMAGE EXTRACTION & DEDUPLICATION

**IMPORTANT**: Run this AFTER completing Phase 4 main changes  
**Duration**: 15 minutes  
**Risk**: LOW (additive changes)

---

## OBJECTIVE

Add two missing features:
1. **Ensure** catalog extractors are extracting images (not just verifying)
2. **Add** image URL matching as deduplication signal (Level 5)
3. **Use** retailer image consistency as confidence modifier

---

## PART A: VERIFY/ADD IMAGE EXTRACTION

### Step 1: Check if Catalog Extractors Extract Images

**Run this check script**:

Create `check_image_extraction.py`:
```python
import asyncio
import sys
sys.path.append('Extraction/Markdown')
sys.path.append('Extraction/Patchright')

from markdown_catalog_extractor import MarkdownCatalogExtractor
from patchright_catalog_extractor import PatchrightCatalogExtractor

async def test_markdown():
    print("Testing Markdown catalog extraction...")
    extractor = MarkdownCatalogExtractor()
    
    # Test on Revolve
    result = await extractor.extract_catalog(
        'https://www.revolve.com/dresses?sortBy=newest',
        'revolve'
    )
    
    if result.success and result.products:
        sample = result.products[0]
        if 'image_urls' in sample and sample['image_urls']:
            print(f"✅ Markdown extracts images: {len(sample['image_urls'])} images")
        else:
            print(f"❌ Markdown NOT extracting images")
    else:
        print(f"❌ Markdown extraction failed")

async def test_patchright():
    print("\nTesting Patchright catalog extraction...")
    extractor = PatchrightCatalogExtractor()
    
    # Test on Anthropologie
    result = await extractor.extract_catalog(
        'https://www.anthropologie.com/dresses',
        'anthropologie'
    )
    
    if result.success and result.products:
        sample = result.products[0]
        if 'image_urls' in sample and sample['image_urls']:
            print(f"✅ Patchright extracts images: {len(sample['image_urls'])} images")
        else:
            print(f"❌ Patchright NOT extracting images")
    else:
        print(f"❌ Patchright extraction failed")

async def main():
    await test_markdown()
    await test_patchright()

if __name__ == '__main__':
    asyncio.run(main())
```

**Run**:
```bash
cd "/Users/yav/Agent Modest Scraper System"
python3 check_image_extraction.py
```

---

### Step 2: If Images NOT Extracted, Add Extraction

**If Markdown catalog extractor NOT extracting images:**

Find in `Extraction/Markdown/markdown_catalog_extractor.py` where products are parsed.

**Look for code parsing products from LLM response**. Should look like:
```python
# Parsing product data
product = {
    'url': parts[0],
    'title': parts[1],
    'price': parts[2],
    # ... other fields
}
```

**Add image_urls field**:
```python
product = {
    'url': parts[0],
    'title': parts[1],
    'price': parts[2],
    'image_urls': parts[X] if len(parts) > X else [],  # ADD THIS
    # ... other fields
}
```

**AND update the LLM prompt** to request images:
```python
prompt = f"""
Extract catalog products. For each product include:
- URL
- Title  
- Price
- Image URLs (all images)  # ADD THIS
...
"""
```

---

**If Patchright catalog extractor NOT extracting images:**

Find in `Extraction/Patchright/patchright_catalog_extractor.py` where DOM extraction happens.

**Look for code extracting product containers**. Add image extraction:
```python
# Extract images from container
images = []
img_elements = container.query_selector_all('img')
for img in img_elements:
    src = img.get_attribute('src')
    if src and 'http' in src:
        images.append(src)

product = {
    'url': url,
    'title': title,
    'price': price,
    'image_urls': images,  # ADD THIS
    # ... other fields
}
```

---

## PART B: ADD IMAGE MATCHING TO DEDUPLICATION

### Modify catalog_monitor.py

**Location**: In the `_link_to_products_table` method (added in Phase 4)

**After Level 4 (fuzzy title + price), BEFORE returning None:**

**Add complete Level 5**:
```python
    # Level 5: Image URL matching (secondary confidence signal)
    if catalog_product.get('image_urls'):
        try:
            import json
            
            # Parse catalog images
            catalog_images_raw = catalog_product.get('image_urls')
            if isinstance(catalog_images_raw, str):
                catalog_images = set(json.loads(catalog_images_raw)) if catalog_images_raw and catalog_images_raw != '[]' else set()
            elif isinstance(catalog_images_raw, list):
                catalog_images = set(catalog_images_raw)
            else:
                catalog_images = set()
            
            if not catalog_images:
                conn.close()
                return None
            
            # Get products with images and matching price (within $10 for broader matching)
            cursor.execute("""
                SELECT url, image_urls FROM products 
                WHERE ABS(price - ?) < 10.0
                AND retailer = ?
                AND image_urls IS NOT NULL
                AND image_urls != ''
                AND image_urls != '[]'
            """, (price or 0, retailer))
            
            products_with_images = cursor.fetchall()
            
            best_match = None
            best_overlap_ratio = 0.0
            
            for product_url, product_images_raw in products_with_images:
                # Parse product images
                if isinstance(product_images_raw, str):
                    product_images = set(json.loads(product_images_raw)) if product_images_raw else set()
                elif isinstance(product_images_raw, list):
                    product_images = set(product_images_raw)
                else:
                    product_images = set()
                
                if not product_images:
                    continue
                
                # Check for overlapping images (exact URL match)
                overlap = catalog_images.intersection(product_images)
                
                if overlap:
                    overlap_ratio = len(overlap) / len(catalog_images)
                    
                    if overlap_ratio > best_overlap_ratio:
                        best_overlap_ratio = overlap_ratio
                        best_match = product_url
            
            if best_match and best_overlap_ratio >= 0.5:  # At least 50% overlap
                # Check retailer image consistency for confidence adjustment
                cursor.execute("""
                    SELECT image_urls_consistent 
                    FROM retailer_url_patterns 
                    WHERE retailer = ?
                """, (retailer,))
                consistency_result = cursor.fetchone()
                
                # Calculate confidence based on overlap and retailer consistency
                if consistency_result and consistency_result[0] == 1:
                    # High consistency retailer: images are reliable
                    confidence = 0.75 + (best_overlap_ratio * 0.20)  # 0.75 to 0.95
                else:
                    # Low consistency retailer: images less reliable
                    confidence = 0.65 + (best_overlap_ratio * 0.15)  # 0.65 to 0.80
                
                conn.close()
                logger.debug(f"Image match: {best_overlap_ratio:.0%} overlap, confidence {confidence:.2f}")
                return {'linked_product_url': best_match, 'link_confidence': confidence, 'link_method': 'image_url_match'}
        
        except Exception as e:
            logger.error(f"Image matching failed: {e}")
    
    # No match found
    conn.close()
    return None
```

---

## PART C: UPDATE BACKFILL SCRIPT

### Modify backfill_product_linking.py

**Location**: In the `_find_matching_product` method

**After Level 5 (fuzzy title + price), add the same Level 6 image matching**:

Copy the entire "Level 5: Image URL matching" code block from above and add it to the backfill script, but rename it to "Level 6" to avoid confusion.

---

## VERIFICATION

### Test 1: Check Image Extraction
```bash
python3 check_image_extraction.py
```
**Expected**: Both Markdown and Patchright should show "✅ extracts images"

### Test 2: Run Catalog Monitor
```bash
python3 -m Workflows.catalog_monitor revolve dresses modest --max-pages 1
```

**Check logs for**:
```
"Image match: 80% overlap, confidence 0.91"
```

### Test 3: Check Database
```sql
-- Check if catalog products have images
SELECT 
    COUNT(*) as total,
    COUNT(CASE WHEN image_urls IS NOT NULL AND image_urls != '' AND image_urls != '[]' THEN 1 END) as with_images
FROM catalog_products
WHERE discovered_date >= date('now', '-1 day');

-- Check image-based linking
SELECT COUNT(*) 
FROM catalog_products 
WHERE link_method = 'image_url_match';
```

---

## SUCCESS CRITERIA

✅ Catalog extractors extract images (both towers)  
✅ Images saved to catalog_products.image_urls  
✅ Image matching added to deduplication (Level 5)  
✅ Image consistency used as confidence modifier  
✅ Backfill script includes image matching  
✅ Database shows some image_url_match links

---

## COMMIT

After successful verification:
```bash
git add Extraction/Markdown/markdown_catalog_extractor.py
git add Extraction/Patchright/patchright_catalog_extractor.py
git add Workflows/catalog_monitor.py
git add Shared/backfill_product_linking.py
git commit -m "Phase 4 Addendum: Add image extraction and deduplication"
```

---

## IF ALREADY EXTRACTING IMAGES

If `check_image_extraction.py` shows images ARE being extracted:
- ✅ Skip Part A
- ✅ Just do Part B (add image matching to deduplication)
- ✅ Do Part C (update backfill script)

---

## NOTES

- Image matching is **secondary confidence** (0.65-0.95)
- Only used when other methods fail
- Respects retailer image consistency scores
- Requires 50%+ overlap to match
- Lower confidence than URL/title matching (appropriate)
