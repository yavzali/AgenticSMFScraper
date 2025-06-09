#!/usr/bin/env python3
"""Test complete system fixes"""

import sys
import os
import asyncio

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unified_extractor import UnifiedExtractor

async def test_complete_fixes():
    """Test complete fixes: multiple images + DOM extraction + improved downloading"""
    
    print("🧪 Testing COMPLETE SYSTEM FIXES")
    print("=" * 60)
    
    extractor = UnifiedExtractor()
    
    # Test a variety of retailers and scenarios
    test_cases = [
        {
            'url': 'https://www.revolve.com/lagence-sima-shirt-dress-in-pine/dp/LAGR-WD258/',
            'retailer': 'revolve',
            'method': 'markdown_extractor',
            'expected_images': '3+'
        },
        {
            'url': 'https://www.aritzia.com/us/en/product/utility-dress/115422.html?color=1275',
            'retailer': 'aritzia',
            'method': 'playwright_multi_screenshot',
            'expected_images': '3+'
        },
        {
            'url': 'https://www.abercrombie.com/shop/us/p/cowl-neck-draped-maxi-dress-59263319?categoryId=12265&faceout=model&seq=05',
            'retailer': 'abercrombie',
            'method': 'playwright_multi_screenshot',
            'expected_images': '3+'
        }
    ]
    
    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n[{i}/{len(test_cases)}] Testing {test_case['retailer']}")
        print(f"URL: {test_case['url'][:70]}...")
        print(f"Expected method: {test_case['method']}")
        print(f"Expected images: {test_case['expected_images']}")
        
        try:
            result = await extractor.extract_product_data(test_case['url'], test_case['retailer'])
            
            success = result.success
            image_count = len(result.data.get('image_urls', [])) if success else 0
            title = result.data.get('title', 'N/A')[:40] if success else 'Failed'
            method = result.method_used if success else 'N/A'
            
            results.append({
                'retailer': test_case['retailer'],
                'success': success,
                'images': image_count,
                'title': title,
                'method': method,
                'time': result.processing_time
            })
            
            # Status evaluation
            if success and image_count >= 3:
                status = "✅ EXCELLENT"
            elif success and image_count >= 1:
                status = "⚠️ PARTIAL"
            else:
                status = "❌ FAILED"
            
            print(f"{status} - Success: {success}, Images: {image_count}, Method: {method}")
            print(f"Title: {title}")
            print(f"Time: {result.processing_time:.2f}s")
            
            if success and image_count > 0:
                # Show first few image URLs
                image_urls = result.data.get('image_urls', [])
                for j, img_url in enumerate(image_urls[:2], 1):
                    print(f"  📷 {j}: {img_url[:80]}...")
                    
        except Exception as e:
            print(f"💥 Exception: {e}")
            results.append({
                'retailer': test_case['retailer'],
                'success': False,
                'images': 0,
                'title': 'Exception',
                'method': 'N/A',
                'time': 0
            })
    
    # Summary
    print(f"\n🎯 COMPLETE SYSTEM TEST SUMMARY")
    print("=" * 60)
    
    total_tests = len(results)
    successful_tests = sum(1 for r in results if r['success'])
    total_images = sum(r['images'] for r in results)
    avg_time = sum(r['time'] for r in results) / total_tests if total_tests > 0 else 0
    
    print(f"✅ Success Rate: {successful_tests}/{total_tests} ({successful_tests/total_tests*100:.1f}%)")
    print(f"📸 Total Images: {total_images} ({total_images/total_tests:.1f} avg per retailer)")
    print(f"⏱️ Avg Time: {avg_time:.1f}s")
    
    for result in results:
        status = "✅" if result['success'] and result['images'] >= 3 else "⚠️" if result['success'] else "❌"
        print(f"{status} {result['retailer']}: {result['images']} images, {result['time']:.1f}s")

if __name__ == "__main__":
    asyncio.run(test_complete_fixes()) 