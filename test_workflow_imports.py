"""
Quick test to verify all workflow imports work
"""

import sys
import os

print("Testing workflow imports...")

try:
    sys.path.append('Workflows')
    sys.path.append('Shared')
    sys.path.append('Extraction/Markdown')
    sys.path.append('Extraction/Patchright')
    
    print("\n1. Testing Product Updater imports...")
    from Workflows.product_updater import ProductUpdater
    print("   ✅ ProductUpdater imported")
    
    print("\n2. Testing New Product Importer imports...")
    from Workflows.new_product_importer import NewProductImporter
    print("   ✅ NewProductImporter imported")
    
    print("\n3. Testing Catalog Baseline Scanner imports...")
    from Workflows.catalog_baseline_scanner import CatalogBaselineScanner
    print("   ✅ CatalogBaselineScanner imported")
    
    print("\n4. Testing Catalog Monitor imports...")
    from Workflows.catalog_monitor import CatalogMonitor
    print("   ✅ CatalogMonitor imported")
    
    print("\n5. Testing Database Manager...")
    from Shared.db_manager import DatabaseManager
    db = DatabaseManager()
    print("   ✅ DatabaseManager initialized")
    
    print("\n6. Testing Assessment Queue Manager...")
    from Shared.assessment_queue_manager import AssessmentQueueManager
    queue = AssessmentQueueManager()
    print("   ✅ AssessmentQueueManager initialized")
    
    print("\n✅ ALL IMPORTS SUCCESSFUL!")
    print("\nArchitecture is properly wired together! 🎉")
    
except Exception as e:
    print(f"\n❌ Import failed: {e}")
    import traceback
    traceback.print_exc()

