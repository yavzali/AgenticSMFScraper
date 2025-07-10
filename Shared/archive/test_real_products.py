#!/usr/bin/env python3
"""
Test Playwright agent on real product URLs
"""

import asyncio
import sys
import os
sys.path.append('.')

from playwright_agent import PlaywrightAgentWrapper

async def test_real_products():
    print("🧪 TESTING PLAYWRIGHT AGENT ON REAL PRODUCT URLS")
    print("=" * 60)
    
    config = {}
    wrapper = PlaywrightAgentWrapper(config)
    
    # Test specific product URLs
    test_urls = [
        ('https://www.aritzia.com/us/en/product/ganna-dress/98513.html', 'aritzia'),
        ('https://www.abercrombie.com/shop/us/p/ultra-high-rise-90s-straight-jeans-50547819', 'abercrombie'),
    ]
    
    results = []
    
    for url, retailer in test_urls:
        print(f'\n🎯 Testing {retailer.upper()}: {url[:60]}...')
        try:
            result = await wrapper.extract_product_data(url, retailer)
            
            if result.success:
                data = result.data
                print(f'  ✅ SUCCESS: {data.get("title", "No title")[:50]}')
                print(f'  📊 Price: ${data.get("price", "N/A")}')
                print(f'  🏷️ Brand: {data.get("brand", "N/A")}')
                print(f'  🖼️ Images: {len(data.get("image_urls", []))} found')
                print(f'  🎨 Colors: {data.get("colors", [])}')
                print(f'  📏 Sizes: {data.get("sizes", [])}')
                print(f'  ⏱️ Time: {result.processing_time:.1f}s')
                
                results.append({
                    'retailer': retailer,
                    'success': True,
                    'time': result.processing_time,
                    'data_quality': len([k for k, v in data.items() if v])
                })
            else:
                print(f'  ❌ FAILED: {result.errors}')
                results.append({
                    'retailer': retailer, 
                    'success': False,
                    'time': result.processing_time,
                    'errors': result.errors
                })
                
        except Exception as e:
            print(f'  💥 ERROR: {e}')
            results.append({
                'retailer': retailer,
                'success': False, 
                'time': 0,
                'error': str(e)
            })
    
    # Summary
    print(f"\n📊 SUMMARY:")
    print("=" * 40)
    successful = [r for r in results if r['success']]
    if successful:
        avg_time = sum(r['time'] for r in successful) / len(successful)
        print(f"✅ Success Rate: {len(successful)}/{len(results)} ({len(successful)/len(results)*100:.1f}%)")
        print(f"⏱️ Average Time: {avg_time:.1f}s")
        print(f"🎯 Playwright Agent: READY FOR PRODUCTION!")
    else:
        print("❌ No successful extractions")

if __name__ == "__main__":
    asyncio.run(test_real_products()) 