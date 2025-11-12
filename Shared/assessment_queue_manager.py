"""
Assessment Queue Manager
Manages the queue of products awaiting human review

Two Types of Reviews:
1. MODESTY Assessment: New products needing modesty classification
2. DUPLICATION Assessment: Suspected duplicates needing human confirmation

Integrates with:
- Catalog Monitor workflow (adds products to queue)
- Web Assessment Interface (retrieves and marks as reviewed)
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

import json
import sqlite3
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging
import asyncio

from logger_config import setup_logging

logger = setup_logging(__name__)


@dataclass
class QueueItem:
    """Single item in assessment queue"""
    id: int
    product_url: str
    retailer: str
    category: str
    review_type: str  # 'modesty' or 'duplication'
    priority: str  # 'high', 'normal', 'low'
    status: str  # 'pending', 'reviewed', 'skipped'
    product_data: Dict
    suspected_match_data: Optional[Dict]
    review_decision: Optional[str]
    reviewer_notes: Optional[str]
    reviewed_at: Optional[datetime]
    reviewed_by: Optional[str]
    added_at: datetime
    source_workflow: str


class AssessmentQueueManager:
    """
    Manages the assessment queue for human review
    
    Features:
    - Add products to queue (with priority)
    - Retrieve next product for review (by type)
    - Mark products as reviewed
    - Record review decisions
    - Queue statistics
    - Cleanup old reviewed items
    """
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            # Default to products.db in Shared folder
            db_path = os.path.join(os.path.dirname(__file__), 'products.db')
        
        self.db_path = db_path
        self._ensure_table_exists()
        logger.info(f"✅ Assessment Queue Manager initialized: {db_path}")
    
    def _ensure_table_exists(self):
        """Create assessment_queue table if it doesn't exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS assessment_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_url TEXT NOT NULL,
                retailer TEXT NOT NULL,
                category TEXT,
                review_type TEXT NOT NULL,
                priority TEXT NOT NULL DEFAULT 'normal',
                status TEXT NOT NULL DEFAULT 'pending',
                
                -- Product data (JSON)
                product_data TEXT NOT NULL,
                
                -- For duplication review
                suspected_match_data TEXT,
                
                -- Review results
                review_decision TEXT,
                reviewer_notes TEXT,
                reviewed_at TIMESTAMP,
                reviewed_by TEXT,
                
                -- Metadata
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                source_workflow TEXT,
                
                -- Prevent duplicate entries
                UNIQUE(product_url, review_type)
            )
        ''')
        
        # Create indexes
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_queue_review_type_status 
            ON assessment_queue(review_type, status, priority)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_queue_priority 
            ON assessment_queue(priority, status)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_queue_status 
            ON assessment_queue(status)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_queue_added_at 
            ON assessment_queue(added_at)
        ''')
        
        conn.commit()
        conn.close()
        
        logger.debug("Assessment queue table and indexes verified")
    
    async def add_to_queue(
        self,
        product: Dict,
        retailer: str,
        category: str,
        review_type: str,  # 'modesty' or 'duplication'
        priority: str = 'normal',  # 'high', 'normal', 'low'
        source_workflow: str = 'catalog_monitor',
        suspected_match: Optional[Dict] = None
    ) -> int:
        """
        Add product to assessment queue
        
        Args:
            product: Dict with product data (url, title, price, images, etc.)
            retailer: Retailer name
            category: Product category
            review_type: 'modesty' or 'duplication'
            priority: 'high', 'normal', or 'low'
            source_workflow: Source workflow name
            suspected_match: For duplication review - matched product data
            
        Returns:
            Queue item ID (or existing ID if duplicate)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            product_url = product.get('url')
            if not product_url:
                raise ValueError("Product must have 'url' field")
            
            # Serialize data to JSON
            product_json = json.dumps(product)
            match_json = json.dumps(suspected_match) if suspected_match else None
            
            # Try to insert (will fail if duplicate URL + review_type)
            try:
                cursor.execute('''
                    INSERT INTO assessment_queue 
                    (product_url, retailer, category, review_type, priority, status,
                     product_data, suspected_match_data, source_workflow)
                    VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?)
                ''', (product_url, retailer, category, review_type, priority,
                      product_json, match_json, source_workflow))
                
                queue_id = cursor.lastrowid
                conn.commit()
                
                # Update assessment_status in products table
                self._update_product_assessment_status(product_url, 'queued')
                
                logger.info(f"Added to queue: {review_type} review for {retailer} - {product.get('title', 'N/A')} (ID: {queue_id})")
                
            except sqlite3.IntegrityError:
                # Already exists - get existing ID
                cursor.execute('''
                    SELECT id FROM assessment_queue 
                    WHERE product_url = ? AND review_type = ?
                ''', (product_url, review_type))
                
                result = cursor.fetchone()
                queue_id = result[0] if result else None
                
                logger.debug(f"Product already in queue: {product_url} ({review_type}) - ID: {queue_id}")
            
            conn.close()
            return queue_id
            
        except Exception as e:
            logger.error(f"Failed to add product to queue: {e}")
            raise
    
    async def get_next_for_review(
        self,
        review_type: str,  # 'modesty' or 'duplication'
        priority_order: bool = True
    ) -> Optional[QueueItem]:
        """
        Get next product for review
        
        Args:
            review_type: 'modesty' or 'duplication'
            priority_order: If True, prioritize by priority then FIFO
            
        Returns:
            QueueItem or None if queue is empty
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            if priority_order:
                # Order by priority (high > normal > low) then oldest first
                order_clause = '''
                    ORDER BY 
                        CASE priority 
                            WHEN 'high' THEN 1 
                            WHEN 'normal' THEN 2 
                            WHEN 'low' THEN 3 
                        END,
                        added_at ASC
                '''
            else:
                # Simple FIFO
                order_clause = 'ORDER BY added_at ASC'
            
            query = f'''
                SELECT * FROM assessment_queue 
                WHERE review_type = ? AND status = 'pending'
                {order_clause}
                LIMIT 1
            '''
            
            cursor.execute(query, (review_type,))
            row = cursor.fetchone()
            
            if not row:
                conn.close()
                return None
            
            # Parse JSON fields
            product_data = json.loads(row['product_data'])
            suspected_match = json.loads(row['suspected_match_data']) if row['suspected_match_data'] else None
            
            queue_item = QueueItem(
                id=row['id'],
                product_url=row['product_url'],
                retailer=row['retailer'],
                category=row['category'],
                review_type=row['review_type'],
                priority=row['priority'],
                status=row['status'],
                product_data=product_data,
                suspected_match_data=suspected_match,
                review_decision=row['review_decision'],
                reviewer_notes=row['reviewer_notes'],
                reviewed_at=row['reviewed_at'],
                reviewed_by=row['reviewed_by'],
                added_at=row['added_at'],
                source_workflow=row['source_workflow']
            )
            
            conn.close()
            return queue_item
            
        except Exception as e:
            logger.error(f"Failed to get next item for review: {e}")
            return None
    
    async def mark_as_reviewed(
        self,
        queue_id: int,
        decision: str,  # 'modest', 'moderately_modest', 'not_modest', 'duplicate', 'not_duplicate'
        reviewer_notes: str = None,
        reviewed_by: str = 'web_interface'
    ) -> bool:
        """
        Mark product as reviewed
        
        Args:
            queue_id: Queue item ID
            decision: Review decision
            reviewer_notes: Optional notes
            reviewed_by: Reviewer identifier
            
        Returns:
            True if successful
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get product_url before updating
            cursor.execute('SELECT product_url FROM assessment_queue WHERE id = ?', (queue_id,))
            row = cursor.fetchone()
            product_url = row[0] if row else None
            
            cursor.execute('''
                UPDATE assessment_queue 
                SET status = 'reviewed',
                    review_decision = ?,
                    reviewer_notes = ?,
                    reviewed_at = ?,
                    reviewed_by = ?
                WHERE id = ?
            ''', (decision, reviewer_notes, datetime.utcnow().isoformat(), reviewed_by, queue_id))
            
            conn.commit()
            affected = cursor.rowcount
            conn.close()
            
            if affected > 0:
                # Update assessment_status in products table
                if product_url:
                    self._update_product_assessment_status(product_url, 'assessed')
                
                logger.info(f"Marked queue item {queue_id} as reviewed: {decision}")
                return True
            else:
                logger.warning(f"Queue item {queue_id} not found")
                return False
                
        except Exception as e:
            logger.error(f"Failed to mark as reviewed: {e}")
            return False
    
    async def skip_product(
        self,
        queue_id: int,
        reason: str = None
    ) -> bool:
        """
        Skip product (mark as skipped, will not appear in queue again)
        
        Args:
            queue_id: Queue item ID
            reason: Optional reason for skipping
            
        Returns:
            True if successful
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE assessment_queue 
                SET status = 'skipped',
                    reviewer_notes = ?,
                    reviewed_at = ?
                WHERE id = ?
            ''', (reason, datetime.utcnow().isoformat(), queue_id))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Skipped queue item {queue_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to skip product: {e}")
            return False
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """
        Get queue statistics
        
        Returns:
            Dict with queue statistics
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Overall stats
            cursor.execute('''
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN status = 'reviewed' THEN 1 ELSE 0 END) as reviewed,
                    SUM(CASE WHEN status = 'skipped' THEN 1 ELSE 0 END) as skipped
                FROM assessment_queue
            ''')
            overall = cursor.fetchone()
            
            # By review type
            cursor.execute('''
                SELECT 
                    review_type,
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN priority = 'high' AND status = 'pending' THEN 1 ELSE 0 END) as high_priority
                FROM assessment_queue
                GROUP BY review_type
            ''')
            by_type = {row[0]: {'total': row[1], 'pending': row[2], 'high_priority': row[3]} 
                      for row in cursor.fetchall()}
            
            # Recent activity (last 24 hours)
            cursor.execute('''
                SELECT COUNT(*) 
                FROM assessment_queue 
                WHERE reviewed_at >= datetime('now', '-1 day')
            ''')
            reviewed_24h = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                'overall': {
                    'total': overall[0],
                    'pending': overall[1],
                    'reviewed': overall[2],
                    'skipped': overall[3]
                },
                'by_review_type': by_type,
                'recent_activity': {
                    'reviewed_last_24h': reviewed_24h
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get queue stats: {e}")
            return {}
    
    async def clear_reviewed_items(self, days_old: int = 30) -> int:
        """
        Clear old reviewed/skipped items from queue
        
        Args:
            days_old: Remove items reviewed more than this many days ago
            
        Returns:
            Number of items removed
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cutoff = (datetime.utcnow() - timedelta(days=days_old)).isoformat()
            
            cursor.execute('''
                DELETE FROM assessment_queue 
                WHERE status IN ('reviewed', 'skipped')
                AND reviewed_at < ?
            ''', (cutoff,))
            
            removed = cursor.rowcount
            conn.commit()
            conn.close()
            
            logger.info(f"Cleared {removed} old reviewed/skipped items (>{days_old} days)")
            return removed
            
        except Exception as e:
            logger.error(f"Failed to clear reviewed items: {e}")
            return 0
    
    async def get_queue_items(
        self,
        review_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[QueueItem]:
        """
        Get multiple queue items (for batch operations)
        
        Args:
            review_type: Filter by review type
            status: Filter by status
            limit: Maximum items to return
            
        Returns:
            List of QueueItem objects
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = 'SELECT * FROM assessment_queue WHERE 1=1'
            params = []
            
            if review_type:
                query += ' AND review_type = ?'
                params.append(review_type)
            
            if status:
                query += ' AND status = ?'
                params.append(status)
            
            query += ' ORDER BY added_at DESC LIMIT ?'
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            items = []
            for row in rows:
                product_data = json.loads(row['product_data'])
                suspected_match = json.loads(row['suspected_match_data']) if row['suspected_match_data'] else None
                
                items.append(QueueItem(
                    id=row['id'],
                    product_url=row['product_url'],
                    retailer=row['retailer'],
                    category=row['category'],
                    review_type=row['review_type'],
                    priority=row['priority'],
                    status=row['status'],
                    product_data=product_data,
                    suspected_match_data=suspected_match,
                    review_decision=row['review_decision'],
                    reviewer_notes=row['reviewer_notes'],
                    reviewed_at=row['reviewed_at'],
                    reviewed_by=row['reviewed_by'],
                    added_at=row['added_at'],
                    source_workflow=row['source_workflow']
                ))
            
            conn.close()
            return items
            
        except Exception as e:
            logger.error(f"Failed to get queue items: {e}")
            return []
    
    def _update_product_assessment_status(self, product_url: str, status: str):
        """Update assessment_status in products table (synchronous)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE products 
                SET assessment_status = ?, last_updated = ?
                WHERE url = ?
            ''', (status, datetime.utcnow().isoformat(), product_url))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.debug(f"Could not update assessment_status for {product_url}: {e}")


# CLI for testing
if __name__ == "__main__":
    import asyncio
    
    async def test_queue():
        """Test queue operations"""
        manager = AssessmentQueueManager()
        
        # Add test product
        test_product = {
            'url': 'https://www.revolve.com/test/dp/TEST123/',
            'title': 'Test Dress',
            'price': '$99.00',
            'images': ['https://example.com/image.jpg']
        }
        
        # Add to queue
        queue_id = await manager.add_to_queue(
            product=test_product,
            retailer='revolve',
            category='dresses',
            review_type='modesty',
            priority='normal'
        )
        print(f"Added to queue: {queue_id}")
        
        # Get stats
        stats = await manager.get_queue_stats()
        print(f"Queue stats: {json.dumps(stats, indent=2)}")
        
        # Get next for review
        next_item = await manager.get_next_for_review('modesty')
        if next_item:
            print(f"Next for review: {next_item.product_data['title']}")
            
            # Mark as reviewed
            await manager.mark_as_reviewed(
                next_item.id,
                'modest',
                'Test review'
            )
            print("Marked as reviewed")
        
        # Get updated stats
        stats = await manager.get_queue_stats()
        print(f"Updated stats: {json.dumps(stats, indent=2)}")
    
    asyncio.run(test_queue())

