"""
DISPOSABLE: Delete 25 specific Revolve dresses from Shopify and assessment queue

These are the imageless products from catalog monitor run on 2024-11-13
They're in Shopify and assessment queue but not in local database (deduped as suspected duplicates)

Shopify IDs extracted from /tmp/revolve_dresses_monitor.log
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'Shared'))

import asyncio
import aiohttp
from dotenv import load_dotenv
from logger_config import setup_logging

logger = setup_logging(__name__)
load_dotenv()

# The 25 Shopify product IDs from today's run
SHOPIFY_IDS = [
    14835383435634, 14835384385906, 14835385008498, 14835385729394, 14835386876274,
    14835387662706, 14835388383602, 14835389333874, 14835389497714, 14835389694322,
    14835389858162, 14835389956466, 14835390251378, 14835390349682, 14835390644594,
    14835390742898, 14835390841202, 14835390972274, 14835391070578, 14835391234418,
    14835391431026, 14835391529330, 14835391660402, 14835392151922, 14835399164274
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
                        logger.warning(f"❌ Failed to delete {shopify_id}: {response.status}")
                
                await asyncio.sleep(0.5)  # Rate limiting
                
            except Exception as e:
                failed += 1
                logger.error(f"Error deleting {shopify_id}: {e}")
    
    return deleted, failed

async def delete_from_assessment_queue_recent():
    """Delete recent Revolve dress entries from assessment queue"""
    
    sys.path.append(os.path.join(os.path.dirname(__file__), 'Shared'))
    from assessment_queue_manager import AssessmentQueueManager
    
    assessment = AssessmentQueueManager()
    conn = assessment.db_manager._get_connection()
    cursor = conn.cursor()
    
    # Delete recent Revolve entries (added in last 2 hours)
    query = """
    DELETE FROM assessment_queue
    WHERE retailer = 'revolve'
      AND datetime(created_at) > datetime('now', '-2 hours')
    """
    
    cursor.execute(query)
    deleted = cursor.rowcount
    
    conn.commit()
    conn.close()
    
    logger.info(f"✅ Deleted {deleted} items from assessment queue")
    return deleted

async def main():
    logger.info("=" * 60)
    logger.info(f"DELETING {len(SHOPIFY_IDS)} REVOLVE DRESSES")
    logger.info("=" * 60)
    logger.info("These products have 0 images due to broken transformation")
    logger.info("Will delete from Shopify and assessment queue only")
    logger.info("(Not in local DB - were deduped)")
    logger.info("=" * 60)
    
    # Confirm
    print(f"\n⚠️  ABOUT TO DELETE {len(SHOPIFY_IDS)} PRODUCTS FROM:")
    print("   1. Shopify")
    print("   2. Assessment Queue")
    print("=" * 60)
    confirm = input("Type 'DELETE' to confirm: ")
    
    if confirm != 'DELETE':
        logger.info("❌ Cancelled by user")
        return
    
    # Step 1: Delete from Shopify
    logger.info("\n🗑️  Step 1: Deleting from Shopify...")
    store_url = os.getenv('SHOPIFY_STORE_URL')
    access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
    
    if not store_url or not access_token:
        logger.error("❌ Missing Shopify credentials in .env")
        return
    
    deleted_shopify, failed_shopify = await delete_from_shopify(
        SHOPIFY_IDS, store_url, access_token
    )
    
    # Step 2: Delete from assessment queue
    logger.info("\n🗑️  Step 2: Deleting from assessment queue...")
    deleted_queue = await delete_from_assessment_queue_recent()
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("✅ DELETION COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Shopify:          {deleted_shopify}/{len(SHOPIFY_IDS)} deleted ({failed_shopify} failed)")
    logger.info(f"Assessment Queue: {deleted_queue} entries deleted")
    logger.info("=" * 60)
    
    if failed_shopify > 0:
        logger.warning(f"⚠️  {failed_shopify} Shopify deletions failed (might already be deleted)")
    
    logger.info("\n✅ Ready to re-run catalog monitor with working image transformation!")
    logger.info("   python3 -m Workflows.catalog_monitor revolve dresses modest")

if __name__ == '__main__':
    asyncio.run(main())

