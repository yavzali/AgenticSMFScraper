"""
Analyze Revolve's actual product card structure
"""
import asyncio
import logging
from patchright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

async def analyze():
    """Analyze Revolve product structure"""
    
    url = "https://www.revolve.com/tops/br/db773d/?navsrc=left&sortBy=newest&vnitems=length_and_mid&vnitems=length_and_long-top&vnitems=neckline_and_round-neck&vnitems=neckline_and_jewel-neck&vnitems=neckline_and_collar&vnitems=neckline_and_v-neck&vnitems=neckline_and_sweetheart&vnitems=neckline_and_turtleneck&vnitems=neckline_and_cowl-neck&vnitems=sleeve_and_long&vnitems=sleeve_and_3_4&loadVisNav=true&pageNumVisNav=1"
    
    playwright = await async_playwright().start()
    
    try:
        browser = await playwright.chromium.launch(headless=False)
        context = await browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = await context.new_page()
        
        logger.info("🔄 Loading Revolve...")
        await page.goto(url, wait_until='networkidle', timeout=60000)
        await asyncio.sleep(5)
        
        # Try finding product containers with different selectors
        logger.info("\n📦 FINDING PRODUCT CONTAINERS")
        
        selectors_to_try = [
            'article',
            '[data-product-id]',
            '.product-card',
            '.product-grid__product',
            '[class*="product"]',
            '[class*="grid"]',
        ]
        
        found_container = None
        for sel in selectors_to_try:
            els = await page.query_selector_all(sel)
            if els and len(els) > 10:
                logger.info(f"✅ Found {len(els)} containers with: {sel}")
                found_container = sel
                break
        
        if not found_container:
            logger.error("❌ No product containers found!")
            return
        
        # Get first 3 products
        containers = await page.query_selector_all(found_container)
        logger.info(f"\n🔍 ANALYZING FIRST 3 PRODUCTS")
        
        for i, container in enumerate(containers[:3], 1):
            logger.info(f"\n{'='*80}")
            logger.info(f"PRODUCT {i}")
            logger.info(f"{'='*80}")
            
            # Get container HTML
            html = await container.evaluate('el => el.outerHTML')
            logger.info(f"\n📄 HTML (first 1000 chars):\n{html[:1000]}\n")
            
            # Try to find product link
            logger.info("🔗 LINK EXTRACTION:")
            link_selectors = ['a[href*="/dp/"]', 'a[href*="/product"]', 'a.js-plp-pdp-link', 'a']
            for link_sel in link_selectors:
                try:
                    link = await container.query_selector(link_sel)
                    if link:
                        href = await link.get_attribute('href')
                        if href and ('/dp/' in href or '/product' in href):
                            logger.info(f"  ✅ {link_sel}: {href}")
                            break
                except:
                    pass
            
            # Try to find title - check text content, aria-label, img alt
            logger.info("\n📝 TITLE EXTRACTION:")
            
            # Method 1: aria-label on link
            try:
                link = await container.query_selector('a[aria-label]')
                if link:
                    aria = await link.get_attribute('aria-label')
                    if aria and len(aria) > 5:
                        logger.info(f"  ✅ a[aria-label]: {aria}")
            except:
                pass
            
            # Method 2: img alt text
            try:
                img = await container.query_selector('img[alt]')
                if img:
                    alt = await img.get_attribute('alt')
                    if alt and len(alt) > 5 and 'revolve' not in alt.lower():
                        logger.info(f"  ✅ img[alt]: {alt}")
            except:
                pass
            
            # Method 3: Look for text nodes
            try:
                text = await container.inner_text()
                lines = [l.strip() for l in text.split('\n') if l.strip() and len(l.strip()) > 5]
                logger.info(f"  📝 Text content ({len(lines)} lines):")
                for line in lines[:10]:
                    if len(line) < 100:  # Skip super long lines
                        logger.info(f"     - {line}")
            except:
                pass
            
            # Try to find price
            logger.info("\n💰 PRICE EXTRACTION:")
            
            # Method 1: Look for $ in text
            try:
                text = await container.inner_text()
                for line in text.split('\n'):
                    if '$' in line and len(line) < 20:
                        logger.info(f"  ✅ Text with $: {line.strip()}")
                        break
            except:
                pass
            
            # Method 2: Common price selectors
            price_selectors = [
                '.price', '[class*="price"]', '[data-price]',
                'span:has-text("$")', 'div:has-text("$")'
            ]
            for price_sel in price_selectors:
                try:
                    el = await container.query_selector(price_sel)
                    if el:
                        price_text = await el.inner_text()
                        if '$' in price_text:
                            logger.info(f"  ✅ {price_sel}: {price_text}")
                            break
                except:
                    pass
        
        logger.info(f"\n{'='*80}")
        logger.info("COMPLETE")
        logger.info(f"{'='*80}")
        
    finally:
        await playwright.stop()

if __name__ == '__main__':
    asyncio.run(analyze())

