#!/usr/bin/env python3

import asyncio
from unified_extractor import UnifiedExtractor

async def test_image_downloads():
    """Test image downloading for problematic retailers"""
    
    print("🧪 Testing Image Download Issues")
    print("=" * 50)
    
    extractor = UnifiedExtractor()
    
    # Test URLs that had image download problems
    test_cases = [
        {
            'url': 'https://www.urbanoutfitters.com/shop/97-nyc-applique-graphic-baby-tee?category=womens-clothing-sale&color=004&type=REGULAR&quantity=1',
            'retailer': 'urban_outfitters',
            'issue': 'No images downloaded'
        },
        {
            'url': 'https://www.abercrombie.com/shop/us/p/cowl-neck-draped-maxi-dress-59263319?categoryId=12265&faceout=model&seq=05',
            'retailer': 'abercrombie',
            'issue': 'No images downloaded'
        },
        {
            'url': 'https://www.aritzia.com/us/en/product/utility-dress/115422.html?color=1275',
            'retailer': 'aritzia',
            'issue': 'Images failed to appear in Shopify'
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n[{i}/{len(test_cases)}] Testing {test_case['retailer']}")
        print(f"Issue: {test_case['issue']}")
        print(f"URL: {test_case['url']}")
        
        try:
            result = await extractor.extract_product_data(test_case['url'], test_case['retailer'])
            
            if result.success:
                data = result.data
                image_count = len(data.get('image_urls', []))
                print(f"✅ Extraction Success: {result.success}")
                print(f"📸 Images extracted: {image_count}")
                print(f"📝 Title: {data.get('title', 'N/A')[:50]}...")
                print(f"🔧 Method: {result.method_used}")
                print(f"⏱️  Time: {result.processing_time:.2f}s")
                
                # Show actual image URLs for debugging
                image_urls = data.get('image_urls', [])
                for j, img_url in enumerate(image_urls[:3], 1):
                    print(f"  📷 Image {j}: {img_url[:80]}...")
                    
            else:
                print(f"❌ Extraction Failed: {result.errors}")
                
        except Exception as e:
            print(f"💥 Exception: {e}")
    
    print(f"\n🎯 Image download test complete")

if __name__ == "__main__":
    asyncio.run(test_image_downloads()) 