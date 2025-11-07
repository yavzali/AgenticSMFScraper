"""
Patchright Tower - DOM Validator
DOM extraction and validation guided by Gemini Vision hints

Extracted from: Shared/playwright_agent.py (DOM extraction logic)
Target: <500 lines
"""

# Add shared path for imports
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../../Shared"))

import asyncio
from typing import Dict, List, Optional
from difflib import SequenceMatcher
import logging

logger = logging.getLogger(__name__)


class PatchrightDOMValidator:
    """
    DOM extraction and validation for Patchright
    
    Key Capabilities:
    1. Gemini-guided DOM extraction (hints from visual analysis)
    2. Title/price validation (compare DOM vs Gemini)
    3. Image URL extraction and ranking
    4. Merge logic with mismatch detection
    
    Key Learnings from v1.0:
    - JavaScript properties (el.href) > HTML attributes (get_attribute)
    - Explicit wait for selectors essential for SPAs
    - Pattern learner provides best selectors per retailer
    - Validation catches Gemini hallucinations
    """
    
    def __init__(self, page, pattern_learner, config: Dict):
        self.page = page
        self.pattern_learner = pattern_learner
        self.config = config
        # TODO: Load retailer config from /Knowledge/RETAILER_CONFIG.json
    
    async def extract_product_links(
        self,
        retailer: str,
        category: str
    ) -> List[Dict]:
        """
        Extract product URLs from catalog page
        
        Returns list of dicts with:
        - url: Product URL (full)
        - product_code: Extracted from URL
        - title: (optional) DOM-extracted title
        - price: (optional) DOM-extracted price
        """
        logger.info(f"🔍 DOM extracting product links: {retailer}")
        
        # TODO: Phase 3 - Implement DOM extraction
        # 1. Get learned selectors from pattern_learner
        # 2. Wait for selectors to appear (explicit wait)
        # 3. Extract hrefs (JavaScript property, not attribute!)
        # 4. Extract product codes from URLs
        # 5. Optionally extract titles/prices for validation
        
        return []
    
    async def _get_best_selectors(self, retailer: str, element_type: str) -> List[str]:
        """
        Get best selectors from pattern learner
        
        Fallback to generic selectors if no learned patterns
        """
        # TODO: Implement
        # Calls pattern_learner.get_best_patterns()
        pass
    
    async def _wait_for_selector(self, selector: str, timeout: int = 10000):
        """
        Explicit wait for selector to appear
        
        Critical for JavaScript-heavy SPAs where products
        load AFTER networkidle/domcontentloaded
        """
        # TODO: Implement
        pass
    
    async def _extract_href_property(self, element) -> Optional[str]:
        """
        Extract href from element (JavaScript property method)
        
        CRITICAL: get_attribute('href') returns None for SPAs
        Solution: Use JavaScript property (el.href)
        
        Applicable to: Abercrombie, Urban Outfitters, Anthropologie
        """
        # Try HTML attribute first (faster)
        href = await element.get_attribute('href')
        
        if not href:
            # Fallback to JavaScript property (SPAs)
            href = await element.evaluate('el => el.href')
        
        return href
    
    def validate_title(
        self,
        gemini_title: str,
        dom_title: str,
        threshold: float = 0.85
    ) -> Dict:
        """
        Validate Gemini-extracted title against DOM
        
        Returns:
        - is_match: bool
        - similarity: float (0.0-1.0)
        - recommended: str (which title to use)
        - reason: str
        """
        similarity = SequenceMatcher(
            None,
            gemini_title.lower(),
            dom_title.lower()
        ).ratio()
        
        is_match = similarity >= threshold
        
        # Prefer DOM if high match (more reliable for structured data)
        if is_match:
            recommended = dom_title
            reason = f"DOM validated by Gemini ({similarity:.2f} similarity)"
        else:
            recommended = gemini_title
            reason = f"Low DOM match ({similarity:.2f}), using Gemini"
        
        return {
            'is_match': is_match,
            'similarity': similarity,
            'recommended': recommended,
            'reason': reason
        }
    
    def validate_price(
        self,
        gemini_price: float,
        dom_price: float,
        tolerance: float = 1.0
    ) -> Dict:
        """
        Validate Gemini-extracted price against DOM
        
        Tolerance of 1.0 allows for minor differences ($89 vs $89.99)
        """
        difference = abs(gemini_price - dom_price)
        is_match = difference < tolerance
        
        # Prefer DOM for exact pricing
        if is_match:
            recommended = dom_price
            reason = f"DOM validated by Gemini (${difference:.2f} diff)"
        else:
            recommended = gemini_price
            reason = f"Price mismatch (${difference:.2f}), using Gemini"
        
        return {
            'is_match': is_match,
            'difference': difference,
            'recommended': recommended,
            'reason': reason
        }
    
    async def extract_image_urls(self, max_images: int = 5) -> List[str]:
        """
        Extract product image URLs
        
        Strategies:
        - Primary product images (highest quality)
        - Gallery/carousel images
        - Thumbnail URLs (upgrade to full-size)
        """
        # TODO: Implement
        pass


# Helper functions
def _calculate_similarity(text1: str, text2: str) -> float:
    """Calculate text similarity (0.0-1.0)"""
    return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()

