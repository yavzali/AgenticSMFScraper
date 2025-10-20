#!/usr/bin/env python3
"""
Product Updater - Main entry point for updating EXISTING products only.
Handles products that already exist in the database/Shopify.
"""

# Add shared path for imports
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../Shared"))
sys.path.append(os.path.dirname(__file__))

import argparse
import asyncio
import json
import sys
import signal
from pathlib import Path
from datetime import datetime

from logger_config import setup_logging
from update_processor import UpdateProcessor
from scheduler import CostOptimizer
from checkpoint_manager import CheckpointManager
from notification_manager import NotificationManager

logger = setup_logging(__name__)

class ProductUpdateSystem:
    def __init__(self):
        self.update_processor = UpdateProcessor()
        self.cost_optimizer = CostOptimizer()
        self.checkpoint_manager = CheckpointManager()
        self.notification_manager = NotificationManager()
        self.shutdown_requested = False
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.shutdown_requested = True
        self.checkpoint_manager.save_checkpoint_immediately()
    
    async def process_batch(self, urls_file, modesty_level, force_run=False, resume=False):
        """Main processing function for EXISTING products only"""
        try:
            if resume:
                batch_data = self.checkpoint_manager.resume_from_checkpoint()
                if not batch_data:
                    logger.error("No checkpoint found to resume from")
                    return False
            else:
                # Load URLs from file
                with open(urls_file, 'r') as f:
                    batch_data = json.load(f)
                
                # Validate input
                if not self._validate_batch_data(batch_data, modesty_level):
                    return False
            
            # Check cost optimization unless forced
            if not force_run and self.cost_optimizer.cost_optimization_enabled and not self.cost_optimizer.is_discount_period():
                logger.info("Outside discount hours. Use --force-run-now to override.")
                return await self._schedule_for_discount_period(batch_data)
            
            # Process the batch - EXISTING PRODUCTS ONLY
            batch_id = batch_data.get('batch_id', f"update_{datetime.now().strftime('%Y%m%d_%H%M')}")
            logger.info(f"Starting EXISTING product update batch: {batch_id}")
            
            results = await self.update_processor.process_existing_products_batch(
                batch_data['urls'], 
                batch_data.get('modesty_level', modesty_level),
                batch_id
            )
            
            # Send completion notification
            await self.notification_manager.send_batch_completion(batch_id, results)
            
            logger.info(f"Product update batch {batch_id} completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Critical error in product update: {e}")
            await self.notification_manager.send_critical_error(str(e))
            return False
    
    def _validate_batch_data(self, batch_data, modesty_level):
        """Validate batch data structure"""
        if 'urls' not in batch_data:
            logger.error("Batch file must contain 'urls' field")
            return False
        
        if not isinstance(batch_data['urls'], list):
            logger.error("URLs must be a list")
            return False
        
        if len(batch_data['urls']) == 0:
            logger.error("No URLs provided")
            return False
        
        return True
    
    async def _schedule_for_discount_period(self, batch_data):
        """Schedule batch for cost-optimized processing"""
        logger.info("Scheduling batch for discount period...")
        # Implementation would schedule for later
        return True

def main():
    parser = argparse.ArgumentParser(description="Product Updater - Update existing products in Shopify")
    
    parser.add_argument('--batch-file', type=str, help='JSON file containing URLs to update')
    parser.add_argument('--modesty-level', choices=['modest', 'moderately_modest', 'not_modest'], 
                       default='modest', help='Modesty classification for products')
    parser.add_argument('--force-run-now', action='store_true', 
                       help='Ignore cost optimization and run immediately')
    parser.add_argument('--schedule-optimized', action='store_true', default=True,
                       help='Schedule for cost-optimized hours (default)')
    parser.add_argument('--resume', action='store_true', 
                       help='Resume from last checkpoint')
    parser.add_argument('--ignore-cost-optimization', action='store_true',
                       help='Alias for --force-run-now')
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.resume and not args.batch_file:
        logger.error("Either --batch-file or --resume must be specified")
        sys.exit(1)
    
    if args.batch_file and not Path(args.batch_file).exists():
        logger.error(f"Batch file not found: {args.batch_file}")
        sys.exit(1)
    
    # Force run takes precedence
    force_run = args.force_run_now or args.ignore_cost_optimization
    
    # Initialize and run system
    system = ProductUpdateSystem()
    
    try:
        asyncio.run(system.process_batch(
            args.batch_file, 
            args.modesty_level, 
            force_run=force_run,
            resume=args.resume
        ))
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 