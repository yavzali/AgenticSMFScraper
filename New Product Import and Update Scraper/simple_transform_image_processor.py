"""
Simple Transform Image Processor - For retailers that need URL transformations only
Handles ASOS, Revolve, H&M, and other retailers with simpler image URL patterns
"""
# Add shared path for imports
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../Shared"))

import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


import re
from typing import List, Dict

from base_image_processor import BaseImageProcessor
from logger_config import setup_logging

logger = setup_logging(__name__)

class SimpleTransformImageProcessor(BaseImageProcessor):
    """Image processor for retailers with simple URL transformation needs"""
    
    def __init__(self, retailer: str):
        super().__init__(retailer)
        
        # URL transformation rules by retailer (FIXED with working patterns from old script)
        self.transformation_rules = {
            "asos": [
                # Replace S or T with XXL in product codes
                (r'\$(.*?)([ST])\$', r'$\1XXL$'),
                # Adjust width parameter
                (r'wid=\d{1,3}', 'wid=1000'),
            ],
            "revolve": [
                # Multiple transformation patterns for Revolve (not just /n/ct/)
                (r'/n/ct/', '/n/z/'),   # Thumbnail to Zoom
                (r'/n/uv/', '/n/z/'),   # UV to Zoom  
                (r'/n/d/', '/n/z/'),    # Detail to Zoom
                (r'/n/p/', '/n/z/'),    # Preview to Zoom
                (r'/n/r/', '/n/z/'),    # Regular to Zoom
                (r'/n/t/', '/n/z/'),    # Thumb to Zoom
            ],
            "hm": [
                # H&M uses imwidth parameters, not resolution patterns
                (r'imwidth=\d+', 'imwidth=2160'),  # Increase imwidth to high-res
                (r'_s\d{1,2}x\d{1,2}', '_1500x2000'),  # Replace small dimensions
            ],
            "nordstrom": [
                (r'(\.[jpg|jpeg|png]+)$', r'?width=1200&height=1500\1'),
            ],
            "anthropologie": [
                (r'_[a-z]+(\.[jpg|jpeg|png]+)$', r'_xl\1'),
            ],
            "urban_outfitters": [
                (r'(\.[jpg|jpeg|png]+)$', r'_xl\1'),
            ],
            "abercrombie": [
                (r'(\.[jpg|jpeg|png]+)$', r'_prod\1'),
            ],
            "mango": [
                (r'(\.[jpg|jpeg|png]+)(\?.*)?$', r'\1?width=1200&height=1500'),
            ]
        }
        
        # Referer and origin by retailer
        self.retailer_domains = {
            "asos": ("https://www.asos.com/", "https://www.asos.com"),
            "revolve": ("https://www.revolve.com/", "https://www.revolve.com"),
            "hm": ("https://www2.hm.com/", "https://www2.hm.com"),
            "nordstrom": ("https://www.nordstrom.com/", "https://www.nordstrom.com"),
            "anthropologie": ("https://www.anthropologie.com/", "https://www.anthropologie.com"),
            "urban_outfitters": ("https://www.urbanoutfitters.com/", "https://www.urbanoutfitters.com"),
            "abercrombie": ("https://www.abercrombie.com/", "https://www.abercrombie.com"),
            "mango": ("https://shop.mango.com/", "https://shop.mango.com")
        }
    
    async def reconstruct_image_urls(self, product_url: str, product_data: Dict) -> List[str]:
        """
        Apply URL transformations to improve image quality
        This is "reconstruction" through transformation rather than building from scratch
        """
        logger.debug(f"Applying URL transformations for {self.retailer}")
        
        # Get extracted image URLs from product data
        extracted_urls = product_data.get('image_urls', [])
        if not extracted_urls:
            logger.debug(f"No extracted image URLs to transform for {self.retailer}")
            return []
        
        # Apply retailer-specific transformations
        rules = self.transformation_rules.get(self.retailer, [])
        if not rules:
            logger.debug(f"No transformation rules for {self.retailer}, returning original URLs")
            return extracted_urls
        
        transformed_urls = []
        
        for url in extracted_urls:
            transformed_url = url
            transformations_applied = []
            
            # Apply each transformation rule
            for pattern, replacement in rules:
                if re.search(pattern, transformed_url):
                    new_url = re.sub(pattern, replacement, transformed_url)
                    if new_url != transformed_url:
                        transformations_applied.append(f"{pattern} -> {replacement}")
                        transformed_url = new_url
            
            # Special handling for H&M: Add imwidth parameter if missing (from working script)
            if self.retailer == "hm" and "imwidth=" not in transformed_url and "width[" not in transformed_url:
                separator = "&" if "?" in transformed_url else "?"
                transformed_url += f"{separator}imwidth=2160"
                transformations_applied.append("Added imwidth=2160 parameter")
            
            transformed_urls.append(transformed_url)
            
            if transformations_applied:
                logger.debug(f"Transformed {self.retailer} URL: {url} -> {transformed_url}")
                logger.debug(f"Applied transformations: {transformations_applied}")
            else:
                logger.debug(f"No transformations applied to {self.retailer} URL: {url}")
        
        # Add some high-quality URL constructions based on patterns
        additional_urls = self._generate_additional_urls(product_url, product_data, transformed_urls)
        transformed_urls.extend(additional_urls)
        
        logger.info(f"Generated {len(transformed_urls)} URLs for {self.retailer} ({len(additional_urls)} additional)")
        return transformed_urls
    
    def _generate_additional_urls(self, product_url: str, product_data: Dict, 
                                transformed_urls: List[str]) -> List[str]:
        """Generate additional high-quality URLs based on patterns"""
        additional_urls = []
        
        if self.retailer == "asos":
            # ASOS: Try to generate more size variations
            for url in transformed_urls[:2]:  # Only process first 2 to avoid too many
                if '$XXL$' in url:
                    # Try other high-res variations
                    alt_url = url.replace('$XXL$', '$XXXL$')
                    if alt_url != url:
                        additional_urls.append(alt_url)
        
        elif self.retailer == "revolve":
            # Revolve: Try different zoom levels
            for url in transformed_urls[:2]:
                if '/n/z/' in url:
                    # Try full-size variation
                    alt_url = url.replace('/n/z/', '/n/f/')
                    if alt_url != url:
                        additional_urls.append(alt_url)
        
        elif self.retailer == "hm":
            # H&M: Try different high-res formats
            for url in transformed_urls[:2]:
                if '_2000x2000' in url:
                    # Try without size parameter (sometimes higher quality)
                    alt_url = re.sub(r'_\d+x\d+', '', url)
                    if alt_url != url:
                        additional_urls.append(alt_url)
        
        return additional_urls
    
    def _get_retailer_referer(self) -> str:
        """Get referer for this retailer"""
        domains = self.retailer_domains.get(self.retailer)
        if domains:
            return domains[0]
        return f"https://www.{self.retailer}.com/"
    
    def _get_retailer_origin(self) -> str:
        """Get origin for this retailer"""
        domains = self.retailer_domains.get(self.retailer)
        if domains:
            return domains[1]
        return f"https://www.{self.retailer}.com"
    
    async def browser_use_fallback(self, product_url: str, product_data: Dict) -> List[str]:
        """
        Browser Use fallback for simple transformation retailers
        """
        logger.info(f"{self.retailer} Browser Use fallback called for {product_url}")
        
        # TODO: Implement retailer-specific Browser Use logic
        # This could navigate to the product page and:
        # 1. Find all image elements
        # 2. Extract their URLs
        # 3. Apply transformations
        # 4. Download via browser session
        # 5. Take screenshots as final fallback
        
        return [] 