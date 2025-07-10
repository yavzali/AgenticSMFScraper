"""
Catalog Main - Entry point for catalog monitoring system
Provides CLI interface and integration with existing scraper system
"""

# Add shared path for imports
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../Shared"))
sys.path.append(os.path.dirname(__file__))

import asyncio
import argparse
import json
import sys
import os
from typing import List, Optional
from datetime import datetime

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from logger_config import setup_logging
from catalog_orchestrator import CatalogOrchestrator, OrchestrationConfig
from retailer_crawlers import CatalogCrawlerFactory
from catalog_db_manager import CatalogDatabaseManager

logger = setup_logging(__name__)

class CatalogMain:
    """
    Main entry point for catalog monitoring system
    Provides CLI interface and programmatic access
    """
    
    def __init__(self):
        self.orchestrator = None
        logger.info("🕷️ Catalog monitoring system initialized")
    
    async def _get_orchestrator(self) -> CatalogOrchestrator:
        """Get or create orchestrator instance"""
        if not self.orchestrator:
            self.orchestrator = CatalogOrchestrator()
        return self.orchestrator
    
    # =================== MAIN WORKFLOW COMMANDS ===================
    
    async def run_weekly_monitoring(self, retailers: Optional[List[str]] = None, 
                                  categories: Optional[List[str]] = None,
                                  dry_run: bool = False) -> bool:
        """
        Run weekly catalog monitoring
        This is the main automated workflow
        """
        
        try:
            logger.info("🕷️ Starting weekly catalog monitoring")
            
            if dry_run:
                logger.info("🧪 DRY RUN MODE - No actual crawling or database changes")
                return await self._simulate_monitoring_run(retailers, categories)
            
            orchestrator = await self._get_orchestrator()
            result = await orchestrator.run_weekly_monitoring(retailers, categories)
            
            if result.success:
                logger.info(f"✅ Weekly monitoring completed successfully")
                logger.info(f"   📊 Results: {result.new_products_found} new products, "
                           f"{result.products_for_review} for review")
                logger.info(f"   💰 Cost: ${result.total_cost:.2f}")
                
                if result.batch_files_created:
                    logger.info(f"   📦 Batch files created: {result.batch_files_created}")
                    print(f"\n🎯 INTEGRATION READY:")
                    print(f"Run these commands to process discovered products:")
                    for batch_file in result.batch_files_created:
                        print(f"   python main_scraper.py --batch-file {batch_file}")
                
                return True
            else:
                logger.error(f"❌ Weekly monitoring failed: {result.errors}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Weekly monitoring error: {e}")
            return False
    
    async def establish_baseline(self, retailer: str, category: str) -> bool:
        """
        Establish baseline for specific retailer/category
        Run this after manual review of entire catalog
        """
        
        try:
            logger.info(f"📋 Establishing baseline for {retailer} {category}")
            
            orchestrator = await self._get_orchestrator()
            result = await orchestrator.establish_baselines([retailer], [category])
            
            if result.success:
                logger.info(f"✅ Baseline established: {result.total_products_crawled} products")
                return True
            else:
                logger.error(f"❌ Baseline establishment failed: {result.errors}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Baseline establishment error: {e}")
            return False
    
    async def establish_all_baselines(self) -> bool:
        """
        Establish baselines for all supported retailers/categories
        Use this for initial system setup
        """
        
        try:
            logger.info("📋 Establishing baselines for all retailers")
            
            orchestrator = await self._get_orchestrator()
            result = await orchestrator.establish_baselines()
            
            if result.success:
                logger.info(f"✅ All baselines established: {result.total_products_crawled} total products")
                return True
            else:
                logger.error(f"❌ Baseline establishment failed: {result.errors}")
                return False
                
        except Exception as e:
            logger.error(f"❌ All baselines establishment error: {e}")
            return False
    
    async def run_manual_refresh(self, retailer: str, category: str) -> bool:
        """
        Run manual refresh for specific retailer/category
        Useful for testing or immediate updates
        """
        
        try:
            logger.info(f"🔄 Running manual refresh for {retailer} {category}")
            
            orchestrator = await self._get_orchestrator()
            result = await orchestrator.run_manual_refresh(retailer, category)
            
            if result.success:
                logger.info(f"✅ Manual refresh completed: {result.new_products_found} new products")
                return True
            else:
                logger.error(f"❌ Manual refresh failed: {result.errors}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Manual refresh error: {e}")
            return False
    
    # =================== SYSTEM MANAGEMENT COMMANDS ===================
    
    async def show_system_status(self):
        """Display comprehensive system status"""
        
        try:
            orchestrator = await self._get_orchestrator()
            status = await orchestrator.get_system_status()
            
            print("\n" + "="*60)
            print("📊 CATALOG MONITORING SYSTEM STATUS")
            print("="*60)
            
            # Database stats
            db_stats = status.get('database_stats', {})
            print(f"📝 Pending Reviews: {db_stats.get('pending_reviews', 0)}")
            print(f"📋 Active Baselines: {db_stats.get('active_baselines', 0)}")
            print(f"🏃 Recent Runs (7 days): {db_stats.get('recent_runs', 0)}")
            print(f"✅ Approved Pending Batch: {db_stats.get('approved_pending_batch', 0)}")
            
            # Baseline validation
            baseline_validation = status.get('baseline_validation', {})
            print(f"\n📋 BASELINE STATUS:")
            print(f"   Valid: {len(baseline_validation.get('valid', []))}")
            print(f"   Need Refresh: {len(baseline_validation.get('needs_refresh', []))}")
            print(f"   Missing: {len(baseline_validation.get('missing', []))}")
            
            if baseline_validation.get('missing'):
                print(f"   Missing Baselines: {baseline_validation['missing']}")
            
            # System configuration
            config = status.get('orchestrator_config', {})
            print(f"\n⚙️ CONFIGURATION:")
            print(f"   Weekly Monitoring: {'✅' if config.get('weekly_monitoring') else '❌'}")
            print(f"   Notifications: {'✅' if config.get('notifications') else '❌'}")
            print(f"   Max Concurrent: {config.get('max_concurrent_crawlers', 'N/A')}")
            
            # Supported retailers
            print(f"\n🏪 SUPPORTED RETAILERS: {status.get('supported_retailers', 0)}")
            
            factory_stats = CatalogCrawlerFactory.get_factory_stats()
            print(f"   Markdown Compatible: {', '.join(factory_stats['markdown_retailers'])}")
            print(f"   Playwright Required: {', '.join(factory_stats['playwright_retailers'])}")
            print(f"   Sort by Newest: {len(factory_stats['sort_supported_retailers'])}/{factory_stats['total_supported_retailers']}")
            
            print(f"\n⏰ Last Updated: {status.get('last_updated', 'Unknown')}")
            print("="*60)
            
        except Exception as e:
            logger.error(f"❌ Error showing system status: {e}")
    
    async def list_supported_retailers(self):
        """List all supported retailers with their configurations"""
        
        try:
            print("\n" + "="*80)
            print("🏪 SUPPORTED RETAILERS")
            print("="*80)
            
            retailers = CatalogCrawlerFactory.get_supported_retailers()
            
            for retailer in retailers:
                config = CatalogCrawlerFactory.get_retailer_config(retailer)
                if config:
                    extraction_method = config.get('extraction_method', 'unknown')
                    pagination_type = config.get('pagination_type', 'unknown')
                    has_sort = '✅' if config.get('has_sort_by_newest') else '❌'
                    special = config.get('special_notes', 'none')
                    
                    print(f"\n📍 {retailer.upper()}")
                    print(f"   Extraction: {extraction_method}")
                    print(f"   Pagination: {pagination_type}")
                    print(f"   Sort by Newest: {has_sort}")
                    if special != 'none':
                        print(f"   Special Notes: {special}")
                    
                    print(f"   Dresses: {config.get('dresses_url', 'N/A')}")
                    print(f"   Tops: {config.get('tops_url', 'N/A')}")
            
            factory_stats = CatalogCrawlerFactory.get_factory_stats()
            print(f"\n📊 SUMMARY:")
            print(f"   Total Retailers: {factory_stats['total_supported_retailers']}")
            print(f"   Markdown: {factory_stats['extraction_methods']['markdown']}")
            print(f"   Playwright: {factory_stats['extraction_methods']['playwright']}")
            print(f"   Pagination: {factory_stats['pagination_types']['pagination']}")
            print(f"   Infinite Scroll: {factory_stats['pagination_types']['infinite_scroll']}")
            print(f"   Hybrid: {factory_stats['pagination_types']['hybrid']}")
            print("="*80)
            
        except Exception as e:
            logger.error(f"❌ Error listing retailers: {e}")
    
    async def validate_baselines(self):
        """Validate all baselines and show recommendations"""
        
        try:
            orchestrator = await self._get_orchestrator()
            validation = await orchestrator.validate_baselines()
            
            print("\n" + "="*60)
            print("📋 BASELINE VALIDATION")
            print("="*60)
            
            print(f"✅ Valid Baselines ({len(validation['valid'])}):")
            for baseline in validation['valid']:
                print(f"   {baseline}")
            
            if validation['needs_refresh']:
                print(f"\n⚠️ Need Refresh ({len(validation['needs_refresh'])}):")
                for baseline in validation['needs_refresh']:
                    print(f"   {baseline}")
                print(f"\n💡 Run: python catalog_main.py --establish-baseline RETAILER CATEGORY")
            
            if validation['missing']:
                print(f"\n❌ Missing Baselines ({len(validation['missing'])}):")
                for baseline in validation['missing']:
                    print(f"   {baseline}")
                print(f"\n💡 Run: python catalog_main.py --establish-all-baselines")
            
            print("="*60)
            
        except Exception as e:
            logger.error(f"❌ Error validating baselines: {e}")
    
    async def show_pending_reviews(self, limit: int = 20):
        """Show products pending modesty review"""
        
        try:
            db_manager = CatalogDatabaseManager()
            products = await db_manager.get_products_for_review(limit=limit)
            
            print(f"\n📝 PRODUCTS PENDING REVIEW ({len(products)} shown, limit={limit})")
            print("="*80)
            
            if not products:
                print("No products pending review.")
                return
            
            for i, product in enumerate(products, 1):
                title = product['title'][:50] + '...' if len(product.get('title', '')) > 50 else product.get('title', 'N/A')
                price = f"${product['price']:.2f}" if product.get('price') else 'N/A'
                
                print(f"{i:2d}. {product['retailer'].upper()} | {product['category']}")
                print(f"    {title}")
                print(f"    Price: {price} | Discovered: {product['discovered_date']}")
                print(f"    URL: {product['catalog_url']}")
                print()
            
            print(f"💡 Use the manual review interface to process these products:")
            print(f"   Open: modesty_review_interface.html")
            print("="*80)
            
        except Exception as e:
            logger.error(f"❌ Error showing pending reviews: {e}")
    
    # =================== UTILITY METHODS ===================
    
    async def _simulate_monitoring_run(self, retailers: Optional[List[str]], 
                                     categories: Optional[List[str]]) -> bool:
        """Simulate monitoring run for dry run mode"""
        
        retailers = retailers or CatalogCrawlerFactory.get_supported_retailers()
        categories = categories or ['dresses', 'tops']
        
        print(f"\n🧪 DRY RUN SIMULATION")
        print(f"   Retailers: {', '.join(retailers)}")
        print(f"   Categories: {', '.join(categories)}")
        print(f"   Total combinations: {len(retailers) * len(categories)}")
        
        for retailer in retailers:
            for category in categories:
                crawler = CatalogCrawlerFactory.create_crawler(retailer, category)
                if crawler:
                    print(f"   ✅ {retailer} {category}: crawler available")
                else:
                    print(f"   ❌ {retailer} {category}: no crawler")
        
        print(f"\n✅ Dry run simulation completed")
        return True
    
    async def close(self):
        """Cleanup resources"""
        if self.orchestrator:
            await self.orchestrator.close()

# =================== CLI INTERFACE ===================

async def main():
    """Main CLI interface"""
    
    parser = argparse.ArgumentParser(
        description="Catalog Monitoring System - Automated new product discovery",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run weekly monitoring for all retailers
  python catalog_main.py --weekly-monitoring
  
  # Run weekly monitoring for specific retailers
  python catalog_main.py --weekly-monitoring --retailers revolve asos
  
  # Establish baseline for specific retailer/category
  python catalog_main.py --establish-baseline revolve dresses
  
  # Establish all baselines (initial setup)
  python catalog_main.py --establish-all-baselines
  
  # Manual refresh for testing
  python catalog_main.py --manual-refresh uniqlo tops
  
  # Show system status
  python catalog_main.py --status
  
  # Show pending reviews
  python catalog_main.py --pending-reviews
  
  # Validate baselines
  python catalog_main.py --validate-baselines
        """
    )
    
    # Main workflow commands
    parser.add_argument('--weekly-monitoring', action='store_true',
                       help='Run weekly catalog monitoring')
    parser.add_argument('--establish-baseline', nargs=2, metavar=('RETAILER', 'CATEGORY'),
                       help='Establish baseline for specific retailer and category')
    parser.add_argument('--establish-all-baselines', action='store_true',
                       help='Establish baselines for all retailers and categories')
    parser.add_argument('--manual-refresh', nargs=2, metavar=('RETAILER', 'CATEGORY'),
                       help='Run manual refresh for specific retailer and category')
    
    # System management commands
    parser.add_argument('--status', action='store_true',
                       help='Show comprehensive system status')
    parser.add_argument('--list-retailers', action='store_true',
                       help='List all supported retailers')
    parser.add_argument('--validate-baselines', action='store_true',
                       help='Validate all baselines')
    parser.add_argument('--pending-reviews', action='store_true',
                       help='Show products pending modesty review')
    
    # Filters and options
    parser.add_argument('--retailers', nargs='+', 
                       help='Specific retailers to process')
    parser.add_argument('--categories', nargs='+', choices=['dresses', 'tops'],
                       help='Specific categories to process')
    parser.add_argument('--dry-run', action='store_true',
                       help='Simulate run without actual crawling')
    parser.add_argument('--limit', type=int, default=20,
                       help='Limit for pending reviews display')
    
    args = parser.parse_args()
    
    # Validate arguments
    if not any([args.weekly_monitoring, args.establish_baseline, args.establish_all_baselines,
                args.manual_refresh, args.status, args.list_retailers, 
                args.validate_baselines, args.pending_reviews]):
        parser.print_help()
        return
    
    catalog_main = CatalogMain()
    
    try:
        # Execute requested command
        if args.weekly_monitoring:
            success = await catalog_main.run_weekly_monitoring(
                retailers=args.retailers, 
                categories=args.categories,
                dry_run=args.dry_run
            )
            sys.exit(0 if success else 1)
            
        elif args.establish_baseline:
            retailer, category = args.establish_baseline
            success = await catalog_main.establish_baseline(retailer, category)
            sys.exit(0 if success else 1)
            
        elif args.establish_all_baselines:
            success = await catalog_main.establish_all_baselines()
            sys.exit(0 if success else 1)
            
        elif args.manual_refresh:
            retailer, category = args.manual_refresh
            success = await catalog_main.run_manual_refresh(retailer, category)
            sys.exit(0 if success else 1)
            
        elif args.status:
            await catalog_main.show_system_status()
            
        elif args.list_retailers:
            await catalog_main.list_supported_retailers()
            
        elif args.validate_baselines:
            await catalog_main.validate_baselines()
            
        elif args.pending_reviews:
            await catalog_main.show_pending_reviews(limit=args.limit)
        
    except KeyboardInterrupt:
        logger.info("🛑 Interrupted by user")
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        sys.exit(1)
    finally:
        await catalog_main.close()

if __name__ == "__main__":
    asyncio.run(main())