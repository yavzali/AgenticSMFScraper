#!/usr/bin/env python3
"""
New Product Importer System Validation Script
Tests that all core components load and work for NEW product import
"""

def test_imports():
    """Test that all core components import successfully"""
    print("🧪 TESTING NEW PRODUCT IMPORTER IMPORTS")
    print("=" * 50)
    
    tests = []
    
    # Add shared path for imports
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), "../Shared"))
    sys.path.append(os.path.dirname(__file__))

    # Test ImportProcessor
    try:
        from import_processor import ImportProcessor
        processor = ImportProcessor()
        assert hasattr(processor, 'unified_extractor')
        assert hasattr(processor, 'shopify_manager')
        assert hasattr(processor, 'duplicate_detector')
        print("✅ ImportProcessor: PASS")
        tests.append(True)
    except Exception as e:
        print(f"❌ ImportProcessor: FAILED - {e}")
        tests.append(False)
    
    # Test NewProductImportSystem
    try:
        from new_product_importer import NewProductImportSystem
        system = NewProductImportSystem()
        assert hasattr(system, 'import_processor')
        print("✅ NewProductImportSystem: PASS")
        tests.append(True)
    except Exception as e:
        print(f"❌ NewProductImportSystem: FAILED - {e}")
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
    
    # Test URLProcessor
    try:
        from url_processor import URLProcessor
        processor = URLProcessor()
        assert hasattr(processor, 'duplicate_detector')
        print("✅ URLProcessor: PASS")
        tests.append(True)
    except Exception as e:
        print(f"❌ URLProcessor: FAILED - {e}")
        tests.append(False)
    
    # Test ImageProcessorFactory
    try:
        from image_processor_factory import ImageProcessorFactory
        factory = ImageProcessorFactory()
        supported = factory.get_supported_retailers()
        assert len(supported) > 0
        print("✅ ImageProcessorFactory: PASS")
        tests.append(True)
    except Exception as e:
        print(f"❌ ImageProcessorFactory: FAILED - {e}")
        tests.append(False)
    
    # Test Shared Components
    try:
        from shopify_manager import ShopifyManager
        manager = ShopifyManager()
        assert hasattr(manager, 'create_product')
        print("✅ ShopifyManager: PASS")
        tests.append(True)
    except Exception as e:
        print(f"❌ ShopifyManager: FAILED - {e}")
        tests.append(False)
    
    try:
        from duplicate_detector import DuplicateDetector
        detector = DuplicateDetector()
        assert hasattr(detector, 'check_duplicate')
        print("✅ DuplicateDetector: PASS")
        tests.append(True)
    except Exception as e:
        print(f"❌ DuplicateDetector: FAILED - {e}")
        tests.append(False)
    
    return tests

def test_system_integration():
    """Test that the system can be initialized properly"""
    print("\n🔧 TESTING SYSTEM INTEGRATION")
    print("=" * 50)
    
    tests = []
    
    # Add shared path for imports
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), "../Shared"))
    sys.path.append(os.path.dirname(__file__))
    
    try:
        from new_product_importer import NewProductImportSystem
        from import_processor import ImportProcessor
        
        # Test system initialization
        system = NewProductImportSystem()
        processor = ImportProcessor()
        
        # Test that processor has all required methods
        assert hasattr(processor, 'process_new_products_batch')
        assert hasattr(processor, '_process_single_new_product')
        assert hasattr(processor, '_process_url')
        assert hasattr(processor, '_process_images')
        assert hasattr(processor, '_store_product_record')
        
        print("✅ System Integration: PASS")
        tests.append(True)
    except Exception as e:
        print(f"❌ System Integration: FAILED - {e}")
        tests.append(False)
    
    return tests

def main():
    """Run all validation tests"""
    print("🚀 NEW PRODUCT IMPORTER SYSTEM VALIDATION")
    print("=" * 60)
    
    # Run import tests
    import_tests = test_imports()
    
    # Run integration tests
    integration_tests = test_system_integration()
    
    # Summary
    all_tests = import_tests + integration_tests
    passed = sum(all_tests)
    total = len(all_tests)
    
    print(f"\n📊 VALIDATION SUMMARY")
    print("=" * 50)
    print(f"✅ Passed: {passed}/{total} tests")
    print(f"❌ Failed: {total - passed}/{total} tests")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED - New Product Importer is ready!")
        return True
    else:
        print("⚠️  Some tests failed - check the errors above")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1) 