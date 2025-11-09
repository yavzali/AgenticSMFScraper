"""
Checkpoint Manager for Product Updater and New Product Importer
Tracks progress and enables resumability for long-running batch jobs
"""

import json
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from logger_config import setup_logging

logger = setup_logging(__name__)


class CheckpointManager:
    """
    Manages checkpoints for batch processing
    
    Features:
    - Auto-save every N products (default: 5)
    - Resume from last checkpoint
    - Track success/failure counts
    """
    
    def __init__(self, checkpoint_dir: str = None):
        if checkpoint_dir is None:
            checkpoint_dir = os.path.join(os.path.dirname(__file__), '../checkpoints')
        
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(exist_ok=True)
        
        self.current_checkpoint = None
        self.batch_id = None
        self.checkpoint_interval = 5
        
        logger.debug(f"Checkpoint Manager initialized: {self.checkpoint_dir}")
    
    def initialize_batch(self, batch_id: str, items: List, workflow_type: str = 'generic'):
        """
        Initialize a new batch or resume from existing checkpoint
        
        Args:
            batch_id: Unique batch identifier
            items: List of items to process (URLs or dicts)
            workflow_type: 'update' or 'import'
        """
        self.batch_id = batch_id
        checkpoint_path = self.checkpoint_dir / f"checkpoint_{batch_id}.json"
        
        # Try to load existing checkpoint
        if checkpoint_path.exists():
            logger.info(f"📂 Found existing checkpoint: {checkpoint_path}")
            try:
                with open(checkpoint_path, 'r') as f:
                    self.current_checkpoint = json.load(f)
                
                logger.info(f"📊 Resuming from checkpoint:")
                logger.info(f"   Processed: {len(self.current_checkpoint.get('processed_urls', []))}/{self.current_checkpoint.get('total_urls', 0)}")
                logger.info(f"   Successful: {self.current_checkpoint.get('successful_count', 0)}")
                logger.info(f"   Failed: {self.current_checkpoint.get('failed_count', 0)}")
                
            except Exception as e:
                logger.warning(f"Failed to load checkpoint: {e}")
                self.current_checkpoint = None
        
        # Create new checkpoint if none exists
        if not self.current_checkpoint:
            logger.info(f"📝 Creating new checkpoint for batch: {batch_id}")
            
            # Extract URLs from items (handles both List[str] and List[Dict])
            urls = []
            for item in items:
                if isinstance(item, str):
                    urls.append(item)
                elif isinstance(item, dict):
                    urls.append(item.get('url', ''))
            
            self.current_checkpoint = {
                'batch_id': batch_id,
                'workflow_type': workflow_type,
                'total_urls': len(urls),
                'all_urls': urls,
                'processed_urls': [],
                'successful_count': 0,
                'failed_count': 0,
                'created_at': datetime.utcnow().isoformat(),
                'last_checkpoint': datetime.utcnow().isoformat()
            }
            
            self._save_checkpoint()
    
    def update_progress(self, result: Dict[str, Any]):
        """
        Update checkpoint with single product result
        
        Args:
            result: Dict with 'url', 'success', and optionally 'shopify_id'
        """
        if not self.current_checkpoint:
            logger.warning("No active checkpoint to update")
            return
        
        url = result.get('url')
        if not url:
            return
        
        # Add to processed list
        if url not in self.current_checkpoint['processed_urls']:
            self.current_checkpoint['processed_urls'].append(url)
        
        # Update counts
        if result.get('success'):
            self.current_checkpoint['successful_count'] += 1
        else:
            self.current_checkpoint['failed_count'] += 1
        
        # Update timestamp
        self.current_checkpoint['last_checkpoint'] = datetime.utcnow().isoformat()
        
        # Auto-save every N products
        processed_count = len(self.current_checkpoint['processed_urls'])
        if processed_count % self.checkpoint_interval == 0:
            self._save_checkpoint()
            logger.debug(f"💾 Checkpoint saved at {processed_count} products")
    
    def get_remaining_urls(self) -> List[str]:
        """
        Get list of URLs that haven't been processed yet
        
        Returns:
            List of unprocessed URLs
        """
        if not self.current_checkpoint:
            return []
        
        all_urls = self.current_checkpoint.get('all_urls', [])
        processed = set(self.current_checkpoint.get('processed_urls', []))
        
        remaining = [url for url in all_urls if url not in processed]
        return remaining
    
    def is_complete(self) -> bool:
        """Check if all URLs have been processed"""
        if not self.current_checkpoint:
            return True
        
        total = self.current_checkpoint.get('total_urls', 0)
        processed = len(self.current_checkpoint.get('processed_urls', []))
        
        return processed >= total
    
    def finalize(self):
        """Finalize checkpoint and optionally clean up"""
        if not self.current_checkpoint:
            return
        
        self.current_checkpoint['completed_at'] = datetime.utcnow().isoformat()
        self._save_checkpoint()
        
        logger.info(f"✅ Checkpoint finalized:")
        logger.info(f"   Total: {self.current_checkpoint['total_urls']}")
        logger.info(f"   Processed: {len(self.current_checkpoint['processed_urls'])}")
        logger.info(f"   Successful: {self.current_checkpoint['successful_count']}")
        logger.info(f"   Failed: {self.current_checkpoint['failed_count']}")
    
    def delete_checkpoint(self):
        """Delete checkpoint file (after successful completion)"""
        if not self.batch_id:
            return
        
        checkpoint_path = self.checkpoint_dir / f"checkpoint_{self.batch_id}.json"
        if checkpoint_path.exists():
            checkpoint_path.unlink()
            logger.info(f"🗑️ Deleted checkpoint: {checkpoint_path}")
    
    def _save_checkpoint(self):
        """Save current checkpoint to disk"""
        if not self.current_checkpoint or not self.batch_id:
            return
        
        checkpoint_path = self.checkpoint_dir / f"checkpoint_{self.batch_id}.json"
        
        try:
            with open(checkpoint_path, 'w') as f:
                json.dump(self.current_checkpoint, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
    
    def should_save_checkpoint(self, current_index: int) -> bool:
        """
        Determine if a checkpoint should be saved based on frequency
        (for compatibility with old system)
        """
        # Save checkpoint every 5 URLs or if this is the first/last item
        checkpoint_frequency = 5
        
        if current_index == 0:  # First item
            return True
        elif current_index % checkpoint_frequency == 0:  # Every N items
            return True
        elif current_index == self.current_checkpoint.get('total_urls', 0) - 1:  # Last item
            return True
        else:
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current checkpoint statistics"""
        if not self.current_checkpoint:
            return {}
        
        return {
            'batch_id': self.current_checkpoint.get('batch_id'),
            'total_urls': self.current_checkpoint.get('total_urls', 0),
            'processed': len(self.current_checkpoint.get('processed_urls', [])),
            'successful': self.current_checkpoint.get('successful_count', 0),
            'failed': self.current_checkpoint.get('failed_count', 0),
            'remaining': len(self.get_remaining_urls())
        }

