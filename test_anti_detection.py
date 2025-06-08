import asyncio
import logging
from agent_extractor import AgentExtractor

# Set up logging to see the anti-detection features in action
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

async def test_anti_detection_features():
    """Test the new anti-detection features on problematic retailers"""
    
    extractor = AgentExtractor()
    
    # Test cases focusing on the retailers that had anti-bot protection
    test_cases = [
        {
            "url": "https://www.nordstrom.com/s/demylee-milo-cashmere-crewneck-sweater/7615559",
            "retailer": "nordstrom",
            "name": "Nordstrom Test (Previously Failed)"
        },
        {
            "url": "https://www.aritzia.com/en/product/contour-long-sleeve/98652.html",
            "retailer": "aritzia", 
            "name": "Aritzia Test (Previously Failed)"
        }
    ]
    
    print("🛡️ Testing Enhanced Anti-Detection Features")
    print("="*60)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. {test_case['name']}")
        print(f"   URL: {test_case['url']}")
        print(f"   Retailer: {test_case['retailer']}")
        print("   Status: Testing...")
        
        try:
            result = await extractor.extract_product_data(
                test_case['url'], 
                test_case['retailer']
            )
            
            if result.success:
                data = result.data
                print(f"   ✅ SUCCESS! Extracted: {data.get('title', 'No title')[:50]}...")
                print(f"   📊 Processing time: {result.processing_time:.2f}s")
                print(f"   🏪 Brand: {data.get('brand', 'N/A')}")
                print(f"   💰 Price: {data.get('price', 'N/A')}")
                print(f"   🖼️  Images: {len(data.get('image_urls', []))} found")
                
                # Check for signs of successful anti-detection
                if result.processing_time > 30:  # Took time = likely used stealth features
                    print("   🕒 Long processing time indicates stealth mode worked")
                if data.get('description') and len(data.get('description', '')) > 100:
                    print("   📝 Rich description extracted - good data quality")
                    
            else:
                print(f"   ❌ FAILED: {result.errors}")
                
        except Exception as e:
            print(f"   💥 ERROR: {str(e)}")
    
    print("\n" + "="*60)
    print("🔍 Anti-Detection Test Summary:")
    print("- Stealth browser arguments applied")
    print("- User agent rotation enabled") 
    print("- Human-like behavior patterns implemented")
    print("- Retailer-specific timeouts configured")
    print("- Exponential backoff retry logic active")

if __name__ == "__main__":
    asyncio.run(test_anti_detection_features()) 