"""
Patchright Tower - Deduplication Helper
Fast deduplication utilities for Patchright extraction

Target: <300 lines
"""

# Add shared path for imports
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../../Shared"))

from typing import List, Dict
from difflib import SequenceMatcher
import logging

logger = logging.getLogger(__name__)


class PatchrightDedupHelper:
    """
    Lightweight deduplication utilities for Patchright extraction
    
    Similar to MarkdownDedupHelper but with Patchright-specific needs:
    - Position-based matching for catalog products
    - Title matching with visual variations
    - Price validation with Gemini extraction tolerance
    
    Note: Full deduplication (against database) handled by
    shared/deduplication_manager.py
    """
    
    def __init__(self, config: Dict):
        self.config = config
    
    def match_by_position(
        self,
        gemini_products: List[Dict],
        dom_products: List[Dict]
    ) -> List[tuple]:
        """
        Match Gemini products with DOM products by position
        
        Assumes products appear in same order in:
        1. Screenshot (visual order)
        2. DOM (HTML order)
        
        Returns:
            List of tuples: (gemini_product, dom_product)
        """
        # TODO: Implement
        # 1. Pair by index (product 0 → product 0)
        # 2. Validate pairing with fuzzy title match
        # 3. Return matched pairs
        pass
    
    def fuzzy_title_match(
        self,
        title1: str,
        title2: str,
        threshold: float = 0.85
    ) -> bool:
        """
        Fuzzy title matching for Patchright
        
        Lower threshold than Markdown (0.85 vs 0.90) because:
        - Gemini may see truncated titles in screenshots
        - Visual extraction less precise than markdown
        """
        similarity = SequenceMatcher(
            None,
            title1.lower(),
            title2.lower()
        ).ratio()
        
        return similarity >= threshold
    
    def price_within_tolerance(
        self,
        price1: float,
        price2: float,
        tolerance: float = 2.0
    ) -> bool:
        """
        Check if prices match within tolerance
        
        Higher tolerance for Patchright (2.0 vs 1.0) because:
        - Gemini Vision may misread prices ($89 vs $87)
        - Sale prices may show differently (strikethrough vs final)
        """
        return abs(price1 - price2) < tolerance
    
    def find_best_match(
        self,
        target_product: Dict,
        candidate_products: List[Dict],
        match_threshold: float = 0.80
    ) -> tuple:
        """
        Find best matching product from candidates
        
        Uses multi-factor scoring:
        - Title similarity (weight: 0.6)
        - Price match (weight: 0.3)
        - Image similarity (weight: 0.1, if available)
        
        Returns: (best_match, confidence_score) or (None, 0.0)
        """
        # TODO: Implement
        pass
    
    def calculate_match_confidence(
        self,
        product1: Dict,
        product2: Dict
    ) -> float:
        """
        Calculate confidence score for product match (0.0-1.0)
        
        Factors:
        - Title similarity
        - Price match
        - Brand match
        - Image similarity (if available)
        """
        # TODO: Implement
        pass


# Helper functions
def normalize_price_for_comparison(price: float) -> float:
    """
    Normalize price for comparison
    
    Rounds to nearest dollar to account for:
    - Gemini Vision misreading ($89.95 → $89 or $90)
    - Sale price variations
    """
    return round(price)


def truncate_title_for_visual_match(title: str, max_chars: int = 50) -> str:
    """
    Truncate title to match what Gemini likely saw
    
    Screenshot titles are often truncated:
    - "Self-Portrait Burgundy Rhinestone..." → first 50 chars
    """
    return title[:max_chars]

