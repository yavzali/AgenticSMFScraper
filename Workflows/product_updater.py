"""
Product Updater Workflow
Updates EXISTING products in Shopify using Dual Tower Architecture

Replaces:
- Product Updater/update_processor.py
- Product Updater/unified_extractor.py (routing logic)

Keeps:
- checkpoint_manager.py (state management)
- generate_update_batches.py (batch creation)
"""

# Add paths for imports
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../Shared"))
sys.path.append(os.path.join(os.path.dirname(__file__), "../Extraction/Markdown"))
sys.path.append(os.path.join(os.path.dirname(__file__), "../Extraction/Patchright"))
sys.path.append(os.path.join(os.path.dirname(__file__), "../Product Updater"))

import asyncio
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
import logging

from logger_config import setup_logging
from shopify_manager import ShopifyManager
from checkpoint_manager import CheckpointManager
from cost_tracker import cost_tracker
from notification_manager import NotificationManager
from db_manager import DatabaseManager
from image_processor import image_processor

# Tower imports
from markdown_product_extractor import MarkdownProductExtractor
from patchright_product_extractor import PatchrightProductExtractor

logger = setup_logging(__name__)

# Retailer classification
MARKDOWN_RETAILERS = [
    'revolve', 'asos', 'mango', 'hm', 'uniqlo'
]

PATCHRIGHT_RETAILERS = [
    'anthropologie', 'urban_outfitters', 'abercrombie',
    'aritzia', 'nordstrom'
]


@dataclass
class UpdateResult:
    """Result of updating a single product"""
    url: str
    success: bool
    shopify_id: Optional[int]
    method_used: str
    processing_time: float
    action: str  # 'updated', 'failed', 'not_found'
    error: Optional[str] = None


class ProductUpdater:
    """
    Updates existing products in Shopify using Dual Tower Architecture
    
    Process:
    1. Load batch file or query DB for products to update
    2. Route each product to appropriate tower (Markdown or Patchright)
    3. Extract fresh product data
    4. Update in Shopify
    5. Update local DB record
    6. Send notifications
    
    No Deduplication: Products already exist (have shopify_id)
    """
    
    def __init__(self):
        self.shopify_manager = ShopifyManager()
        self.checkpoint_manager = CheckpointManager()
        self.db_manager = DatabaseManager()
        self.notification_manager = NotificationManager()
        
        # Initialize towers
        self.markdown_tower = None
        self.patchright_tower = None
        
        logger.info("✅ Product Updater initialized (Dual Tower)")
    
    async def run_batch_update(
        self,
        batch_file: Optional[str] = None,
        filters: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Run product update batch
        
        Args:
            batch_file: Path to JSON batch file with URLs
            filters: Dict for DB query (retailer, age, status, etc.)
            
        Returns:
            Summary dict with results
        """
        start_time = datetime.utcnow()
        
        try:
            # Step 1: Get products to update
            if batch_file:
                logger.info(f"📂 Loading batch file: {batch_file}")
                products = await self._load_batch_file(batch_file)
                batch_id = os.path.basename(batch_file).replace('.json', '')
            elif filters:
                logger.info(f"🔍 Querying DB with filters: {filters}")
                products = await self._query_products_for_update(filters)
                batch_id = f"filter_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            else:
                raise ValueError("Must provide either batch_file or filters")
            
            if not products:
                logger.warning("No products to update")
                return {
                    'success': False,
                    'batch_id': batch_id,
                    'total_products': 0,
                    'message': 'No products found'
                }
            
            logger.info(f"📦 Found {len(products)} products to update")
            
            # Step 2: Initialize checkpoint
            self.checkpoint_manager.initialize_batch(batch_id, products, 'update')
            
            # Step 3: Initialize towers
            await self._initialize_towers()
            
            # Step 4: Group by extraction method
            markdown_products = [p for p in products if self._get_retailer(p) in MARKDOWN_RETAILERS]
            patchright_products = [p for p in products if self._get_retailer(p) in PATCHRIGHT_RETAILERS]
            
            logger.info(f"📊 Routing: {len(markdown_products)} markdown, {len(patchright_products)} patchright")
            
            # Step 5: Process products
            results = {
                'batch_id': batch_id,
                'start_time': start_time.isoformat(),
                'total_products': len(products),
                'processed': 0,
                'updated': 0,
                'failed': 0,
                'not_found': 0,
                'results': []
            }
            
            # Process markdown products
            for product in markdown_products:
                result = await self._update_single_product(product, 'markdown')
                results['results'].append(asdict(result))  # Convert to dict for JSON
                results['processed'] += 1
                
                if result.success:
                    results['updated'] += 1
                elif result.action == 'not_found':
                    results['not_found'] += 1
                else:
                    results['failed'] += 1
                
                # Update checkpoint
                self.checkpoint_manager.update_progress({
                    'url': result.url,
                    'success': result.success,
                    'shopify_id': result.shopify_id
                })
                
                # Respectful delay
                await asyncio.sleep(1)
            
            # Process patchright products
            for product in patchright_products:
                result = await self._update_single_product(product, 'patchright')
                results['results'].append(asdict(result))  # Convert to dict for JSON
                results['processed'] += 1
                
                if result.success:
                    results['updated'] += 1
                elif result.action == 'not_found':
                    results['not_found'] += 1
                else:
                    results['failed'] += 1
                
                # Update checkpoint
                self.checkpoint_manager.update_progress({
                    'url': result.url,
                    'success': result.success,
                    'shopify_id': result.shopify_id
                })
                
                await asyncio.sleep(1)
            
            # Step 6: Finalize
            results['end_time'] = datetime.utcnow().isoformat()
            results['success'] = True
            results['total_cost'] = cost_tracker.get_session_cost()
            
            # Step 7: Send notification
            await self.notification_manager.send_batch_completion(
                'Product Updater',
                results
            )
            
            logger.info(f"✅ Batch complete: {results['updated']}/{results['total_products']} updated")
            return results
            
        except Exception as e:
            logger.error(f"Batch update failed: {e}")
            return {
                'success': False,
                'batch_id': batch_id if 'batch_id' in locals() else 'unknown',
                'error': str(e)
            }
    
    async def _update_single_product(
        self,
        product: Dict,
        tower: str
    ) -> UpdateResult:
        """
        Update a single product using specified tower
        
        Args:
            product: Dict with 'url' and optional 'shopify_id'
            tower: 'markdown' or 'patchright'
            
        Returns:
            UpdateResult
        """
        url = product.get('url') if isinstance(product, dict) else product
        start_time = asyncio.get_event_loop().time()
        
        try:
            retailer = self._get_retailer(url)
            logger.info(f"🔄 Updating {retailer}: {url}")
            
            # Step 1: Extract fresh data from tower
            if tower == 'markdown':
                extraction_result = await self.markdown_tower.extract_product(url, retailer)
            else:
                extraction_result = await self.patchright_tower.extract_product(url, retailer)
            
            if not extraction_result.success:
                logger.warning(f"❌ Extraction failed: {extraction_result.errors}")
                return UpdateResult(
                    url=url,
                    success=False,
                    shopify_id=None,
                    method_used=extraction_result.method_used,
                    processing_time=asyncio.get_event_loop().time() - start_time,
                    action='failed',
                    error=str(extraction_result.errors)
                )
            
            # Step 2: Find existing product in DB
            existing_product = await self.db_manager.get_product_by_url(url)
            
            if not existing_product or not existing_product.get('shopify_id'):
                logger.warning(f"⚠️ Product not found in DB or no shopify_id: {url}")
                return UpdateResult(
                    url=url,
                    success=False,
                    shopify_id=None,
                    method_used=extraction_result.method_used,
                    processing_time=asyncio.get_event_loop().time() - start_time,
                    action='not_found',
                    error='Product not in DB or missing shopify_id'
                )
            
            shopify_id = existing_product['shopify_id']
            
            # Step 3: Conditional image processing (only if needed)
            should_process_images = self._should_process_images(existing_product, extraction_result.data)
            
            if should_process_images:
                image_urls = extraction_result.data.get('image_urls', [])
                if image_urls:
                    logger.debug(f"🖼️ Processing {len(image_urls)} images (first time or previous failure)")
                    try:
                        downloaded_image_paths = await image_processor.process_images(
                            image_urls=image_urls,
                            retailer=retailer,
                            product_title=extraction_result.data.get('title', 'Product')
                        )
                        
                        if downloaded_image_paths:
                            # Add processed images to extraction data
                            extraction_result.data['downloaded_image_paths'] = downloaded_image_paths
                            
                            # Mark images as successfully uploaded
                            extraction_result.data['images_uploaded'] = 1
                            extraction_result.data['images_uploaded_at'] = datetime.utcnow().isoformat()
                            extraction_result.data['images_failed_count'] = 0
                            extraction_result.data['last_image_error'] = None
                            
                            logger.info(f"✅ Processed {len(downloaded_image_paths)} images successfully")
                        else:
                            # Image processing failed
                            extraction_result.data['images_failed_count'] = existing_product.get('images_failed_count', 0) + 1
                            extraction_result.data['last_image_error'] = 'No images downloaded'
                            logger.warning(f"⚠️ Image processing returned 0 files")
                            
                    except Exception as e:
                        # Track failure
                        extraction_result.data['images_failed_count'] = existing_product.get('images_failed_count', 0) + 1
                        extraction_result.data['last_image_error'] = str(e)[:500]
                        logger.error(f"❌ Image processing failed: {e}")
            else:
                logger.debug(f"⏭️ Skipping image processing (already uploaded successfully)")
            
            # Step 4: Update in Shopify
            logger.debug(f"📤 Updating Shopify product {shopify_id}")
            update_result = await self.shopify_manager.update_product(
                shopify_id,
                extraction_result.data,
                retailer  # Required by ShopifyManager
            )
            
            if not update_result.get('success'):
                logger.error(f"❌ Shopify update failed for {shopify_id}")
                return UpdateResult(
                    url=url,
                    success=False,
                    shopify_id=shopify_id,
                    method_used=extraction_result.method_used,
                    processing_time=asyncio.get_event_loop().time() - start_time,
                    action='failed',
                    error=update_result.get('error', 'Shopify update failed')
                )
            
            # Step 5: Update local DB
            await self.db_manager.update_product_record(
                url,
                extraction_result.data,
                last_updated=datetime.utcnow()
            )
            
            processing_time = asyncio.get_event_loop().time() - start_time
            logger.info(f"✅ Updated {shopify_id} in {processing_time:.1f}s")
            
            return UpdateResult(
                url=url,
                success=True,
                shopify_id=shopify_id,
                method_used=extraction_result.method_used,
                processing_time=processing_time,
                action='updated'
            )
            
        except Exception as e:
            logger.error(f"Failed to update {url}: {e}")
            return UpdateResult(
                url=url,
                success=False,
                shopify_id=None,
                method_used=tower,
                processing_time=asyncio.get_event_loop().time() - start_time,
                action='failed',
                error=str(e)
            )
    
    async def _load_batch_file(self, batch_file: str) -> List[str]:
        """Load URLs from batch JSON file"""
        try:
            with open(batch_file, 'r') as f:
                data = json.load(f)
            
            # Handle different batch file formats
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and 'urls' in data:
                return data['urls']
            else:
                logger.error(f"Invalid batch file format: {batch_file}")
                return []
                
        except Exception as e:
            logger.error(f"Failed to load batch file: {e}")
            return []
    
    async def _query_products_for_update(self, filters: Dict) -> List[Dict]:
        """Query DB for products to update based on filters"""
        try:
            # Use DB manager to query products
            products = await self.db_manager.query_products(
                retailer=filters.get('retailer'),
                modesty_status=filters.get('modesty_status'),
                has_shopify_id=True,  # Only products in Shopify
                min_age_days=filters.get('min_age_days'),
                sale_status=filters.get('sale_status'),
                stock_status=filters.get('stock_status'),
                limit=filters.get('limit', 100)
            )
            
            return products
            
        except Exception as e:
            logger.error(f"DB query failed: {e}")
            return []
    
    async def _initialize_towers(self):
        """Initialize extraction towers"""
        if not self.markdown_tower:
            self.markdown_tower = MarkdownProductExtractor()
            logger.debug("Markdown Tower initialized")
        
        if not self.patchright_tower:
            self.patchright_tower = PatchrightProductExtractor()
            logger.debug("Patchright Tower initialized")
    
    def _should_process_images(self, existing_product: Dict, new_data: Dict) -> bool:
        """
        Determine if images should be processed/uploaded
        
        Images are processed only if:
        1. Never uploaded before (images_uploaded = 0 or NULL)
        2. Previous upload failed (images_failed_count > 0)
        3. Image URLs have changed (different from what's in DB)
        
        Args:
            existing_product: Current product record from DB
            new_data: Newly extracted product data
            
        Returns:
            bool: True if images should be processed
        """
        # Check if images were successfully uploaded before
        images_uploaded = existing_product.get('images_uploaded', 0)
        if not images_uploaded:
            logger.debug("Images never uploaded before → process")
            return True
        
        # Check if previous uploads failed
        images_failed_count = existing_product.get('images_failed_count', 0)
        if images_failed_count > 0:
            logger.debug(f"Previous upload failed {images_failed_count} times → retry")
            return True
        
        # Check if image URLs changed
        # Note: This is simplified - in production you'd compare normalized URLs
        old_image_count = existing_product.get('image_count', 0)
        new_image_urls = new_data.get('image_urls', [])
        if len(new_image_urls) != old_image_count:
            logger.debug(f"Image count changed ({old_image_count} → {len(new_image_urls)}) → process")
            return True
        
        # Images already uploaded successfully and unchanged
        logger.debug("Images already uploaded successfully → skip")
        return False
    
    def _get_retailer(self, url_or_product: Any) -> str:
        """Extract retailer from URL or product dict"""
        if isinstance(url_or_product, dict):
            if 'retailer' in url_or_product:
                return url_or_product['retailer']
            url = url_or_product.get('url', '')
        else:
            url = url_or_product
        
        # Extract from URL
        url_lower = url.lower()
        if 'revolve.com' in url_lower:
            return 'revolve'
        elif 'asos.com' in url_lower:
            return 'asos'
        elif 'mango.com' in url_lower:
            return 'mango'
        elif 'hm.com' in url_lower or 'h&m' in url_lower:
            return 'hm'
        elif 'uniqlo.com' in url_lower:
            return 'uniqlo'
        elif 'aritzia.com' in url_lower:
            return 'aritzia'
        elif 'anthropologie.com' in url_lower:
            return 'anthropologie'
        elif 'urbanoutfitters.com' in url_lower:
            return 'urban_outfitters'
        elif 'abercrombie.com' in url_lower:
            return 'abercrombie'
        elif 'nordstrom.com' in url_lower:
            return 'nordstrom'
        else:
            logger.warning(f"Unknown retailer in URL: {url}")
            return 'unknown'


# CLI entry point
async def main():
    """CLI entry point for Product Updater"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Update existing products in Shopify')
    parser.add_argument('--batch-file', help='Path to batch JSON file')
    parser.add_argument('--retailer', help='Filter by retailer')
    parser.add_argument('--min-age-days', type=int, help='Minimum age in days')
    parser.add_argument('--sale-status', choices=['on_sale', 'regular'], help='Sale status filter')
    parser.add_argument('--limit', type=int, default=100, help='Maximum products to update')
    
    args = parser.parse_args()
    
    updater = ProductUpdater()
    
    if args.batch_file:
        result = await updater.run_batch_update(batch_file=args.batch_file)
    else:
        filters = {
            'retailer': args.retailer,
            'min_age_days': args.min_age_days,
            'sale_status': args.sale_status,
            'limit': args.limit
        }
        # Remove None values
        filters = {k: v for k, v in filters.items() if v is not None}
        
        if not filters:
            print("Error: Must provide either --batch-file or filter arguments")
            return
        
        result = await updater.run_batch_update(filters=filters)
    
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())

