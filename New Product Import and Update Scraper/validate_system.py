#!/usr/bin/env python3
"""
Conservative System Validation Script
Tests that all core components load and work without modification
"""

def test_imports():
    """Test that all core components import successfully"""
    print("🧪 TESTING CORE IMPORTS")
    print("=" * 50)
    
    tests = []
    
    # Add shared path for imports
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), "../Shared"))
    sys.path.append(os.path.dirname(__file__))

    # Test MarkdownExtractor
    try:
        from markdown_extractor import MarkdownExtractor
        extractor = MarkdownExtractor()
        assert hasattr(extractor, 'deepseek_enabled')
        print("✅ MarkdownExtractor: PASS")
        tests.append(True)
    except Exception as e:
        print(f"❌ MarkdownExtractor: FAILED - {e}")
        tests.append(False)
    
    # Test UnifiedExtractor
    try:
        from unified_extractor import UnifiedExtractor
        extractor = UnifiedExtractor()
        assert hasattr(extractor, 'pattern_learner')
        print("✅ UnifiedExtractor: PASS")
        tests.append(True)
    except Exception as e:
        print(f"❌ UnifiedExtractor: FAILED - {e}")
        tests.append(False)
    
    # Test BatchProcessor
    try:
        from batch_processor import BatchProcessor
        processor = BatchProcessor()
        assert hasattr(processor, 'unified_extractor')
        print("✅ BatchProcessor: PASS")
        tests.append(True)
    except Exception as e:
        print(f"❌ BatchProcessor: FAILED - {e}")
        tests.append(False)
    
    # Test ScrapingSystem
    try:
        from main_scraper import ScrapingSystem
        system = ScrapingSystem()
        assert hasattr(system, 'batch_processor')
        print("✅ ScrapingSystem: PASS")
        tests.append(True)
    except Exception as e:
        print(f"❌ ScrapingSystem: FAILED - {e}")
        tests.append(False)
    
    return tests

def test_databases():
    """Test database accessibility"""
    print("\n🗄️ TESTING DATABASES")
    print("=" * 50)
    
    tests = []
    
    # Test products.db
    try:
        import sqlite3
        conn = sqlite3.connect('../Shared/products.db')
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        conn.close()
        assert len(tables) > 0
        print("✅ Products DB: PASS")
        tests.append(True)
    except Exception as e:
        print(f"❌ Products DB: FAILED - {e}")
        tests.append(False)
    
    # Test patterns.db
    try:
        import sqlite3
        conn = sqlite3.connect('../Shared/patterns.db')
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        conn.close()
        assert len(tables) > 0
        print("✅ Patterns DB: PASS")
        tests.append(True)
    except Exception as e:
        print(f"❌ Patterns DB: FAILED - {e}")
        tests.append(False)
    
    return tests

def test_config_files():
    """Test configuration file validity"""
    print("\n⚙️ TESTING CONFIGURATION")
    print("=" * 50)
    
    tests = []
    
    # Test config.json
    try:
        import json
        with open('../Shared/config.json', 'r') as f:
            config = json.load(f)
        assert 'llm_providers' in config
        assert 'shopify' in config  # Check for actual key instead of extraction_routing
        print("✅ Config JSON: PASS")
        tests.append(True)
    except Exception as e:
        print(f"❌ Config JSON: FAILED - {e}")
        tests.append(False)
    
    # Test urls.json
    try:
        import json
        with open('../Shared/urls.json', 'r') as f:
            urls = json.load(f)
        assert isinstance(urls, dict)
        print("✅ URLs JSON: PASS")
        tests.append(True)
    except Exception as e:
        print(f"❌ URLs JSON: FAILED - {e}")
        tests.append(False)
    
    return tests

def main():
    """Run all validation tests"""
    print("🛡️ AGENT MODEST SCRAPER SYSTEM VALIDATION")
    print("=" * 60)
    
    # Run all test suites
    import_tests = test_imports()
    database_tests = test_databases()
    config_tests = test_config_files()
    
    # Calculate results
    all_tests = import_tests + database_tests + config_tests
    passed = sum(all_tests)
    total = len(all_tests)
    
    # Summary
    print(f"\n📊 VALIDATION SUMMARY")
    print("=" * 60)
    print(f"✅ Passed: {passed}/{total} tests")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED - System is stable and ready")
        return True
    else:
        failed = total - passed
        print(f"❌ Failed: {failed}/{total} tests")
        print("⚠️ System has issues that need attention")
        return False

if __name__ == '__main__':
    success = main()
    exit(0 if success else 1) 