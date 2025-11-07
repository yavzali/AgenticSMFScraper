"""
Quick test for Patchright Single Product Extractor
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../Shared"))
sys.path.append(os.path.join(os.path.dirname(__file__), "../Extraction/Patchright"))

import asyncio
import json
from patchright_product_extractor import PatchrightProductExtractor

async def test_single_product():
    # Test URL: Abercrombie dress (Patchright retailer)
    # This was successfully tested during Phase 6 Abercrombie catalog tests
    test_url = "https://www.abercrombie.com/shop/us/p/linen-blend-strapless-midi-dress-55272335"
    retailer = "abercrombie"
    
    print(f"=== TEST 7: PATCHRIGHT SINGLE PRODUCT ===")
    print(f"Testing: {retailer}")
    print(f"URL: {test_url}")
    print()
    
    extractor = PatchrightProductExtractor()
    result = await extractor.extract_product(test_url, retailer)
    
    print(f"\n=== RESULTS ===")
    print(f"Success: {result.success}")
    print(f"Method: {result.method_used}")
    print(f"Processing Time: {result.processing_time:.1f}s")
    
    if result.success:
        print(f"\nExtracted Data:")
        print(json.dumps(result.data, indent=2))
    else:
        print(f"\nErrors: {result.errors}")
    
    return result

if __name__ == "__main__":
    asyncio.run(test_single_product())

