"""
Markdown Tower - Pattern Learner
Learn which LLMs work best per retailer over time

Target: <400 lines
"""

# Add shared path for imports
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../../Shared"))

import sqlite3
from typing import Dict, Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class MarkdownPatternLearner:
    """
    Learn markdown extraction patterns over time
    
    Tracks:
    - LLM performance per retailer (DeepSeek vs Gemini)
    - Chunking strategies that work
    - Extraction success rates
    - Processing times
    
    Purpose: Optimize which LLM to use first per retailer
    """
    
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.join(script_dir, '../..')
            db_path = os.path.join(project_root, 'Shared/markdown_patterns.db')
        
        self.db_path = db_path
        self._init_db()
        
        logger.info(f"✅ Markdown Pattern Learner initialized: {db_path}")
    
    def _init_db(self):
        """Initialize database schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS markdown_extraction_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                retailer TEXT NOT NULL,
                extraction_type TEXT NOT NULL,  -- 'catalog' or 'product'
                llm_used TEXT NOT NULL,  -- 'deepseek_v3' or 'gemini_flash_2.0'
                success BOOLEAN NOT NULL,
                processing_time REAL,
                markdown_size INTEGER,
                chunking_used BOOLEAN,
                validation_passed BOOLEAN,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_retailer_llm 
            ON markdown_extraction_performance(retailer, llm_used)
        ''')
        
        conn.commit()
        conn.close()
    
    def record_extraction(
        self,
        retailer: str,
        extraction_type: str,
        llm_used: str,
        success: bool,
        processing_time: float,
        markdown_size: int = 0,
        chunking_used: bool = False,
        validation_passed: bool = False
    ):
        """
        Record extraction performance
        
        Args:
            retailer: 'revolve', 'asos', etc.
            extraction_type: 'catalog' or 'product'
            llm_used: 'deepseek_v3' or 'gemini_flash_2.0'
            success: Did extraction succeed?
            processing_time: Time in seconds
            markdown_size: Size of markdown content
            chunking_used: Was chunking applied?
            validation_passed: Did validation pass?
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO markdown_extraction_performance
                (retailer, extraction_type, llm_used, success, processing_time, 
                 markdown_size, chunking_used, validation_passed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                retailer,
                extraction_type,
                llm_used,
                success,
                processing_time,
                markdown_size,
                chunking_used,
                validation_passed
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.debug(f"Failed to record extraction performance: {e}")
    
    def get_best_llm(
        self,
        retailer: str,
        extraction_type: str = 'product'
    ) -> str:
        """
        Get best performing LLM for a retailer
        
        Returns:
            'deepseek_v3' or 'gemini_flash_2.0'
            (defaults to 'deepseek_v3' if no data)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get success rates for each LLM (last 50 extractions)
            cursor.execute('''
                SELECT 
                    llm_used,
                    COUNT(*) as total,
                    SUM(CASE WHEN success THEN 1 ELSE 0 END) as successes,
                    AVG(processing_time) as avg_time
                FROM markdown_extraction_performance
                WHERE retailer = ? AND extraction_type = ?
                ORDER BY timestamp DESC
                LIMIT 50
            ''', (retailer, extraction_type))
            
            rows = cursor.fetchall()
            conn.close()
            
            if not rows:
                return 'deepseek_v3'  # Default
            
            # Calculate success rates
            best_llm = 'deepseek_v3'
            best_rate = 0.0
            
            for llm, total, successes, avg_time in rows:
                if total > 0:
                    rate = successes / total
                    if rate > best_rate:
                        best_rate = rate
                        best_llm = llm
            
            return best_llm
            
        except Exception as e:
            logger.debug(f"Failed to get best LLM: {e}")
            return 'deepseek_v3'  # Default
    
    def get_stats(self, retailer: Optional[str] = None) -> Dict:
        """
        Get extraction statistics
        
        Returns:
            Dict with success rates, average times, etc.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if retailer:
                cursor.execute('''
                    SELECT 
                        llm_used,
                        extraction_type,
                        COUNT(*) as total,
                        SUM(CASE WHEN success THEN 1 ELSE 0 END) as successes,
                        AVG(processing_time) as avg_time
                    FROM markdown_extraction_performance
                    WHERE retailer = ?
                    GROUP BY llm_used, extraction_type
                ''', (retailer,))
            else:
                cursor.execute('''
                    SELECT 
                        retailer,
                        llm_used,
                        COUNT(*) as total,
                        SUM(CASE WHEN success THEN 1 ELSE 0 END) as successes,
                        AVG(processing_time) as avg_time
                    FROM markdown_extraction_performance
                    GROUP BY retailer, llm_used
                ''')
            
            rows = cursor.fetchall()
            conn.close()
            
            return {'stats': rows}
            
        except Exception as e:
            logger.debug(f"Failed to get stats: {e}")
            return {}
