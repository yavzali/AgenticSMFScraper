#!/usr/bin/env python3
"""
Conservative Test Suite for Agent Modest Scraper System
Tests existing functionality without modification
"""

import unittest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestSystemImports(unittest.TestCase):
    """Test that all core components can be imported successfully"""
    
    def test_markdown_extractor_import(self):
        """Test markdown extractor imports and initializes"""
        try:
            from markdown_extractor import MarkdownExtractor
            extractor = MarkdownExtractor()
            self.assertTrue(hasattr(extractor, 'deepseek_enabled'))
            print("✅ MarkdownExtractor: PASS", file=sys.stderr)
        except Exception as e:
            self.fail(f"❌ MarkdownExtractor failed: {e}")
    
    def test_unified_extractor_import(self):
        """Test unified extractor imports and initializes"""
        try:
            from unified_extractor import UnifiedExtractor
            extractor = UnifiedExtractor()
            self.assertTrue(hasattr(extractor, 'pattern_learner'))
            print("✅ UnifiedExtractor: PASS", file=sys.stderr)
        except Exception as e:
            self.fail(f"❌ UnifiedExtractor failed: {e}")
    
    def test_batch_processor_import(self):
        """Test batch processor imports and initializes"""
        try:
            from batch_processor import BatchProcessor
            processor = BatchProcessor()
            self.assertTrue(hasattr(processor, 'unified_extractor'))
            print("✅ BatchProcessor: PASS", file=sys.stderr)
        except Exception as e:
            self.fail(f"❌ BatchProcessor failed: {e}")
    
    def test_main_scraper_import(self):
        """Test main scraper system imports and initializes"""
        try:
            from main_scraper import ScrapingSystem
            system = ScrapingSystem()
            self.assertTrue(hasattr(system, 'batch_processor'))
            print("✅ ScrapingSystem: PASS", file=sys.stderr)
        except Exception as e:
            self.fail(f"❌ ScrapingSystem failed: {e}")

class TestDatabaseConnections(unittest.TestCase):
    """Test database connections work"""
    
    def test_products_db_accessible(self):
        """Test products database is accessible"""
        try:
            import sqlite3
            conn = sqlite3.connect('products.db')
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            conn.close()
            self.assertTrue(len(tables) > 0)
            print("✅ Products DB: PASS", file=sys.stderr)
        except Exception as e:
            self.fail(f"❌ Products DB failed: {e}")
    
    def test_patterns_db_accessible(self):
        """Test patterns database is accessible"""
        try:
            import sqlite3
            conn = sqlite3.connect('patterns.db')
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            conn.close()
            self.assertTrue(len(tables) > 0)
            print("✅ Patterns DB: PASS", file=sys.stderr)
        except Exception as e:
            self.fail(f"❌ Patterns DB failed: {e}")

class TestConfigurationFiles(unittest.TestCase):
    """Test configuration files are valid"""
    
    def test_config_json_loads(self):
        """Test config.json loads properly"""
        try:
            import json
            with open('config.json', 'r') as f:
                config = json.load(f)
            self.assertIn('llm_providers', config)
            self.assertIn('shopify', config)
            print("✅ Config JSON: PASS", file=sys.stderr)
        except Exception as e:
            self.fail(f"❌ Config JSON failed: {e}")
    
    def test_urls_json_loads(self):
        """Test urls.json loads properly"""
        try:
            import json
            with open('urls.json', 'r') as f:
                urls = json.load(f)
            self.assertTrue(isinstance(urls, dict))
            print("✅ URLs JSON: PASS", file=sys.stderr)
        except Exception as e:
            self.fail(f"❌ URLs JSON failed: {e}")

if __name__ == '__main__':
    print("🧪 CONSERVATIVE SYSTEM VALIDATION")
    print("=" * 50)
    
    # Run tests with normal output
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestSystemImports,
        TestDatabaseConnections, 
        TestConfigurationFiles
    ]
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run with normal output
    runner = unittest.TextTestRunner(verbosity=0)
    result = runner.run(suite)
    
    print("\n📊 VALIDATION SUMMARY")
    print("=" * 50)
    if result.wasSuccessful():
        print("✅ ALL TESTS PASSED - System is stable")
        print(f"✅ Ran {result.testsRun} tests successfully")
    else:
        print("❌ SOME TESTS FAILED")
        print(f"❌ Failures: {len(result.failures)}")
        print(f"❌ Errors: {len(result.errors)}")
        for failure in result.failures:
            print(f"   - {failure[0]}: {failure[1]}")
        for error in result.errors:
            print(f"   - {error[0]}: {error[1]}")
    
    exit(0 if result.wasSuccessful() else 1) 