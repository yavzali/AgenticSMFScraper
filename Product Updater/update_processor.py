"""
Update Processor - Handles EXISTING product update workflow only
Extracted from BatchProcessor with focus on duplicate/existing products
"""

# Add shared path for imports
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../Shared"))
sys.path.append(os.path.dirname(__file__))

import asyncio
from typing import List, Dict, Any
from datetime import datetime
import json
from dataclasses import dataclass
import logging
import traceback

from logger_config import setup_logging
from unified_extractor import UnifiedExtractor
from shopify_manager import ShopifyManager
from checkpoint_manager import CheckpointManager
from pattern_learner import PatternLearner
from manual_review_manager import ManualReviewManager
from cost_tracker import CostTracker
from duplicate_detector import DuplicateDetector
from markdown_extractor import MarkdownExtractor
from playwright_agent import PlaywrightAgentWrapper
from notification_manager import NotificationManager

logger = setup_logging(__name__)

@dataclass
class ProcessedURL:
    url: str
    retailer: str
    clean_url: str
    modesty_level: str
    is_duplicate: bool = False
    duplicate_action: str = None
    existing_product_id: int = None

class UpdateProcessor:
    def __init__(self):
        self.unified_extractor = UnifiedExtractor()
        self.shopify_manager = ShopifyManager()
        self.checkpoint_manager = CheckpointManager()
        self.duplicate_detector = DuplicateDetector()
    
    async def process_existing_products_batch(self, urls: List[str], modesty_level: str, batch_id: str) -> Dict[str, Any]:
        """Process a batch of URLs for EXISTING product updates only"""
        
        logger.info(f"Starting EXISTING product update batch: {batch_id} with {len(urls)} URLs")
        
        # Initialize checkpoint
        self.checkpoint_manager.initialize_batch(batch_id, urls, modesty_level)
        
        results = {
            'batch_id': batch_id,
            'total_urls': len(urls),
            'processed_count': 0,
            'updated_count': 0,
            'failed_count': 0,
            'not_found_count': 0,  # For products that don't exist
            'manual_review_count': 0,
            'results': [],
            'start_time': datetime.utcnow().isoformat(),
            'end_time': None
        }
        
        try:
            # Process each URL - EXISTING PRODUCTS ONLY
            for i, url in enumerate(urls, 1):
                logger.info(f"Processing URL {i}/{len(urls)}: {url}")
                
                result = await self._process_single_existing_product(url, modesty_level, batch_id, i, len(urls))
                
                results['results'].append(result)
                results['processed_count'] += 1
                
                if result['success']:
                    results['updated_count'] += 1
                elif result.get('action') == 'not_found':
                    results['not_found_count'] += 1
                elif result.get('manual_review'):
                    results['manual_review_count'] += 1
                else:
                    results['failed_count'] += 1
                
                # Update checkpoint
                self.checkpoint_manager.update_progress(result)
                
                # Small delay to be respectful
                await asyncio.sleep(1)
        
        except Exception as e:
            logger.error(f"Critical error in batch processing: {e}")
            results['error'] = str(e)
        
        finally:
            results['end_time'] = datetime.utcnow().isoformat()
            await self.cleanup()
        
        logger.info(f"Batch {batch_id} completed: {results['updated_count']} updated, {results['not_found_count']} not found, {results['failed_count']} failed")
        return results
    
    async def _process_single_existing_product(self, url: str, modesty_level: str, batch_id: str, current: int, total: int) -> Dict[str, Any]:
        """Process a single URL for EXISTING product updates only"""
        
        start_time = datetime.utcnow()
        result = {
            'url': url,
            'batch_id': batch_id,
            'position': f"{current}/{total}",
            'start_time': start_time.isoformat(),
            'success': False,
            'manual_review': False,
            'warnings': [],
            'errors': []
        }
        
        try:
            # Phase 1: URL Processing and Existing Product Detection
            logger.debug(f"[{current}/{total}] Phase 1: Processing URL and checking for existing product")
            processed_url = await self._process_url(url, modesty_level)
            
            result['retailer'] = processed_url.retailer
            result['clean_url'] = processed_url.clean_url
            
            # CRITICAL: Only process if duplicate/existing - EXISTING PRODUCTS ONLY
            if not processed_url.is_duplicate:
                logger.info(f"[{current}/{total}] Product not found in database: {url}")
                result['success'] = True
                result['action'] = 'not_found'
                result['reason'] = 'Product does not exist in database - use New Product Importer instead'
                return result
            
            # Ensure we have the existing product ID
            if not processed_url.existing_product_id:
                logger.warning(f"[{current}/{total}] Duplicate detected but no existing product ID found")
                result['manual_review'] = True
                result['warnings'].append('Duplicate detected but no existing product ID found')
                return result
            
            # Phase 2: Extract Fresh Data
            logger.debug(f"[{current}/{total}] Phase 2: Extracting fresh product data")
            extraction_result = await self.unified_extractor.extract_product_data(processed_url.clean_url, processed_url.retailer)
            
            result['extraction_method'] = extraction_result.method_used
            result['extraction_time'] = extraction_result.processing_time
            result['warnings'].extend(extraction_result.warnings)
            
            if not extraction_result.success:
                result['errors'].extend(extraction_result.errors)
                result['manual_review'] = True
                await self._add_to_manual_review(url, processed_url.retailer, modesty_level, 
                                               'extraction_failed', '; '.join(extraction_result.errors))
                return result
            
            extracted_data = extraction_result.data
            
            # Phase 3: Update Existing Product in Shopify
            logger.debug(f"[{current}/{total}] Phase 3: Updating EXISTING Shopify product {processed_url.existing_product_id}")
            update_result = await self.shopify_manager.update_product(
                processed_url.existing_product_id,
                extracted_data,
                processed_url.retailer
            )
            
            if update_result['success']:
                result['success'] = True
                result['shopify_product_id'] = processed_url.existing_product_id
                result['action'] = 'updated'
                
                # Update database record
                await self._update_product_record(extracted_data, processed_url, extraction_result.method_used)
                
                logger.info(f"[{current}/{total}] Successfully updated EXISTING product: {processed_url.existing_product_id}")
            else:
                result['errors'].append(update_result['error'])
                result['manual_review'] = True
                await self._add_to_manual_review(url, processed_url.retailer, modesty_level, 
                                               'shopify_update_failed', update_result['error'])
        
        except Exception as e:
            logger.error(f"[{current}/{total}] Critical error processing {url}: {e}")
            result['errors'].append(str(e))
            result['manual_review'] = True
            await self._add_to_manual_review(url, result.get('retailer', 'unknown'), modesty_level, 
                                           'critical_error', str(e))
        
        finally:
            end_time = datetime.utcnow()
            result['end_time'] = end_time.isoformat()
            result['total_processing_time'] = (end_time - start_time).total_seconds()
        
        return result
    
    async def _process_url(self, url: str, modesty_level: str) -> ProcessedURL:
        """Process URL with duplicate detection - simplified for update focus"""
        
        # Import URL processor
        from url_processor import URLProcessor
        
        url_processor = URLProcessor()
        processed_url = await url_processor.process_url(url, modesty_level)
        
        return processed_url
    
    async def _update_product_record(self, extracted_data: Dict, processed_url: ProcessedURL, extraction_method: str):
        """Update existing product record in database"""
        
        try:
            # Use the duplicate detector to update the existing record
            await self.duplicate_detector.update_existing_product(
                existing_id=processed_url.existing_product_id,
                url=processed_url.clean_url,
                retailer=processed_url.retailer,
                title=extracted_data.get('title', ''),
                product_code=extracted_data.get('product_code', ''),
                brand=extracted_data.get('brand', ''),
                price=extracted_data.get('price', 0),
                original_price=extracted_data.get('original_price'),
                clothing_type=extracted_data.get('clothing_type', ''),
                sale_status=extracted_data.get('sale_status', 'not on sale'),
                stock_status=extracted_data.get('stock_status', 'in stock'),
                scraping_method=extraction_method,
                neckline=extracted_data.get('neckline', 'unknown'),
                sleeve_length=extracted_data.get('sleeve_length', 'unknown'),
                visual_analysis_confidence=extracted_data.get('visual_analysis_confidence'),
                visual_analysis_source=extracted_data.get('visual_analysis_source', '')
            )
            
            logger.debug(f"Updated product record for {processed_url.clean_url}")
        
        except Exception as e:
            logger.error(f"Failed to update product record: {e}")
    
    async def _add_to_manual_review(self, url: str, retailer: str, modesty_level: str, 
                                  error_type: str, error_details: str, extracted_data: Dict = None):
        """Add failed item to manual review queue - EXACT COPY from BatchProcessor"""
        
        try:
            review_data = {
                'url': url,
                'retailer': retailer,
                'modesty_level': modesty_level,
                'error_type': error_type,
                'error_details': error_details,
                'timestamp': datetime.utcnow().isoformat(),
                'extracted_data': extracted_data or {}
            }
            
            # This would write to manual_review.csv
            logger.info(f"Added to manual review: {url} ({error_type})")
            
        except Exception as e:
            logger.error(f"Failed to add to manual review: {e}")
    
    async def cleanup(self):
        """Cleanup all processors and resources"""
        
        logger.info("UpdateProcessor cleanup completed")
    
    def __del__(self):
        """Cleanup on destruction"""
        pass 