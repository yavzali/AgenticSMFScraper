"""
Update Product Tags Script - Fix Tag Formatting to Title Case
Fixes existing products with lowercase tags to use proper title case.
"""

import asyncio
import aiohttp
import json
import os
import sys
from datetime import datetime
from typing import List, Dict, Any
from dotenv import load_dotenv

# Load environment variables
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)

# Shopify configuration
SHOPIFY_STORE_URL = os.getenv('SHOPIFY_STORE_URL')
SHOPIFY_ACCESS_TOKEN = os.getenv('SHOPIFY_ACCESS_TOKEN')
SHOPIFY_API_VERSION = '2023-10'
SHOPIFY_API_BASE = f'https://{SHOPIFY_STORE_URL}/admin/api/{SHOPIFY_API_VERSION}'

# Tag mapping: old lowercase -> new title case
TAG_MAPPING = {
    # Modesty levels
    'modest': 'Modest',
    'moderately modest': 'Moderately Modest',
    'moderately_modest': 'Moderately Modest',
    'not modest': 'Not Modest',
    'not_modest': 'Not Modest',
    'pending review': 'Pending Review',
    'pending_review': 'Pending Review',
    
    # Retailers
    'revolve': 'Revolve',
    'asos': 'Asos',
    'aritzia': 'Aritzia',
    'anthropologie': 'Anthropologie',
    'uniqlo': 'Uniqlo',
    'h&m': 'H&M',
    'hm': 'H&M',
    'mango': 'Mango',
    'abercrombie': 'Abercrombie',
    'nordstrom': 'Nordstrom',
    'urban outfitters': 'Urban Outfitters',
    'urban_outfitters': 'Urban Outfitters',
    
    # Clothing types
    'dress': 'Dress',
    'dresses': 'Dresses',
    'top': 'Top',
    'tops': 'Tops',
    'dress top': 'Dress Top',
    'dress tops': 'Dress Tops',
    'dress-top': 'Dress Top',
    'dress-tops': 'Dress Tops',
    'bottom': 'Bottom',
    'bottoms': 'Bottoms',
    'skirt': 'Skirt',
    'pants': 'Pants',
    'jeans': 'Jeans',
    
    # System tags
    'auto-scraped': 'Auto-Scraped',
    'auto scraped': 'Auto-Scraped',
    
    # Sale tags
    'on-sale': 'On-Sale',
    'on sale': 'On-Sale',
    
    # Stock status
    'in stock': 'In-Stock',
    'in_stock': 'In-Stock',
    'low in stock': 'Low-In-Stock',
    'low_in_stock': 'Low-In-Stock',
    'out of stock': 'Out-Of-Stock',
    'out_of_stock': 'Out-Of-Stock',
}


class TagUpdater:
    def __init__(self):
        self.headers = {
            'X-Shopify-Access-Token': SHOPIFY_ACCESS_TOKEN,
            'Content-Type': 'application/json'
        }
        self.updated_count = 0
        self.skipped_count = 0
        self.error_count = 0
        self.results = []
    
    async def get_all_products(self, session: aiohttp.ClientSession, limit: int = 250) -> List[Dict]:
        """Fetch all products from Shopify"""
        all_products = []
        url = f"{SHOPIFY_API_BASE}/products.json?limit={limit}"
        
        while url:
            async with session.get(url, headers=self.headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    print(f"❌ Error fetching products: {response.status} - {error_text}")
                    break
                
                data = await response.json()
                products = data.get('products', [])
                all_products.extend(products)
                
                print(f"📦 Fetched {len(products)} products (total: {len(all_products)})")
                
                # Check for pagination
                link_header = response.headers.get('Link', '')
                if 'rel="next"' in link_header:
                    # Extract next URL from Link header
                    next_link = [l for l in link_header.split(',') if 'rel="next"' in l]
                    if next_link:
                        url = next_link[0].split(';')[0].strip('<> ')
                    else:
                        url = None
                else:
                    url = None
        
        return all_products
    
    def normalize_tags(self, tags_string: str) -> List[str]:
        """Convert tag string to normalized list and update to title case"""
        if not tags_string:
            return []
        
        # Split tags
        current_tags = [tag.strip() for tag in tags_string.split(',') if tag.strip()]
        
        # Update tags using mapping
        updated_tags = []
        changed = False
        
        for tag in current_tags:
            tag_lower = tag.lower()
            
            # Check if tag needs updating
            if tag_lower in TAG_MAPPING:
                new_tag = TAG_MAPPING[tag_lower]
                if new_tag != tag:
                    changed = True
                updated_tags.append(new_tag)
            else:
                # Keep tag as is if no mapping exists
                updated_tags.append(tag)
        
        return updated_tags, changed
    
    async def update_product_tags(self, session: aiohttp.ClientSession, product: Dict) -> Dict:
        """Update a single product's tags"""
        product_id = product['id']
        product_title = product['title']
        current_tags_string = product.get('tags', '')
        
        # Normalize and update tags
        updated_tags, changed = self.normalize_tags(current_tags_string)
        
        if not changed:
            self.skipped_count += 1
            return {
                'product_id': product_id,
                'title': product_title,
                'status': 'skipped',
                'reason': 'tags already correct'
            }
        
        # Update product
        updated_tags_string = ', '.join(updated_tags)
        payload = {
            "product": {
                "id": product_id,
                "tags": updated_tags_string
            }
        }
        
        try:
            async with session.put(
                f"{SHOPIFY_API_BASE}/products/{product_id}.json",
                headers=self.headers,
                data=json.dumps(payload)
            ) as response:
                if response.status == 200:
                    self.updated_count += 1
                    print(f"✅ Updated: {product_title}")
                    print(f"   Old tags: {current_tags_string}")
                    print(f"   New tags: {updated_tags_string}")
                    return {
                        'product_id': product_id,
                        'title': product_title,
                        'status': 'updated',
                        'old_tags': current_tags_string,
                        'new_tags': updated_tags_string
                    }
                else:
                    self.error_count += 1
                    error_text = await response.text()
                    print(f"❌ Error updating {product_title}: {response.status} - {error_text}")
                    return {
                        'product_id': product_id,
                        'title': product_title,
                        'status': 'error',
                        'error': error_text
                    }
        except Exception as e:
            self.error_count += 1
            print(f"❌ Exception updating {product_title}: {e}")
            return {
                'product_id': product_id,
                'title': product_title,
                'status': 'error',
                'error': str(e)
            }
    
    async def run(self, dry_run: bool = False):
        """Main execution"""
        print("🏷️  Tag Update Script - Title Case Formatting")
        print("=" * 60)
        print(f"Store: {SHOPIFY_STORE_URL}")
        print(f"Mode: {'DRY RUN (no changes)' if dry_run else 'LIVE UPDATE'}")
        print("=" * 60)
        print()
        
        async with aiohttp.ClientSession() as session:
            # Fetch all products
            print("📦 Fetching all products...")
            products = await self.get_all_products(session)
            print(f"✅ Found {len(products)} total products")
            print()
            
            # Filter products that need updating
            products_to_update = []
            for product in products:
                tags_string = product.get('tags', '')
                _, needs_update = self.normalize_tags(tags_string)
                if needs_update:
                    products_to_update.append(product)
            
            print(f"🔍 Found {len(products_to_update)} products needing tag updates")
            print()
            
            if dry_run:
                print("DRY RUN - Showing what would be updated:")
                print("-" * 60)
                for product in products_to_update[:10]:  # Show first 10
                    current_tags = product.get('tags', '')
                    updated_tags, _ = self.normalize_tags(current_tags)
                    print(f"📦 {product['title']}")
                    print(f"   Current: {current_tags}")
                    print(f"   Updated: {', '.join(updated_tags)}")
                    print()
                
                if len(products_to_update) > 10:
                    print(f"... and {len(products_to_update) - 10} more products")
                
                print("\nTo apply these changes, run without --dry-run flag")
                return
            
            # Update products
            if not products_to_update:
                print("✅ All products already have correct tags!")
                return
            
            print(f"🔄 Updating {len(products_to_update)} products...")
            print()
            
            for product in products_to_update:
                result = await self.update_product_tags(session, product)
                self.results.append(result)
                
                # Small delay to respect rate limits
                await asyncio.sleep(0.5)
            
            # Summary
            print()
            print("=" * 60)
            print("📊 SUMMARY")
            print("=" * 60)
            print(f"✅ Updated: {self.updated_count}")
            print(f"⏭️  Skipped: {self.skipped_count}")
            print(f"❌ Errors: {self.error_count}")
            print(f"📦 Total: {len(products_to_update)}")
            print()
            
            # Save results
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            results_file = f"tag_update_results_{timestamp}.json"
            with open(results_file, 'w') as f:
                json.dump({
                    'timestamp': timestamp,
                    'total_products': len(products),
                    'products_updated': self.updated_count,
                    'products_skipped': self.skipped_count,
                    'products_error': self.error_count,
                    'results': self.results
                }, f, indent=2)
            
            print(f"📝 Results saved to: {results_file}")


async def main():
    """Main entry point"""
    dry_run = '--dry-run' in sys.argv
    
    updater = TagUpdater()
    await updater.run(dry_run=dry_run)


if __name__ == '__main__':
    asyncio.run(main())

