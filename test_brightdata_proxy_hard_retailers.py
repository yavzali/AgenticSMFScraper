"""
Test Bright Data Web Unlocker via HTTP PROXY on Hard Retailers
Tests the "hardsite_modfash_extower" zone configuration
"""

import asyncio
import aiohttp
import time
from typing import Dict, Optional
import re

# Bright Data HTTP Proxy Configuration
PROXY_HOST = "brd.superproxy.io"
PROXY_PORT = 33335
PROXY_USERNAME = "brd-customer-hl_12a2049f-zone-hardsite_modfash_extower"
PROXY_PASSWORD = "tp3ajprkp1iv"

# Test retailers in order of difficulty
TEST_RETAILERS = [
    {
        'name': 'H&M',
        'difficulty': 'Low',
        'url': 'https://www2.hm.com/en_us/ladies/shop-by-product/dresses.html?sort=newProduct',
        'product_pattern': r'/en_us/productpage\.[0-9]+\.html',
        'expected_indicator': 'hm.com',
    },
    {
        'name': 'Abercrombie',
        'difficulty': 'Medium',
        'url': 'https://www.abercrombie.com/shop/us/womens-dresses-and-jumpsuits?pagefm=navigation-left+nav&rows=90&sort=newest&start=0',
        'product_pattern': r'/shop/us/p/',
        'expected_indicator': 'abercrombie',
    },
    {
        'name': 'Aritzia',
        'difficulty': 'Cloudflare',
        'url': 'https://www.aritzia.com/us/en/clothing/dresses?srule=production_ecommerce_aritzia__Aritzia_US__products__en_US__newest',
        'product_pattern': r'/us/en/product/',
        'expected_indicator': 'aritzia',
    },
    {
        'name': 'Urban Outfitters',
        'difficulty': 'PerimeterX',
        'url': 'https://www.urbanoutfitters.com/womens-dresses?sort=newest',
        'product_pattern': r'/products/',
        'expected_indicator': 'urbanoutfitters',
    },
    {
        'name': 'Anthropologie',
        'difficulty': 'PerimeterX (Press & Hold)',
        'url': 'https://www.anthropologie.com/dresses?order=Descending&sleevelength=Long%20Sleeve%2C3%2F4%20Sleeve%2CShort%20Sleeve&sort=tile.product.newestColorDate',
        'product_pattern': r'/shop/',
        'expected_indicator': 'anthropologie',
    },
    {
        'name': 'Nordstrom',
        'difficulty': 'Strongest',
        'url': 'https://www.nordstrom.com/browse/women/clothing/dresses?breadcrumb=Home%2FWomen%2FDresses&origin=topnav&sort=Newest',
        'product_pattern': r'/s/',
        'expected_indicator': 'nordstrom',
    },
]


async def test_retailer(retailer: Dict) -> Dict:
    """
    Test a single retailer via Bright Data HTTP Proxy
    
    Returns:
        Dict with status, response_size, products_found, error, duration
    """
    print(f"\n{'='*80}")
    print(f"Testing: {retailer['name']} ({retailer['difficulty']} anti-bot)")
    print(f"URL: {retailer['url'][:80]}...")
    print(f"{'='*80}")
    
    start_time = time.time()
    
    # Construct proxy URL
    proxy_url = (
        f"http://{PROXY_USERNAME}:{PROXY_PASSWORD}@"
        f"{PROXY_HOST}:{PROXY_PORT}"
    )
    
    # Headers (minimal, let Bright Data add realistic ones)
    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        ),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    
    result = {
        'name': retailer['name'],
        'difficulty': retailer['difficulty'],
        'status': 'FAILED',
        'http_status': None,
        'response_size': 0,
        'products_found': 0,
        'error': None,
        'duration': 0,
    }
    
    try:
        # Create session with 60 second timeout (anti-bot sites take longer)
        timeout = aiohttp.ClientTimeout(total=60, connect=15, sock_read=60)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            print(f"🌐 Fetching via Bright Data proxy (60s timeout)...")
            
            async with session.get(
                retailer['url'],
                proxy=proxy_url,
                headers=headers,
                ssl=False,  # Bright Data handles SSL termination
                allow_redirects=True,
            ) as response:
                result['http_status'] = response.status
                
                print(f"📊 HTTP Status: {response.status}")
                
                if response.status != 200:
                    error_text = await response.text()
                    result['error'] = f"HTTP {response.status}: {error_text[:200]}"
                    print(f"❌ Error: {result['error']}")
                    return result
                
                # Get HTML
                html = await response.text()
                result['response_size'] = len(html)
                
                print(f"✅ Response received: {result['response_size']:,} bytes")
                
                # Check for error indicators
                html_lower = html.lower()
                
                error_indicators = [
                    'access denied',
                    'you have been blocked',
                    'captcha',
                    'security check required',
                    'unusual traffic detected',
                    'verification required',
                    'please verify you are a human',
                ]
                
                for indicator in error_indicators:
                    if indicator in html_lower:
                        result['error'] = f"Error page detected: '{indicator}'"
                        print(f"⚠️  {result['error']}")
                        return result
                
                # Check if HTML contains expected retailer content
                if retailer['expected_indicator'] not in html_lower:
                    result['error'] = f"Missing expected indicator: '{retailer['expected_indicator']}'"
                    print(f"⚠️  {result['error']}")
                    # Don't fail here, continue to check products
                
                # Count product links
                product_matches = re.findall(retailer['product_pattern'], html, re.IGNORECASE)
                result['products_found'] = len(set(product_matches))  # Unique products
                
                print(f"🔍 Product URLs found: {result['products_found']}")
                
                # Show sample HTML
                print(f"\n📄 HTML Sample (first 500 chars):")
                print(html[:500])
                print("...")
                
                # Validate success
                if result['response_size'] > 10000 and result['products_found'] > 5:
                    result['status'] = 'SUCCESS'
                    print(f"\n✅ {retailer['name']}: SUCCESS!")
                elif result['products_found'] > 0:
                    result['status'] = 'PARTIAL'
                    result['error'] = 'Low product count (might be pagination issue)'
                    print(f"\n⚠️  {retailer['name']}: PARTIAL SUCCESS (low product count)")
                else:
                    result['status'] = 'FAILED'
                    result['error'] = 'No product URLs found in HTML'
                    print(f"\n❌ {retailer['name']}: FAILED (no products found)")
    
    except asyncio.TimeoutError:
        result['error'] = 'Request timeout (60 seconds exceeded)'
        print(f"❌ Timeout after 60 seconds")
    
    except aiohttp.ClientError as e:
        result['error'] = f"Connection error: {str(e)[:200]}"
        print(f"❌ Connection error: {e}")
    
    except Exception as e:
        result['error'] = f"Unexpected error: {str(e)[:200]}"
        print(f"❌ Unexpected error: {e}")
    
    finally:
        result['duration'] = time.time() - start_time
        print(f"⏱️  Duration: {result['duration']:.2f}s")
    
    return result


async def main():
    """Run tests on all retailers and generate summary table"""
    
    print("=" * 80)
    print("🧪 BRIGHT DATA WEB UNLOCKER - HTTP PROXY TEST")
    print("=" * 80)
    print(f"Proxy: {PROXY_HOST}:{PROXY_PORT}")
    print(f"Zone: hardsite_modfash_extower")
    print(f"Method: HTTP Proxy (aiohttp)")
    print(f"Timeout: 60 seconds per retailer")
    print("=" * 80)
    
    results = []
    
    # Test each retailer
    for retailer in TEST_RETAILERS:
        result = await test_retailer(retailer)
        results.append(result)
        
        # Wait 2 seconds between tests to avoid rate limiting
        if retailer != TEST_RETAILERS[-1]:
            print("\n⏳ Waiting 2 seconds before next test...")
            await asyncio.sleep(2)
    
    # Generate summary table
    print("\n\n" + "=" * 80)
    print("📊 SUMMARY TABLE")
    print("=" * 80)
    print(f"{'Retailer':<20} {'Anti-Bot':<25} {'Status':<10} {'Size':<15} {'Products':<10} {'Duration':<10}")
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
        
        print(f"{result['name']:<20} {result['difficulty']:<25} {status_display:<10} {size_str:<15} {products_str:<10} {duration_str:<10}")
        
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
        print(f"✅ Use Commercial API Tower for: {', '.join(successful_retailers)}")
    
    if failed_retailers:
        print(f"❌ Keep Patchright Tower for: {', '.join(failed_retailers)}")
    
    print("=" * 80)


if __name__ == '__main__':
    asyncio.run(main())

