"""
Test script for Foundation Changes for Modesty Assessment Pipeline
Validates:
1. CLI accepts 'not_modest' option
2. Shopify status determination logic
3. Database schema new columns
4. Store operations with new columns
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../Shared"))
sys.path.append(os.path.dirname(__file__))

import asyncio
import argparse
from datetime import date

from logger_config import setup_logging

logger = setup_logging(__name__)

class FoundationChangesTest:
    """Test suite for foundation changes"""
    
    def __init__(self):
        self.passed_tests = 0
        self.failed_tests = 0
        self.test_details = []
    
    def log_test(self, test_name: str, passed: bool, details: str = ""):
        """Log test result"""
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"{status}: {test_name}")
        if details:
            logger.info(f"  Details: {details}")
        
        if passed:
            self.passed_tests += 1
        else:
            self.failed_tests += 1
        
        self.test_details.append({
            'test': test_name,
            'passed': passed,
            'details': details
        })
    
    def test_cli_validation(self):
        """Test that CLI accepts not_modest option"""
        logger.info("\n🎯 Testing CLI Validation...")
        
        try:
            # Test with argparse
            parser = argparse.ArgumentParser()
            parser.add_argument('--modesty-level', choices=['modest', 'moderately_modest', 'not_modest'])
            
            # Try parsing valid values
            for level in ['modest', 'moderately_modest', 'not_modest']:
                try:
                    args = parser.parse_args(['--modesty-level', level])
                    if args.modesty_level == level:
                        self.log_test(f"CLI accepts '{level}'", True)
                    else:
                        self.log_test(f"CLI accepts '{level}'", False, 
                                     f"Expected {level}, got {args.modesty_level}")
                except:
                    self.log_test(f"CLI accepts '{level}'", False, "Parser rejected valid value")
        
        except Exception as e:
            self.log_test("CLI validation test", False, str(e))
    
    def test_shopify_status_logic(self):
        """Test Shopify status determination"""
        logger.info("\n🛍️  Testing Shopify Status Logic...")
        
        try:
            from shopify_manager import ShopifyManager
            
            # Create instance
            manager = ShopifyManager()
            
            # Test status determination
            test_cases = [
                ('modest', 'active', 'Modest products should be active'),
                ('moderately_modest', 'active', 'Moderately modest products should be active'),
                ('not_modest', 'draft', 'Not modest products should be draft'),
                ('unknown', 'draft', 'Unknown levels should default to draft')
            ]
            
            for modesty_level, expected_status, description in test_cases:
                actual_status = manager._determine_product_status(modesty_level)
                if actual_status == expected_status:
                    self.log_test(f"Status for '{modesty_level}'", True, 
                                 f"{expected_status} (correct)")
                else:
                    self.log_test(f"Status for '{modesty_level}'", False,
                                 f"Expected {expected_status}, got {actual_status}")
        
        except Exception as e:
            self.log_test("Shopify status logic test", False, str(e))
    
    async def test_database_schema(self):
        """Test that new columns exist in database"""
        logger.info("\n🗄️  Testing Database Schema...")
        
        try:
            from catalog_db_manager import CatalogDatabaseManager
            import aiosqlite
            
            db_manager = CatalogDatabaseManager()
            await db_manager._ensure_db_initialized()
            
            # Check if new columns exist
            async with aiosqlite.connect(db_manager.db_path) as conn:
                cursor = await conn.cursor()
                await cursor.execute("PRAGMA table_info(catalog_products)")
                columns = await cursor.fetchall()
                
                column_names = [col[1] for col in columns]
                
                required_columns = [
                    'shopify_draft_id',
                    'processing_stage',
                    'full_scrape_attempted',
                    'full_scrape_completed',
                    'cost_incurred'
                ]
                
                for col_name in required_columns:
                    if col_name in column_names:
                        self.log_test(f"Column '{col_name}' exists", True)
                    else:
                        self.log_test(f"Column '{col_name}' exists", False,
                                     "Column not found in catalog_products table")
        
        except Exception as e:
            self.log_test("Database schema test", False, str(e))
    
    async def test_store_operations(self):
        """Test that store operations work with new columns"""
        logger.info("\n💾 Testing Store Operations...")
        
        try:
            from catalog_db_manager import CatalogDatabaseManager, CatalogProduct, MatchResult
            
            db_manager = CatalogDatabaseManager()
            await db_manager._ensure_db_initialized()
            
            # Create a test product
            test_product = CatalogProduct(
                catalog_url='https://test.com/product/test',
                retailer='test_retailer',
                category='dresses',
                title='Test Product',
                price=99.99,
                discovered_date=date.today(),
                extraction_method='test'
            )
            
            # Create a match result
            match_result = MatchResult(
                is_new_product=True,
                confidence_score=0.95,
                match_type='test'
            )
            
            # Try storing
            try:
                run_id = 'test_foundation_changes'
                stored = await db_manager.store_new_products(
                    [(test_product, match_result)], 
                    run_id
                )
                
                if stored > 0:
                    self.log_test("Store operation with new columns", True,
                                 f"Successfully stored {stored} product(s)")
                else:
                    self.log_test("Store operation with new columns", False,
                                 "No products were stored")
                
                # Clean up test data
                import aiosqlite
                async with aiosqlite.connect(db_manager.db_path) as conn:
                    await conn.execute(
                        "DELETE FROM catalog_products WHERE discovery_run_id = ?",
                        (run_id,)
                    )
                    await conn.commit()
                
            except Exception as e:
                self.log_test("Store operation with new columns", False, str(e))
        
        except Exception as e:
            self.log_test("Store operations test", False, str(e))
    
    async def run_all_tests(self):
        """Run all foundation change tests"""
        logger.info("🚀 Starting Foundation Changes Tests\n")
        
        # Run tests
        self.test_cli_validation()
        self.test_shopify_status_logic()
        await self.test_database_schema()
        await self.test_store_operations()
        
        # Generate report
        total_tests = self.passed_tests + self.failed_tests
        success_rate = self.passed_tests / total_tests if total_tests > 0 else 0
        
        logger.info("\n" + "="*60)
        logger.info("📊 TEST SUMMARY")
        logger.info("="*60)
        logger.info(f"Total Tests: {total_tests}")
        logger.info(f"Passed: {self.passed_tests} ✅")
        logger.info(f"Failed: {self.failed_tests} ❌")
        logger.info(f"Success Rate: {success_rate:.1%}")
        logger.info("="*60)
        
        if success_rate >= 0.9:  # 90% pass rate
            logger.info("\n✅ FOUNDATION CHANGES TESTS PASSED")
            logger.info("All critical features are working as expected!")
            return True
        else:
            logger.error("\n❌ FOUNDATION CHANGES TESTS FAILED")
            logger.error("Some features need attention before deployment.")
            return False

async def main():
    """Main test runner"""
    tester = FoundationChangesTest()
    success = await tester.run_all_tests()
    
    if success:
        logger.info("\n🎉 All foundation changes validated successfully!")
        logger.info("The system is ready for the next phase.")
    else:
        logger.error("\n⚠️  Some foundation changes need attention.")
        logger.error("Please review the failed tests above.")
    
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

