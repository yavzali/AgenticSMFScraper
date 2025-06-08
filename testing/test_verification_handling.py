#!/usr/bin/env python3
"""
Test verification handling capabilities
"""

import asyncio
import sys
import os
from unified_extractor import UnifiedExtractor

# Test verification-heavy retailers
VERIFICATION_RETAILERS = [
    ("https://www.aritzia.com/us/en/product/effortless-pant/70347.html", "aritzia"),
    ("https://www.anthropologie.com/clothing/dresses", "anthropologie"),
    ("https://www.urban_outfitters.com/women", "urban_outfitters")
]

async def test_verification_handling():
    """Test verification challenge handling"""
    print("🔐 Testing Verification Handling")
    print("=" * 40)
    
    extractor = UnifiedExtractor()
    
    for url, retailer in VERIFICATION_RETAILERS:
        print(f"\n🧪 Testing {retailer}: {url}")
        
        try:
            result = await extractor.extract_product_data(url, retailer)
            
            print(f"  📤 Method: {result.method_used}")
            print(f"  ✅ Success: {result.success}")
            print(f"  ⏱️  Time: {result.processing_time:.2f}s")
            
            if result.success:
                data = result.data
                print(f"  📦 Data fields: {len(data.keys())} extracted")
                if 'title' in data:
                    title = data['title'][:50] + '...' if len(data.get('title', '')) > 50 else data.get('title', 'N/A')
                    print(f"  📝 Title: {title}")
            
            if result.warnings:
                print(f"  ⚠️  Warnings: {result.warnings}")
            
            if result.errors:
                print(f"  ❌ Errors: {result.errors}")
                
        except Exception as e:
            print(f"  💥 Exception: {e}")
    
    print("\n🎯 Verification handling test complete")

if __name__ == "__main__":
    asyncio.run(test_verification_handling()) 