#!/usr/bin/env python3
"""
Test script to verify prompt generation and system configuration.
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
from test_single_url import detect_retailer

logger = setup_logging(__name__)

def test_prompt_generation(url: str, retailer: str = None):
    """Test prompt generation without running actual agents"""
    
    print(f"🎯 Testing prompt generation for: {url}")
    print(f"🏪 Retailer: {retailer or 'auto-detect'}")
    print("-" * 60)
    
    try:
        # Initialize extractor
        extractor = AgentExtractor()
        
        # Auto-detect retailer if not provided
        if not retailer:
            retailer = detect_retailer(url)
            print(f"🔍 Auto-detected retailer: {retailer}")
        
        # Test prompt generation
        print("\n🔧 Testing prompt generation...")
        learned_patterns = []  # Empty for now
        prompt = extractor._build_extraction_prompt(url, retailer, learned_patterns)
        
        print(f"✅ Generated prompt:")
        print(f"   {prompt}")
        
        # Test retailer-specific instructions
        instructions = extractor._get_retailer_instructions(retailer)
        print(f"\n🎯 Retailer-specific instructions:")
        print(f"   {instructions}")
        
        # Test configuration loading
        config = extractor.config
        print(f"\n⚙️  Configuration check:")
        print(f"   OpenManus enabled: {config['agents']['openmanus']['enabled']}")
        print(f"   OpenManus path: {config['agents']['openmanus']['installation_path']}")
        print(f"   Skyvern enabled: {config['agents']['skyvern']['enabled']}")
        print(f"   Browser Use enabled: {config['agents']['browser_use']['enabled']}")
        print(f"   Gemini API key: {'✅ configured' if config['llm_providers']['google']['api_key'] else '❌ missing'}")
        
        # Test image processor
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from image_processor_factory import ImageProcessorFactory
        processor = ImageProcessorFactory.get_processor(retailer)
        print(f"\n🖼️  Image processor:")
        print(f"   Processor available: {'✅ Yes' if processor else '❌ No'}")
        if processor:
            print(f"   Processor type: {type(processor).__name__}")
        
        print(f"\n🎉 System configuration test completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n💥 Configuration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    # Test with the Uniqlo URL
    url = "https://www.uniqlo.com/us/en/products/E479225-000/00?colorDisplayCode=00&sizeDisplayCode=003"
    
    print("=== Testing System Configuration ===\n")
    success = test_prompt_generation(url)
    
    if success:
        print("\n✅ System is properly configured!")
        print("\nNext step: Test with actual agent implementations")
        print("Note: OpenManus will try to run but may fail due to prompt format")
        print("Note: Skyvern and Browser Use are placeholder implementations")
    else:
        print("\n❌ System configuration issues found!")

if __name__ == "__main__":
    main() 