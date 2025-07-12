#!/usr/bin/env python3
"""
Comprehensive Catalog Crawler Testing Script
Tests all crawler mechanics without requiring API keys
"""

import asyncio
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../Shared"))
sys.path.append(os.path.dirname(__file__))

import json
import time
from typing import Dict, List, Optional, Any
from datetime import datetime

from logger_config import setup_logging
from catalog_extractor import CatalogExtractor, CatalogExtractionResult
from retailer_crawlers import CatalogCrawlerFactory, RevolveCrawler, CrawlConfig
from catalog_db_manager import CatalogDatabaseManager, CatalogProduct

logger = setup_logging(__name__)

class CatalogCrawlerTester:
    """
    Comprehensive testing for catalog crawler mechanics
    Tests everything except actual API-based extraction
    """
    
    def __init__(self):
        self.test_results = []
        self.passed = 0
        self.failed = 0
        
    async def run_comprehensive_test(self):
        """Run all catalog crawler tests"""
        
        print("🧪 COMPREHENSIVE CATALOG CRAWLER TEST SUITE")
        print("=" * 60)
        
        # Test 1: URL Generation and Crawling Logic
        await self._test_url_generation()
        
        # Test 2: Crawler Configuration
        await self._test_crawler_configuration()
        
        # Test 3: Database Integration
        await self._test_database_integration()
        
        # Test 4: Mock Extraction Pipeline
        await self._test_extraction_pipeline()
        
        # Test 5: Browser Setup (without API calls)
        await self._test_browser_setup()
        
        # Test 6: Error Handling
        await self._test_error_handling()
        
        # Test 7: Performance Testing
        await self._test_performance()
        
        # Generate final report
        self._generate_report()
        
        return self.passed > self.failed
    
    async def _test_url_generation(self):
        """Test URL generation for all retailers"""
        print("\n🔗 Testing URL Generation...")
        
        try:
            factory = CatalogCrawlerFactory()
            
            test_cases = [
                ('revolve', 'dresses'),
                ('asos', 'tops'),
                ('uniqlo', 'dresses'),
                ('hm', 'tops'),
                ('mango', 'dresses')
            ]
            
            for retailer, category in test_cases:
                crawler = factory.create_crawler(retailer, category)
                
                # Test URL generation for multiple pages
                for page in [1, 2, 3]:
                    url = await crawler._get_page_url(crawler.config.base_url, page)
                    
                    # Validate URL structure
                    if not url.startswith('https://'):
                        raise ValueError(f"Invalid URL for {retailer}: {url}")
                    
                    if retailer not in url:
                        raise ValueError(f"Retailer name not in URL: {url}")
                    
                    print(f"  ✅ {retailer} {category} page {page}: {url[:50]}...")
            
            self._log_test("URL Generation", True, f"Generated URLs for {len(test_cases)} retailers")
            
        except Exception as e:
            self._log_test("URL Generation", False, str(e))
    
    async def _test_crawler_configuration(self):
        """Test crawler configuration and setup"""
        print("\n⚙️ Testing Crawler Configuration...")
        
        try:
            factory = CatalogCrawlerFactory()
            
            # Test all supported retailers
            supported_retailers = ['revolve', 'asos', 'uniqlo', 'hm', 'mango', 
                                 'aritzia', 'anthropologie', 'abercrombie', 'nordstrom', 'urban_outfitters']
            
            for retailer in supported_retailers:
                crawler = factory.create_crawler(retailer, 'dresses')
                
                # Test configuration loading
                config = crawler.config
                if not config:
                    raise ValueError(f"No config loaded for {retailer}")
                
                # Test crawler initialization
                if not hasattr(crawler, 'extractor'):
                    raise ValueError(f"Extractor not initialized for {retailer}")
                
                print(f"  ✅ {retailer}: Config loaded, extractor initialized")
            
            self._log_test("Crawler Configuration", True, f"Configured {len(supported_retailers)} retailers")
            
        except Exception as e:
            self._log_test("Crawler Configuration", False, str(e))
    
    async def _test_database_integration(self):
        """Test database operations"""
        print("\n🗄️ Testing Database Integration...")
        
        try:
            db_manager = CatalogDatabaseManager()
            
            # Test database connection
            stats = await db_manager.get_system_stats()
            print(f"  📊 Database stats: {stats}")
            
            # Test product storage with mock data
            mock_products = [
                CatalogProduct(
                    catalog_url="https://test.com/product1",
                    retailer="test_retailer",
                    category="test_category",
                    title="Test Product 1",
                    price=99.99,
                    discovered_date=datetime.now().date(),
                    extraction_method="test"
                ),
                CatalogProduct(
                    catalog_url="https://test.com/product2",
                    retailer="test_retailer",
                    category="test_category",
                    title="Test Product 2",
                    price=149.99,
                    discovered_date=datetime.now().date(),
                    extraction_method="test"
                )
            ]
            
            # Test monitoring run creation
            run_id = await db_manager.create_monitoring_run('test_retailer', {'test': True})
            print(f"  ✅ Created monitoring run: {run_id}")
            
            # Test product storage
            stored_count = await db_manager.store_baseline_products(mock_products, run_id)
            print(f"  ✅ Stored {stored_count} test products")
            
            await db_manager.close()
            
            self._log_test("Database Integration", True, f"Stored {stored_count} products")
            
        except Exception as e:
            self._log_test("Database Integration", False, str(e))
    
    async def _test_extraction_pipeline(self):
        """Test extraction pipeline with mock data"""
        print("\n🔄 Testing Extraction Pipeline...")
        
        try:
            extractor = CatalogExtractor()
            
            # Test prompt generation
            prompt = extractor._build_catalog_markdown_prompt(
                "https://test.com/catalog",
                "test_retailer",
                "dresses",
                {},
                {}
            )
            
            if len(prompt) < 100:
                raise ValueError("Prompt too short")
            
            print(f"  ✅ Generated prompt: {len(prompt)} characters")
            
            # Test result parsing with mock data
            mock_extraction_result = {
                "success": True,
                "products": [
                    {
                        "url": "https://test.com/product1",
                        "title": "Test Dress 1",
                        "price": 89.99,
                        "sale_status": "regular",
                        "image_urls": ["https://test.com/image1.jpg"],
                        "availability": "in_stock"
                    },
                    {
                        "url": "https://test.com/product2",
                        "title": "Test Dress 2",
                        "price": 129.99,
                        "original_price": 149.99,
                        "sale_status": "on_sale",
                        "image_urls": ["https://test.com/image2.jpg"],
                        "availability": "in_stock"
                    }
                ]
            }
            
            parsed_products = extractor._parse_catalog_extraction_result(
                mock_extraction_result, "test_retailer", "dresses"
            )
            
            print(f"  ✅ Parsed {len(parsed_products)} products")
            
            # Test product cleaning
            for product in parsed_products:
                cleaned = extractor._clean_catalog_product(product, "test_retailer", "dresses")
                if not cleaned:
                    raise ValueError("Product cleaning failed")
            
            print(f"  ✅ Cleaned {len(parsed_products)} products")
            
            self._log_test("Extraction Pipeline", True, f"Processed {len(parsed_products)} products")
            
        except Exception as e:
            self._log_test("Extraction Pipeline", False, str(e))
    
    async def _test_browser_setup(self):
        """Test browser setup without making actual requests"""
        print("\n🌐 Testing Browser Setup...")
        
        try:
            # Test browser configuration loading
            config_path = os.path.join(os.path.dirname(__file__), '../Shared/config.json')
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            browser_config = config.get('agents', {}).get('browser_use', {})
            if not browser_config:
                raise ValueError("Browser configuration not found")
            
            print(f"  ✅ Browser config loaded: {browser_config.get('model', 'unknown')} model")
            
            # Test anti-detection configuration
            anti_detection = browser_config.get('anti_detection', {})
            if not anti_detection.get('stealth_mode'):
                raise ValueError("Stealth mode not enabled")
            
            print(f"  ✅ Anti-detection configured: stealth mode enabled")
            
            # Test verification handling
            verification = browser_config.get('verification_handling', {})
            if not verification.get('checkbox_click_enabled'):
                raise ValueError("Verification handling not configured")
            
            print(f"  ✅ Verification handling configured")
            
            self._log_test("Browser Setup", True, "Browser configuration validated")
            
        except Exception as e:
            self._log_test("Browser Setup", False, str(e))
    
    async def _test_error_handling(self):
        """Test error handling scenarios"""
        print("\n❌ Testing Error Handling...")
        
        try:
            extractor = CatalogExtractor()
            
            # Test invalid URL handling
            result = await extractor.extract_catalog_page(
                "invalid-url",
                "test_retailer",
                "dresses"
            )
            
            if result.success:
                raise ValueError("Should have failed with invalid URL")
            
            print(f"  ✅ Invalid URL handled correctly")
            
            # Test empty extraction result
            empty_result = extractor._parse_catalog_extraction_result({}, "test", "test")
            if len(empty_result) > 0:
                raise ValueError("Should return empty list for empty input")
            
            print(f"  ✅ Empty results handled correctly")
            
            self._log_test("Error Handling", True, "Error scenarios handled properly")
            
        except Exception as e:
            self._log_test("Error Handling", False, str(e))
    
    async def _test_performance(self):
        """Test performance characteristics"""
        print("\n⚡ Testing Performance...")
        
        try:
            extractor = CatalogExtractor()
            
            # Test prompt generation performance
            start_time = time.time()
            for i in range(100):
                prompt = extractor._build_catalog_markdown_prompt(
                    f"https://test.com/catalog/{i}",
                    "test_retailer",
                    "dresses",
                    {},
                    {}
                )
            prompt_time = time.time() - start_time
            
            print(f"  ✅ Prompt generation: {prompt_time:.3f}s for 100 prompts")
            
            # Test parsing performance
            mock_data = {
                "products": [
                    {
                        "url": f"https://test.com/product{i}",
                        "title": f"Test Product {i}",
                        "price": 99.99 + i,
                        "sale_status": "regular",
                        "image_urls": [f"https://test.com/image{i}.jpg"],
                        "availability": "in_stock"
                    }
                    for i in range(100)
                ]
            }
            
            start_time = time.time()
            parsed = extractor._parse_catalog_extraction_result(mock_data, "test", "test")
            parse_time = time.time() - start_time
            
            print(f"  ✅ Parsing performance: {parse_time:.3f}s for 100 products")
            
            self._log_test("Performance", True, f"Prompt: {prompt_time:.3f}s, Parse: {parse_time:.3f}s")
            
        except Exception as e:
            self._log_test("Performance", False, str(e))
    
    def _log_test(self, test_name: str, success: bool, details: str):
        """Log test result"""
        result = {
            'test': test_name,
            'success': success,
            'details': details,
            'timestamp': datetime.now().isoformat()
        }
        
        self.test_results.append(result)
        
        if success:
            self.passed += 1
            print(f"  ✅ {test_name}: PASSED - {details}")
        else:
            self.failed += 1
            print(f"  ❌ {test_name}: FAILED - {details}")
    
    def _generate_report(self):
        """Generate comprehensive test report"""
        print("\n" + "=" * 60)
        print("🧪 CATALOG CRAWLER TEST REPORT")
        print("=" * 60)
        
        total_tests = len(self.test_results)
        success_rate = (self.passed / total_tests) * 100 if total_tests > 0 else 0
        
        print(f"📊 Overall Results:")
        print(f"   Total Tests: {total_tests}")
        print(f"   Passed: {self.passed} ✅")
        print(f"   Failed: {self.failed} ❌")
        print(f"   Success Rate: {success_rate:.1f}%")
        
        if self.failed > 0:
            print(f"\n❌ Failed Tests:")
            for result in self.test_results:
                if not result['success']:
                    print(f"   - {result['test']}: {result['details']}")
        
        print(f"\n🎯 System Status:")
        if success_rate >= 90:
            print("   ✅ EXCELLENT - System ready for API key testing")
        elif success_rate >= 75:
            print("   ⚠️  GOOD - Minor issues to address")
        else:
            print("   ❌ NEEDS WORK - Major issues found")
        
        print("\n📋 Next Steps:")
        print("   1. Fix any failed tests")
        print("   2. Get valid API keys (DeepSeek/Google)")
        print("   3. Run live extraction tests")
        print("   4. Establish production baselines")

async def main():
    """Main test execution"""
    tester = CatalogCrawlerTester()
    
    try:
        success = await tester.run_comprehensive_test()
        exit_code = 0 if success else 1
        
    except Exception as e:
        print(f"❌ Test suite failed: {e}")
        exit_code = 1
    
    return exit_code

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code) 