"""
Test DOM-First Extraction Across All Retailers
Tests the new DOM extraction logic with retailer-specific selectors
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Extraction', 'Patchright'))

from patchright_catalog_extractor import PatchrightCatalogExtractor
import logging

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Test URLs for each retailer
TEST_URLS = {
    'revolve': {
        'url': 'https://www.revolve.com/tops/br/db773d/?navsrc=left&sortBy=newest&vnitems=length_and_mid&vnitems=length_and_long-top&vnitems=neckline_and_round-neck&vnitems=neckline_and_jewel-neck&vnitems=neckline_and_collar&vnitems=neckline_and_v-neck&vnitems=neckline_and_sweetheart&vnitems=neckline_and_turtleneck&vnitems=neckline_and_cowl-neck&vnitems=sleeve_and_long&vnitems=sleeve_and_3_4&loadVisNav=true&pageNumVisNav=1',
        'expected_min': 40
    },
    'anthropologie': {
        'url': 'https://www.anthropologie.com/dresses?sort=tile.product.newestColorDate&order=Descending',
        'expected_min': 50
    },
    'urban_outfitters': {
        'url': 'https://www.urbanoutfitters.com/dresses?sort=tile.product.newestColorDate&order=Descending&sleeve=Long+Sleeve,3/4+Sleeve,Short+Sleeve',
        'expected_min': 50
    },
    'abercrombie': {
        'url': 'https://www.abercrombie.com/shop/us/womens-dresses-and-jumpsuits?pagefm=navigation-left+nav&rows=90&sort=newest&start=0',
        'expected_min': 60
    },
    'nordstrom': {
        'url': 'https://www.nordstrom.com/browse/women/clothing/dresses?breadcrumb=Home%2FWomen%2FClothing%2FDresses&preferredStore=210&preferredPostalCode=10451&sort=Newest&postalCodeAvailability=10451&filterByNeckStyle=boat-neck&filterByNeckStyle=collared&filterByNeckStyle=cowl-neck&filterByNeckStyle=crewneck&filterByNeckStyle=henley&filterByNeckStyle=high-neck&filterByNeckStyle=mock-neck&filterByNeckStyle=quarter-zip&filterByNeckStyle=shawl-collar&filterByNeckStyle=tie-neck&filterByNeckStyle=turtleneck&filterBySleeveLength=cap-sleeve&filterBySleeveLength=short-sleeve&filterBySleeveLength=3-4-sleeve&filterBySleeveLength=long-sleeve',
        'expected_min': 40
    },
    'aritzia': {
        'url': 'https://www.aritzia.com/us/en/clothing/dresses',
        'expected_min': 40
    }
}

async def test_retailer(retailer: str, config: dict):
    """Test DOM extraction for a single retailer"""
    logger.info(f"\n{'='*80}")
    logger.info(f"TESTING: {retailer.upper()}")
    logger.info(f"{'='*80}")
    
    extractor = PatchrightCatalogExtractor()
    
    try:
        prompt = f"Extract all products from this {retailer} catalog page"
        result = await extractor.extract_catalog(
            config['url'],
            retailer,
            prompt
        )
        
        if not result['success']:
            logger.error(f"❌ {retailer}: Extraction failed - {result.get('errors')}")
            return {
                'retailer': retailer,
                'success': False,
                'error': result.get('errors')
            }
        
        products = result['products']
        logger.info(f"\n📊 RESULTS FOR {retailer.upper()}:")
        logger.info(f"  Total products: {len(products)}")
        
        # Analyze extraction quality
        with_urls = sum(1 for p in products if p.get('url'))
        with_titles = sum(1 for p in products if p.get('title') and len(p.get('title', '')) > 5)
        # Handle both string and numeric prices
        def has_valid_price(p):
            price = p.get('price')
            if not price:
                return False
            if isinstance(price, str):
                # Try to extract number from string like "$115" or "115.00"
                import re
                match = re.search(r'\d+\.?\d*', price.replace('$', '').replace(',', ''))
                return bool(match and float(match.group()) > 0)
            return price > 0
        with_prices = sum(1 for p in products if has_valid_price(p))
        
        logger.info(f"  With URLs: {with_urls}/{len(products)} ({with_urls/len(products)*100:.1f}%)")
        logger.info(f"  With Titles: {with_titles}/{len(products)} ({with_titles/len(products)*100:.1f}%)")
        logger.info(f"  With Prices: {with_prices}/{len(products)} ({with_prices/len(products)*100:.1f}%)")
        
        # Show first 3 products
        logger.info(f"\n📦 SAMPLE PRODUCTS (first 3):")
        for i, product in enumerate(products[:3], 1):
            logger.info(f"\n  Product {i}:")
            logger.info(f"    Title: {product.get('title', 'N/A')}")
            logger.info(f"    Price: ${product.get('price', 'N/A')}")
            logger.info(f"    URL: {product.get('url', 'N/A')[:80]}...")
        
        # Check if meets expectations
        expected_min = config['expected_min']
        meets_count = len(products) >= expected_min
        meets_quality = with_titles >= len(products) * 0.8 and with_prices >= len(products) * 0.8
        
        if meets_count and meets_quality:
            logger.info(f"\n✅ {retailer}: PASSED (found {len(products)} products, {with_titles/len(products)*100:.1f}% titles, {with_prices/len(products)*100:.1f}% prices)")
        else:
            reasons = []
            if not meets_count:
                reasons.append(f"Expected {expected_min}+, got {len(products)}")
            if not meets_quality:
                reasons.append(f"Low quality: {with_titles/len(products)*100:.1f}% titles, {with_prices/len(products)*100:.1f}% prices")
            logger.warning(f"\n⚠️ {retailer}: NEEDS IMPROVEMENT - {', '.join(reasons)}")
        
        return {
            'retailer': retailer,
            'success': True,
            'total': len(products),
            'with_urls': with_urls,
            'with_titles': with_titles,
            'with_prices': with_prices,
            'meets_expectations': meets_count and meets_quality,
            'sample_products': products[:3]
        }
        
    except Exception as e:
        logger.error(f"❌ {retailer}: Exception - {e}")
        import traceback
        traceback.print_exc()
        return {
            'retailer': retailer,
            'success': False,
            'error': str(e)
        }

async def main():
    """Test all retailers"""
    logger.info("🚀 STARTING DOM-FIRST EXTRACTION TESTS")
    logger.info(f"Testing {len(TEST_URLS)} retailers\n")
    
    results = []
    
    for retailer, config in TEST_URLS.items():
        result = await test_retailer(retailer, config)
        results.append(result)
        
        # Small delay between tests
        await asyncio.sleep(2)
    
    # Summary
    logger.info(f"\n\n{'='*80}")
    logger.info("FINAL SUMMARY")
    logger.info(f"{'='*80}\n")
    
    passed = sum(1 for r in results if r.get('success') and r.get('meets_expectations'))
    failed = sum(1 for r in results if not r.get('success'))
    needs_improvement = sum(1 for r in results if r.get('success') and not r.get('meets_expectations'))
    
    logger.info(f"✅ Passed: {passed}/{len(results)}")
    logger.info(f"⚠️ Needs Improvement: {needs_improvement}/{len(results)}")
    logger.info(f"❌ Failed: {failed}/{len(results)}")
    
    logger.info(f"\n📊 DETAILED RESULTS:\n")
    for result in results:
        retailer = result['retailer']
        if result.get('success'):
            total = result['total']
            titles = result['with_titles']
            prices = result['with_prices']
            status = "✅ PASS" if result.get('meets_expectations') else "⚠️ IMPROVE"
            logger.info(f"{status} {retailer:20s} - {total:3d} products ({titles/total*100:5.1f}% titles, {prices/total*100:5.1f}% prices)")
        else:
            logger.info(f"❌ FAIL {retailer:20s} - {result.get('error')}")

if __name__ == '__main__':
    asyncio.run(main())

