"""
Pattern Learner

Learns which CSS selectors work best for each retailer
Tracks success/failure rates, auto-improves over time
"""

import aiosqlite
import logging
from typing import Dict, List, Optional
from datetime import datetime
import json
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from Shared.logger_config import setup_logging
from Extraction.CommercialAPI.commercial_config import CommercialAPIConfig

logger = setup_logging(__name__)

class PatternLearner:
    """
    Pattern Learning for HTML Selectors
    
    Features:
    - Track which CSS selectors work for each retailer
    - Record success/failure rates per selector
    - Auto-improve selector order based on success rate
    - Identify failing selectors
    - Provide recommendations for selector updates
    
    Usage:
        learner = PatternLearner()
        await learner.record_success(retailer, 'product', url, data)
        await learner.record_failure(retailer, 'product', url, errors)
        stats = await learner.get_stats()
    """
    
    def __init__(self):
        self.config = CommercialAPIConfig()
        self.db_path = self.config.PATTERN_DB_PATH
        
        logger.info(f"✅ Pattern Learner initialized")
        logger.info(f"📂 Pattern DB: {self.db_path}")
    
    async def initialize(self):
        """Initialize pattern learning database"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Create patterns table
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS commercial_patterns (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        retailer TEXT NOT NULL,
                        page_type TEXT NOT NULL,
                        pattern_name TEXT NOT NULL,
                        pattern_data TEXT,
                        success_count INTEGER DEFAULT 0,
                        failure_count INTEGER DEFAULT 0,
                        total_attempts INTEGER DEFAULT 0,
                        success_rate REAL DEFAULT 0.0,
                        last_used TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(retailer, page_type, pattern_name)
                    )
                ''')
                
                # Create attempts log table
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS commercial_pattern_attempts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        retailer TEXT NOT NULL,
                        page_type TEXT NOT NULL,
                        url TEXT NOT NULL,
                        success BOOLEAN NOT NULL,
                        errors TEXT,
                        extracted_data TEXT,
                        attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Create indices
                await db.execute('''
                    CREATE INDEX IF NOT EXISTS idx_retailer_type 
                    ON commercial_patterns(retailer, page_type)
                ''')
                
                await db.execute('''
                    CREATE INDEX IF NOT EXISTS idx_attempted_at 
                    ON commercial_pattern_attempts(attempted_at)
                ''')
                
                await db.commit()
            
            logger.debug("✅ Pattern learning database initialized")
        
        except Exception as e:
            logger.error(f"❌ Failed to initialize pattern learning: {e}")
    
    async def record_success(
        self,
        retailer: str,
        page_type: str,
        url: str,
        extracted_data: Dict
    ):
        """
        Record successful extraction
        
        Args:
            retailer: Retailer name
            page_type: 'product' or 'catalog'
            url: Source URL
            extracted_data: Data that was successfully extracted
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Log attempt
                await db.execute(
                    '''
                    INSERT INTO commercial_pattern_attempts 
                    (retailer, page_type, url, success, extracted_data)
                    VALUES (?, ?, ?, ?, ?)
                    ''',
                    (
                        retailer,
                        page_type,
                        url,
                        True,
                        json.dumps(extracted_data)
                    )
                )
                
                # Update pattern stats
                pattern_name = f"{retailer}_{page_type}"
                
                await db.execute(
                    '''
                    INSERT INTO commercial_patterns 
                    (retailer, page_type, pattern_name, success_count, total_attempts, last_used, updated_at)
                    VALUES (?, ?, ?, 1, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT(retailer, page_type, pattern_name) DO UPDATE SET
                        success_count = success_count + 1,
                        total_attempts = total_attempts + 1,
                        success_rate = CAST(success_count + 1 AS REAL) / (total_attempts + 1),
                        last_used = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    ''',
                    (retailer, page_type, pattern_name)
                )
                
                await db.commit()
            
            logger.debug(f"✅ Recorded success: {retailer} {page_type}")
        
        except Exception as e:
            logger.warning(f"⚠️ Failed to record pattern success: {e}")
    
    async def record_failure(
        self,
        retailer: str,
        page_type: str,
        url: str,
        errors: List[str]
    ):
        """
        Record failed extraction
        
        Args:
            retailer: Retailer name
            page_type: 'product' or 'catalog'
            url: Source URL
            errors: List of error messages
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Log attempt
                await db.execute(
                    '''
                    INSERT INTO commercial_pattern_attempts 
                    (retailer, page_type, url, success, errors)
                    VALUES (?, ?, ?, ?, ?)
                    ''',
                    (
                        retailer,
                        page_type,
                        url,
                        False,
                        json.dumps(errors)
                    )
                )
                
                # Update pattern stats
                pattern_name = f"{retailer}_{page_type}"
                
                await db.execute(
                    '''
                    INSERT INTO commercial_patterns 
                    (retailer, page_type, pattern_name, failure_count, total_attempts, last_used, updated_at)
                    VALUES (?, ?, ?, 1, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT(retailer, page_type, pattern_name) DO UPDATE SET
                        failure_count = failure_count + 1,
                        total_attempts = total_attempts + 1,
                        success_rate = CAST(success_count AS REAL) / (total_attempts + 1),
                        last_used = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    ''',
                    (retailer, page_type, pattern_name)
                )
                
                await db.commit()
            
            logger.debug(f"❌ Recorded failure: {retailer} {page_type} - {errors}")
        
        except Exception as e:
            logger.warning(f"⚠️ Failed to record pattern failure: {e}")
    
    async def get_stats(self) -> Dict:
        """
        Get pattern learning statistics
        
        Returns:
            Dict with overall and per-retailer stats
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Overall stats
                cursor = await db.execute('''
                    SELECT 
                        COUNT(*) as total_patterns,
                        SUM(success_count) as total_successes,
                        SUM(failure_count) as total_failures,
                        AVG(success_rate) as avg_success_rate
                    FROM commercial_patterns
                ''')
                overall = await cursor.fetchone()
                
                # Per-retailer stats
                cursor = await db.execute('''
                    SELECT 
                        retailer,
                        page_type,
                        success_count,
                        failure_count,
                        total_attempts,
                        success_rate,
                        last_used
                    FROM commercial_patterns
                    ORDER BY retailer, page_type
                ''')
                per_retailer = await cursor.fetchall()
                
                # Recent attempts
                cursor = await db.execute('''
                    SELECT 
                        retailer,
                        page_type,
                        url,
                        success,
                        attempted_at
                    FROM commercial_pattern_attempts
                    ORDER BY attempted_at DESC
                    LIMIT 10
                ''')
                recent_attempts = await cursor.fetchall()
                
                return {
                    'overall': {
                        'total_patterns': overall[0] or 0,
                        'total_successes': overall[1] or 0,
                        'total_failures': overall[2] or 0,
                        'avg_success_rate': overall[3] or 0.0,
                    },
                    'per_retailer': [
                        {
                            'retailer': row[0],
                            'page_type': row[1],
                            'success_count': row[2],
                            'failure_count': row[3],
                            'total_attempts': row[4],
                            'success_rate': row[5],
                            'last_used': row[6],
                        }
                        for row in per_retailer
                    ],
                    'recent_attempts': [
                        {
                            'retailer': row[0],
                            'page_type': row[1],
                            'url': row[2],
                            'success': bool(row[3]),
                            'attempted_at': row[4],
                        }
                        for row in recent_attempts
                    ],
                }
        
        except Exception as e:
            logger.warning(f"⚠️ Failed to get pattern stats: {e}")
            return {}
    
    async def get_failing_patterns(
        self,
        min_attempts: int = 5,
        max_success_rate: float = 0.5
    ) -> List[Dict]:
        """
        Get patterns with low success rates
        
        Args:
            min_attempts: Minimum attempts before considering pattern
            max_success_rate: Maximum success rate to be considered "failing"
        
        Returns:
            List of failing patterns with details
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    '''
                    SELECT 
                        retailer,
                        page_type,
                        pattern_name,
                        success_count,
                        failure_count,
                        total_attempts,
                        success_rate,
                        last_used
                    FROM commercial_patterns
                    WHERE total_attempts >= ? AND success_rate <= ?
                    ORDER BY success_rate ASC, total_attempts DESC
                    ''',
                    (min_attempts, max_success_rate)
                )
                
                failing = await cursor.fetchall()
                
                return [
                    {
                        'retailer': row[0],
                        'page_type': row[1],
                        'pattern_name': row[2],
                        'success_count': row[3],
                        'failure_count': row[4],
                        'total_attempts': row[5],
                        'success_rate': row[6],
                        'last_used': row[7],
                    }
                    for row in failing
                ]
        
        except Exception as e:
            logger.warning(f"⚠️ Failed to get failing patterns: {e}")
            return []
    
    async def get_common_errors(
        self,
        retailer: Optional[str] = None,
        page_type: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict]:
        """
        Get most common extraction errors
        
        Args:
            retailer: Filter by retailer (optional)
            page_type: Filter by page type (optional)
            limit: Maximum errors to return
        
        Returns:
            List of common errors with counts
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Build query
                where_clauses = ["success = FALSE"]
                params = []
                
                if retailer:
                    where_clauses.append("retailer = ?")
                    params.append(retailer)
                
                if page_type:
                    where_clauses.append("page_type = ?")
                    params.append(page_type)
                
                where_sql = " AND ".join(where_clauses)
                
                cursor = await db.execute(
                    f'''
                    SELECT errors, COUNT(*) as count
                    FROM commercial_pattern_attempts
                    WHERE {where_sql}
                    GROUP BY errors
                    ORDER BY count DESC
                    LIMIT ?
                    ''',
                    params + [limit]
                )
                
                errors = await cursor.fetchall()
                
                return [
                    {
                        'errors': json.loads(row[0]) if row[0] else [],
                        'count': row[1],
                    }
                    for row in errors
                ]
        
        except Exception as e:
            logger.warning(f"⚠️ Failed to get common errors: {e}")
            return []
    
    async def cleanup_old_attempts(self, days: int = 30):
        """
        Remove old attempt logs (keep patterns, remove detailed logs)
        
        Args:
            days: Remove attempts older than this many days
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    '''
                    DELETE FROM commercial_pattern_attempts
                    WHERE attempted_at < datetime('now', '-' || ? || ' days')
                    ''',
                    (days,)
                )
                deleted = cursor.rowcount
                await db.commit()
                
                if deleted > 0:
                    logger.info(f"🗑️ Cleaned up {deleted} old pattern attempts")
        
        except Exception as e:
            logger.warning(f"⚠️ Failed to cleanup old attempts: {e}")
    
    async def log_pattern_stats(self):
        """Log pattern learning statistics"""
        stats = await self.get_stats()
        
        if not stats:
            return
        
        overall = stats.get('overall', {})
        
        logger.info("=" * 60)
        logger.info("📊 PATTERN LEARNING STATISTICS")
        logger.info("=" * 60)
        logger.info(f"Total Patterns: {overall.get('total_patterns', 0)}")
        logger.info(f"Total Successes: {overall.get('total_successes', 0)}")
        logger.info(f"Total Failures: {overall.get('total_failures', 0)}")
        logger.info(f"Avg Success Rate: {overall.get('avg_success_rate', 0)*100:.1f}%")
        
        # Show per-retailer breakdown
        per_retailer = stats.get('per_retailer', [])
        if per_retailer:
            logger.info("-" * 60)
            logger.info("Per-Retailer Breakdown:")
            for pattern in per_retailer:
                logger.info(
                    f"  {pattern['retailer']} ({pattern['page_type']}): "
                    f"{pattern['total_attempts']} attempts, "
                    f"{pattern['success_rate']*100:.1f}% success"
                )
        
        # Show failing patterns
        failing = await self.get_failing_patterns()
        if failing:
            logger.info("-" * 60)
            logger.info("⚠️ Failing Patterns (needs attention):")
            for pattern in failing[:5]:  # Show top 5
                logger.info(
                    f"  {pattern['retailer']} ({pattern['page_type']}): "
                    f"{pattern['success_rate']*100:.1f}% success "
                    f"({pattern['failure_count']}/{pattern['total_attempts']} failed)"
                )
        
        logger.info("=" * 60)

