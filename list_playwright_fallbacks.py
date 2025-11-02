#!/usr/bin/env python3
"""
Quick script to list all products that used Playwright fallback instead of markdown
"""
import sqlite3
import json
from datetime import datetime

db_path = "/Users/yav/Agent Modest Scraper System/Shared/products.db"

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Find all products that used playwright (fallback from markdown)
cursor.execute("""
    SELECT url, retailer, title, scraping_method, first_seen, shopify_id
    FROM products 
    WHERE scraping_method LIKE '%playwright%'
    ORDER BY first_seen DESC
""")

results = cursor.fetchall()

print(f"\n{'='*80}")
print(f"PLAYWRIGHT FALLBACK PRODUCTS (Total: {len(results)})")
print(f"{'='*80}\n")

if results:
    playwright_urls = []
    for i, (url, retailer, title, method, first_seen, shopify_id) in enumerate(results, 1):
        print(f"{i}. [{retailer}] {title[:60]}")
        print(f"   URL: {url}")
        print(f"   Method: {method}")
        print(f"   First Seen: {first_seen}")
        print(f"   Shopify ID: {shopify_id}")
        print()
        playwright_urls.append(url)
    
    # Generate batch file
    batch_file = f"/Users/yav/Agent Modest Scraper System/batch_playwright_fallbacks_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(batch_file, 'w') as f:
        json.dump({"urls": playwright_urls}, f, indent=2)
    
    print(f"\n✅ Batch file created: {batch_file}")
    print(f"   Contains {len(playwright_urls)} URLs that used Playwright fallback")
    print(f"\nYou can re-run these with the Product Updater after fixing the markdown cascade bug.")
else:
    print("No products found that used Playwright fallback.")

conn.close()
