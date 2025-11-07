"""
New Product Importer Workflow
Imports NEW products from URL lists using Dual Tower Architecture

Replaces:
- New Product Importer/new_product_importer.py
- New Product Importer/import_processor.py
- New Product Importer/unified_extractor.py (routing logic)

Keeps:
- checkpoint_manager.py (state management)
- In-batch URL deduplication
- Modesty assessment integration
"""

# Add paths for imports
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../Shared"))
sys.path.append(os.path.join(os.path.dirname(__file__), "../Extraction/Markdown"))
sys.path.append(os.path.join(os.path.dirname(__file__), "../Extraction/Patchright"))
sys.path.append(os.path.join(os.path.dirname(__file__), "../New Product Importer"))

import asyncio
import json
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass
from urllib.parse import urlparse
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
    'revolve', 'asos', 'mango', 'hm', 'uniqlo',
    'aritzia', 'nordstrom'
]

PATCHRIGHT_RETAILERS = [
    'anthropologie', 'urban_outfitters', 'abercrombie'
]


@dataclass
class ImportResult:
    """Result of importing a single product"""
    url: str
    success: bool
    shopify_id: Optional[int]
    method_used: str
    processing_time: float
    action: str  # 'uploaded', 'skipped', 'failed'
    modesty_status: Optional[str] = None
    error: Optional[str] = None


class NewProductImporter:
    """
    Imports new products from URL lists using Dual Tower Architecture
    
    Process:
    1. Load batch file (list of URLs)
    2. In-batch URL deduplication
    3. Route to appropriate tower (Markdown or Patchright)
    4. Extract product data
    5. Modesty assessment (Gemini classification)
    6. Upload to Shopify if modest/moderately_modest
    7. Save ALL products to DB (regardless of modesty)
    8. Send notifications
    
    Deduplication: In-batch only (not against DB)
    """
    
    def __init__(self):
        self.shopify_manager = ShopifyManager()
        self.checkpoint_manager = CheckpointManager()
        self.db_manager = DatabaseManager()
        self.notification_manager = NotificationManager()
        
        # Initialize towers
        self.markdown_tower = None
        self.patchright_tower = None
        
        # Modesty assessment (Gemini)
        self.modesty_assessor = None
        
        logger.info("✅ New Product Importer initialized (Dual Tower)")
    
    async def run_batch_import(
        self,
        batch_file: str,
        modesty_level: Optional[str] = None,
        product_type_override: Optional[str] = None,
        resume: bool = False
    ) -> Dict[str, Any]:
        """
        Run product import batch
        
        Args:
            batch_file: Path to JSON batch file with URLs
            modesty_level: Expected modesty level for batch (optional)
            product_type_override: Override product type (e.g., 'Tops')
            resume: Resume from checkpoint if True
            
        Returns:
            Summary dict with results
        """
        start_time = datetime.utcnow()
        
        try:
            # Step 1: Load batch file
            if resume:
                logger.info("🔄 Resuming from checkpoint")
                checkpoint_data = self.checkpoint_manager.resume_from_checkpoint()
                if not checkpoint_data:
                    raise ValueError("No checkpoint found to resume from")
                
                urls = checkpoint_data.get('remaining_urls', [])
                batch_id = checkpoint_data.get('batch_id')
                modesty_level = checkpoint_data.get('modesty_level', modesty_level)
            else:
                logger.info(f"📂 Loading batch file: {batch_file}")
                with open(batch_file, 'r') as f:
                    batch_data = json.load(f)
                
                # Handle different batch file formats
                if isinstance(batch_data, list):
                    urls = batch_data
                elif isinstance(batch_data, dict):
                    urls = batch_data.get('urls', [])
                    modesty_level = batch_data.get('modesty_level', modesty_level)
                else:
                    raise ValueError(f"Invalid batch file format")
                
                batch_id = os.path.basename(batch_file).replace('.json', '').replace('.txt', '')
            
            if not urls:
                logger.warning("No URLs to process")
                return {
                    'success': False,
                    'batch_id': batch_id,
                    'total_urls': 0,
                    'message': 'No URLs to process'
                }
            
            logger.info(f"📦 Loaded {len(urls)} URLs")
            
            # Step 2: In-batch URL deduplication
            unique_urls = self._deduplicate_batch_urls(urls)
            logger.info(f"🔍 After deduplication: {len(unique_urls)} unique URLs")
            
            # Step 3: Initialize checkpoint
            if not resume:
                self.checkpoint_manager.initialize_batch(batch_id, unique_urls, modesty_level or 'unknown')
            
            # Step 4: Initialize towers and modesty assessor
            await self._initialize_towers()
            await self._initialize_modesty_assessor()
            
            # Step 5: Group by extraction method
            markdown_urls = [u for u in unique_urls if self._get_retailer(u) in MARKDOWN_RETAILERS]
            patchright_urls = [u for u in unique_urls if self._get_retailer(u) in PATCHRIGHT_RETAILERS]
            
            logger.info(f"📊 Routing: {len(markdown_urls)} markdown, {len(patchright_urls)} patchright")
            
            # Step 6: Process products
            results = {
                'batch_id': batch_id,
                'start_time': start_time.isoformat(),
                'total_urls': len(unique_urls),
                'processed': 0,
                'uploaded': 0,
                'skipped': 0,
                'failed': 0,
                'modest': 0,
                'moderately_modest': 0,
                'not_modest': 0,
                'results': []
            }
            
            # Process markdown URLs
            for url in markdown_urls:
                result = await self._import_single_product(
                    url,
                    'markdown',
                    modesty_level,
                    product_type_override
                )
                # Convert ImportResult to dict for JSON serialization
                from dataclasses import asdict
                results['results'].append(asdict(result))
                results['processed'] += 1
                
                if result.success and result.action == 'uploaded':
                    results['uploaded'] += 1
                elif result.action == 'skipped':
                    results['skipped'] += 1
                else:
                    results['failed'] += 1
                
                # Count by modesty status
                if result.modesty_status:
                    if result.modesty_status == 'modest':
                        results['modest'] += 1
                    elif result.modesty_status == 'moderately_modest':
                        results['moderately_modest'] += 1
                    elif result.modesty_status == 'not_modest':
                        results['not_modest'] += 1
                
                # Update checkpoint
                self.checkpoint_manager.update_progress({
                    'url': result.url,
                    'success': result.success,
                    'shopify_id': result.shopify_id
                })
                
                # Respectful delay
                await asyncio.sleep(1)
            
            # Process patchright URLs
            for url in patchright_urls:
                result = await self._import_single_product(
                    url,
                    'patchright',
                    modesty_level,
                    product_type_override
                )
                # Convert ImportResult to dict for JSON serialization
                from dataclasses import asdict
                results['results'].append(asdict(result))
                results['processed'] += 1
                
                if result.success and result.action == 'uploaded':
                    results['uploaded'] += 1
                elif result.action == 'skipped':
                    results['skipped'] += 1
                else:
                    results['failed'] += 1
                
                # Count by modesty status
                if result.modesty_status:
                    if result.modesty_status == 'modest':
                        results['modest'] += 1
                    elif result.modesty_status == 'moderately_modest':
                        results['moderately_modest'] += 1
                    elif result.modesty_status == 'not_modest':
                        results['not_modest'] += 1
                
                # Update checkpoint
                self.checkpoint_manager.update_progress({
                    'url': result.url,
                    'success': result.success,
                    'shopify_id': result.shopify_id
                })
                
                await asyncio.sleep(1)
            
            # Step 7: Finalize
            results['end_time'] = datetime.utcnow().isoformat()
            results['success'] = True
            results['total_cost'] = cost_tracker.get_session_cost()
            results['products_uploaded'] = results['uploaded']
            
            # Step 8: Send notification
            await self.notification_manager.send_batch_completion(
                'New Product Importer',
                results
            )
            
            logger.info(f"✅ Batch complete: {results['uploaded']}/{results['total_urls']} uploaded to Shopify")
            logger.info(f"   Modesty breakdown: {results['modest']} modest, {results['moderately_modest']} moderately, {results['not_modest']} not modest")
            
            return results
            
        except Exception as e:
            logger.error(f"Batch import failed: {e}")
            return {
                'success': False,
                'batch_id': batch_id if 'batch_id' in locals() else 'unknown',
                'error': str(e)
            }
    
    async def _import_single_product(
        self,
        url: str,
        tower: str,
        expected_modesty: Optional[str],
        product_type_override: Optional[str]
    ) -> ImportResult:
        """
        Import a single product using specified tower
        
        Args:
            url: Product URL
            tower: 'markdown' or 'patchright'
            expected_modesty: Expected modesty level (optional)
            product_type_override: Product type override (optional)
            
        Returns:
            ImportResult
        """
        start_time = asyncio.get_event_loop().time()
        
        try:
            retailer = self._get_retailer(url)
            logger.info(f"🔄 Importing {retailer}: {url}")
            
            # Step 1: Extract product data from tower
            if tower == 'markdown':
                extraction_result = await self.markdown_tower.extract_product(url, retailer)
            else:
                extraction_result = await self.patchright_tower.extract_product(url, retailer)
            
            if not extraction_result.success:
                logger.warning(f"❌ Extraction failed: {extraction_result.errors}")
                return ImportResult(
                    url=url,
                    success=False,
                    shopify_id=None,
                    method_used=extraction_result.method_used,
                    processing_time=asyncio.get_event_loop().time() - start_time,
                    action='failed',
                    error=str(extraction_result.errors)
                )
            
            product_data = extraction_result.data
            
            # Apply product type override if provided
            if product_type_override:
                product_data['clothing_type'] = product_type_override
                logger.debug(f"Product type overridden to: {product_type_override}")
            
            # Step 2: Modesty assessment (Gemini classification)
            logger.debug("🤖 Running modesty assessment")
            modesty_classification = await self._assess_modesty(product_data)
            product_data['modesty_status'] = modesty_classification
            
            logger.info(f"📊 Modesty: {modesty_classification}")
            
            # Step 3: Process images (enhance URLs + download)
            image_urls = product_data.get('image_urls', [])
            downloaded_image_paths = []
            
            if image_urls:
                logger.debug(f"🖼️ Processing {len(image_urls)} images")
                downloaded_image_paths = await image_processor.process_images(
                    image_urls=image_urls,
                    retailer=retailer,
                    product_title=product_data.get('title', 'Product')
                )
                logger.info(f"✅ Processed {len(downloaded_image_paths)} images")
            
            # Step 4: Upload to Shopify if modest/moderately_modest
            shopify_id = None
            action = 'skipped'
            
            if modesty_classification in ['modest', 'moderately_modest']:
                logger.debug(f"📤 Uploading to Shopify ({modesty_classification})")
                shopify_id = await self.shopify_manager.create_product(
                    extracted_data=product_data,
                    retailer_name=retailer,
                    modesty_level=modesty_classification,
                    source_url=url,
                    downloaded_images=downloaded_image_paths,  # ✅ File paths, not URLs
                    product_type_override=product_type_override
                )
                
                if shopify_id:
                    product_data['shopify_id'] = shopify_id
                    action = 'uploaded'
                    logger.info(f"✅ Uploaded to Shopify: {shopify_id}")
                else:
                    logger.error("❌ Shopify upload failed")
                    action = 'failed'
            else:
                logger.info(f"⏭️ Skipping Shopify upload ({modesty_classification})")
                action = 'skipped'
            
            # Step 5: Save to DB (ALL products, regardless of modesty)
            await self.db_manager.save_product(
                url=url,
                retailer=retailer,
                product_data=product_data,
                shopify_id=shopify_id,
                modesty_status=modesty_classification,
                first_seen=datetime.utcnow()
            )
            
            processing_time = asyncio.get_event_loop().time() - start_time
            
            return ImportResult(
                url=url,
                success=True,
                shopify_id=shopify_id,
                method_used=extraction_result.method_used,
                processing_time=processing_time,
                action=action,
                modesty_status=modesty_classification
            )
            
        except Exception as e:
            logger.error(f"Failed to import {url}: {e}")
            return ImportResult(
                url=url,
                success=False,
                shopify_id=None,
                method_used=tower,
                processing_time=asyncio.get_event_loop().time() - start_time,
                action='failed',
                error=str(e)
            )
    
    def _deduplicate_batch_urls(self, urls: List[str]) -> List[str]:
        """
        Deduplicate URLs within batch by normalizing for retailer-specific patterns
        Handles Revolve's changing query params and other URL variations
        
        Returns:
            List of unique URLs
        """
        seen_products = {}  # product_identifier -> first_url
        deduplicated = []
        duplicates_removed = 0
        
        for url in urls:
            # Extract product identifier for deduplication
            product_id = self._extract_product_identifier(url)
            
            # Check if we've seen this product
            if product_id in seen_products:
                duplicates_removed += 1
                logger.debug(f"Duplicate URL removed: {url}")
                logger.debug(f"  Same as: {seen_products[product_id]}")
            else:
                seen_products[product_id] = url
                deduplicated.append(url)
        
        if duplicates_removed > 0:
            logger.info(f"🔍 In-batch deduplication: Removed {duplicates_removed} duplicates")
            logger.info(f"   Original: {len(urls)}, Unique: {len(deduplicated)}")
        
        return deduplicated
    
    def _extract_product_identifier(self, url: str) -> str:
        """
        Extract a stable product identifier from URL for deduplication
        
        Handles:
        - Revolve: /dp/CODE/ pattern
        - Others: domain + path (no query params)
        """
        url_lower = url.lower()
        
        # Revolve: Extract product code from /dp/CODE/
        if 'revolve.com' in url_lower:
            match = re.search(r'/dp/([A-Z0-9\-]+)/?', url, re.IGNORECASE)
            if match:
                return f"revolve:{match.group(1)}"
        
        # For other retailers: Use domain + path
        parsed = urlparse(url)
        return f"{parsed.netloc}{parsed.path}"
    
    async def _assess_modesty(self, product_data: Dict) -> str:
        """
        Assess product modesty using Gemini
        
        Args:
            product_data: Dict with title, description, images
            
        Returns:
            Classification: 'modest', 'moderately_modest', or 'not_modest'
        """
        try:
            # Use Gemini for modesty classification
            # This is a placeholder - actual implementation would use Gemini API
            
            # For now, return a default based on expected patterns
            # TODO: Implement actual Gemini modesty assessment
            
            title = product_data.get('title', '').lower()
            description = product_data.get('description', '').lower()
            
            # Simple heuristics (replace with Gemini)
            modest_keywords = ['modest', 'maxi', 'long sleeve', 'high neck', 'ankle length']
            not_modest_keywords = ['mini', 'crop', 'bikini', 'revealing', 'sheer']
            
            text = f"{title} {description}"
            
            if any(kw in text for kw in not_modest_keywords):
                return 'not_modest'
            elif any(kw in text for kw in modest_keywords):
                return 'modest'
            else:
                return 'moderately_modest'
                
        except Exception as e:
            logger.error(f"Modesty assessment failed: {e}")
            return 'moderately_modest'  # Default to moderate on error
    
    async def _initialize_towers(self):
        """Initialize extraction towers"""
        if not self.markdown_tower:
            self.markdown_tower = MarkdownProductExtractor()
            logger.debug("Markdown Tower initialized")
        
        if not self.patchright_tower:
            self.patchright_tower = PatchrightProductExtractor()
            logger.debug("Patchright Tower initialized")
    
    async def _initialize_modesty_assessor(self):
        """Initialize Gemini modesty assessor"""
        if not self.modesty_assessor:
            # Placeholder for actual Gemini modesty assessor
            # TODO: Implement proper modesty assessment with Gemini
            self.modesty_assessor = True
            logger.debug("Modesty Assessor initialized")
    
    def _get_retailer(self, url: str) -> str:
        """Extract retailer from URL"""
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
    """CLI entry point for New Product Importer"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Import new products from URL batch files')
    parser.add_argument('batch_file', help='Path to JSON/TXT batch file with URLs')
    parser.add_argument('--modesty-level', choices=['modest', 'moderately_modest', 'not_modest'],
                       help='Expected modesty level for batch')
    parser.add_argument('--product-type', help='Override product type (e.g., "Tops", "Dresses")')
    parser.add_argument('--resume', action='store_true', help='Resume from checkpoint')
    
    args = parser.parse_args()
    
    importer = NewProductImporter()
    result = await importer.run_batch_import(
        batch_file=args.batch_file,
        modesty_level=args.modesty_level,
        product_type_override=args.product_type,
        resume=args.resume
    )
    
    # Result is already a dict
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())

