# PHASE 6: BACKFILL EXISTING DATA

**Duration**: 20-30 minutes  
**Risk**: LOW (only analyzes and updates existing data)  
**Prerequisites**: All previous phases completed successfully  
**Can rollback**: Yes (can re-run anytime)

---

## OBJECTIVE

Analyze existing database and populate new fields:
1. Link catalog_products to products table
2. Analyze URL stability per retailer
3. Set lifecycle_stage for existing products

**WHY LAST**: Needs all schema changes and workflows working first. Safe to run multiple times.

---

## FILES TO CREATE

1. `Shared/backfill_product_linking.py`
2. `Shared/analyze_url_stability.py`
3. `Shared/backfill_lifecycle_stages.py`

---

## SCRIPT 1: PRODUCT LINKING

### File: `Shared/backfill_product_linking.py`

**Copy this complete script**:

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

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
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
        
        logger.info(f"\n📊 Found {len(catalog_products):,} catalog products to link\n")
        
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
                logger.info(f"⏳ Processed {processed:,}/{len(catalog_products):,} ({processed/len(catalog_products)*100:.1f}%)")
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

## SCRIPT 2: URL STABILITY ANALYSIS

### File: `Shared/analyze_url_stability.py`

**Copy this complete script**:

```python
"""
Analyze URL Stability Per Retailer
Populates retailer_url_patterns table based on actual linking results
Run manually AFTER backfill_product_linking.py completes
"""

import sqlite3
from datetime import datetime
import logging
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
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
                try:
                    # Parse JSON arrays
                    cp_set = set(json.loads(cp_images)) if cp_images and cp_images != '[]' else set()
                    p_set = set(json.loads(p_images)) if p_images and p_images != '[]' else set()
                    
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

## SCRIPT 3: LIFECYCLE BACKFILL

### File: `Shared/backfill_lifecycle_stages.py`

**Copy this complete script**:

```python
"""
Backfill Lifecycle Stages
Sets lifecycle_stage for existing products in products table
Run manually AFTER schema changes are applied
"""

import sqlite3
from datetime import datetime
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
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
        
        logger.info(f"\n📊 Found {len(products):,} products to classify\n")
        
        processed = 0
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
            
            processed += 1
            if processed % 100 == 0:
                logger.info(f"⏳ Processed {processed:,}/{len(products):,} ({processed/len(products)*100:.1f}%)")
                conn.commit()
        
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

## EXECUTION

Run scripts in order:

```bash
cd "/Users/yav/Agent Modest Scraper System"

# Script 1: Link catalog to products
python3 Shared/backfill_product_linking.py

# Script 2: Analyze URL stability
python3 Shared/analyze_url_stability.py

# Script 3: Set lifecycle stages
python3 Shared/backfill_lifecycle_stages.py
```

---

## VERIFICATION QUERIES

After all scripts complete:

```sql
-- 1. Linking summary
SELECT 
    link_method,
    COUNT(*) as count,
    ROUND(AVG(link_confidence), 3) as avg_confidence
FROM catalog_products
WHERE linked_product_url IS NOT NULL
GROUP BY link_method
ORDER BY count DESC;

-- 2. Retailer stability (focus on Revolve)
SELECT 
    retailer,
    ROUND(url_stability_score, 3) as url_stability,
    best_dedup_method,
    sample_size
FROM retailer_url_patterns
ORDER BY url_stability ASC;

-- 3. Revolve specific
SELECT * FROM retailer_url_patterns WHERE retailer = 'revolve';

-- 4. Lifecycle distribution
SELECT 
    lifecycle_stage,
    COUNT(*) as count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM products), 1) as percentage
FROM products
GROUP BY lifecycle_stage
ORDER BY count DESC;

-- 5. Data completeness
SELECT 
    lifecycle_stage,
    data_completeness,
    COUNT(*) as count
FROM products
WHERE lifecycle_stage IS NOT NULL
GROUP BY lifecycle_stage, data_completeness;
```

---

## SHOW ME

After execution, show me:
1. ✅ Output from Script 1 (linking stats by method and retailer)
2. ✅ Output from Script 2 (stability scores, especially Revolve)
3. ✅ Output from Script 3 (lifecycle distribution)
4. ✅ Results of all 5 verification queries
5. ✅ Any errors or warnings

---

## SUCCESS CRITERIA

✅ 80-95% of catalog_products linked  
✅ Revolve shows low URL stability (<0.50)  
✅ Revolve best_dedup_method = 'fuzzy_title_price'  
✅ All products have lifecycle_stage set  
✅ Lifecycle distribution makes sense  
✅ No errors during execution

---

## IF ERRORS OCCUR

**Error: "no such table: retailer_url_patterns"**  
- Phase 1 not completed
- Run schema changes first

**Error: "no such column: linked_product_url"**  
- Phase 1 not completed
- Check catalog_products schema

**Error: Import errors**  
- Make sure scripts are in Shared/ directory
- Check Python path

---

## COMMIT

After successful verification:
```bash
git add Shared/backfill_product_linking.py
git add Shared/analyze_url_stability.py
git add Shared/backfill_lifecycle_stages.py
git commit -m "Phase 6: Add backfill scripts for lifecycle system"
```

---

## FINAL VALIDATION

Run complete system test:

```bash
# Test baseline scan
python3 -m Workflows.catalog_baseline_scanner mango dresses modest

# Test monitor scan
python3 -m Workflows.catalog_monitor mango dresses modest --max-pages 1

# Check everything working
python3 -c "
import sqlite3
conn = sqlite3.connect('Shared/products.db')
c = conn.cursor()

# Check scan_type distribution
c.execute('SELECT scan_type, COUNT(*) FROM catalog_products GROUP BY scan_type')
print('Scan types:', c.fetchall())

# Check retailer patterns
c.execute('SELECT COUNT(*) FROM retailer_url_patterns')
print('Retailers analyzed:', c.fetchone()[0])

# Check lifecycle distribution
c.execute('SELECT lifecycle_stage, COUNT(*) FROM products WHERE lifecycle_stage IS NOT NULL GROUP BY lifecycle_stage')
print('Lifecycle stages:', c.fetchall())

conn.close()
"
```

---

## 🎉 IMPLEMENTATION COMPLETE

If all phases completed successfully:
- ✅ Schema changes applied
- ✅ All workflows updated
- ✅ Assessment interface working
- ✅ Backfill completed
- ✅ System validated

**Next**: Update documentation and monitor system in production.
