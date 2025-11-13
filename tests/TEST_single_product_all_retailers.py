"""
Test Single Product Extraction - Patchright-Only Retailers
Tests DOM-first extraction on individual product pages

Focus: Patchright-only retailers (Anthropologie, Urban Outfitters, Abercrombie, Aritzia, H&M)
Excluded: Revolve (uses Markdown for single product), Nordstrom (blocked)
"""
import asyncio
import sys
import os
import re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Extraction', 'Patchright'))

from patchright_product_extractor import PatchrightProductExtractor
import logging

# Suppress debug logs for cleaner output
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Test URLs - real product pages from Patchright-only retailers (provided by user)
TEST_PRODUCTS = {
    'anthropologie': {
        'url': 'https://www.anthropologie.com/shop/mare-mare-long-sleeve-slim-sweater-maxi-dress?color=060&type=STANDARD',
        'expected_title': 'Mare Mare Long-Sleeve Slim Sweater Maxi Dress',
        'has_price': True
    },
    'urban_outfitters': {
        'url': 'https://www.urbanoutfitters.com/shop/uo-samara-mesh-strapless-midi-dress?color=001&type=REGULAR',
        'expected_title': 'UO Samara Mesh Strapless Midi Dress',
        'has_price': True
    },
    'abercrombie': {
        'url': 'https://www.abercrombie.com/shop/us/p/flannel-shirt-dress-61008349?categoryId=12265&faceout=model&seq=01',
        'expected_title': 'Flannel Shirt Dress',
        'has_price': True
    },
    'aritzia': {
        'url': 'https://www.aritzia.com/us/en/product/choreo-satin-dress/128697.html?color=11420',
        'expected_title': 'Choreo Satin Dress',
        'has_price': True
    },
    'hm': {
        'url': 'https://www2.hm.com/en_us/productpage.1323522001.html',
        'expected_title': 'H&M Dress',
        'has_price': True
    }
}

async def test_single_product(retailer, test_data):
    """Test single product extraction for a retailer"""
    logger.info(f"\n{'='*80}")
    logger.info(f"Testing {retailer.upper()}")
    logger.info(f"{'='*80}")
    
    extractor = PatchrightProductExtractor()
    
    try:
        url = test_data['url']
        logger.info(f"URL: {url[:70]}...")
        
        # Extract product
        result = await extractor.extract_product(url, retailer)
        
        # Handle ExtractionResult object (has .success, .data attributes)
        if not result.success:
            error_msg = ', '.join(result.errors) if result.errors else 'Unknown error'
            logger.error(f"❌ FAILED: {error_msg}")
            return {
                'retailer': retailer,
                'success': False,
                'has_title': False,
                'has_price': False,
                'has_images': False,
                'error': error_msg
            }
        
        product = result.data
        
        # Validate extraction
        has_title = bool(product.get('title') and len(product.get('title', '')) > 5)
        
        # Price validation
        def has_valid_price(price):
            if not price:
                return False
            if isinstance(price, str):
                match = re.search(r'\d+\.?\d*', str(price).replace('$', '').replace(',', ''))
                return bool(match and float(match.group()) > 0)
            return price > 0
        
        has_price = has_valid_price(product.get('price'))
        has_images = bool(product.get('image_urls') and len(product.get('image_urls', [])) > 0)
        
        # Display results
        logger.info(f"\n📊 RESULTS:")
        logger.info(f"  Title: {product.get('title', 'N/A')[:60]}")
        logger.info(f"  Price: ${product.get('price', 'N/A')}")
        logger.info(f"  Images: {len(product.get('image_urls', []))} found")
        desc = product.get('description') or ''
        logger.info(f"  Description: {len(desc)} chars")
        
        # Assessment
        all_good = has_title and has_price and has_images
        
        if all_good:
            logger.info(f"\n✅ PASS - Complete extraction")
        else:
            logger.info(f"\n⚠️ INCOMPLETE:")
            if not has_title:
                logger.info(f"  ❌ Missing title")
            if not has_price:
                logger.info(f"  ❌ Missing price")
            if not has_images:
                logger.info(f"  ❌ Missing images")
        
        return {
            'retailer': retailer,
            'success': True,
            'has_title': has_title,
            'has_price': has_price,
            'has_images': has_images,
            'complete': all_good
        }
        
    except Exception as e:
        logger.error(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return {
            'retailer': retailer,
            'success': False,
            'has_title': False,
            'has_price': False,
            'has_images': False,
            'error': str(e)
        }

async def main():
    """Run all tests"""
    logger.info("🚀 TESTING SINGLE PRODUCT EXTRACTION - ALL RETAILERS")
    logger.info("="*80)
    
    results = []
    
    # Test each retailer
    for retailer, test_data in TEST_PRODUCTS.items():
        result = await test_single_product(retailer, test_data)
        results.append(result)
        await asyncio.sleep(2)  # Brief pause between retailers
    
    # Final summary
    logger.info(f"\n\n{'='*80}")
    logger.info("FINAL SUMMARY")
    logger.info("="*80)
    
    total = len(TEST_PRODUCTS)
    passed = sum(1 for r in results if r.get('complete', False))
    partial = sum(1 for r in results if r.get('success', False) and not r.get('complete', False))
    failed = sum(1 for r in results if not r.get('success', False))
    
    logger.info(f"\n✅ Complete: {passed}/{total}")
    logger.info(f"⚠️ Partial: {partial}/{total}")
    logger.info(f"❌ Failed: {failed}/{total}")
    logger.info(f"\n📊 DETAILED RESULTS:\n")
    
    for result in results:
        retailer = result['retailer']
        if result.get('complete'):
            logger.info(f"✅ PASS {retailer:20s} - Complete extraction (title, price, images)")
        elif result.get('success'):
            missing = []
            if not result.get('has_title'):
                missing.append('title')
            if not result.get('has_price'):
                missing.append('price')
            if not result.get('has_images'):
                missing.append('images')
            logger.info(f"⚠️ PARTIAL {retailer:20s} - Missing: {', '.join(missing)}")
        else:
            error = result.get('error', 'Unknown error')
            logger.info(f"❌ FAIL {retailer:20s} - {error[:50]}")

if __name__ == '__main__':
    asyncio.run(main())

