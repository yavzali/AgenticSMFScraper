"""
Test Revolve Container-First Extraction Strategy
Extract from product containers instead of traversing from links
"""
import asyncio
import re
from patchright.async_api import async_playwright
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

async def test_container_strategy():
    """Test container-first approach"""
    
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
        
        logger.info("\n🎯 STRATEGY: Extract from product containers directly")
        logger.info("="*80)
        
        # Find product containers
        containers = await page.query_selector_all('li.plp__product')
        logger.info(f"\nFound {len(containers)} product containers")
        
        # Analyze first 3 containers
        for i, container in enumerate(containers[:3], 1):
            logger.info(f"\n{'='*80}")
            logger.info(f"PRODUCT CONTAINER {i}")
            logger.info(f"{'='*80}")
            
            # Get container ID
            try:
                container_id = await container.get_attribute('id')
                logger.info(f"Container ID: {container_id}")
            except:
                pass
            
            # Get product URL
            try:
                link = await container.query_selector('a[href*="/dp/"]')
                if link:
                    href = await link.get_attribute('href')
                    if href:
                        # Make absolute URL
                        if href.startswith('/'):
                            href = f"https://www.revolve.com{href}"
                        logger.info(f"✅ URL: {href}")
            except Exception as e:
                logger.info(f"❌ URL extraction failed: {e}")
            
            # Get title from img alt
            try:
                img = await container.query_selector('img[alt]')
                if img:
                    alt = await img.get_attribute('alt')
                    if alt and alt.strip() and 'revolve' not in alt.lower():
                        logger.info(f"✅ Title: {alt}")
            except:
                pass
            
            # Get container text (should be just this product)
            try:
                text = await container.inner_text()
                lines = [l.strip() for l in text.split('\n') if l.strip() and len(l.strip()) > 0]
                logger.info(f"\n📝 Container Text ({len(lines)} lines):")
                for line in lines[:15]:
                    if len(line) < 100:
                        has_price = '$' in line
                        marker = "💰" if has_price else "  "
                        logger.info(f"  {marker} {line}")
                
                # Try regex price extraction
                for line in lines:
                    match = re.search(r'\$\s*\d+\.?\d*', line)
                    if match:
                        logger.info(f"\n💰 PRICE FOUND: {match.group()}")
                        break
            except Exception as e:
                logger.info(f"❌ Text extraction failed: {e}")
            
            # Try specific price selectors within container
            logger.info(f"\n🔍 Testing price selectors within container:")
            price_selectors = [
                'span[class*="price"]',
                '[class*="price"]',
                '[data-price]',
                'span.productInfo',
                'div.productInfo',
                'span',
                'div'
            ]
            
            for sel in price_selectors:
                try:
                    els = await container.query_selector_all(sel)
                    found_price = False
                    for el in els[:20]:  # Check first 20 elements
                        el_text = (await el.inner_text()).strip()
                        if '$' in el_text and len(el_text) < 30 and len(el_text) > 0:
                            logger.info(f"  ✅ {sel}: {el_text}")
                            found_price = True
                            break
                    if found_price:
                        break
                except:
                    pass
        
        # Now test full extraction
        logger.info(f"\n\n{'='*80}")
        logger.info("TESTING FULL EXTRACTION ON ALL PRODUCTS")
        logger.info(f"{'='*80}\n")
        
        containers = await page.query_selector_all('li.plp__product')
        success_count = 0
        products = []
        
        for container in containers[:50]:  # Test first 50
            try:
                # Extract URL
                url = None
                link = await container.query_selector('a[href*="/dp/"]')
                if link:
                    href = await link.get_attribute('href')
                    if href:
                        url = f"https://www.revolve.com{href}" if href.startswith('/') else href
                
                # Extract title
                title = None
                img = await container.query_selector('img[alt]')
                if img:
                    alt = await img.get_attribute('alt')
                    if alt and alt.strip() and 'revolve' not in alt.lower():
                        title = alt.strip()
                
                # Extract price
                price = None
                text = await container.inner_text()
                for line in text.split('\n'):
                    match = re.search(r'\$\s*(\d+\.?\d*)', line.strip())
                    if match:
                        price = match.group()
                        break
                
                if url and title and price:
                    success_count += 1
                    products.append({'url': url, 'title': title, 'price': price})
                    
            except Exception as e:
                pass
        
        logger.info(f"📊 Extraction Results:")
        logger.info(f"  Total tested: 50")
        logger.info(f"  Successful: {success_count}")
        logger.info(f"  Success rate: {success_count/50*100:.1f}%")
        
        logger.info(f"\n📦 Sample Products:")
        for i, p in enumerate(products[:5], 1):
            logger.info(f"\n  Product {i}:")
            logger.info(f"    Title: {p['title']}")
            logger.info(f"    Price: {p['price']}")
            logger.info(f"    URL: {p['url'][:80]}...")
        
        await asyncio.sleep(2)
        
    finally:
        await playwright.stop()

if __name__ == '__main__':
    asyncio.run(test_container_strategy())

