"""
Test ZenRows API with 6 Hard Retailers
Tests the Commercial API Tower with ZenRows provider
"""

import asyncio
import time
from typing import Dict
import re
import sys
import os

sys.path.append(os.path.dirname(__file__))

from Extraction.CommercialAPI.commercial_config import CommercialAPIConfig
from Extraction.CommercialAPI.commercial_api_client import get_client

# Test retailers in order of difficulty
TEST_RETAILERS = [
    {
        'name': 'H&M',
        'difficulty': 'HIGH (Access Denied - BLOCKED)',
        'url': 'https://www2.hm.com/en_us/ladies/shop-by-product/dresses.html?sort=newProduct',
        'product_pattern': r'/en_us/productpage\.[0-9]+\.html',
        'expected_indicator': 'hm.com',
        'expected_min': 20,
        'notes': 'Patchright shows "Access Denied" - high anti-bot, may be blocked by IP',
    },
    {
        'name': 'Abercrombie',
        'difficulty': 'Medium (JavaScript)',
        'url': 'https://www.abercrombie.com/shop/us/womens-dresses-and-jumpsuits?pagefm=navigation-left+nav&rows=90&sort=newest&start=0',
        'product_pattern': r'/shop/us/p/[^"\'>\s]+',  # Capture full product URL with query params
        'expected_indicator': 'abercrombie',
        'expected_min': 60,  # Expected 90 products (60 minimum)
    },
    {
        'name': 'Aritzia',
        'difficulty': 'Cloudflare Turnstile + SPA (1-15s API delay)',
        'url': 'https://www.aritzia.com/us/en/clothing/dresses?srule=production_ecommerce_aritzia__Aritzia_US__products__en_US__newest',
        'product_pattern': r'/us/en/product/[\w\-]+/\d+',  # Capture full product URL
        'expected_indicator': 'aritzia',
        'expected_min': 40,
        'notes': 'Patchright uses 30s polling - variable API delay requires long wait',
    },
    {
        'name': 'Urban Outfitters',
        'difficulty': 'PerimeterX (same as Anthropologie)',
        'url': 'https://www.urbanoutfitters.com/womens-dresses?sort=newest',
        'product_pattern': r'/products/[\w\-]+',  # Capture full product URL
        'expected_indicator': 'urbanoutfitters',
        'expected_min': 50,
        'notes': 'Same PerimeterX as Anthropologie - should work with same config',
    },
    {
        'name': 'Anthropologie',
        'difficulty': 'PerimeterX (Press & Hold)',
        'url': 'https://www.anthropologie.com/dresses?order=Descending&sleevelength=Long%20Sleeve%2C3%2F4%20Sleeve%2CShort%20Sleeve&sort=tile.product.newestColorDate',
        'product_pattern': r'/shop/[\w\-]+',  # Capture full product URL
        'expected_indicator': 'anthropologie',
        'expected_min': 50,
        'notes': 'ZenRows works but Patchright sometimes fails - may need additional tuning for 100% reliability',
    },
    {
        'name': 'Nordstrom',
        'difficulty': 'Strongest (Akamai)',
        'url': 'https://www.nordstrom.com/browse/women/clothing/dresses?breadcrumb=Home%2FWomen%2FDresses&origin=topnav&sort=Newest',
        'product_pattern': r'/s/[\w\-]+/\d+',  # Capture full product URL (not just "/s/")
        'expected_indicator': 'nordstrom',
        'expected_min': 40,  # Expected 90+ products (40 minimum from Patchright)
    },
]


async def test_retailer(client, retailer: Dict) -> Dict:
    """
    Test a single retailer with ZenRows
    
    Returns:
        Dict with status, response_size, products_found, error, duration
    """
    print(f"\n{'='*80}")
    print(f"Testing: {retailer['name']} ({retailer['difficulty']})")
    print(f"URL: {retailer['url'][:80]}...")
    print(f"{'='*80}")
    
    start_time = time.time()
    
    result = {
        'name': retailer['name'],
        'difficulty': retailer['difficulty'],
        'status': 'FAILED',
        'http_status': None,
        'response_size': 0,
        'products_found': 0,
        'error': None,
        'duration': 0,
        'sample_html': '',
    }
    
    try:
        print(f"🌐 Fetching via ZenRows API...")
        
        html = await client.fetch_html(
            retailer['url'],
            retailer['name'].lower().replace(' ', '_').replace('&', ''),
            'catalog'
        )
        
        result['http_status'] = 200  # If we got here, it was successful
        result['response_size'] = len(html)
        
        print(f"✅ Response received: {result['response_size']:,} bytes")
        
        # Check for error indicators
        html_lower = html.lower()
        
        # Validate using Patchright's approach: check for real error pages
        # Large HTML (>500KB) with error keywords is likely legitimate content (JS variable names)
        error_phrases = [
            'access denied',
            'you have been blocked',
            'captcha challenge',  # More specific than just "captcha"
            'security check required',
            'unusual traffic detected',
            'verification required',
            'please verify you are a human',
        ]
        
        for phrase in error_phrases:
            if phrase in html_lower:
                # Only fail if HTML is small (likely actual error page)
                if result['response_size'] < 500000:  # 500 KB threshold
                    result['error'] = f"Error page detected: '{phrase}' (size: {result['response_size']:,} bytes)"
                    print(f"⚠️  {result['error']}")
                    result['duration'] = time.time() - start_time
                    return result
                else:
                    # Large HTML with error keyword - likely false positive
                    print(f"   ℹ️  Found '{phrase}' but HTML is large ({result['response_size']:,} bytes) - likely in JavaScript code")
        
        # Check if HTML contains expected retailer content
        if retailer['expected_indicator'] not in html_lower:
            result['error'] = f"Missing expected indicator: '{retailer['expected_indicator']}'"
            print(f"⚠️  {result['error']}")
        
        # Count product links
        product_matches = re.findall(retailer['product_pattern'], html, re.IGNORECASE)
        result['products_found'] = len(set(product_matches))  # Unique products
        
        print(f"🔍 Product URLs found: {result['products_found']}")
        
        # Show sample HTML
        result['sample_html'] = html[:500]
        print(f"\n📄 HTML Sample (first 500 chars):")
        print(result['sample_html'])
        print("...")
        
        # Validate success using Patchright's expected minimums
        expected_min = retailer.get('expected_min', 20)
        
        if result['products_found'] >= expected_min:
            result['status'] = 'SUCCESS'
            print(f"\n✅ {retailer['name']}: SUCCESS! ({result['products_found']}/{expected_min} minimum)")
        elif result['products_found'] >= expected_min * 0.5:  # At least 50% of expected
            result['status'] = 'PARTIAL'
            result['error'] = f'Below minimum: {result["products_found"]}/{expected_min} expected'
            print(f"\n⚠️  {retailer['name']}: PARTIAL ({result['products_found']}/{expected_min})")
        else:
            result['status'] = 'FAILED'
            result['error'] = f'Far below minimum: {result["products_found"]}/{expected_min} expected'
            print(f"\n❌ {retailer['name']}: FAILED ({result['products_found']}/{expected_min})")
    
    except Exception as e:
        result['error'] = str(e)[:200]
        print(f"❌ Exception: {e}")
    
    finally:
        result['duration'] = time.time() - start_time
        print(f"⏱️  Duration: {result['duration']:.2f}s")
    
    return result


async def main():
    """Run tests on all retailers and generate summary table"""
    
    print("=" * 80)
    print("🧪 ZENROWS API TEST - 6 HARD RETAILERS")
    print("=" * 80)
    
    # Initialize config
    config = CommercialAPIConfig()
    
    print(f"Provider: {config.ACTIVE_PROVIDER}")
    print(f"API Endpoint: {config.ZENROWS_API_ENDPOINT}")
    print(f"API Key: {config.ZENROWS_API_KEY[:10]}...{config.ZENROWS_API_KEY[-4:]}")
    print(f"Cost per request: ${config.COST_PER_REQUEST:.4f}")
    print("=" * 80)
    
    # Create client
    client = get_client(config)
    await client.initialize()
    
    results = []
    
    # Test each retailer
    for retailer in TEST_RETAILERS:
        result = await test_retailer(client, retailer)
        results.append(result)
        
        # Wait 2 seconds between tests to avoid rate limiting
        if retailer != TEST_RETAILERS[-1]:
            print("\n⏳ Waiting 2 seconds before next test...")
            await asyncio.sleep(2)
    
    # Close client
    await client.close()
    
    # Generate summary table
    print("\n\n" + "=" * 80)
    print("📊 SUMMARY TABLE")
    print("=" * 80)
    print(f"{'Retailer':<20} {'Anti-Bot':<30} {'Status':<12} {'Size':<15} {'Products':<10} {'Duration':<10}")
    print("-" * 80)
    
    for result in results:
        size_str = f"{result['response_size']:,} bytes" if result['response_size'] > 0 else "N/A"
        products_str = str(result['products_found']) if result['products_found'] > 0 else "0"
        duration_str = f"{result['duration']:.1f}s"
        
        # Add status emoji
        status_display = result['status']
        if result['status'] == 'SUCCESS':
            status_display = '✅ SUCCESS'
        elif result['status'] == 'PARTIAL':
            status_display = '⚠️  PARTIAL'
        else:
            status_display = '❌ FAILED'
        
        print(f"{result['name']:<20} {result['difficulty']:<30} {status_display:<12} {size_str:<15} {products_str:<10} {duration_str:<10}")
        
        if result['error']:
            print(f"  └─ Error: {result['error'][:60]}...")
    
    print("=" * 80)
    
    # Success rate
    success_count = sum(1 for r in results if r['status'] == 'SUCCESS')
    partial_count = sum(1 for r in results if r['status'] == 'PARTIAL')
    total_count = len(results)
    
    print(f"\n📈 Results:")
    print(f"   ✅ Success: {success_count}/{total_count}")
    print(f"   ⚠️  Partial: {partial_count}/{total_count}")
    print(f"   ❌ Failed: {total_count - success_count - partial_count}/{total_count}")
    print(f"   Success Rate: {(success_count/total_count)*100:.1f}%")
    print("=" * 80)
    
    # Recommendations
    print("\n💡 RECOMMENDATIONS:")
    print("-" * 80)
    
    successful_retailers = [r['name'] for r in results if r['status'] == 'SUCCESS']
    failed_retailers = [r['name'] for r in results if r['status'] == 'FAILED']
    
    if successful_retailers:
        print(f"✅ ZenRows works for: {', '.join(successful_retailers)}")
    
    if failed_retailers:
        print(f"❌ Keep Patchright Tower for: {', '.join(failed_retailers)}")
    
    if success_count >= 4:
        print("\n🎉 SUCCESS! ZenRows is viable for most retailers.")
        print("   Recommendation: Migrate working retailers to ZenRows")
    elif success_count >= 1:
        print("\n⚠️ PARTIAL SUCCESS. ZenRows works for some retailers.")
        print("   Recommendation: Hybrid approach (ZenRows + Patchright)")
    else:
        print("\n❌ ZenRows NOT WORKING. Keep Patchright Tower.")
    
    print("=" * 80)


if __name__ == '__main__':
    asyncio.run(main())

