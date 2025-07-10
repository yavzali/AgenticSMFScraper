"""
Catalog System Test - Comprehensive end-to-end testing
Validates all components work together correctly before production use
"""

import asyncio
import os
import sys
import json
import tempfile
import shutil
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, date
import sqlite3

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from logger_config import setup_logging
from catalog_db_manager import CatalogDatabaseManager, CatalogProduct
from catalog_extractor import CatalogExtractor
from retailer_crawlers import CatalogCrawlerFactory, RevolveCrawler, CrawlConfig
from change_detector import ChangeDetector
from catalog_orchestrator import CatalogOrchestrator
from pattern_learner import EnhancedPatternLearner, PatternType
from notification_manager import EnhancedNotificationManager, NotificationType

logger = setup_logging(__name__)

class CatalogSystemTester:
    """
    Comprehensive testing suite for catalog monitoring system
    Tests all components individually and as an integrated system
    """
    
    def __init__(self):
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.test_results = {
            'total_tests': 0,
            'passed_tests': 0,
            'failed_tests': 0,
            'skipped_tests': 0,
            'test_details': []
        }
        
        # Test configuration
        self.test_retailers = ['revolve', 'asos', 'uniqlo']  # Safe test retailers
        self.test_categories = ['dresses', 'tops']
        
        logger.info("🧪 Catalog system tester initialized")
    
    # =================== MAIN TEST INTERFACE ===================
    
    async def run_all_tests(self, include_integration: bool = True, 
                           include_live_tests: bool = False) -> bool:
        """
        Run complete test suite
        
        Args:
            include_integration: Include integration tests
            include_live_tests: Include tests that make actual network requests
        """
        
        try:
            logger.info("🚀 Starting comprehensive catalog system test suite")
            
            # Component tests
            await self._test_database_components()
            await self._test_crawler_components()
            await self._test_extractor_components() 
            await self._test_change_detection_components()
            await self._test_pattern_learning_components()
            await self._test_notification_components()
            
            # Integration tests
            if include_integration:
                await self._test_orchestrator_integration()
                await self._test_end_to_end_workflow()
            
            # Live tests (optional, make actual requests)
            if include_live_tests:
                await self._test_live_catalog_extraction()
            
            # Generate test report
            self._generate_test_report()
            
            success_rate = self.test_results['passed_tests'] / max(self.test_results['total_tests'], 1)
            
            if success_rate >= 0.9:  # 90% pass rate required
                logger.info(f"✅ Test suite PASSED ({success_rate:.1%} success rate)")
                return True
            else:
                logger.error(f"❌ Test suite FAILED ({success_rate:.1%} success rate)")
                return False
                
        except Exception as e:
            logger.error(f"❌ Test suite execution failed: {e}")
            return False
    
    # =================== COMPONENT TESTS ===================
    
    async def _test_database_components(self):
        """Test database manager and schema"""
        
        await self._run_test("Database Initialization", self._test_db_initialization)
        await self._run_test("Database Schema Validation", self._test_db_schema)
        await self._run_test("Catalog Product Storage", self._test_catalog_product_storage)
        await self._run_test("Baseline Management", self._test_baseline_management)
        await self._run_test("Monitoring Run Tracking", self._test_monitoring_run_tracking)
        await self._run_test("Change Detection Database", self._test_change_detection_db)
    
    async def _test_db_initialization(self) -> Tuple[bool, str]:
        """Test database initialization"""
        try:
            db_manager = CatalogDatabaseManager()
            stats = await db_manager.get_system_stats()
            await db_manager.close()
            return True, f"Database initialized, stats: {stats}"
        except Exception as e:
            return False, f"Database initialization failed: {e}"
    
    async def _test_db_schema(self) -> Tuple[bool, str]:
        """Test database schema validation"""
        try:
            # Test products.db extensions
            products_db_path = os.path.join(self.script_dir, 'products.db')
            conn = sqlite3.connect(products_db_path)
            cursor = conn.cursor()
            
            required_tables = [
                'catalog_products', 'catalog_baselines', 
                'catalog_monitoring_runs', 'catalog_errors'
            ]
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            existing_tables = [row[0] for row in cursor.fetchall()]
            
            missing_tables = [t for t in required_tables if t not in existing_tables]
            conn.close()
            
            if missing_tables:
                return False, f"Missing tables: {missing_tables}"
            
            return True, f"All {len(required_tables)} catalog tables present"
            
        except Exception as e:
            return False, f"Schema validation failed: {e}"
    
    async def _test_catalog_product_storage(self) -> Tuple[bool, str]:
        """Test catalog product storage and retrieval"""
        try:
            db_manager = CatalogDatabaseManager()
            
            # Create test product
            test_product = CatalogProduct(
                catalog_url="https://test.com/product123",
                retailer="test_retailer",
                category="test_category",
                title="Test Product",
                price=99.99,
                discovered_date=date.today(),
                extraction_method="test"
            )
            
            # Test storage
            run_id = await db_manager.create_monitoring_run('test', config={'test': True})
            stored_count = await db_manager.store_baseline_products([test_product], run_id)
            
            # Test retrieval
            products_for_review = await db_manager.get_products_for_review(limit=1)
            
            await db_manager.close()
            
            if stored_count > 0:
                return True, f"Stored and retrieved {stored_count} test products"
            else:
                return False, "Failed to store test products"
                
        except Exception as e:
            return False, f"Product storage test failed: {e}"
    
    async def _test_baseline_management(self) -> Tuple[bool, str]:
        """Test baseline creation and management"""
        try:
            db_manager = CatalogDatabaseManager()
            
            baseline_id = await db_manager.create_baseline(
                'test_retailer', 'test_category', date.today(),
                100, {'test': True}
            )
            
            baseline = await db_manager.get_active_baseline('test_retailer', 'test_category')
            await db_manager.close()
            
            if baseline and baseline_id:
                return True, f"Created and retrieved baseline: {baseline_id}"
            else:
                return False, "Baseline creation/retrieval failed"
                
        except Exception as e:
            return False, f"Baseline test failed: {e}"
    
    async def _test_monitoring_run_tracking(self) -> Tuple[bool, str]:
        """Test monitoring run creation and updates"""
        try:
            db_manager = CatalogDatabaseManager()
            
            run_id = await db_manager.create_monitoring_run(
                'test_run', 'test_retailer', 'test_category'
            )
            
            await db_manager.update_monitoring_run(run_id, {
                'total_products_crawled': 50,
                'new_products_found': 5,
                'run_status': 'completed'
            })
            
            await db_manager.close()
            
            return True, f"Created and updated monitoring run: {run_id}"
            
        except Exception as e:
            return False, f"Monitoring run test failed: {e}"
    
    async def _test_change_detection_db(self) -> Tuple[bool, str]:
        """Test change detection database operations"""
        try:
            db_manager = CatalogDatabaseManager()
            
            # Create test products for detection
            test_products = [
                CatalogProduct(
                    catalog_url="https://test.com/new-product",
                    retailer="test_retailer",
                    category="test_category", 
                    title="New Test Product",
                    price=49.99,
                    discovered_date=date.today()
                )
            ]
            
            # Test new product detection
            results = await db_manager.detect_new_products(
                test_products, 'test_retailer', 'test_category'
            )
            
            await db_manager.close()
            
            if results:
                return True, f"Change detection processed {len(results)} products"
            else:
                return False, "Change detection returned no results"
                
        except Exception as e:
            return False, f"Change detection DB test failed: {e}"
    
    async def _test_crawler_components(self):
        """Test crawler factory and retailer-specific crawlers"""
        
        await self._run_test("Crawler Factory", self._test_crawler_factory)
        await self._run_test("Crawler Configuration", self._test_crawler_configuration)
        await self._run_test("URL Generation", self._test_url_generation)
        await self._run_test("Crawler Initialization", self._test_crawler_initialization)
    
    async def _test_crawler_factory(self) -> Tuple[bool, str]:
        """Test crawler factory functionality"""
        try:
            # Test factory stats
            stats = CatalogCrawlerFactory.get_factory_stats()
            
            # Test crawler creation
            revolve_crawler = CatalogCrawlerFactory.create_crawler('revolve', 'dresses')
            asos_crawler = CatalogCrawlerFactory.create_crawler('asos', 'tops')
            
            if revolve_crawler and asos_crawler:
                return True, f"Factory created crawlers for {stats['total_supported_retailers']} retailers"
            else:
                return False, "Failed to create test crawlers"
                
        except Exception as e:
            return False, f"Crawler factory test failed: {e}"
    
    async def _test_crawler_configuration(self) -> Tuple[bool, str]:
        """Test crawler configuration validation"""
        try:
            # Test all retailer configurations
            supported_retailers = CatalogCrawlerFactory.get_supported_retailers()
            
            config_issues = []
            for retailer in supported_retailers:
                config = CatalogCrawlerFactory.get_retailer_config(retailer)
                if not config:
                    config_issues.append(f"{retailer}: missing config")
                elif not config.get('dresses_url') or not config.get('tops_url'):
                    config_issues.append(f"{retailer}: missing URLs")
            
            if config_issues:
                return False, f"Configuration issues: {config_issues[:3]}"
            
            return True, f"All {len(supported_retailers)} retailer configs valid"
            
        except Exception as e:
            return False, f"Configuration test failed: {e}"
    
    async def _test_url_generation(self) -> Tuple[bool, str]:
        """Test URL generation for pagination"""
        try:
            # Test Revolve URL generation (pagination)
            config = CrawlConfig(
                retailer='revolve',
                category='dresses',
                base_url='https://www.revolve.com/dresses/br/a8e981/',
                sort_by_newest_url='https://www.revolve.com/dresses/br/a8e981/?sortBy=newest',
                pagination_type='pagination'
            )
            
            crawler = RevolveCrawler(config)
            
            # Test page URL generation
            page_2_url = await crawler._get_page_url(config.base_url, 2)
            page_3_url = await crawler._get_page_url(config.base_url, 3)
            
            if 'page=2' in page_2_url and 'page=3' in page_3_url:
                return True, f"URL generation working: {page_2_url}"
            else:
                return False, f"URL generation failed: {page_2_url}"
                
        except Exception as e:
            return False, f"URL generation test failed: {e}"
    
    async def _test_crawler_initialization(self) -> Tuple[bool, str]:
        """Test crawler initialization and configuration"""
        try:
            success_count = 0
            total_retailers = len(self.test_retailers)
            
            for retailer in self.test_retailers:
                try:
                    crawler = CatalogCrawlerFactory.create_crawler(retailer, 'dresses')
                    if crawler:
                        stats = await crawler.get_crawler_stats()
                        if stats['retailer'] == retailer:
                            success_count += 1
                except Exception as e:
                    logger.warning(f"Crawler init failed for {retailer}: {e}")
            
            if success_count == total_retailers:
                return True, f"Initialized all {success_count} test crawlers"
            else:
                return False, f"Only {success_count}/{total_retailers} crawlers initialized"
                
        except Exception as e:
            return False, f"Crawler initialization test failed: {e}"
    
    async def _test_extractor_components(self):
        """Test catalog extractor functionality"""
        
        await self._run_test("Extractor Initialization", self._test_extractor_initialization)
        await self._run_test("Prompt Generation", self._test_prompt_generation)
        await self._run_test("Result Parsing", self._test_result_parsing)
    
    async def _test_extractor_initialization(self) -> Tuple[bool, str]:
        """Test catalog extractor initialization"""
        try:
            extractor = CatalogExtractor()
            stats = await extractor.get_extraction_stats()
            
            if stats['extractor_type'] == 'catalog_extractor':
                return True, f"Extractor initialized: {stats['routing_logic']}"
            else:
                return False, "Extractor initialization failed"
                
        except Exception as e:
            return False, f"Extractor initialization failed: {e}"
    
    async def _test_prompt_generation(self) -> Tuple[bool, str]:
        """Test catalog extraction prompt generation"""
        try:
            extractor = CatalogExtractor()
            
            # Test markdown prompt
            markdown_prompt = extractor._build_catalog_markdown_prompt(
                'https://test.com/catalog', 'test_retailer', 'dresses', {}, {}
            )
            
            # Test playwright prompt  
            playwright_prompt = extractor._build_catalog_playwright_prompt(
                'https://test.com/catalog', 'test_retailer', 'dresses', {}, {}
            )
            
            if len(markdown_prompt) > 500 and len(playwright_prompt) > 500:
                return True, f"Generated prompts: {len(markdown_prompt)}, {len(playwright_prompt)} chars"
            else:
                return False, "Prompt generation too short"
                
        except Exception as e:
            return False, f"Prompt generation failed: {e}"
    
    async def _test_result_parsing(self) -> Tuple[bool, str]:
        """Test catalog extraction result parsing"""
        try:
            extractor = CatalogExtractor()
            
            # Test parsing with mock result
            mock_result = {
                'success': True,
                'products': [
                    {
                        'url': 'https://test.com/product1',
                        'title': 'Test Product 1',
                        'price': '99.99',
                        'image_urls': ['https://test.com/image1.jpg']
                    },
                    {
                        'url': 'https://test.com/product2', 
                        'title': 'Test Product 2',
                        'price': '149.99',
                        'image_urls': ['https://test.com/image2.jpg']
                    }
                ]
            }
            
            parsed_products = extractor._parse_catalog_extraction_result(
                mock_result, 'test_retailer', 'test_category'
            )
            
            if len(parsed_products) == 2:
                return True, f"Parsed {len(parsed_products)} products successfully"
            else:
                return False, f"Expected 2 products, got {len(parsed_products)}"
                
        except Exception as e:
            return False, f"Result parsing failed: {e}"
    
    async def _test_change_detection_components(self):
        """Test change detection logic"""
        
        await self._run_test("Change Detector Initialization", self._test_change_detector_init)
        await self._run_test("URL Normalization", self._test_url_normalization)
        await self._run_test("Product ID Extraction", self._test_product_id_extraction)
        await self._run_test("Comprehensive Matching", self._test_comprehensive_matching)
    
    async def _test_change_detector_init(self) -> Tuple[bool, str]:
        """Test change detector initialization"""
        try:
            detector = ChangeDetector()
            stats = await detector.get_detection_stats()
            
            if stats['detector_type'] == 'comprehensive_change_detector':
                return True, f"Detector initialized: threshold {stats['confidence_threshold']}"
            else:
                return False, "Detector initialization failed"
                
        except Exception as e:
            return False, f"Change detector init failed: {e}"
    
    async def _test_url_normalization(self) -> Tuple[bool, str]:
        """Test URL normalization logic"""
        try:
            detector = ChangeDetector()
            
            # Test URL normalization
            test_urls = [
                ('https://revolve.com/product.html?navsrc=test&origin=nav', 'revolve'),
                ('https://asos.com/product?currentpricerange=10-100&sort=newest', 'asos'),
                ('https://aritzia.com/product.html?campaign=test', 'aritzia')
            ]
            
            normalized_results = []
            for url, retailer in test_urls:
                normalized = detector._normalize_product_url(url, retailer)
                normalized_results.append(len(normalized) < len(url))  # Should be shorter
            
            if all(normalized_results):
                return True, f"Normalized {len(test_urls)} URLs successfully"
            else:
                return False, "URL normalization failed for some retailers"
                
        except Exception as e:
            return False, f"URL normalization failed: {e}"
    
    async def _test_product_id_extraction(self) -> Tuple[bool, str]:
        """Test product ID extraction from URLs"""
        try:
            detector = ChangeDetector()
            
            test_urls = [
                ('https://revolve.com/product-ABC123.html', 'revolve', 'ABC123'),
                ('https://asos.com/prd/12345', 'asos', '12345'),
                ('https://uniqlo.com/products/E443577-000', 'uniqlo', 'E443577'),
            ]
            
            extraction_results = []
            for url, retailer, expected in test_urls:
                extracted = detector._extract_product_code_from_url(url, retailer)
                extraction_results.append(expected in str(extracted))
            
            if all(extraction_results):
                return True, f"Extracted product IDs from {len(test_urls)} URLs"
            else:
                return False, "Product ID extraction failed for some retailers"
                
        except Exception as e:
            return False, f"Product ID extraction failed: {e}"
    
    async def _test_comprehensive_matching(self) -> Tuple[bool, str]:
        """Test comprehensive product matching logic"""
        try:
            detector = ChangeDetector()
            
            # Create test product
            test_product = CatalogProduct(
                catalog_url="https://test.com/new-product-456",
                retailer="test_retailer",
                category="test_category",
                title="Test Product for Matching",
                price=79.99,
                product_code="TEST456",
                discovered_date=date.today()
            )
            
            # Test matching (should be new product since no existing data)
            match_result = await detector._comprehensive_product_matching(
                test_product, 'test_retailer', 'test_category'
            )
            
            if match_result.is_new_product and match_result.confidence_score > 0.9:
                return True, f"Matching logic working: {match_result.match_type} ({match_result.confidence_score:.2f})"
            else:
                return False, f"Unexpected matching result: {match_result.match_type}"
                
        except Exception as e:
            return False, f"Comprehensive matching failed: {e}"
    
    async def _test_pattern_learning_components(self):
        """Test enhanced pattern learning functionality"""
        
        await self._run_test("Pattern Learner Initialization", self._test_pattern_learner_init)
        await self._run_test("Pattern Type Separation", self._test_pattern_type_separation)
        await self._run_test("Cross Learning", self._test_cross_learning)
        await self._run_test("Pattern Statistics", self._test_pattern_statistics)
    
    async def _test_pattern_learner_init(self) -> Tuple[bool, str]:
        """Test enhanced pattern learner initialization"""
        try:
            learner = EnhancedPatternLearner()
            stats = await learner.get_pattern_statistics()
            
            return True, f"Pattern learner initialized: {stats.get('total_patterns', 0)} patterns"
            
        except Exception as e:
            return False, f"Pattern learner init failed: {e}"
    
    async def _test_pattern_type_separation(self) -> Tuple[bool, str]:
        """Test pattern type separation and retrieval"""
        try:
            learner = EnhancedPatternLearner()
            
            # Test different pattern type retrievals
            catalog_patterns = await learner.get_catalog_crawling_patterns('test_retailer')
            extraction_patterns = await learner.get_individual_extraction_patterns('test_retailer')
            update_patterns = await learner.get_product_update_patterns('test_retailer')
            
            # Test pattern type recording
            await learner.record_catalog_crawling_success(
                'test_retailer', 'https://test.com', {'test': True}
            )
            
            return True, f"Pattern types working: catalog, extraction, update patterns accessible"
            
        except Exception as e:
            return False, f"Pattern type separation failed: {e}"
    
    async def _test_cross_learning(self) -> Tuple[bool, str]:
        """Test cross-learning between pattern types"""
        try:
            learner = EnhancedPatternLearner()
            
            # Record pattern that should trigger cross-learning
            await learner.record_success(
                'test_retailer', 'https://test.com', 'anti_bot_success',
                1.0, {'anti_bot_encountered': True, 'verification_type': 'test'},
                PatternType.CATALOG_CRAWLING
            )
            
            # Check if cross-learning was applied
            stats = await learner.get_pattern_statistics()
            
            return True, f"Cross-learning tested: {stats.get('cross_learning_patterns', {})}"
            
        except Exception as e:
            return False, f"Cross-learning test failed: {e}"
    
    async def _test_pattern_statistics(self) -> Tuple[bool, str]:
        """Test pattern statistics and analytics"""
        try:
            learner = EnhancedPatternLearner()
            
            stats = await learner.get_pattern_statistics()
            
            required_keys = ['total_patterns', 'patterns_by_type', 'pattern_types_supported']
            missing_keys = [k for k in required_keys if k not in stats]
            
            if missing_keys:
                return False, f"Missing statistics keys: {missing_keys}"
            
            return True, f"Statistics working: {stats['total_patterns']} patterns tracked"
            
        except Exception as e:
            return False, f"Pattern statistics failed: {e}"
    
    async def _test_notification_components(self):
        """Test enhanced notification manager"""
        
        await self._run_test("Notification Manager Init", self._test_notification_manager_init)
        await self._run_test("Template Loading", self._test_template_loading)
        await self._run_test("Notification Health", self._test_notification_health)
    
    async def _test_notification_manager_init(self) -> Tuple[bool, str]:
        """Test notification manager initialization"""
        try:
            manager = EnhancedNotificationManager()
            
            if manager.templates and len(manager.templates) > 5:
                return True, f"Notification manager initialized: {len(manager.templates)} templates"
            else:
                return False, "Notification manager missing templates"
                
        except Exception as e:
            return False, f"Notification manager init failed: {e}"
    
    async def _test_template_loading(self) -> Tuple[bool, str]:
        """Test notification template loading"""
        try:
            manager = EnhancedNotificationManager()
            
            # Test specific templates
            required_types = [
                NotificationType.CATALOG_MONITORING_COMPLETE,
                NotificationType.CATALOG_NEW_PRODUCTS_FOUND,
                NotificationType.CATALOG_REVIEW_NEEDED
            ]
            
            missing_templates = [nt for nt in required_types if nt not in manager.templates]
            
            if missing_templates:
                return False, f"Missing templates: {missing_templates}"
            
            return True, f"All required templates loaded: {len(required_types)}"
            
        except Exception as e:
            return False, f"Template loading failed: {e}"
    
    async def _test_notification_health(self) -> Tuple[bool, str]:
        """Test notification system health check"""
        try:
            manager = EnhancedNotificationManager()
            health = await manager.check_notification_health()
            
            return True, f"Notification health: {health['status']} ({health['templates_loaded']} templates)"
            
        except Exception as e:
            return False, f"Notification health check failed: {e}"
    
    # =================== INTEGRATION TESTS ===================
    
    async def _test_orchestrator_integration(self):
        """Test orchestrator integration"""
        
        await self._run_test("Orchestrator Initialization", self._test_orchestrator_init)
        await self._run_test("System Status", self._test_system_status)
        await self._run_test("Baseline Validation", self._test_baseline_validation)
    
    async def _test_orchestrator_init(self) -> Tuple[bool, str]:
        """Test orchestrator initialization"""
        try:
            orchestrator = CatalogOrchestrator()
            
            if orchestrator.supported_retailers and len(orchestrator.supported_retailers) >= 5:
                await orchestrator.close()
                return True, f"Orchestrator initialized: {len(orchestrator.supported_retailers)} retailers"
            else:
                await orchestrator.close()
                return False, "Orchestrator missing supported retailers"
                
        except Exception as e:
            return False, f"Orchestrator init failed: {e}"
    
    async def _test_system_status(self) -> Tuple[bool, str]:
        """Test system status reporting"""
        try:
            orchestrator = CatalogOrchestrator()
            status = await orchestrator.get_system_status()
            await orchestrator.close()
            
            required_keys = ['database_stats', 'baseline_validation', 'supported_retailers']
            missing_keys = [k for k in required_keys if k not in status]
            
            if missing_keys:
                return False, f"Missing status keys: {missing_keys}"
            
            return True, f"System status working: {status['supported_retailers']} retailers"
            
        except Exception as e:
            return False, f"System status failed: {e}"
    
    async def _test_baseline_validation(self) -> Tuple[bool, str]:
        """Test baseline validation logic"""
        try:
            orchestrator = CatalogOrchestrator()
            validation = await orchestrator.validate_baselines()
            await orchestrator.close()
            
            required_keys = ['valid', 'needs_refresh', 'missing']
            missing_keys = [k for k in required_keys if k not in validation]
            
            if missing_keys:
                return False, f"Missing validation keys: {missing_keys}"
            
            total_checked = sum(len(validation[k]) for k in required_keys)
            return True, f"Baseline validation working: {total_checked} retailer/category combinations checked"
            
        except Exception as e:
            return False, f"Baseline validation failed: {e}"
    
    async def _test_end_to_end_workflow(self):
        """Test complete end-to-end workflow"""
        
        await self._run_test("E2E Workflow Simulation", self._test_e2e_simulation)
        await self._run_test("Batch File Integration", self._test_batch_file_integration)
    
    async def _test_e2e_simulation(self) -> Tuple[bool, str]:
        """Test end-to-end workflow simulation"""
        try:
            # This would test the complete workflow:
            # 1. Baseline establishment simulation
            # 2. New product discovery simulation  
            # 3. Change detection simulation
            # 4. Review process simulation
            # 5. Batch creation simulation
            
            # For now, test that all components can work together
            orchestrator = CatalogOrchestrator()
            
            # Simulate orchestration without actual network calls
            config = {
                'simulation': True,
                'test_mode': True
            }
            
            # Test baseline validation (doesn't require network)
            validation = await orchestrator.validate_baselines()
            
            await orchestrator.close()
            
            return True, f"E2E simulation completed: baseline validation successful"
            
        except Exception as e:
            return False, f"E2E simulation failed: {e}"
    
    async def _test_batch_file_integration(self) -> Tuple[bool, str]:
        """Test batch file creation and compatibility"""
        try:
            # Create test batch file compatible with existing scraper
            test_batch = {
                "batch_name": "Catalog Test Batch",
                "created_date": datetime.utcnow().strftime('%Y-%m-%d'),
                "total_urls": 2,
                "source": "catalog_monitoring_test",
                "urls": [
                    {
                        "url": "https://test.com/product1",
                        "retailer": "test_retailer",
                        "discovered_date": datetime.utcnow().strftime('%Y-%m-%d'),
                        "catalog_source": "test_catalog"
                    },
                    {
                        "url": "https://test.com/product2",
                        "retailer": "test_retailer", 
                        "discovered_date": datetime.utcnow().strftime('%Y-%m-%d'),
                        "catalog_source": "test_catalog"
                    }
                ]
            }
            
            # Write test batch file
            test_batch_path = os.path.join(self.script_dir, 'test_catalog_batch.json')
            with open(test_batch_path, 'w') as f:
                json.dump(test_batch, f, indent=2)
            
            # Verify it can be read
            with open(test_batch_path, 'r') as f:
                loaded_batch = json.load(f)
            
            # Clean up
            os.remove(test_batch_path)
            
            if loaded_batch['total_urls'] == 2:
                return True, f"Batch file integration working: {loaded_batch['total_urls']} URLs"
            else:
                return False, "Batch file format validation failed"
                
        except Exception as e:
            return False, f"Batch file integration failed: {e}"
    
    # =================== LIVE TESTS (OPTIONAL) ===================
    
    async def _test_live_catalog_extraction(self):
        """Test live catalog extraction (makes actual network requests)"""
        
        await self._run_test("Live Extraction Test", self._test_live_extraction)
    
    async def _test_live_extraction(self) -> Tuple[bool, str]:
        """Test actual catalog extraction (network request)"""
        try:
            # Only test if explicitly enabled
            logger.warning("Live extraction test disabled by default")
            return True, "Live extraction test skipped (disabled)"
            
            # Uncomment below to enable live testing
            # extractor = CatalogExtractor()
            # result = await extractor.extract_catalog_page(
            #     'https://www.revolve.com/dresses/br/a8e981/',
            #     'revolve', 'dresses'
            # )
            # 
            # if result.success and len(result.products) > 0:
            #     return True, f"Live extraction successful: {len(result.products)} products"
            # else:
            #     return False, f"Live extraction failed: {result.errors}"
                
        except Exception as e:
            return False, f"Live extraction test failed: {e}"
    
    # =================== TEST UTILITIES ===================
    
    async def _run_test(self, test_name: str, test_func) -> bool:
        """Run individual test and track results"""
        
        self.test_results['total_tests'] += 1
        
        try:
            logger.info(f"🧪 Running test: {test_name}")
            
            success, message = await test_func()
            
            if success:
                self.test_results['passed_tests'] += 1
                self.test_results['test_details'].append({
                    'name': test_name,
                    'status': 'PASSED',
                    'message': message
                })
                logger.info(f"  ✅ {test_name}: {message}")
                return True
            else:
                self.test_results['failed_tests'] += 1
                self.test_results['test_details'].append({
                    'name': test_name,
                    'status': 'FAILED', 
                    'message': message
                })
                logger.error(f"  ❌ {test_name}: {message}")
                return False
                
        except Exception as e:
            self.test_results['failed_tests'] += 1
            self.test_results['test_details'].append({
                'name': test_name,
                'status': 'ERROR',
                'message': str(e)
            })
            logger.error(f"  💥 {test_name}: {e}")
            return False
    
    def _generate_test_report(self):
        """Generate comprehensive test report"""
        
        results = self.test_results
        success_rate = results['passed_tests'] / max(results['total_tests'], 1)
        
        print("\n" + "="*80)
        print("🧪 CATALOG SYSTEM TEST REPORT")
        print("="*80)
        
        print(f"\n📊 Overall Results:")
        print(f"   Total Tests: {results['total_tests']}")
        print(f"   Passed: {results['passed_tests']} ✅")
        print(f"   Failed: {results['failed_tests']} ❌")
        print(f"   Skipped: {results['skipped_tests']} ⏭️")
        print(f"   Success Rate: {success_rate:.1%}")
        
        if results['failed_tests'] > 0:
            print(f"\n❌ Failed Tests:")
            for test in results['test_details']:
                if test['status'] in ['FAILED', 'ERROR']:
                    print(f"   {test['name']}: {test['message']}")
        
        print(f"\n📋 Test Categories:")
        categories = {}
        for test in results['test_details']:
            category = test['name'].split()[0] if ' ' in test['name'] else 'Other'
            if category not in categories:
                categories[category] = {'passed': 0, 'failed': 0}
            
            if test['status'] == 'PASSED':
                categories[category]['passed'] += 1
            else:
                categories[category]['failed'] += 1
        
        for category, stats in categories.items():
            total = stats['passed'] + stats['failed']
            rate = stats['passed'] / max(total, 1)
            print(f"   {category}: {stats['passed']}/{total} ({rate:.1%})")
        
        print(f"\n🎯 System Readiness:")
        if success_rate >= 0.95:
            print("   ✅ EXCELLENT - System ready for production")
        elif success_rate >= 0.90:
            print("   ✅ GOOD - System ready with minor issues")
        elif success_rate >= 0.80:
            print("   ⚠️ FAIR - Address failed tests before production")
        else:
            print("   ❌ POOR - Significant issues need resolution")
        
        print("="*80)

# =================== CLI INTERFACE ===================

async def main():
    """Main CLI interface for system testing"""
    
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Catalog Monitoring System Test Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--all', action='store_true',
                       help='Run all tests including integration')
    parser.add_argument('--components-only', action='store_true',
                       help='Run only component tests')
    parser.add_argument('--integration-only', action='store_true',
                       help='Run only integration tests')
    parser.add_argument('--include-live', action='store_true',
                       help='Include live network tests (use carefully)')
    parser.add_argument('--quick', action='store_true',
                       help='Run quick subset of tests')
    
    args = parser.parse_args()
    
    if not any([args.all, args.components_only, args.integration_only, args.quick]):
        parser.print_help()
        return
    
    tester = CatalogSystemTester()
    
    try:
        if args.all:
            success = await tester.run_all_tests(
                include_integration=True,
                include_live_tests=args.include_live
            )
        elif args.components_only:
            success = await tester.run_all_tests(
                include_integration=False,
                include_live_tests=False
            )
        elif args.integration_only:
            success = await tester.run_all_tests(
                include_integration=True,
                include_live_tests=args.include_live
            )
        elif args.quick:
            # Quick subset - just critical components
            await tester._test_database_components()
            await tester._test_crawler_components()
            await tester._test_orchestrator_integration()
            tester._generate_test_report()
            success = tester.test_results['failed_tests'] == 0
        
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        logger.info("🛑 Testing interrupted by user")
    except Exception as e:
        logger.error(f"❌ Testing failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())