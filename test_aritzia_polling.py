"""
Test script for Aritzia catalog extraction with polling logic
Tests the new polling approach for handling unpredictable API delays
"""

import asyncio
import sys
import os
import time

# Add paths for imports
sys.path.append(os.path.join(os.path.dirname(__file__), "Extraction/Patchright"))
sys.path.append(os.path.join(os.path.dirname(__file__), "Shared"))

from patchright_catalog_extractor import PatchrightCatalogExtractor

# Test URL
ARITZIA_TEST_URL = "https://www.aritzia.com/us/en/clothing/dresses?srule=production_ecommerce_aritzia__Aritzia_US__products__en_US__newest"

# Basic catalog prompt for testing
CATALOG_PROMPT = """Extract all products from this catalog page.
For each product, extract:
- Title
- Price
- Image URL (if visible)
- Sale status (on_sale or regular)

Return as a JSON array of products."""


async def test_aritzia_extraction():
    """Test Aritzia catalog extraction with polling logic"""
    
    print("=" * 60)
    print("🧪 ARITZIA POLLING TEST")
    print("=" * 60)
    print(f"URL: {ARITZIA_TEST_URL}")
    print(f"Start time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    start_time = time.time()
    extractor = None
    
    try:
        # Initialize extractor
        print("📦 Initializing PatchrightCatalogExtractor...")
        extractor = PatchrightCatalogExtractor()
        print("✅ Extractor initialized")
        print()
        
        # Run extraction
        print("🚀 Starting catalog extraction...")
        print("⏱️  Watch for polling messages (checking every 1 second)...")
        print()
        
        result = await extractor.extract_catalog(
            catalog_url=ARITZIA_TEST_URL,
            retailer="aritzia",
            catalog_prompt=CATALOG_PROMPT
        )
        
        # Calculate elapsed time
        elapsed_time = time.time() - start_time
        
        print()
        print("=" * 60)
        print("📊 RESULTS")
        print("=" * 60)
        
        # Extract results
        if isinstance(result, dict):
            success = result.get('success', False)
            products = result.get('products', [])
            total_found = result.get('total_found', len(products))
            method_used = result.get('method_used', 'unknown')
            errors = result.get('errors', [])
            warnings = result.get('warnings', [])
        else:
            # Handle object return type
            success = result.success if hasattr(result, 'success') else False
            products = result.data.get('products', []) if hasattr(result, 'data') else []
            total_found = len(products)
            method_used = getattr(result, 'method_used', 'unknown')
            errors = getattr(result, 'errors', [])
            warnings = getattr(result, 'warnings', [])
        
        print(f"✅ Success: {success}")
        print(f"📦 Products found: {total_found}")
        print(f"🔧 Method used: {method_used}")
        print(f"⏱️  Total time: {elapsed_time:.2f} seconds")
        print()
        
        if products:
            print(f"📋 Sample products (first 3):")
            for i, product in enumerate(products[:3], 1):
                title = product.get('title', 'N/A')
                price = product.get('price', 'N/A')
                print(f"  {i}. {title} - {price}")
        else:
            print("⚠️  No products extracted")
        
        if warnings:
            print()
            print("⚠️  Warnings:")
            for warning in warnings:
                print(f"  - {warning}")
        
        if errors:
            print()
            print("❌ Errors:")
            for error in errors:
                print(f"  - {error}")
        
        print()
        print("=" * 60)
        
        if success and total_found > 0:
            print("✅ TEST PASSED: Products successfully extracted!")
        elif success and total_found == 0:
            print("⚠️  TEST INCONCLUSIVE: Extraction succeeded but no products found")
        else:
            print("❌ TEST FAILED: Extraction did not succeed")
        
        print("=" * 60)
        
    except Exception as e:
        elapsed_time = time.time() - start_time
        print()
        print("=" * 60)
        print("❌ ERROR OCCURRED")
        print("=" * 60)
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        print(f"Time elapsed: {elapsed_time:.2f} seconds")
        print()
        import traceback
        print("Full traceback:")
        traceback.print_exc()
        print("=" * 60)
        
    finally:
        # Cleanup
        if extractor:
            try:
                print()
                print("🧹 Cleaning up browser resources...")
                await extractor._cleanup()
                print("✅ Cleanup complete")
            except Exception as cleanup_error:
                print(f"⚠️  Cleanup error: {cleanup_error}")


if __name__ == "__main__":
    print()
    asyncio.run(test_aritzia_extraction())
    print()

