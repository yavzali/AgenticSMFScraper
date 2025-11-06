"""
Page Structure Learner - Learns and tracks retailer page structures over time
Enables Patchright to get smarter with each extraction and detect page changes
"""

import json
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class PageStructurePattern:
    """Represents a learned pattern for extracting data from a retailer's page"""
    retailer: str
    pattern_type: str  # 'selector', 'layout', 'visual_marker'
    element_type: str  # 'title', 'price', 'image', 'description', etc.
    pattern_data: str  # CSS selector, XPath, or visual description
    confidence_score: float  # 0.0-1.0, increases with successful uses
    success_count: int
    failure_count: int
    last_success: Optional[str]  # ISO datetime
    last_failure: Optional[str]  # ISO datetime
    created_at: str  # ISO datetime
    visual_hints: Optional[Dict]  # Gemini's visual description {"location": "top-right", "style": "red text"}

@dataclass
class PageStructureSnapshot:
    """Snapshot of a page's structure at a point in time"""
    retailer: str
    snapshot_date: str  # ISO datetime
    dom_structure_hash: str  # Hash of key DOM elements
    visual_layout_hash: str  # Hash of Gemini's layout description
    key_selectors: Dict[str, str]  # {element_type: selector}
    layout_description: str  # Gemini's description of page layout
    screenshot_metadata: Dict  # Information about what was visible

class PageStructureLearner:
    """
    Learns page structures from successful extractions and detects changes
    Enables Gemini → DOM collaboration and adaptive extraction
    """
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = str(Path(__file__).parent / "page_structures.db")
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database for pattern storage"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS page_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    retailer TEXT NOT NULL,
                    pattern_type TEXT NOT NULL,
                    element_type TEXT NOT NULL,
                    pattern_data TEXT NOT NULL,
                    confidence_score REAL DEFAULT 0.5,
                    success_count INTEGER DEFAULT 0,
                    failure_count INTEGER DEFAULT 0,
                    last_success TEXT,
                    last_failure TEXT,
                    created_at TEXT NOT NULL,
                    visual_hints TEXT,
                    UNIQUE(retailer, pattern_type, element_type, pattern_data)
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS page_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    retailer TEXT NOT NULL,
                    snapshot_date TEXT NOT NULL,
                    dom_structure_hash TEXT NOT NULL,
                    visual_layout_hash TEXT NOT NULL,
                    key_selectors TEXT NOT NULL,
                    layout_description TEXT,
                    screenshot_metadata TEXT,
                    UNIQUE(retailer, snapshot_date)
                )
            """)
            
            # Table for tracking extraction method performance (Patchright-specific)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS extraction_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    retailer TEXT NOT NULL,
                    extraction_date TEXT NOT NULL,
                    gemini_success BOOLEAN,
                    gemini_extraction_time REAL,
                    gemini_completeness REAL,
                    dom_needed BOOLEAN,
                    dom_gaps_filled TEXT,
                    dom_extraction_time REAL,
                    total_time REAL,
                    final_completeness REAL,
                    method_used TEXT
                )
            """)
            
            # Indexes for performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_patterns_retailer ON page_patterns(retailer)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_patterns_confidence ON page_patterns(confidence_score DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_retailer ON page_snapshots(retailer)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_extraction_retailer ON extraction_performance(retailer)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_extraction_date ON extraction_performance(extraction_date DESC)")
            
            conn.commit()
        
        logger.info("✅ Page Structure Learner database initialized")
    
    def record_successful_extraction(self, 
                                     retailer: str,
                                     element_type: str,
                                     selector: str,
                                     visual_hint: Optional[Dict] = None):
        """Record a successful extraction using a specific selector"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Check if pattern exists
                cursor = conn.execute("""
                    SELECT id, confidence_score, success_count, failure_count
                    FROM page_patterns
                    WHERE retailer = ? AND pattern_type = 'selector' 
                    AND element_type = ? AND pattern_data = ?
                """, (retailer, element_type, selector))
                
                existing = cursor.fetchone()
                now = datetime.utcnow().isoformat()
                
                if existing:
                    # Update existing pattern
                    pattern_id, confidence, successes, failures = existing
                    new_confidence = min(1.0, confidence + 0.05)  # Increase confidence
                    
                    conn.execute("""
                        UPDATE page_patterns
                        SET confidence_score = ?,
                            success_count = success_count + 1,
                            last_success = ?,
                            visual_hints = ?
                        WHERE id = ?
                    """, (new_confidence, now, json.dumps(visual_hint) if visual_hint else None, pattern_id))
                else:
                    # Create new pattern
                    conn.execute("""
                        INSERT INTO page_patterns
                        (retailer, pattern_type, element_type, pattern_data, confidence_score,
                         success_count, last_success, created_at, visual_hints)
                        VALUES (?, 'selector', ?, ?, 0.7, 1, ?, ?, ?)
                    """, (retailer, element_type, selector, now, now, 
                         json.dumps(visual_hint) if visual_hint else None))
                
                conn.commit()
                logger.debug(f"✅ Recorded successful pattern: {retailer} → {element_type} → {selector}")
                
        except Exception as e:
            logger.error(f"Failed to record successful extraction: {e}")
    
    def record_failed_extraction(self, retailer: str, element_type: str, selector: str):
        """Record a failed extraction attempt"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT id, confidence_score FROM page_patterns
                    WHERE retailer = ? AND pattern_type = 'selector'
                    AND element_type = ? AND pattern_data = ?
                """, (retailer, element_type, selector))
                
                existing = cursor.fetchone()
                now = datetime.utcnow().isoformat()
                
                if existing:
                    pattern_id, confidence = existing
                    new_confidence = max(0.0, confidence - 0.1)  # Decrease confidence
                    
                    conn.execute("""
                        UPDATE page_patterns
                        SET confidence_score = ?,
                            failure_count = failure_count + 1,
                            last_failure = ?
                        WHERE id = ?
                    """, (new_confidence, now, pattern_id))
                    
                    conn.commit()
                    logger.debug(f"⚠️ Recorded failed pattern: {retailer} → {element_type} → {selector}")
                
        except Exception as e:
            logger.error(f"Failed to record failed extraction: {e}")
    
    def get_best_patterns(self, retailer: str, element_type: Optional[str] = None) -> List[Dict]:
        """Get highest-confidence patterns for a retailer"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                if element_type:
                    cursor = conn.execute("""
                        SELECT pattern_type, element_type, pattern_data, confidence_score, 
                               success_count, failure_count, visual_hints
                        FROM page_patterns
                        WHERE retailer = ? AND element_type = ?
                        ORDER BY confidence_score DESC, success_count DESC
                        LIMIT 10
                    """, (retailer, element_type))
                else:
                    cursor = conn.execute("""
                        SELECT pattern_type, element_type, pattern_data, confidence_score,
                               success_count, failure_count, visual_hints
                        FROM page_patterns
                        WHERE retailer = ?
                        ORDER BY confidence_score DESC, success_count DESC
                        LIMIT 50
                    """, (retailer,))
                
                results = []
                for row in cursor.fetchall():
                    visual_hints = json.loads(row[6]) if row[6] else None
                    results.append({
                        'pattern_type': row[0],
                        'element_type': row[1],
                        'pattern_data': row[2],
                        'confidence_score': row[3],
                        'success_count': row[4],
                        'failure_count': row[5],
                        'visual_hints': visual_hints
                    })
                
                return results
                
        except Exception as e:
            logger.error(f"Failed to get best patterns: {e}")
            return []
    
    def save_page_snapshot(self,
                          retailer: str,
                          dom_structure_hash: str,
                          visual_layout_hash: str,
                          key_selectors: Dict[str, str],
                          layout_description: str,
                          screenshot_metadata: Dict):
        """Save a snapshot of the current page structure"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                now = datetime.utcnow().isoformat()
                
                conn.execute("""
                    INSERT OR REPLACE INTO page_snapshots
                    (retailer, snapshot_date, dom_structure_hash, visual_layout_hash,
                     key_selectors, layout_description, screenshot_metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (retailer, now, dom_structure_hash, visual_layout_hash,
                     json.dumps(key_selectors), layout_description,
                     json.dumps(screenshot_metadata)))
                
                conn.commit()
                logger.info(f"📸 Saved page snapshot for {retailer}")
                
        except Exception as e:
            logger.error(f"Failed to save page snapshot: {e}")
    
    def detect_page_structure_change(self, retailer: str, 
                                    current_dom_hash: str,
                                    current_visual_hash: str) -> Dict:
        """
        Detect if page structure has changed significantly
        Returns: {
            'changed': bool,
            'severity': 'none'|'minor'|'major',
            'last_snapshot_date': str,
            'recommendations': List[str]
        }
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Get most recent snapshot
                cursor = conn.execute("""
                    SELECT snapshot_date, dom_structure_hash, visual_layout_hash, key_selectors
                    FROM page_snapshots
                    WHERE retailer = ?
                    ORDER BY snapshot_date DESC
                    LIMIT 1
                """, (retailer,))
                
                last_snapshot = cursor.fetchone()
                
                if not last_snapshot:
                    return {
                        'changed': False,
                        'severity': 'none',
                        'last_snapshot_date': None,
                        'recommendations': ['First snapshot - no baseline to compare']
                    }
                
                last_date, last_dom_hash, last_visual_hash, last_selectors_json = last_snapshot
                
                # Compare hashes
                dom_changed = (current_dom_hash != last_dom_hash)
                visual_changed = (current_visual_hash != last_visual_hash)
                
                severity = 'none'
                recommendations = []
                
                if dom_changed and visual_changed:
                    severity = 'major'
                    recommendations.append('Major page redesign detected')
                    recommendations.append('Re-learn selectors for this retailer')
                    recommendations.append('Consider manual review of extraction patterns')
                elif dom_changed or visual_changed:
                    severity = 'minor'
                    recommendations.append('Minor page changes detected')
                    recommendations.append('Monitor extraction success rate')
                
                return {
                    'changed': dom_changed or visual_changed,
                    'severity': severity,
                    'last_snapshot_date': last_date,
                    'recommendations': recommendations
                }
                
        except Exception as e:
            logger.error(f"Failed to detect page change: {e}")
            return {
                'changed': False,
                'severity': 'unknown',
                'last_snapshot_date': None,
                'recommendations': [f'Error checking: {e}']
            }
    
    def record_extraction_performance(self,
                                      retailer: str,
                                      gemini_success: bool,
                                      gemini_time: float,
                                      gemini_completeness: float,
                                      dom_needed: bool,
                                      dom_gaps: List[str],
                                      dom_time: float,
                                      total_time: float,
                                      final_completeness: float,
                                      method_used: str,
                                      validation_stats: Dict = None):
        """
        Record performance metrics for Patchright extraction
        Now includes optional validation statistics for catalog extraction
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                now = datetime.utcnow().isoformat()
                
                # Store validation stats as JSON if provided
                validation_json = json.dumps(validation_stats) if validation_stats else None
                
                conn.execute("""
                    INSERT INTO extraction_performance
                    (retailer, extraction_date, gemini_success, gemini_extraction_time,
                     gemini_completeness, dom_needed, dom_gaps_filled, dom_extraction_time,
                     total_time, final_completeness, method_used)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (retailer, now, gemini_success, gemini_time, gemini_completeness,
                     dom_needed, json.dumps(dom_gaps), dom_time, total_time,
                     final_completeness, method_used))
                
                # If validation stats provided, also record those
                if validation_stats:
                    # Add validation metadata to a separate tracking system
                    logger.debug(f"Validation stats: {validation_stats.get('validations_performed', 0)} checks, "
                               f"{validation_stats.get('mismatches_found', 0)} corrections")
                
                conn.commit()
                logger.debug(f"Recorded extraction performance for {retailer}")
                
        except Exception as e:
            logger.error(f"Failed to record extraction performance: {e}")
    
    def get_extraction_stats(self, retailer: str, days: int = 30) -> Dict:
        """Get extraction performance stats for a retailer"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                from datetime import timedelta
                cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
                
                cursor = conn.execute("""
                    SELECT 
                        COUNT(*) as total_extractions,
                        AVG(CASE WHEN gemini_success THEN 1 ELSE 0 END) as gemini_success_rate,
                        AVG(gemini_completeness) as avg_gemini_completeness,
                        AVG(CASE WHEN dom_needed THEN 1 ELSE 0 END) as dom_needed_rate,
                        AVG(total_time) as avg_total_time,
                        AVG(final_completeness) as avg_final_completeness
                    FROM extraction_performance
                    WHERE retailer = ? AND extraction_date > ?
                """, (retailer, cutoff_date))
                
                row = cursor.fetchone()
                
                if row and row[0] > 0:
                    return {
                        'retailer': retailer,
                        'period_days': days,
                        'total_extractions': row[0],
                        'gemini_success_rate': round(row[1] * 100, 1) if row[1] else 0,
                        'avg_gemini_completeness': round(row[2] * 100, 1) if row[2] else 0,
                        'dom_assistance_rate': round(row[3] * 100, 1) if row[3] else 0,
                        'avg_extraction_time': round(row[4], 1) if row[4] else 0,
                        'avg_final_completeness': round(row[5] * 100, 1) if row[5] else 0
                    }
                
                return {'retailer': retailer, 'total_extractions': 0}
                
        except Exception as e:
            logger.error(f"Failed to get extraction stats: {e}")
            return {}
    
    def get_stats(self, retailer: Optional[str] = None) -> Dict:
        """Get statistics about learned patterns"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                if retailer:
                    # Retailer-specific stats
                    cursor = conn.execute("""
                        SELECT 
                            COUNT(*) as total_patterns,
                            AVG(confidence_score) as avg_confidence,
                            SUM(success_count) as total_successes,
                            SUM(failure_count) as total_failures,
                            COUNT(DISTINCT element_type) as unique_elements
                        FROM page_patterns
                        WHERE retailer = ?
                    """, (retailer,))
                    
                    row = cursor.fetchone()
                    
                    # Get snapshot count
                    snapshot_cursor = conn.execute("""
                        SELECT COUNT(*) FROM page_snapshots WHERE retailer = ?
                    """, (retailer,))
                    snapshot_count = snapshot_cursor.fetchone()[0]
                    
                    return {
                        'retailer': retailer,
                        'total_patterns': row[0],
                        'avg_confidence': round(row[1], 2) if row[1] else 0,
                        'total_successes': row[2] or 0,
                        'total_failures': row[3] or 0,
                        'unique_elements': row[4] or 0,
                        'snapshots_saved': snapshot_count,
                        'success_rate': round((row[2] / (row[2] + row[3]) * 100), 1) if (row[2] + row[3]) > 0 else 0
                    }
                else:
                    # Global stats
                    cursor = conn.execute("""
                        SELECT 
                            COUNT(*) as total_patterns,
                            COUNT(DISTINCT retailer) as retailers_learned,
                            AVG(confidence_score) as avg_confidence,
                            SUM(success_count) as total_successes,
                            SUM(failure_count) as total_failures
                        FROM page_patterns
                    """)
                    
                    row = cursor.fetchone()
                    
                    return {
                        'total_patterns': row[0],
                        'retailers_learned': row[1],
                        'avg_confidence': round(row[2], 2) if row[2] else 0,
                        'total_successes': row[3] or 0,
                        'total_failures': row[4] or 0,
                        'success_rate': round((row[3] / (row[3] + row[4]) * 100), 1) if (row[3] + row[4]) > 0 else 0
                    }
                    
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}

