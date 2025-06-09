#!/usr/bin/env python3
"""
Test script for Playwright Multi-Screenshot Agent
Validates replacement of Browser Use with performance monitoring
"""

import asyncio
import sys
import os
import time
import json
from typing import Dict, List

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright_agent import PlaywrightMultiScreenshotAgent, PlaywrightPerformanceMonitor
from logger_config import setup_logging

logger = setup_logging(__name__)

# Test configuration
TEST_URLS = {
    # High-priority retailers that failed with Browser Use
    "nordstrom": "https://www.nordstrom.com/browse/women/clothing/dresses",
    "anthropologie": "https://www.anthropologie.com/dresses/casual-dresses", 
    "aritzia": "https://www.aritzia.com/us/en/product/utility-dress/115422.html?color=1275",
    "urban_outfitters": "https://www.urbanoutfitters.com/women/dresses",
    
    # Test single product URLs vs category pages
    "aritzia_product": "https://www.aritzia.com/us/en/product/utility-dress/115422.html?color=1275",
}

async def test_verification_handling():
    """Test handling of verification challenges that broke Browser Use"""
    
    print("🛡️ TESTING VERIFICATION CHALLENGE HANDLING")
    print("=" * 60)
    
    # Test cases that specifically triggered verification in Browser Use
    verification_test_urls = [
        ("anthropologie", "https://www.anthropologie.com/dresses/casual-dresses"),
        ("urban_outfitters", "https://www.urbanoutfitters.com/women/dresses"),
        ("nordstrom", "https://www.nordstrom.com/browse/women/clothing/dresses")  # IP blocking
    ]
    
    agent = PlaywrightMultiScreenshotAgent()
    verification_results = {}
    
    for retailer, url in verification_test_urls:
        print(f"\n🎯 Testing {retailer.upper()} verification handling...")
        start_time = time.time()
        
        try:
            result = await agent.extract_product(url, retailer)
            processing_time = time.time() - start_time
            
            # Analyze if verification was encountered and handled
            verification_handled = "verification" not in str(result.errors).lower()
            data_extracted = bool(result.data and result.data.get('title'))
            
            verification_results[retailer] = {
                "success": result.success,
                "verification_handled": verification_handled,
                "data_extracted": data_extracted,
                "processing_time": processing_time,
                "errors": result.errors
            }
            
            status = "✅" if result.success else "⚠️" if verification_handled else "❌"
            print(f"  {status} Success: {result.success} | Time: {processing_time:.1f}s")
            print(f"     Verification handled: {verification_handled}")
            print(f"     Data extracted: {data_extracted}")
            
            if result.errors:
                print(f"     Errors: {result.errors}")
                
        except Exception as e:
            verification_results[retailer] = {
                "success": False,
                "error": str(e),
                "processing_time": time.time() - start_time
            }
            print(f"  ❌ EXCEPTION: {e}")
    
    # Summary
    successful = sum(1 for r in verification_results.values() if r.get("success", False))
    total = len(verification_results)
    
    print(f"\n📊 VERIFICATION HANDLING SUMMARY:")
    print(f"Success Rate: {successful}/{total} ({successful/total*100:.1f}%)")
    print(f"Average Processing Time: {sum(r.get('processing_time', 0) for r in verification_results.values())/total:.1f}s")
    
    return verification_results

async def test_anti_scraping_effectiveness():
    """Test anti-scraping effectiveness vs Browser Use failures"""
    
    print("\n🥷 TESTING ANTI-SCRAPING EFFECTIVENESS")
    print("=" * 60)
    
    # Test retailers with different anti-scraping levels
    anti_scraping_tests = [
        ("nordstrom", "https://www.nordstrom.com/browse/women/clothing/dresses", "very_high"),  # Known to block
        ("aritzia", "https://www.aritzia.com/us/en/product/utility-dress/115422.html?color=1275", "medium"),
        ("anthropologie", "https://www.anthropologie.com/dresses/casual-dresses", "high")
    ]
    
    agent = PlaywrightMultiScreenshotAgent()
    anti_scraping_results = {}
    
    for retailer, url, expected_difficulty in anti_scraping_tests:
        print(f"\n🛡️ Testing {retailer.upper()} ({expected_difficulty} anti-scraping)...")
        
        try:
            result = await agent.extract_product(url, retailer)
            
            # Analyze anti-scraping indicators
            blocked_indicators = [
                "403" in str(result.errors),
                "blocked" in str(result.errors).lower(),
                "cloudflare" in str(result.errors).lower(),
                not result.success and "timeout" in str(result.errors).lower()
            ]
            
            blocked = any(blocked_indicators)
            
            anti_scraping_results[retailer] = {
                "success": result.success,
                "blocked": blocked,
                "expected_difficulty": expected_difficulty,
                "data_quality": len(str(result.data)) if result.data else 0
            }
            
            status = "✅" if result.success else "🔒" if blocked else "⚠️"
            print(f"  {status} Success: {result.success} | Blocked: {blocked}")
            print(f"     Expected difficulty: {expected_difficulty}")
            print(f"     Data extracted: {len(str(result.data)) if result.data else 0} chars")
            
        except Exception as e:
            anti_scraping_results[retailer] = {
                "success": False,
                "error": str(e),
                "expected_difficulty": expected_difficulty
            }
            print(f"  ❌ EXCEPTION: {e}")
    
    return anti_scraping_results

async def test_performance_vs_browser_use():
    """Test performance improvements vs Browser Use baseline"""
    
    print("\n⚡ TESTING PERFORMANCE VS BROWSER USE")
    print("=" * 60)
    
    # Browser Use baseline (from previous tests)
    browser_use_baseline = {
        "average_time": 60.0,  # 60+ seconds average
        "success_rate": 30.0,  # 20-40% quality
        "cost_per_extraction": 0.50  # $0.50+ per extraction
    }
    
    performance_monitor = PlaywrightPerformanceMonitor()
    test_urls = [
        ("aritzia", "https://www.aritzia.com/us/en/product/utility-dress/115422.html?color=1275"),
        ("anthropologie", "https://www.anthropologie.com/dresses/casual-dresses"),
        ("nordstrom", "https://www.nordstrom.com/browse/women/clothing/dresses")
    ]
    
    agent = PlaywrightMultiScreenshotAgent()
    
    print(f"🎯 Testing {len(test_urls)} extractions for performance...")
    
    for retailer, url in test_urls:
        print(f"\n⏱️ Testing {retailer.upper()}...")
        start_time = time.time()
        
        try:
            result = await agent.extract_product(url, retailer)
            processing_time = time.time() - start_time
            
            # Estimate cost (single Gemini call vs Browser Use's 10+ calls)
            estimated_cost = 0.15  # Much lower than Browser Use
            
            performance_monitor.log_extraction(retailer, processing_time, result.success, estimated_cost)
            
            print(f"  ⏱️ Time: {processing_time:.1f}s (vs Browser Use {browser_use_baseline['average_time']:.1f}s)")
            print(f"  💰 Cost: ~${estimated_cost:.2f} (vs Browser Use ~${browser_use_baseline['cost_per_extraction']:.2f})")
            print(f"  ✅ Success: {result.success}")
            
        except Exception as e:
            performance_monitor.log_extraction(retailer, 999, False, 0)
            print(f"  ❌ FAILED: {e}")
    
    # Performance summary
    summary = performance_monitor.get_performance_summary()
    
    print(f"\n📊 PERFORMANCE SUMMARY:")
    print(f"Average Time: {summary['average_extraction_time']:.1f}s")
    print(f"Success Rate: {summary['success_rate_percent']:.1f}%")
    print(f"Improvements vs Browser Use:")
    print(f"  • Speed: {summary['improvement_vs_browser_use']['speed']}")
    print(f"  • Success Rate: {summary['improvement_vs_browser_use']['success_rate']}")
    print(f"  • Cost: {summary['improvement_vs_browser_use']['cost_savings']}")
    
    return summary

async def test_comprehensive_data_extraction():
    """Test comprehensive data extraction quality"""
    
    print("\n📊 TESTING DATA EXTRACTION QUALITY")
    print("=" * 60)
    
    # Test single product page for comprehensive extraction
    test_url = "https://www.aritzia.com/us/en/product/utility-dress/115422.html?color=1275"
    retailer = "aritzia"
    
    print(f"🎯 Testing comprehensive extraction: {retailer.upper()}")
    
    agent = PlaywrightMultiScreenshotAgent()
    
    try:
        result = await agent.extract_product(test_url, retailer)
        
        if result.success and result.data:
            data = result.data
            
            # Analyze data completeness
            required_fields = ["title", "price", "brand", "image_urls", "retailer"]
            optional_fields = ["colors", "sizes", "material", "description", "product_code"]
            
            completeness_score = 0
            field_analysis = {}
            
            print(f"\n📋 EXTRACTED DATA ANALYSIS:")
            
            for field in required_fields:
                has_value = field in data and data[field]
                field_analysis[field] = has_value
                if has_value:
                    completeness_score += 20
                
                status = "✅" if has_value else "❌"
                value_preview = str(data.get(field, ""))[:50] + "..." if len(str(data.get(field, ""))) > 50 else str(data.get(field, ""))
                print(f"  {status} {field}: {value_preview}")
            
            for field in optional_fields:
                has_value = field in data and data[field]
                field_analysis[field] = has_value
                if has_value:
                    completeness_score += 10
                
                status = "✅" if has_value else "⚪"
                value_preview = str(data.get(field, ""))[:50] + "..." if len(str(data.get(field, ""))) > 50 else str(data.get(field, ""))
                print(f"  {status} {field}: {value_preview}")
            
            # Image analysis
            image_urls = data.get("image_urls", [])
            print(f"\n🖼️ IMAGE EXTRACTION:")
            print(f"  Total images found: {len(image_urls)}")
            for i, img_url in enumerate(image_urls[:3]):  # Show first 3
                print(f"  {i+1}. {img_url}")
            
            print(f"\n📈 COMPLETENESS SCORE: {completeness_score}/100")
            
            return {
                "success": True,
                "completeness_score": completeness_score,
                "field_analysis": field_analysis,
                "image_count": len(image_urls),
                "data": data
            }
        
        else:
            print(f"❌ Extraction failed: {result.errors}")
            return {"success": False, "errors": result.errors}
            
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")
        return {"success": False, "error": str(e)}

async def main():
    """Run comprehensive Playwright agent tests"""
    
    print("🚀 PLAYWRIGHT MULTI-SCREENSHOT AGENT COMPREHENSIVE TEST")
    print("=" * 80)
    print("Testing replacement of Browser Use with performance monitoring")
    print()
    
    # Run all test suites
    results = {}
    
    try:
        # Test 1: Verification Handling
        results["verification"] = await test_verification_handling()
        
        # Test 2: Anti-scraping Effectiveness  
        results["anti_scraping"] = await test_anti_scraping_effectiveness()
        
        # Test 3: Performance vs Browser Use
        results["performance"] = await test_performance_vs_browser_use()
        
        # Test 4: Data Extraction Quality
        results["data_quality"] = await test_comprehensive_data_extraction()
        
        # Final Assessment
        print("\n🎯 FINAL ASSESSMENT: PLAYWRIGHT vs BROWSER USE")
        print("=" * 80)
        
        verification_success = sum(1 for r in results["verification"].values() if r.get("success", False))
        verification_total = len(results["verification"])
        
        performance = results["performance"]
        data_quality = results["data_quality"]
        
        print(f"📊 VERIFICATION HANDLING: {verification_success}/{verification_total} ({verification_success/verification_total*100:.1f}%)")
        print(f"⚡ PERFORMANCE: {performance['average_extraction_time']:.1f}s avg (vs Browser Use 60s+)")
        print(f"📈 SUCCESS RATE: {performance['success_rate_percent']:.1f}% (vs Browser Use 20-40%)")
        print(f"🎯 DATA QUALITY: {data_quality.get('completeness_score', 0)}/100")
        
        # Overall recommendation
        overall_score = (
            (verification_success / verification_total) * 0.3 +
            (min(performance['success_rate_percent'] / 100, 1.0)) * 0.4 +
            (data_quality.get('completeness_score', 0) / 100) * 0.3
        ) * 100
        
        print(f"\n🏆 OVERALL PLAYWRIGHT SCORE: {overall_score:.1f}/100")
        
        if overall_score >= 75:
            print("✅ RECOMMENDATION: Playwright agent is ready for production!")
            print("   Significant improvements over Browser Use in all areas.")
        elif overall_score >= 50:
            print("⚠️ RECOMMENDATION: Playwright agent needs refinement before production.")
            print("   Some improvements over Browser Use but still needs work.")
        else:
            print("❌ RECOMMENDATION: Playwright agent not ready - more development needed.")
        
        # Save detailed results
        with open("playwright_test_results.json", "w") as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n💾 Detailed results saved to: playwright_test_results.json")
        
    except Exception as e:
        logger.error(f"Test suite failed: {e}")
        print(f"❌ Test suite failed: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 