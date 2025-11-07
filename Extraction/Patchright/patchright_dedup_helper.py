"""
Patchright Tower - Deduplication Helper
Lightweight deduplication utilities for Patchright extraction

Target: <300 lines
"""

# Add shared path for imports
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../../Shared"))

from typing import List, Dict, Optional
from urllib.parse import urlparse, parse_qs
import logging

logger = logging.getLogger(__name__)


class PatchrightDedupHelper:
    """
    Lightweight deduplication for Patchright extraction
    
    Note: Most deduplication logic is in Shared/deduplication_manager.py
    This helper provides Patchright-specific utilities
    """
    
    def __init__(self):
        pass
    
    def normalize_url(self, url: str) -> str:
        """
        Normalize URL for deduplication
        
        Removes:
        - Query parameters
        - Fragments
        - Trailing slashes
        """
        parsed = urlparse(url)
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        normalized = normalized.rstrip('/')
        return normalized.lower()
    
    def extract_product_code_from_image(self, image_url: str) -> Optional[str]:
        """
        Extract product code from image URL
        
        Examples:
        - revolve.com/.../-/AFFM-WD514.jpg → AFFM-WD514
        - asos.com/.../12345678-1.jpg → 12345678
        """
        try:
            # Get filename from URL
            filename = image_url.split('/')[-1]
            
            # Remove extension
            name_without_ext = filename.rsplit('.', 1)[0]
            
            # Remove size/variant suffixes (-1, -2, _alt, etc.)
            code = name_without_ext.split('-')[0].split('_')[0]
            
            return code if code else None
            
        except Exception as e:
            logger.debug(f"Could not extract code from image URL: {e}")
            return None
