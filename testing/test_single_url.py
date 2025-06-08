#!/usr/bin/env python3
"""
Simple URL testing script for the automated clothing scraper system.
Tests a single URL through the complete extraction pipeline.
"""

import asyncio
import json
import sys
import os
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logger_config import setup_logging
from agent_extractor import AgentExtractor
from image_processor_factory import ImageProcessorFactory

logger = setup_logging(__name__)

async def test_url(url: str, retailer: str = None):
    """Test a single URL extraction"""
    
    print(f"🎯 Testing URL: {url}")
    print(f"🏪 Retailer: {retailer or 'auto-detect'}")
    print("-" * 60)
    
    try:
        # Auto-detect retailer if not provided
        if not retailer:
            retailer = detect_retailer(url)
            print(f"🔍 Auto-detected retailer: {retailer}")
        
        # Initialize extractor
        print("🔧 Initializing extraction system...")
        extractor = AgentExtractor()
        
        # Extract product data
        print("🤖 Starting extraction...")
        print("⏳ This may take 2-5 minutes for complete product extraction...")
        start_time = datetime.now()
        
        result = await extractor.extract_product_data(url, retailer)
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        print(f"⏱️  Processing time: {processing_time:.2f} seconds")
        print(f"✅ Success: {result.success}")
        print(f"🔧 Method used: {result.method_used}")
        
        if result.success:
            print("\n📊 Extracted Data:")
            print(json.dumps(result.data, indent=2, ensure_ascii=False))
            
            # Test image processing
            if result.data.get('image_urls'):
                print(f"\n🖼️  Testing image processing for {len(result.data['image_urls'])} images...")
                processor = ImageProcessorFactory.get_processor(retailer)
                if processor:
                    # Test a few image URLs
                    test_images = result.data['image_urls'][:3]
                    for i, img_url in enumerate(test_images, 1):
                        print(f"  🔗 Image {i}: {img_url[:80]}...")
                        
                        # Test image processing
                        try:
                            processed_urls = await processor.process_image_url(img_url)
                            print(f"     ✅ Generated {len(processed_urls)} variants")
                        except Exception as e:
                            print(f"     ❌ Processing failed: {e}")
                else:
                    print("  ⚠️  No image processor available for this retailer")
        else:
            print("\n❌ Extraction failed:")
            for error in result.errors:
                print(f"  • {error}")
        
        if result.warnings:
            print("\n⚠️  Warnings:")
            for warning in result.warnings:
                print(f"  • {warning}")
                
        return result.success
        
    except Exception as e:
        print(f"\n💥 Critical error: {e}")
        import traceback
        traceback.print_exc()
        return False

def detect_retailer(url: str) -> str:
    """Auto-detect retailer from URL"""
    url_lower = url.lower()
    
    if 'aritzia.com' in url_lower:
        return 'aritzia'
    elif 'asos.com' in url_lower:
        return 'asos'
    elif 'hm.com' in url_lower or 'h&m' in url_lower:
        return 'hm'
    elif 'uniqlo.com' in url_lower:
        return 'uniqlo'
    elif 'revolve.com' in url_lower:
        return 'revolve'
    elif 'mango.com' in url_lower:
        return 'mango'
    elif 'anthropologie.com' in url_lower:
        return 'anthropologie'
    elif 'abercrombie.com' in url_lower:
        return 'abercrombie'
    elif 'nordstrom.com' in url_lower:
        return 'nordstrom'
    elif 'urbanoutfitters.com' in url_lower:
        return 'urban_outfitters'
    else:
        return 'unknown'

def main():
    if len(sys.argv) < 2:
        print("Usage: python test_single_url.py <URL> [retailer]")
        print("\nExample:")
        print("  python test_single_url.py https://www.uniqlo.com/us/en/products/E474062-000")
        print("  python test_single_url.py https://www.asos.com/example-dress uniqlo")
        print("\nSupported retailers:")
        print("  aritzia, asos, hm, uniqlo, revolve, mango, anthropologie, abercrombie, nordstrom, urban_outfitters")
        sys.exit(1)
    
    url = sys.argv[1]
    retailer = sys.argv[2] if len(sys.argv) > 2 else None
    
    # Run the test
    success = asyncio.run(test_url(url, retailer))
    
    if success:
        print("\n🎉 Test completed successfully!")
        sys.exit(0)
    else:
        print("\n💔 Test failed!")
        sys.exit(1)

if __name__ == "__main__":
    main() 