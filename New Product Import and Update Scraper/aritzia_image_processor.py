"""
Aritzia Image Processor - Handles Aritzia's specific image patterns and requirements
Extends the optimized base image processor with Aritzia-specific logic
"""

# Add shared path for imports
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../Shared"))
sys.path.append(os.path.dirname(__file__))

import re
from typing import List, Dict, Optional

from base_image_processor import BaseImageProcessor
from logger_config import setup_logging

logger = setup_logging(__name__)

class AritziaImageProcessor(BaseImageProcessor):
    """Aritzia-specific image processor with URL optimization and anti-scraping"""
    
    def __init__(self):
        super().__init__("aritzia")
    
    async def reconstruct_image_urls(self, product_url: str, product_data: Dict) -> List[str]:
        """
        Aritzia URL reconstruction and transformation
        """
        logger.debug(f"Processing Aritzia image URLs from {product_url}")
        
        # Get extracted image URLs
        extracted_urls = product_data.get('image_urls', [])
        if not extracted_urls:
            logger.debug(f"No extracted image URLs for Aritzia")
            return []
        
        enhanced_urls = []
        
        for url in extracted_urls:
            # Apply Aritzia-specific transformations
            enhanced_url = self._enhance_aritzia_url(url)
            enhanced_urls.append(enhanced_url)
            
            # Generate additional high-quality variants
            additional_urls = self._generate_aritzia_variants(enhanced_url)
            enhanced_urls.extend(additional_urls)
        
        logger.info(f"Generated {len(enhanced_urls)} enhanced URLs for Aritzia")
        return enhanced_urls
    
    def _enhance_aritzia_url(self, url: str) -> str:
        """Apply Aritzia-specific URL enhancements"""
        
        enhanced_url = url
        
        # Transform resolution parameters
        # Example: _400x400 → _1200x1500
        resolution_pattern = r'_\d{2,4}x\d{2,4}'
        if re.search(resolution_pattern, enhanced_url):
            enhanced_url = re.sub(resolution_pattern, '_1200x1500', enhanced_url)
            logger.debug(f"Enhanced Aritzia resolution: {url} → {enhanced_url}")
        
        # Add size parameters if missing
        elif '?' not in enhanced_url and enhanced_url.endswith(('.jpg', '.jpeg', '.png')):
            enhanced_url += '?width=1200&height=1500'
            logger.debug(f"Added Aritzia size params: {url} → {enhanced_url}")
        
        return enhanced_url
    
    def _generate_aritzia_variants(self, url: str) -> List[str]:
        """Generate additional high-quality URL variants for Aritzia"""
        
        variants = []
        
        # Try different size combinations
        size_variants = ['_1500x1875', '_800x1000', '_original']
        
        for size in size_variants:
            if '_1200x1500' in url:
                variant_url = url.replace('_1200x1500', size)
                if variant_url != url:
                    variants.append(variant_url)
        
        # Try removing size parameters for original size
        if '?' in url and ('width=' in url or 'height=' in url):
            base_url = url.split('?')[0]
            variants.append(base_url)
        
        return variants[:3]  # Limit to 3 additional variants
    
    def _get_retailer_referer(self) -> str:
        """Aritzia referer"""
        return "https://www.aritzia.com/"
    
    def _get_retailer_origin(self) -> str:
        """Aritzia origin"""
        return "https://www.aritzia.com"
    
    async def browser_use_fallback(self, product_url: str, product_data: Dict) -> List[str]:
        """
        Enhanced fallback using Playwright screenshots
        NEW: Integrates with Playwright agent for screenshot-based image fallback
        """
        logger.info(f"Aritzia enhanced fallback called for {product_url}")
        
        try:
            # Try to import and use Playwright agent for screenshot fallback
            from playwright_agent import PlaywrightMultiScreenshotAgent
            
            config = {}  # Use default config
            playwright_agent = PlaywrightMultiScreenshotAgent(config)
            
            # Extract product code for file naming
            product_code = product_data.get('product_code', 'unknown')
            if not product_code or product_code == 'unknown':
                # Try to extract from URL
                import re
                match = re.search(r'/(\d+)\.html', product_url)
                product_code = match.group(1) if match else 'aritzia_product'
            
            # Use Playwright to capture high-quality screenshots as fallback images
            logger.info(f"🎭 Using Playwright screenshot fallback for Aritzia product {product_code}")
            
            async with playwright_agent:
                screenshot_paths = await playwright_agent.save_screenshots_as_fallback(
                    product_url, 'aritzia', product_code
                )
                
                if screenshot_paths:
                    logger.info(f"✅ Playwright fallback generated {len(screenshot_paths)} images")
                    return screenshot_paths
                else:
                    logger.warning("⚠️ Playwright fallback failed to generate images")
                    return []
        
        except ImportError:
            logger.warning("Playwright agent not available for fallback")
            return []
        except Exception as e:
            logger.error(f"Playwright fallback failed: {e}")
            return [] 