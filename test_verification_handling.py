import asyncio
import logging
from agent_extractor import AgentExtractor

# Set up detailed logging to see verification handling in action
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

async def test_verification_handling():
    """Test automatic verification handling on sites with anti-bot protection"""
    
    extractor = AgentExtractor()
    
    # Test cases focusing on sites with verification challenges
    test_cases = [
        {
            "url": "https://www.anthropologie.com/shop/maeve-sleeveless-mini-shift-dress?category=dresses&color=010&type=STANDARD&quantity=1",
            "retailer": "anthropologie",
            "name": "Anthropologie - Press & Hold Verification",
            "expected_verification": "Press & Hold button",
            "success_indicators": ["price", "title", "brand", "image_urls"],
            "min_processing_time": 30,  # Real verification takes time
            "verification_keywords": ["press", "hold", "verification", "human"]
        },
        {
            "url": "https://www.urbanoutfitters.com/shop/hybrid/97-nyc-applique-graphic-baby-tee?category=womens-clothing-sale&color=004&type=REGULAR&quantity=1",
            "retailer": "urban_outfitters", 
            "name": "Urban Outfitters - Press & Hold Verification",
            "expected_verification": "Press & Hold button",
            "success_indicators": ["price", "title", "brand", "image_urls"],
            "min_processing_time": 30,
            "verification_keywords": ["press", "hold", "verification", "human"]
        },
        {
            "url": "https://www.aritzia.com/en/product/contour-long-sleeve/98652.html",
            "retailer": "aritzia",
            "name": "Aritzia - Checkbox + Cloudflare Verification",
            "expected_verification": "Verify human checkbox + Cloudflare tabs",
            "success_indicators": ["price", "title", "brand", "image_urls"],
            "min_processing_time": 20,
            "verification_keywords": ["verify", "human", "cloudflare", "checkbox"]
        }
    ]
    
    print("🔐 Testing ACTUAL Verification Handling (Enhanced Detection)")
    print("="*80)
    print("This test now properly distinguishes between:")
    print("✓ Real verification handling success")
    print("✗ False positives (agent created fallback data)")
    print("✓ Detailed verification attempt analysis")
    print("✓ Actual vs simulated verification detection")
    print()
    
    successful_verifications = 0
    total_tests = len(test_cases)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"{i}. {test_case['name']}")
        print(f"   URL: {test_case['url']}")
        print(f"   Expected: {test_case['expected_verification']}")
        print("   Status: Testing verification handling...")
        
        try:
            result = await extractor.extract_product_data(
                test_case['url'], 
                test_case['retailer']
            )
            
            # Enhanced success detection
            verification_success = analyze_verification_success(result, test_case)
            
            if verification_success["is_real_success"]:
                data = result.data
                print(f"   ✅ REAL VERIFICATION SUCCESS!")
                print(f"   📝 Title: {data.get('title', 'No title')[:60]}...")
                print(f"   💰 Price: {data.get('price', 'N/A')}")
                print(f"   🏪 Brand: {data.get('brand', 'N/A')}")
                print(f"   🖼️  Images: {len(data.get('image_urls', []))} found")
                print(f"   ⏱️  Processing time: {result.processing_time:.2f}s")
                print(f"   🎯 Quality score: {verification_success['quality_score']}/10")
                
                successful_verifications += 1
                
            elif verification_success["is_partial_success"]:
                print(f"   🟡 PARTIAL SUCCESS (verification handling attempted)")
                print(f"   📋 Issues detected: {', '.join(verification_success['issues'])}")
                print(f"   ⏱️  Processing time: {result.processing_time:.2f}s")
                print(f"   🔍 Analysis: {verification_success['analysis']}")
                
            else:
                print(f"   ❌ VERIFICATION HANDLING FAILED")
                print(f"   📋 Failure reasons: {', '.join(verification_success['issues'])}")
                print(f"   🔍 Analysis: {verification_success['analysis']}")
                
                # More detailed failure analysis
                if "fallback_data" in verification_success['issues']:
                    print(f"   ⚠️  Agent created fallback data instead of real extraction")
                if "insufficient_processing_time" in verification_success['issues']:
                    print(f"   ⚠️  Processing too fast ({result.processing_time:.1f}s) - likely no verification encountered")
                if "repeated_actions" in verification_success['issues']:
                    print(f"   ⚠️  Agent got stuck in verification loop")
                    
        except Exception as e:
            print(f"   💥 SYSTEM ERROR: {str(e)}")
            print(f"   🔍 This indicates a technical failure, not verification failure")
            
        print()  # Add spacing between tests
    
    print("="*80)
    print(f"🔐 ENHANCED Verification Handling Test Results:")
    print(f"   Real verification successes: {successful_verifications}/{total_tests}")
    print(f"   Actual success rate: {(successful_verifications/total_tests)*100:.1f}%")
    print()
    
    if successful_verifications == 0:
        print("🚨 VERIFICATION HANDLING NOT WORKING")
        print("   The system is not actually handling verification challenges.")
        print("   Current implementation appears to be prompt-based only.")
        print("   Browser Use agent may not support actual press-and-hold actions.")
        print()
        print("🔧 Recommended fixes:")
        print("   • Implement actual mouse press-and-hold in Browser Use")
        print("   • Add verification element detection logic")
        print("   • Test with visual browser to confirm actions")
        print("   • Consider alternative verification handling approaches")
        
    elif successful_verifications < total_tests:
        print(f"⚠️  PARTIAL VERIFICATION HANDLING")
        print(f"   {total_tests - successful_verifications} sites still need work")
        print("   Some verification types may not be fully implemented")
        
    else:
        print("🎉 ALL VERIFICATION CHALLENGES SUCCESSFULLY HANDLED!")
        print("   The system is properly detecting and handling verification")

def analyze_verification_success(result, test_case) -> dict:
    """Analyze whether verification was actually handled successfully"""
    
    analysis = {
        "is_real_success": False,
        "is_partial_success": False,
        "quality_score": 0,
        "issues": [],
        "analysis": ""
    }
    
    if not result.success:
        analysis["issues"].append("extraction_failed")
        analysis["analysis"] = "Basic extraction failed"
        return analysis
    
    data = result.data
    
    # Check for fallback/dummy data patterns
    title = data.get('title', '')
    raw_output = data.get('raw_output', '')
    
    # Red flags for fake success
    if any(phrase in title.lower() for phrase in ['extracted by browser use', 'extracted product', 'no title']):
        analysis["issues"].append("fallback_data")
        analysis["quality_score"] -= 3
    
    if 'raw_output' in data and len(str(raw_output)) > len(str(data.get('title', ''))):
        analysis["issues"].append("mostly_raw_output")
        analysis["quality_score"] -= 2
    
    # Check processing time (real verification takes time)
    if result.processing_time < test_case['min_processing_time']:
        analysis["issues"].append("insufficient_processing_time")
        analysis["quality_score"] -= 2
        analysis["analysis"] += f"Too fast ({result.processing_time:.1f}s), likely no verification encountered. "
    
    # Check for verification loop indicators (like the Urban Outfitters case)
    if result.processing_time > 300:  # Over 5 minutes suggests getting stuck
        analysis["issues"].append("possible_verification_loop")
        analysis["quality_score"] -= 3
        analysis["analysis"] += "Very long processing suggests verification loop. "
    
    # Check data quality
    success_indicators = test_case['success_indicators']
    present_indicators = sum(1 for indicator in success_indicators if data.get(indicator))
    
    if present_indicators == 0:
        analysis["issues"].append("no_real_data")
        analysis["quality_score"] -= 4
    elif present_indicators < len(success_indicators) * 0.5:
        analysis["issues"].append("insufficient_data_quality")
        analysis["quality_score"] -= 2
    else:
        analysis["quality_score"] += present_indicators
    
    # Check for actual price data (strong indicator of real extraction)
    price = data.get('price')
    if price and isinstance(price, (int, float)) and price > 0:
        analysis["quality_score"] += 3
        analysis["analysis"] += "Real price data found. "
    elif price:
        analysis["quality_score"] += 1
        analysis["analysis"] += "Price field present but format unclear. "
    
    # Check for actual image URLs
    image_urls = data.get('image_urls', [])
    if len(image_urls) >= 3:
        analysis["quality_score"] += 2
        analysis["analysis"] += "Multiple high-quality images found. "
    elif len(image_urls) > 0:
        analysis["quality_score"] += 1
    
    # Check for specific retailer data patterns
    retailer = test_case['retailer']
    if retailer == 'aritzia' and 'CAD' in str(data.get('price', '')):
        analysis["quality_score"] += 1
    elif retailer == 'anthropologie' and data.get('brand') == 'Anthropologie':
        analysis["quality_score"] += 1
    
    # Final determination
    if analysis["quality_score"] >= 6 and len(analysis["issues"]) <= 1:
        analysis["is_real_success"] = True
        analysis["analysis"] += "High confidence real verification success."
    elif analysis["quality_score"] >= 3 and "fallback_data" not in analysis["issues"]:
        analysis["is_partial_success"] = True
        analysis["analysis"] += "Partial success, some verification handling detected."
    else:
        analysis["analysis"] += "Low confidence, likely no real verification handling."
    
    # Cap quality score
    analysis["quality_score"] = min(10, max(0, analysis["quality_score"]))
    
    return analysis

if __name__ == "__main__":
    asyncio.run(test_verification_handling()) 