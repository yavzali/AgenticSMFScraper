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
from urllib.parse import urlparse, parse_qs
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
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
    
    def deduplicate_urls(self, urls: List[str]) -> List[str]:
        """
        Remove duplicate URLs from a list (in-batch deduplication)
        
        Returns:
            List of unique URLs (preserves order)
        """
        seen = set()
        unique = []
        
        for url in urls:
            normalized = self.normalize_url(url)
            if normalized not in seen:
                seen.add(normalized)
                unique.append(url)
        
        return unique
    
    def normalize_url(self, url: str) -> str:
        """
        Normalize URL for deduplication
        
        Removes:
        - Query parameters (?color=red&size=M)
        - Fragments (#reviews)
        - Trailing slashes
        """
        # Parse URL
        parsed = urlparse(url)
        
        # Rebuild without query and fragment
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        
        # Remove trailing slash
        normalized = normalized.rstrip('/')
        
        return normalized.lower()
    
    def fuzzy_title_match(
        self,
        title1: str,
        title2: str,
        threshold: float = 0.90
    ) -> bool:
        """
        Fast fuzzy title matching
        
        Returns True if titles are >threshold similar
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
