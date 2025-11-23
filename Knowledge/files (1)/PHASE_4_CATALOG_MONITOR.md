# PHASE 4: CATALOG MONITOR UPDATES

**Duration**: 30-40 minutes  
**Risk**: MEDIUM (most complex workflow, many changes)  
**Prerequisites**: Phase 1, 2, 3 completed successfully  
**Can rollback**: Yes (git revert)

---

## OBJECTIVE

Update `catalog_monitor.py` to:
1. Write ALL scanned products to catalog_products (historical snapshots)
2. Detect price changes and flag for Product Updater
3. Link catalog products to products table
4. Set lifecycle_stage on new products
5. Set scan_type='monitor' for snapshots

**WHY LAST**: Most complex workflow, depends on all previous phases working.

---

## FILE TO MODIFY

`Workflows/catalog_monitor.py`

---

## CHANGES REQUIRED

### Change 1: Add New Imports

**Location**: Top of file

**Add**:
```python
from datetime import datetime
from typing import Optional
from difflib import SequenceMatcher
```

---

### Change 2: Add Snapshot Writing Method

**Location**: After existing methods, before monitor_catalog (around line 150)

**Add complete new method**:
```python
async def _save_catalog_snapshot(
    self,
    catalog_products: List[Dict],
    retailer: str,
    category: str,
    modesty_level: str
) -> None:
    """
    Save ALL catalog products as historical snapshot
    Called on EVERY monitor run to track catalog changes over time
    
    This creates new entries in catalog_products table with scan_type='monitor'
    to maintain historical log of what was in catalog on each scan date.
    """
    logger.info(f"📸 Saving catalog snapshot: {len(catalog_products)} products")
    
    conn = self.db_manager._get_connection()
    cursor = conn.cursor()
    
    saved = 0
    for product in catalog_products:
        try:
            # Extract fields
            url = product.get('url') or product.get('catalog_url')
            title = product.get('title')
            price = product.get('price')
            product_code = product.get('product_code')
            image_urls = product.get('image_urls')
            
            # Convert image_urls to JSON string if it's a list
            if isinstance(image_urls, list):
                import json
                image_urls = json.dumps(image_urls)
            
            # Insert into catalog_products
            cursor.execute("""
                INSERT INTO catalog_products 
                (catalog_url, retailer, category, title, price, product_code, 
                 image_urls, discovered_date, review_status, scan_type, image_url_source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                url,
                retailer,
                category,
                title,
                price,
                product_code,
                image_urls,
                datetime.utcnow().isoformat(),
                'baseline',  # All catalog snapshots are marked 'baseline'
                'monitor',   # This distinguishes from baseline scanner
                'catalog_extraction'
            ))
            saved += 1
            
        except Exception as e:
            logger.error(f"Failed to save catalog snapshot for {url}: {e}")
            continue
    
    conn.commit()
    conn.close()
    
    logger.info(f"✅ Catalog snapshot saved: {saved}/{len(catalog_products)} products")
```

---

### Change 3: Add Price Change Detection Method

**Location**: After _save_catalog_snapshot method

**Add complete new method**:
```python
async def _detect_price_changes(
    self,
    catalog_products: List[Dict],
    retailer: str
) -> int:
    """
    Compare catalog prices to products table
    Flag products where price changed for Product Updater priority queue
    
    Returns:
        Number of price changes detected
    """
    conn = self.db_manager._get_connection()
    cursor = conn.cursor()
    
    price_changes = 0
    
    for product in catalog_products:
        try:
            url = product.get('url') or product.get('catalog_url')
            catalog_price = product.get('price')
            
            if not url or not catalog_price:
                continue
            
            # Check if product exists in products table
            # Try exact match first, then normalized
            cursor.execute("""
                SELECT url, price FROM products 
                WHERE (url = ? OR RTRIM(SUBSTR(url, 1, INSTR(url || '?', '?') - 1), '/') = ?)
                AND retailer = ?
            """, (url, url.split('?')[0].rstrip('/'), retailer))
            
            result = cursor.fetchone()
            
            if result:
                product_url, product_price = result
                
                # Price changed?
                if product_price and abs(float(catalog_price) - float(product_price)) >= 0.01:
                    price_diff = float(catalog_price) - float(product_price)
                    
                    # Add to priority queue
                    cursor.execute("""
                        INSERT INTO product_update_queue
                        (product_url, retailer, priority, reason, 
                         catalog_price, products_price, price_difference, detected_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        product_url,
                        retailer,
                        'high' if abs(price_diff) > 50 else 'normal',
                        'price_change_detected_in_catalog',
                        catalog_price,
                        product_price,
                        price_diff,
                        datetime.utcnow().isoformat()
                    ))
                    
                    price_changes += 1
                    logger.debug(f"💰 Price change: {product_url[:50]}... ${product_price} → ${catalog_price}")
        
        except Exception as e:
            logger.error(f"Price change detection failed: {e}")
            continue
    
    conn.commit()
    conn.close()
    
    if price_changes > 0:
        logger.info(f"💰 Detected {price_changes} price changes")
    
    return price_changes
```

---

### Change 4: Add Cross-Table Linking Method

**Location**: After _detect_price_changes method

**Add complete new method**:
```python
async def _link_to_products_table(
    self,
    catalog_product: Dict,
    retailer: str
) -> Optional[Dict]:
    """
    Try to link catalog product to products table using multi-level deduplication
    
    Returns:
        dict with linked_product_url, link_confidence, link_method or None
    """
    conn = self.db_manager._get_connection()
    cursor = conn.cursor()
    
    url = catalog_product.get('url') or catalog_product.get('catalog_url')
    title = catalog_product.get('title')
    price = catalog_product.get('price')
    product_code = catalog_product.get('product_code')
    
    # Check retailer URL stability to decide strategy
    cursor.execute("""
        SELECT best_dedup_method, url_stability_score 
        FROM retailer_url_patterns 
        WHERE retailer = ?
    """, (retailer,))
    
    pattern_result = cursor.fetchone()
    
    # If retailer has low URL stability, prefer fuzzy matching
    prefer_fuzzy = False
    if pattern_result:
        best_method, stability = pattern_result
        prefer_fuzzy = (stability < 0.50 or best_method == 'fuzzy_title_price')
    
    # Level 1: Exact URL (unless we prefer fuzzy)
    if not prefer_fuzzy:
        cursor.execute("SELECT url FROM products WHERE url = ? AND retailer = ?", (url, retailer))
        result = cursor.fetchone()
        if result:
            conn.close()
            return {'linked_product_url': result[0], 'link_confidence': 1.0, 'link_method': 'exact_url'}
    
    # Level 2: Normalized URL
    if not prefer_fuzzy:
        normalized = url.split('?')[0].rstrip('/')
        cursor.execute("""
            SELECT url FROM products 
            WHERE RTRIM(SUBSTR(url, 1, INSTR(url || '?', '?') - 1), '/') = ?
            AND retailer = ?
        """, (normalized, retailer))
        result = cursor.fetchone()
        if result:
            conn.close()
            return {'linked_product_url': result[0], 'link_confidence': 0.95, 'link_method': 'normalized_url'}
    
    # Level 3: Product code
    if product_code and not prefer_fuzzy:
        cursor.execute("""
            SELECT url FROM products 
            WHERE product_code = ? AND retailer = ?
        """, (product_code, retailer))
        result = cursor.fetchone()
        if result:
            conn.close()
            return {'linked_product_url': result[0], 'link_confidence': 0.90, 'link_method': 'product_code'}
    
    # Level 4: Fuzzy title + price (ALWAYS try this, especially for low-stability retailers)
    if title and price:
        cursor.execute("""
            SELECT url, title FROM products 
            WHERE ABS(price - ?) < 1.0 AND retailer = ?
        """, (price, retailer))
        
        products = cursor.fetchall()
        
        best_match = None
        best_similarity = 0.0
        
        for product_url, product_title in products:
            similarity = SequenceMatcher(
                None,
                title.lower().strip(),
                product_title.lower().strip()
            ).ratio()
            
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = product_url
        
        if best_similarity > 0.90:
            confidence = 0.85 + (best_similarity - 0.90) * 0.5
            conn.close()
            return {'linked_product_url': best_match, 'link_confidence': confidence, 'link_method': 'fuzzy_title_price'}
    
    conn.close()
    return None
```

---

### Change 5: Modify monitor_catalog Method

**Location**: Find the monitor_catalog method (around line 180-400)

**Find the section AFTER deduplication, BEFORE extraction of new products**

**Add these two new steps**:

```python
# Existing code above (deduplication results)
# ...

# NEW STEP 4.5: Save catalog snapshot (ALL products, every run)
await self._save_catalog_snapshot(
    catalog_products=catalog_products,
    retailer=retailer,
    category=category,
    modesty_level=modesty_level
)

# NEW STEP 4.6: Detect price changes
price_changes = await self._detect_price_changes(
    catalog_products=catalog_products,
    retailer=retailer
)

# Continue with existing code (extract new products)
# ...
```

---

### Change 6: Modify Product Creation

**Location**: Find where new products are saved to products table (around line 700-800)

**Look for code like**:
```python
await self.db_manager.save_product(
    url=product['url'],
    product_data=full_product,
    source='monitor',
    # ... other fields
)
```

**Modify to ADD lifecycle tracking**:
```python
await self.db_manager.save_product(
    url=product['url'],
    product_data=full_product,
    source='monitor',
    lifecycle_stage='pending_assessment',  # NEW
    data_completeness='full',  # NEW
    last_workflow='catalog_monitor',  # NEW
    extracted_at=datetime.utcnow().isoformat(),  # NEW
    # ... other existing fields
)
```

---

## TESTING

Run catalog monitor on small retailer to verify:

```bash
cd "/Users/yav/Agent Modest Scraper System"
python3 -m Workflows.catalog_monitor revolve dresses modest --max-pages 1
```

**What to look for**:
1. "📸 Saving catalog snapshot" log message
2. "✅ Catalog snapshot saved" confirmation
3. "💰 Detected X price changes" (if any)
4. No errors during snapshot save
5. New products have lifecycle_stage set

---

## VERIFICATION QUERIES

After test run:

```sql
-- 1. Verify monitor snapshots created
SELECT scan_type, COUNT(*) 
FROM catalog_products 
WHERE retailer = 'revolve'
AND discovered_date >= date('now', '-1 hour')
GROUP BY scan_type;
-- Expected: Should show scan_type='monitor' for new entries

-- 2. Check price change detection
SELECT * FROM product_update_queue 
WHERE detected_at >= datetime('now', '-1 hour')
LIMIT 5;
-- Expected: Any detected price changes should appear here

-- 3. Verify lifecycle_stage on new products
SELECT lifecycle_stage, data_completeness, COUNT(*)
FROM products
WHERE first_seen >= datetime('now', '-1 hour')
AND source = 'monitor'
GROUP BY lifecycle_stage, data_completeness;
-- Expected: Should show lifecycle_stage='pending_assessment', data_completeness='full'

-- 4. Check snapshot count vs detected products
SELECT 
    (SELECT COUNT(*) FROM catalog_products WHERE scan_type='monitor' AND discovered_date >= date('now', '-1 hour')) as snapshots,
    (SELECT COUNT(*) FROM products WHERE source='monitor' AND first_seen >= datetime('now', '-1 hour')) as new_products;
-- Expected: snapshots >> new_products (snapshot includes ALL catalog products)
```

---

## SHOW ME

After execution, show me:
1. ✅ All 3 new methods added (_save_catalog_snapshot, _detect_price_changes, _link_to_products_table)
2. ✅ monitor_catalog modified to call snapshot/price methods
3. ✅ save_product modified to include lifecycle fields
4. ✅ Test run output (snapshot saved, price changes detected)
5. ✅ Results of all 4 verification queries
6. ✅ Any errors or warnings

---

## SUCCESS CRITERIA

✅ Catalog monitor completes without errors  
✅ Snapshot saved with scan_type='monitor'  
✅ Snapshot count matches catalog_products scanned  
✅ Price changes detected (if any exist)  
✅ New products have lifecycle_stage='pending_assessment'  
✅ No duplicate snapshot entries (unique per run)

---

## IF ERRORS OCCUR

**Error: "AttributeError: 'CatalogMonitor' object has no attribute '_save_catalog_snapshot'"**  
- Method not added to class properly
- Check indentation matches class methods

**Error: "no such table: product_update_queue"**  
- Phase 1 not completed
- Go back and run Phase 1 schema changes

**Error: "too many SQL variables"**  
- Batch inserts may hit limits
- Already handled with individual inserts in snapshot method

**Error: "UNIQUE constraint failed"**  
- Snapshot entries might be duplicating
- Expected behavior (historical log grows)
- Check if scan_type distinguishing properly

---

## COMMIT

After successful verification:
```bash
git add Workflows/catalog_monitor.py
git commit -m "Phase 4: Update catalog monitor for lifecycle tracking and snapshots"
```

---

## NEXT STEP

After Phase 4 completes successfully:
→ Proceed to **Phase 5: Assessment & Importer Updates**

DO NOT proceed until verification queries confirm snapshots working.
