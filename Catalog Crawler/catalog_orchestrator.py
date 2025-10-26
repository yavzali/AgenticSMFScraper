"""
Catalog Orchestrator - Coordinates complete catalog monitoring workflow
Handles baseline establishment, weekly monitoring, and integration with existing scraper
"""

# Add shared path for imports
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../Shared"))
sys.path.append(os.path.dirname(__file__))

import asyncio
import json
import uuid
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, date, timedelta
import os

from logger_config import setup_logging
from catalog_db_manager import CatalogDatabaseManager
from retailer_crawlers import CatalogCrawlerFactory
from change_detector import ChangeDetector, ChangeDetectionConfig
from notification_manager import NotificationManager

logger = setup_logging(__name__)

@dataclass
class OrchestrationConfig:
    """Configuration for catalog orchestration"""
    enable_weekly_monitoring: bool = True
    enable_baseline_establishment: bool = True
    enable_manual_review_interface: bool = True
    enable_batch_creation: bool = True
    enable_notifications: bool = True
    max_concurrent_crawlers: int = 2
    baseline_max_pages: int = 10
    monitoring_max_pages: int = 20
    cost_limit_per_run: float = 50.0
    
@dataclass
class OrchestrationResult:
    """Result of orchestration run"""
    success: bool
    run_id: str
    run_type: str
    retailers_processed: List[str]
    total_products_crawled: int
    new_products_found: int
    products_for_review: int
    processing_time: float
    total_cost: float
    errors: List[str]
    warnings: List[str]
    batch_files_created: List[str]

class CatalogOrchestrator:
    """
    Main orchestrator for catalog monitoring system
    Coordinates crawling, change detection, review, and batch creation
    """
    
    def __init__(self, config: OrchestrationConfig = None):
        self.config = config or OrchestrationConfig()
        self.db_manager = CatalogDatabaseManager()
        self.change_detector = ChangeDetector()
        self.notification_manager = NotificationManager() if self.config.enable_notifications else None
        
        # Active retailers and categories from crawler factory
        self.supported_retailers = CatalogCrawlerFactory.get_supported_retailers()
        self.categories = ['dresses', 'tops']
        
        logger.info(f"✅ Catalog orchestrator initialized for {len(self.supported_retailers)} retailers")
    
    # =================== MAIN ORCHESTRATION METHODS ===================
    
    async def run_weekly_monitoring(self, retailers: List[str] = None, 
                                  categories: List[str] = None) -> OrchestrationResult:
        """
        Run weekly catalog monitoring for new products
        This is the main scheduled workflow
        """
        run_id = f"weekly_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        logger.info(f"🕷️ Starting weekly catalog monitoring run: {run_id}")
        
        return await self._execute_monitoring_workflow(
            run_id=run_id,
            run_type='weekly_monitoring',
            retailers=retailers or self.supported_retailers,
            categories=categories or self.categories
        )
    
    async def establish_baselines(self, retailers: List[str] = None, 
                                categories: List[str] = None) -> OrchestrationResult:
        """
        Establish catalog baselines for specified retailers/categories
        Run this after manual review of entire catalogs
        """
        run_id = f"baseline_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        logger.info(f"📋 Starting baseline establishment run: {run_id}")
        
        return await self._execute_monitoring_workflow(
            run_id=run_id,
            run_type='baseline_establishment',
            retailers=retailers or self.supported_retailers,
            categories=categories or self.categories
        )
    
    async def run_manual_refresh(self, retailer: str, category: str) -> OrchestrationResult:
        """
        Run manual refresh for specific retailer/category
        Useful for debugging or immediate updates
        """
        run_id = f"manual_{retailer}_{category}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        logger.info(f"🔄 Starting manual refresh: {retailer} {category}")
        
        return await self._execute_monitoring_workflow(
            run_id=run_id,
            run_type='manual_refresh',
            retailers=[retailer],
            categories=[category]
        )
    
    # =================== CORE WORKFLOW EXECUTION ===================
    
    async def _execute_monitoring_workflow(self, run_id: str, run_type: str,
                                         retailers: List[str], categories: List[str]) -> OrchestrationResult:
        """Core workflow execution for all run types"""
        
        start_time = datetime.utcnow()
        total_cost = 0.0
        total_products_crawled = 0
        total_new_products = 0
        total_for_review = 0
        errors = []
        warnings = []
        retailers_processed = []
        batch_files_created = []
        
        try:
            # Create monitoring run record
            await self.db_manager.create_monitoring_run(
                run_type, config={'run_id': run_id, 'retailers': retailers, 'categories': categories})
            
            # Process each retailer/category combination
            semaphore = asyncio.Semaphore(self.config.max_concurrent_crawlers)
            
            tasks = []
            for retailer in retailers:
                for category in categories:
                    task = self._process_retailer_category(
                        semaphore, run_id, run_type, retailer, category)
                    tasks.append(task)
            
            # Execute all crawler tasks
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for i, result in enumerate(results):
                retailer = retailers[i // len(categories)]
                category = categories[i % len(categories)]
                
                if isinstance(result, Exception):
                    error_msg = f"{retailer} {category}: {str(result)}"
                    errors.append(error_msg)
                    logger.error(f"❌ {error_msg}")
                elif result:
                    # Successful crawl result
                    total_products_crawled += result.get('products_crawled', 0)
                    total_new_products += result.get('new_products', 0)
                    total_for_review += result.get('for_review', 0)
                    total_cost += result.get('cost', 0.0)
                    
                    if result.get('warnings'):
                        warnings.extend(result['warnings'])
                    
                    retailers_processed.append(f"{retailer}_{category}")
                    
                    logger.info(f"✅ {retailer} {category}: {result.get('new_products', 0)} new products")
            
            # Post-processing workflow
            if run_type != 'baseline_establishment':
                # Create batch files for approved products
                batch_files = await self._create_batch_files_for_approved_products(run_id)
                batch_files_created.extend(batch_files)
                
                # Send notifications
                if self.notification_manager:
                    await self._send_completion_notifications(
                        run_id, run_type, total_new_products, total_for_review, errors)
            
            # Update monitoring run with final results
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            await self.db_manager.update_monitoring_run(run_id, {
                'total_products_crawled': total_products_crawled,
                'new_products_found': total_new_products,
                'products_for_review': total_for_review,
                'total_runtime': processing_time,
                'total_cost': total_cost,
                'run_status': 'completed' if not errors else 'completed_with_errors',
                'error_count': len(errors),
                'batch_files_created': json.dumps(batch_files_created),
                'completed_at': datetime.utcnow()
            })
            
            success = len(errors) == 0 or len(retailers_processed) > 0
            
            logger.info(f"🎯 Monitoring run {run_id} completed: "
                       f"{total_new_products} new products, "
                       f"{total_for_review} for review, "
                       f"${total_cost:.2f} cost, "
                       f"{processing_time:.1f}s")
            
            return OrchestrationResult(
                success=success,
                run_id=run_id,
                run_type=run_type,
                retailers_processed=retailers_processed,
                total_products_crawled=total_products_crawled,
                new_products_found=total_new_products,
                products_for_review=total_for_review,
                processing_time=processing_time,
                total_cost=total_cost,
                errors=errors,
                warnings=warnings,
                batch_files_created=batch_files_created
            )
            
        except Exception as e:
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            logger.error(f"❌ Orchestration failed: {e}")
            
            # Update run as failed
            await self.db_manager.update_monitoring_run(run_id, {
                'run_status': 'failed',
                'error_count': len(errors) + 1,
                'total_runtime': processing_time,
                'completed_at': datetime.utcnow()
            })
            
            return OrchestrationResult(
                success=False,
                run_id=run_id,
                run_type=run_type,
                retailers_processed=[],
                total_products_crawled=0,
                new_products_found=0,
                products_for_review=0,
                processing_time=processing_time,
                total_cost=0.0,
                errors=errors + [str(e)],
                warnings=warnings,
                batch_files_created=[]
            )
    
    async def _process_retailer_category(self, semaphore: asyncio.Semaphore, 
                                       run_id: str, run_type: str, 
                                       retailer: str, category: str) -> Dict:
        """Process single retailer/category combination"""
        
        async with semaphore:
            try:
                logger.info(f"🕷️ Processing {retailer} {category}")
                
                # Create retailer-specific crawler
                crawler = CatalogCrawlerFactory.create_crawler(retailer, category)
                if not crawler:
                    raise ValueError(f"No crawler available for {retailer}")
                
                # Execute crawling
                crawl_result = await crawler.crawl_catalog(run_id, run_type)
                
                if not crawl_result.success:
                    raise Exception(f"Crawl failed: {crawl_result.errors}")
                
                # For baseline establishment, record baseline metadata
                if run_type == 'baseline_establishment':
                    try:
                        await self.db_manager.create_baseline(
                            retailer=retailer,
                            category=category,
                            baseline_date=datetime.utcnow().date(),
                            total_products=crawl_result.total_products_crawled,
                            crawl_config={
                                'crawl_pages': crawl_result.pages_crawled,
                                'crawl_depth_reached': f"page_{crawl_result.pages_crawled}",
                                'extraction_method': crawl_result.crawl_metadata.get('extraction_method', 'markdown'),
                                'catalog_url': crawler.config.base_url,
                                'sort_by_newest_url': crawler.config.sort_by_newest_url,
                                'pagination_type': crawler.config.pagination_type,
                                'has_sort_by_newest': crawler.config.has_sort_by_newest,
                                'early_stop_threshold': 3,
                                'baseline_crawl_time': crawl_result.processing_time
                            }
                        )
                        logger.info(f"📊 Recorded baseline metadata for {retailer} {category}")
                    except Exception as e:
                        logger.error(f"Failed to record baseline metadata: {e}")
                
                # For monitoring runs, perform change detection
                new_products_count = 0
                for_review_count = 0
                
                if run_type != 'baseline_establishment':
                    # Get discovered products and detect changes
                    discovered_products = await self._get_discovered_products_for_run(
                        run_id, retailer, category)
                    
                    if discovered_products:
                        detection_result = await self.change_detector.detect_changes(
                            discovered_products, retailer, category, run_id)
                        
                        new_products_count = detection_result.new_products_found
                        for_review_count = detection_result.manual_review_required
                
                return {
                    'success': True,
                    'products_crawled': crawl_result.total_products_crawled,
                    'new_products': new_products_count,
                    'for_review': for_review_count,
                    'cost': 0.0,  # Would be calculated from cost_tracker
                    'warnings': crawl_result.warnings
                }
                
            except Exception as e:
                logger.error(f"Error processing {retailer} {category}: {e}")
                raise
    
    # =================== BATCH CREATION WORKFLOW ===================
    
    async def _create_batch_files_for_approved_products(self, run_id: str) -> List[str]:
        """Create batch files for products approved for scraping"""
        
        try:
            batch_files_created = []
            
            # Get approved products that haven't been batched yet
            approved_products = await self.db_manager.get_approved_products_for_batch()
            
            if not approved_products:
                logger.info("No approved products ready for batch creation")
                return []
            
            # Group products by retailer for efficient processing
            retailer_groups = {}
            for product in approved_products:
                retailer = product['retailer']
                if retailer not in retailer_groups:
                    retailer_groups[retailer] = []
                retailer_groups[retailer].append(product)
            
            # Create batch files per retailer
            for retailer, products in retailer_groups.items():
                batch_file = await self._create_batch_file(retailer, products, run_id)
                if batch_file:
                    batch_files_created.append(batch_file)
                    
                    # Mark products as batched
                    product_ids = [p['id'] for p in products]
                    await self.db_manager.mark_products_as_batched(product_ids, batch_file)
            
            logger.info(f"📦 Created {len(batch_files_created)} batch files")
            return batch_files_created
            
        except Exception as e:
            logger.error(f"Error creating batch files: {e}")
            return []
    
    async def _create_batch_file(self, retailer: str, products: List[Dict], run_id: str) -> Optional[str]:
        """Create batch file for specific retailer"""
        
        try:
            # Generate batch file name
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            batch_filename = f"approved_catalog_batch_{retailer}_{timestamp}.json"
            
            # Build batch content compatible with existing scraper
            batch_content = {
                "batch_name": f"Catalog Discoveries - {retailer} - {datetime.utcnow().strftime('%B %d, %Y')}",
                "created_date": datetime.utcnow().strftime('%Y-%m-%d'),
                "total_urls": len(products),
                "source": "catalog_monitoring",
                "discovery_run_id": run_id,
                "urls": []
            }
            
            # Add products to batch
            for product in products:
                batch_content["urls"].append({
                    "url": product['catalog_url'],
                    "retailer": product['retailer'],
                    "discovered_date": product['discovered_date'],
                    "catalog_source": f"{product['category']}_catalog",
                    "review_status": product['review_status'],
                    "reviewed_by": product.get('reviewed_by'),
                    "catalog_product_id": product['id']
                })
            
            # Write batch file to same directory as existing batch files
            script_dir = os.path.dirname(os.path.abspath(__file__))
            batch_file_path = os.path.join(script_dir, batch_filename)
            
            with open(batch_file_path, 'w') as f:
                json.dump(batch_content, f, indent=2)
            
            logger.info(f"📄 Created batch file: {batch_filename} ({len(products)} products)")
            return batch_filename
            
        except Exception as e:
            logger.error(f"Error creating batch file for {retailer}: {e}")
            return None
    
    # =================== UTILITY METHODS ===================
    
    async def _get_discovered_products_for_run(self, run_id: str, retailer: str, 
                                             category: str) -> List:
        """Get products discovered in this run for change detection"""
        try:
            # This would query the catalog_products table for products
            # discovered in this specific run
            # For now, return empty list as placeholder
            return []
            
        except Exception as e:
            logger.error(f"Error getting discovered products: {e}")
            return []
    
    async def _send_completion_notifications(self, run_id: str, run_type: str,
                                           new_products: int, for_review: int, errors: List[str]):
        """Send notifications about completed run"""
        try:
            if not self.notification_manager:
                return
            
            subject = f"Catalog Monitoring Complete - {run_type}"
            
            message = f"""
Catalog monitoring run completed:

Run ID: {run_id}
Run Type: {run_type}
New Products Found: {new_products}
Products for Review: {for_review}
Errors: {len(errors)}

{f'Errors: {errors[:3]}' if errors else 'No errors'}

Please review new products in the catalog monitoring interface.
"""
            
            await self.notification_manager.send_notification(
                subject=subject,
                message=message,
                notification_type='catalog_monitoring_complete'
            )
            
        except Exception as e:
            logger.error(f"Error sending completion notifications: {e}")
    
    # =================== BASELINE MANAGEMENT ===================
    
    async def validate_baselines(self) -> Dict[str, List[str]]:
        """Validate all active baselines and identify those needing refresh"""
        
        validation_results = {
            'valid': [],
            'needs_refresh': [],
            'missing': []
        }
        
        try:
            for retailer in self.supported_retailers:
                for category in self.categories:
                    baseline = await self.db_manager.get_active_baseline(retailer, category)
                    
                    if not baseline:
                        validation_results['missing'].append(f"{retailer}_{category}")
                    elif self._baseline_needs_refresh(baseline):
                        validation_results['needs_refresh'].append(f"{retailer}_{category}")
                    else:
                        validation_results['valid'].append(f"{retailer}_{category}")
            
            logger.info(f"Baseline validation: {len(validation_results['valid'])} valid, "
                       f"{len(validation_results['needs_refresh'])} need refresh, "
                       f"{len(validation_results['missing'])} missing")
            
            return validation_results
            
        except Exception as e:
            logger.error(f"Error validating baselines: {e}")
            return validation_results
    
    def _baseline_needs_refresh(self, baseline: Dict) -> bool:
        """Check if baseline needs refresh based on age and validation"""
        
        # Check if baseline is older than 30 days
        baseline_date = datetime.fromisoformat(baseline['baseline_date'])
        age_days = (datetime.utcnow() - baseline_date).days
        
        if age_days > 30:
            return True
        
        # Check last validation
        last_validated = baseline.get('last_validated')
        if last_validated:
            last_validated_date = datetime.fromisoformat(last_validated)
            validation_age = (datetime.utcnow() - last_validated_date).days
            if validation_age > 7:
                return True
        
        return False
    
    # =================== SYSTEM MANAGEMENT ===================
    
    async def get_system_status(self) -> Dict:
        """Get comprehensive system status"""
        
        try:
            # Get database stats
            db_stats = await self.db_manager.get_system_stats()
            
            # Get baseline validation
            baseline_validation = await self.validate_baselines()
            
            # Get recent run performance
            # This would query recent runs from catalog_monitoring_runs
            
            # Get cost tracking info
            # This would integrate with cost_tracker
            
            return {
                'database_stats': db_stats,
                'baseline_validation': baseline_validation,
                'supported_retailers': len(self.supported_retailers),
                'supported_categories': len(self.categories),
                'orchestrator_config': {
                    'weekly_monitoring': self.config.enable_weekly_monitoring,
                    'baseline_establishment': self.config.enable_baseline_establishment,
                    'notifications': self.config.enable_notifications,
                    'max_concurrent_crawlers': self.config.max_concurrent_crawlers
                },
                'last_updated': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return {'error': str(e)}
    
    async def emergency_stop_all_crawlers(self):
        """Emergency stop for all active crawlers"""
        logger.warning("🛑 Emergency stop requested - stopping all active crawlers")
        
        # This would implement emergency stop logic
        # For now, log the request
        pass
    
    async def close(self):
        """Cleanup resources"""
        await self.db_manager.close()
        await self.change_detector.close()
        logger.info("Catalog orchestrator closed")