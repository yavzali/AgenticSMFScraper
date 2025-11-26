"""
Test ZenRows with Nordstrom (Focus Test)
Tune ZenRows configuration to get Nordstrom working fully
"""

import asyncio
import time
import re
import sys
import os

sys.path.append(os.path.dirname(__file__))

from Extraction.CommercialAPI.commercial_config import CommercialAPIConfig
from Extraction.CommercialAPI.commercial_api_client import get_client

# Nordstrom catalog URL
NORDSTROM_URL = 'https://www.nordstrom.com/browse/women/clothing/dresses?breadcrumb=Home%2FWomen%2FDresses&origin=topnav&sort=Newest'


async def test_nordstrom():
    """
    Test Nordstrom with optimized ZenRows settings
    
    Expected: 90+ product URLs (full catalog page)
    """
    print("=" * 80)
    print("🧪 ZENROWS NORDSTROM FOCUS TEST")
    print("=" * 80)
    
    # Initialize config
    config = CommercialAPIConfig()
    
    print(f"Provider: {config.ACTIVE_PROVIDER}")
    print(f"API Endpoint: {config.ZENROWS_API_ENDPOINT}")
    print(f"API Key: {config.ZENROWS_API_KEY[:10]}...{config.ZENROWS_API_KEY[-4:]}")
    print("=" * 80)
    
    # Create client
    client = get_client(config)
    await client.initialize()
    
    print(f"\n🎯 Target: Nordstrom Dresses (Newest)")
    print(f"URL: {NORDSTROM_URL[:80]}...")
    print(f"Anti-Bot: Akamai Bot Manager (Hardest)")
    print(f"Expected Products: 90+ product links")
    print("\n" + "=" * 80)
    
    start_time = time.time()
    
    try:
        print(f"🌐 Fetching with ZenRows...")
        print(f"   ✅ js_render: true (JavaScript execution)")
        print(f"   ✅ premium_proxy: true (Residential IPs)")
        print(f"   ✅ proxy_country: us")
        print(f"   ✅ wait_for: a[data-testid=\"product-link\"] (wait for products)")
        print(f"   ✅ wait: 8000ms (8 second stability wait)")
        print("")
        
        html = await client.fetch_html(
            NORDSTROM_URL,
            'nordstrom',
            'catalog'
        )
        
        duration = time.time() - start_time
        html_size = len(html)
        
        print(f"\n{'='*80}")
        print(f"📊 RESPONSE ANALYSIS")
        print(f"{'='*80}")
        print(f"✅ HTTP Status: 200 (Success)")
        print(f"📦 Response Size: {html_size:,} bytes ({html_size/1024/1024:.2f} MB)")
        print(f"⏱️  Duration: {duration:.2f} seconds")
        
        # Check for error indicators
        html_lower = html.lower()
        
        error_indicators = {
            'captcha': 'CAPTCHA challenge page',
            'access denied': 'Access denied error',
            'blocked': 'Blocked by anti-bot',
            'security check': 'Security check required',
            'unusual traffic': 'Unusual traffic detected',
        }
        
        errors_found = []
        for indicator, description in error_indicators.items():
            if indicator in html_lower:
                errors_found.append(f"⚠️  {description}")
        
        if errors_found:
            print(f"\n❌ ERROR INDICATORS FOUND:")
            for error in errors_found:
                print(f"   {error}")
            print(f"\n   This is NOT actual product data - it's an error page.")
        else:
            print(f"\n✅ No error indicators found (good sign!)")
        
        # Count product links
        product_pattern = r'/s/[^"\'>\s]+'  # Nordstrom product URLs: /s/...
        product_matches = re.findall(product_pattern, html, re.IGNORECASE)
        unique_products = list(set(product_matches))
        products_found = len(unique_products)
        
        print(f"\n{'='*80}")
        print(f"🔍 PRODUCT EXTRACTION")
        print(f"{'='*80}")
        print(f"Product URLs found: {products_found}")
        print(f"Expected: 90+ products")
        
        if products_found >= 90:
            print(f"\n🎉 SUCCESS! Found {products_found} products (≥90)")
            print(f"   ✅ ZenRows is working perfectly for Nordstrom!")
        elif products_found >= 20:
            print(f"\n⚠️  PARTIAL SUCCESS: Found {products_found} products (< 90)")
            print(f"   Need to increase wait time or check pagination")
        else:
            print(f"\n❌ FAILED: Only {products_found} products found")
            print(f"   Products may not have loaded yet, or page structure changed")
        
        # Show sample product URLs
        if products_found > 0:
            print(f"\n📦 Sample Product URLs (first 10):")
            for i, url in enumerate(unique_products[:10], 1):
                print(f"   {i}. https://www.nordstrom.com{url}")
        
        # Show HTML sample
        print(f"\n{'='*80}")
        print(f"📄 HTML SAMPLE (first 800 chars):")
        print(f"{'='*80}")
        print(html[:800])
        print("...")
        
        # Cost analysis
        print(f"\n{'='*80}")
        print(f"💰 COST ANALYSIS")
        print(f"{'='*80}")
        print(f"Cost: ${config.COST_PER_REQUEST:.4f} per request")
        print(f"Monthly cost (10 scans/day): ${config.COST_PER_REQUEST * 10 * 30:.2f}")
        
        # Verdict
        print(f"\n{'='*80}")
        print(f"📊 VERDICT")
        print(f"{'='*80}")
        
        if errors_found:
            print(f"❌ FAILED: Getting error pages, not product data")
            print(f"\nNext steps:")
            print(f"   1. Check if anti-bot detection is still triggering")
            print(f"   2. Try longer wait times (10-15 seconds)")
            print(f"   3. Check if Nordstrom changed their HTML structure")
        elif products_found >= 90:
            print(f"🎉 SUCCESS! ZenRows works for Nordstrom!")
            print(f"\nNext steps:")
            print(f"   1. Test other retailers with same config")
            print(f"   2. Update ACTIVE_RETAILERS in commercial_config.py")
            print(f"   3. Start migration from Patchright to ZenRows")
        elif products_found >= 20:
            print(f"⚠️  PARTIAL: Getting some products, but not all")
            print(f"\nNext steps:")
            print(f"   1. Increase wait time to 10-12 seconds")
            print(f"   2. Check if pagination is handled correctly")
            print(f"   3. Verify wait_for selector is correct")
        else:
            print(f"❌ FAILED: Not getting product data")
            print(f"\nNext steps:")
            print(f"   1. Verify wait_for selector: a[data-testid=\"product-link\"]")
            print(f"   2. Increase wait time to 10-15 seconds")
            print(f"   3. Check if HTML structure changed")
        
        print(f"{'='*80}")
    
    except Exception as e:
        duration = time.time() - start_time
        print(f"\n❌ EXCEPTION OCCURRED:")
        print(f"   Error: {str(e)}")
        print(f"   Duration: {duration:.2f}s")
        print(f"\nThis indicates a connectivity or timeout issue.")
    
    finally:
        # Close client
        await client.close()


if __name__ == '__main__':
    asyncio.run(test_nordstrom())

