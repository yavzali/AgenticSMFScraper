"""
Diagnostic script to test DOM extraction for Revolve
Tests what titles/prices can be extracted from the DOM
"""
import asyncio
import sys
import os
import logging

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Extraction', 'Patchright'))

from patchright_catalog_extractor import PatchrightCatalogExtractor

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_dom_extraction():
    """Test Revolve DOM extraction"""
    
    url = "https://www.revolve.com/tops/br/db773d/?navsrc=left&sortBy=newest&vnitems=length_and_mid&vnitems=length_and_long-top&vnitems=neckline_and_round-neck&vnitems=neckline_and_jewel-neck&vnitems=neckline_and_collar&vnitems=neckline_and_v-neck&vnitems=neckline_and_sweetheart&vnitems=neckline_and_turtleneck&vnitems=neckline_and_cowl-neck&vnitems=sleeve_and_long&vnitems=sleeve_and_3_4&loadVisNav=true&pageNumVisNav=1"
    
    extractor = PatchrightCatalogExtractor()
    
    try:
        # Initialize browser
        await extractor._setup_stealth_browser()
        
        # Navigate to page
        logger.info(f"🔄 Loading Revolve tops catalog...")
        await extractor.page.goto(url, wait_until='domcontentloaded', timeout=60000)
        
        # Wait for products
        await asyncio.sleep(10)
        
        # Try to bypass verification if needed
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Shared'))
        from gemini_vision import GeminiVision
        
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Extraction', 'Patchright'))
        from patchright_verification_handler import PatchrightVerificationHandler
        
        gemini = GeminiVision()
        verification_handler = PatchrightVerificationHandler(extractor.page, gemini)
        
        if await verification_handler.is_verification_page():
            logger.info("🛡️ Bypassing verification...")
            await verification_handler.handle_verification()
            await asyncio.sleep(5)
        
        # Extract from DOM
        logger.info("🔍 Extracting from DOM...")
        strategy = {
            'product_selectors': ['a[href*="/dp/"]']
        }
        
        dom_links = await extractor._extract_catalog_product_links_from_dom('revolve', strategy)
        
        logger.info(f"\n📊 DOM EXTRACTION RESULTS:")
        logger.info(f"Total products found: {len(dom_links)}")
        
        # Analyze what data we got
        with_titles = sum(1 for link in dom_links if link.get('dom_title'))
        with_prices = sum(1 for link in dom_links if link.get('dom_price'))
        
        logger.info(f"With titles: {with_titles}/{len(dom_links)} ({with_titles/len(dom_links)*100:.1f}%)")
        logger.info(f"With prices: {with_prices}/{len(dom_links)} ({with_prices/len(dom_links)*100:.1f}%)")
        
        # Show first 5 products
        logger.info(f"\n📦 FIRST 5 PRODUCTS:")
        for i, link in enumerate(dom_links[:5], 1):
            logger.info(f"\nProduct {i}:")
            logger.info(f"  URL: {link['url']}")
            logger.info(f"  Code: {link.get('product_code', 'N/A')}")
            logger.info(f"  Title: {link.get('dom_title', 'NOT FOUND')}")
            logger.info(f"  Price: {link.get('dom_price', 'NOT FOUND')}")
        
        # Now try more aggressive DOM extraction
        logger.info(f"\n\n🔬 TRYING AGGRESSIVE DOM EXTRACTION:")
        
        # Get all product links
        links = await extractor.page.query_selector_all('a[href*="/dp/"]')
        logger.info(f"Found {len(links)} product links")
        
        # Try first link with different selectors
        if links:
            first_link = links[0]
            href = await first_link.get_attribute('href')
            logger.info(f"\nAnalyzing first product: {href}")
            
            # Get parent element
            parent = await first_link.evaluate_handle('el => el.closest("[class*=\\"product\\"]") || el.closest("article") || el.parentElement')
            
            # Try to get HTML to inspect
            html = await parent.evaluate('el => el.outerHTML')
            logger.info(f"\nParent HTML (first 500 chars):\n{html[:500]}")
            
            # Try various title selectors
            logger.info(f"\n📝 Title extraction attempts:")
            title_selectors = [
                'h3', 'h2', '.title', '.product-title', '.name', 
                '[class*="title"]', '[class*="name"]', '[class*="Title"]',
                'span[class*="name"]', 'div[class*="title"]'
            ]
            
            for sel in title_selectors:
                try:
                    el = await parent.query_selector(sel)
                    if el:
                        text = (await el.inner_text()).strip()
                        if text and len(text) > 3:
                            logger.info(f"  ✅ {sel}: {text}")
                        else:
                            logger.info(f"  ⚠️ {sel}: (empty)")
                    else:
                        logger.info(f"  ❌ {sel}: not found")
                except Exception as e:
                    logger.info(f"  ❌ {sel}: error - {e}")
            
            # Try various price selectors
            logger.info(f"\n💰 Price extraction attempts:")
            price_selectors = [
                '.price', '.product-price', '[class*="price"]', '[class*="Price"]',
                'span[class*="price"]', 'div[class*="price"]',
                '[data-testid*="price"]', 'span[class*="Price"]'
            ]
            
            for sel in price_selectors:
                try:
                    el = await parent.query_selector(sel)
                    if el:
                        text = (await el.inner_text()).strip()
                        if text:
                            logger.info(f"  ✅ {sel}: {text}")
                        else:
                            logger.info(f"  ⚠️ {sel}: (empty)")
                    else:
                        logger.info(f"  ❌ {sel}: not found")
                except Exception as e:
                    logger.info(f"  ❌ {sel}: error - {e}")
        
    finally:
        await extractor._cleanup()

if __name__ == '__main__':
    asyncio.run(test_dom_extraction())

