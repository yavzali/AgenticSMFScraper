"""
Test Revolve Price Extraction Fix
Quick validation of container scoping improvements
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Extraction', 'Patchright'))

from patchright_catalog_extractor import PatchrightCatalogExtractor
import logging

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

async def test_revolve_fix():
    """Test Revolve extraction with new fixes"""
    
    url = "https://www.revolve.com/tops/br/db773d/?navsrc=left&sortBy=newest&vnitems=length_and_mid&vnitems=length_and_long-top&vnitems=neckline_and_round-neck&vnitems=neckline_and_jewel-neck&vnitems=neckline_and_collar&vnitems=neckline_and_v-neck&vnitems=neckline_and_sweetheart&vnitems=neckline_and_turtleneck&vnitems=neckline_and_cowl-neck&vnitems=sleeve_and_long&vnitems=sleeve_and_3_4&loadVisNav=true&pageNumVisNav=1"
    
    extractor = PatchrightCatalogExtractor()
    
    logger.info("🚀 TESTING REVOLVE WITH CONTAINER SCOPING FIX")
    logger.info("="*80)
    
    try:
        prompt = "Extract all products from this Revolve tops catalog"
        result = await extractor.extract_catalog(url, 'revolve', prompt)
        
        if not result['success']:
            logger.error(f"❌ Extraction failed: {result.get('errors')}")
            return
        
        products = result['products']
        logger.info(f"\n📊 RESULTS:")
        logger.info(f"  Total products: {len(products)}")
        
        # Analyze quality
        with_urls = sum(1 for p in products if p.get('url'))
        with_titles = sum(1 for p in products if p.get('title') and len(p.get('title', '')) > 5)
        
        # Price validation
        import re
        def has_valid_price(p):
            price = p.get('price')
            if not price:
                return False
            if isinstance(price, str):
                match = re.search(r'\d+\.?\d*', str(price).replace('$', '').replace(',', ''))
                return bool(match and float(match.group()) > 0)
            return price > 0
        
        with_prices = sum(1 for p in products if has_valid_price(p))
        
        logger.info(f"  With URLs: {with_urls}/{len(products)} ({with_urls/len(products)*100:.1f}%)")
        logger.info(f"  With Titles: {with_titles}/{len(products)} ({with_titles/len(products)*100:.1f}%)")
        logger.info(f"  With Prices: {with_prices}/{len(products)} ({with_prices/len(products)*100:.1f}%)")
        
        # Show first 5 products
        logger.info(f"\n📦 SAMPLE PRODUCTS:")
        for i, product in enumerate(products[:5], 1):
            logger.info(f"\n  Product {i}:")
            logger.info(f"    Title: {product.get('title', 'N/A')[:60]}...")
            logger.info(f"    Price: {product.get('price', 'N/A')}")
            url_display = product.get('url', 'N/A')
            if url_display and url_display != 'N/A':
                url_display = url_display[:70] + "..."
            logger.info(f"    URL: {url_display}")
        
        # Assessment
        logger.info(f"\n🎯 ASSESSMENT:")
        if with_prices >= len(products) * 0.7:
            logger.info(f"  ✅ SUCCESS! Price extraction: {with_prices/len(products)*100:.1f}% (target: 70%+)")
        elif with_prices >= len(products) * 0.5:
            logger.info(f"  ⚠️ IMPROVED! Price extraction: {with_prices/len(products)*100:.1f}% (was: 19.4%)")
        else:
            logger.info(f"  ❌ NEEDS MORE WORK: Price extraction: {with_prices/len(products)*100:.1f}%")
        
        # Compare to previous
        previous_rate = 0.194
        current_rate = with_prices/len(products)
        improvement = (current_rate - previous_rate) / previous_rate * 100 if previous_rate > 0 else 0
        
        if improvement > 0:
            logger.info(f"  📈 Improvement: +{improvement:.1f}% from previous run")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(test_revolve_fix())

