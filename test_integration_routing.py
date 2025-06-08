"""
Integration Test - Markdown/Agent Routing
Quick test to verify proper routing between markdown extractor and agent extractor
"""

import asyncio
from agent_extractor import AgentExtractor
from logger_config import setup_logging

logger = setup_logging(__name__)

async def test_routing():
    """Test routing logic for different retailers"""
    
    print("🧪 INTEGRATION ROUTING TEST")
    print("=" * 50)
    
    # Initialize agent extractor (which includes markdown routing)
    agent_extractor = AgentExtractor()
    
    # Test URLs (simple ones to minimize API costs)
    test_cases = [
        # Markdown retailers (should use markdown first)
        ("asos", "https://www.asos.com/us/nike/nike-club-fleece-hoodie-in-dark-gray-heather/prd/204295151"),
        ("uniqlo", "https://www.uniqlo.com/us/en/products/E449220-000"),
        
        # Non-markdown retailers (should go directly to browser agent)
        ("nordstrom", "https://www.nordstrom.com/s/sample-product"),
        ("aritzia", "https://www.aritzia.com/us/en/sample-product")
    ]
    
    results = {}
    
    for retailer, url in test_cases:
        print(f"\n🔍 Testing {retailer.upper()}")
        print(f"URL: {url}")
        
        try:
            result = await agent_extractor.extract_product_data(url, retailer)
            
            print(f"✅ Method used: {result.method_used}")
            print(f"⏱️ Processing time: {result.processing_time:.2f}s")
            print(f"📊 Success: {result.success}")
            
            if result.success:
                print(f"📦 Title: {result.data.get('title', 'N/A')[:50]}...")
            else:
                print(f"❌ Errors: {result.errors}")
            
            results[retailer] = {
                'success': result.success,
                'method_used': result.method_used,
                'processing_time': result.processing_time
            }
            
        except Exception as e:
            print(f"💥 Exception: {e}")
            results[retailer] = {
                'success': False,
                'method_used': 'exception',
                'error': str(e)
            }
    
    # Summary
    print(f"\n📊 ROUTING TEST SUMMARY")
    print("=" * 50)
    
    for retailer, result in results.items():
        method = result.get('method_used', 'unknown')
        success = result.get('success', False)
        status = "✅" if success else "❌"
        
        print(f"{status} {retailer}: {method}")
    
    # Expected routing validation
    print(f"\n🎯 ROUTING VALIDATION")
    print("-" * 30)
    
    expected_routing = {
        "asos": "markdown_extractor",
        "uniqlo": "markdown_extractor", 
        "nordstrom": "browser_use",
        "aritzia": "browser_use"
    }
    
    routing_correct = True
    for retailer, expected_method in expected_routing.items():
        actual_method = results.get(retailer, {}).get('method_used', 'unknown')
        
        # Handle fallback cases
        if expected_method == "markdown_extractor" and actual_method == "browser_use":
            print(f"⚠️ {retailer}: Expected markdown, got browser (fallback - OK)")
        elif actual_method == expected_method:
            print(f"✅ {retailer}: Correct routing ({actual_method})")
        else:
            print(f"❌ {retailer}: Expected {expected_method}, got {actual_method}")
            routing_correct = False
    
    if routing_correct:
        print(f"\n🎉 All routing tests passed!")
    else:
        print(f"\n⚠️ Some routing issues detected - review logs")

if __name__ == "__main__":
    asyncio.run(test_routing()) 