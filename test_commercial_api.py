#!/usr/bin/env python3
"""
Isolated Test for Commercial API Tower (Bright Data + BeautifulSoup)

Tests WITHOUT:
- Database writes
- Patchright fallback
- Workflow integration

Tests WITH:
- Bright Data HTML fetching
- BeautifulSoup parsing
- CSS selector extraction
- Detailed logging at each step
"""

import asyncio
import sys
import os

# Add paths
sys.path.append(os.path.join(os.path.dirname(__file__), "Shared"))
sys.path.append(os.path.join(os.path.dirname(__file__), "Extraction/CommercialAPI"))

from Shared.logger_config import setup_logging
from commercial_config import CommercialAPIConfig
from brightdata_client import BrightDataClient
from html_cache_manager import HTMLCacheManager
from commercial_retailer_strategies import CommercialRetailerStrategies
from bs4 import BeautifulSoup

logger = setup_logging(__name__)


async def test_commercial_api_tower():
    """Test Commercial API Tower end-to-end"""
    import time
    test_start = time.time()
    
    print("=" * 80)
    print("🧪 COMMERCIAL API TOWER - ISOLATED TEST (REVOLVE DIAGNOSTIC)")
    print("=" * 80)
    print()
    
    # Test configuration - USING REVOLVE (No anti-bot, easiest retailer)
    retailer = "revolve"
    category = "dresses"
    test_url = "https://www.revolve.com/dresses/br/a8e981/?navsrc=subDresses&sortBy=newest&vnitems=length_and_midi&vnitems=length_and_maxi&vnitems=cut_and_straight&vnitems=cut_and_flared&vnitems=neckline_and_jewel-neck&vnitems=neckline_and_bardot-neck&vnitems=neckline_and_collar&vnitems=neckline_and_v-neck&vnitems=neckline_and_turtleneck&vnitems=sleeve_and_long&vnitems=sleeve_and_3_4&loadVisNav=true&pageNumVisNav=1"
    
    print(f"📋 Test Configuration:")
    print(f"   Retailer: {retailer}")
    print(f"   Category: {category}")
    print(f"   URL: {test_url[:80]}...")
    print()
    
    # Step 1: Verify configuration
    print("=" * 80)
    print("STEP 1: Verify Configuration")
    print("=" * 80)
    
    config = CommercialAPIConfig()
    print(f"✅ BRIGHTDATA_USERNAME: {config.BRIGHTDATA_USERNAME[:30]}...")
    print(f"✅ BRIGHTDATA_PASSWORD: {'*' * len(config.BRIGHTDATA_PASSWORD)}")
    print(f"✅ PROXY_HOST: {config.BRIGHTDATA_PROXY_HOST}")
    print(f"✅ PROXY_PORT: {config.BRIGHTDATA_PROXY_PORT}")
    print(f"✅ ACTIVE_RETAILERS: {config.ACTIVE_RETAILERS}")
    print(f"✅ should_use_commercial_api('{retailer}'): {config.should_use_commercial_api(retailer)}")
    print()
    
    # Step 2: Test Bright Data Connection
    print("=" * 80)
    print("STEP 2: Test Bright Data HTML Fetch")
    print("=" * 80)
    
    brightdata = BrightDataClient()
    html_cache = HTMLCacheManager()
    await html_cache.initialize()
    
    # Check cache first
    cached_html = await html_cache.get(test_url, retailer)
    
    if cached_html:
        print(f"💾 Using cached HTML ({len(cached_html):,} bytes)")
        html = cached_html
    else:
        print("🌐 Fetching HTML from Bright Data...")
        try:
            html = await brightdata.fetch_html(test_url, retailer, 'catalog')
            print(f"✅ SUCCESS! Fetched {len(html):,} bytes")
            
            # Cache it
            await html_cache.set(test_url, retailer, html)
            print("💾 Cached HTML for future tests")
            
            # Show stats
            stats = brightdata.get_usage_stats()
            print(f"\n📊 Bright Data Stats:")
            print(f"   Requests: {stats['total_requests']}")
            print(f"   Success Rate: {stats['success_rate']*100:.1f}%")
            print(f"   Cost: ${stats['total_cost']:.4f}")
            
        except Exception as e:
            print(f"❌ FAILED: {e}")
            await brightdata.close()
            return
    
    print()
    
    # Step 3: Show HTML sample
    print("=" * 80)
    print("STEP 3: HTML Content Sample")
    print("=" * 80)
    
    print(f"HTML Size: {len(html):,} bytes")
    print()
    print(f"First 500 characters:")
    print(html[:500])
    print()
    print(f"HTML contains '{retailer}': {(retailer in html.lower())}")
    print(f"HTML contains 'product': {('product' in html.lower())}")
    print(f"HTML contains 'dress': {('dress' in html.lower())}")
    print(f"HTML contains '/dp/' (Revolve product URLs): {('/dp/' in html)}")
    print(f"HTML contains 'revolveassets' (Revolve images): {('revolveassets' in html.lower())}")
    print()
    
    # Step 4: Test BeautifulSoup Parsing
    print("=" * 80)
    print("STEP 4: BeautifulSoup Parsing")
    print("=" * 80)
    
    print("Parsing HTML with BeautifulSoup...")
    soup = BeautifulSoup(html, 'html.parser')
    print(f"✅ Parsed successfully")
    print(f"   Total elements: {len(soup.find_all())}")
    print()
    
    # Step 5: Test CSS Selectors
    print("=" * 80)
    print("STEP 5: Test CSS Selectors for Nordstrom Catalog")
    print("=" * 80)
    
    strategies = CommercialRetailerStrategies()
    
    # Get Nordstrom catalog selectors
    if retailer.lower() not in strategies.CATALOG_SELECTORS:
        print(f"❌ No catalog selectors defined for {retailer}")
        await brightdata.close()
        return
    
    selectors = strategies.CATALOG_SELECTORS[retailer.lower()]
    
    print(f"📋 Testing {retailer.upper()} catalog selectors:")
    print()
    
    # Test each selector type
    for field, selector_list in selectors.items():
        print(f"   {field}:")
        for selector in selector_list:
            elements = soup.select(selector)
            print(f"      '{selector}' → Found {len(elements)} elements")
            if elements and len(elements) <= 5:
                for i, elem in enumerate(elements[:5], 1):
                    text = elem.get_text(strip=True)[:60]
                    href = elem.get('href', 'N/A')[:80] if field == 'product_links' else 'N/A'
                    print(f"         [{i}] {text} | {href}")
        print()
    
    # Step 6: Attempt Full Extraction
    print("=" * 80)
    print("STEP 6: Full Catalog Extraction")
    print("=" * 80)
    
    print("Extracting products using CommercialRetailerStrategies...")
    catalog_products = strategies.extract_catalog(soup, retailer)
    
    print(f"✅ Extracted {len(catalog_products)} products")
    print()
    
    if catalog_products:
        print("📦 Sample Products (first 5):")
        for i, product in enumerate(catalog_products[:5], 1):
            print(f"\n   Product {i}:")
            print(f"      URL: {product.get('url', 'N/A')[:80]}")
            print(f"      Title: {product.get('title', 'N/A')[:60]}")
            print(f"      Price: {product.get('price', 'N/A')}")
    else:
        print("⚠️  No products extracted!")
        print("\n🔍 Debugging Tips:")
        print("   1. Check if CSS selectors match current Nordstrom HTML structure")
        print("   2. Inspect HTML sample above for actual element classes/IDs")
        print("   3. Update selectors in commercial_retailer_strategies.py")
    
    print()
    
    # Cleanup
    await brightdata.close()
    
    test_duration = time.time() - test_start
    
    print()
    print("=" * 80)
    print("✅ TEST COMPLETE")
    print("=" * 80)
    print(f"⏱️  Total test duration: {test_duration:.2f} seconds")
    print(f"📊 Products extracted: {len(catalog_products)}")
    print()


if __name__ == "__main__":
    asyncio.run(test_commercial_api_tower())

