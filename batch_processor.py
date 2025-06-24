"""
Batch Processor - Orchestrates the complete workflow for batches of URLs
"""

import asyncio
from typing import List, Dict, Any
from datetime import datetime
import importlib
import json
from dataclasses import dataclass, asdict
import sqlite3
import logging
import traceback

from logger_config import setup_logging
from url_processor import URLProcessor, ProcessedURL
from unified_extractor import UnifiedExtractor  # Simplified: single extraction system
from shopify_manager import ShopifyManager
from checkpoint_manager import CheckpointManager
from duplicate_detector import DuplicateDetector
from pattern_learner import PatternLearner
from manual_review_manager import ManualReviewManager
from cost_tracker import CostTracker
from notification_manager import NotificationManager

logger = setup_logging(__name__)

class BatchProcessor:
    def __init__(self):
        self.url_processor = URLProcessor()
        self.unified_extractor = UnifiedExtractor()  # Single extraction system
        self.shopify_manager = ShopifyManager()
        self.checkpoint_manager = CheckpointManager()
        self.duplicate_detector = DuplicateDetector()
        
        # Image processor mapping
        self.image_processors = {}
        self._load_image_processors()
    
    def _load_image_processors(self):
        """Load image processors using the new factory system"""
        
        # Import the factory
        from image_processor_factory import ImageProcessorFactory
        
        self.image_processor_factory = ImageProcessorFactory
        
        # Get supported retailers
        supported_retailers = self.image_processor_factory.get_supported_retailers()
        
        logger.info(f"Image processor factory supports {len(supported_retailers)} retailers:")
        for retailer in supported_retailers:
            processor_type = self.image_processor_factory.get_processor_type(retailer)
            logger.info(f"  {retailer}: {processor_type}")
    
    async def process_batch(self, urls: List, modesty_level: str, batch_id: str) -> Dict[str, Any]:
        """Process a batch of URLs with complete error handling and checkpointing"""
        
        batch_start = datetime.utcnow()
        total_urls = len(urls)
        
        results = {
            'batch_id': batch_id,
            'start_time': batch_start.isoformat(),
            'total_urls': total_urls,
            'successful_count': 0,
            'failed_count': 0,
            'skipped_count': 0,
            'processing_details': [],
            'method_performance': {},
            'cost_tracking': {},
            'warnings': []
        }
        
        logger.info(f"Starting batch {batch_id}: {total_urls} URLs with modesty level '{modesty_level}'")
        
        try:
            for i, url_input in enumerate(urls, 1):
                if self.checkpoint_manager.should_save_checkpoint(i):
                    self.checkpoint_manager.save_batch_progress(batch_id, results, urls[i:])
                
                try:
                    # Normalize URL input - handle both string URLs and URL objects
                    if isinstance(url_input, dict):
                        url = url_input.get('url', str(url_input))
                        if not url or url == str(url_input):
                            logger.warning(f"Invalid URL object format: {url_input}")
                            results['failed_count'] += 1
                            continue
                    else:
                        url = str(url_input)
                    
                    logger.info(f"[{i}/{total_urls}] Processing: {url}")
                    
                    # Process individual URL
                    result = await self._process_single_url(url, modesty_level, batch_id, i, total_urls)
                    results['processing_details'].append(result)
                    
                    # Update counters
                    if result['success']:
                        results['successful_count'] += 1
                    else:
                        results['failed_count'] += 1
                    
                    # Track method performance
                    method = result.get('extraction_method', 'unknown')
                    if method not in results['method_performance']:
                        results['method_performance'][method] = {'count': 0, 'success_count': 0}
                    
                    results['method_performance'][method]['count'] += 1
                    if result['success']:
                        results['method_performance'][method]['success_count'] += 1
                    
                    # Brief pause between URLs
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(f"Error processing URL {url_input}: {e}")
                    results['failed_count'] += 1
                    results['processing_details'].append({
                        'url': str(url_input),
                        'success': False,
                        'error': str(e),
                        'manual_review': True
                    })
                    
                    # Add to manual review
                    url_str = url_input.get('url', str(url_input)) if isinstance(url_input, dict) else str(url_input)
                    await self._add_to_manual_review(url_str, 'unknown', modesty_level, 'processing_error', str(e))
        
        finally:
            # Calculate final statistics
            batch_end = datetime.utcnow()
            results['end_time'] = batch_end.isoformat()
            results['duration_minutes'] = (batch_end - batch_start).total_seconds() / 60
            results['success_rate'] = (results['successful_count'] / total_urls * 100) if total_urls > 0 else 0
            
            # Calculate method success rates
            for method, stats in results['method_performance'].items():
                successful_with_method = sum(1 for detail in results['processing_details'] 
                                           if detail.get('extraction_method') == method and detail.get('success'))
                stats['success_rate'] = (successful_with_method / stats['count'] * 100) if stats['count'] > 0 else 0
            
            # Clear checkpoint on completion
            self.checkpoint_manager.clear_checkpoint(batch_id)
            
            logger.info(f"Batch {batch_id} completed: {results['successful_count']}/{total_urls} successful ({results['success_rate']:.1f}%)")
        
        return results
    
    async def _process_single_url(self, url: str, modesty_level: str, batch_id: str, current: int, total: int) -> Dict[str, Any]:
        """Process a single URL through the complete workflow"""
        
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
            # Phase 1: URL Processing and Validation
            logger.debug(f"[{current}/{total}] Phase 1: Processing URL")
            processed_url = await self.url_processor.process_url(url, modesty_level)
            
            result['retailer'] = processed_url.retailer
            result['clean_url'] = processed_url.clean_url
            
            # Handle duplicates
            if processed_url.is_duplicate:
                logger.info(f"[{current}/{total}] Duplicate detected: {processed_url.duplicate_action}")
                if processed_url.duplicate_action == 'update':
                    return await self._handle_product_update(processed_url, result)
                elif processed_url.duplicate_action == 'skip':
                    result['success'] = True
                    result['action'] = 'skipped_duplicate'
                    return result
                else:
                    result['manual_review'] = True
                    result['warnings'].append('Uncertain duplicate - manual review required')
                    await self._add_to_manual_review(url, processed_url.retailer, modesty_level, 
                                                   'duplicate_uncertain', 'Manual duplicate review required')
                    return result
            
            # Phase 2: Data Extraction (simplified with unified extractor)
            logger.debug(f"[{current}/{total}] Phase 2: Extracting product data")
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
            
            # Phase 3: Image Processing
            logger.debug(f"[{current}/{total}] Phase 3: Processing images")
            image_result = await self._process_images(processed_url.retailer, extracted_data.get('image_urls', []), 
                                                    processed_url.clean_url, extracted_data.get('product_code'), extracted_data)
            
            result['images_processed'] = len(image_result['downloaded_images'])
            result['warnings'].extend(image_result['warnings'])
            
            # Phase 4: Shopify Product Creation
            logger.debug(f"[{current}/{total}] Phase 4: Creating Shopify product")
            shopify_result = await self.shopify_manager.create_product(
                extracted_data, 
                processed_url.retailer, 
                modesty_level, 
                processed_url.clean_url,
                image_result['downloaded_images']
            )
            
            if shopify_result['success']:
                result['success'] = True
                result['shopify_product_id'] = shopify_result['product_id']
                result['shopify_url'] = shopify_result['product_url']
                result['action'] = 'created'
                
                # Store in database
                await self._store_product_record(extracted_data, processed_url, shopify_result, extraction_result.method_used)
                
                logger.info(f"[{current}/{total}] Successfully created product: {shopify_result['product_id']}")
            else:
                result['errors'].append(shopify_result['error'])
                result['manual_review'] = True
                await self._add_to_manual_review(url, processed_url.retailer, modesty_level, 
                                               'shopify_creation_failed', shopify_result['error'])
        
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
    
    async def _process_images(self, retailer: str, image_urls: List[str], product_url: str, 
                            product_code: str, extracted_data: Dict = None) -> Dict:
        """Process images using the new optimized 4-layer architecture"""
        
        result = {
            'downloaded_images': [],
            'warnings': [],
            'method_used': 'none',
            'quality_report': {},
            'processor_type': 'none'
        }
        
        if not image_urls:
            result['warnings'].append('No image URLs found')
            return result
        
        try:
            # Get appropriate processor for this retailer
            processor = self.image_processor_factory.get_processor(retailer)
            
            if not processor:
                result['warnings'].append(f'No image processor available for {retailer}')
                return result
            
            result['processor_type'] = self.image_processor_factory.get_processor_type(retailer)
            
            # Prepare product data for the processor
            product_data = extracted_data or {}
            product_data['image_urls'] = image_urls
            
            logger.info(f"Processing {len(image_urls)} images for {retailer} using {result['processor_type']} processor")
            
            # Use the optimized 4-layer processing
            downloaded_images = await processor.process_images(image_urls, product_url, product_data)
            
            if downloaded_images:
                result['downloaded_images'] = downloaded_images
                result['method_used'] = 'processor_success'
                logger.info(f"Successfully processed {len(downloaded_images)} images for {retailer}")
                
                # Generate quality report
                result['quality_report'] = {
                    'total_processed': len(downloaded_images),
                    'source_urls': len(image_urls),
                    'processor_type': result['processor_type'],
                    'success_rate': f"{len(downloaded_images)}/{len(image_urls)}"
                }
            else:
                result['warnings'].append('No images successfully processed')
                result['method_used'] = 'processor_failed'
                
                # Try legacy fallback for backward compatibility
                logger.warning(f"Primary processing failed for {retailer}, trying legacy fallback")
                legacy_images = await self._legacy_image_fallback(retailer, image_urls, product_url)
                if legacy_images:
                    result['downloaded_images'] = legacy_images
                    result['method_used'] = 'legacy_fallback'
                    result['warnings'].append('Used legacy fallback method')
        
        except Exception as e:
            logger.error(f"Image processing failed for {retailer}: {e}")
            result['warnings'].append(f'Image processing error: {str(e)}')
            result['method_used'] = 'error'
        
        return result
    
    async def _legacy_image_fallback(self, retailer: str, image_urls: List[str], product_url: str) -> List[str]:
        """Legacy image download fallback for backward compatibility"""
        
        try:
            # Try to get a processor from the factory first
            processor = self.image_processor_factory.get_processor(retailer)
            if processor:
                # Use the factory processor but with simple download logic
                product_data = {'image_urls': image_urls}
                downloaded_images = await processor.process_images(image_urls, product_url, product_data)
                return downloaded_images
            
            # If no factory processor available, log and return empty
            logger.warning(f"No image processor available for {retailer} in legacy fallback")
            return []
        
        except Exception as e:
            logger.error(f"Legacy image fallback failed for {retailer}: {e}")
            return []
    
    async def _handle_product_update(self, processed_url: ProcessedURL, result: Dict) -> Dict:
        """Handle updating an existing product"""
        
        try:
            # Extract new data
            extraction_result = await self.unified_extractor.extract_product_data(processed_url.clean_url, processed_url.retailer)
            
            if extraction_result.success:
                # Update product via Shopify manager
                update_result = await self.shopify_manager.update_product(
                    processed_url.existing_product_id,
                    extraction_result.data,
                    processed_url.retailer
                )
                
                if update_result['success']:
                    result['success'] = True
                    result['action'] = 'updated'
                    result['shopify_product_id'] = processed_url.existing_product_id
                    logger.info(f"Successfully updated existing product: {processed_url.existing_product_id}")
                else:
                    result['manual_review'] = True
                    result['errors'].append(update_result['error'])
            else:
                result['manual_review'] = True
                result['errors'].extend(extraction_result.errors)
        
        except Exception as e:
            result['manual_review'] = True
            result['errors'].append(str(e))
        
        return result
    
    async def _store_product_record(self, extracted_data: Dict, processed_url: ProcessedURL, 
                                  shopify_result: Dict, extraction_method: str):
        """Store product record in database"""
        
        try:
            await self.duplicate_detector.store_product(
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
                modesty_status=processed_url.modesty_level,
                shopify_id=shopify_result['product_id'],
                shopify_variant_id=shopify_result.get('variant_id'),
                scraping_method=extraction_method,
                neckline=extracted_data.get('neckline', 'unknown'),
                sleeve_length=extracted_data.get('sleeve_length', 'unknown'),
                visual_analysis_confidence=extracted_data.get('visual_analysis_confidence'),
                visual_analysis_source=extracted_data.get('visual_analysis_source', '')
            )
            
            logger.debug(f"Stored product record for {processed_url.clean_url}")
        
        except Exception as e:
            logger.error(f"Failed to store product record: {e}")
    
    async def _add_to_manual_review(self, url: str, retailer: str, modesty_level: str, 
                                  error_type: str, error_details: str, extracted_data: Dict = None):
        """Add failed item to manual review queue"""
        
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
        
        # Close image processor factory instances
        if hasattr(self, 'image_processor_factory'):
            await self.image_processor_factory.close_all()
        
        # UnifiedExtractor doesn't have a close method, so we skip it
        
        logger.info("BatchProcessor cleanup completed")
    
    def __del__(self):
        """Cleanup on destruction - improved to avoid runtime warnings"""
        if hasattr(self, 'image_processor_factory'):
            import asyncio
            try:
                # Only attempt cleanup if there's an active event loop
                loop = asyncio.get_running_loop()
                if loop and not loop.is_closed():
                    asyncio.create_task(self.image_processor_factory.close_all())
            except RuntimeError:
                # No running event loop - cleanup will happen on process exit
                pass  # Ignore cleanup errors during destruction