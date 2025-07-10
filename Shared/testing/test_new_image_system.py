"""
Test Script for New Optimized Image Processing System
Tests the 4-layer architecture with URL reconstruction and quality validation
"""

import asyncio
import sys
from typing import Dict, List

# Add system path for imports
sys.path.append('.')

from image_processor_factory import ImageProcessorFactory
from logger_config import setup_logging

logger = setup_logging(__name__)

# Test data for different retailers
TEST_PRODUCTS = {
    "uniqlo": {
        "url": "https://www.uniqlo.com/us/en/products/E474062-000",
        "product_data": {
            "title": "Heattech Cotton Long Sleeve T-Shirt",
            "product_code": "474062",
            "image_urls": [
                "https://image.uniqlo.com/UQ/ST3/WesternCommon/imagesgoods/474062/item/goods_000_474062_3L.jpg"
            ]
        }
    },
    "aritzia": {
        "url": "https://www.aritzia.com/us/en/product/dress/example",
        "product_data": {
            "title": "Aritzia Summer Dress",
            "image_urls": [
                "https://media.aritzia.com/media/catalog/product/c/l/cloth_dress_400x400.jpg"
            ]
        }
    },
    "asos": {
        "url": "https://www.asos.com/us/asos-design/asos-design-oversized-t-shirt/prd/12345",
        "product_data": {
            "title": "ASOS DESIGN oversized t-shirt",
            "image_urls": [
                "https://images.asos-media.com/products/asos-design-oversized-t-shirt-in-black/12345-1-black?$S$&wid=513&fit=constrain"
            ]
        }
    },
    "revolve": {
        "url": "https://www.revolve.com/superdown-dress/dp/SUPE-WD12345/",
        "product_data": {
            "title": "Superdown Mini Dress",
            "image_urls": [
                "https://revolve.s3.amazonaws.com/images/SUPE-WD12345/n/ct/1.jpg"
            ]
        }
    },
    "hm": {
        "url": "https://www2.hm.com/en_us/productpage.12345.html",
        "product_data": {
            "title": "H&M Cotton T-shirt",
            "image_urls": [
                "https://lp2.hm.com/hmgoepprod.azureedge.net/imagesources/pic_12345_600x600.jpg"
            ]
        }
    }
}

async def test_image_processor_factory():
    """Test the image processor factory functionality"""
    
    print("\n" + "="*60)
    print("TESTING IMAGE PROCESSOR FACTORY")
    print("="*60)
    
    # Test factory stats
    stats = ImageProcessorFactory.get_factory_stats()
    print(f"\nFactory Statistics:")
    print(f"  Total supported retailers: {stats['total_supported_retailers']}")
    print(f"  Reconstruction retailers: {stats['reconstruction_retailers']}")
    print(f"  Transformation retailers: {stats['transformation_retailers']}")
    
    print(f"\nProcessor types by retailer:")
    for retailer, proc_type in stats['processor_types'].items():
        print(f"  {retailer}: {proc_type}")
    
    # Test processor creation
    print(f"\nTesting processor creation:")
    for retailer in ["uniqlo", "aritzia", "asos", "revolve", "invalid_retailer"]:
        processor = ImageProcessorFactory.get_processor(retailer)
        if processor:
            print(f"  ✓ Created {type(processor).__name__} for {retailer}")
        else:
            print(f"  ✗ No processor available for {retailer}")

async def test_retailer_processing(retailer: str, test_data: Dict):
    """Test image processing for a specific retailer"""
    
    print(f"\n" + "-"*50)
    print(f"TESTING {retailer.upper()} IMAGE PROCESSING")
    print("-"*50)
    
    # Get processor
    processor = ImageProcessorFactory.get_processor(retailer)
    if not processor:
        print(f"❌ No processor available for {retailer}")
        return
    
    processor_type = ImageProcessorFactory.get_processor_type(retailer)
    print(f"Processor type: {processor_type}")
    print(f"Processor class: {type(processor).__name__}")
    
    # Test data
    product_url = test_data["url"]
    product_data = test_data["product_data"]
    image_urls = product_data["image_urls"]
    
    print(f"Product URL: {product_url}")
    print(f"Original image URLs ({len(image_urls)}):")
    for i, url in enumerate(image_urls, 1):
        print(f"  {i}. {url}")
    
    try:
        # Test URL reconstruction/transformation
        print(f"\nTesting URL reconstruction/transformation...")
        reconstructed_urls = await processor.reconstruct_image_urls(product_url, product_data)
        
        if reconstructed_urls:
            print(f"Generated {len(reconstructed_urls)} reconstructed URLs:")
            for i, url in enumerate(reconstructed_urls[:5], 1):  # Show first 5
                print(f"  {i}. {url}")
            if len(reconstructed_urls) > 5:
                print(f"  ... and {len(reconstructed_urls) - 5} more")
        else:
            print("No reconstructed URLs generated")
        
        # Test full processing (without actual downloads for testing)
        print(f"\nTesting quality assessment logic...")
        
        # Test image quality assessment with dummy content
        dummy_content = b"dummy_image_content_for_testing" * 1000  # Simulate decent file size
        dummy_url = image_urls[0] if image_urls else "https://example.com/test.jpg"
        
        quality_result = await processor._assess_image_quality(dummy_content, dummy_url)
        print(f"Quality assessment results:")
        print(f"  Quality score: {quality_result.quality_score}/100")
        print(f"  Is high quality: {quality_result.is_high_quality}")
        print(f"  File size: {quality_result.file_size} bytes")
        print(f"  Resolution: {quality_result.resolution}")
        if quality_result.reasons:
            print(f"  Quality reasons: {', '.join(quality_result.reasons)}")
        
        print(f"✅ {retailer} processing test completed successfully")
        
    except Exception as e:
        print(f"❌ {retailer} processing test failed: {e}")
        import traceback
        traceback.print_exc()

async def test_quality_validation():
    """Test the image quality validation system"""
    
    print(f"\n" + "="*60)
    print("TESTING IMAGE QUALITY VALIDATION")
    print("="*60)
    
    processor = ImageProcessorFactory.get_processor("asos")  # Use any processor
    
    test_urls = [
        ("https://images.asos-media.com/products/test/$XXL$&wid=2000", "High quality ASOS"),
        ("https://images.asos-media.com/products/test/$S$&wid=150", "Thumbnail ASOS"),
        ("https://revolve.s3.amazonaws.com/images/test/n/z/1.jpg", "High quality Revolve"),
        ("https://revolve.s3.amazonaws.com/images/test/n/ct/1.jpg", "Thumbnail Revolve"),
        ("https://hmgoepprod.azureedge.net/imagesources/pic_test_2000x2000.jpg", "High quality H&M"),
        ("https://hmgoepprod.azureedge.net/imagesources/pic_test_150x150.jpg", "Low quality H&M"),
    ]
    
    for url, description in test_urls:
        dummy_content = b"test_content" * (200 if "High quality" in description else 50)
        quality_result = await processor._assess_image_quality(dummy_content, url)
        
        print(f"\n{description}:")
        print(f"  URL: {url}")
        print(f"  Quality score: {quality_result.quality_score}/100")
        print(f"  High quality: {quality_result.is_high_quality}")
        if quality_result.reasons:
            print(f"  Reasons: {', '.join(quality_result.reasons[:2])}")

async def run_comprehensive_test():
    """Run comprehensive test of the new image processing system"""
    
    print("🧪 COMPREHENSIVE IMAGE PROCESSING SYSTEM TEST")
    print("=" * 80)
    
    try:
        # Test 1: Factory functionality
        await test_image_processor_factory()
        
        # Test 2: Quality validation
        await test_quality_validation()
        
        # Test 3: Individual retailer processing
        for retailer, test_data in TEST_PRODUCTS.items():
            await test_retailer_processing(retailer, test_data)
        
        print(f"\n" + "="*80)
        print("🎉 ALL TESTS COMPLETED")
        print("="*80)
        
        # Cleanup
        await ImageProcessorFactory.close_all()
        print("✅ Cleanup completed")
        
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_comprehensive_test()) 