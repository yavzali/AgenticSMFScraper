"""
Inspect Revolve DOM Structure
Find out where product data actually lives
"""
import asyncio
from patchright.async_api import async_playwright
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

async def inspect_dom():
    """Inspect what's actually in the DOM"""
    
    url = "https://www.revolve.com/tops/br/db773d/?navsrc=left&sortBy=newest&vnitems=length_and_mid&vnitems=length_and_long-top&vnitems=neckline_and_round-neck&vnitems=neckline_and_jewel-neck&vnitems=neckline_and_collar&vnitems=neckline_and_v-neck&vnitems=neckline_and_sweetheart&vnitems=neckline_and_turtleneck&vnitems=neckline_and_cowl-neck&vnitems=sleeve_and_long&vnitems=sleeve_and_3_4&loadVisNav=true&pageNumVisNav=1"
    
    playwright = await async_playwright().start()
    
    try:
        browser = await playwright.chromium.launch(headless=False)
        context = await browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = await context.new_page()
        
        logger.info("🔄 Loading Revolve...")
        await page.goto(url, wait_until='networkidle', timeout=90000)
        logger.info("✅ Page loaded with networkidle")
        
        await asyncio.sleep(5)
        
        # Check for different container selectors
        logger.info("\n🔍 TESTING CONTAINER SELECTORS:")
        logger.info("="*80)
        
        selectors_to_test = [
            'li.plp__product',
            'li.gc',
            'li[class*="plp"]',
            'li[class*="product"]',
            '.products-grid li',
            '#plp-prod-list li',
            '[id*="plp-prod-list"] li',
            'article',
            '[data-product-id]',
            '.plp-container'
        ]
        
        for sel in selectors_to_test:
            try:
                els = await page.query_selector_all(sel)
                logger.info(f"  {sel:40s} → {len(els)} elements")
                
                # If we found some, show first element's classes
                if els and len(els) > 0:
                    classes = await els[0].get_attribute('class')
                    element_id = await els[0].get_attribute('id')
                    logger.info(f"      First element: id='{element_id}', class='{classes}'")
            except:
                logger.info(f"  {sel:40s} → ERROR")
        
        # Check if product list exists
        logger.info(f"\n\n🔍 INSPECTING PRODUCT LIST:")
        logger.info("="*80)
        
        prod_list = await page.query_selector('#plp-prod-list')
        if prod_list:
            html = await prod_list.evaluate('el => el.outerHTML')
            logger.info(f"Product list HTML (first 1000 chars):")
            logger.info(html[:1000])
            logger.info("...")
            
            # Get children
            children = await prod_list.query_selector_all(':scope > *')
            logger.info(f"\n📦 Direct children: {len(children)}")
            
            if children and len(children) > 0:
                logger.info(f"\nFirst child details:")
                first_child_html = await children[0].evaluate('el => el.outerHTML')
                logger.info(first_child_html[:500])
        else:
            logger.info("❌ #plp-prod-list not found!")
        
        # Try to find where prices actually are
        logger.info(f"\n\n💰 SEARCHING FOR PRICE ELEMENTS:")
        logger.info("="*80)
        
        # Search for any element containing $
        all_text_with_price = await page.evaluate('''() => {
            const elements = Array.from(document.querySelectorAll('*'));
            const withPrice = [];
            
            for (let el of elements) {
                const text = el.textContent;
                if (text && text.includes('$') && text.length < 100) {
                    const ownText = Array.from(el.childNodes)
                        .filter(node => node.nodeType === Node.TEXT_NODE)
                        .map(node => node.textContent.trim())
                        .join(' ');
                    
                    if (ownText && ownText.includes('$')) {
                        withPrice.push({
                            tag: el.tagName,
                            class: el.className,
                            text: ownText,
                            parent: el.parentElement ? el.parentElement.tagName : 'none'
                        });
                    }
                }
            }
            return withPrice.slice(0, 20);  // First 20
        }''')
        
        logger.info(f"Found {len(all_text_with_price)} elements with $ in text:")
        for i, el in enumerate(all_text_with_price[:10], 1):
            logger.info(f"  {i}. <{el['tag']}> class='{el['class'][:50]}' text='{el['text']}'")
        
        await asyncio.sleep(2)
        
    finally:
        await playwright.stop()

if __name__ == '__main__':
    asyncio.run(inspect_dom())

