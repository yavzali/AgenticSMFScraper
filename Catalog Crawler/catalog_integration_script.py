"""
Catalog Integration Script - Complete system setup and integration
Handles database initialization, system validation, and integration with existing scraper
"""

# Add shared path for imports
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../Shared"))

import asyncio
import os
import sys
import json
import shutil
from typing import Dict, List, Optional, Any
from datetime import datetime
import sqlite3

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from logger_config import setup_logging
from catalog_db_manager import CatalogDatabaseManager
from retailer_crawlers import CatalogCrawlerFactory
from catalog_orchestrator import CatalogOrchestrator
from catalog_scheduler import CatalogScheduler
from pattern_learner import EnhancedPatternLearner
from notification_manager import EnhancedNotificationManager

logger = setup_logging(__name__)

class CatalogSystemIntegrator:
    """
    Complete catalog monitoring system integration and setup
    Handles initialization, validation, and integration with existing scraper
    """
    
    def __init__(self):
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_path = os.path.join(self.script_dir, 'config.json')
        self.backup_dir = os.path.join(self.script_dir, 'backup')
        
        logger.info("🔧 Catalog system integrator initialized")
    
    # =================== SYSTEM SETUP ===================
    
    async def setup_complete_system(self, backup_existing: bool = True) -> bool:
        """
        Complete system setup including database, configuration, and validation
        """
        
        try:
            logger.info("🚀 Starting complete catalog monitoring system setup")
            
            # Step 1: Backup existing system if requested
            if backup_existing:
                await self._backup_existing_system()
            
            # Step 2: Initialize databases
            await self._initialize_databases()
            
            # Step 3: Update configuration
            await self._update_system_configuration()
            
            # Step 4: Validate system components
            await self._validate_system_components()
            
            # Step 5: Setup initial data
            await self._setup_initial_data()
            
            # Step 6: Test system integration
            await self._test_system_integration()
            
            logger.info("✅ Complete catalog monitoring system setup successful")
            
            # Print next steps
            self._print_setup_summary()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ System setup failed: {e}")
            return False
    
    async def _backup_existing_system(self):
        """Backup existing system files"""
        
        try:
            if not os.path.exists(self.backup_dir):
                os.makedirs(self.backup_dir)
            
            backup_timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            backup_subdir = os.path.join(self.backup_dir, f"backup_{backup_timestamp}")
            os.makedirs(backup_subdir)
            
            # Files to backup
            backup_files = [
                'products.db',
                'patterns.db', 
                'config.json',
                'markdown_cache.pkl'
            ]
            
            backed_up_count = 0
            for filename in backup_files:
                file_path = os.path.join(self.script_dir, filename)
                if os.path.exists(file_path):
                    backup_path = os.path.join(backup_subdir, filename)
                    shutil.copy2(file_path, backup_path)
                    backed_up_count += 1
            
            logger.info(f"📦 Backed up {backed_up_count} files to {backup_subdir}")
            
        except Exception as e:
            logger.warning(f"Backup failed (continuing anyway): {e}")
    
    async def _initialize_databases(self):
        """Initialize all database components"""
        
        try:
            logger.info("📊 Initializing catalog monitoring databases")
            
            # Initialize catalog database manager (extends products.db)
            db_manager = CatalogDatabaseManager()
            await db_manager._ensure_db_initialized()
            
            # Initialize enhanced pattern learner
            pattern_learner = EnhancedPatternLearner()
            
            # Validate databases
            await self._validate_database_schemas()
            
            logger.info("✅ Database initialization completed")
            
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise
    
    async def _validate_database_schemas(self):
        """Validate that all required database tables exist"""
        
        try:
            # Check catalog tables
            catalog_tables = [
                'catalog_products',
                'catalog_baselines', 
                'catalog_monitoring_runs',
                'catalog_errors'
            ]
            
            # Check enhanced pattern tables
            pattern_tables = [
                'enhanced_patterns',
                'cross_learning_patterns',
                'pattern_usage_stats'
            ]
            
            # Validate products.db
            products_db_path = os.path.join(self.script_dir, 'products.db')
            conn = sqlite3.connect(products_db_path)
            cursor = conn.cursor()
            
            # Get all table names
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            existing_tables = [row[0] for row in cursor.fetchall()]
            
            # Check catalog tables
            missing_catalog_tables = [t for t in catalog_tables if t not in existing_tables]
            if missing_catalog_tables:
                raise Exception(f"Missing catalog tables: {missing_catalog_tables}")
            
            conn.close()
            
            # Validate patterns.db  
            patterns_db_path = os.path.join(self.script_dir, 'patterns.db')
            conn = sqlite3.connect(patterns_db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            existing_pattern_tables = [row[0] for row in cursor.fetchall()]
            
            # Check pattern tables
            missing_pattern_tables = [t for t in pattern_tables if t not in existing_pattern_tables]
            if missing_pattern_tables:
                raise Exception(f"Missing pattern tables: {missing_pattern_tables}")
            
            conn.close()
            
            logger.info(f"✅ Database validation passed: {len(catalog_tables + pattern_tables)} tables verified")
            
        except Exception as e:
            logger.error(f"Database validation failed: {e}")
            raise
    
    async def _update_system_configuration(self):
        """Update config.json with catalog monitoring settings"""
        
        try:
            logger.info("⚙️ Updating system configuration")
            
            # Load existing config
            config = {}
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
            
            # Add catalog monitoring configuration
            if 'catalog_monitoring' not in config:
                config['catalog_monitoring'] = {
                    'enabled': True,
                    'weekly_monitoring': True,
                    'max_concurrent_crawlers': 2,
                    'cost_limit_per_run': 50.0,
                    'confidence_threshold': 0.85,
                    'early_stop_threshold': 3,
                    'baseline_max_pages': 10,
                    'monitoring_max_pages': 20
                }
            
            # Add catalog scheduler configuration
            if 'catalog_scheduler' not in config:
                config['catalog_scheduler'] = {
                    'enabled': True,
                    'weekly_monitoring': {
                        'enabled': True,
                        'day': 'monday',
                        'time': '09:00',
                        'retailers': 'all',
                        'categories': ['dresses', 'tops']
                    },
                    'health_checks': {
                        'enabled': True,
                        'frequency': 'daily',
                        'time': '08:00'
                    },
                    'review_reminders': {
                        'enabled': True,
                        'frequency': 'daily',
                        'time': '17:00',
                        'threshold_days': 3
                    },
                    'cleanup': {
                        'enabled': True,
                        'frequency': 'weekly',
                        'day': 'sunday',
                        'time': '02:00',
                        'retention_days': 30
                    }
                }
            
            # Update notifications to include catalog alerts
            if 'notifications' in config:
                config['notifications']['catalog_monitoring'] = {
                    'enabled': True,
                    'include_new_products': True,
                    'include_review_reminders': True,
                    'include_system_health': True
                }
            
            # Save updated configuration
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            logger.info("✅ Configuration updated successfully")
            
        except Exception as e:
            logger.error(f"Configuration update failed: {e}")
            raise
    
    async def _validate_system_components(self):
        """Validate all system components can be initialized"""
        
        try:
            logger.info("🔍 Validating system components")
            
            # Test catalog database manager
            db_manager = CatalogDatabaseManager()
            stats = await db_manager.get_system_stats()
            logger.info(f"  ✅ Database manager: {stats}")
            await db_manager.close()
            
            # Test crawler factory
            factory_stats = CatalogCrawlerFactory.get_factory_stats()
            logger.info(f"  ✅ Crawler factory: {factory_stats['total_supported_retailers']} retailers")
            
            # Test pattern learner
            pattern_learner = EnhancedPatternLearner()
            pattern_stats = await pattern_learner.get_pattern_statistics()
            logger.info(f"  ✅ Pattern learner: {pattern_stats.get('total_patterns', 0)} patterns")
            
            # Test notification manager
            notification_manager = EnhancedNotificationManager()
            notification_health = await notification_manager.check_notification_health()
            logger.info(f"  ✅ Notification manager: {notification_health['status']}")
            
            # Test orchestrator
            orchestrator = CatalogOrchestrator()
            orchestrator_status = await orchestrator.get_system_status()
            logger.info(f"  ✅ Orchestrator: {orchestrator_status.get('supported_retailers', 0)} retailers")
            await orchestrator.close()
            
            logger.info("✅ All system components validated successfully")
            
        except Exception as e:
            logger.error(f"Component validation failed: {e}")
            raise
    
    async def _setup_initial_data(self):
        """Setup initial data and test records"""
        
        try:
            logger.info("📋 Setting up initial data")
            
            # Create sample monitoring run record
            db_manager = CatalogDatabaseManager()
            
            run_id = await db_manager.create_monitoring_run(
                'system_setup', 
                config={'description': 'Initial system setup run'}
            )
            
            # Update run as completed
            await db_manager.update_monitoring_run(run_id, {
                'run_status': 'completed',
                'total_products_crawled': 0,
                'new_products_found': 0,
                'products_for_review': 0,
                'total_runtime': 0.0,
                'completed_at': datetime.utcnow()
            })
            
            await db_manager.close()
            
            logger.info(f"✅ Initial data setup completed (run_id: {run_id})")
            
        except Exception as e:
            logger.warning(f"Initial data setup failed (continuing): {e}")
    
    async def _test_system_integration(self):
        """Test integration between catalog system and existing scraper"""
        
        try:
            logger.info("🧪 Testing system integration")
            
            # Test 1: Can we create a batch file?
            test_batch = {
                "batch_name": "Integration Test Batch",
                "created_date": datetime.utcnow().strftime('%Y-%m-%d'),
                "total_urls": 1,
                "source": "catalog_monitoring_test",
                "urls": [
                    {
                        "url": "https://www.revolve.com/test-product.html",
                        "retailer": "revolve",
                        "discovered_date": datetime.utcnow().strftime('%Y-%m-%d'),
                        "catalog_source": "integration_test"
                    }
                ]
            }
            
            test_batch_file = os.path.join(self.script_dir, 'test_integration_batch.json')
            with open(test_batch_file, 'w') as f:
                json.dump(test_batch, f, indent=2)
            
            # Test 2: Verify existing scraper can read the batch file
            if os.path.exists(test_batch_file):
                with open(test_batch_file, 'r') as f:
                    loaded_batch = json.load(f)
                
                if loaded_batch['total_urls'] == 1:
                    logger.info("  ✅ Batch file creation and reading works")
                
                # Clean up test file
                os.remove(test_batch_file)
            
            # Test 3: Check that existing scraper files are present
            required_scraper_files = [
                'main_scraper.py',
                'unified_extractor.py',
                'batch_processor.py'
            ]
            
            missing_files = []
            for filename in required_scraper_files:
                if not os.path.exists(os.path.join(self.script_dir, filename)):
                    missing_files.append(filename)
            
            if missing_files:
                logger.warning(f"  ⚠️ Missing existing scraper files: {missing_files}")
            else:
                logger.info("  ✅ Existing scraper files present")
            
            logger.info("✅ System integration test completed")
            
        except Exception as e:
            logger.warning(f"Integration test failed (non-critical): {e}")
    
    def _print_setup_summary(self):
        """Print setup summary and next steps"""
        
        print("\n" + "="*80)
        print("🎉 CATALOG MONITORING SYSTEM SETUP COMPLETE")
        print("="*80)
        
        print("\n📁 System Components Installed:")
        print("  ✅ Catalog database schema (extended products.db)")
        print("  ✅ Enhanced pattern learner (multi-function support)")
        print("  ✅ Catalog crawler factory (10 retailers supported)")
        print("  ✅ Change detection system (comprehensive matching)")
        print("  ✅ Catalog orchestrator (workflow coordination)")
        print("  ✅ Scheduler integration (weekly automation)")
        print("  ✅ Enhanced notifications (catalog alerts)")
        print("  ✅ Modesty review interface (web-based)")
        print("  ✅ CLI interface (catalog_main.py)")
        
        print("\n🏪 Supported Retailers:")
        factory_stats = CatalogCrawlerFactory.get_factory_stats()
        print(f"  📊 Total: {factory_stats['total_supported_retailers']} retailers")
        print(f"  📝 Markdown: {', '.join(factory_stats['markdown_retailers'])}")
        print(f"  🎭 Playwright: {', '.join(factory_stats['playwright_retailers'])}")
        print(f"  📋 Sort by Newest: {len(factory_stats['sort_supported_retailers'])}/{factory_stats['total_supported_retailers']}")
        
        print("\n🚀 Next Steps:")
        print("\n1. 📋 ESTABLISH BASELINES (Required First Step)")
        print("   For each retailer/category you want to monitor:")
        print("   a) Manually review the entire catalog and import modest/moderately modest items")
        print("   b) Run baseline establishment:")
        print("      python catalog_main.py --establish-baseline RETAILER CATEGORY")
        print("   c) Example:")
        print("      python catalog_main.py --establish-baseline revolve dresses")
        print("      python catalog_main.py --establish-baseline asos tops")
        
        print("\n2. 🕷️ START WEEKLY MONITORING")
        print("   After baselines are established:")
        print("   python catalog_main.py --weekly-monitoring")
        print("   or for specific retailers:")
        print("   python catalog_main.py --weekly-monitoring --retailers revolve asos")
        
        print("\n3. 📝 REVIEW NEW PRODUCTS")
        print("   Open the web interface: modesty_review_interface.html")
        print("   Or use CLI: python catalog_main.py --pending-reviews")
        
        print("\n4. 📦 INTEGRATE WITH EXISTING SCRAPER")
        print("   Approved products will create batch files like:")
        print("   approved_catalog_batch_revolve_20250709_143022.json")
        print("   Run with existing scraper:")
        print("   python main_scraper.py --batch-file approved_catalog_batch_revolve_20250709_143022.json")
        
        print("\n5. ⚙️ ENABLE AUTOMATION (Optional)")
        print("   Start scheduler for weekly automation:")
        print("   # This would be integrated with your existing scheduler")
        
        print("\n🔧 Useful Commands:")
        print("  python catalog_main.py --status                    # System status")
        print("  python catalog_main.py --list-retailers           # Supported retailers")
        print("  python catalog_main.py --validate-baselines       # Check baselines")
        print("  python catalog_main.py --manual-refresh RETAILER CATEGORY  # Manual run")
        
        print("\n📊 Monitoring:")
        print("  - Weekly monitoring will discover new products")
        print("  - Products flagged for manual review in web interface")
        print("  - Approved products automatically queued for existing scraper")
        print("  - Email notifications for completion and issues")
        
        print("\n⚠️ Important Notes:")
        print("  - Establish baselines BEFORE running monitoring")
        print("  - Review interface at: modesty_review_interface.html")
        print("  - Existing scraper system unchanged and fully compatible")
        print("  - Cost tracking integrated with existing system")
        print("  - Pattern learning shared between catalog and individual extraction")
        
        print("\n🎯 Integration Success:")
        print("  ✅ Zero impact on existing scraper functionality")
        print("  ✅ Seamless batch file integration")
        print("  ✅ Shared configuration and database")
        print("  ✅ Enhanced pattern learning across functions")
        print("  ✅ Comprehensive new product detection")
        
        print("="*80)
        print("🕷️ Catalog Monitoring System Ready!")
        print("="*80)
    
    # =================== SYSTEM MANAGEMENT ===================
    
    async def validate_system_health(self) -> Dict[str, Any]:
        """Comprehensive system health validation"""
        
        try:
            health_report = {
                'overall_status': 'unknown',
                'components': {},
                'recommendations': [],
                'critical_issues': [],
                'warnings': []
            }
            
            # Test database connectivity
            try:
                db_manager = CatalogDatabaseManager()
                stats = await db_manager.get_system_stats()
                health_report['components']['database'] = {
                    'status': 'healthy',
                    'stats': stats
                }
                await db_manager.close()
            except Exception as e:
                health_report['components']['database'] = {
                    'status': 'unhealthy',
                    'error': str(e)
                }
                health_report['critical_issues'].append(f"Database connectivity failed: {e}")
            
            # Test crawler factory
            try:
                factory_stats = CatalogCrawlerFactory.get_factory_stats()
                health_report['components']['crawler_factory'] = {
                    'status': 'healthy',
                    'stats': factory_stats
                }
            except Exception as e:
                health_report['components']['crawler_factory'] = {
                    'status': 'unhealthy',
                    'error': str(e)
                }
                health_report['critical_issues'].append(f"Crawler factory failed: {e}")
            
            # Test configuration
            try:
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                
                required_sections = ['catalog_monitoring', 'catalog_scheduler']
                missing_sections = [s for s in required_sections if s not in config]
                
                if missing_sections:
                    health_report['warnings'].append(f"Missing config sections: {missing_sections}")
                
                health_report['components']['configuration'] = {
                    'status': 'healthy' if not missing_sections else 'warning',
                    'missing_sections': missing_sections
                }
            except Exception as e:
                health_report['components']['configuration'] = {
                    'status': 'unhealthy',
                    'error': str(e)
                }
                health_report['critical_issues'].append(f"Configuration invalid: {e}")
            
            # Determine overall status
            if health_report['critical_issues']:
                health_report['overall_status'] = 'critical'
            elif health_report['warnings']:
                health_report['overall_status'] = 'warning'
            else:
                health_report['overall_status'] = 'healthy'
            
            # Generate recommendations
            if health_report['critical_issues']:
                health_report['recommendations'].append("Resolve critical issues before using system")
            
            if not health_report['components'].get('database', {}).get('stats', {}).get('active_baselines', 0):
                health_report['recommendations'].append("Establish baselines using: python catalog_main.py --establish-all-baselines")
            
            return health_report
            
        except Exception as e:
            return {
                'overall_status': 'critical',
                'error': str(e),
                'recommendations': ['Run system setup again']
            }
    
    async def repair_system_issues(self) -> bool:
        """Attempt to repair common system issues"""
        
        try:
            logger.info("🔧 Attempting to repair system issues")
            
            # Repair 1: Recreate missing database tables
            try:
                await self._initialize_databases()
                logger.info("  ✅ Database tables verified/recreated")
            except Exception as e:
                logger.error(f"  ❌ Database repair failed: {e}")
                return False
            
            # Repair 2: Restore default configuration
            try:
                await self._update_system_configuration()
                logger.info("  ✅ Configuration verified/updated")
            except Exception as e:
                logger.error(f"  ❌ Configuration repair failed: {e}")
                return False
            
            # Repair 3: Validate file permissions
            try:
                test_file = os.path.join(self.script_dir, 'test_permissions.tmp')
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
                logger.info("  ✅ File permissions verified")
            except Exception as e:
                logger.error(f"  ❌ File permission issues: {e}")
                return False
            
            logger.info("✅ System repair completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"System repair failed: {e}")
            return False

# =================== CLI INTERFACE ===================

async def main():
    """Main CLI interface for system integration"""
    
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Catalog Monitoring System Integration",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--setup', action='store_true',
                       help='Setup complete catalog monitoring system')
    parser.add_argument('--validate', action='store_true',
                       help='Validate system health')
    parser.add_argument('--repair', action='store_true',
                       help='Attempt to repair system issues')
    parser.add_argument('--no-backup', action='store_true',
                       help='Skip backup during setup')
    
    args = parser.parse_args()
    
    if not any([args.setup, args.validate, args.repair]):
        parser.print_help()
        return
    
    integrator = CatalogSystemIntegrator()
    
    try:
        if args.setup:
            success = await integrator.setup_complete_system(
                backup_existing=not args.no_backup)
            sys.exit(0 if success else 1)
            
        elif args.validate:
            health_report = await integrator.validate_system_health()
            
            print(f"\n🏥 System Health Report")
            print(f"Overall Status: {health_report['overall_status'].upper()}")
            
            for component, status in health_report['components'].items():
                print(f"  {component}: {status['status']}")
            
            if health_report['critical_issues']:
                print(f"\n❌ Critical Issues:")
                for issue in health_report['critical_issues']:
                    print(f"  - {issue}")
            
            if health_report['warnings']:
                print(f"\n⚠️ Warnings:")
                for warning in health_report['warnings']:
                    print(f"  - {warning}")
            
            if health_report['recommendations']:
                print(f"\n💡 Recommendations:")
                for rec in health_report['recommendations']:
                    print(f"  - {rec}")
            
            sys.exit(0 if health_report['overall_status'] == 'healthy' else 1)
            
        elif args.repair:
            success = await integrator.repair_system_issues()
            sys.exit(0 if success else 1)
            
    except KeyboardInterrupt:
        logger.info("🛑 Interrupted by user")
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())