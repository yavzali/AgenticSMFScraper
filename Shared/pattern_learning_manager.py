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

