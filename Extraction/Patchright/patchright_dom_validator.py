"""
Patchright Tower - DOM Validator
DOM extraction and validation utilities

Extracted from: Shared/playwright_agent.py (DOM utilities, lines 2104-2238, 2943-3097)
Target: <700 lines
"""

# Add shared path for imports
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../../Shared"))

import re
from typing import List, Dict, Optional
from difflib import SequenceMatcher
import logging

logger = logging.getLogger(__name__)


class PatchrightDOMValidator:
    """
    DOM extraction and validation utilities
    
    Provides:
    - Image URL extraction from DOM
    - Title/price extraction with learned patterns
    - Gemini→DOM guided extraction
    - Validation of Gemini data against DOM
    - Image quality ranking
    """
    
    def __init__(self, page, retailer: str):
        """
        Args:
            page: Patchright Page object
            retailer: Retailer name
        """
        self.page = page
        self.retailer = retailer
    
    async def guided_dom_extraction(
        self,
        product_data: Dict,
        gemini_visual_hints: Dict
    ) -> Dict:
        """
        DOM fills gaps & validates Gemini's work (guided by Gemini Vision)
        
        Process:
        1. Check if Gemini missed critical fields (title, price, images)
        2. Use learned patterns + Gemini hints to extract from DOM
        3. Validate Gemini data against DOM (cross-check)
        
        Args:
            product_data: Product data from Gemini
            gemini_visual_hints: Visual hints from Gemini (DOM guidance)
            
        Returns:
            Dict with: title, price, images, selectors_used, validations, gaps_filled
        """
        result = {
            'title': None,
            'price': None,
            'images': [],
            'selectors_used': {},
            'validations': {},
            'gaps_filled': []
        }
        
        try:
            # TITLE: Extract if missing or validate if present
            if not product_data.get('title') or len(product_data.get('title', '')) < 5:
                logger.debug("Title missing from Gemini, DOM extracting...")
                title = await self._extract_title(gemini_visual_hints)
                if title:
                    result['title'] = title
                    result['gaps_filled'].append('title')
                    logger.info("✅ DOM filled gap: title")
            else:
                # Validate Gemini's title
                validation = await self._validate_title(product_data['title'])
                if validation:
                    result['validations']['title'] = validation
                    if validation['similarity'] > 0.8:
                        logger.debug(f"✅ DOM validated title ({validation['similarity']:.0%})")
                    else:
                        logger.warning(f"⚠️ Title mismatch ({validation['similarity']:.0%})")
            
            # PRICE: Extract if missing
            if not product_data.get('price') or product_data.get('price') == 0:
                logger.debug("Price missing from Gemini, DOM extracting...")
                price = await self._extract_price(gemini_visual_hints)
                if price:
                    result['price'] = price
                    result['gaps_filled'].append('price')
                    logger.info("✅ DOM filled gap: price")
            
            # IMAGES: ALWAYS extract from DOM (images aren't visible in screenshots!)
            # DOM-FIRST LEARNING: Image URLs must come from DOM, not Gemini Vision
            logger.debug(f"DOM extracting images (Gemini had: {len(product_data.get('image_urls', []))})")
            images = await self._extract_images(gemini_visual_hints)
            if images:
                result['images'] = images
                # Mark as filled if Gemini had none or few
                if len(product_data.get('image_urls', [])) < 2:
                    result['gaps_filled'].append('images')
                logger.info(f"✅ DOM extracted {len(images)} images")
            else:
                logger.warning("⚠️ DOM found no images!")
            
            gaps_msg = f"{len(result['gaps_filled'])} gaps" if result['gaps_filled'] else "no gaps"
            val_msg = f"{len(result['validations'])} validations" if result['validations'] else "no validations"
            logger.info(f"🎯 DOM complete: {gaps_msg}, {val_msg}")
            
            return result
            
        except Exception as e:
            logger.error(f"Guided DOM extraction failed: {e}")
            return result
    
    async def _extract_title(self, gemini_hints: Dict) -> Optional[str]:
        """Extract title from DOM using learned patterns + Gemini hints"""
        title_selectors = []
        
        # Gemini's DOM hints
        dom_hints = gemini_hints.get('dom_hints', {})
        gemini_selectors = dom_hints.get('title_selectors', [])
        if gemini_selectors:
            title_selectors.extend(gemini_selectors)
        
        # Fallback generic selectors
        title_selectors.extend([
            'h1',
            '.product-title',
            '.product-name',
            '[data-testid="product-title"]',
            'h1.title',
            '.title',
            'h2.product-title'
        ])
        
        for selector in title_selectors:
            try:
                element = await self.page.query_selector(selector)
                if element:
                    title = await element.inner_text()
                    if title and len(title) > 5:
                        return title.strip()
            except:
                continue
        
        return None
    
    async def _validate_title(self, gemini_title: str) -> Optional[Dict]:
        """Validate Gemini's title against DOM"""
        validation_selectors = ['h1', '.product-title', '[data-testid="product-title"]']
        
        for selector in validation_selectors:
            try:
                element = await self.page.query_selector(selector)
                if element:
                    dom_title = (await element.inner_text()).strip()
                    similarity = self.calculate_similarity(gemini_title, dom_title)
                    return {
                        'gemini': gemini_title[:50],
                        'dom': dom_title[:50],
                        'similarity': similarity,
                        'validated': similarity > 0.8
                    }
            except:
                continue
        
        return None
    
    async def _extract_price(self, gemini_hints: Dict) -> Optional[str]:
        """Extract price from DOM using learned patterns + Gemini hints"""
        price_selectors = []
        
        # Gemini's hints
        gemini_selectors = gemini_hints.get('dom_hints', {}).get('price_selectors', [])
        if gemini_selectors:
            price_selectors.extend(gemini_selectors)
        
        # Fallback selectors (retailer-specific first, then generic)
        price_selectors.extend([
            # Nordstrom-specific (from catalog testing)
            'span.qHz0a',            # Nordstrom primary price
            'span[class*="qHz0a"]',  # Nordstrom price (flexible)
            'span.He8hw',            # Nordstrom accessibility text
            # Generic selectors
            '.price',
            '.product-price',
            '[data-testid="price"]',
            '.sale-price',
            '.current-price',
            'span.price',
            'div.price'
        ])
        
        for selector in price_selectors:
            try:
                element = await self.page.query_selector(selector)
                if element:
                    price_text = await element.inner_text()
                    if price_text and '$' in price_text:
                        return price_text.strip()
            except:
                continue
        
        return None
    
    async def _extract_images(self, gemini_hints: Dict) -> List[str]:
        """
        Extract image URLs from DOM (ENHANCED with DOM-first learnings)
        
        Uses JS evaluation for reliable src extraction (learned from catalog extraction)
        """
        image_selectors = []
        
        # Gemini's hints
        gemini_selectors = gemini_hints.get('dom_hints', {}).get('image_selectors', [])
        if gemini_selectors:
            image_selectors.extend(gemini_selectors)
        
        # Retailer-specific selectors (comprehensive)
        retailer_selectors = {
            'anthropologie': [
                'img[src*="anthropologie"]',
                '.product-images img',
                'picture img',
                '[data-testid="carousel"] img'
            ],
            'urban_outfitters': [
                'img[src*="urbanoutfitters"]',
                '.product-image img',
                '.carousel-item img',
                'picture img'
            ],
            'abercrombie': [
                'img[src*="abercrombie"]',
                'img[src*="scene7"]',
                '.product-images img',
                'picture img'
            ],
            'aritzia': [
                'img[src*="aritzia"]',
                '.product-carousel img',
                'picture img',
                'img[alt*="product"]'
            ],
            'hm': [
                'img[src*="hm.com"]',
                'img[src*="hmgroup"]',
                '.product-detail-main-image-container img',
                'picture img',
                'img[data-testid="product-image"]'
            ]
        }
        
        # Add retailer-specific selectors
        if self.retailer.lower() in retailer_selectors:
            image_selectors.extend(retailer_selectors[self.retailer.lower()])
        
        # Generic fallback selectors
        image_selectors.extend([
            'img.product-image',
            '.product-images img',
            '.image-gallery img',
            'picture img',
            '[data-testid="product-image"]',
            'img[src*="product"]',
            'main img',  # Generic main content images
            'img[alt]'   # Any img with alt text
        ])
        
        images = []
        
        for selector in image_selectors:
            try:
                elements = await self.page.query_selector_all(selector)
                
                for img in elements[:20]:  # Check more images (was :5)
                    # DOM-FIRST LEARNING: Use JS evaluation (not get_attribute)
                    # Works better for dynamically loaded images
                    try:
                        src = await img.evaluate('el => el.src || el.dataset.src || el.dataset.original')
                    except:
                        # Fallback to get_attribute
                        src = await img.get_attribute('src')
                        if not src:
                            src = await img.get_attribute('data-src')
                        if not src:
                            src = await img.get_attribute('data-original')
                    
                    if src and self.is_valid_product_image_url(src):
                        # Convert relative to absolute
                        if src.startswith('//'):
                            src = 'https:' + src
                        elif src.startswith('/'):
                            base_url = await self.page.evaluate('() => window.location.origin')
                            src = base_url + src
                        
                        # Deduplicate
                        if src not in images:
                            images.append(src)
                
                # Continue searching if we have < 3 images (want multiple product images)
                if len(images) >= 3:
                    break
                    
            except Exception as e:
                logger.debug(f"Selector {selector} failed: {e}")
                continue
        
        # Rank by quality and return top 10 images (was 5)
        ranked = self.rank_image_urls(images)[:10]
        logger.debug(f"Extracted {len(ranked)} images from {len(images)} total found")
        return ranked
    
    async def extract_image_urls_from_dom(self) -> List[str]:
        """
        Extract image URLs directly from DOM
        
        Uses retailer-specific selectors + generic fallbacks
        """
        try:
            # Retailer-specific selectors
            image_selectors = {
                'aritzia': [
                    'img[src*="media.aritzia.com"]',
                    '.product-images img',
                    '.product-carousel img',
                    'img[data-src*="aritzia"]'
                ],
                'urban_outfitters': [
                    'img[src*="urbanoutfitters.com"]',
                    '.product-image img',
                    '.carousel-item img',
                    'img[data-src*="urbanoutfitters"]'
                ],
                'abercrombie': [
                    'img[src*="abercrombie.com"]',
                    'img[src*="anf.scene7.com"]',
                    '.product-images img',
                    'img[data-src*="abercrombie"]'
                ],
                'anthropologie': [
                    'img[src*="anthropologie.com"]',
                    'img[src*="assets.anthropologie.com"]',
                    '.product-images img',
                    'img[data-src*="anthropologie"]'
                ],
                'nordstrom': [
                    'img[src*="nordstrommedia.com"]',
                    '.product-media img',
                    'img[data-src*="nordstrom"]'
                ]
            }
            
            # Generic fallbacks
            generic_selectors = [
                'img[src*="product"]',
                'img[src*="image"]',
                'img[src*="media"]',
                '.product img',
                '.product-image img',
                '.product-photo img',
                'img[data-src]',
                'img[src]:not([src*="icon"]):not([src*="logo"])'
            ]
            
            selectors = image_selectors.get(self.retailer, []) + generic_selectors
            image_urls = []
            
            for selector in selectors:
                try:
                    elements = await self.page.query_selector_all(selector)
                    
                    for element in elements:
                        # Try multiple attributes
                        src = await element.get_attribute('src')
                        if not src:
                            src = await element.get_attribute('data-src')
                        if not src:
                            src = await element.get_attribute('data-original')
                        
                        if src and self.is_valid_product_image_url(src):
                            # Convert relative URLs
                            if src.startswith('//'):
                                src = 'https:' + src
                            elif src.startswith('/'):
                                base_url = await self.page.evaluate('() => window.location.origin')
                                src = base_url + src
                            
                            if src not in image_urls:
                                image_urls.append(src)
                    
                    # Stop if we have enough
                    if len(image_urls) >= 10:
                        break
                        
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")
                    continue
            
            # Rank by quality
            quality_images = self.rank_image_urls(image_urls)
            
            logger.info(f"🖼️ DOM extracted {len(quality_images)} images for {self.retailer}")
            return quality_images[:5]
            
        except Exception as e:
            logger.error(f"Image extraction failed: {e}")
            return []
    
    def is_valid_product_image_url(self, url: str) -> bool:
        """Check if URL is likely a valid product image"""
        if not url or len(url) < 10:
            return False
        
        url_lower = url.lower()
        
        # Exclude non-product images
        exclusions = [
            'icon', 'logo', 'sprite', 'banner', 'placeholder',
            'thumbnail', 'badge', 'social', 'favicon'
        ]
        
        if any(excl in url_lower for excl in exclusions):
            return False
        
        # Must be image format
        image_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
        if not any(ext in url_lower for ext in image_extensions):
            # Check if URL contains image indicators
            if not any(ind in url_lower for ind in ['image', 'img', 'photo', 'product', 'media']):
                return False
        
        # Must be HTTP/HTTPS
        if not url.startswith(('http://', 'https://', '//', '/')):
            return False
        
        return True
    
    def rank_image_urls(self, image_urls: List[str]) -> List[str]:
        """
        Rank image URLs by quality indicators
        
        Higher quality = larger images, product photos, not thumbnails
        """
        def quality_score(url: str) -> int:
            score = 0
            url_lower = url.lower()
            
            # Positive indicators (higher quality)
            if 'large' in url_lower or 'big' in url_lower:
                score += 10
            if '1000' in url or '2000' in url or '3000' in url:
                score += 8
            if 'zoom' in url_lower or 'detail' in url_lower:
                score += 7
            if 'product' in url_lower or 'main' in url_lower:
                score += 5
            if '.jpg' in url_lower or '.png' in url_lower:
                score += 3
            
            # Negative indicators (lower quality)
            if 'thumb' in url_lower or 'thumbnail' in url_lower:
                score -= 10
            if 'small' in url_lower or 'tiny' in url_lower:
                score -= 8
            if '_50' in url or '_100' in url or '_200' in url:
                score -= 5
            if 'icon' in url_lower:
                score -= 15
            
            # URL length (longer often means more parameters = higher res)
            if len(url) > 200:
                score += 2
            
            return score
        
        # Sort by quality score
        ranked = sorted(image_urls, key=quality_score, reverse=True)
        return ranked
    
    def calculate_similarity(self, str1: str, str2: str) -> float:
        """
        Calculate string similarity (0.0-1.0)
        
        Uses SequenceMatcher for fuzzy matching
        """
        try:
            return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()
        except:
            return 0.0
    
    def parse_price(self, price_text: str) -> Optional[float]:
        """
        Parse price from text
        
        Examples:
        - "$89.99" → 89.99
        - "CA$120.00" → 120.0
        - "€95" → 95.0
        """
        try:
            # Remove currency symbols and commas
            cleaned = price_text.replace('$', '').replace('CA$', '').replace('€', '').replace(',', '').strip()
            
            # Extract numeric value
            match = re.search(r'[\d,]+\.?\d*', cleaned.replace(',', ''))
            if match:
                return float(match.group(0))
        except Exception as e:
            logger.debug(f"Price parsing failed: {e}")
        
        return None
