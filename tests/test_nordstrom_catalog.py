"""
Test script for Nordstrom catalog extraction using Patchright Tower
Tests the PatchrightCatalogExtractor for catalog page extraction

CRITICAL NOTES:
- Nordstrom uses Patchright (browser automation + AI vision)
- Very high anti-bot complexity (most complex retailer)
- Catalog page has ads mixed into product grid
- This test is SLOW (2-5 minutes expected) and costs ~$0.10-0.20 per run
"""

import sys
import os
import asyncio
import time
from datetime import datetime
from urllib.parse import urlparse

# Add parent directory to path for imports
parent_dir = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(parent_dir)

# Add Extraction directories to path
patchright_dir = os.path.join(parent_dir, "Extraction", "Patchright")
sys.path.append(patchright_dir)

from Extraction.Patchright.patchright_catalog_extractor import PatchrightCatalogExtractor

# Test configuration
RETAILER = "nordstrom"
TEST_URL = "https://www.nordstrom.com/browse/women/clothing/dresses"
EXPECTED_MIN_PRODUCTS = 45
EXPECTED_MAX_PRODUCTS = 70
EXPECTED_TIME_MIN = 120  # 2 minutes
EXPECTED_TIME_MAX = 300  # 5 minutes


async def test_nordstrom_catalog_extraction():
    """Test Nordstrom catalog extraction with Patchright Tower"""
    
    print("=" * 70)
    print("NORDSTROM PATCHRIGHT CATALOG EXTRACTION TEST")
    print("=" * 70)
    print()
    print("⚠️  IMPORTANT NOTES:")
    print("   - Nordstrom uses Patchright tower (browser automation + AI vision)")
    print("   - This test is MUCH SLOWER than Markdown tests (2-5 minutes expected)")
    print("   - Nordstrom injects ads into the product grid")
    print("   - Expected: ~58 real products + 4-8 ads = ~62-66 total cards")
    print("   - Goal: Extract only real products, filter out ads")
    print("   - Anti-bot complexity: Very High (most complex retailer)")
    print("   - Cost: ~$0.10-0.20 per test run (Gemini Vision API)")
    print("   - Please be patient - this test may take several minutes")
    print()
    print(f"Test URL: {TEST_URL}")
    print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    start_time = time.time()
    extractor = None
    
    try:
        # Initialize extractor
        print("📦 Initializing PatchrightCatalogExtractor...")
        print("   (This may launch a browser window - this is normal)")
        extractor = PatchrightCatalogExtractor()
        print("✅ Extractor initialized")
        print()
        
        # Run extraction
        print("🚀 Starting Patchright catalog extraction...")
        print("   Step 1: Launching browser...")
        print("   Step 2: Navigating to catalog page...")
        print("   Step 3: Waiting for products to load...")
        print("   Step 4: Taking full-page screenshot...")
        print("   Step 5: Gemini Vision analyzing image...")
        print("   Step 6: DOM extracting URLs...")
        print("   Step 7: Merging and validating results...")
        print()
        print("⏱️  This will take 2-5 minutes (120-300 seconds)...")
        print("⏱️  Please be patient - Patchright is thorough but slow")
        print("⏱️  Nordstrom's anti-bot measures add significant delay")
        print()
        
        catalog_prompt = """Extract all dress products from this Nordstrom catalog page.
For each product, extract:
- Title
- Price
- Image URL (if visible)
- Sale status (on_sale or regular)

Return as a JSON array of products.
Note: Ignore advertisement cards - only extract actual product listings."""
        
        result = await extractor.extract_catalog(
            catalog_url=TEST_URL,
            retailer=RETAILER,
            catalog_prompt=catalog_prompt
        )
        
        # Calculate elapsed time
        elapsed_time = time.time() - start_time
        
        print()
        print("=" * 70)
        print("TEST RESULTS")
        print("=" * 70)
        
        # Extract results
        success = result.get('success', False)
        products = result.get('products', [])
        total_found = len(products)
        method_used = result.get('method_used', 'unknown')
        processing_time = result.get('processing_time', elapsed_time)
        warnings = result.get('warnings', [])
        errors = result.get('errors', [])
        
        # AD DETECTION AND FILTERING LOGIC
        potential_ads = []
        for i, product in enumerate(products):
            url = product.get('url', '')
            title = product.get('title', '').lower()
            
            # Ad detection heuristics:
            # 1. URL doesn't contain '/s/' (Nordstrom product URLs have /s/)
            # 2. Title contains advertising keywords
            # 3. Missing price (ads often don't have prices)
            
            is_potential_ad = False
            ad_reasons = []
            
            if url and '/s/' not in url:
                is_potential_ad = True
                ad_reasons.append("URL missing /s/ pattern")
            
            # Only flag as ad if title is MOSTLY promotional text, not just contains one word
            ad_patterns = ['shop now', 'shop all', 'shop the', 'save now', 'discover our', 'explore our', 'advertisement']
            if any(pattern in title for pattern in ad_patterns):
                is_potential_ad = True
                ad_reasons.append(f"Ad-like keywords in title")
            
            # Also flag if title is suspiciously short (< 10 chars) and has generic words
            if len(title) < 10 and any(word in title for word in ['sale', 'shop', 'ad']):
                is_potential_ad = True
                ad_reasons.append(f"Short generic title")
            
            if not product.get('price') or product.get('price') == 0:
                is_potential_ad = True
                ad_reasons.append("Missing price")
            
            if is_potential_ad:
                potential_ads.append({
                    'index': i + 1,
                    'title': product.get('title', 'N/A'),
                    'url': url,
                    'reasons': ad_reasons
                })
        
        # Filter out ads
        ad_indices = {ad['index'] - 1 for ad in potential_ads}
        filtered_products = [p for i, p in enumerate(products) if i not in ad_indices]
        
        filtered_count = len(filtered_products)
        ads_detected = len(potential_ads)
        
        # Determine PASS/FAIL
        products_in_acceptable_range = EXPECTED_MIN_PRODUCTS <= filtered_count <= EXPECTED_MAX_PRODUCTS
        test_passed = success and products_in_acceptable_range
        
        status = "PASS" if test_passed else "FAIL"
        
        print(f"Status: {status}")
        print()
        print("📊 Extraction Metrics:")
        print(f"   Total Cards Extracted: {total_found}")
        print(f"   Ads Detected: {ads_detected}")
        print(f"   Real Products (filtered): {filtered_count}")
        print(f"   Expected Range: 50-65 products")
        print(f"   Minimum for PASS: {EXPECTED_MIN_PRODUCTS} products")
        print(f"   Processing Time: {processing_time:.2f} seconds")
        print(f"   Method Used: {method_used}")
        print(f"   Warnings: {len(warnings)}")
        print(f"   Errors: {len(errors)}")
        
        # Sample products display (first 5)
        if filtered_products:
            print()
            print("📦 Sample Products (first 5 after ad filtering):")
            print()
            for i, product in enumerate(filtered_products[:5], 1):
                title = product.get('title', 'N/A')
                price = product.get('price', 'N/A')
                url = product.get('url', 'N/A')
                
                # Format price
                if isinstance(price, (int, float)):
                    price_str = f"${price:.2f}"
                else:
                    price_str = str(price)
                
                # Truncate URL for readability
                url_display = url[:60] + "..." if len(url) > 60 else url
                
                print(f"  {i}. {title}")
                print(f"     Price: {price_str}")
                print(f"     URL: {url_display}")
                print()
        else:
            print()
            print("⚠️  No products extracted after filtering")
            print()
        
        # Ad detection report
        if potential_ads:
            print()
            print("🚨 ADVERTISEMENT DETECTION REPORT:")
            print(f"   Detected {len(potential_ads)} potential ads/non-products")
            print()
            for ad in potential_ads[:3]:  # Show first 3
                print(f"   Card #{ad['index']}:")
                print(f"      Title: {ad['title']}")
                print(f"      Reasons: {', '.join(ad['reasons'])}")
                print()
            if len(potential_ads) > 3:
                print(f"   ... and {len(potential_ads) - 3} more")
                print()
        
        # Validation analysis
        print()
        print("=" * 70)
        print("VALIDATION ANALYSIS")
        print("=" * 70)
        print()
        
        validation_issues = []
        
        # Check 1: Are URLs valid Nordstrom URLs?
        non_nordstrom_urls = [p for p in filtered_products if 'nordstrom.com' not in p.get('url', '')]
        if non_nordstrom_urls:
            validation_issues.append(f"Found {len(non_nordstrom_urls)} non-Nordstrom URLs")
            print(f"⚠️  {len(non_nordstrom_urls)} products have non-Nordstrom URLs")
        else:
            print("✅ All product URLs are from nordstrom.com")
        
        # Check 2: Are prices reasonable?
        price_issues = [p for p in filtered_products if p.get('price', 0) < 10 or p.get('price', 0) > 1000]
        if price_issues:
            validation_issues.append(f"Found {len(price_issues)} products with unusual prices")
            print(f"⚠️  {len(price_issues)} products have unusual prices (< $10 or > $1000)")
        else:
            print("✅ All prices are in reasonable range ($10-$1000)")
        
        # Check 3: Are titles complete?
        empty_titles = [p for p in filtered_products if not p.get('title') or len(p.get('title', '')) < 5]
        if empty_titles:
            validation_issues.append(f"Found {len(empty_titles)} products with missing/short titles")
            print(f"⚠️  {len(empty_titles)} products have missing or very short titles")
        else:
            print("✅ All products have complete titles")
        
        # Check 4: Method switching
        if 'gemini' in method_used.lower():
            print(f"ℹ️  Used {method_used} (Patchright standard)")
        elif 'fallback' in method_used.lower():
            print(f"⚠️  Method fallback occurred: {method_used}")
            validation_issues.append("LLM fallback occurred")
        
        # Check 5: Ad filtering effectiveness
        ad_ratio = (ads_detected / total_found * 100) if total_found > 0 else 0
        print(f"ℹ️  Ad detection rate: {ad_ratio:.1f}% ({ads_detected}/{total_found} cards)")
        if ad_ratio > 20:
            print(f"⚠️  Warning: Ad detection rate seems high (> 20%)")
            validation_issues.append(f"High ad detection rate: {ad_ratio:.1f}%")
        
        # Error and warning display
        if warnings:
            print()
            print("⚠️  Warnings:")
            for warning in warnings:
                print(f"   - {warning}")
        
        if errors:
            print()
            print("❌ Errors:")
            for error in errors:
                print(f"   - {error}")
        
        # Anti-bot and performance analysis
        print()
        print("=" * 70)
        print("ANTI-BOT & PERFORMANCE ANALYSIS")
        print("=" * 70)
        print()
        
        # Processing time analysis
        processing_minutes = processing_time / 60
        if processing_time < 120:
            print(f"⚡ Very fast extraction: {processing_minutes:.1f} minutes ({processing_time:.0f}s)")
            print("   → May indicate incomplete page load or anti-bot blocking")
        elif processing_time < 180:
            print(f"✅ Normal extraction speed: {processing_minutes:.1f} minutes ({processing_time:.0f}s)")
        elif processing_time < 300:
            print(f"⏱️  Slower extraction: {processing_minutes:.1f} minutes ({processing_time:.0f}s)")
            print("   → May have encountered verification or loading delays")
        else:
            print(f"🐌 Very slow extraction: {processing_minutes:.1f} minutes ({processing_time:.0f}s)")
            print("   → Likely multiple retries or verification challenges")
            print("   → This is still acceptable for Nordstrom's complexity")
        
        # Product count analysis
        if filtered_count == 0:
            print()
            print("🚨 ZERO PRODUCTS EXTRACTED")
            print("   Possible causes:")
            print("   → Nordstrom blocked the request (anti-bot)")
            print("   → Page structure changed")
            print("   → All cards were detected as ads (over-filtering)")
            print("   → Verification challenge failed")
        elif filtered_count < 30:
            print()
            print(f"⚠️  VERY FEW PRODUCTS: {filtered_count}")
            print("   Possible causes:")
            print("   → Partial anti-bot blocking")
            print("   → Incomplete page load")
            print("   → Over-aggressive ad filtering")
        elif filtered_count > 70:
            print()
            print(f"⚠️  TOO MANY PRODUCTS: {filtered_count}")
            print("   Possible causes:")
            print("   → Ads not being filtered properly")
            print("   → Duplicate detection not working")
            print("   → Page loaded multiple times")
        
        # Final summary and recommendations
        print()
        print("=" * 70)
        print("FINAL SUMMARY")
        print("=" * 70)
        print()
        
        if test_passed:
            print("✅ TEST PASSED!")
            print(f"   Nordstrom catalog extraction is working correctly")
            print(f"   Successfully extracted {filtered_count} products")
            if ads_detected > 0:
                print(f"   Successfully filtered out {ads_detected} ads")
        elif filtered_count < EXPECTED_MIN_PRODUCTS:
            print("❌ TEST FAILED: Too few products extracted")
            print(f"   Expected: {EXPECTED_MIN_PRODUCTS}+ products")
            print(f"   Got: {filtered_count} products")
            print()
            print("   Recommended actions:")
            print("   1. Check if Nordstrom changed their site structure")
            print("   2. Review ad filtering logic (may be too aggressive)")
            print("   3. Check for anti-bot blocking in logs")
            print("   4. Try running test again (may be temporary issue)")
        elif not success:
            print("❌ TEST FAILED: Extraction did not succeed")
            print("   Check errors above for details")
        else:
            print(f"❌ TEST FAILED: Unexpected issue")
            print(f"   Success: {success}, Products: {filtered_count}")
        
        if validation_issues:
            print()
            print("⚠️  Validation issues found:")
            for issue in validation_issues:
                print(f"   - {issue}")
        
        print()
        print("=" * 70)
        
        return test_passed
        
    except Exception as e:
        elapsed_time = time.time() - start_time
        print()
        print("=" * 70)
        print("❌ FATAL ERROR OCCURRED")
        print("=" * 70)
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        print(f"Time elapsed before error: {elapsed_time:.2f} seconds")
        print()
        print("Full traceback:")
        import traceback
        traceback.print_exc()
        print()
        print("=" * 70)
        print("TROUBLESHOOTING:")
        print("=" * 70)
        print("1. Check if browser launched successfully")
        print("2. Check if Nordstrom.com is accessible")
        print("3. Check for API key issues (Gemini Vision required)")
        print("4. Check logs for detailed error information")
        print("5. Try running with a simpler retailer first (Abercrombie)")
        print("=" * 70)
        return False
        
    finally:
        # Cleanup
        if extractor:
            try:
                print()
                print("🧹 Cleaning up browser resources...")
                await extractor._cleanup()
                print("✅ Browser cleanup complete")
            except Exception as cleanup_error:
                print(f"⚠️  Cleanup error: {cleanup_error}")


if __name__ == "__main__":
    print()
    result = asyncio.run(test_nordstrom_catalog_extraction())
    print()
    sys.exit(0 if result else 1)

