#!/usr/bin/env python3
"""
Test single URL extraction with the unified system
"""

import asyncio
import sys
import os
from unified_extractor import UnifiedExtractor

async def test_single_url(url: str, retailer: str):
    """Test single URL extraction"""
    print(f"🧪 Testing single URL extraction")
    print(f"URL: {url}")
    print(f"Retailer: {retailer}")
    print("=" * 50)
    
    extractor = UnifiedExtractor()
    
    try:
        result = await extractor.extract_product_data(url, retailer)
        
        print(f"📤 Method used: {result.method_used}")
        print(f"✅ Success: {result.success}")
        print(f"⏱️  Processing time: {result.processing_time:.2f}s")
        
        if result.success:
            data = result.data
            print(f"\n📦 Extracted data ({len(data.keys())} fields):")
            
            # Show key fields
            for key in ['title', 'brand', 'price', 'original_price', 'retailer']:
                if key in data:
                    value = data[key]
                    if key == 'title' and len(str(value)) > 60:
                        value = str(value)[:60] + '...'
                    print(f"  {key}: {value}")
            
            # Show image count
            image_urls = data.get('image_urls', [])
            print(f"  image_urls: {len(image_urls)} images")
            
            # Show other fields
            other_fields = [k for k in data.keys() if k not in ['title', 'brand', 'price', 'original_price', 'retailer', 'image_urls']]
            if other_fields:
                print(f"  other_fields: {', '.join(other_fields)}")
        
        if result.warnings:
            print(f"\n⚠️  Warnings: {result.warnings}")
        
        if result.errors:
            print(f"\n❌ Errors: {result.errors}")
            
    except Exception as e:
        print(f"💥 Exception: {e}")
    
    print("\n🎯 Single URL test complete")

if __name__ == "__main__":
    if len(sys.argv) >= 3:
        url = sys.argv[1]
        retailer = sys.argv[2]
        asyncio.run(test_single_url(url, retailer))
    else:
        print("Usage: python test_single_url.py <url> <retailer>")
        print("Example: python test_single_url.py 'https://www.uniqlo.com/us/en/products/E443577-000' uniqlo") 