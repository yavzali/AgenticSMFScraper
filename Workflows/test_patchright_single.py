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
    # Test URL: Anthropologie dress (Patchright retailer)
    # Real product: The Emmy Short-Sleeve Swing Mini Dress by Maeve: Velvet Edition
    test_url = "https://www.anthropologie.com/shop/the-emmy-short-sleeve-swing-mini-dress-by-maeve-velvet-edition?color=525&type=STANDARD"
    retailer = "anthropologie"
    
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

