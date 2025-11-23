# COMPREHENSIVE PRODUCT LIFECYCLE & CROSS-TABLE LINKING IMPLEMENTATION

**Context**: This prompt implements the complete product lifecycle management system, cross-table linking between catalog_products and products, URL stability tracking, price change detection, and image consistency tracking for the Agent Modest e-commerce scraper system.

**Date**: November 23, 2025

---

## 🎯 OBJECTIVES

1. **Cross-Table Linking**: Link catalog_products to products table using multi-level deduplication
2. **URL Stability Tracking**: Learn which retailers have stable URLs vs unstable (like Revolve)
3. **Lifecycle Management**: Track product state through 7 distinct lifecycle stages
4. **Price Change Detection**: Flag products for Product Updater when catalog prices change
5. **Image Consistency**: Track which retailers have consistent image URLs catalog→product
6. **Historical Snapshots**: Catalog Monitor writes ALL products to catalog_products on every run
7. **Backfill Scripts**: Create scripts to analyze existing data (manual execution)

---

## 📋 PART 1: DATABASE SCHEMA CHANGES

### Step 1.1: Modify catalog_products Table

```sql
-- Add cross-table linking fields
ALTER TABLE catalog_products ADD COLUMN linked_product_url TEXT;
ALTER TABLE catalog_products ADD COLUMN link_confidence REAL;
ALTER TABLE catalog_products ADD COLUMN link_method TEXT;

-- Add scan type tracking (baseline vs monitor)
ALTER TABLE catalog_products ADD COLUMN scan_type TEXT DEFAULT 'baseline';

-- Add price change detection
ALTER TABLE catalog_products ADD COLUMN price_change_detected INTEGER DEFAULT 0;
ALTER TABLE catalog_products ADD COLUMN old_price REAL;
ALTER TABLE catalog_products ADD COLUMN needs_product_update INTEGER DEFAULT 0;

-- Add image source tracking
ALTER TABLE catalog_products ADD COLUMN image_url_source TEXT DEFAULT 'catalog_extraction';
```

### Step 1.2: Modify products Table

```sql
-- Add lifecycle tracking
ALTER TABLE products ADD COLUMN lifecycle_stage TEXT;
ALTER TABLE products ADD COLUMN data_completeness TEXT;
ALTER TABLE products ADD COLUMN last_workflow TEXT;
ALTER TABLE products ADD COLUMN extracted_at TIMESTAMP;
ALTER TABLE products ADD COLUMN assessed_at TIMESTAMP;
ALTER TABLE products ADD COLUMN last_checked TIMESTAMP;
```

**Lifecycle Stage Values**:
- `'pending_assessment'` - Extracted, uploaded to Shopify as draft, in assessment queue
- `'assessed_approved'` - Human approved, published to Shopify
- `'assessed_rejected'` - Human rejected, kept as draft
- `'imported_direct'` - Imported via New Product Importer (bypassed assessment)

**Data Completeness Values**:
- `'lightweight'` - Catalog data only (URL, title, price)
- `'full'` - Complete extraction (description, neckline, sleeves)
- `'enriched'` - Full + Shopify data (uploaded with images)

### Step 1.3: Create retailer_url_patterns Table

```sql
CREATE TABLE retailer_url_patterns (
    retailer TEXT PRIMARY KEY,
    url_stability_score REAL DEFAULT 0.0,
    last_measured TIMESTAMP,
    sample_size INTEGER DEFAULT 0,
    
    -- Stability flags
    product_code_stable INTEGER DEFAULT 1,
    path_stable INTEGER DEFAULT 1,
    image_urls_consistent INTEGER DEFAULT 1,
    
    -- Deduplication strategy
    best_dedup_method TEXT DEFAULT 'url',
    dedup_confidence_threshold REAL DEFAULT 0.85,
    
    -- Change tracking
    url_changes_detected INTEGER DEFAULT 0,
    code_changes_detected INTEGER DEFAULT 0,
    image_url_changes_detected INTEGER DEFAULT 0,
    
    notes TEXT
);
```

**Purpose**: Learn which retailers have stable URLs (Anthropologie) vs unstable (Revolve), and automatically adjust deduplication strategy.

### Step 1.4: Create product_update_queue Table

```sql
CREATE TABLE product_update_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_url TEXT NOT NULL,
    retailer TEXT NOT NULL,
    priority TEXT DEFAULT 'normal',
    reason TEXT,
    
    -- Price tracking
    catalog_price REAL,
    products_price REAL,
    price_difference REAL,
    
    -- Queue management
    detected_at TIMESTAMP,
    processed INTEGER DEFAULT 0,
    processed_at TIMESTAMP,
    
    FOREIGN KEY (product_url) REFERENCES products(url)
);
```

**Purpose**: When Catalog Monitor detects price changes, flag products here so user can manually review and run Product Updater on them.

---

## 📝 PART 2: WORKFLOW MODIFICATIONS

### Step 2.1: Modify catalog_monitor.py

**Location**: `Workflows/catalog_monitor.py`

**Changes Required**:

#### A. Add Imports
```python
from datetime import datetime
from typing import Optional
```

#### B. After Catalog Extraction (around line 250-300)

Add new method:
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
            
        except Exception as e:
            logger.error(f"Failed to save catalog snapshot for {url}: {e}")
            continue
    
    conn.commit()
    conn.close()
    
    logger.info(f"✅ Catalog snapshot saved: {len(catalog_products)} products")
```

#### C. Add Price Change Detection Method

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
            cursor.execute("""
                SELECT url, price FROM products 
                WHERE url = ? OR RTRIM(SUBSTR(url, 1, INSTR(url || '?', '?') - 1), '/') = ?
            """, (url, url.split('?')[0].rstrip('/')))
            
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
                    logger.info(f"💰 Price change detected: {product_url} ${product_price} → ${catalog_price}")
        
        except Exception as e:
            logger.error(f"Price change detection failed: {e}")
            continue
    
    conn.commit()
    conn.close()
    
    return price_changes
```

#### D. Add Cross-Table Linking Method

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
    
    # Level 4: Fuzzy title + price (ALWAYS try this, especially for Revolve)
    if title and price:
        cursor.execute("""
            SELECT url, title FROM products 
            WHERE ABS(price - ?) < 1.0 AND retailer = ?
        """, (price, retailer))
        
        products = cursor.fetchall()
        
        best_match = None
        best_similarity = 0.0
        
        from difflib import SequenceMatcher
        
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

#### E. Modify monitor_catalog Method (around line 180-400)

Find the section after deduplication where products are classified. Add:

```python
# AFTER: Step 4: Deduplicate catalog products
# BEFORE: Step 5: Extract new products

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

if price_changes > 0:
    logger.info(f"💰 Detected {price_changes} price changes - added to update queue")
```

#### F. Modify Product Creation (around line 700-800)

Find where new products are saved to products table. Update:

```python
# EXISTING CODE (find this):
await self.db_manager.save_product(
    url=product['url'],
    product_data=full_product,
    # ... other fields
)

# MODIFY TO ADD lifecycle tracking:
await self.db_manager.save_product(
    url=product['url'],
    product_data=full_product,
    lifecycle_stage='pending_assessment',
    data_completeness='full',
    last_workflow='catalog_monitor',
    extracted_at=datetime.utcnow().isoformat(),
    # ... other existing fields
)
```

---

### Step 2.2: Modify catalog_baseline_scanner.py

**Location**: `Workflows/catalog_baseline_scanner.py`

**Changes Required**:

#### A. Modify Product Saving (around line 300-350)

Find where products are saved to catalog_products. Ensure:

```python
# Save baseline products with scan_type='baseline'
for product in unique_products:
    await self.db_manager.save_catalog_product(
        product,
        scan_type='baseline',  # ADD THIS
        review_status='baseline',
        image_url_source='catalog_extraction'  # ADD THIS
    )
```

#### B. Verify Image Extraction

Check if catalog extraction is capturing images. Look for:

```python
# In _extract_catalog_products method
# Ensure image_urls are being extracted

# If using Markdown tower:
# Check markdown_catalog_extractor.py extracts images

# If using Patchright tower:
# Check patchright_catalog_extractor.py extracts images
```

**Action**: Add logging to verify:

```python
if product.get('image_urls'):
    logger.debug(f"✅ Extracted {len(product['image_urls'])} images for {product.get('title')}")
else:
    logger.warning(f"⚠️ No images extracted for {product.get('title')}")
```

---

### Step 2.3: Modify Assessment Interface

**Location**: `web_assessment/api/submit_review.php`

**Changes Required**:

When products are approved/rejected, update lifecycle_stage:

```php
// FIND the existing code that updates products table after assessment
// ADD lifecycle_stage updates:

if ($decision === 'modest' || $decision === 'moderately_modest') {
    // Product approved - publish to Shopify
    $sql = "UPDATE products 
            SET modesty_status = ?,
                shopify_status = 'published',
                lifecycle_stage = 'assessed_approved',
                assessed_at = ?
            WHERE url = ?";
    $stmt->execute([$decision, date('Y-m-d H:i:s'), $product_url]);
    
} else {
    // Product rejected - keep as draft
    $sql = "UPDATE products 
            SET modesty_status = 'not_modest',
                shopify_status = 'draft',
                lifecycle_stage = 'assessed_rejected',
                assessed_at = ?
            WHERE url = ?";
    $stmt->execute([date('Y-m-d H:i:s'), $product_url]);
}
```

---

### Step 2.4: Modify New Product Importer

**Location**: `Workflows/new_product_importer.py`

**Changes Required**:

#### Find Product Creation (around line 400-500)

Update to set lifecycle_stage:

```python
# EXISTING CODE (find this):
await self.db_manager.save_product(
    url=url,
    product_data=extraction_result.product_data,
    source='new_product_import',
    # ... other fields
)

# MODIFY TO ADD:
await self.db_manager.save_product(
    url=url,
    product_data=extraction_result.product_data,
    source='new_product_import',
    lifecycle_stage='imported_direct',  # ADD THIS
    data_completeness='full',  # ADD THIS
    last_workflow='new_product_importer',  # ADD THIS
    extracted_at=datetime.utcnow().isoformat(),  # ADD THIS
    # ... other existing fields
)
```

---

### Step 2.5: Modify db_manager.py

**Location**: `Shared/db_manager.py`

**Changes Required**:

#### A. Update save_product Method

Find the `save_product` method and add new parameters:

```python
async def save_product(
    self,
    url: str,
    product_data: Dict,
    source: str = None,
    lifecycle_stage: str = None,  # ADD
    data_completeness: str = None,  # ADD
    last_workflow: str = None,  # ADD
    extracted_at: str = None,  # ADD
    assessed_at: str = None,  # ADD
    # ... other existing parameters
) -> bool:
    """Save product to database with lifecycle tracking"""
    
    try:
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # EXISTING code to extract fields from product_data
        # ...
        
        # ADD lifecycle fields to INSERT statement:
        cursor.execute("""
            INSERT INTO products (
                url, retailer, title, price, description,
                modesty_status, clothing_type, neckline, sleeve_length,
                shopify_id, shopify_status, source,
                lifecycle_stage, data_completeness, last_workflow,
                extracted_at, assessed_at,
                first_seen, last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                title = excluded.title,
                price = excluded.price,
                last_updated = excluded.last_updated,
                lifecycle_stage = excluded.lifecycle_stage,
                data_completeness = excluded.data_completeness,
                last_workflow = excluded.last_workflow
        """, (
            # ... existing fields
            lifecycle_stage,
            data_completeness,
            last_workflow,
            extracted_at,
            assessed_at,
            # ... existing fields
        ))
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Failed to save product: {e}")
        return False
```

#### B. Update save_catalog_product Method

Add scan_type and image_url_source parameters:

```python
async def save_catalog_product(
    self,
    product: Dict,
    scan_type: str = 'baseline',  # ADD
    review_status: str = 'baseline',
    image_url_source: str = 'catalog_extraction'  # ADD
) -> bool:
    """Save catalog product with scan type tracking"""
    
    try:
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO catalog_products (
                catalog_url, retailer, category, title, price, product_code,
                image_urls, discovered_date, review_status,
                scan_type, image_url_source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            product.get('url') or product.get('catalog_url'),
            product.get('retailer'),
            product.get('category'),
            product.get('title'),
            product.get('price'),
            product.get('product_code'),
            product.get('image_urls'),
            datetime.utcnow().isoformat(),
            review_status,
            scan_type,  # ADD
            image_url_source  # ADD
        ))
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Failed to save catalog product: {e}")
        return False
```

---

## 🔧 PART 3: BACKFILL SCRIPTS (Manual Execution)

### Step 3.1: Create backfill_product_linking.py

**Location**: `Shared/backfill_product_linking.py`

**Purpose**: Link existing catalog_products to products table

```python
"""
Backfill Product Linking
Links existing catalog_products entries to products table entries
Run manually AFTER schema changes are applied
"""

import asyncio
import sqlite3
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from difflib import SequenceMatcher
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ProductLinker:
    """Links catalog_products to products table using multi-level matching"""
    
    def __init__(self, db_path: str = 'Shared/products.db'):
        self.db_path = db_path
        self.stats = {
            'total_catalog_products': 0,
            'linked': 0,
            'high_confidence': 0,  # >95%
            'medium_confidence': 0,  # 85-95%
            'unlinked': 0,  # <85%, not confident enough
            'by_method': {},
            'by_retailer': {}
        }
    
    def get_connection(self):
        """Get database connection"""
        return sqlite3.connect(self.db_path)
    
    async def backfill_all(self):
        """Main backfill process"""
        logger.info("="*60)
        logger.info("🔗 STARTING PRODUCT LINKING BACKFILL")
        logger.info("="*60)
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get all catalog products not yet linked
        cursor.execute("""
            SELECT id, catalog_url, retailer, title, price, product_code, image_urls
            FROM catalog_products
            WHERE linked_product_url IS NULL
        """)
        catalog_products = cursor.fetchall()
        self.stats['total_catalog_products'] = len(catalog_products)
        
        logger.info(f"\n📊 Found {len(catalog_products)} catalog products to link\n")
        
        # Process each one
        processed = 0
        for cp in catalog_products:
            cp_id, catalog_url, retailer, title, price, product_code, image_urls = cp
            
            match = await self._find_matching_product(
                cursor, catalog_url, retailer, title, price, product_code, image_urls
            )
            
            if match:
                product_url, confidence, method = match
                
                # Only link if confidence >= 85%
                if confidence >= 0.85:
                    # Update catalog_products
                    cursor.execute("""
                        UPDATE catalog_products
                        SET linked_product_url = ?,
                            link_confidence = ?,
                            link_method = ?
                        WHERE id = ?
                    """, (product_url, confidence, method, cp_id))
                    
                    self.stats['linked'] += 1
                    self.stats['by_method'][method] = self.stats['by_method'].get(method, 0) + 1
                    self.stats['by_retailer'][retailer] = self.stats['by_retailer'].get(retailer, 0) + 1
                    
                    if confidence >= 0.95:
                        self.stats['high_confidence'] += 1
                    else:
                        self.stats['medium_confidence'] += 1
                else:
                    self.stats['unlinked'] += 1
            else:
                self.stats['unlinked'] += 1
            
            processed += 1
            if processed % 100 == 0:
                logger.info(f"⏳ Processed {processed}/{len(catalog_products)} ({processed/len(catalog_products)*100:.1f}%)")
                conn.commit()  # Commit periodically
        
        conn.commit()
        conn.close()
        
        self._print_stats()
    
    async def _find_matching_product(
        self, 
        cursor, 
        catalog_url: str, 
        retailer: str, 
        title: str, 
        price: float, 
        product_code: str, 
        image_urls: str
    ) -> Optional[Tuple[str, float, str]]:
        """
        Try to match catalog product to products table
        Returns: (product_url, confidence, method) or None
        """
        
        # Check if this retailer prefers fuzzy matching
        cursor.execute("""
            SELECT best_dedup_method, url_stability_score 
            FROM retailer_url_patterns 
            WHERE retailer = ?
        """, (retailer,))
        pattern_result = cursor.fetchone()
        
        prefer_fuzzy = False
        if pattern_result:
            best_method, stability = pattern_result
            prefer_fuzzy = (stability < 0.50 or best_method == 'fuzzy_title_price')
        
        # Level 1: Exact URL match (skip if prefer fuzzy)
        if not prefer_fuzzy:
            cursor.execute("""
                SELECT url FROM products 
                WHERE url = ? AND retailer = ?
            """, (catalog_url, retailer))
            result = cursor.fetchone()
            if result:
                return (result[0], 1.0, 'exact_url')
        
        # Level 2: Normalized URL match
        if not prefer_fuzzy:
            normalized = catalog_url.split('?')[0].rstrip('/')
            cursor.execute("""
                SELECT url FROM products 
                WHERE RTRIM(SUBSTR(url, 1, INSTR(url || '?', '?') - 1), '/') = ?
                AND retailer = ?
            """, (normalized, retailer))
            result = cursor.fetchone()
            if result:
                return (result[0], 0.95, 'normalized_url')
        
        # Level 3: Product code match
        if product_code and not prefer_fuzzy:
            cursor.execute("""
                SELECT url FROM products 
                WHERE product_code = ? AND retailer = ?
            """, (product_code, retailer))
            result = cursor.fetchone()
            if result:
                return (result[0], 0.90, 'product_code')
        
        # Level 4: Exact title + price
        if title and price:
            cursor.execute("""
                SELECT url FROM products 
                WHERE title = ? AND ABS(price - ?) < 1.0 AND retailer = ?
            """, (title, price, retailer))
            result = cursor.fetchone()
            if result:
                return (result[0], 0.95, 'exact_title_price')
        
        # Level 5: Fuzzy title + price (ALWAYS try, especially for unstable retailers)
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
                return (best_match, confidence, 'fuzzy_title_price')
        
        # No match found with sufficient confidence
        return None
    
    def _print_stats(self):
        """Print summary statistics"""
        total = self.stats['total_catalog_products']
        linked = self.stats['linked']
        unlinked = self.stats['unlinked']
        
        logger.info("\n" + "="*60)
        logger.info("📊 BACKFILL RESULTS")
        logger.info("="*60)
        logger.info(f"Total catalog products: {total:,}")
        logger.info(f"Successfully linked: {linked:,} ({linked/total*100:.1f}%)")
        logger.info(f"  High confidence (≥95%): {self.stats['high_confidence']:,}")
        logger.info(f"  Medium confidence (85-95%): {self.stats['medium_confidence']:,}")
        logger.info(f"Not linked (low confidence): {unlinked:,} ({unlinked/total*100:.1f}%)")
        
        logger.info(f"\n📈 By Method:")
        for method, count in sorted(self.stats['by_method'].items(), key=lambda x: -x[1]):
            logger.info(f"  {method}: {count:,}")
        
        logger.info(f"\n🏪 By Retailer:")
        for retailer, count in sorted(self.stats['by_retailer'].items(), key=lambda x: -x[1]):
            logger.info(f"  {retailer}: {count:,}")
        
        logger.info("="*60 + "\n")


async def main():
    """Main entry point"""
    linker = ProductLinker()
    await linker.backfill_all()


if __name__ == '__main__':
    asyncio.run(main())
```

---

### Step 3.2: Create analyze_url_stability.py

**Location**: `Shared/analyze_url_stability.py`

**Purpose**: Populate retailer_url_patterns table with real data

```python
"""
Analyze URL Stability Per Retailer
Populates retailer_url_patterns table based on actual linking results
Run manually AFTER backfill_product_linking.py completes
"""

import sqlite3
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class URLStabilityAnalyzer:
    """Analyzes URL stability patterns per retailer"""
    
    def __init__(self, db_path: str = 'Shared/products.db'):
        self.db_path = db_path
    
    def analyze_all_retailers(self):
        """Analyze URL stability for all retailers"""
        logger.info("="*60)
        logger.info("📊 ANALYZING URL STABILITY")
        logger.info("="*60)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get all retailers with linked products
        cursor.execute("""
            SELECT DISTINCT retailer 
            FROM catalog_products 
            WHERE linked_product_url IS NOT NULL
        """)
        retailers = [r[0] for r in cursor.fetchall()]
        
        logger.info(f"\nFound {len(retailers)} retailers to analyze\n")
        
        for retailer in retailers:
            self.analyze_retailer(cursor, retailer)
        
        conn.commit()
        conn.close()
        
        logger.info("\n✅ URL stability analysis complete!\n")
    
    def analyze_retailer(self, cursor, retailer: str):
        """Analyze URL stability for one retailer"""
        logger.info(f"📊 Analyzing {retailer}...")
        
        # Get all linked products for this retailer
        cursor.execute("""
            SELECT 
                cp.catalog_url,
                cp.linked_product_url,
                cp.link_method,
                cp.link_confidence,
                cp.product_code as cp_code,
                p.product_code as p_code,
                cp.image_urls as cp_images,
                p.image_urls as p_images
            FROM catalog_products cp
            JOIN products p ON cp.linked_product_url = p.url
            WHERE cp.retailer = ?
            AND cp.linked_product_url IS NOT NULL
        """, (retailer,))
        
        linked = cursor.fetchall()
        
        if not linked:
            logger.warning(f"  ⚠️ No linked products for {retailer}")
            return
        
        # Calculate metrics
        total = len(linked)
        url_changes = 0
        code_changes = 0
        image_url_changes = 0
        
        method_counts = {}
        
        for row in linked:
            catalog_url, product_url, method, confidence, cp_code, p_code, cp_images, p_images = row
            
            # Count method usage
            method_counts[method] = method_counts.get(method, 0) + 1
            
            # URL changed?
            normalized_catalog = catalog_url.split('?')[0].rstrip('/')
            normalized_product = product_url.split('?')[0].rstrip('/')
            if normalized_catalog != normalized_product:
                url_changes += 1
            
            # Product code changed?
            if cp_code and p_code and cp_code != p_code:
                code_changes += 1
            
            # Image URLs changed?
            if cp_images and p_images:
                import json
                try:
                    # Parse JSON arrays
                    cp_set = set(json.loads(cp_images)) if cp_images else set()
                    p_set = set(json.loads(p_images)) if p_images else set()
                    
                    # Check if they share any URLs
                    if cp_set and p_set and not cp_set.intersection(p_set):
                        image_url_changes += 1
                except:
                    # Simple string comparison fallback
                    if cp_images != p_images:
                        image_url_changes += 1
        
        # Calculate stability scores
        url_stability = 1.0 - (url_changes / total) if total > 0 else 1.0
        code_stability = 1 if code_changes == 0 else 0
        path_stability = 1 if url_stability > 0.80 else 0
        image_consistency = 1.0 - (image_url_changes / total) if total > 0 else 1.0
        
        # Determine best method based on actual usage
        best_method = max(method_counts.items(), key=lambda x: x[1])[0] if method_counts else 'url'
        
        # Get confidence threshold based on best method
        threshold_map = {
            'exact_url': 1.0,
            'normalized_url': 0.95,
            'product_code': 0.90,
            'exact_title_price': 0.95,
            'fuzzy_title_price': 0.85
        }
        threshold = threshold_map.get(best_method, 0.85)
        
        # Generate notes
        notes = (
            f"Analyzed {total} linked products. "
            f"URL stability: {url_stability:.0%}. "
            f"Primary matching: {best_method}. "
        )
        
        if url_stability < 0.50:
            notes += "⚠️ HIGH URL INSTABILITY - Use fuzzy title+price matching."
        elif url_stability < 0.80:
            notes += "⚠️ MODERATE URL INSTABILITY - Monitor changes."
        else:
            notes += "✅ URLs stable - Direct matching reliable."
        
        # Insert/update retailer_url_patterns
        cursor.execute("""
            INSERT OR REPLACE INTO retailer_url_patterns
            (retailer, url_stability_score, last_measured, sample_size,
             product_code_stable, path_stable, image_urls_consistent,
             best_dedup_method, dedup_confidence_threshold,
             url_changes_detected, code_changes_detected, image_url_changes_detected,
             notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            retailer,
            url_stability,
            datetime.now().isoformat(),
            total,
            code_stability,
            path_stability,
            1 if image_consistency > 0.80 else 0,
            best_method,
            threshold,
            url_changes,
            code_changes,
            image_url_changes,
            notes
        ))
        
        # Print summary
        logger.info(f"  ✅ {retailer}:")
        logger.info(f"     Sample size: {total:,}")
        logger.info(f"     URL stability: {url_stability:.1%}")
        logger.info(f"     URL changes: {url_changes:,}")
        logger.info(f"     Code changes: {code_changes:,}")
        logger.info(f"     Image consistency: {image_consistency:.1%}")
        logger.info(f"     Best method: {best_method}")
        logger.info(f"     Notes: {notes}\n")


if __name__ == '__main__':
    analyzer = URLStabilityAnalyzer()
    analyzer.analyze_all_retailers()
```

---

### Step 3.3: Create backfill_lifecycle_stages.py

**Location**: `Shared/backfill_lifecycle_stages.py`

**Purpose**: Set lifecycle_stage for existing products

```python
"""
Backfill Lifecycle Stages
Sets lifecycle_stage for existing products in products table
Run manually AFTER schema changes are applied
"""

import sqlite3
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LifecycleBackfiller:
    """Backfills lifecycle stages for existing products"""
    
    def __init__(self, db_path: str = 'Shared/products.db'):
        self.db_path = db_path
        self.stats = {
            'total_products': 0,
            'imported_direct': 0,
            'assessed_approved': 0,
            'assessed_rejected': 0,
            'pending_assessment': 0,
            'unknown': 0
        }
    
    def backfill_all(self):
        """Main backfill process"""
        logger.info("="*60)
        logger.info("🔄 STARTING LIFECYCLE BACKFILL")
        logger.info("="*60)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get all products without lifecycle_stage
        cursor.execute("""
            SELECT url, source, shopify_status, modesty_status, assessment_status
            FROM products
            WHERE lifecycle_stage IS NULL
        """)
        products = cursor.fetchall()
        self.stats['total_products'] = len(products)
        
        logger.info(f"\n📊 Found {len(products)} products to classify\n")
        
        for product in products:
            url, source, shopify_status, modesty_status, assessment_status = product
            
            # Determine lifecycle_stage
            lifecycle_stage = self._determine_lifecycle_stage(
                source, shopify_status, modesty_status, assessment_status
            )
            
            # Determine data_completeness
            data_completeness = 'full'  # All existing products have full data
            if shopify_status in ['published', 'draft']:
                data_completeness = 'enriched'  # Has Shopify data
            
            # Update product
            cursor.execute("""
                UPDATE products
                SET lifecycle_stage = ?,
                    data_completeness = ?
                WHERE url = ?
            """, (lifecycle_stage, data_completeness, url))
            
            # Track stats
            self.stats[lifecycle_stage] += 1
        
        conn.commit()
        conn.close()
        
        self._print_stats()
    
    def _determine_lifecycle_stage(
        self, 
        source: str, 
        shopify_status: str, 
        modesty_status: str,
        assessment_status: str
    ) -> str:
        """Determine lifecycle stage based on existing fields"""
        
        # Products from New Product Importer
        if source == 'new_product_import':
            return 'imported_direct'
        
        # Products published to Shopify (approved)
        if shopify_status == 'published':
            return 'assessed_approved'
        
        # Products kept as draft (rejected or pending)
        if shopify_status == 'draft':
            # Check if actually rejected
            if modesty_status == 'not_modest':
                return 'assessed_rejected'
            # Otherwise pending assessment
            return 'pending_assessment'
        
        # Products in assessment queue
        if assessment_status in ['queued', 'pending_modesty_review']:
            return 'pending_assessment'
        
        # Default: unknown
        return 'unknown'
    
    def _print_stats(self):
        """Print summary statistics"""
        total = self.stats['total_products']
        
        logger.info("\n" + "="*60)
        logger.info("📊 LIFECYCLE BACKFILL RESULTS")
        logger.info("="*60)
        logger.info(f"Total products: {total:,}")
        logger.info(f"\nBy Lifecycle Stage:")
        logger.info(f"  imported_direct: {self.stats['imported_direct']:,}")
        logger.info(f"  assessed_approved: {self.stats['assessed_approved']:,}")
        logger.info(f"  assessed_rejected: {self.stats['assessed_rejected']:,}")
        logger.info(f"  pending_assessment: {self.stats['pending_assessment']:,}")
        logger.info(f"  unknown: {self.stats['unknown']:,}")
        logger.info("="*60 + "\n")


if __name__ == '__main__':
    backfiller = LifecycleBackfiller()
    backfiller.backfill_all()
```

---

## 🧪 PART 4: VERIFICATION QUERIES

After implementation and backfill, run these queries to verify:

### Query 1: Linking Summary
```sql
SELECT 
    link_method,
    COUNT(*) as count,
    ROUND(AVG(link_confidence), 3) as avg_confidence,
    ROUND(MIN(link_confidence), 3) as min_confidence,
    ROUND(MAX(link_confidence), 3) as max_confidence
FROM catalog_products
WHERE linked_product_url IS NOT NULL
GROUP BY link_method
ORDER BY count DESC;
```

### Query 2: Retailer Stability Summary
```sql
SELECT 
    retailer,
    ROUND(url_stability_score, 3) as url_stability,
    product_code_stable,
    image_urls_consistent,
    best_dedup_method,
    sample_size,
    notes
FROM retailer_url_patterns
ORDER BY url_stability ASC;
```

### Query 3: Revolve Specific Analysis
```sql
SELECT 
    'URL Stability' as metric,
    ROUND(url_stability_score, 3) as value
FROM retailer_url_patterns WHERE retailer = 'revolve'
UNION ALL
SELECT 
    'URL Changes Detected',
    url_changes_detected
FROM retailer_url_patterns WHERE retailer = 'revolve'
UNION ALL
SELECT
    'Code Changes Detected',
    code_changes_detected
FROM retailer_url_patterns WHERE retailer = 'revolve'
UNION ALL
SELECT
    'Best Dedup Method',
    best_dedup_method
FROM retailer_url_patterns WHERE retailer = 'revolve';
```

### Query 4: Lifecycle Distribution
```sql
SELECT 
    lifecycle_stage,
    data_completeness,
    COUNT(*) as count
FROM products
GROUP BY lifecycle_stage, data_completeness
ORDER BY count DESC;
```

### Query 5: Price Change Queue
```sql
SELECT 
    retailer,
    priority,
    COUNT(*) as count,
    ROUND(AVG(ABS(price_difference)), 2) as avg_price_change
FROM product_update_queue
WHERE processed = 0
GROUP BY retailer, priority
ORDER BY priority DESC, count DESC;
```

### Query 6: Scan Type Distribution
```sql
SELECT 
    scan_type,
    retailer,
    COUNT(*) as count,
    DATE(MIN(discovered_date)) as first_scan,
    DATE(MAX(discovered_date)) as last_scan
FROM catalog_products
GROUP BY scan_type, retailer
ORDER BY retailer, scan_type;
```

---

## 📋 PART 5: EXECUTION CHECKLIST

Follow this order:

### Phase 1: Schema & Code Changes
- [ ] Run all SQL statements from Part 1 (schema changes)
- [ ] Modify catalog_monitor.py (Part 2.1)
- [ ] Modify catalog_baseline_scanner.py (Part 2.2)
- [ ] Modify submit_review.php (Part 2.3)
- [ ] Modify new_product_importer.py (Part 2.4)
- [ ] Modify db_manager.py (Part 2.5)
- [ ] Commit changes to GitHub

### Phase 2: Test New Code
- [ ] Run catalog_baseline_scanner for one small retailer
- [ ] Verify scan_type='baseline' in catalog_products
- [ ] Run catalog_monitor for same retailer
- [ ] Verify scan_type='monitor' entries created
- [ ] Check price_change_detection works
- [ ] Verify lifecycle_stage set correctly on new products

### Phase 3: Backfill Existing Data
- [ ] Create backfill_product_linking.py (Part 3.1)
- [ ] Create analyze_url_stability.py (Part 3.2)
- [ ] Create backfill_lifecycle_stages.py (Part 3.3)
- [ ] Run: `python3 Shared/backfill_product_linking.py`
- [ ] Run: `python3 Shared/analyze_url_stability.py`
- [ ] Run: `python3 Shared/backfill_lifecycle_stages.py`

### Phase 4: Verification
- [ ] Run all verification queries (Part 4)
- [ ] Check Revolve has low URL stability score
- [ ] Check linking worked (>80% linked)
- [ ] Check lifecycle stages distributed correctly
- [ ] Review price change queue

### Phase 5: Documentation
- [ ] Update SYSTEM_OVERVIEW.md with new tables
- [ ] Document lifecycle stages in relevant guides
- [ ] Update RETAILER_PLAYBOOK.md with stability findings
- [ ] Commit documentation updates

---

## 🎯 EXPECTED OUTCOMES

After full implementation:

1. **Cross-Table Linking**:
   - 80-95% of catalog_products linked to products table
   - Confidence scores accurately reflect match quality
   - Easy to query related products across tables

2. **URL Stability Tracking**:
   - Revolve identified as unstable (<50% stability)
   - System automatically uses fuzzy matching for Revolve
   - Other retailers use URL/code matching when stable

3. **Lifecycle Management**:
   - All products have clear lifecycle_stage
   - Easy to query products by stage
   - Workflow transitions tracked

4. **Price Change Detection**:
   - Automated flagging when catalog prices change
   - Priority queue for Product Updater
   - User can manually review and process changes

5. **Historical Snapshots**:
   - Complete history of catalog changes over time
   - Can track when products appeared/disappeared
   - Can analyze catalog evolution

6. **Image Consistency**:
   - Track which retailers have matching catalog/product images
   - Use as secondary confidence signal in deduplication
   - Learn patterns over time

---

## ⚠️ CRITICAL NOTES

1. **Run backfills AFTER schema changes**: Database must have new columns before backfill scripts run

2. **Catalog Monitor frequency**: Writing ALL products on EVERY run will grow catalog_products quickly. Plan for ~100-200 new entries per monitor run per retailer.

3. **Price change threshold**: Currently flags ANY price change. May want to add minimum threshold later ($5 or 10%).

4. **Image extraction**: Verify both towers (Markdown & Patchright) are extracting images from catalog pages.

5. **Lifecycle transitions**: Assessment interface must update lifecycle_stage when products are approved/rejected.

6. **Testing**: Test on one small retailer first before running on full system.

7. **Commit frequently**: Commit after each major change to allow rollback if needed.

---

## 🆘 TROUBLESHOOTING

### Issue: Backfill scripts fail with "column not found"
**Solution**: Run schema changes first (Part 1) before backfill scripts

### Issue: No products getting linked
**Solution**: Check that products table has data, verify URL formats match

### Issue: Revolve products not using fuzzy matching
**Solution**: Run analyze_url_stability.py to populate retailer_url_patterns table

### Issue: Lifecycle_stage always NULL on new products
**Solution**: Verify db_manager.save_product accepts new parameters and passes them to INSERT

### Issue: Catalog Monitor not writing snapshots
**Solution**: Verify _save_catalog_snapshot method is called after deduplication

### Issue: Price changes not detected
**Solution**: Check that products have accurate prices, verify price comparison logic

---

## 📚 DOCUMENTATION UPDATES NEEDED

After implementation, update these files:

1. **SYSTEM_OVERVIEW.md**: Add new tables, explain lifecycle stages
2. **CATALOG_MONITOR_GUIDE.md**: Document snapshot writing behavior
3. **PRODUCT_LIFECYCLE_MANAGEMENT.md**: Expand with implementation details
4. **RETAILER_PLAYBOOK.md**: Add URL stability findings per retailer
5. **DATABASE_SCHEMA.md**: Document all new fields and tables

---

## ✅ SUCCESS CRITERIA

Implementation is complete when:

- ✅ All schema changes applied without errors
- ✅ Catalog Monitor creates snapshot entries on every run
- ✅ Products have lifecycle_stage set correctly
- ✅ Backfill scripts run successfully
- ✅ Retailer URL patterns populated
- ✅ 80%+ catalog products linked to products table
- ✅ Price change detection working
- ✅ Revolve identified as unstable retailer
- ✅ All verification queries return expected results
- ✅ Documentation updated

---

**End of prompt. Good luck with implementation! 🚀**
