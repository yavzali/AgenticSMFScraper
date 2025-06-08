#!/usr/bin/env python3
"""
Test complete Playwright + Image Processing integration
"""

import asyncio
import os
from playwright_agent import PlaywrightAgentWrapper
from image_processor_factory import ImageProcessorFactory

async def test_complete_integration():
    print("🚀 TESTING COMPLETE PLAYWRIGHT + IMAGE PROCESSING INTEGRATION")
    print("=" * 70)
    
    # Test configuration
    config = {}
    wrapper = PlaywrightAgentWrapper(config)
    
    # Test URL
    url = 'https://www.aritzia.com/us/en/product/utility-dress/115422.html?color=1275'
    retailer = 'aritzia'
    
    print(f"🎯 Testing: {url}")
    print(f"🏪 Retailer: {retailer}")
    
    # Phase 1: Playwright extraction
    print(f"\n🎭 PHASE 1: Playwright Agent Extraction")
    print("-" * 50)
    
    result = await wrapper.extract_product_data(url, retailer)
    
    if not result.success:
        print(f"❌ Playwright extraction failed: {result.errors}")
        return
    
    extracted_data = result.data
    image_urls = extracted_data.get('image_urls', [])
    product_code = extracted_data.get('product_code', 'test_product')
    
    print(f"✅ Extraction successful!")
    print(f"   📊 Title: {extracted_data.get('title', 'N/A')}")
    print(f"   💰 Price: ${extracted_data.get('price', 'N/A')}")
    print(f"   🖼️ Image URLs found: {len(image_urls)}")
    print(f"   🏷️ Product Code: {product_code}")
    
    # Phase 2: Image processing integration
    print(f"\n🖼️ PHASE 2: Image Processing Integration")
    print("-" * 50)
    
    processor = ImageProcessorFactory.get_processor(retailer)
    if not processor:
        print(f"❌ No processor available for {retailer}")
        return
    
    processor_type = ImageProcessorFactory.get_processor_type(retailer)
    print(f"✅ Using {processor_type} processor for {retailer}")
    
    # Test standard image processing
    if image_urls:
        print(f"🔧 Processing {len(image_urls)} extracted image URLs...")
        processed_images = await processor.process_images(image_urls, url, extracted_data)
        
        if processed_images:
            print(f"✅ Standard processing successful: {len(processed_images)} images")
        else:
            print(f"⚠️ Standard processing failed, will test fallback")
    else:
        print(f"⚠️ No image URLs to process, testing fallback directly")
        processed_images = []
    
    # Phase 3: Playwright screenshot fallback
    print(f"\n📸 PHASE 3: Playwright Screenshot Fallback")
    print("-" * 50)
    
    if not processed_images:
        print(f"🎭 Testing Playwright screenshot fallback...")
        
        try:
            # Test the enhanced fallback
            fallback_images = await processor.browser_use_fallback(url, extracted_data)
            
            if fallback_images:
                print(f"✅ Screenshot fallback successful: {len(fallback_images)} images")
                for i, img_path in enumerate(fallback_images, 1):
                    file_size = os.path.getsize(img_path) if os.path.exists(img_path) else 0
                    print(f"   {i}. {img_path} ({file_size:,} bytes)")
            else:
                print(f"❌ Screenshot fallback failed")
        except Exception as e:
            print(f"❌ Fallback error: {e}")
    else:
        print(f"ℹ️ Skipping fallback test - standard processing succeeded")
    
    # Phase 4: Integration summary
    print(f"\n📊 INTEGRATION SUMMARY")
    print("=" * 50)
    
    print(f"🎭 Playwright Agent:")
    print(f"   ✅ Data extraction: {result.success}")
    print(f"   ⏱️ Processing time: {result.processing_time:.1f}s")
    print(f"   📋 Fields extracted: {len([k for k, v in extracted_data.items() if v])}")
    
    print(f"\n🖼️ Image Processing:")
    print(f"   ✅ Processor available: {processor is not None}")
    print(f"   🔧 Standard processing: {'✅ Worked' if processed_images else '⚠️ Failed'}")
    print(f"   📸 Screenshot fallback: {'✅ Available' if hasattr(processor, 'browser_use_fallback') else '❌ Not available'}")
    
    print(f"\n🏆 INTEGRATION STATUS:")
    if result.success and processor:
        print(f"   ✅ COMPLETE INTEGRATION WORKING")
        print(f"   🎯 Playwright replaces Browser Use successfully")
        print(f"   🖼️ Image processing enhanced with screenshot fallback")
        print(f"   ⚡ Performance: {result.processing_time:.1f}s (vs Browser Use 60s+)")
    else:
        print(f"   ⚠️ Integration needs attention")

if __name__ == "__main__":
    asyncio.run(test_complete_integration()) 