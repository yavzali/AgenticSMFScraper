"""
Import Processor - Handles NEW product creation workflow only
Extracted from BatchProcessor with focus on non-duplicate products
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
from dataclasses import dataclass, asdict
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

class ImportProcessor:
    def __init__(self):
        self.unified_extractor = UnifiedExtractor()
        self.shopify_manager = ShopifyManager()
        self.checkpoint_manager = CheckpointManager()
        self.duplicate_detector = DuplicateDetector()
        
        # Image processor mapping
        self.image_processors = {}
        self._load_image_processors()
    
    def _load_image_processors(self):
        """Load image processors using the factory system"""
        
        # Import the factory
        from image_processor_factory import ImageProcessorFactory
        
        self.image_processor_factory = ImageProcessorFactory
        
        # Get supported retailers
        supported_retailers = self.image_processor_factory.get_supported_retailers()
        
        logger.info(f"Image processor factory supports {len(supported_retailers)} retailers:")
        for retailer in supported_retailers:
            processor_type = self.image_processor_factory.get_processor_type(retailer)
            logger.info(f"  {retailer}: {processor_type}")
    
    async def process_new_products_batch(self, urls: List[str], modesty_level: str, batch_id: str) -> Dict[str, Any]:
        """Process a batch of URLs for NEW product creation only"""
        
        logger.info(f"Starting NEW product import batch: {batch_id} with {len(urls)} URLs")
        
        # Initialize checkpoint
        self.checkpoint_manager.initialize_batch(batch_id, urls, modesty_level)
        
        results = {
            'batch_id': batch_id,
            'total_urls': len(urls),
            'processed_count': 0,
            'successful_count': 0,
            'failed_count': 0,
            'skipped_count': 0,  # For duplicates
            'manual_review_count': 0,
            'results': [],
            'start_time': datetime.utcnow().isoformat(),
            'end_time': None
        }
        
        try:
            # Process each URL - NEW PRODUCTS ONLY
            for i, url in enumerate(urls, 1):
                logger.info(f"Processing URL {i}/{len(urls)}: {url}")
                
                result = await self._process_single_new_product(url, modesty_level, batch_id, i, len(urls))
                
                results['results'].append(result)
                results['processed_count'] += 1
                
                if result['success']:
                    results['successful_count'] += 1
                elif result.get('action') == 'skipped_duplicate':
                    results['skipped_count'] += 1
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
        
        logger.info(f"Batch {batch_id} completed: {results['successful_count']} successful, {results['skipped_count']} skipped, {results['failed_count']} failed")
        return results
    
    async def _process_single_new_product(self, url: str, modesty_level: str, batch_id: str, current: int, total: int) -> Dict[str, Any]:
        """Process a single URL for NEW product creation only"""
        
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
            # Phase 1: URL Processing and Duplicate Detection
            logger.debug(f"[{current}/{total}] Phase 1: Processing URL and checking for duplicates")
            processed_url = await self._process_url(url, modesty_level)
            
            result['retailer'] = processed_url.retailer
            result['clean_url'] = processed_url.clean_url
            
            # CRITICAL: Skip if duplicate - NEW PRODUCTS ONLY
            if processed_url.is_duplicate:
                logger.info(f"[{current}/{total}] Skipping duplicate product: {url}")
                result['success'] = True
                result['action'] = 'skipped_duplicate'
                result['reason'] = 'Product already exists in database'
                return result
            
            # Phase 2: Data Extraction
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
            
            # Phase 4: Shopify Product Creation (NEW PRODUCTS ONLY)
            logger.debug(f"[{current}/{total}] Phase 4: Creating NEW Shopify product")
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
                
                logger.info(f"[{current}/{total}] Successfully created NEW product: {shopify_result['product_id']}")
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
    
    async def _process_url(self, url: str, modesty_level: str) -> ProcessedURL:
        """Process URL with duplicate detection - simplified for import focus"""
        
        # Import URL processor
        from url_processor import URLProcessor
        
        url_processor = URLProcessor()
        processed_url = await url_processor.process_url(url, modesty_level)
        
        return processed_url
    
    async def _process_images(self, retailer: str, image_urls: List[str], product_url: str, 
                            product_code: str, extracted_data: Dict = None) -> Dict:
        """Process images using the optimized 4-layer architecture - EXACT COPY from BatchProcessor"""
        
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
        """Legacy image download fallback - EXACT COPY from BatchProcessor"""
        
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
    
    async def _store_product_record(self, extracted_data: Dict, processed_url: ProcessedURL, 
                                  shopify_result: Dict, extraction_method: str):
        """Store product record in database - EXACT COPY from BatchProcessor"""
        
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
        """Cleanup all processors and resources - EXACT COPY from BatchProcessor"""
        
        # Close image processor factory instances
        if hasattr(self, 'image_processor_factory'):
            await self.image_processor_factory.close_all()
        
        logger.info("ImportProcessor cleanup completed")
    
    def __del__(self):
        """Cleanup on destruction"""
        if hasattr(self, 'image_processor_factory'):
            import asyncio
            try:
                # Only attempt cleanup if there's an active event loop
                loop = asyncio.get_running_loop()
                if loop and not loop.is_closed():
                    asyncio.create_task(self.image_processor_factory.close_all())
            except RuntimeError:
                # No running event loop - cleanup will happen on process exit
                pass 