#!/usr/bin/env python3
"""
Disposable script to delete 5 Anthropologie test products
Created: Nov 13, 2024
Purpose: Clean up test products from Anthropologie import test
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "Shared"))

import asyncio
import aiohttp
from dotenv import load_dotenv
from db_manager import DatabaseManager
from logger_config import setup_logging

logger = setup_logging(__name__)
load_dotenv()

# Test product IDs from Anthropologie test run (Nov 13, 03:10-03:15)
TEST_PRODUCT_IDS = [
    14836307427698,  # Reformation Tommie Knit Dress
    14836309197170,  # The Bettina Tiered Shirt Dress by Maeve
    14836311032178,  # De La Vali Daira Mock-Neck Ruffle Long-Sleeve Bias-Cut Maxi Dress
    14836312932722,  # Farm Rio Deco Jersey Long-Sleeve Mock-Neck Midi Dress
    14836314734962,  # By Anthropologie Long-Sleeve Turtleneck Belted Sweater Midi Dress
]

async def delete_from_shopify(shopify_ids, store_url, access_token):
    """Delete products from Shopify"""
    
    headers = {
        'Content-Type': 'application/json',
        'X-Shopify-Access-Token': access_token
    }
    
    base_url = f"https://{store_url}/admin/api/2025-01"
    
    deleted = 0
    failed = 0
    
    async with aiohttp.ClientSession() as session:
        for shopify_id in shopify_ids:
            try:
                url = f"{base_url}/products/{shopify_id}.json"
                async with session.delete(url, headers=headers) as response:
                    if response.status == 200:
                        deleted += 1
                        logger.info(f"✅ Deleted from Shopify: {shopify_id}")
                    else:
                        failed += 1
                        text = await response.text()
                        logger.warning(f"❌ Failed to delete {shopify_id}: {response.status} - {text}")
                
                await asyncio.sleep(0.5)  # Rate limiting
                
            except Exception as e:
                failed += 1
                logger.error(f"Error deleting {shopify_id}: {e}")
    
    return deleted, failed

async def main():
    logger.info("🗑️  Deleting Anthropologie test products...")
    logger.info(f"   Products to delete: {len(TEST_PRODUCT_IDS)}")
    
    # Step 1: Delete from Shopify
    logger.info("\n📦 Step 1: Deleting from Shopify...")
    store_url = os.getenv('SHOPIFY_STORE_URL')
    access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
    
    if not store_url or not access_token:
        logger.error("❌ Missing Shopify credentials in .env")
        return
    
    deleted_shopify, failed_shopify = await delete_from_shopify(
        TEST_PRODUCT_IDS, store_url, access_token
    )
    
    # Step 2: Delete from local database
    logger.info("\n💾 Step 2: Deleting from local database...")
    db = DatabaseManager()
    conn = db._get_connection()
    c = conn.cursor()
    
    deleted_db = 0
    for product_id in TEST_PRODUCT_IDS:
        c.execute("DELETE FROM products WHERE shopify_id = ?", (product_id,))
        if c.rowcount > 0:
            deleted_db += 1
            logger.info(f"✅ Deleted from DB: {product_id}")
        else:
            logger.info(f"ℹ️  Not found in DB: {product_id} (may not have been saved)")
    
    conn.commit()
    conn.close()
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("✅ CLEANUP COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Shopify: {deleted_shopify}/{len(TEST_PRODUCT_IDS)} deleted ({failed_shopify} failed)")
    logger.info(f"Database: {deleted_db}/{len(TEST_PRODUCT_IDS)} deleted")
    logger.info("=" * 60)
    
    if failed_shopify > 0:
        logger.warning(f"⚠️  {failed_shopify} Shopify deletions failed (might already be deleted)")

if __name__ == "__main__":
    asyncio.run(main())
