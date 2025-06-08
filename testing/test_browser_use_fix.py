import asyncio
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_extractor import AgentExtractor

async def test_browser_use_fix():
    """Test if the Browser Use API fix works"""
    try:
        print("🧪 Testing Browser Use API fix...")
        extractor = AgentExtractor()
        
        # Test with an Aritzia URL (browser agent route)
        result = await extractor.extract_product_data(
            'https://www.aritzia.com/us/en/product/utility-dress/115422.html?color=1275', 
            'aritzia'
        )
        
        print(f"✅ SUCCESS: {result.success}")
        print(f"📊 METHOD: {result.method_used}")
        print(f"❌ ERRORS: {result.errors}")
        print(f"⚠️  WARNINGS: {result.warnings}")
        
        if result.data:
            print(f"📝 TITLE: {result.data.get('title', 'N/A')}")
            print(f"💰 PRICE: {result.data.get('price', 'N/A')}")
            print(f"🏪 RETAILER: {result.data.get('retailer', 'N/A')}")
        
        if result.success:
            print("🎉 Browser Use API fix successful!")
        else:
            print("🚨 Browser Use still failing")
            
    except Exception as e:
        print(f"💥 EXCEPTION: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_browser_use_fix()) 