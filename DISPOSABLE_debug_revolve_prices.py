"""
Debug Revolve Price Extraction
Diagnose why DOM extraction only finding 19.4% of prices
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Extraction', 'Patchright'))

from patchright.async_api import async_playwright
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

async def debug_revolve():
    """Debug Revolve price extraction"""
    
    url = "https://www.revolve.com/tops/br/db773d/?navsrc=left&sortBy=newest&vnitems=length_and_mid&vnitems=length_and_long-top&vnitems=neckline_and_round-neck&vnitems=neckline_and_jewel-neck&vnitems=neckline_and_collar&vnitems=neckline_and_v-neck&vnitems=neckline_and_sweetheart&vnitems=neckline_and_turtleneck&vnitems=neckline_and_cowl-neck&vnitems=sleeve_and_long&vnitems=sleeve_and_3_4&loadVisNav=true&pageNumVisNav=1"
    
    playwright = await async_playwright().start()
    
    try:
        browser = await playwright.chromium.launch(headless=False)
        context = await browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = await context.new_page()
        
        logger.info("🔄 Loading Revolve...")
        await page.goto(url, wait_until='domcontentloaded', timeout=60000)
        await asyncio.sleep(5)
        
        # Dismiss popups
        try:
            close_buttons = await page.query_selector_all('button[aria-label*="Close"], button:has-text("Don\'t Allow"), button:has-text("No Thanks")')
            for btn in close_buttons[:3]:
                try:
                    await btn.click(timeout=2000)
                    await asyncio.sleep(0.5)
                except:
                    pass
        except:
            pass
        
        await asyncio.sleep(2)
        
        # Get product links
        logger.info("\n🔍 ANALYZING PRODUCT STRUCTURE")
        links = await page.query_selector_all('a[href*="/dp/"]')
        logger.info(f"Found {len(links)} product links")
        
        # Analyze first 3 products
        for i, link in enumerate(links[:3], 1):
            logger.info(f"\n{'='*80}")
            logger.info(f"PRODUCT {i}")
            logger.info(f"{'='*80}")
            
            href = await link.get_attribute('href')
            logger.info(f"URL: {href}")
            
            # Try to get title from img alt
            try:
                img = await link.query_selector('img[alt]')
                if img:
                    alt = await img.get_attribute('alt')
                    logger.info(f"✅ Title (img alt): {alt}")
            except:
                pass
            
            # Try different parent levels
            for level in range(1, 6):
                logger.info(f"\n🔍 Parent Level {level}:")
                
                try:
                    parent = link
                    for _ in range(level):
                        parent = await parent.evaluate_handle('el => el.parentElement')
                    
                    # Get parent HTML (first 500 chars)
                    html = await parent.evaluate('el => el.outerHTML')
                    logger.info(f"  HTML snippet: {html[:200]}...")
                    
                    # Get parent text
                    text = await parent.inner_text()
                    lines = [l.strip() for l in text.split('\n') if l.strip()]
                    logger.info(f"  Text lines ({len(lines)} total):")
                    for line in lines[:10]:
                        if len(line) < 100:
                            has_price = '$' in line
                            marker = "💰" if has_price else "  "
                            logger.info(f"    {marker} {line}")
                    
                    # Try price selectors
                    price_selectors = [
                        'span[class*="price"]',
                        '[class*="price"]',
                        'span',
                        'div'
                    ]
                    
                    for sel in price_selectors:
                        try:
                            els = await parent.query_selector_all(sel)
                            for el in els[:5]:
                                el_text = (await el.inner_text()).strip()
                                if '$' in el_text and len(el_text) < 30:
                                    logger.info(f"  💰 Found via {sel}: {el_text}")
                                    break
                        except:
                            pass
                    
                except Exception as e:
                    logger.info(f"  ❌ Error: {e}")
            
            logger.info("")
        
        logger.info(f"\n{'='*80}")
        logger.info("ANALYSIS COMPLETE")
        logger.info(f"{'='*80}")
        
        # Try to find the optimal parent level
        logger.info("\n🔬 TESTING OPTIMAL EXTRACTION STRATEGY")
        
        links = await page.query_selector_all('a[href*="/dp/"]')
        success_count = 0
        
        for link in links[:10]:
            try:
                # Get title
                img = await link.query_selector('img[alt]')
                title = await img.get_attribute('alt') if img else None
                
                # Try to get price - test different strategies
                price = None
                
                # Strategy 1: Parent level 4 text search
                parent = link
                for _ in range(4):
                    parent = await parent.evaluate_handle('el => el.parentElement')
                
                text = await parent.inner_text()
                import re
                for line in text.split('\n'):
                    if '$' in line and len(line.strip()) < 30:
                        match = re.search(r'\$\s*\d+\.?\d*', line)
                        if match:
                            price = match.group()
                            break
                
                if title and price:
                    success_count += 1
                    
            except:
                pass
        
        logger.info(f"\n📊 Extraction Success Rate: {success_count}/10 ({success_count*10}%)")
        logger.info(f"Strategy: Parent level 4, regex text search")
        
        await asyncio.sleep(2)
        
    finally:
        await playwright.stop()

if __name__ == '__main__':
    asyncio.run(debug_revolve())

