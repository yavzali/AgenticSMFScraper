"""
Simple DOM extraction test for Revolve
"""
import asyncio
import logging
from patchright.async_api import async_playwright

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

async def test_dom():
    """Test what we can extract from Revolve DOM"""
    
    url = "https://www.revolve.com/tops/br/db773d/?navsrc=left&sortBy=newest&vnitems=length_and_mid&vnitems=length_and_long-top&vnitems=neckline_and_round-neck&vnitems=neckline_and_jewel-neck&vnitems=neckline_and_collar&vnitems=neckline_and_v-neck&vnitems=neckline_and_sweetheart&vnitems=neckline_and_turtleneck&vnitems=neckline_and_cowl-neck&vnitems=sleeve_and_long&vnitems=sleeve_and_3_4&loadVisNav=true&pageNumVisNav=1"
    
    playwright = await async_playwright().start()
    
    try:
        browser = await playwright.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080}
        )
        page = await context.new_page()
        
        logger.info("🔄 Loading Revolve page...")
        await page.goto(url, wait_until='domcontentloaded', timeout=60000)
        
        logger.info("⏳ Waiting 15 seconds for page to load...")
        await asyncio.sleep(15)
        
        logger.info("\n🔍 Extracting product links...")
        links = await page.query_selector_all('a[href*="/dp/"]')
        logger.info(f"Found {len(links)} product links")
        
        if not links:
            logger.error("No links found!")
            return
        
        # Analyze first 3 products
        logger.info("\n" + "="*80)
        logger.info("ANALYZING FIRST 3 PRODUCTS")
        logger.info("="*80)
        
        for i, link in enumerate(links[:3], 1):
            href = await link.get_attribute('href')
            logger.info(f"\n{'='*80}")
            logger.info(f"PRODUCT {i}: {href}")
            logger.info(f"{'='*80}")
            
            # Get parent container
            parent = await link.evaluate_handle('''el => {
                // Try to find product container
                let container = el.closest('[class*="product"]') || 
                                el.closest('article') || 
                                el.closest('div[class]');
                return container || el.parentElement;
            }''')
            
            # Get HTML snippet
            html = await parent.evaluate('el => el.outerHTML')
            logger.info(f"\n📄 HTML Structure (first 800 chars):")
            logger.info(html[:800] + "...")
            
            # Try title extraction
            logger.info(f"\n📝 TITLE EXTRACTION ATTEMPTS:")
            title_selectors = [
                {'sel': 'a', 'attr': 'aria-label'},
                {'sel': 'img', 'attr': 'alt'},
                {'sel': 'h1', 'method': 'text'},
                {'sel': 'h2', 'method': 'text'},
                {'sel': 'h3', 'method': 'text'},
                {'sel': '.title', 'method': 'text'},
                {'sel': '[class*="title"]', 'method': 'text'},
                {'sel': '[class*="name"]', 'method': 'text'},
                {'sel': '[class*="Title"]', 'method': 'text'},
                {'sel': '[class*="Name"]', 'method': 'text'},
                {'sel': 'span', 'method': 'text'},
                {'sel': 'div', 'method': 'text'},
            ]
            
            for test in title_selectors:
                try:
                    if test.get('attr'):
                        el = await parent.query_selector(test['sel'])
                        if el:
                            text = await el.get_attribute(test['attr'])
                            if text and len(text) > 5 and len(text) < 200:
                                logger.info(f"  ✅ {test['sel']}[@{test['attr']}]: {text}")
                    else:
                        el = await parent.query_selector(test['sel'])
                        if el:
                            text = (await el.inner_text()).strip()
                            if text and len(text) > 5 and len(text) < 200:
                                logger.info(f"  ✅ {test['sel']}: {text}")
                except:
                    pass
            
            # Try price extraction
            logger.info(f"\n💰 PRICE EXTRACTION ATTEMPTS:")
            price_selectors = [
                '[class*="price"]', '[class*="Price"]',
                'span[class*="price"]', 'span[class*="Price"]',
                'div[class*="price"]', 'div[class*="Price"]',
                '[data-price]', '[data-testid*="price"]'
            ]
            
            for sel in price_selectors:
                try:
                    el = await parent.query_selector(sel)
                    if el:
                        text = (await el.inner_text()).strip()
                        if text and '$' in text:
                            logger.info(f"  ✅ {sel}: {text}")
                except:
                    pass
            
            logger.info("")
        
        logger.info("\n" + "="*80)
        logger.info("TEST COMPLETE")
        logger.info("="*80)
        
    finally:
        await playwright.stop()

if __name__ == '__main__':
    asyncio.run(test_dom())

