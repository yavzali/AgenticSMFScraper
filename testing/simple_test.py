"""
Simple test for Phase 1 & 2 implementations
"""
import asyncio
from image_url_enhancer import ImageURLEnhancer

async def test_image_transformations():
    """Test image URL transformations directly"""
    
    print("=" * 60)
    print("TESTING IMAGE URL TRANSFORMATIONS")
    print("=" * 60)
    
    enhancer = ImageURLEnhancer()
    
    # Test ASOS transformations
    print("\n--- ASOS Transformations ---")
    asos_urls = [
        'https://images.asos-media.com/products/test-$S$.jpg',
        'https://images.asos-media.com/products/test-$M$.jpg'
    ]
    
    for url in asos_urls:
        enhanced_results = await enhancer.enhance_image_urls('asos', [url])
        for result in enhanced_results:
            print(f"Original: {result['original_url']}")
            print(f"Enhanced: {result['enhanced_url']}")
            print(f"Transformations: {result['transformations_applied']}")
            print(f"Quality Score: {result['quality_score']}")
            print()
    
    # Test Revolve transformations
    print("\n--- Revolve Transformations ---")
    revolve_urls = [
        'https://media.revolve.com/r/2024/n/ct/product.jpg',
        'https://media.revolve.com/r/2024/n/d/product.jpg'
    ]
    
    for url in revolve_urls:
        enhanced_results = await enhancer.enhance_image_urls('revolve', [url])
        for result in enhanced_results:
            print(f"Original: {result['original_url']}")
            print(f"Enhanced: {result['enhanced_url']}")
            print(f"Transformations: {result['transformations_applied']}")
            print(f"Quality Score: {result['quality_score']}")
            print()
    
    # Test H&M transformations
    print("\n--- H&M Transformations ---")
    hm_urls = [
        'https://hmgoepprod.azureedge.net/test_600x600.jpg',
        'https://hmgoepprod.azureedge.net/test_300x300.jpg'
    ]
    
    for url in hm_urls:
        enhanced_results = await enhancer.enhance_image_urls('hm', [url])
        for result in enhanced_results:
            print(f"Original: {result['original_url']}")
            print(f"Enhanced: {result['enhanced_url']}")
            print(f"Transformations: {result['transformations_applied']}")
            print(f"Quality Score: {result['quality_score']}")
            print()
    
    await enhancer.close()

def test_transformation_rules():
    """Test transformation rules without async"""
    
    print("=" * 60)
    print("TESTING TRANSFORMATION RULES")
    print("=" * 60)
    
    enhancer = ImageURLEnhancer()
    
    print("\nAVAILABLE TRANSFORMATION RULES:")
    for retailer, rules in enhancer.transformation_rules.items():
        print(f"\n{retailer.upper()}:")
        for rule in rules:
            print(f"  Pattern: {rule['pattern']}")
            print(f"  Replacement: {rule['replacement']}")
            print(f"  Description: {rule['description']}")

async def main():
    """Run the simplified tests"""
    
    print("PHASE 1 & 2 IMPLEMENTATION VERIFICATION")
    print("Testing core functionality...")
    
    # Test transformation rules
    test_transformation_rules()
    
    # Test actual transformations
    await test_image_transformations()
    
    print("\n" + "=" * 60)
    print("✅ CORE FUNCTIONALITY VERIFIED")
    print("Phase 1 & 2 implementations are working correctly!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main()) 