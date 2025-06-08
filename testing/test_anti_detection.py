#!/usr/bin/env python3
"""
Test anti-detection measures and verification handling
"""

import asyncio
import sys
import os
from unified_extractor import UnifiedExtractor

# Test URLs that require anti-detection
TEST_URLS = [
    ("https://www.aritzia.com/us/en/product/effortless-pant/70347.html", "aritzia"),
    ("https://www.anthropologie.com/clothing/dresses", "anthropologie"),
    ("https://www.nordstrom.com/browse/women/clothing", "nordstrom")
]

async def test_anti_detection():
    """Test anti-detection capabilities"""
    print("🛡️ Testing Anti-Detection Measures")
    print("=" * 40)
    
    extractor = UnifiedExtractor()
    
    for url, retailer in TEST_URLS:
        print(f"\n🧪 Testing {retailer}: {url}")
        
        try:
            result = await extractor.extract_product_data(url, retailer)
            
            print(f"  📤 Method: {result.method_used}")
            print(f"  ✅ Success: {result.success}")
            print(f"  ⏱️  Time: {result.processing_time:.2f}s")
            
            if result.warnings:
                print(f"  ⚠️  Warnings: {result.warnings}")
            
            if result.errors:
                print(f"  ❌ Errors: {result.errors}")
                
        except Exception as e:
            print(f"  💥 Exception: {e}")
    
    print("\n🎯 Anti-detection testing complete")

if __name__ == "__main__":
    asyncio.run(test_anti_detection()) 