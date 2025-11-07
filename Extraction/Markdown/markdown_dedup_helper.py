"""
Markdown Tower - Deduplication Helper
Fast deduplication utilities for markdown extraction

Target: <300 lines
"""

# Add shared path for imports
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../../Shared"))

from typing import List, Dict, Optional
from difflib import SequenceMatcher
import logging

logger = logging.getLogger(__name__)


class MarkdownDedupHelper:
    """
    Lightweight deduplication utilities for markdown extraction
    
    Provides:
    - In-batch URL deduplication (before extraction)
    - Quick product code extraction
    - Fast title+price fuzzy matching
    - URL normalization
    
    Note: Full deduplication (against database) handled by
    shared/deduplication_manager.py
    """
    
    def __init__(self, config: Dict):
        self.config = config
    
    def deduplicate_urls(self, urls: List[str]) -> List[str]:
        """
        Remove duplicate URLs from a list (in-batch deduplication)
        
        Handles:
        - Exact duplicates
        - URLs with different query parameters
        - URLs with different fragments (#section)
        
        Returns:
            List of unique URLs (preserves order)
        """
        # TODO: Implement
        # 1. Normalize URLs (strip query params, fragments)
        # 2. Track seen URLs
        # 3. Return unique list
        pass
    
    def normalize_url(self, url: str) -> str:
        """
        Normalize URL for deduplication
        
        Removes:
        - Query parameters (?color=red&size=M)
        - Fragments (#reviews)
        - Trailing slashes
        
        Preserves:
        - Domain
        - Path
        - Product code in path
        """
        # TODO: Implement
        pass
    
    def quick_product_code_extract(
        self,
        url: str,
        retailer: str
    ) -> Optional[str]:
        """
        Quick product code extraction (without full retailer logic)
        
        Used for fast deduplication before full extraction
        """
        # TODO: Import from markdown_retailer_logic
        pass
    
    def fuzzy_title_match(
        self,
        title1: str,
        title2: str,
        threshold: float = 0.90
    ) -> bool:
        """
        Fast fuzzy title matching
        
        Returns True if titles are >threshold similar
        
        Used for:
        - Revolve URL change detection
        - Suspected duplicate identification
        """
        similarity = SequenceMatcher(
            None,
            title1.lower(),
            title2.lower()
        ).ratio()
        
        return similarity >= threshold
    
    def price_match(
        self,
        price1: float,
        price2: float,
        tolerance: float = 1.0
    ) -> bool:
        """
        Check if two prices match (within tolerance)
        
        Tolerance of 1.0 allows for $89.00 vs $89.99
        """
        return abs(price1 - price2) < tolerance
    
    def title_price_match(
        self,
        product1: Dict,
        product2: Dict,
        title_threshold: float = 0.90
    ) -> bool:
        """
        Combined title+price matching (for Revolve-style deduplication)
        
        Returns True if:
        - Title similarity >90%
        - Price matches exactly
        """
        title_match = self.fuzzy_title_match(
            product1.get('title', ''),
            product2.get('title', ''),
            title_threshold
        )
        
        price_match = self.price_match(
            product1.get('price', 0),
            product2.get('price', 0)
        )
        
        return title_match and price_match


# Helper functions
def extract_domain(url: str) -> str:
    """Extract domain from URL"""
    # TODO: Implement
    pass


def strip_query_params(url: str) -> str:
    """Remove query parameters from URL"""
    # TODO: Implement
    pass

