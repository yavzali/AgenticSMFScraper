"""
Checkpoint Manager - Handles state persistence and resume functionality
"""

import json
import os
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pathlib import Path

from logger_config import setup_logging

logger = setup_logging(__name__)

class CheckpointManager:
    def __init__(self, checkpoint_file: str = "processing_state.json"):
        self.checkpoint_file = checkpoint_file
        self.current_state = {}
    
    def initialize_batch(self, batch_id: str, urls: List[str], modesty_level: str):
        """Initialize a new batch for checkpoint tracking"""
        
        self.current_state = {
            'batch_id': batch_id,
            'batch_start_time': datetime.utcnow().isoformat(),
            'total_urls': len(urls),
            'processed_count': 0,
            'successful_count': 0,
            'failed_count': 0,
            'manual_review_count': 0,
            'modesty_level': modesty_level,
            'remaining_urls': [{'url': url, 'modesty_level': modesty_level} for url in urls],
            'failed_urls': [],
            'completed_urls': [],
            'current_position': 0,
            'last_checkpoint': datetime.utcnow().isoformat(),
            'estimated_completion': self._estimate_completion_time(len(urls)),
            'processing_stats': {
                'avg_time_per_url': 45.0,  # Initial estimate
                'total_processing_time': 0,
                'retailer_performance': {},
                'method_performance': {}
            }
        }
        
        logger.info(f"Initialized batch checkpoint: {batch_id} with {len(urls)} URLs")
    
    async def save_checkpoint(self, batch_id: str, current_results: Dict, remaining_urls: List[str]):
        """Save current processing state to checkpoint file"""
        
        try:
            # Update current state
            self.current_state.update({
                'batch_id': batch_id,
                'processed_count': current_results.get('processed_count', 0),
                'successful_count': current_results.get('successful_count', 0),
                'failed_count': current_results.get('failed_count', 0),
                'manual_review_count': current_results.get('manual_review_count', 0),
                'remaining_urls': [{'url': url, 'modesty_level': self.current_state.get('modesty_level', 'modest')} 
                                 for url in remaining_urls],
                'last_checkpoint': datetime.utcnow().isoformat(),
                'estimated_completion': self._estimate_completion_time(len(remaining_urls))
            })
            
            # Update processing stats
            if current_results.get('processing_details'):
                self._update_processing_stats(current_results['processing_details'])
            
            # Save to file
            with open(self.checkpoint_file, 'w') as f:
                json.dump(self.current_state, f, indent=2)
            
            # Safe access to total_urls for logging
            total_urls = self.current_state.get('total_urls', 'unknown')
            processed_count = self.current_state.get('processed_count', 0)
            logger.debug(f"Checkpoint saved: {processed_count}/{total_urls} completed")
        
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
    
    def save_checkpoint_immediately(self):
        """Save current state immediately (for graceful shutdown)"""
        
        try:
            if self.current_state:
                self.current_state['last_checkpoint'] = datetime.utcnow().isoformat()
                self.current_state['graceful_shutdown'] = True
                
                with open(self.checkpoint_file, 'w') as f:
                    json.dump(self.current_state, f, indent=2)
                
                logger.info("Emergency checkpoint saved for graceful shutdown")
        
        except Exception as e:
            logger.error(f"Failed to save emergency checkpoint: {e}")
    
    def resume_from_checkpoint(self) -> Optional[Dict]:
        """Resume processing from last checkpoint"""
        
        try:
            if not os.path.exists(self.checkpoint_file):
                logger.info("No checkpoint file found")
                return None
            
            with open(self.checkpoint_file, 'r') as f:
                checkpoint_data = json.load(f)
            
            # Validate checkpoint data
            if not self._validate_checkpoint(checkpoint_data):
                logger.warning("Invalid checkpoint data, cannot resume")
                return None
            
            # Check if checkpoint is too old (more than 24 hours)
            last_checkpoint = datetime.fromisoformat(checkpoint_data['last_checkpoint'])
            if datetime.utcnow() - last_checkpoint > timedelta(hours=24):
                logger.warning("Checkpoint is too old (>24h), starting fresh")
                return None
            
            remaining_urls = [item['url'] for item in checkpoint_data.get('remaining_urls', [])]
            modesty_level = checkpoint_data.get('modesty_level', 'modest')
            
            logger.info(f"Resuming batch {checkpoint_data['batch_id']}: "
                       f"{checkpoint_data['processed_count']}/{checkpoint_data['total_urls']} completed, "
                       f"{len(remaining_urls)} remaining")
            
            return {
                'batch_id': checkpoint_data['batch_id'],
                'urls': remaining_urls,
                'modesty_level': modesty_level,
                'resuming': True,
                'previous_results': {
                    'processed_count': checkpoint_data['processed_count'],
                    'successful_count': checkpoint_data['successful_count'],
                    'failed_count': checkpoint_data['failed_count'],
                    'manual_review_count': checkpoint_data['manual_review_count']
                }
            }
        
        except Exception as e:
            logger.error(f"Failed to resume from checkpoint: {e}")
            return None
    
    def save_scheduled_batch(self, batch_data: Dict, scheduled_time: datetime):
        """Save batch for scheduled execution"""
        
        try:
            scheduled_state = {
                'type': 'scheduled_batch',
                'batch_data': batch_data,
                'scheduled_time': scheduled_time.isoformat(),
                'created_time': datetime.utcnow().isoformat(),
                'status': 'pending'
            }
            
            scheduled_file = f"scheduled_batch_{batch_data.get('batch_id', 'unknown')}.json"
            
            with open(scheduled_file, 'w') as f:
                json.dump(scheduled_state, f, indent=2)
            
            logger.info(f"Saved scheduled batch for {scheduled_time}")
        
        except Exception as e:
            logger.error(f"Failed to save scheduled batch: {e}")
    
    def clear_checkpoint(self, batch_id: str):
        """Clear checkpoint file after successful completion"""
        
        try:
            if os.path.exists(self.checkpoint_file):
                # Archive the checkpoint for reference
                archive_name = f"completed_{batch_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.json"
                archive_path = Path("logs") / archive_name
                
                # Ensure logs directory exists
                Path("logs").mkdir(exist_ok=True)
                
                # Move checkpoint to archive
                os.rename(self.checkpoint_file, archive_path)
                
                logger.info(f"Checkpoint archived to {archive_path}")
            
            # Clear current state
            self.current_state = {}
        
        except Exception as e:
            logger.error(f"Failed to clear checkpoint: {e}")
    
    def should_save_checkpoint(self, current_index: int) -> bool:
        """Determine if a checkpoint should be saved based on frequency"""
        
        # Save checkpoint every 5 URLs or if this is the first/last item
        checkpoint_frequency = 5
        
        if current_index == 0:  # First item
            return True
        elif current_index % checkpoint_frequency == 0:  # Every N items
            return True
        elif current_index == self.current_state.get('total_urls', 0) - 1:  # Last item
            return True
        else:
            return False
    
    def save_batch_progress(self, batch_id: str, results: Dict, remaining_urls: List[str]):
        """Save batch progress synchronously (wrapper for async method)"""
        
        try:
            import asyncio
            
            # Try to get existing event loop
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Create a task for async save_checkpoint
                    asyncio.create_task(self.save_checkpoint(batch_id, results, remaining_urls))
                else:
                    # Run in new event loop
                    loop.run_until_complete(self.save_checkpoint(batch_id, results, remaining_urls))
            except RuntimeError:
                # No event loop, create new one
                asyncio.run(self.save_checkpoint(batch_id, results, remaining_urls))
                
        except Exception as e:
            logger.error(f"Failed to save batch progress: {e}")
            # Fallback: at least update the current state
            self.current_state.update({
                'batch_id': batch_id,
                'processed_count': results.get('processed_count', 0),
                'successful_count': results.get('successful_count', 0),
                'failed_count': results.get('failed_count', 0),
                'manual_review_count': results.get('manual_review_count', 0),
                'last_checkpoint': datetime.utcnow().isoformat()
            })
    
    def _validate_checkpoint(self, checkpoint_data: Dict) -> bool:
        """Validate checkpoint data integrity"""
        
        required_fields = [
            'batch_id', 'total_urls', 'processed_count', 
            'remaining_urls', 'last_checkpoint'
        ]
        
        for field in required_fields:
            if field not in checkpoint_data:
                logger.error(f"Missing required field in checkpoint: {field}")
                return False
        
        # Validate data types
        if not isinstance(checkpoint_data['remaining_urls'], list):
            logger.error("Invalid remaining_urls format in checkpoint")
            return False
        
        if checkpoint_data['processed_count'] > checkpoint_data['total_urls']:
            logger.error("Invalid processed count in checkpoint")
            return False
        
        return True
    
    def _estimate_completion_time(self, remaining_urls: int) -> str:
        """Estimate completion time based on current performance"""
        
        avg_time_per_url = self.current_state.get('processing_stats', {}).get('avg_time_per_url', 45.0)
        estimated_seconds = remaining_urls * avg_time_per_url
        estimated_completion = datetime.utcnow() + timedelta(seconds=estimated_seconds)
        
        return estimated_completion.isoformat()
    
    def _update_processing_stats(self, processing_details: List[Dict]):
        """Update processing statistics for better time estimation"""
        
        try:
            if not processing_details:
                return
            
            stats = self.current_state.setdefault('processing_stats', {
                'avg_time_per_url': 45.0,
                'total_processing_time': 0,
                'retailer_performance': {},
                'method_performance': {}
            })
            
            # Calculate average processing time
            total_time = 0
            successful_count = 0
            
            for detail in processing_details:
                if detail.get('total_processing_time') and detail.get('success'):
                    total_time += detail['total_processing_time']
                    successful_count += 1
                    
                    # Update retailer performance
                    retailer = detail.get('retailer', 'unknown')
                    if retailer not in stats['retailer_performance']:
                        stats['retailer_performance'][retailer] = {'total_time': 0, 'count': 0, 'success_count': 0}
                    
                    stats['retailer_performance'][retailer]['total_time'] += detail['total_processing_time']
                    stats['retailer_performance'][retailer]['count'] += 1
                    if detail.get('success'):
                        stats['retailer_performance'][retailer]['success_count'] += 1
                    
                    # Update method performance
                    method = detail.get('extraction_method', 'unknown')
                    if method not in stats['method_performance']:
                        stats['method_performance'][method] = {'total_time': 0, 'count': 0, 'success_count': 0}
                    
                    stats['method_performance'][method]['total_time'] += detail.get('extraction_time', 0)
                    stats['method_performance'][method]['count'] += 1
                    if detail.get('success'):
                        stats['method_performance'][method]['success_count'] += 1
            
            if successful_count > 0:
                stats['avg_time_per_url'] = total_time / successful_count
                stats['total_processing_time'] += total_time
            
            # Calculate retailer success rates
            for retailer_stats in stats['retailer_performance'].values():
                if retailer_stats['count'] > 0:
                    retailer_stats['success_rate'] = retailer_stats['success_count'] / retailer_stats['count']
                    retailer_stats['avg_time'] = retailer_stats['total_time'] / retailer_stats['count']
            
            # Calculate method success rates
            for method_stats in stats['method_performance'].values():
                if method_stats['count'] > 0:
                    method_stats['success_rate'] = method_stats['success_count'] / method_stats['count']
                    method_stats['avg_time'] = method_stats['total_time'] / method_stats['count']
        
        except Exception as e:
            logger.error(f"Failed to update processing stats: {e}")
    
    def get_checkpoint_status(self) -> Dict:
        """Get current checkpoint status"""
        
        if not self.current_state:
            return {'status': 'no_active_batch'}
        
        return {
            'status': 'active_batch',
            'batch_id': self.current_state.get('batch_id'),
            'progress': f"{self.current_state.get('processed_count', 0)}/{self.current_state.get('total_urls', 0)}",
            'success_rate': (self.current_state.get('successful_count', 0) / 
                           max(self.current_state.get('processed_count', 1), 1) * 100),
            'estimated_completion': self.current_state.get('estimated_completion'),
            'last_checkpoint': self.current_state.get('last_checkpoint')
        }
    
    def list_available_checkpoints(self) -> List[Dict]:
        """List all available checkpoint files"""
        
        checkpoints = []
        
        # Current checkpoint
        if os.path.exists(self.checkpoint_file):
            try:
                with open(self.checkpoint_file, 'r') as f:
                    data = json.load(f)
                checkpoints.append({
                    'type': 'current',
                    'file': self.checkpoint_file,
                    'batch_id': data.get('batch_id'),
                    'progress': f"{data.get('processed_count', 0)}/{data.get('total_urls', 0)}",
                    'last_updated': data.get('last_checkpoint')
                })
            except Exception as e:
                logger.error(f"Error reading checkpoint file: {e}")
        
        # Scheduled batches
        for file_path in Path('.').glob('scheduled_batch_*.json'):
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                checkpoints.append({
                    'type': 'scheduled',
                    'file': str(file_path),
                    'batch_id': data.get('batch_data', {}).get('batch_id'),
                    'scheduled_time': data.get('scheduled_time'),
                    'status': data.get('status')
                })
            except Exception as e:
                logger.error(f"Error reading scheduled file {file_path}: {e}")
        
        # Archived checkpoints (in logs directory)
        logs_dir = Path('logs')
        if logs_dir.exists():
            for file_path in logs_dir.glob('completed_*.json'):
                try:
                    with open(file_path, 'r') as f:
                        data = json.load(f)
                    checkpoints.append({
                        'type': 'archived',
                        'file': str(file_path),
                        'batch_id': data.get('batch_id'),
                        'completion_time': file_path.stem.split('_')[-1] if '_' in file_path.stem else 'unknown'
                    })
                except Exception as e:
                    logger.error(f"Error reading archived file {file_path}: {e}")
        
        return checkpoints