"""
Pattern Learner - Learns from successful and failed extractions to improve future performance
"""

import aiosqlite
import asyncio
import json
import re
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from collections import defaultdict
import difflib

from logger_config import setup_logging

logger = setup_logging(__name__)

class PatternLearner:
    def __init__(self, db_path: str = "patterns.db"):
        self.db_path = db_path
        
        # In-memory pattern cache for performance
        self.pattern_cache = {
            'success_patterns': defaultdict(list),
            'failure_patterns': defaultdict(list),
            'image_transformations': defaultdict(list)
        }
        
        # Initialize database and load patterns asynchronously
        try:
            loop = asyncio.get_running_loop()
            # If we're already in an event loop, create a task
            asyncio.create_task(self._async_init())
            # For testing purposes, we'll need to call _async_init later
            self._init_deferred = True
        except RuntimeError:
            # No event loop running, safe to use asyncio.run()
            try:
                asyncio.run(self._async_init())
                self._init_deferred = False
            except Exception as e:
                logger.warning(f"Could not initialize pattern learner: {e}")
                self._init_deferred = True
    
    async def _ensure_initialized(self):
        """Ensure async initialization is complete"""
        if getattr(self, '_init_deferred', False):
            await self._async_init()
            self._init_deferred = False
    
    async def _async_init(self):
        """Async initialization"""
        await self._init_pattern_database()
        await self._load_pattern_cache()
    
    async def _init_pattern_database(self):
        """Initialize pattern learning database"""
        
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                cursor = await conn.cursor()
                
                # Success patterns table
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS success_patterns (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        retailer VARCHAR(100),
                        url_pattern VARCHAR(500),
                        extraction_method VARCHAR(50),
                        data_selectors TEXT,
                        confidence_score DECIMAL(3,2),
                        success_timestamp TIMESTAMP,
                        usage_count INTEGER DEFAULT 1,
                        success_rate DECIMAL(3,2) DEFAULT 1.0
                    )
                """)
                
                # Failure patterns table
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS failure_patterns (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        retailer VARCHAR(100),
                        url_pattern VARCHAR(500),
                        extraction_method VARCHAR(50),
                        error_type VARCHAR(100),
                        error_details TEXT,
                        failure_timestamp TIMESTAMP,
                        occurrence_count INTEGER DEFAULT 1
                    )
                """)
                
                # Image transformation patterns table
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS image_transformations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        retailer VARCHAR(100),
                        original_pattern VARCHAR(500),
                        transformed_pattern VARCHAR(500),
                        transformation_rule TEXT,
                        success_count INTEGER DEFAULT 1,
                        failure_count INTEGER DEFAULT 0,
                        confidence DECIMAL(3,2),
                        last_used TIMESTAMP
                    )
                """)
                
                # Create indexes
                await cursor.execute("CREATE INDEX IF NOT EXISTS idx_retailer_success ON success_patterns(retailer, confidence_score)")
                await cursor.execute("CREATE INDEX IF NOT EXISTS idx_retailer_failure ON failure_patterns(retailer, error_type)")
                await cursor.execute("CREATE INDEX IF NOT EXISTS idx_image_confidence ON image_transformations(retailer, confidence)")
                
                await conn.commit()
                logger.info("Pattern learning database initialized")
        
        except Exception as e:
            logger.error(f"Failed to initialize pattern database: {e}")
            raise
    
    async def _load_pattern_cache(self):
        """Load recent patterns into memory cache"""
        
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                cursor = await conn.cursor()
                
                # Load recent success patterns (last 30 days)
                await cursor.execute("""
                    SELECT retailer, url_pattern, extraction_method, data_selectors, confidence_score
                    FROM success_patterns 
                    WHERE success_timestamp >= datetime('now', '-30 days')
                    ORDER BY confidence_score DESC, usage_count DESC
                    LIMIT 100
                """)
                
                rows = await cursor.fetchall()
                for row in rows:
                    retailer, url_pattern, method, selectors, confidence = row
                    self.pattern_cache['success_patterns'][retailer].append({
                        'url_pattern': url_pattern,
                        'method': method,
                        'selectors': json.loads(selectors) if selectors else {},
                        'confidence': confidence
                    })
                
                # Load recent failure patterns
                await cursor.execute("""
                    SELECT retailer, url_pattern, extraction_method, error_type, error_details
                    FROM failure_patterns 
                    WHERE failure_timestamp >= datetime('now', '-7 days')
                    ORDER BY occurrence_count DESC
                    LIMIT 50
                """)
                
                rows = await cursor.fetchall()
                for row in rows:
                    retailer, url_pattern, method, error_type, error_details = row
                    self.pattern_cache['failure_patterns'][retailer].append({
                        'url_pattern': url_pattern,
                        'method': method,
                        'error_type': error_type,
                        'error_details': error_details
                    })
                
                # Load image transformations
                await cursor.execute("""
                    SELECT retailer, original_pattern, transformed_pattern, transformation_rule, confidence
                    FROM image_transformations 
                    WHERE confidence > 0.7
                    ORDER BY confidence DESC, success_count DESC
                    LIMIT 50
                """)
                
                rows = await cursor.fetchall()
                for row in rows:
                    retailer, original, transformed, rule, confidence = row
                    self.pattern_cache['image_transformations'][retailer].append({
                        'original_pattern': original,
                        'transformed_pattern': transformed,
                        'rule': rule,
                        'confidence': confidence
                    })
                
                logger.info("Pattern cache loaded successfully")
        
        except Exception as e:
            logger.error(f"Failed to load pattern cache: {e}")
    
    async def record_successful_extraction(self, retailer: str, url: str, extraction_method: str, 
                                         extracted_data: Dict):
        """Record successful extraction patterns"""
        
        try:
            url_pattern = self._extract_url_pattern(url)
            data_selectors = self._analyze_data_patterns(extracted_data)
            confidence_score = self._calculate_confidence_score(extracted_data)
            
            async with aiosqlite.connect(self.db_path) as conn:
                cursor = await conn.cursor()
                
                # Check if pattern already exists
                await cursor.execute("""
                    SELECT id, usage_count, success_rate FROM success_patterns 
                    WHERE retailer = ? AND url_pattern = ? AND extraction_method = ?
                """, (retailer, url_pattern, extraction_method))
                
                existing = await cursor.fetchone()
                
                if existing:
                    # Update existing pattern
                    pattern_id, usage_count, success_rate = existing
                    new_usage_count = usage_count + 1
                    new_success_rate = (success_rate * usage_count + 1.0) / new_usage_count
                    
                    await cursor.execute("""
                        UPDATE success_patterns 
                        SET usage_count = ?, success_rate = ?, success_timestamp = ?, confidence_score = ?
                        WHERE id = ?
                    """, (new_usage_count, new_success_rate, datetime.utcnow(), confidence_score, pattern_id))
                else:
                    # Insert new pattern
                    await cursor.execute("""
                        INSERT INTO success_patterns 
                        (retailer, url_pattern, extraction_method, data_selectors, confidence_score, success_timestamp)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (retailer, url_pattern, extraction_method, json.dumps(data_selectors), 
                         confidence_score, datetime.utcnow()))
                
                await conn.commit()
            
            # Update cache
            pattern = {
                'url_pattern': url_pattern,
                'method': extraction_method,
                'selectors': data_selectors,
                'confidence': confidence_score
            }
            
            self.pattern_cache['success_patterns'][retailer].append(pattern)
            # Keep cache size manageable
            if len(self.pattern_cache['success_patterns'][retailer]) > 20:
                self.pattern_cache['success_patterns'][retailer] = \
                    sorted(self.pattern_cache['success_patterns'][retailer], 
                          key=lambda x: x['confidence'], reverse=True)[:20]
            
            logger.debug(f"Recorded successful pattern for {retailer}: {extraction_method}")
        
        except Exception as e:
            logger.error(f"Failed to record successful extraction: {e}")
    
    async def record_failed_extraction(self, retailer: str, url: str, extraction_method: str, error_message: str):
        """Record failed extraction patterns"""
        
        try:
            url_pattern = self._extract_url_pattern(url)
            error_type = self._classify_error_type(error_message)
            
            async with aiosqlite.connect(self.db_path) as conn:
                cursor = await conn.cursor()
                
                # Check if pattern already exists
                await cursor.execute("""
                    SELECT id, occurrence_count FROM failure_patterns 
                    WHERE retailer = ? AND url_pattern = ? AND extraction_method = ? AND error_type = ?
                """, (retailer, url_pattern, extraction_method, error_type))
                
                existing = await cursor.fetchone()
                
                if existing:
                    # Update existing pattern
                    pattern_id, occurrence_count = existing
                    new_occurrence_count = occurrence_count + 1
                    
                    await cursor.execute("""
                        UPDATE failure_patterns 
                        SET occurrence_count = ?, failure_timestamp = ?
                        WHERE id = ?
                    """, (new_occurrence_count, datetime.utcnow(), pattern_id))
                else:
                    # Insert new pattern
                    await cursor.execute("""
                        INSERT INTO failure_patterns 
                        (retailer, url_pattern, extraction_method, error_type, error_details, failure_timestamp)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (retailer, url_pattern, extraction_method, error_type, error_message, datetime.utcnow()))
                
                await conn.commit()
            
            # Update cache
            failure_pattern = {
                'url_pattern': url_pattern,
                'method': extraction_method,
                'error_type': error_type,
                'error_details': error_message
            }
            
            self.pattern_cache['failure_patterns'][retailer].append(failure_pattern)
            # Keep cache size manageable
            if len(self.pattern_cache['failure_patterns'][retailer]) > 10:
                self.pattern_cache['failure_patterns'][retailer] = \
                    self.pattern_cache['failure_patterns'][retailer][-10:]
            
            logger.debug(f"Recorded failure pattern for {retailer}: {error_type}")
        
        except Exception as e:
            logger.error(f"Failed to record failed extraction: {e}")
    
    async def get_learned_patterns(self, retailer: str, url: str) -> List[Dict]:
        """Get learned patterns for retailer/URL combination"""
        
        try:
            await self._ensure_initialized()
            
            url_pattern = self._extract_url_pattern(url)
            
            # Get from cache first
            cached_patterns = self.pattern_cache['success_patterns'].get(retailer, [])
            
            # Filter patterns that match the URL
            matching_patterns = []
            for pattern in cached_patterns:
                if self._url_matches_pattern(url, pattern['url_pattern']):
                    matching_patterns.append(pattern)
            
            # Sort by confidence and return top 3
            matching_patterns.sort(key=lambda x: x['confidence'], reverse=True)
            return matching_patterns[:3]
        
        except Exception as e:
            logger.error(f"Failed to get learned patterns: {e}")
            return []
    
    async def learn_image_transformation(self, retailer: str, original_url: str, high_res_url: str, success: bool):
        """Learn image URL transformation patterns"""
        
        try:
            original_pattern = self._extract_url_pattern(original_url)
            transformed_pattern = self._extract_url_pattern(high_res_url)
            transformation_rule = self._identify_transformation_rule(original_url, high_res_url)
            
            async with aiosqlite.connect(self.db_path) as conn:
                cursor = await conn.cursor()
                
                # Check if transformation already exists
                await cursor.execute("""
                    SELECT id, success_count, failure_count FROM image_transformations 
                    WHERE retailer = ? AND original_pattern = ? AND transformed_pattern = ?
                """, (retailer, original_pattern, transformed_pattern))
                
                existing = await cursor.fetchone()
                
                if existing:
                    # Update existing transformation
                    trans_id, success_count, failure_count = existing
                    if success:
                        new_success_count = success_count + 1
                        new_failure_count = failure_count
                    else:
                        new_success_count = success_count
                        new_failure_count = failure_count + 1
                    
                    new_confidence = new_success_count / (new_success_count + new_failure_count)
                    
                    await cursor.execute("""
                        UPDATE image_transformations 
                        SET success_count = ?, failure_count = ?, confidence = ?, last_used = ?
                        WHERE id = ?
                    """, (new_success_count, new_failure_count, new_confidence, datetime.utcnow(), trans_id))
                else:
                    # Insert new transformation
                    initial_confidence = 1.0 if success else 0.0
                    initial_success = 1 if success else 0
                    initial_failure = 0 if success else 1
                    
                    await cursor.execute("""
                        INSERT INTO image_transformations 
                        (retailer, original_pattern, transformed_pattern, transformation_rule, 
                         success_count, failure_count, confidence, last_used)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (retailer, original_pattern, transformed_pattern, transformation_rule,
                         initial_success, initial_failure, initial_confidence, datetime.utcnow()))
                
                await conn.commit()
                
            logger.debug(f"Learned image transformation for {retailer}: {success}")
        
        except Exception as e:
            logger.error(f"Failed to learn image transformation: {e}")
    
    async def apply_learned_image_patterns(self, retailer: str, image_urls: List[str]) -> List[str]:
        """Apply learned image transformation patterns"""
        
        try:
            learned_transformations = self.pattern_cache['image_transformations'].get(retailer, [])
            
            enhanced_urls = []
            for url in image_urls:
                best_transformation = None
                best_confidence = 0
                
                for transformation in learned_transformations:
                    if transformation['confidence'] > 0.8 and transformation['confidence'] > best_confidence:
                        # Check if transformation pattern applies
                        if self._transformation_applies(url, transformation):
                            best_transformation = transformation
                            best_confidence = transformation['confidence']
                
                if best_transformation:
                    enhanced_url = self._apply_transformation(url, best_transformation)
                    enhanced_urls.append(enhanced_url)
                else:
                    enhanced_urls.append(url)
            
            return enhanced_urls
        
        except Exception as e:
            logger.error(f"Failed to apply image patterns: {e}")
            return image_urls  # Return original URLs on error
    
    def _extract_url_pattern(self, url: str) -> str:
        """Extract generalized pattern from URL"""
        
        # Remove specific product IDs and codes, keep structure
        pattern = re.sub(r'/\d{6,}', '/[PRODUCT_ID]', url)
        pattern = re.sub(r'/[A-Z0-9]{6,}', '/[PRODUCT_CODE]', pattern)
        pattern = re.sub(r'product-\d+', 'product-[ID]', pattern)
        pattern = re.sub(r'style-[A-Z0-9]+', 'style-[CODE]', pattern)
        
        # Remove query parameters for pattern matching
        if '?' in pattern:
            pattern = pattern.split('?')[0]
        
        return pattern
    
    def _analyze_data_patterns(self, extracted_data: Dict) -> Dict:
        """Analyze successful data patterns"""
        
        patterns = {
            'fields_found': list(extracted_data.keys()),
            'data_quality': {},
            'field_patterns': {}
        }
        
        # Analyze data quality
        for field, value in extracted_data.items():
            if value is not None and value != '':
                patterns['data_quality'][field] = 'good'
                
                # Analyze field patterns
                if field == 'price' and isinstance(value, (int, float)):
                    patterns['field_patterns']['price_numeric'] = True
                elif field == 'title' and isinstance(value, str) and len(value) > 10:
                    patterns['field_patterns']['title_substantial'] = True
                elif field == 'image_urls' and isinstance(value, list) and len(value) > 0:
                    patterns['field_patterns']['images_found'] = len(value)
            else:
                patterns['data_quality'][field] = 'poor'
        
        return patterns
    
    def _calculate_confidence_score(self, extracted_data: Dict) -> float:
        """Calculate confidence score for extraction success"""
        
        required_fields = ['title', 'price', 'retailer']
        important_fields = ['brand', 'description', 'stock_status', 'image_urls']
        
        score = 0.0
        max_score = 1.0
        
        # Required fields (70% of score)
        required_found = sum(1 for field in required_fields if extracted_data.get(field))
        score += (required_found / len(required_fields)) * 0.7
        
        # Important fields (20% of score)
        important_found = sum(1 for field in important_fields if extracted_data.get(field))
        score += (important_found / len(important_fields)) * 0.2
        
        # Data quality (10% of score)
        if extracted_data.get('price') and isinstance(extracted_data['price'], (int, float)):
            score += 0.05
        if extracted_data.get('image_urls') and len(extracted_data['image_urls']) > 0:
            score += 0.05
        
        return min(score, max_score)
    
    def _classify_error_type(self, error_message: str) -> str:
        """Classify error types for pattern analysis"""
        
        error_lower = error_message.lower()
        
        if 'timeout' in error_lower:
            return 'timeout'
        elif 'connection' in error_lower or 'network' in error_lower:
            return 'network_error'
        elif '404' in error_lower or 'not found' in error_lower:
            return 'page_not_found'
        elif '403' in error_lower or 'forbidden' in error_lower:
            return 'access_denied'
        elif 'captcha' in error_lower:
            return 'captcha_challenge'
        elif 'rate limit' in error_lower or 'too many requests' in error_lower:
            return 'rate_limited'
        elif 'parsing' in error_lower or 'extraction' in error_lower:
            return 'extraction_failed'
        else:
            return 'unknown_error'
    
    def _url_matches_pattern(self, url: str, pattern: str) -> bool:
        """Check if URL matches learned pattern"""
        
        url_pattern = self._extract_url_pattern(url)
        return url_pattern == pattern or difflib.SequenceMatcher(None, url_pattern, pattern).ratio() > 0.8
    
    def _identify_transformation_rule(self, original: str, transformed: str) -> str:
        """Identify the transformation rule between URLs"""
        
        transformations = []
        
        # Common transformation patterns
        patterns = [
            (r'_small\.jpg', '_large.jpg'),
            (r'_150x150\.jpg', '_800x800.jpg'),
            (r'_2xl\.jpg', '_xxl.jpg'),
            (r'\?sw=150', '?sw=800'),
            (r'_thumb\.', '_main.'),
            (r'_s\.', '_l.'),
            (r'_sm\.', '_lg.')
        ]
        
        for old_pattern, new_pattern in patterns:
            if re.search(old_pattern, original) and new_pattern.replace('\\', '') in transformed:
                transformations.append(f"{old_pattern} -> {new_pattern}")
        
        return '; '.join(transformations) if transformations else 'custom_transformation'
    
    def _transformation_applies(self, url: str, transformation: Dict) -> bool:
        """Check if transformation pattern applies to URL"""
        
        rule = transformation.get('rule', '')
        
        # Simple pattern matching for common transformations
        if '_small.jpg' in rule and '_small.jpg' in url:
            return True
        elif '_150x150' in rule and ('150' in url or 'small' in url):
            return True
        elif 'sw=150' in rule and 'sw=' in url:
            return True
        
        return False
    
    def _apply_transformation(self, url: str, transformation: Dict) -> str:
        """Apply transformation rule to URL"""
        
        rule = transformation.get('rule', '')
        
        # Apply known transformation patterns
        if '_small.jpg -> _large.jpg' in rule:
            return url.replace('_small.jpg', '_large.jpg')
        elif '_150x150.jpg -> _800x800.jpg' in rule:
            return url.replace('_150x150.jpg', '_800x800.jpg')
        elif '?sw=150 -> ?sw=800' in rule:
            return url.replace('?sw=150', '?sw=800')
        
        return url  # Return original if no transformation applies
    
    async def get_stats(self) -> Dict:
        """Get pattern learning statistics"""
        
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                cursor = await conn.cursor()
                
                # Success patterns stats
                await cursor.execute("SELECT COUNT(*) FROM success_patterns")
                success_count_result = await cursor.fetchone()
                success_count = success_count_result[0] if success_count_result else 0
                
                # Failure patterns stats
                await cursor.execute("SELECT COUNT(*) FROM failure_patterns")
                failure_count_result = await cursor.fetchone()
                failure_count = failure_count_result[0] if failure_count_result else 0
                
                # Image transformations stats
                await cursor.execute("SELECT COUNT(*) FROM image_transformations WHERE confidence > 0.7")
                high_confidence_transforms_result = await cursor.fetchone()
                high_confidence_transforms = high_confidence_transforms_result[0] if high_confidence_transforms_result else 0
                
                # Top performing retailers
                await cursor.execute("""
                    SELECT retailer, COUNT(*) as pattern_count
                    FROM success_patterns 
                    GROUP BY retailer 
                    ORDER BY pattern_count DESC 
                    LIMIT 5
                """)
                top_retailers = await cursor.fetchall()
                
                return {
                    'success_patterns': success_count,
                    'failure_patterns': failure_count,
                    'high_confidence_transformations': high_confidence_transforms,
                    'cache_size': {
                        'success': sum(len(patterns) for patterns in self.pattern_cache['success_patterns'].values()),
                        'failures': sum(len(patterns) for patterns in self.pattern_cache['failure_patterns'].values()),
                        'transformations': sum(len(patterns) for patterns in self.pattern_cache['image_transformations'].values())
                    },
                    'top_retailers': [{'retailer': r[0], 'patterns': r[1]} for r in top_retailers]
                }
        
        except Exception as e:
            logger.error(f"Failed to get pattern stats: {e}")
            return {
                'success_patterns': 0,
                'failure_patterns': 0,
                'high_confidence_transformations': 0,
                'cache_size': {'success': 0, 'failures': 0, 'transformations': 0},
                'top_retailers': []
            }