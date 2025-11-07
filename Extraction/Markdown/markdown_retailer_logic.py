"""
Markdown Tower - Retailer-Specific Logic
Handle retailer-specific quirks and transformations

Extracted from: Shared/markdown_extractor.py
Target: <500 lines
"""

# Add shared path for imports
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../../Shared"))

import re
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


class MarkdownRetailerLogic:
    """
    Retailer-specific logic for markdown extraction
    
    Handles:
    - Price parsing (Aritzia CAD, Mango EUR, etc.)
    - Title cleaning (remove retailer name, marketing text)
    - Product code patterns (regex per retailer)
    - Brand validation and correction
    - Size/color parsing variations
    """
    
    # Product code regex patterns per retailer
    PRODUCT_CODE_PATTERNS = {
        'revolve': r'/dp/([A-Z0-9\-]+)/?',
        'asos': r'/prd/(\d+)',
        'aritzia': r'/([A-Z0-9\-]+)/?$',
        'anthropologie': r'/shopop/([A-Z0-9\-]+)',
        'abercrombie': r'/shop/([A-Za-z0-9\-]+)/?$',
        'hm': r'\.([0-9]+)\.html',
        'uniqlo': r'/([A-Z0-9\-]+)/?$',
        'urban_outfitters': r'/([A-Za-z0-9\-]+)/?$',
        'nordstrom': r'-(\d+)\.html',
        'mango': r'/([A-Z0-9\-]+)\.html'
    }
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
    
    def parse_price(self, price_str: str, retailer: str) -> Optional[float]:
        """
        Parse price string to float, handling currency variations
        
        Examples:
        - "$89" → 89.0
        - "CA$120" (Aritzia) → 120.0
        - "€95" (Mango) → 95.0
        - "$89.99" → 89.99
        """
        try:
            # Remove currency symbols and commas
            cleaned = price_str.replace('$', '').replace('CA$', '').replace('€', '').replace(',', '').strip()
            if cleaned:
                return float(cleaned)
        except Exception as e:
            logger.debug(f"Could not parse price '{price_str}': {e}")
        return None
    
    def clean_title(self, title: str, retailer: str) -> str:
        """
        Clean product title
        
        Remove:
        - Retailer name (e.g., "REVOLVE" from title)
        - Marketing text (e.g., "NEW!", "SALE!")
        - Extra whitespace
        
        Preserve:
        - Brand name
        - Product description
        - Color/style descriptors
        """
        # Remove common marketing text
        title = re.sub(r'\b(NEW|SALE|EXCLUSIVE|LIMITED)\b', '', title, flags=re.IGNORECASE)
        
        # Remove retailer names
        retailer_names = {
            'revolve': 'REVOLVE',
            'asos': 'ASOS',
            'mango': 'Mango',
            'hm': 'H&M'
        }
        if retailer in retailer_names:
            title = title.replace(retailer_names[retailer], '')
        
        # Clean extra whitespace
        title = re.sub(r'\s+', ' ', title).strip()
        
        return title
    
    def extract_product_code(self, url: str, retailer: str) -> Optional[str]:
        """
        Extract product code from URL using retailer-specific pattern
        
        Returns:
            Product code string or None if pattern doesn't match
        """
        try:
            # Get pattern for retailer
            pattern = self.PRODUCT_CODE_PATTERNS.get(retailer)
            
            if not pattern:
                logger.debug(f"No product code pattern for retailer: {retailer}")
                # Fallback: try to get last segment
                parts = url.rstrip('/').split('/')
                if parts:
                    return parts[-1].split('?')[0].split('#')[0]
                return None
            
            # Try to match pattern
            match = re.search(pattern, url)
            if match:
                return match.group(1)
            
            # Fallback
            parts = url.rstrip('/').split('/')
            if parts:
                return parts[-1].split('?')[0].split('#')[0]
                
        except Exception as e:
            logger.debug(f"Could not extract product code from {url}: {e}")
        
        return None
    
    def validate_brand(self, brand: str, retailer: str) -> str:
        """
        Validate and correct brand name
        
        Common issues:
        - LLM returns retailer name as brand
        - Brand name in all caps (fix to title case)
        - Typos in common brands
        """
        if not brand:
            return ""
        
        # Don't use retailer name as brand
        retailer_names = ['revolve', 'asos', 'mango', 'h&m', 'hm', 'uniqlo']
        if brand.lower() in retailer_names:
            return ""
        
        # Fix all caps to title case
        if brand.isupper() and len(brand) > 3:
            brand = brand.title()
        
        return brand.strip()
    
    def parse_sizes(self, sizes_str: str, retailer: str) -> list:
        """
        Parse size string to list
        
        Examples:
        - "XS, S, M, L, XL" → ['XS', 'S', 'M', 'L', 'XL']
        - "0, 2, 4, 6, 8" → ['0', '2', '4', '6', '8']
        - "XS-XL" → ['XS', 'S', 'M', 'L', 'XL']
        """
        if not sizes_str:
            return []
        
        # Handle comma-separated
        if ',' in sizes_str:
            return [s.strip() for s in sizes_str.split(',') if s.strip()]
        
        # Handle range (XS-XL)
        if '-' in sizes_str and len(sizes_str) < 10:
            range_map = {
                'XS-XL': ['XS', 'S', 'M', 'L', 'XL'],
                'XS-L': ['XS', 'S', 'M', 'L'],
                'S-XL': ['S', 'M', 'L', 'XL']
            }
            return range_map.get(sizes_str, [sizes_str])
        
        # Single size
        return [sizes_str.strip()]
    
    def parse_colors(self, colors_str: str, retailer: str) -> list:
        """
        Parse color string to list
        
        Examples:
        - "Black, White, Navy" → ['Black', 'White', 'Navy']
        - "Available in 5 colors" → Extract from context
        """
        if not colors_str:
            return []
        
        # Handle comma-separated
        if ',' in colors_str:
            return [c.strip() for c in colors_str.split(',') if c.strip()]
        
        # Single color
        return [colors_str.strip()]
