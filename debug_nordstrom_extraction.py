"""
Debug script to inspect actual extracted product data from Nordstrom
"""

import asyncio
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "Extraction", "Patchright"))
from patchright_catalog_extractor import PatchrightCatalogExtractor

async def debug_extraction():
    """Test extraction and print detailed product data"""
    
    url = "https://www.nordstrom.com/browse/women/clothing/dresses"
    retailer = "nordstrom"
    
    catalog_prompt = """Extract all dress products from this Nordstrom catalog page.
For each product, extract:
- Title
- Price (current/sale price if on sale)
- Original price (if different from current price)
- Sale status

Return a JSON array."""
    
    print("\n" + "="*70)
    print("NORDSTROM EXTRACTION DATA INSPECTOR")
    print("="*70 + "\n")
    
    extractor = PatchrightCatalogExtractor()
    
    try:
        result = await extractor.extract_catalog(url, retailer, catalog_prompt)
        
        print(f"Success: {result.get('success')}")
        print(f"Total products: {result.get('total_found')}")
        print(f"Method: {result.get('method_used')}\n")
        
        products = result.get('products', [])
        
        print(f"\n{'='*70}")
        print(f"FIRST 10 PRODUCTS (detailed):")
        print(f"{'='*70}\n")
        
        for i, product in enumerate(products[:10]):
            print(f"\n--- PRODUCT #{i+1} ---")
            print(f"Title: {product.get('title', 'N/A')}")
            print(f"Price: {product.get('price', 'N/A')}")
            print(f"Original Price: {product.get('original_price', 'N/A')}")
            print(f"Sale Status: {product.get('sale_status', 'N/A')}")
            print(f"URL: {product.get('url', 'N/A')[:80] if product.get('url') else 'N/A'}")
            print(f"Product Code: {product.get('product_code', 'N/A')}")
            print(f"Needs Reprocessing: {product.get('needs_reprocessing', False)}")
            print(f"Match Confidence: {product.get('match_confidence', 'N/A')}")
        
        # Count products with various fields
        with_price = sum(1 for p in products if p.get('price') and p.get('price') != 0)
        with_title = sum(1 for p in products if p.get('title') and len(p.get('title', '')) > 5)
        with_url = sum(1 for p in products if p.get('url'))
        needs_reprocess = sum(1 for p in products if p.get('needs_reprocessing'))
        
        print(f"\n{'='*70}")
        print(f"STATISTICS:")
        print(f"{'='*70}")
        print(f"Total products: {len(products)}")
        print(f"With price: {with_price} ({with_price/len(products)*100:.1f}%)")
        print(f"With title: {with_title} ({with_title/len(products)*100:.1f}%)")
        print(f"With URL: {with_url} ({with_url/len(products)*100:.1f}%)")
        print(f"Needs reprocessing: {needs_reprocess} ({needs_reprocess/len(products)*100:.1f}%)")
        
        print(f"\n{'='*70}")
        print(f"DIAGNOSIS:")
        print(f"{'='*70}\n")
        
        if with_price == 0:
            print("❌ CRITICAL: No products have prices!")
            print("   Possible causes:")
            print("   1. Gemini Vision failed to extract prices from screenshot")
            print("   2. DOM price extraction failed")
            print("   3. Merge logic didn't transfer prices correctly")
        elif with_price < len(products) * 0.5:
            print(f"⚠️  WARNING: Only {with_price}/{len(products)} products have prices")
            print("   Gemini may have only seen products in visible viewport")
            print("   DOM-first mode might be better for Nordstrom")
        else:
            print(f"✅ Good: {with_price}/{len(products)} products have prices")
        
    finally:
        await extractor.cleanup()

if __name__ == "__main__":
    asyncio.run(debug_extraction())

