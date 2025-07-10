"""
Test Markdown Extractor System - Comprehensive validation
Tests markdown extraction for ASOS, Mango, Uniqlo, Revolve, H&M with fallback handling
"""
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


import asyncio
import json
from typing import Dict, List
from logger_config import setup_logging
from markdown_extractor import MarkdownExtractor

logger = setup_logging(__name__)

# Test URLs for each supported retailer
TEST_URLS = {
    "asos": [
        "https://www.asos.com/us/nike/nike-club-fleece-hoodie-in-dark-gray-heather/prd/204295151",
        "https://www.asos.com/us/adidas-originals/adidas-originals-adicolor-classics-3-stripes-track-top-in-black/prd/205098765"
    ],
    "mango": [
        "https://shop.mango.com/us/women/coats-coats/oversized-wool-coat_17035931.html",
        "https://shop.mango.com/us/women/tops-sweatshirts/cotton-sweatshirt_17020933.html"
    ],
    "uniqlo": [
        "https://www.uniqlo.com/us/en/products/E449220-000",
        "https://www.uniqlo.com/us/en/products/E460166-000"
    ],
    "revolve": [
        "https://www.revolve.com/by-anthropologie-tularosa-maya-dress/dp/TULA-WD1685/",
        "https://www.revolve.com/lovers-friends-luna-sweater/dp/LOVF-WK1879/"
    ],
    "hm": [
        "https://www2.hm.com/en_us/productpage.0970819001.html",
        "https://www2.hm.com/en_us/productpage.1074406001.html"
    ]
}

class MarkdownExtractorTester:
    def __init__(self):
        self.markdown_extractor = MarkdownExtractor()
        self.test_results = {}
        
    async def run_comprehensive_tests(self):
        """Run all tests and generate comprehensive report"""
        
        logger.info("🚀 Starting Markdown Extractor Comprehensive Tests")
        print("=" * 80)
        print("MARKDOWN EXTRACTOR TEST SUITE")
        print("=" * 80)
        
        # Test 1: System initialization
        await self._test_initialization()
        
        # Test 2: Retailer routing
        await self._test_retailer_routing()
        
        # Test 3: Individual retailer extraction
        await self._test_individual_retailers()
        
        # Test 4: Fallback behavior
        await self._test_fallback_behavior()
        
        # Test 5: Validation and quality assessment
        await self._test_validation_system()
        
        # Test 6: Cache functionality
        await self._test_cache_functionality()
        
        # Generate final report
        await self._generate_final_report()
    
    async def _test_initialization(self):
        """Test markdown extractor initialization"""
        
        print("\n🔧 TEST 1: SYSTEM INITIALIZATION")
        print("-" * 50)
        
        try:
            stats = await self.markdown_extractor.get_stats()
            
            print(f"✅ Supported retailers: {stats['supported_retailers']}")
            print(f"✅ DeepSeek enabled: {stats['deepseek_enabled']}")
            print(f"✅ Cache expiry: {stats['cache_expiry_days']} days")
            print(f"✅ Cache size: {stats['cache_size']} entries")
            
            self.test_results['initialization'] = {
                'status': 'PASSED',
                'supported_retailers': stats['supported_retailers'],
                'deepseek_enabled': stats['deepseek_enabled']
            }
            
        except Exception as e:
            print(f"❌ Initialization failed: {e}")
            self.test_results['initialization'] = {
                'status': 'FAILED',
                'error': str(e)
            }
    
    async def _test_retailer_routing(self):
        """Test retailer routing logic"""
        
        print("\n🔀 TEST 2: RETAILER ROUTING")
        print("-" * 50)
        
        test_retailers = [
            ("asos", True),
            ("mango", True), 
            ("uniqlo", True),
            ("revolve", True),
            ("hm", True),
            ("nordstrom", False),
            ("aritzia", False),
            ("anthropologie", False)
        ]
        
        routing_results = {}
        
        for retailer, should_support in test_retailers:
            is_supported = self.markdown_extractor.is_supported_retailer(retailer)
            
            if is_supported == should_support:
                print(f"✅ {retailer}: {'Supported' if is_supported else 'Not supported'} (correct)")
                routing_results[retailer] = 'PASSED'
            else:
                print(f"❌ {retailer}: Expected {'supported' if should_support else 'not supported'}, got {'supported' if is_supported else 'not supported'}")
                routing_results[retailer] = 'FAILED'
        
        self.test_results['routing'] = routing_results
    
    async def _test_individual_retailers(self):
        """Test extraction for each supported retailer"""
        
        print("\n🛍️ TEST 3: INDIVIDUAL RETAILER EXTRACTION")
        print("-" * 50)
        
        self.test_results['individual_extraction'] = {}
        
        for retailer, urls in TEST_URLS.items():
            print(f"\nTesting {retailer.upper()}:")
            print("-" * 30)
            
            retailer_results = []
            
            for i, url in enumerate(urls[:1]):  # Test first URL only for speed
                print(f"  Testing URL {i+1}: {url}")
                
                try:
                    result = await self.markdown_extractor.extract_product_data(url, retailer)
                    
                    if result.success:
                        print(f"    ✅ Success in {result.processing_time:.2f}s")
                        print(f"    📦 Title: {result.data.get('title', 'N/A')[:60]}...")
                        print(f"    💰 Price: {result.data.get('price', 'N/A')}")
                        print(f"    🖼️ Images: {len(result.data.get('image_urls', []))} found")
                        
                        # Validate required fields
                        validation_score = self._calculate_validation_score(result.data, retailer)
                        print(f"    📊 Validation Score: {validation_score}/10")
                        
                        retailer_results.append({
                            'url': url,
                            'status': 'SUCCESS',
                            'processing_time': result.processing_time,
                            'validation_score': validation_score,
                            'data': result.data
                        })
                    else:
                        print(f"    ❌ Failed: {result.errors}")
                        print(f"    ⚠️ Should fallback: {result.should_fallback}")
                        
                        retailer_results.append({
                            'url': url,
                            'status': 'FAILED',
                            'errors': result.errors,
                            'should_fallback': result.should_fallback
                        })
                
                except Exception as e:
                    print(f"    💥 Exception: {e}")
                    retailer_results.append({
                        'url': url,
                        'status': 'EXCEPTION',
                        'error': str(e)
                    })
            
            self.test_results['individual_extraction'][retailer] = retailer_results
    
    async def _test_fallback_behavior(self):
        """Test fallback behavior with invalid URLs"""
        
        print("\n🔄 TEST 4: FALLBACK BEHAVIOR")
        print("-" * 50)
        
        # Test invalid URLs that should trigger fallback
        fallback_tests = [
            ("asos", "https://www.asos.com/invalid-product-url"),
            ("mango", "https://shop.mango.com/invalid-url"),
            ("uniqlo", "https://www.uniqlo.com/us/en/products/INVALID")
        ]
        
        fallback_results = {}
        
        for retailer, invalid_url in fallback_tests:
            print(f"\nTesting fallback for {retailer}")
            
            try:
                result = await self.markdown_extractor.extract_product_data(invalid_url, retailer)
                
                if result.should_fallback:
                    print(f"✅ Correctly identified need for fallback")
                    fallback_results[retailer] = 'PASSED'
                else:
                    print(f"❌ Failed to identify need for fallback")
                    fallback_results[retailer] = 'FAILED'
                    
            except Exception as e:
                print(f"💥 Exception in fallback test: {e}")
                fallback_results[retailer] = 'EXCEPTION'
        
        self.test_results['fallback'] = fallback_results
    
    async def _test_validation_system(self):
        """Test validation and quality assessment"""
        
        print("\n🔍 TEST 5: VALIDATION SYSTEM")
        print("-" * 50)
        
        # Test validation with mock data
        mock_data_tests = [
            # Good data
            {
                'data': {
                    'title': 'Nike Air Max 90 Sneakers',
                    'brand': 'Nike',
                    'price': '$120.00',
                    'image_urls': ['https://example.com/img1.jpg', 'https://example.com/img2.jpg'],
                    'stock_status': 'in stock',
                    'sale_status': 'not on sale'
                },
                'retailer': 'asos',
                'expected': 'valid'
            },
            # Missing required fields
            {
                'data': {
                    'title': '',
                    'price': '',
                    'image_urls': []
                },
                'retailer': 'asos',
                'expected': 'invalid'
            },
            # Invalid price format
            {
                'data': {
                    'title': 'Test Product',
                    'price': 'invalid price',
                    'image_urls': ['https://example.com/img.jpg']
                },
                'retailer': 'uniqlo',
                'expected': 'invalid'
            }
        ]
        
        validation_results = []
        
        for i, test in enumerate(mock_data_tests):
            issues = self.markdown_extractor._validate_extracted_data(
                test['data'], test['retailer'], "https://example.com"
            )
            
            has_issues = len(issues) > 0
            expected_invalid = test['expected'] == 'invalid'
            
            if has_issues == expected_invalid:
                print(f"✅ Validation test {i+1}: PASSED")
                validation_results.append('PASSED')
            else:
                print(f"❌ Validation test {i+1}: FAILED")
                print(f"   Expected: {'invalid' if expected_invalid else 'valid'}")
                print(f"   Got: {'invalid' if has_issues else 'valid'}")
                print(f"   Issues: {issues}")
                validation_results.append('FAILED')
        
        self.test_results['validation'] = validation_results
    
    async def _test_cache_functionality(self):
        """Test markdown caching system"""
        
        print("\n💾 TEST 6: CACHE FUNCTIONALITY")
        print("-" * 50)
        
        # Test cache with a simple URL
        test_url = "https://www.uniqlo.com/us/en/products/E449220-000"
        
        try:
            # First request (should cache)
            print("Making first request (should cache)...")
            start_time = asyncio.get_event_loop().time()
            result1 = await self.markdown_extractor.extract_product_data(test_url, "uniqlo")
            first_time = asyncio.get_event_loop().time() - start_time
            
            # Second request (should use cache)
            print("Making second request (should use cache)...")
            start_time = asyncio.get_event_loop().time()
            result2 = await self.markdown_extractor.extract_product_data(test_url, "uniqlo")
            second_time = asyncio.get_event_loop().time() - start_time
            
            # Cache should make second request faster
            if second_time < first_time * 0.5:  # At least 50% faster
                print(f"✅ Cache working: First={first_time:.2f}s, Second={second_time:.2f}s")
                self.test_results['cache'] = 'PASSED'
            else:
                print(f"❌ Cache not effective: First={first_time:.2f}s, Second={second_time:.2f}s")
                self.test_results['cache'] = 'FAILED'
                
        except Exception as e:
            print(f"💥 Cache test failed: {e}")
            self.test_results['cache'] = 'EXCEPTION'
    
    def _calculate_validation_score(self, data: Dict, retailer: str) -> int:
        """Calculate validation score for extracted data (0-10)"""
        
        score = 0
        
        # Required fields (3 points each)
        if data.get('title') and len(data['title']) > 5:
            score += 3
        if data.get('price'):
            score += 3
        if data.get('image_urls') and len(data['image_urls']) > 0:
            score += 3
        
        # Quality indicators (1 point each) 
        if data.get('brand'):
            score += 1
        if data.get('description'):
            score += 1
        if data.get('stock_status') in ['in stock', 'low in stock', 'out of stock']:
            score += 1
        if data.get('sale_status') in ['on sale', 'not on sale']:
            score += 1
        
        # Bonus for multiple images
        if len(data.get('image_urls', [])) >= 3:
            score += 1
        
        # Bonus for product code
        if data.get('product_code'):
            score += 1
        
        return min(score, 10)  # Cap at 10
    
    async def _generate_final_report(self):
        """Generate comprehensive test report"""
        
        print("\n📊 FINAL TEST REPORT")
        print("=" * 80)
        
        # Calculate overall statistics
        total_tests = 0
        passed_tests = 0
        
        # Count results
        for test_category, results in self.test_results.items():
            if test_category == 'individual_extraction':
                for retailer, retailer_results in results.items():
                    for result in retailer_results:
                        total_tests += 1
                        if result['status'] == 'SUCCESS':
                            passed_tests += 1
            elif test_category == 'routing':
                for retailer, status in results.items():
                    total_tests += 1
                    if status == 'PASSED':
                        passed_tests += 1
            elif test_category == 'validation':
                for status in results:
                    total_tests += 1
                    if status == 'PASSED':
                        passed_tests += 1
            else:
                total_tests += 1
                if results in ['PASSED'] or (isinstance(results, dict) and results.get('status') == 'PASSED'):
                    passed_tests += 1
        
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        print(f"📈 Overall Success Rate: {success_rate:.1f}% ({passed_tests}/{total_tests})")
        print()
        
        # Detailed breakdown
        for test_category, results in self.test_results.items():
            print(f"🔍 {test_category.upper().replace('_', ' ')}:")
            
            if test_category == 'individual_extraction':
                for retailer, retailer_results in results.items():
                    successful = sum(1 for r in retailer_results if r['status'] == 'SUCCESS')
                    total = len(retailer_results)
                    print(f"  {retailer}: {successful}/{total} successful")
                    
                    for result in retailer_results:
                        if result['status'] == 'SUCCESS':
                            score = result.get('validation_score', 0)
                            print(f"    ✅ Score: {score}/10, Time: {result.get('processing_time', 0):.2f}s")
                        else:
                            print(f"    ❌ {result['status']}")
            else:
                print(f"  {results}")
            print()
        
        # Recommendations
        print("📋 RECOMMENDATIONS:")
        
        if success_rate >= 80:
            print("✅ System performing well - ready for production use")
        elif success_rate >= 60:
            print("⚠️ System needs some tuning but functional")
        else:
            print("❌ System needs significant improvements before production")
        
        print()
        print("🎯 NEXT STEPS:")
        print("1. Review failed extractions and improve prompts")
        print("2. Test with more diverse product URLs")
        print("3. Monitor cache performance in production")
        print("4. Set up automated testing pipeline")
        
        # Save detailed results
        with open('markdown_extractor_test_results.json', 'w') as f:
            json.dump(self.test_results, f, indent=2, default=str)
        
        print(f"\n💾 Detailed results saved to: markdown_extractor_test_results.json")

async def main():
    """Run the comprehensive markdown extractor test suite"""
    
    tester = MarkdownExtractorTester()
    await tester.run_comprehensive_tests()

if __name__ == "__main__":
    asyncio.run(main()) 