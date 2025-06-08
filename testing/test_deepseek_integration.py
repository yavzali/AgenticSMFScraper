import asyncio
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from markdown_extractor import MarkdownExtractor

async def test_deepseek_integration():
    """Test if DeepSeek V3 integration is working"""
    try:
        print("🧪 Testing DeepSeek V3 integration...")
        
        extractor = MarkdownExtractor()
        
        # Check if DeepSeek is enabled
        print(f"🔑 DeepSeek enabled: {extractor.deepseek_enabled}")
        
        if not extractor.deepseek_enabled:
            print("❌ DeepSeek not enabled - check API key setup")
            return
        
        # Test with a simple URL (Mango - markdown extraction)
        result = await extractor.extract_product_data(
            'https://shop.mango.com/us/en/p/women/dresses-and-jumpsuits/dresses/short-button-down-linen-blend-dress_87039065',
            'mango'
        )
        
        print(f"✅ SUCCESS: {result.success}")
        print(f"📊 METHOD: {result.method_used}")
        if result.data:
            print(f"📝 TITLE: {result.data.get('title', 'N/A')}")
            print(f"💰 PRICE: {result.data.get('price', 'N/A')}")
        print(f"❌ ERRORS: {result.errors}")
        print(f"⚠️  WARNINGS: {result.warnings}")
        
    except Exception as e:
        print(f"❌ Error testing DeepSeek integration: {e}")

if __name__ == "__main__":
    asyncio.run(test_deepseek_integration()) 