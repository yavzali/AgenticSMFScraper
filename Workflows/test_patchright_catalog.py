"""
Quick test for Patchright Catalog Extractor
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../Shared"))
sys.path.append(os.path.join(os.path.dirname(__file__), "../Extraction/Patchright"))

import asyncio
import json
from patchright_catalog_extractor import PatchrightCatalogExtractor

async def test_catalog():
    # Test URL: Anthropologie dresses catalog (Patchright retailer)
    test_url = "https://www.anthropologie.com/dresses?sort=tile.product.newestColorDate&order=Descending"
    retailer = "anthropologie"
    
    print(f"=== TEST 8: PATCHRIGHT CATALOG ===")
    print(f"Testing: {retailer}")
    print(f"URL: {test_url}")
    print()
    
    extractor = PatchrightCatalogExtractor()
    
    # Build catalog prompt (similar to markdown)
    catalog_prompt = f"""Extract product data from {retailer} catalog page.
    
Return products with: title, price, url, image
Limit to first 10 products for testing."""
    
    result = await extractor.extract_catalog(test_url, retailer, catalog_prompt)
    
    print(f"\n=== RESULTS ===")
    print(f"Success: {result.get('success', False)}")
    print(f"Products Found: {result.get('total_found', 0)}")
    print(f"Processing Time: {result.get('processing_time', 0):.1f}s")
    
    if result.get('success'):
        products = result.get('products', [])
        print(f"\n=== SAMPLE PRODUCTS (first 3) ===")
        for i, product in enumerate(products[:3], 1):
            print(f"\nProduct {i}:")
            print(f"  Title: {product.get('title', 'N/A')[:60]}...")
            print(f"  Price: ${product.get('price', 0)}")
            print(f"  URL: {product.get('url', 'N/A')[:80]}...")
    else:
        print(f"\nErrors: {result.get('errors', [])}")
    
    return result

if __name__ == "__main__":
    asyncio.run(test_catalog())

