"""
Updated Pattern Learner - Multi-Function Pattern Learning with Cross-Learning
Supports catalog crawling, individual extraction, and product update patterns
"""

import sqlite3
import asyncio
import json
import time
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import os

from logger_config import setup_logging

logger = setup_logging(__name__)

class PatternType(Enum):
    """Types of patterns the system can learn"""
    CATALOG_CRAWLING = "catalog_crawling"
    INDIVIDUAL_EXTRACTION = "individual_extraction"
    PRODUCT_UPDATES = "product_updates"

@dataclass
class PatternData:
    """Individual pattern data structure"""
    pattern_id: str
    pattern_type: PatternType
    retailer: str
    pattern_category: str  # e.g., 'pagination_detection', 'title_selectors', 'price_change_patterns'
    pattern_data: Dict[str, Any]
    success_count: int = 0
    failure_count: int = 0
    last_used: Optional[datetime] = None
    confidence_score: float = 0.0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class EnhancedPatternLearner:
    """
    Enhanced Pattern Learner supporting multiple pattern types with cross-learning
    Distinguishes between catalog crawling, individual extraction, and product update patterns
    """
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(script_dir, 'patterns.db')
        self.db_path = db_path
        
        # Pattern category definitions
        self.PATTERN_CATEGORIES = {
            PatternType.CATALOG_CRAWLING: {
                'pagination_detection',
                'load_more_buttons', 
                'infinite_scroll_triggers',
                'product_grid_selectors',
                'anti_bot_patterns',
                'sort_by_newest_detection',
                'catalog_page_structure',
                'product_count_detection',
                'next_page_indicators'
            },
            PatternType.INDIVIDUAL_EXTRACTION: {
                'title_selectors',
                'price_selectors', 
                'image_selectors',
                'description_patterns',
                'size_variant_detection',
                'color_variant_detection',
                'availability_indicators',
                'sale_badge_detection',
                'brand_extraction',
                'product_code_patterns'
            },
            PatternType.PRODUCT_UPDATES: {
                'price_change_patterns',
                'stock_status_indicators',
                'sale_status_patterns', 
                'title_update_detection',
                'image_update_patterns',
                'variant_availability_changes',
                'discontinued_indicators',
                'back_in_stock_patterns'
            }
        }
        
        # Cross-learning opportunities
        self.CROSS_LEARNING_PATTERNS = {
            # Anti-bot patterns learned from catalog crawling help individual extraction
            ('catalog_crawling', 'anti_bot_patterns'): [
                ('individual_extraction', 'anti_bot_patterns'),
                ('product_updates', 'anti_bot_patterns')
            ],
            # Price selectors learned from individual extraction help catalog and updates
            ('individual_extraction', 'price_selectors'): [
                ('catalog_crawling', 'price_detection'),
                ('product_updates', 'price_change_patterns')
            ],
            # Stock indicators learned from updates help catalog and individual extraction
            ('product_updates', 'stock_status_indicators'): [
                ('catalog_crawling', 'availability_detection'),
                ('individual_extraction', 'availability_indicators')
            ]
        }
        
        self._init_database()
        logger.info("✅ Enhanced pattern learner initialized with multi-function support")
    
    def _init_database(self):
        """Initialize enhanced pattern learning database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create enhanced patterns table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS enhanced_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern_id VARCHAR(100) UNIQUE NOT NULL,
                    pattern_type VARCHAR(50) NOT NULL,
                    retailer VARCHAR(100) NOT NULL,
                    pattern_category VARCHAR(100) NOT NULL,
                    pattern_data TEXT NOT NULL,
                    success_count INTEGER DEFAULT 0,
                    failure_count INTEGER DEFAULT 0,
                    confidence_score DECIMAL(3,2) DEFAULT 0.0,
                    last_used TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create cross-learning patterns table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cross_learning_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_pattern_id VARCHAR(100) NOT NULL,
                    target_pattern_type VARCHAR(50) NOT NULL,
                    target_pattern_category VARCHAR(100) NOT NULL,
                    retailer VARCHAR(100) NOT NULL,
                    learned_data TEXT NOT NULL,
                    confidence_transfer_score DECIMAL(3,2) DEFAULT 0.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (source_pattern_id) REFERENCES enhanced_patterns(pattern_id)
                )
            """)
            
            # Create pattern usage statistics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pattern_usage_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern_id VARCHAR(100) NOT NULL,
                    usage_context VARCHAR(100) NOT NULL,
                    success BOOLEAN NOT NULL,
                    processing_time DECIMAL(8,2),
                    error_details TEXT,
                    used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (pattern_id) REFERENCES enhanced_patterns(pattern_id)
                )
            """)
            
            # Create indexes for performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_patterns_type_retailer ON enhanced_patterns(pattern_type, retailer)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_patterns_category ON enhanced_patterns(pattern_category)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cross_learning_source ON cross_learning_patterns(source_pattern_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_usage_stats_pattern ON pattern_usage_stats(pattern_id)")
            
            conn.commit()
            conn.close()
            
            logger.info("Enhanced pattern learning database initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize pattern database: {e}")
            raise
    
    # =================== MAIN PATTERN LEARNING INTERFACE ===================
    
    async def get_learned_patterns(self, retailer: str, url: str = None, 
                                 pattern_type: PatternType = None) -> Dict[str, Any]:
        """
        Get learned patterns for retailer, optionally filtered by type
        Includes cross-learned patterns from other pattern types
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Build query based on parameters
            if pattern_type:
                query = """
                    SELECT pattern_category, pattern_data, confidence_score, last_used
                    FROM enhanced_patterns 
                    WHERE retailer = ? AND pattern_type = ? AND confidence_score > 0.3
                    ORDER BY confidence_score DESC, last_used DESC
                """
                cursor.execute(query, (retailer, pattern_type.value))
            else:
                query = """
                    SELECT pattern_type, pattern_category, pattern_data, confidence_score, last_used
                    FROM enhanced_patterns 
                    WHERE retailer = ? AND confidence_score > 0.3
                    ORDER BY pattern_type, confidence_score DESC, last_used DESC
                """
                cursor.execute(query, (retailer,))
            
            patterns = cursor.fetchall()
            
            # Get cross-learned patterns
            cross_patterns = await self._get_cross_learned_patterns(cursor, retailer, pattern_type)
            
            conn.close()
            
            # Organize patterns
            organized_patterns = self._organize_patterns(patterns, cross_patterns, pattern_type)
            
            logger.debug(f"Retrieved {len(patterns)} patterns + {len(cross_patterns)} cross-learned for {retailer}")
            return organized_patterns
            
        except Exception as e:
            logger.error(f"Error getting learned patterns for {retailer}: {e}")
            return {}
    
    async def record_success(self, retailer: str, url: str, pattern_context: str,
                           processing_time: float, extraction_metadata: Dict[str, Any],
                           pattern_type: PatternType = None):
        """
        Record successful pattern usage and extract learnable patterns
        """
        try:
            # Infer pattern type from context if not provided
            if not pattern_type:
                pattern_type = self._infer_pattern_type(pattern_context)
            
            # Extract patterns from successful operation
            patterns = self._extract_patterns_from_success(
                retailer, url, pattern_context, extraction_metadata, pattern_type)
            
            # Store patterns and update statistics
            await self._store_learned_patterns(patterns)
            await self._record_usage_stats(patterns, True, processing_time, pattern_context)
            
            # Check for cross-learning opportunities
            await self._apply_cross_learning(patterns)
            
            logger.debug(f"Recorded success for {retailer} - {pattern_context} ({len(patterns)} patterns)")
            
        except Exception as e:
            logger.error(f"Error recording success for {retailer}: {e}")
    
    async def record_failure(self, retailer: str, url: str, pattern_context: str, 
                           error_details: str, pattern_type: PatternType = None):
        """
        Record pattern failure and adjust confidence scores
        """
        try:
            # Infer pattern type from context if not provided
            if not pattern_type:
                pattern_type = self._infer_pattern_type(pattern_context)
            
            # Update failure counts for related patterns
            await self._update_pattern_failures(retailer, pattern_type, pattern_context)
            
            # Record usage statistics
            await self._record_usage_stats([], False, None, pattern_context, error_details)
            
            logger.debug(f"Recorded failure for {retailer} - {pattern_context}")
            
        except Exception as e:
            logger.error(f"Error recording failure for {retailer}: {e}")
    
    # =================== PATTERN TYPE SPECIFIC METHODS ===================
    
    async def get_catalog_crawling_patterns(self, retailer: str) -> Dict[str, Any]:
        """Get patterns specific to catalog crawling"""
        return await self.get_learned_patterns(retailer, pattern_type=PatternType.CATALOG_CRAWLING)
    
    async def get_individual_extraction_patterns(self, retailer: str) -> Dict[str, Any]:
        """Get patterns specific to individual product extraction"""
        return await self.get_learned_patterns(retailer, pattern_type=PatternType.INDIVIDUAL_EXTRACTION)
    
    async def get_product_update_patterns(self, retailer: str) -> Dict[str, Any]:
        """Get patterns specific to product updates"""
        return await self.get_learned_patterns(retailer, pattern_type=PatternType.PRODUCT_UPDATES)
    
    async def record_catalog_crawling_success(self, retailer: str, url: str, crawl_metadata: Dict):
        """Record successful catalog crawling with specific pattern extraction"""
        await self.record_success(
            retailer, url, 'catalog_crawling', 
            crawl_metadata.get('processing_time', 0.0),
            crawl_metadata,
            PatternType.CATALOG_CRAWLING
        )
    
    async def record_extraction_success(self, retailer: str, url: str, extraction_metadata: Dict):
        """Record successful individual product extraction"""
        await self.record_success(
            retailer, url, 'individual_extraction',
            extraction_metadata.get('processing_time', 0.0),
            extraction_metadata,
            PatternType.INDIVIDUAL_EXTRACTION
        )
    
    async def record_update_success(self, retailer: str, url: str, update_metadata: Dict):
        """Record successful product update"""
        await self.record_success(
            retailer, url, 'product_update',
            update_metadata.get('processing_time', 0.0),
            update_metadata,
            PatternType.PRODUCT_UPDATES
        )
    
    # =================== PATTERN EXTRACTION LOGIC ===================
    
    def _extract_patterns_from_success(self, retailer: str, url: str, context: str,
                                     metadata: Dict, pattern_type: PatternType) -> List[PatternData]:
        """Extract learnable patterns from successful operations"""
        patterns = []
        
        try:
            if pattern_type == PatternType.CATALOG_CRAWLING:
                patterns.extend(self._extract_catalog_patterns(retailer, url, metadata))
            elif pattern_type == PatternType.INDIVIDUAL_EXTRACTION:
                patterns.extend(self._extract_extraction_patterns(retailer, url, metadata))
            elif pattern_type == PatternType.PRODUCT_UPDATES:
                patterns.extend(self._extract_update_patterns(retailer, url, metadata))
            
            return patterns
            
        except Exception as e:
            logger.warning(f"Error extracting patterns from success: {e}")
            return []
    
    def _extract_catalog_patterns(self, retailer: str, url: str, metadata: Dict) -> List[PatternData]:
        """Extract catalog crawling specific patterns"""
        patterns = []
        
        try:
            # Pagination detection patterns
            if 'pagination_type' in metadata:
                pattern = PatternData(
                    pattern_id=f"{retailer}_pagination_{int(time.time())}",
                    pattern_type=PatternType.CATALOG_CRAWLING,
                    retailer=retailer,
                    pattern_category='pagination_detection',
                    pattern_data={
                        'pagination_type': metadata['pagination_type'],
                        'items_per_page': metadata.get('items_per_page'),
                        'page_parameter': metadata.get('page_parameter'),
                        'url_pattern': url
                    },
                    success_count=1,
                    confidence_score=0.7,
                    created_at=datetime.utcnow()
                )
                patterns.append(pattern)
            
            # Product grid detection patterns
            if 'total_products_found' in metadata:
                pattern = PatternData(
                    pattern_id=f"{retailer}_grid_{int(time.time())}",
                    pattern_type=PatternType.CATALOG_CRAWLING,
                    retailer=retailer,
                    pattern_category='product_grid_selectors',
                    pattern_data={
                        'products_found': metadata['total_products_found'],
                        'extraction_method': metadata.get('extraction_method'),
                        'success_rate': 1.0
                    },
                    success_count=1,
                    confidence_score=0.8,
                    created_at=datetime.utcnow()
                )
                patterns.append(pattern)
            
            # Anti-bot pattern detection
            if 'anti_bot_encountered' in metadata:
                pattern = PatternData(
                    pattern_id=f"{retailer}_antibot_{int(time.time())}",
                    pattern_type=PatternType.CATALOG_CRAWLING,
                    retailer=retailer,
                    pattern_category='anti_bot_patterns',
                    pattern_data={
                        'verification_type': metadata.get('verification_type'),
                        'bypass_method': metadata.get('bypass_method'),
                        'success': metadata.get('anti_bot_success', False)
                    },
                    success_count=1 if metadata.get('anti_bot_success') else 0,
                    failure_count=0 if metadata.get('anti_bot_success') else 1,
                    confidence_score=0.9 if metadata.get('anti_bot_success') else 0.3,
                    created_at=datetime.utcnow()
                )
                patterns.append(pattern)
            
            return patterns
            
        except Exception as e:
            logger.warning(f"Error extracting catalog patterns: {e}")
            return []
    
    def _extract_extraction_patterns(self, retailer: str, url: str, metadata: Dict) -> List[PatternData]:
        """Extract individual product extraction patterns"""
        patterns = []
        
        try:
            # Title extraction patterns
            if 'title_selector' in metadata:
                pattern = PatternData(
                    pattern_id=f"{retailer}_title_{int(time.time())}",
                    pattern_type=PatternType.INDIVIDUAL_EXTRACTION,
                    retailer=retailer,
                    pattern_category='title_selectors',
                    pattern_data={
                        'selector': metadata['title_selector'],
                        'extraction_method': metadata.get('extraction_method'),
                        'success_rate': 1.0
                    },
                    success_count=1,
                    confidence_score=0.8,
                    created_at=datetime.utcnow()
                )
                patterns.append(pattern)
            
            # Price extraction patterns
            if 'price_selector' in metadata:
                pattern = PatternData(
                    pattern_id=f"{retailer}_price_{int(time.time())}",
                    pattern_type=PatternType.INDIVIDUAL_EXTRACTION,
                    retailer=retailer,
                    pattern_category='price_selectors',
                    pattern_data={
                        'selector': metadata['price_selector'],
                        'price_format': metadata.get('price_format'),
                        'currency_symbol': metadata.get('currency_symbol')
                    },
                    success_count=1,
                    confidence_score=0.9,  # Price patterns are highly reliable
                    created_at=datetime.utcnow()
                )
                patterns.append(pattern)
            
            # Image extraction patterns
            if 'image_selectors' in metadata:
                pattern = PatternData(
                    pattern_id=f"{retailer}_images_{int(time.time())}",
                    pattern_type=PatternType.INDIVIDUAL_EXTRACTION,
                    retailer=retailer,
                    pattern_category='image_selectors',
                    pattern_data={
                        'selectors': metadata['image_selectors'],
                        'image_count': metadata.get('image_count'),
                        'image_quality': metadata.get('image_quality')
                    },
                    success_count=1,
                    confidence_score=0.7,
                    created_at=datetime.utcnow()
                )
                patterns.append(pattern)
            
            return patterns
            
        except Exception as e:
            logger.warning(f"Error extracting extraction patterns: {e}")
            return []
    
    def _extract_update_patterns(self, retailer: str, url: str, metadata: Dict) -> List[PatternData]:
        """Extract product update specific patterns"""
        patterns = []
        
        try:
            # Price change detection patterns
            if 'price_change_detected' in metadata:
                pattern = PatternData(
                    pattern_id=f"{retailer}_pricechange_{int(time.time())}",
                    pattern_type=PatternType.PRODUCT_UPDATES,
                    retailer=retailer,
                    pattern_category='price_change_patterns',
                    pattern_data={
                        'change_indicator': metadata.get('price_change_indicator'),
                        'old_price': metadata.get('old_price'),
                        'new_price': metadata.get('new_price'),
                        'change_type': metadata.get('change_type')  # increase, decrease, sale
                    },
                    success_count=1,
                    confidence_score=0.8,
                    created_at=datetime.utcnow()
                )
                patterns.append(pattern)
            
            # Stock status patterns
            if 'stock_status_detected' in metadata:
                pattern = PatternData(
                    pattern_id=f"{retailer}_stock_{int(time.time())}",
                    pattern_type=PatternType.PRODUCT_UPDATES,
                    retailer=retailer,
                    pattern_category='stock_status_indicators',
                    pattern_data={
                        'status_indicator': metadata.get('stock_indicator'),
                        'status_value': metadata.get('stock_status'),
                        'detection_method': metadata.get('detection_method')
                    },
                    success_count=1,
                    confidence_score=0.85,
                    created_at=datetime.utcnow()
                )
                patterns.append(pattern)
            
            return patterns
            
        except Exception as e:
            logger.warning(f"Error extracting update patterns: {e}")
            return []
    
    # =================== CROSS-LEARNING LOGIC ===================
    
    async def _apply_cross_learning(self, patterns: List[PatternData]):
        """Apply cross-learning between pattern types"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for pattern in patterns:
                # Check if this pattern type/category has cross-learning opportunities
                source_key = (pattern.pattern_type.value, pattern.pattern_category)
                
                if source_key in self.CROSS_LEARNING_PATTERNS:
                    target_patterns = self.CROSS_LEARNING_PATTERNS[source_key]
                    
                    for target_type, target_category in target_patterns:
                        # Create cross-learning pattern
                        learned_data = self._adapt_pattern_for_cross_learning(
                            pattern, target_type, target_category)
                        
                        if learned_data:
                            cursor.execute("""
                                INSERT OR REPLACE INTO cross_learning_patterns 
                                (source_pattern_id, target_pattern_type, target_pattern_category, 
                                 retailer, learned_data, confidence_transfer_score)
                                VALUES (?, ?, ?, ?, ?, ?)
                            """, (
                                pattern.pattern_id, target_type, target_category,
                                pattern.retailer, json.dumps(learned_data),
                                pattern.confidence_score * 0.7  # Reduced confidence for cross-learning
                            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.warning(f"Error applying cross-learning: {e}")
    
    def _adapt_pattern_for_cross_learning(self, source_pattern: PatternData, 
                                        target_type: str, target_category: str) -> Optional[Dict]:
        """Adapt a pattern for use in a different context"""
        try:
            source_data = source_pattern.pattern_data
            
            # Example adaptations
            if (source_pattern.pattern_category == 'anti_bot_patterns' and 
                target_category == 'anti_bot_patterns'):
                # Anti-bot patterns transfer directly
                return {
                    'verification_type': source_data.get('verification_type'),
                    'bypass_method': source_data.get('bypass_method'),
                    'adapted_from': source_pattern.pattern_type.value
                }
            
            elif (source_pattern.pattern_category == 'price_selectors' and 
                  target_category in ['price_detection', 'price_change_patterns']):
                # Price selector patterns help price detection in other contexts
                return {
                    'selector': source_data.get('selector'),
                    'price_format': source_data.get('price_format'),
                    'adapted_for': target_type
                }
            
            elif (source_pattern.pattern_category == 'stock_status_indicators' and
                  target_category in ['availability_detection', 'availability_indicators']):
                # Stock patterns help availability detection
                return {
                    'status_indicator': source_data.get('status_indicator'),
                    'detection_method': source_data.get('detection_method'),
                    'adapted_for': target_type
                }
            
            return None
            
        except Exception as e:
            logger.warning(f"Error adapting pattern for cross-learning: {e}")
            return None
    
    async def _get_cross_learned_patterns(self, cursor, retailer: str, 
                                        pattern_type: PatternType = None) -> List[Dict]:
        """Get cross-learned patterns for retailer"""
        try:
            if pattern_type:
                query = """
                    SELECT target_pattern_category, learned_data, confidence_transfer_score
                    FROM cross_learning_patterns 
                    WHERE retailer = ? AND target_pattern_type = ?
                    ORDER BY confidence_transfer_score DESC
                """
                cursor.execute(query, (retailer, pattern_type.value))
            else:
                query = """
                    SELECT target_pattern_type, target_pattern_category, learned_data, confidence_transfer_score
                    FROM cross_learning_patterns 
                    WHERE retailer = ?
                    ORDER BY target_pattern_type, confidence_transfer_score DESC
                """
                cursor.execute(query, (retailer,))
            
            return cursor.fetchall()
            
        except Exception as e:
            logger.warning(f"Error getting cross-learned patterns: {e}")
            return []
    
    # =================== UTILITY METHODS ===================
    
    def _infer_pattern_type(self, pattern_context: str) -> PatternType:
        """Infer pattern type from context string"""
        context_lower = pattern_context.lower()
        
        if any(word in context_lower for word in ['catalog', 'crawl', 'pagination', 'grid']):
            return PatternType.CATALOG_CRAWLING
        elif any(word in context_lower for word in ['update', 'refresh', 'change', 'stock']):
            return PatternType.PRODUCT_UPDATES
        else:
            return PatternType.INDIVIDUAL_EXTRACTION
    
    def _organize_patterns(self, patterns: List, cross_patterns: List, 
                         pattern_type: PatternType = None) -> Dict[str, Any]:
        """Organize patterns into structured format"""
        organized = {}
        
        try:
            # Organize main patterns
            for pattern in patterns:
                if pattern_type:
                    # Single pattern type
                    category, data, confidence, last_used = pattern
                    if category not in organized:
                        organized[category] = []
                    organized[category].append({
                        'data': json.loads(data) if isinstance(data, str) else data,
                        'confidence': confidence,
                        'last_used': last_used
                    })
                else:
                    # Multiple pattern types
                    p_type, category, data, confidence, last_used = pattern
                    if p_type not in organized:
                        organized[p_type] = {}
                    if category not in organized[p_type]:
                        organized[p_type][category] = []
                    organized[p_type][category].append({
                        'data': json.loads(data) if isinstance(data, str) else data,
                        'confidence': confidence,
                        'last_used': last_used
                    })
            
            # Add cross-learned patterns
            if cross_patterns:
                if 'cross_learned' not in organized:
                    organized['cross_learned'] = {}
                
                for cross_pattern in cross_patterns:
                    if pattern_type:
                        category, data, confidence = cross_pattern
                        if category not in organized['cross_learned']:
                            organized['cross_learned'][category] = []
                        organized['cross_learned'][category].append({
                            'data': json.loads(data) if isinstance(data, str) else data,
                            'confidence': confidence,
                            'cross_learned': True
                        })
                    else:
                        p_type, category, data, confidence = cross_pattern
                        if p_type not in organized['cross_learned']:
                            organized['cross_learned'][p_type] = {}
                        if category not in organized['cross_learned'][p_type]:
                            organized['cross_learned'][p_type][category] = []
                        organized['cross_learned'][p_type][category].append({
                            'data': json.loads(data) if isinstance(data, str) else data,
                            'confidence': confidence,
                            'cross_learned': True
                        })
            
            return organized
            
        except Exception as e:
            logger.warning(f"Error organizing patterns: {e}")
            return {}
    
    async def _store_learned_patterns(self, patterns: List[PatternData]):
        """Store learned patterns in database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for pattern in patterns:
                cursor.execute("""
                    INSERT OR REPLACE INTO enhanced_patterns 
                    (pattern_id, pattern_type, retailer, pattern_category, pattern_data,
                     success_count, failure_count, confidence_score, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    pattern.pattern_id, pattern.pattern_type.value, pattern.retailer,
                    pattern.pattern_category, json.dumps(pattern.pattern_data),
                    pattern.success_count, pattern.failure_count, pattern.confidence_score,
                    pattern.created_at, datetime.utcnow()
                ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error storing learned patterns: {e}")
    
    async def _record_usage_stats(self, patterns: List[PatternData], success: bool,
                                processing_time: Optional[float], context: str,
                                error_details: str = None):
        """Record pattern usage statistics"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for pattern in patterns:
                cursor.execute("""
                    INSERT INTO pattern_usage_stats 
                    (pattern_id, usage_context, success, processing_time, error_details)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    pattern.pattern_id, context, success, processing_time, error_details
                ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.warning(f"Error recording usage stats: {e}")
    
    async def _update_pattern_failures(self, retailer: str, pattern_type: PatternType, context: str):
        """Update failure counts for related patterns"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE enhanced_patterns 
                SET failure_count = failure_count + 1,
                    confidence_score = CASE 
                        WHEN confidence_score > 0.1 THEN confidence_score - 0.05
                        ELSE 0.1
                    END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE retailer = ? AND pattern_type = ?
            """, (retailer, pattern_type.value))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.warning(f"Error updating pattern failures: {e}")
    
    # =================== ANALYTICS AND MANAGEMENT ===================
    
    async def get_pattern_statistics(self) -> Dict[str, Any]:
        """Get comprehensive pattern learning statistics"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Pattern counts by type
            cursor.execute("""
                SELECT pattern_type, COUNT(*) as count
                FROM enhanced_patterns
                GROUP BY pattern_type
            """)
            type_counts = dict(cursor.fetchall())
            
            # Pattern counts by retailer
            cursor.execute("""
                SELECT retailer, COUNT(*) as count
                FROM enhanced_patterns
                GROUP BY retailer
                ORDER BY count DESC
            """)
            retailer_counts = dict(cursor.fetchall())
            
            # Success rates by pattern type
            cursor.execute("""
                SELECT pattern_type, 
                       AVG(CASE WHEN success_count > 0 THEN 
                           CAST(success_count AS FLOAT) / (success_count + failure_count)
                           ELSE 0 END) as success_rate
                FROM enhanced_patterns
                WHERE success_count + failure_count > 0
                GROUP BY pattern_type
            """)
            success_rates = dict(cursor.fetchall())
            
            # Cross-learning statistics
            cursor.execute("""
                SELECT target_pattern_type, COUNT(*) as count
                FROM cross_learning_patterns
                GROUP BY target_pattern_type
            """)
            cross_learning_counts = dict(cursor.fetchall())
            
            conn.close()
            
            return {
                'total_patterns': sum(type_counts.values()),
                'patterns_by_type': type_counts,
                'patterns_by_retailer': retailer_counts,
                'success_rates_by_type': success_rates,
                'cross_learning_patterns': cross_learning_counts,
                'pattern_types_supported': [pt.value for pt in PatternType]
            }
            
        except Exception as e:
            logger.error(f"Error getting pattern statistics: {e}")
            return {}
    
    async def cleanup_old_patterns(self, days_old: int = 30):
        """Clean up old, low-confidence patterns"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            
            cursor.execute("""
                DELETE FROM enhanced_patterns 
                WHERE created_at < ? AND confidence_score < 0.3
            """, (cutoff_date,))
            
            deleted_count = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            logger.info(f"Cleaned up {deleted_count} old patterns")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error cleaning up old patterns: {e}")
            return 0

# Maintain backward compatibility with existing unified_extractor usage
class PatternLearner(EnhancedPatternLearner):
    """Backward compatibility class"""
    
    async def get_learned_patterns(self, retailer: str, url: str = None) -> Dict[str, Any]:
        """Backward compatible method"""
        return await super().get_learned_patterns(retailer, url, PatternType.INDIVIDUAL_EXTRACTION)
    
    async def record_success(self, retailer: str, url: str, method: str, 
                           processing_time: float, metadata: Dict):
        """Backward compatible method"""
        await super().record_success(
            retailer, url, method, processing_time, metadata, 
            PatternType.INDIVIDUAL_EXTRACTION)
    
    async def record_failure(self, retailer: str, url: str, method: str, error: str):
        """Backward compatible method"""
        await super().record_failure(
            retailer, url, method, error, PatternType.INDIVIDUAL_EXTRACTION)