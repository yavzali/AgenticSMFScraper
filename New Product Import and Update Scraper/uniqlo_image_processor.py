"""
Uniqlo Image Processor - Handles Uniqlo's complex URL reconstruction patterns
Based on analysis of working patterns from the old script
"""

# Add shared path for imports
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../Shared"))
sys.path.append(os.path.dirname(__file__))

import re
from typing import List, Dict, Optional
from urllib.parse import urlparse, parse_qs

from base_image_processor import BaseImageProcessor
from logger_config import setup_logging

logger = setup_logging(__name__)

class UniqloImageProcessor(BaseImageProcessor):
    """Uniqlo-specific image processor with URL reconstruction"""
    
    def __init__(self):
        super().__init__("uniqlo")
        
        # Uniqlo image server patterns
        self.base_patterns = [
            "https://image.uniqlo.com/UQ/ST3/WesternCommon/imagesgoods/{product_code}/item/goods_{color_code}_{product_code}.jpg?width=2000",
            "https://image.uniqlo.com/UQ/ST3/WesternCommon/imagesgoods/{product_code}/item/goods_{color_code}_{product_code}_l.jpg",
            "https://image.uniqlo.com/UQ/ST3/AsianCommon/imagesgoods/{product_code}/item/goods_{color_code}_{product_code}.jpg?width=2000",
            "https://image.uniqlo.com/UQ/ST3/us/imagesgoods/{product_code}/item/goods_{color_code}_{product_code}.jpg?width=2000"
        ]
        
        # Alternative patterns for different product types
        self.alt_patterns = [
            "https://image.uniqlo.com/UQ/ST3/WesternCommon/imagesgoods/{product_code}/sub/goods_{color_code}_{product_code}_sub01.jpg?width=1500",
            "https://image.uniqlo.com/UQ/ST3/WesternCommon/imagesgoods/{product_code}/sub/goods_{color_code}_{product_code}_sub02.jpg?width=1500",
            "https://image.uniqlo.com/UQ/ST3/WesternCommon/imagesgoods/{product_code}/item/goods_{color_code}_{product_code}_3L.jpg"
        ]
    
    async def reconstruct_image_urls(self, product_url: str, product_data: Dict) -> List[str]:
        """
        Reconstruct Uniqlo image URLs from product codes
        """
        logger.debug(f"Reconstructing Uniqlo image URLs from {product_url}")
        
        # Extract product code and color code
        product_code = self._extract_product_code(product_url, product_data)
        color_code = self._extract_color_code(product_url, product_data)
        
        if not product_code:
            logger.warning(f"Could not extract product code from {product_url}")
            return []
        
        if not color_code:
            color_code = "000"  # Default color
            logger.debug(f"Using default color code 000 for product {product_code}")
        
        logger.info(f"Reconstructing Uniqlo URLs for product {product_code}, color {color_code}")
        
        # Build URLs from patterns
        reconstructed_urls = []
        
        # Primary patterns
        for pattern in self.base_patterns:
            url = pattern.format(product_code=product_code, color_code=color_code)
            reconstructed_urls.append(url)
        
        # Alternative patterns
        for pattern in self.alt_patterns:
            url = pattern.format(product_code=product_code, color_code=color_code)
            reconstructed_urls.append(url)
        
        logger.debug(f"Generated {len(reconstructed_urls)} reconstructed URLs for Uniqlo")
        return reconstructed_urls
    
    def _extract_product_code(self, product_url: str, product_data: Dict) -> Optional[str]:
        """Extract Uniqlo product code from URL or product data"""
        
        # Method 1: From URL path
        # Examples: 
        # https://www.uniqlo.com/us/en/products/E474062-000
        # https://www.uniqlo.com/us/en/men/t-shirts/474062
        
        patterns = [
            r'/products/E?(\d{6})',  # E474062 or 474062
            r'/products/(\d{6})',    # Direct 6-digit code
            r'/(\d{6})-\d{3}',       # 474062-000 format
            r'/(\d{6})$',            # Ending with 6-digit code
            r'/(\d{6})/',            # 6-digit code in path
        ]
        
        for pattern in patterns:
            match = re.search(pattern, product_url)
            if match:
                product_code = match.group(1)
                logger.debug(f"Extracted product code {product_code} from URL using pattern {pattern}")
                return product_code
        
        # Method 2: From product data
        if product_data:
            # Check product_code field
            if 'product_code' in product_data and product_data['product_code']:
                code = str(product_data['product_code'])
                # Clean and validate
                code = re.sub(r'[^0-9]', '', code)
                if len(code) >= 6:
                    product_code = code[-6:]  # Take last 6 digits
                    logger.debug(f"Extracted product code {product_code} from product data")
                    return product_code
            
            # Check title for product codes
            title = product_data.get('title', '')
            title_match = re.search(r'\b(\d{6})\b', title)
            if title_match:
                product_code = title_match.group(1)
                logger.debug(f"Extracted product code {product_code} from title")
                return product_code
        
        logger.warning(f"Could not extract product code from {product_url}")
        return None
    
    def _extract_color_code(self, product_url: str, product_data: Dict) -> Optional[str]:
        """Extract Uniqlo color code from URL or product data"""
        
        # Method 1: From URL
        # Examples: E474062-000, 474062-000
        color_patterns = [
            r'-(\d{3})$',           # -000 at end
            r'-(\d{3})[/?]',        # -000 followed by / or ?
            r'color=(\d{3})',       # color=000 parameter
        ]
        
        for pattern in color_patterns:
            match = re.search(pattern, product_url)
            if match:
                color_code = match.group(1)
                logger.debug(f"Extracted color code {color_code} from URL")
                return color_code
        
        # Method 2: From URL parameters
        parsed_url = urlparse(product_url)
        if parsed_url.query:
            params = parse_qs(parsed_url.query)
            if 'color' in params:
                color_code = params['color'][0]
                logger.debug(f"Extracted color code {color_code} from URL params")
                return color_code
        
        # Method 3: From product data (if available)
        if product_data:
            # Check for color in product code
            product_code = product_data.get('product_code', '')
            if isinstance(product_code, str) and '-' in product_code:
                parts = product_code.split('-')
                if len(parts) > 1 and parts[-1].isdigit() and len(parts[-1]) == 3:
                    color_code = parts[-1]
                    logger.debug(f"Extracted color code {color_code} from product_code field")
                    return color_code
        
        logger.debug(f"Could not extract color code from {product_url}, will use default")
        return None
    
    def _get_retailer_referer(self) -> str:
        """Uniqlo referer"""
        return "https://www.uniqlo.com/"
    
    def _get_retailer_origin(self) -> str:
        """Uniqlo origin"""
        return "https://www.uniqlo.com"
    
    async def browser_use_fallback(self, product_url: str, product_data: Dict) -> List[str]:
        """
        Browser Use fallback for Uniqlo
        Can be enhanced to use Browser Use for downloading or screenshots
        """
        logger.info(f"Uniqlo Browser Use fallback called for {product_url}")
        
        # TODO: Implement Browser Use integration
        # This would:
        # 1. Navigate to product page
        # 2. Find image elements
        # 3. Download via browser session (bypassing anti-scraping)
        # 4. Take screenshots as last resort
        
        return [] 