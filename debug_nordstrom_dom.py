"""
Debug script to inspect Nordstrom's actual DOM structure
"""

import asyncio
from patchright.async_api import async_playwright
import json

async def inspect_nordstrom():
    """Launch browser and inspect Nordstrom catalog page"""
    
    url = "https://www.nordstrom.com/browse/women/clothing/dresses"
    
    print(f"\n{'='*70}")
    print("NORDSTROM DOM STRUCTURE INSPECTOR")
    print(f"{'='*70}\n")
    print(f"URL: {url}\n")
    
    playwright = await async_playwright().start()
    
    try:
        # Launch browser
        browser = await playwright.chromium.launch_persistent_context(
            user_data_dir="/Users/yav/Agent Modest Scraper System/Shared/browser_profiles/default",
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-features=IsolateOrigins,site-per-process'
            ],
            ignore_default_args=['--enable-automation'],
            viewport={'width': 1920, 'height': 1080}
        )
        
        page = await browser.new_page()
        
        print("🌐 Navigating to page...")
        await page.goto(url, wait_until='domcontentloaded', timeout=60000)
        
        print("⏱️  Waiting for page to load...")
        await asyncio.sleep(10)
        
        print("\n📋 TESTING SELECTORS:\n")
        
        # Test various selectors
        selectors_to_test = [
            "a[class*='product-card']",
            "a[href*='/product']",
            "a[href*='/s/']",
            "a[data-testid*='product']",
            "[data-product-id]",
            ".product-card",
            ".product-tile",
            "article a",
            "div[data-testid*='product'] a",
            "a[aria-label*='dress' i]",
            "a[aria-label*='product' i]",
        ]
        
        results = {}
        
        for selector in selectors_to_test:
            try:
                elements = await page.query_selector_all(selector)
                count = len(elements)
                
                if count > 0:
                    # Get first few hrefs as examples
                    hrefs = []
                    for i, el in enumerate(elements[:3]):
                        try:
                            href = await el.get_attribute('href')
                            if not href:
                                href = await el.evaluate('el => el.href')
                            hrefs.append(href if href else 'None')
                        except:
                            hrefs.append('Error')
                    
                    results[selector] = {
                        'count': count,
                        'examples': hrefs
                    }
                    print(f"✅ {selector:50} → {count:3} elements")
                    for href in hrefs:
                        print(f"   └─ {href[:80] if href else 'None'}")
                else:
                    print(f"❌ {selector:50} → 0 elements")
            except Exception as e:
                print(f"⚠️  {selector:50} → Error: {e}")
        
        # Save results
        with open('/tmp/nordstrom_selector_results.json', 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n{'='*70}")
        print("RECOMMENDATIONS:")
        print(f"{'='*70}\n")
        
        # Find best selector
        best_selector = None
        best_count = 0
        
        for selector, data in results.items():
            if data['count'] > best_count and data['count'] < 200:  # Not too many
                best_count = data['count']
                best_selector = selector
        
        if best_selector:
            print(f"✅ BEST SELECTOR: {best_selector}")
            print(f"   Found {best_count} products")
            print(f"\n   Update patchright_retailer_strategies.py:")
            print(f"   'nordstrom': {{")
            print(f"       'product_selectors': ['{best_selector}'],")
            print(f"       ...")
            print(f"   }}")
        else:
            print("❌ No suitable selectors found")
            print("   Nordstrom may have changed their page structure")
            print("   or anti-bot measures are blocking DOM access")
        
        print(f"\n{'='*70}")
        print(f"✅ Results saved to: /tmp/nordstrom_selector_results.json")
        print(f"{'='*70}\n")
        
        # Keep browser open for manual inspection
        print("🔍 Browser window left open for manual inspection")
        print("   Press Ctrl+C when done inspecting...")
        
        try:
            await asyncio.sleep(3600)  # Wait 1 hour
        except KeyboardInterrupt:
            print("\n👋 Closing browser...")
        
        await browser.close()
        
    finally:
        await playwright.stop()

if __name__ == "__main__":
    asyncio.run(inspect_nordstrom())

