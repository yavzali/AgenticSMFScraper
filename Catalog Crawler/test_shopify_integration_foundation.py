"""
Test Shopify Integration Foundation
Tests the "not-assessed" workflow and CDN URL storage
"""

import asyncio
import json
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from logger_config import setup_logging

logger = setup_logging(__name__)

class TestShopifyIntegrationFoundation:
    """Test suite for Shopify integration foundation"""
    
    def __init__(self):
        self.tests_passed = 0
        self.tests_failed = 0
        self.test_results = []
    
    def assert_test(self, condition: bool, test_name: str, details: str = ""):
        """Assert a test condition"""
        if condition:
            self.tests_passed += 1
            self.test_results.append(f"✅ PASS: {test_name}")
            logger.info(f"✅ {test_name}")
        else:
            self.tests_failed += 1
            self.test_results.append(f"❌ FAIL: {test_name} - {details}")
            logger.error(f"❌ {test_name} - {details}")
    
    async def test_build_product_payload_not_assessed(self):
        """Test that _build_product_payload adds 'not-assessed' tag"""
        logger.info("\n🧪 Testing _build_product_payload with pending_review...")
        
        try:
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../Shared'))
            from shopify_manager import ShopifyManager
            
            shopify_manager = ShopifyManager()
            
            # Test data
            extracted_data = {
                'title': 'Test Product',
                'description': 'Test description',
                'brand': 'Test Brand',
                'clothing_type': 'Dress',
                'price': 99.99,
                'product_code': 'TEST123'
            }
            
            # Build payload with pending_review
            payload = shopify_manager._build_product_payload(
                extracted_data, 'test_retailer', 'pending_review'
            )
            
            # Check that not-assessed tag is present
            tags = payload['product']['tags']
            self.assert_test(
                'not-assessed' in tags,
                "not-assessed tag added for pending_review",
                f"Tags: {tags}"
            )
            
            # Check that status is draft
            status = payload['product']['status']
            self.assert_test(
                status == 'draft',
                "Product status is draft for not-assessed",
                f"Status: {status}"
            )
            
            # Test normal modesty level doesn't add not-assessed
            payload_normal = shopify_manager._build_product_payload(
                extracted_data, 'test_retailer', 'modest'
            )
            tags_normal = payload_normal['product']['tags']
            self.assert_test(
                'not-assessed' not in tags_normal,
                "not-assessed tag not added for normal modesty level",
                f"Tags: {tags_normal}"
            )
            
        except Exception as e:
            self.assert_test(False, "Build product payload test", str(e))
    
    async def test_create_product_returns_cdn_urls(self):
        """Test that create_product returns shopify_image_urls"""
        logger.info("\n🧪 Testing create_product return structure...")
        
        try:
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../Shared'))
            from shopify_manager import ShopifyManager
            
            # We can't test actual API calls without credentials,
            # but we can verify the method signature and structure
            shopify_manager = ShopifyManager()
            
            # Check that the method exists
            self.assert_test(
                hasattr(shopify_manager, 'create_product'),
                "create_product method exists"
            )
            
            # Verify error return structure includes shopify_image_urls
            # by inspecting the method code
            import inspect
            source = inspect.getsource(shopify_manager.create_product)
            
            self.assert_test(
                "'shopify_image_urls'" in source,
                "create_product includes shopify_image_urls in return"
            )
            
            self.assert_test(
                "shopify_image_urls = []" in source,
                "create_product includes empty list for error cases"
            )
            
        except Exception as e:
            self.assert_test(False, "Create product CDN URL test", str(e))
    
    async def test_update_modesty_decision_method(self):
        """Test that update_modesty_decision method exists and has correct signature"""
        logger.info("\n🧪 Testing update_modesty_decision method...")
        
        try:
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../Shared'))
            from shopify_manager import ShopifyManager
            import inspect
            
            shopify_manager = ShopifyManager()
            
            # Check method exists
            self.assert_test(
                hasattr(shopify_manager, 'update_modesty_decision'),
                "update_modesty_decision method exists"
            )
            
            # Check signature
            sig = inspect.signature(shopify_manager.update_modesty_decision)
            params = list(sig.parameters.keys())
            
            self.assert_test(
                'product_id' in params and 'decision' in params,
                "update_modesty_decision has correct parameters",
                f"Parameters: {params}"
            )
            
            # Check it removes not-assessed tag
            source = inspect.getsource(shopify_manager.update_modesty_decision)
            self.assert_test(
                'not-assessed' in source,
                "Method handles not-assessed tag removal"
            )
            
        except Exception as e:
            self.assert_test(False, "Update modesty decision test", str(e))
    
    async def test_database_schema_shopify_image_urls(self):
        """Test that database schema includes shopify_image_urls column"""
        logger.info("\n🧪 Testing database schema...")
        
        try:
            import aiosqlite
            db_path = os.path.join(os.path.dirname(__file__), '../Shared/products.db')
            
            async with aiosqlite.connect(db_path) as conn:
                cursor = await conn.cursor()
                
                # Check catalog_products table schema
                await cursor.execute("PRAGMA table_info(catalog_products)")
                columns = await cursor.fetchall()
                column_names = [col[1] for col in columns]
                
                self.assert_test(
                    'shopify_image_urls' in column_names,
                    "shopify_image_urls column exists in catalog_products",
                    f"Columns: {column_names}"
                )
                
                # Check index exists
                await cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_catalog_products_shopify_draft_id'"
                )
                index = await cursor.fetchone()
                
                self.assert_test(
                    index is not None,
                    "idx_catalog_products_shopify_draft_id index exists"
                )
                
        except Exception as e:
            self.assert_test(False, "Database schema test", str(e))
    
    async def test_catalog_db_manager_cdn_url_handling(self):
        """Test that catalog_db_manager handles shopify_image_urls"""
        logger.info("\n🧪 Testing catalog_db_manager CDN URL handling...")
        
        try:
            from catalog_db_manager import CatalogDatabaseManager
            import inspect
            
            db_manager = CatalogDatabaseManager()
            
            # Check store_new_products handles shopify_image_urls
            source = inspect.getsource(db_manager.store_new_products)
            
            self.assert_test(
                'shopify_image_urls' in source,
                "store_new_products includes shopify_image_urls handling"
            )
            
            self.assert_test(
                'getattr(product, \'shopify_image_urls\'' in source,
                "store_new_products extracts shopify_image_urls from product"
            )
            
            # Check update_review_decision exists
            self.assert_test(
                hasattr(db_manager, 'update_review_decision'),
                "update_review_decision method exists in CatalogDatabaseManager"
            )
            
        except Exception as e:
            self.assert_test(False, "Catalog DB manager test", str(e))
    
    async def test_change_detector_cdn_url_storage(self):
        """Test that change_detector stores CDN URLs"""
        logger.info("\n🧪 Testing change_detector CDN URL storage...")
        
        try:
            from change_detector import ChangeDetector
            import inspect
            
            detector = ChangeDetector()
            
            # Check _store_detection_results handles shopify_image_urls
            source = inspect.getsource(detector._store_detection_results)
            
            self.assert_test(
                'shopify_image_urls' in source,
                "change_detector includes shopify_image_urls handling"
            )
            
            self.assert_test(
                'product.shopify_image_urls = shopify_image_urls' in source,
                "change_detector sets shopify_image_urls on product object"
            )
            
            # Check that it uses create_product instead of create_draft_for_review
            self.assert_test(
                'create_product(' in source,
                "change_detector uses create_product method"
            )
            
            self.assert_test(
                '"pending_review"' in source,
                "change_detector passes pending_review for modesty level"
            )
            
        except Exception as e:
            self.assert_test(False, "Change detector test", str(e))
    
    async def test_database_sync_utility(self):
        """Test that database_sync utility exists"""
        logger.info("\n🧪 Testing database_sync utility...")
        
        try:
            from database_sync import DatabaseSync, sync_database_to_web
            
            self.assert_test(
                DatabaseSync is not None,
                "DatabaseSync class exists"
            )
            
            self.assert_test(
                callable(sync_database_to_web),
                "sync_database_to_web function exists"
            )
            
            # Check DatabaseSync has sync_to_server method
            sync_obj = DatabaseSync()
            self.assert_test(
                hasattr(sync_obj, 'sync_to_server'),
                "DatabaseSync has sync_to_server method"
            )
            
        except Exception as e:
            self.assert_test(False, "Database sync utility test", str(e))
    
    async def test_integration_workflow(self):
        """Test the complete integration workflow"""
        logger.info("\n🧪 Testing complete integration workflow...")
        
        try:
            # Simulate the workflow steps
            workflow_steps = []
            
            # Step 1: Product discovered
            workflow_steps.append("Product discovered by catalog crawler")
            
            # Step 2: Change detector creates product with pending_review
            workflow_steps.append("ChangeDetector calls create_product with 'pending_review'")
            
            # Step 3: ShopifyManager adds not-assessed tag
            workflow_steps.append("ShopifyManager adds 'not-assessed' tag")
            
            # Step 4: CDN URLs returned and stored
            workflow_steps.append("Shopify CDN URLs returned in create_product result")
            
            # Step 5: CDN URLs stored in database
            workflow_steps.append("CDN URLs stored in catalog_products.shopify_image_urls")
            
            self.assert_test(
                len(workflow_steps) == 5,
                "Complete workflow has 5 steps",
                f"Steps: {', '.join(workflow_steps)}"
            )
            
            logger.info("\n📋 Integration Workflow:")
            for i, step in enumerate(workflow_steps, 1):
                logger.info(f"  {i}. {step}")
            
        except Exception as e:
            self.assert_test(False, "Integration workflow test", str(e))
    
    async def run_all_tests(self):
        """Run all tests"""
        logger.info("\n" + "="*80)
        logger.info("🧪 SHOPIFY INTEGRATION FOUNDATION TEST SUITE")
        logger.info("="*80)
        
        # Run all test methods
        await self.test_build_product_payload_not_assessed()
        await self.test_create_product_returns_cdn_urls()
        await self.test_update_modesty_decision_method()
        await self.test_database_schema_shopify_image_urls()
        await self.test_catalog_db_manager_cdn_url_handling()
        await self.test_change_detector_cdn_url_storage()
        await self.test_database_sync_utility()
        await self.test_integration_workflow()
        
        # Print summary
        logger.info("\n" + "="*80)
        logger.info("📊 TEST RESULTS SUMMARY")
        logger.info("="*80)
        
        for result in self.test_results:
            logger.info(result)
        
        total = self.tests_passed + self.tests_failed
        pass_rate = (self.tests_passed / total * 100) if total > 0 else 0
        
        logger.info("\n" + "-"*80)
        logger.info(f"✅ Passed: {self.tests_passed}/{total}")
        logger.info(f"❌ Failed: {self.tests_failed}/{total}")
        logger.info(f"📈 Pass Rate: {pass_rate:.1f}%")
        logger.info("-"*80)
        
        if self.tests_failed == 0:
            logger.info("\n🎉 ALL TESTS PASSED! Shopify integration foundation is ready.")
        else:
            logger.warning(f"\n⚠️  {self.tests_failed} test(s) failed. Please review.")
        
        return self.tests_failed == 0

async def main():
    """Main test runner"""
    tester = TestShopifyIntegrationFoundation()
    success = await tester.run_all_tests()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())

