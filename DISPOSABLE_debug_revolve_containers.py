"""
Debug why Revolve container extraction finds 0 products
"""
import asyncio
from patchright.async_api import async_playwright
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

async def debug_containers():
    """Debug Revolve container structure"""
    
    url = "https://www.revolve.com/tops/br/db773d/?navsrc=left&sortBy=newest&vnitems=length_and_mid&vnitems=length_and_long-top&vnitems=neckline_and_round-neck&vnitems=neckline_and_jewel-neck&vnitems=neckline_and_collar&vnitems=neckline_and_v-neck&vnitems=neckline_and_sweetheart&vnitems=neckline_and_turtleneck&vnitems=neckline_and_cowl-neck&vnitems=sleeve_and_long&vnitems=sleeve_and_3_4&loadVisNav=true&pageNumVisNav=1"
    
    playwright = await async_playwright().start()
    
    try:
        browser = await playwright.chromium.launch(headless=False)
        context = await browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = await context.new_page()
        
        logger.info("🔄 Loading Revolve...")
        await page.goto(url, wait_until='domcontentloaded', timeout=60000)
        await asyncio.sleep(8)
        
        # Dismiss popups
        try:
            close_buttons = await page.query_selector_all('button[aria-label*="Close"], button:has-text("Don\'t Allow")')
            for btn in close_buttons[:3]:
                try:
                    await btn.click(timeout=2000)
                    await asyncio.sleep(0.5)
                except:
                    pass
        except:
            pass
        
        await asyncio.sleep(2)
        
        # Find containers
        containers = await page.query_selector_all('li.plp__product')
        logger.info(f"\nFound {len(containers)} containers with 'li.plp__product'")
        
        if len(containers) == 0:
            logger.info("\n❌ No containers found! Trying alternative selectors...")
            
            alt_selectors = [
                'li[class*="plp"]',
                'li[class*="product"]',
                '#plp-prod-list li',
                'ul.products-grid li'
            ]
            
            for sel in alt_selectors:
                containers = await page.query_selector_all(sel)
                logger.info(f"  {sel}: {len(containers)} containers")
                if len(containers) > 0:
                    break
        
        # Analyze first 3 containers
        for i, container in enumerate(containers[:3], 1):
            logger.info(f"\n{'='*80}")
            logger.info(f"CONTAINER {i}")
            logger.info(f"{'='*80}")
            
            # Get HTML (first 500 chars)
            html = await container.evaluate('el => el.outerHTML')
            logger.info(f"HTML (first 500 chars):\n{html[:500]}...")
            
            # Try to find link
            logger.info(f"\n🔗 Looking for links:")
            
            link_selectors = [
                'a[href*="/dp/"]',
                'a[href]',
                'a'
            ]
            
            for sel in link_selectors:
                links = await container.query_selector_all(sel)
                logger.info(f"  {sel}: {len(links)} links")
                
                if links and len(links) > 0:
                    first_link = links[0]
                    href = await first_link.get_attribute('href')
                    logger.info(f"    First link href: {href}")
        
        await asyncio.sleep(2)
        
    finally:
        await playwright.stop()

if __name__ == '__main__':
    asyncio.run(debug_containers())

