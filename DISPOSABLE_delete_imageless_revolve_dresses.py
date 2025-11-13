"""
DISPOSABLE: Delete 25 imageless Revolve dresses from Shopify, DB, and assessment queue
Then re-run catalog monitor to get them with proper images

Date: 2024-11-13
Reason: Products uploaded with broken image transformation (0 images)
Fix: Delete and re-process with working transformation
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'Shared'))

import asyncio
import aiohttp
from datetime import datetime
from typing import List, Dict
from dotenv import load_dotenv

from db_manager import DatabaseManager
from assessment_queue_manager import AssessmentQueueManager
from logger_config import setup_logging

logger = setup_logging(__name__)

# Load environment
load_dotenv()

async def get_imageless_revolve_dresses(db: DatabaseManager) -> List[Dict]:
    """Find Revolve dresses from recent catalog monitor run with 0 images"""
    
    # Query for Revolve dresses added in last hour with shopify_id
    # These are the ones from the broken image run
    query = """
    SELECT id, url, title, shopify_id, first_seen
    FROM products
    WHERE retailer = 'revolve'
      AND clothing_type = 'dress'
      AND shopify_id IS NOT NULL
      AND datetime(first_seen) > datetime('now', '-2 hours')
    ORDER BY first_seen DESC
    LIMIT 30
    """
    
    conn = db._get_connection()
    cursor = conn.cursor()
    cursor.execute(query)
    
    products = []
    for row in cursor.fetchall():
        products.append({
            'id': row[0],
            'url': row[1],
            'title': row[2],
            'shopify_id': row[3],
            'first_seen': row[4]
        })
    
    conn.close()
    
    logger.info(f"Found {len(products)} Revolve dresses from last 2 hours")
    return products

async def delete_from_shopify(shopify_ids: List[int], store_url: str, access_token: str):
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
                        logger.warning(f"❌ Failed to delete {shopify_id}: {response.status}")
                
                await asyncio.sleep(0.5)  # Rate limiting
                
            except Exception as e:
                failed += 1
                logger.error(f"Error deleting {shopify_id}: {e}")
    
    return deleted, failed

async def delete_from_database(product_ids: List[int], db: DatabaseManager):
    """Delete products from local database"""
    
    conn = db._get_connection()
    cursor = conn.cursor()
    
    placeholders = ','.join('?' * len(product_ids))
    query = f"DELETE FROM products WHERE id IN ({placeholders})"
    
    cursor.execute(query, product_ids)
    deleted = cursor.rowcount
    
    conn.commit()
    conn.close()
    
    logger.info(f"✅ Deleted {deleted} products from local database")
    return deleted

async def delete_from_assessment_queue(product_urls: List[str], assessment: AssessmentQueueManager):
    """Delete products from assessment queue by URLs"""
    
    conn = assessment.db_manager._get_connection()
    cursor = conn.cursor()
    
    # Delete by URLs
    placeholders = ','.join('?' * len(product_urls))
    query = f"""
    DELETE FROM assessment_queue
    WHERE product_url IN ({placeholders})
    """
    
    cursor.execute(query, product_urls)
    deleted = cursor.rowcount
    
    conn.commit()
    conn.close()
    
    logger.info(f"✅ Deleted {deleted} items from assessment queue")
    return deleted

async def main():
    logger.info("=" * 60)
    logger.info("DELETING IMAGELESS REVOLVE DRESSES")
    logger.info("=" * 60)
    
    # Initialize managers
    db = DatabaseManager()
    assessment = AssessmentQueueManager()
    
    # Step 1: Find the imageless products
    logger.info("\n📋 Step 1: Finding imageless Revolve dresses...")
    products = await get_imageless_revolve_dresses(db)
    
    if not products:
        logger.warning("⚠️ No products found to delete")
        return
    
    # Display what we found
    logger.info(f"\n📦 Found {len(products)} products to delete:")
    for i, p in enumerate(products[:10], 1):
        logger.info(f"  {i}. {p['title'][:50]} (Shopify: {p['shopify_id']})")
    if len(products) > 10:
        logger.info(f"  ... and {len(products) - 10} more")
    
    # Confirm
    print("\n" + "=" * 60)
    print(f"⚠️  ABOUT TO DELETE {len(products)} PRODUCTS FROM:")
    print("   1. Shopify")
    print("   2. Local Database")
    print("   3. Assessment Queue")
    print("=" * 60)
    confirm = input("Type 'DELETE' to confirm: ")
    
    if confirm != 'DELETE':
        logger.info("❌ Cancelled by user")
        return
    
    # Extract IDs and URLs
    product_ids = [p['id'] for p in products]
    shopify_ids = [p['shopify_id'] for p in products]
    product_urls = [p['url'] for p in products]
    
    # Step 2: Delete from Shopify
    logger.info("\n🗑️  Step 2: Deleting from Shopify...")
    store_url = os.getenv('SHOPIFY_STORE_URL')
    access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
    
    if not store_url or not access_token:
        logger.error("❌ Missing Shopify credentials in .env")
        return
    
    deleted_shopify, failed_shopify = await delete_from_shopify(
        shopify_ids, store_url, access_token
    )
    
    # Step 3: Delete from assessment queue
    logger.info("\n🗑️  Step 3: Deleting from assessment queue...")
    deleted_queue = await delete_from_assessment_queue(product_urls, assessment)
    
    # Step 4: Delete from database (do this last)
    logger.info("\n🗑️  Step 4: Deleting from local database...")
    deleted_db = await delete_from_database(product_ids, db)
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("✅ DELETION COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Shopify:          {deleted_shopify}/{len(shopify_ids)} deleted")
    logger.info(f"Assessment Queue: {deleted_queue} entries deleted")
    logger.info(f"Local Database:   {deleted_db}/{len(product_ids)} products deleted")
    logger.info("=" * 60)
    
    if failed_shopify > 0:
        logger.warning(f"⚠️  {failed_shopify} Shopify deletions failed (might already be deleted)")
    
    logger.info("\n✅ Ready to re-run catalog monitor!")
    logger.info("   python3 -m Workflows.catalog_monitor revolve dresses modest")

if __name__ == '__main__':
    asyncio.run(main())

