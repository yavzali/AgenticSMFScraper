# PHASE 6: BACKFILL & CONTINUOUS LEARNING

**Duration**: 30-40 minutes  
**Risk**: LOW (additive changes, non-breaking)  
**Prerequisites**: All previous phases completed successfully  
**Can rollback**: Yes (can re-run anytime)

---

## OBJECTIVE

Create continuous learning infrastructure and backfill existing data:
1. **Architecture**: Add Pattern Learning Manager (intelligence layer)
2. **Integration**: Connect catalog_monitor to pattern learning
3. **Backfill**: Link catalog_products to products table
4. **Backfill**: Set lifecycle_stage for existing products

**WHY LAST**: Needs all schema changes and workflows working first. Learning system enhances but doesn't break existing functionality.

---

## ARCHITECTURAL OVERVIEW

### Pattern Learning Manager
New specialized manager in `Shared/` (like cost_tracker, notification_manager, etc.):
- **Purpose**: Learn patterns from operational data
- **Scope**: URL stability, price trends, image consistency, seasonal patterns
- **Integration**: All workflows can contribute learning data
- **Safe**: System works with or without it (graceful degradation)

### Continuous Learning Flow
```
Catalog Monitor runs
  ↓
Links catalog → products
  ↓
Records linking attempt → Pattern Learning Manager
  ↓
Updates retailer_url_patterns table
  ↓
Next run uses learned patterns (smarter matching!)
```

---

## FILES TO CREATE

### Part A: Architecture
1. `Shared/pattern_learning_manager.py` - Intelligence layer

### Part B: Backfill Scripts
2. `Shared/backfill_product_linking.py` - Link existing data + seed patterns
3. `Shared/backfill_lifecycle_stages.py` - Set lifecycle stages

### Part C: Integration
4. Update `Workflows/catalog_monitor.py` - Use pattern learning

---

## PART A: PATTERN LEARNING MANAGER

### File: `Shared/pattern_learning_manager.py`

**Copy this complete script**:

```python
"""
Pattern Learning Manager
Learns patterns from operational data to improve system intelligence

This is the learning/intelligence layer of the system, separate from operations.
Tracks URL stability, price patterns, image consistency, etc.
"""

import sqlite3
import os
from typing import Dict, Optional, Tuple
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class PatternLearningManager:
    """
    Learns patterns from operational data
    Updates retailer_url_patterns and future learning tables
    """
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.path.join(os.path.dirname(__file__), 'products.db')
        self.db_path = db_path
    
    def _get_connection(self):
        """Get database connection"""
        return sqlite3.connect(self.db_path)
    
    async def record_linking_attempt(
        self,
        retailer: str,
        method: str,
        success: bool,
        confidence: float = 0.0,
        url_changed: bool = False
    ):
        """
        Record a linking attempt to learn URL patterns
        
        Args:
            retailer: Retailer name
            method: Method used (exact_url, normalized_url, product_code, etc.)
            success: Whether link was successful (confidence >= 0.85)
            confidence: Link confidence score
            url_changed: Whether URL differed from normalized form
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Get current stats
            cursor.execute("""
                SELECT 
                    sample_size,
                    url_stability_score,
                    url_changes_detected,
                    best_dedup_method,
                    dedup_confidence_threshold
                FROM retailer_url_patterns
                WHERE retailer = ?
            """, (retailer,))
            
            result = cursor.fetchone()
            
            if result:
                # Update existing
                sample_size, url_stability, url_changes, best_method, threshold = result
                
                # Increment counters
                new_sample_size = sample_size + 1
                new_url_changes = url_changes + (1 if url_changed else 0)
                
                # Recalculate URL stability
                new_url_stability = 1.0 - (new_url_changes / new_sample_size)
                
                # Track method success (simplified - could be more sophisticated)
                # If this method succeeded, consider it
                if success and confidence > threshold:
                    best_method = method
                    threshold = confidence
                
                cursor.execute("""
                    UPDATE retailer_url_patterns
                    SET sample_size = ?,
                        url_stability_score = ?,
                        url_changes_detected = ?,
                        best_dedup_method = ?,
                        dedup_confidence_threshold = ?,
                        last_measured = ?
                    WHERE retailer = ?
                """, (
                    new_sample_size,
                    new_url_stability,
                    new_url_changes,
                    best_method,
                    threshold,
                    datetime.now().isoformat(),
                    retailer
                ))
                
                logger.debug(f"Updated {retailer} patterns: stability={new_url_stability:.2f}, method={best_method}")
            else:
                # Initialize new retailer
                cursor.execute("""
                    INSERT INTO retailer_url_patterns
                    (retailer, url_stability_score, last_measured, sample_size,
                     product_code_stable, path_stable, image_urls_consistent,
                     best_dedup_method, dedup_confidence_threshold,
                     url_changes_detected, code_changes_detected, image_url_changes_detected,
                     notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    retailer,
                    1.0 if not url_changed else 0.0,
                    datetime.now().isoformat(),
                    1,
                    1,  # Assume stable initially
                    1 if not url_changed else 0,
                    1,  # Assume consistent initially
                    method,
                    confidence,
                    1 if url_changed else 0,
                    0,
                    0,
                    f"Initialized from first linking attempt using {method}"
                ))
                
                logger.info(f"Initialized {retailer} patterns with method={method}")
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to record linking attempt: {e}")
            # Don't raise - learning is non-critical
    
    async def get_best_dedup_method(self, retailer: str) -> Optional[Tuple[str, float]]:
        """
        Get best deduplication method for retailer based on learned patterns
        
        Returns:
            (method_name, confidence_threshold) or None if no data
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT best_dedup_method, dedup_confidence_threshold, url_stability_score
                FROM retailer_url_patterns
                WHERE retailer = ?
            """, (retailer,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                method, threshold, stability = result
                logger.debug(f"{retailer}: best_method={method}, stability={stability:.2f}")
                return (method, threshold, stability)
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get best dedup method: {e}")
            return None
    
    async def get_retailer_stats(self, retailer: str) -> Optional[Dict]:
        """Get all learned stats for a retailer"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM retailer_url_patterns WHERE retailer = ?", (retailer,))
            result = cursor.fetchone()
            
            if result:
                columns = [desc[0] for desc in cursor.description]
                stats = dict(zip(columns, result))
                conn.close()
                return stats
            
            conn.close()
            return None
            
        except Exception as e:
            logger.error(f"Failed to get retailer stats: {e}")
            return None
    
    # Future expansion methods (stubs for now)
    
    async def record_price_change(self, retailer: str, old_price: float, new_price: float):
        """Record price change for pattern learning (future)"""
        # TODO: Track price volatility, seasonal patterns
        pass
    
    async def record_image_consistency(self, retailer: str, images_changed: bool):
        """Record image URL consistency (future)"""
        # TODO: Track how often image URLs change
        pass


# Singleton instance
_pattern_learning_manager = None

def get_pattern_learning_manager(db_path: str = None) -> PatternLearningManager:
    """Get or create singleton pattern learning manager"""
    global _pattern_learning_manager
    if _pattern_learning_manager is None:
        _pattern_learning_manager = PatternLearningManager(db_path)
    return _pattern_learning_manager
```

---

## PART B: BACKFILL SCRIPT 1 - PRODUCT LINKING

### File: `Shared/backfill_product_linking.py`

**Copy this complete script**:

```python
"""
Backfill Product Linking
Links existing catalog_products entries to products table entries
Also initializes retailer_url_patterns with baseline data

Run manually AFTER schema changes are applied
"""

import asyncio
import sqlite3
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from difflib import SequenceMatcher
import logging
import json

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
        self.retailer_stats = {}  # Track per-retailer patterns
    
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
        
        # Initialize retailer stats tracking
        cursor.execute("SELECT DISTINCT retailer FROM catalog_products")
        retailers = [r[0] for r in cursor.fetchall()]
        for retailer in retailers:
            self.retailer_stats[retailer] = {
                'total': 0,
                'linked': 0,
                'url_changes': 0,
                'method_counts': {},
                'confidences': []
            }
        
        # Process each one
        processed = 0
        for cp in catalog_products:
            cp_id, catalog_url, retailer, title, price, product_code, image_urls = cp
            
            match = await self._find_matching_product(
                cursor, catalog_url, retailer, title, price, product_code, image_urls
            )
            
            # Track retailer stats
            self.retailer_stats[retailer]['total'] += 1
            
            if match:
                product_url, confidence, method = match
                
                # Track method usage
                self.retailer_stats[retailer]['method_counts'][method] = \
                    self.retailer_stats[retailer]['method_counts'].get(method, 0) + 1
                self.retailer_stats[retailer]['confidences'].append(confidence)
                
                # Track URL changes
                normalized_catalog = catalog_url.split('?')[0].rstrip('/')
                normalized_product = product_url.split('?')[0].rstrip('/')
                if normalized_catalog != normalized_product:
                    self.retailer_stats[retailer]['url_changes'] += 1
                
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
                    self.retailer_stats[retailer]['linked'] += 1
                    
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
        
        # Initialize retailer_url_patterns table with learned data
        await self._initialize_retailer_patterns(cursor)
        
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
        
        # Check if this retailer prefers fuzzy matching (would be empty initially)
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
    
    async def _initialize_retailer_patterns(self, cursor):
        """Initialize retailer_url_patterns table with backfill data"""
        logger.info("\n" + "="*60)
        logger.info("🌱 INITIALIZING RETAILER PATTERNS")
        logger.info("="*60)
        
        for retailer, stats in self.retailer_stats.items():
            if stats['linked'] == 0:
                logger.warning(f"⚠️  {retailer}: No linked products, skipping")
                continue
            
            # Calculate metrics
            total = stats['total']
            linked = stats['linked']
            url_changes = stats['url_changes']
            
            url_stability = 1.0 - (url_changes / linked) if linked > 0 else 1.0
            path_stable = 1 if url_stability > 0.80 else 0
            
            # Determine best method
            if stats['method_counts']:
                best_method = max(stats['method_counts'].items(), key=lambda x: x[1])[0]
            else:
                best_method = 'url'
            
            # Calculate average confidence
            avg_confidence = sum(stats['confidences']) / len(stats['confidences']) if stats['confidences'] else 0.85
            
            # Generate notes
            notes = (
                f"Initialized from backfill: {linked} products linked "
                f"({linked/total*100:.1f}% success rate). "
                f"URL stability: {url_stability:.1%}. "
                f"Primary method: {best_method}."
            )
            
            # Insert into retailer_url_patterns
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
                linked,
                1,  # Will learn over time
                path_stable,
                1,  # Will learn over time
                best_method,
                avg_confidence,
                url_changes,
                0,  # Will learn over time
                0,  # Will learn over time
                notes
            ))
            
            logger.info(f"✅ {retailer}:")
            logger.info(f"   Linked: {linked:,}/{total:,} ({linked/total*100:.1f}%)")
            logger.info(f"   URL stability: {url_stability:.1%}")
            logger.info(f"   URL changes: {url_changes:,}")
            logger.info(f"   Best method: {best_method}")
            logger.info(f"   Method breakdown: {stats['method_counts']}")
    
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

## PART B: BACKFILL SCRIPT 2 - LIFECYCLE STAGES

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

## PART C: CATALOG MONITOR INTEGRATION

### File: `Workflows/catalog_monitor.py`

**Add these imports at the top**:

```python
# Add to existing imports
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../Shared"))

# Add after other Shared imports
try:
    from pattern_learning_manager import get_pattern_learning_manager
    PATTERN_LEARNING_AVAILABLE = True
except ImportError:
    PATTERN_LEARNING_AVAILABLE = False
    logger.warning("⚠️ Pattern learning manager not available - will use defaults")
```

**In `__init__` method** (around line 150):

```python
def __init__(self):
    self.db_manager = DatabaseManager()
    self.notification_manager = NotificationManager()
    self.assessment_queue = AssessmentQueueManager()
    
    # Initialize pattern learning (optional, non-critical)
    self.pattern_learner = None
    if PATTERN_LEARNING_AVAILABLE:
        try:
            self.pattern_learner = get_pattern_learning_manager()
            logger.info("✅ Pattern learning enabled")
        except Exception as e:
            logger.warning(f"⚠️ Pattern learning initialization failed: {e}")
    
    # Initialize towers
    # ... rest of init
```

**In `_save_catalog_snapshot` method** (after saving snapshot, around line 216):

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
    ... existing docstring ...
    """
    logger.info(f"📸 Saving catalog snapshot: {len(catalog_products)} products")
    
    conn = self.db_manager._get_connection()
    cursor = conn.cursor()
    
    saved = 0
    for product in catalog_products:
        # ... existing save logic ...
        saved += 1
    
    conn.commit()
    conn.close()
    
    logger.info(f"✅ Catalog snapshot saved: {saved}/{len(catalog_products)} products")
    
    # NEW: Learn from linking attempts if available
    if self.pattern_learner:
        try:
            # Get linked products from this snapshot
            conn = self.db_manager._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT linked_product_url, link_method, link_confidence, catalog_url
                FROM catalog_products
                WHERE retailer = ?
                AND discovered_date >= datetime('now', '-1 hour')
                AND linked_product_url IS NOT NULL
            """, (retailer,))
            
            linked_products = cursor.fetchall()
            conn.close()
            
            # Record each linking attempt for learning
            for linked_url, method, confidence, catalog_url in linked_products:
                # Check if URL changed
                normalized_catalog = catalog_url.split('?')[0].rstrip('/')
                normalized_linked = linked_url.split('?')[0].rstrip('/')
                url_changed = (normalized_catalog != normalized_linked)
                
                await self.pattern_learner.record_linking_attempt(
                    retailer=retailer,
                    method=method,
                    success=True,  # It was linked
                    confidence=confidence,
                    url_changed=url_changed
                )
            
            if linked_products:
                logger.debug(f"📚 Recorded {len(linked_products)} linking attempts for pattern learning")
                
        except Exception as e:
            logger.warning(f"⚠️ Pattern learning failed (non-critical): {e}")
```

---

## EXECUTION

Run in order:

```bash
cd "/Users/yav/Agent Modest Scraper System"

# Step 1: Create pattern learning manager
# (Copy file from Part A above)
# System continues working normally ✅

# Step 2: Run linking backfill (also initializes patterns)
python3 Shared/backfill_product_linking.py

# Step 3: Run lifecycle backfill
python3 Shared/backfill_lifecycle_stages.py

# Step 4: Integrate catalog_monitor (optional updates from Part C)
# System now learns continuously ✅
```

---

## VERIFICATION QUERIES

After all steps complete:

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

-- 2. Retailer patterns initialized
SELECT 
    retailer,
    ROUND(url_stability_score, 3) as url_stability,
    best_dedup_method,
    sample_size
FROM retailer_url_patterns
ORDER BY sample_size DESC;

-- 3. Revolve specific (should show low URL stability)
SELECT 
    retailer,
    url_stability_score,
    best_dedup_method,
    sample_size,
    url_changes_detected,
    notes
FROM retailer_url_patterns 
WHERE retailer = 'revolve';

-- 4. Lifecycle distribution
SELECT 
    lifecycle_stage,
    COUNT(*) as count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM products), 1) as percentage
FROM products
GROUP BY lifecycle_stage
ORDER BY count DESC;

-- 5. Data completeness check
SELECT 
    lifecycle_stage,
    data_completeness,
    COUNT(*) as count
FROM products
WHERE lifecycle_stage IS NOT NULL
GROUP BY lifecycle_stage, data_completeness;
```

---

## SUCCESS CRITERIA

✅ Pattern learning manager created (architecture enhanced)  
✅ 80-95% of catalog_products linked  
✅ retailer_url_patterns populated with baseline data  
✅ Revolve shows appropriate URL stability based on data  
✅ All products have lifecycle_stage set  
✅ Catalog monitor optionally uses pattern learning  
✅ System works with or without pattern learning (graceful)  
✅ No breaking changes to existing functionality

---

## COMMIT

After successful verification:

```bash
git add Shared/pattern_learning_manager.py
git add Shared/backfill_product_linking.py
git add Shared/backfill_lifecycle_stages.py
git add Workflows/catalog_monitor.py
git commit -m "Phase 6: Add pattern learning architecture and backfill scripts"
```

---

## BENEFITS

### Immediate
1. ✅ Historical data linked
2. ✅ Lifecycle stages populated
3. ✅ Retailer patterns initialized

### Ongoing (Continuous Learning)
1. ✅ System learns from every linking attempt
2. ✅ Adapts to retailer URL pattern changes
3. ✅ Improves matching accuracy over time
4. ✅ Foundation for future ML features

### Architecture
1. ✅ Clean separation: Intelligence layer in Shared/
2. ✅ Non-breaking: Works with or without pattern learning
3. ✅ Extensible: Easy to add price/image/seasonal patterns
4. ✅ Reusable: All workflows can use pattern learning

---

## 🎉 PHASE 6 COMPLETE

If all steps completed successfully:
- ✅ Pattern learning architecture added
- ✅ Backfill completed (linking + lifecycle)
- ✅ Continuous learning integrated
- ✅ System validated

**Result**: Self-improving system that learns from operational data!

**Next**: Monitor system in production, observe pattern learning in action.
