"""
Test script for Mango catalog extraction using Markdown Tower
Tests the MarkdownCatalogExtractor for catalog page extraction
Note: Mango uses infinite scroll - markdown can only capture initially visible products
"""

import sys
import os
import asyncio
import time
from datetime import datetime

# Add parent directory to path for imports
parent_dir = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(parent_dir)

# CRITICAL: Also add Extraction/Markdown to path
# (markdown_catalog_extractor imports markdown_retailer_logic from same directory)
markdown_dir = os.path.join(parent_dir, "Extraction", "Markdown")
sys.path.append(markdown_dir)

from Extraction.Markdown.markdown_catalog_extractor import MarkdownCatalogExtractor

# Test configuration
RETAILER = "mango"
TEST_URL = "https://shop.mango.com/us/en/c/women/dresses-and-jumpsuits/dresses_b4864b2e"
EXPECTED_MIN_PRODUCTS = 40
EXPECTED_MAX_PRODUCTS = 60


async def test_mango_catalog_extraction():
    """Test Mango catalog extraction with Markdown Tower"""
    
    print("=" * 60)
    print("MANGO CATALOG EXTRACTION TEST")
    print("=" * 60)
    print(f"Test URL: {TEST_URL}")
    print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    start_time = time.time()
    extractor = None
    
    try:
        # Initialize extractor
        print("📦 Initializing MarkdownCatalogExtractor...")
        extractor = MarkdownCatalogExtractor()
        print("✅ Extractor initialized")
        print()
        
        # Run extraction
        print("🚀 Starting catalog extraction...")
        print("⏱️  This may take 30-60 seconds...")
        print()
        
        result = await extractor.extract_catalog(
            catalog_url=TEST_URL,
            retailer=RETAILER,
            max_pages=1  # Test single page first
        )
        
        # Calculate elapsed time
        elapsed_time = time.time() - start_time
        
        print()
        print("=" * 60)
        print("TEST RESULTS")
        print("=" * 60)
        
        # Extract results
        success = result.get('success', False)
        products = result.get('products', [])
        total_found = result.get('total_found', len(products))
        method_used = result.get('method_used', 'unknown')
        processing_time = result.get('processing_time', elapsed_time)
        warnings = result.get('warnings', [])
        errors = result.get('errors', [])
        
        # Determine PASS/FAIL (products >= 40 and success == True)
        # Note: Mango has infinite scroll, so we only expect initially visible products
        test_passed = success and total_found >= EXPECTED_MIN_PRODUCTS
        
        status = "PASS" if test_passed else "FAIL"
        
        print(f"Status: {status}")
        print(f"Products Found: {total_found}")
        print(f"Expected Range: {EXPECTED_MIN_PRODUCTS}-{EXPECTED_MAX_PRODUCTS}")
        print(f"Processing Time: {processing_time:.2f} seconds")
        print(f"Method Used: {method_used}")
        print(f"Warnings: {len(warnings)}")
        print(f"Errors: {len(errors)}")
        print()
        
        # Show sample products
        if products:
            print("Sample Products (first 3):")
            print()
            for i, product in enumerate(products[:3], 1):
                title = product.get('title', 'N/A')
                price = product.get('price', 'N/A')
                # Format price if it's a number
                if isinstance(price, (int, float)):
                    price_str = f"${price:.2f}"
                else:
                    price_str = str(price)
                print(f"  {i}. {title} - {price_str}")
        else:
            print("⚠️  No products extracted")
        
        # Show warnings if any
        if warnings:
            print()
            print("Warnings:")
            for warning in warnings:
                print(f"  - {warning}")
        
        # Show errors if any
        if errors:
            print()
            print("Errors:")
            for error in errors:
                print(f"  - {error}")
        
        print()
        print("=" * 60)
        print("Note: Mango uses infinite scroll - markdown can only capture")
        print("initially visible products (~48). This is expected behavior.")
        print("=" * 60)
        
        # Final status message
        if test_passed:
            print("✅ TEST PASSED: Mango catalog extraction working correctly!")
        elif success and total_found < EXPECTED_MIN_PRODUCTS:
            print(f"⚠️  TEST FAILED: Only {total_found} products found (expected {EXPECTED_MIN_PRODUCTS}+)")
        elif not success:
            print("❌ TEST FAILED: Extraction did not succeed")
        else:
            print(f"⚠️  TEST FAILED: {total_found} products found (expected {EXPECTED_MIN_PRODUCTS}+)")
        
        print("=" * 60)
        
        return test_passed
        
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
        return False


if __name__ == "__main__":
    print()
    result = asyncio.run(test_mango_catalog_extraction())
    print()
    sys.exit(0 if result else 1)

