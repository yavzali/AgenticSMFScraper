#!/usr/bin/env python3
"""
Phase 1: Validate Current Extraction for Aritzia
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Goal: Test all possible selectors on fetched HTML to determine if:
  A) We're missing products that ARE in the HTML (selector problem) → Easy fix!
  B) Products are NOT in HTML due to lazy loading (lazy load problem) → Phase 2
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Expected: 40+ products
Current: 23 products with selector 'a[href*="/product/"]'
"""

import asyncio
import sys
import os
from bs4 import BeautifulSoup
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from Extraction.CommercialAPI.commercial_api_client import get_client
from Extraction.CommercialAPI.commercial_config import CommercialAPIConfig


async def test_aritzia_selectors():
    """Test all possible CSS selectors on Aritzia HTML."""
    
    print("=" * 80)
    print("🔍 PHASE 1: ARITZIA SELECTOR VALIDATION")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Initialize ZenRows client
    config = CommercialAPIConfig()
    client = get_client(config)
    
    try:
        # Fetch HTML from Aritzia
        url = 'https://www.aritzia.com/us/en/clothing/dresses'
        print(f"📥 Fetching HTML from: {url}")
        print(f"⏱️  Using ZenRows with 30s wait time...\n")
        
        html = await client.fetch_html(url, 'aritzia', 'catalog')
        
        print(f"✅ HTML fetched successfully")
        print(f"📊 HTML size: {len(html):,} bytes ({len(html) / 1024 / 1024:.2f} MB)")
        print(f"📏 HTML length: {len(html):,} characters\n")
        
        # Parse with BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        
        # Define all possible selectors (from Patchright + alternatives)
        selectors = [
            # Current selector (what we're using now)
            ('a[href*="/product/"]', 'Current Selector (ZenRows)'),
            
            # Patchright backup selectors
            ('[data-product-id]', 'Patchright Backup #1'),
            ('a[class*="ProductCard"]', 'Patchright Backup #2'),
            
            # Generic product selectors
            ('div[class*="product"]', 'Generic: div[class*="product"]'),
            ('a[class*="product"]', 'Generic: a[class*="product"]'),
            
            # Full path variations
            ('a[href*="/us/en/product/"]', 'Full Path (country + product)'),
            ('a[href^="/us/en/product/"]', 'Starts with /us/en/product/'),
            
            # Alternative class-based
            ('[class*="tile"]', 'Generic: tile classes'),
            ('[class*="card"]', 'Generic: card classes'),
            
            # Data attribute alternatives
            ('[data-productid]', 'data-productid (lowercase)'),
            ('[data-product]', 'data-product (partial)'),
        ]
        
        print("=" * 80)
        print("🧪 TESTING ALL SELECTORS")
        print("=" * 80)
        print(f"{'Selector':<50} {'Type':<30} {'Products':<10}")
        print("-" * 80)
        
        results = []
        max_products = 0
        best_selector = None
        
        for selector, description in selectors:
            try:
                elements = soup.select(selector)
                unique_urls = set()
                
                for elem in elements:
                    # Handle both direct links and parent containers
                    if elem.name == 'a':
                        href = elem.get('href')
                        if href and '/product/' in href:
                            # Normalize URL
                            if href.startswith('http'):
                                unique_urls.add(href)
                            else:
                                unique_urls.add(f"https://www.aritzia.com{href}")
                    else:
                        # Find links within container
                        link = elem.find('a', href=lambda x: x and '/product/' in x)
                        if link:
                            href = link.get('href')
                            if href.startswith('http'):
                                unique_urls.add(href)
                            else:
                                unique_urls.add(f"https://www.aritzia.com{href}")
                
                product_count = len(unique_urls)
                results.append((selector, description, product_count, unique_urls))
                
                # Track best performer
                if product_count > max_products:
                    max_products = product_count
                    best_selector = description
                
                # Color code output
                if product_count >= 40:
                    status = f"✅ {product_count}"
                elif product_count >= 23:
                    status = f"⚠️  {product_count}"
                else:
                    status = f"❌ {product_count}"
                
                print(f"{selector:<50} {description:<30} {status:<10}")
                
            except Exception as e:
                print(f"{selector:<50} {description:<30} ❌ ERROR: {str(e)[:30]}")
        
        print("-" * 80)
        print(f"\n📊 SUMMARY:")
        print(f"   Max products found: {max_products}")
        print(f"   Best selector: {best_selector}")
        print(f"   Target: 40+ products\n")
        
        # Diagnosis
        print("=" * 80)
        print("🔬 DIAGNOSIS")
        print("=" * 80)
        
        if max_products >= 40:
            print("✅ SELECTOR PROBLEM (EASY FIX!)")
            print(f"   → HTML contains {max_products} products")
            print(f"   → Current selector only finding {results[0][2]} products")
            print(f"   → Switch to: {best_selector}")
            print("\n🎯 NEXT STEP: Update selector in commercial_retailer_strategies.py")
            
        elif max_products >= 30:
            print("⚠️  PARTIAL SELECTOR ISSUE")
            print(f"   → HTML contains {max_products} products (close to target)")
            print(f"   → Current selector finding {results[0][2]} products")
            print(f"   → Might be both selector + lazy loading issue")
            print("\n🎯 NEXT STEP: Update selector AND try Phase 2 (custom JS)")
            
        else:
            print("❌ LAZY LOADING PROBLEM (COMPLEX)")
            print(f"   → HTML only contains {max_products} products (need 40+)")
            print(f"   → All selectors finding similar counts")
            print(f"   → Products NOT in HTML (loaded dynamically)")
            print("\n🎯 NEXT STEP: Phase 2 - Test ZenRows custom JavaScript")
        
        # Show sample URLs from best selector
        print("\n" + "=" * 80)
        print("📝 SAMPLE PRODUCT URLS (from best selector)")
        print("=" * 80)
        
        if max_products > 0:
            best_result = max(results, key=lambda x: x[2])
            sample_urls = list(best_result[3])[:5]
            for i, url in enumerate(sample_urls, 1):
                print(f"{i}. {url}")
        else:
            print("❌ No product URLs found")
        
        # Show HTML snippet for debugging
        print("\n" + "=" * 80)
        print("📄 HTML SNIPPET (first 500 chars)")
        print("=" * 80)
        print(html[:500])
        print("...")
        
        # Search for specific keywords in HTML
        print("\n" + "=" * 80)
        print("🔍 KEYWORD SEARCH IN HTML")
        print("=" * 80)
        
        keywords = [
            'product',
            'data-product',
            'ProductCard',
            '/product/',
            'lazy',
            'pagination',
            'load-more'
        ]
        
        for keyword in keywords:
            count = html.lower().count(keyword.lower())
            print(f"   '{keyword}': {count} occurrences")
        
    finally:
        await client.close()
    
    print("\n" + "=" * 80)
    print("🏁 PHASE 1 COMPLETE")
    print("=" * 80)


if __name__ == '__main__':
    asyncio.run(test_aritzia_selectors())

