#!/usr/bin/env python3
"""
Update Dress Tops Tags - Fix products that were wrongly tagged as "Dress"

This script updates products that should have:
- Product Type: "Dress Tops" (instead of "Dresses")
- Tag: "Dress Top" (instead of "Dress")

Targets:
- Batch 2: Modest Dress Tops (38 products from batch_modest_dress_tops.json)
- Batch 4: Moderately Modest Dress Tops (20 products from batch_moderately_modest_dress_tops.json)

Method:
- Loads URLs from batch files
- Matches products in Shopify by source URL metafield
- Updates only products from these specific batches
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

import asyncio
import aiohttp
import json
from datetime import datetime
from typing import List, Dict, Any, Set
from dotenv import load_dotenv
from urllib.parse import urlparse, parse_qs

from logger_config import setup_logging

logger = setup_logging(__name__)

class DressTopsUpdater:
    def __init__(self):
        # Load environment variables
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.join(script_dir, '..')
        env_path = os.path.join(project_root, '.env')
        load_dotenv(env_path, override=True)
        
        # Load Shopify credentials
        self.store_url = os.getenv('SHOPIFY_STORE_URL')
        self.access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
        
        if not self.store_url or not self.access_token:
            raise ValueError("Missing Shopify credentials in .env file")
        
        self.api_version = '2023-10'
        self.base_api_url = f"https://{self.store_url}/admin/api/{self.api_version}"
        self.headers = {
            'X-Shopify-Access-Token': self.access_token,
            'Content-Type': 'application/json'
        }
        
        # Load dress tops URLs from batch files
        self.dress_tops_urls = self._load_dress_tops_urls()
        
        logger.info(f"✅ DressTopsUpdater initialized for store: {self.store_url}")
        logger.info(f"   Loaded {len(self.dress_tops_urls)} dress tops URLs from batch files")
    
    def _load_dress_tops_urls(self) -> Set[str]:
        """Load URLs from the two dress tops batch files"""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.join(script_dir, '..')
        baseline_dir = os.path.join(project_root, 'Baseline URLs')
        
        urls = set()
        
        batch_files = [
            'batch_modest_dress_tops.json',
            'batch_moderately_modest_dress_tops.json'
        ]
        
        for batch_file in batch_files:
            batch_path = os.path.join(baseline_dir, batch_file)
            try:
                with open(batch_path, 'r') as f:
                    data = json.load(f)
                    batch_urls = data.get('urls', [])
                    # Normalize URLs by extracting product code
                    for url in batch_urls:
                        product_code = self._extract_product_code(url)
                        if product_code:
                            urls.add(product_code)
                    logger.info(f"   Loaded {len(batch_urls)} URLs from {batch_file}")
            except Exception as e:
                logger.error(f"Error loading {batch_file}: {e}")
        
        return urls
    
    def _extract_product_code(self, url: str) -> str:
        """Extract product code from Revolve URL (e.g., DEBY-WD49)"""
        try:
            parsed = urlparse(url)
            path_parts = parsed.path.strip('/').split('/')
            # Product code is in the path like: /deme-by-gabriella.../dp/DEBY-WD49/
            if 'dp' in path_parts:
                dp_index = path_parts.index('dp')
                if dp_index + 1 < len(path_parts):
                    return path_parts[dp_index + 1]
        except Exception as e:
            logger.debug(f"Could not extract product code from {url}: {e}")
        return None
    
    async def get_all_products(self) -> List[Dict]:
        """Fetch all products from Shopify"""
        all_products = []
        
        async with aiohttp.ClientSession() as session:
            url = f"{self.base_api_url}/products.json?limit=250"
            
            while url:
                async with session.get(url, headers=self.headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Failed to fetch products: {response.status} - {error_text}")
                        break
                    
                    data = await response.json()
                    products = data.get('products', [])
                    all_products.extend(products)
                    
                    logger.info(f"Fetched {len(products)} products (total: {len(all_products)})")
                    
                    # Check for pagination
                    link_header = response.headers.get('Link', '')
                    if 'rel="next"' in link_header:
                        # Extract next URL from Link header
                        next_link = [link.split(';')[0].strip('<> ') for link in link_header.split(',') if 'rel="next"' in link]
                        url = next_link[0] if next_link else None
                    else:
                        url = None
        
        return all_products
    
    async def get_product_metafields(self, session: aiohttp.ClientSession, product_id: int) -> Dict:
        """Fetch metafields for a product to get source URL and product code"""
        try:
            async with session.get(
                f"{self.base_api_url}/products/{product_id}/metafields.json",
                headers=self.headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    metafields = data.get('metafields', [])
                    result = {}
                    
                    for metafield in metafields:
                        # Find source_urls (inventory namespace)
                        if metafield.get('namespace') == 'inventory' and metafield.get('key') == 'source_urls':
                            try:
                                source_urls = json.loads(metafield.get('value', '[]'))
                                if source_urls:
                                    result['source_url'] = source_urls[0]  # Take first URL
                            except:
                                pass
                        
                        # Find product_id (custom namespace)
                        if metafield.get('namespace') == 'custom' and metafield.get('key') == 'product_id':
                            try:
                                product_ids = json.loads(metafield.get('value', '[]'))
                                if product_ids:
                                    result['product_code'] = product_ids[0]  # Take first code
                            except:
                                pass
                    
                    return result
                return {}
        except Exception as e:
            logger.debug(f"Error fetching metafields for product {product_id}: {e}")
            return {}
    
    async def identify_dress_tops_products(self, all_products: List[Dict], session: aiohttp.ClientSession) -> List[Dict]:
        """Identify products that need updating based on source URLs from batch files"""
        dress_tops_products = []
        
        logger.info("Checking products against batch file URLs...")
        
        for i, product in enumerate(all_products, 1):
            if i % 10 == 0:
                logger.info(f"  Checked {i}/{len(all_products)} products...")
            
            tags = [tag.strip() for tag in product.get('tags', '').split(',') if tag.strip()]
            product_type = product.get('product_type', '')
            
            # Only check products with wrong tags/type
            has_wrong_dress_tag = 'Dress' in tags and 'Dress Top' not in tags
            has_wrong_product_type = product_type == 'Dresses'
            
            if not (has_wrong_dress_tag and has_wrong_product_type):
                continue
            
            # Get metafields to check product code and source URL
            metafields = await self.get_product_metafields(session, product['id'])
            product_code = metafields.get('product_code')
            source_url = metafields.get('source_url')
            
            # Match by product code from metafield
            if product_code and product_code in self.dress_tops_urls:
                modesty_level = 'Modest' if 'Modest' in tags else 'Moderately Modest' if 'Moderately Modest' in tags else 'Unknown'
                dress_tops_products.append({
                    'id': product['id'],
                    'title': product['title'],
                    'current_product_type': product_type,
                    'current_tags': tags,
                    'modesty_level': modesty_level,
                    'source_url': source_url or 'N/A',
                    'product_code': product_code
                })
        
        return dress_tops_products
    
    async def update_product(self, product_info: Dict, dry_run: bool = False) -> bool:
        """Update a single product with correct tags and product type"""
        product_id = product_info['id']
        current_tags = product_info['current_tags']
        
        # Remove "Dress" tag and add "Dress Top" tag
        new_tags = [tag for tag in current_tags if tag != 'Dress']
        if 'Dress Top' not in new_tags:
            new_tags.append('Dress Top')
        
        update_payload = {
            'product': {
                'id': product_id,
                'product_type': 'Dress Tops',
                'tags': ', '.join(new_tags)
            }
        }
        
        if dry_run:
            logger.info(f"[DRY RUN] Would update product {product_id}:")
            logger.info(f"  Title: {product_info['title']}")
            logger.info(f"  Product Code: {product_info.get('product_code', 'N/A')}")
            logger.info(f"  Modesty: {product_info.get('modesty_level', 'Unknown')}")
            logger.info(f"  Product Type: {product_info['current_product_type']} → Dress Tops")
            logger.info(f"  Tags: {', '.join(current_tags)} → {', '.join(new_tags)}")
            return True
        
        async with aiohttp.ClientSession() as session:
            async with session.put(
                f"{self.base_api_url}/products/{product_id}.json",
                headers=self.headers,
                data=json.dumps(update_payload)
            ) as response:
                if response.status == 200:
                    logger.info(f"✅ Updated product {product_id}: {product_info['title']}")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Failed to update product {product_id}: {response.status} - {error_text}")
                    return False
    
    async def run(self, dry_run: bool = True):
        """Main execution flow"""
        logger.info("=" * 80)
        logger.info("DRESS TOPS TAG UPDATE (URL-MATCHED)")
        logger.info("=" * 80)
        logger.info(f"Mode: {'DRY RUN' if dry_run else 'LIVE UPDATE'}")
        logger.info(f"Target URLs: {len(self.dress_tops_urls)} product codes from batch files")
        logger.info("")
        
        # Fetch all products
        logger.info("Fetching all products from Shopify...")
        all_products = await self.get_all_products()
        logger.info(f"Total products in Shopify: {len(all_products)}")
        logger.info("")
        
        # Identify dress tops products by matching URLs
        logger.info("Identifying dress tops products by matching source URLs...")
        async with aiohttp.ClientSession() as session:
            dress_tops_products = await self.identify_dress_tops_products(all_products, session)
        logger.info(f"Found {len(dress_tops_products)} products matching dress tops batch URLs")
        logger.info("")
        
        if not dress_tops_products:
            logger.info("✅ No products need updating!")
            return
        
        # Show breakdown by modesty level
        modest_count = sum(1 for p in dress_tops_products if p['modesty_level'] == 'Modest')
        moderately_modest_count = sum(1 for p in dress_tops_products if p['modesty_level'] == 'Moderately Modest')
        
        logger.info("Breakdown:")
        logger.info(f"  Modest Dress Tops: {modest_count}")
        logger.info(f"  Moderately Modest Dress Tops: {moderately_modest_count}")
        logger.info("")
        
        if dry_run:
            logger.info("=" * 80)
            logger.info("DRY RUN - Showing what would be updated:")
            logger.info("=" * 80)
        
        # Update products
        success_count = 0
        failed_count = 0
        
        for i, product_info in enumerate(dress_tops_products, 1):
            logger.info(f"\n[{i}/{len(dress_tops_products)}]")
            success = await self.update_product(product_info, dry_run)
            if success:
                success_count += 1
            else:
                failed_count += 1
            
            # Small delay to be respectful to API
            if not dry_run:
                await asyncio.sleep(0.5)
        
        # Summary
        logger.info("")
        logger.info("=" * 80)
        logger.info("SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total identified: {len(dress_tops_products)}")
        logger.info(f"Successfully {'simulated' if dry_run else 'updated'}: {success_count}")
        if failed_count > 0:
            logger.info(f"Failed: {failed_count}")
        
        if dry_run:
            logger.info("")
            logger.info("⚠️  This was a DRY RUN - no changes were made")
            logger.info("   To apply changes, run with --live flag")

async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Update Dress Tops products with correct tags")
    parser.add_argument('--live', action='store_true', help='Actually update products (default is dry run)')
    args = parser.parse_args()
    
    updater = DressTopsUpdater()
    await updater.run(dry_run=not args.live)

if __name__ == "__main__":
    asyncio.run(main())

