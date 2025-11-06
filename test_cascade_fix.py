#!/usr/bin/env python3
"""
Test script to verify the cascade fix works correctly
Tests with the Polo Ralph Lauren product that previously fell back to Playwright
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "Shared"))

import asyncio
from markdown_extractor import MarkdownExtractor

async def test_cascade_fix():
    """Test the fixed cascade with a product that previously failed"""
    
    # This URL previously triggered Playwright fallback
    test_url = "https://www.revolve.com/polo-ralph-lauren-x-revolve-graphic-cropped-quarter-zip-sweatshirt-in-signal-yellow-polo-black-multi/dp/PLOR-WS53/"
    retailer = "revolve"
    
    print(f"\n{'='*80}")
    print(f"TESTING CASCADE FIX")
    print(f"{'='*80}")
    print(f"URL: {test_url}")
    print(f"Retailer: {retailer}")
    print(f"\nThis product previously:")
    print(f"  ❌ DeepSeek returned incomplete data (missing price/images)")
    print(f"  ❌ Gemini was NOT tried")
    print(f"  ⚠️  Fell back to Playwright")
    print(f"\nExpected behavior now:")
    print(f"  ✅ DeepSeek returns incomplete data")
    print(f"  ✅ Validation catches it")
    print(f"  ✅ Gemini is tried as fallback")
    print(f"  ✅ Success without Playwright")
    print(f"{'='*80}\n")
    
    extractor = MarkdownExtractor()
    
    try:
        result = await extractor.extract_product_data(test_url, retailer)
        
        print(f"\n{'='*80}")
        print(f"RESULT")
        print(f"{'='*80}")
        print(f"Success: {result.success}")
        print(f"Method: {result.method_used}")
        print(f"Processing Time: {result.processing_time:.2f}s")
        print(f"Should Fallback: {result.should_fallback}")
        
        if result.success:
            print(f"\n✅ EXTRACTION SUCCESS")
            print(f"Title: {result.data.get('title', 'N/A')}")
            print(f"Price: {result.data.get('price', 'N/A')}")
            print(f"Images: {len(result.data.get('image_urls', []))} images")
            print(f"Stock: {result.data.get('stock_status', 'N/A')}")
            
            if result.should_fallback:
                print(f"\n⚠️  WARNING: Still flagged for fallback despite success")
                print(f"Warnings: {result.warnings}")
            else:
                print(f"\n🎉 CASCADE FIX WORKING!")
                print(f"   - Markdown extraction succeeded")
                print(f"   - No Playwright fallback needed")
        else:
            print(f"\n❌ EXTRACTION FAILED")
            print(f"Errors: {result.errors}")
            print(f"Warnings: {result.warnings}")
            
            if result.should_fallback:
                print(f"\n⚠️  Will fall back to Playwright (expected if both LLMs failed)")
        
        print(f"{'='*80}\n")
        
        return result.success and not result.should_fallback
        
    except Exception as e:
        print(f"\n❌ TEST FAILED WITH EXCEPTION")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_cascade_fix())
    sys.exit(0 if success else 1)

