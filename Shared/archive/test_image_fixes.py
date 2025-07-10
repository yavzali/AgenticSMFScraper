#!/usr/bin/env python3

import asyncio
from unified_extractor import UnifiedExtractor

async def test_image_extraction():
    """Test the fixed image extraction for multiple retailers"""
    
    print("🧪 Testing FIXED Image Extraction")
    print("=" * 50)
    
    extractor = UnifiedExtractor()
    
    # Test URLs that should extract multiple images
    test_cases = [
        {
            'url': 'https://www.revolve.com/lagence-sima-shirt-dress-in-pine/dp/LAGR-WD258/',
            'retailer': 'revolve',
            'expected_multiple': True
        },
        {
            'url': 'https://shop.mango.com/us/en/p/women/dresses-and-jumpsuits/dresses/short-button-down-linen-blend-dress_87039065',
            'retailer': 'mango', 
            'expected_multiple': True
        },
        {
            'url': 'https://www.uniqlo.com/us/en/products/E479225-000/',
            'retailer': 'uniqlo',
            'expected_multiple': True
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n[{i}/{len(test_cases)}] Testing {test_case['retailer']}")
        print(f"URL: {test_case['url']}")
        
        try:
            result = await extractor.extract_product_data(test_case['url'], test_case['retailer'])
            
            if result.success:
                data = result.data
                image_count = len(data.get('image_urls', []))
                print(f"✅ Success: {result.success}")
                print(f"📸 Images extracted: {image_count}")
                print(f"📝 Title: {data.get('title', 'N/A')[:50]}...")
                print(f"🔧 Method: {result.method_used}")
                print(f"⏱️  Time: {result.processing_time:.2f}s")
                
                # Check if we got multiple images as expected
                if test_case['expected_multiple'] and image_count > 1:
                    print(f"🎯 FIXED: Multiple images extracted ({image_count})")
                elif image_count == 1:
                    print(f"⚠️  Only 1 image - investigating needed")
                else:
                    print(f"❌ No images extracted")
            else:
                print(f"❌ Failed: {result.errors}")
                
        except Exception as e:
            print(f"💥 Exception: {e}")
    
    print(f"\n🎯 Image extraction test complete")

if __name__ == "__main__":
    asyncio.run(test_image_extraction()) 