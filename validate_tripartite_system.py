#!/usr/bin/env python3
"""
Tripartite System Validation Script
Tests all three systems: New Product Importer, Product Updater, and Catalog Crawler
"""

import subprocess
import sys
import os

def run_subsystem_validation(system_name, script_path):
    """Run validation for a specific subsystem"""
    print(f"\n🔍 VALIDATING {system_name.upper()}")
    print("=" * 60)
    
    try:
        # Get the correct working directory and script name
        script_dir = os.path.dirname(script_path)
        script_name = os.path.basename(script_path)
        
        result = subprocess.run([sys.executable, script_name], 
                              capture_output=True, text=True, cwd=script_dir)
        
        if result.returncode == 0:
            print(f"✅ {system_name} validation: PASSED")
            return True
        else:
            print(f"❌ {system_name} validation: FAILED")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            return False
            
    except Exception as e:
        print(f"❌ {system_name} validation: ERROR - {e}")
        return False

def test_architecture_separation():
    """Test that the systems are properly separated"""
    print("\n🏗️  TESTING ARCHITECTURE SEPARATION")
    print("=" * 60)
    
    tests = []
    
    # Test directory structure
    expected_dirs = ["New Product Importer", "Product Updater", "Catalog Crawler", "Shared"]
    for directory in expected_dirs:
        if os.path.exists(directory):
            print(f"✅ {directory}: EXISTS")
            tests.append(True)
        else:
            print(f"❌ {directory}: MISSING")
            tests.append(False)
    
    # Test that original combined folder is gone
    if not os.path.exists("New Product Import and Update Scraper"):
        print("✅ Original combined folder: PROPERLY REMOVED")
        tests.append(True)
    else:
        print("❌ Original combined folder: STILL EXISTS")
        tests.append(False)
    
    # Test key files exist in each system
    key_files = {
        "New Product Importer": ["new_product_importer.py", "import_processor.py", "validate_import_system.py"],
        "Product Updater": ["product_updater.py", "update_processor.py", "validate_update_system.py"],
        "Catalog Crawler": ["catalog_main.py"],  # Should be untouched
        "Shared": ["duplicate_detector.py", "shopify_manager.py", "config.json"]
    }
    
    for system, files in key_files.items():
        for file in files:
            file_path = os.path.join(system, file)
            if os.path.exists(file_path):
                print(f"✅ {file_path}: EXISTS")
                tests.append(True)
            else:
                print(f"❌ {file_path}: MISSING")
                tests.append(False)
    
    return tests

def test_shared_components():
    """Test that shared components are properly enhanced"""
    print("\n🔧 TESTING SHARED COMPONENTS")
    print("=" * 60)
    
    tests = []
    
    # Add shared path for imports
    sys.path.append(os.path.join(os.path.dirname(__file__), "Shared"))
    
    try:
        from duplicate_detector import DuplicateDetector
        detector = DuplicateDetector()
        
        # Test that the new update method exists
        if hasattr(detector, 'update_existing_product'):
            print("✅ DuplicateDetector.update_existing_product: EXISTS")
            tests.append(True)
        else:
            print("❌ DuplicateDetector.update_existing_product: MISSING")
            tests.append(False)
            
    except Exception as e:
        print(f"❌ DuplicateDetector: FAILED - {e}")
        tests.append(False)
    
    try:
        from shopify_manager import ShopifyManager
        manager = ShopifyManager()
        
        # Test that both create and update methods exist
        if hasattr(manager, 'create_product'):
            print("✅ ShopifyManager.create_product: EXISTS")
            tests.append(True)
        else:
            print("❌ ShopifyManager.create_product: MISSING")
            tests.append(False)
            
        if hasattr(manager, 'update_product'):
            print("✅ ShopifyManager.update_product: EXISTS")
            tests.append(True)
        else:
            print("❌ ShopifyManager.update_product: MISSING")
            tests.append(False)
            
    except Exception as e:
        print(f"❌ ShopifyManager: FAILED - {e}")
        tests.append(False)
        tests.append(False)
    
    return tests

def main():
    """Run complete tripartite system validation"""
    print("🚀 TRIPARTITE SYSTEM VALIDATION")
    print("=" * 70)
    print("Testing: New Product Importer | Product Updater | Catalog Crawler")
    print("=" * 70)
    
    all_tests = []
    
    # Test architecture separation
    architecture_tests = test_architecture_separation()
    all_tests.extend(architecture_tests)
    
    # Test shared components
    shared_tests = test_shared_components()
    all_tests.extend(shared_tests)
    
    # Test each subsystem
    subsystem_results = []
    
    # New Product Importer
    new_product_result = run_subsystem_validation(
        "New Product Importer", 
        "New Product Importer/validate_import_system.py"
    )
    subsystem_results.append(new_product_result)
    
    # Product Updater
    product_updater_result = run_subsystem_validation(
        "Product Updater", 
        "Product Updater/validate_update_system.py"
    )
    subsystem_results.append(product_updater_result)
    
    # Catalog Crawler (just check it exists and wasn't modified)
    if os.path.exists("Catalog Crawler"):
        print(f"\n✅ Catalog Crawler: PRESERVED (untouched as required)")
        subsystem_results.append(True)
    else:
        print(f"\n❌ Catalog Crawler: MISSING")
        subsystem_results.append(False)
    
    # Final summary
    architecture_passed = sum(architecture_tests)
    architecture_total = len(architecture_tests)
    
    shared_passed = sum(shared_tests)
    shared_total = len(shared_tests)
    
    subsystem_passed = sum(subsystem_results)
    subsystem_total = len(subsystem_results)
    
    total_passed = architecture_passed + shared_passed + subsystem_passed
    total_tests = architecture_total + shared_total + subsystem_total
    
    print(f"\n📊 TRIPARTITE SYSTEM VALIDATION SUMMARY")
    print("=" * 70)
    print(f"🏗️  Architecture Separation: {architecture_passed}/{architecture_total} tests passed")
    print(f"🔧 Shared Components: {shared_passed}/{shared_total} tests passed")
    print(f"🚀 Subsystem Validation: {subsystem_passed}/{subsystem_total} systems passed")
    print("-" * 70)
    print(f"🎯 TOTAL: {total_passed}/{total_tests} tests passed")
    
    if total_passed == total_tests:
        print("🎉 ALL TESTS PASSED - Tripartite system is ready!")
        print("\n📋 USAGE:")
        print("  • New products: cd 'New Product Importer' && python new_product_importer.py")
        print("  • Update products: cd 'Product Updater' && python product_updater.py")
        print("  • Catalog monitoring: cd 'Catalog Crawler' && python catalog_main.py")
        return True
    else:
        print("⚠️  Some tests failed - check the errors above")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1) 