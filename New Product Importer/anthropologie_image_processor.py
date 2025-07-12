"""
Anthropologie Image Processor - Enhanced lazy-loading and image quality handling
Addresses the specific challenge of color placeholder images instead of actual products
"""

# Add shared path for imports
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../Shared"))
sys.path.append(os.path.dirname(__file__))

import asyncio
import re
from typing import List, Dict, Any, Optional
from base_image_processor import BaseImageProcessor
from logger_config import setup_logging

logger = setup_logging(__name__)

class AnthropologieImageProcessor(BaseImageProcessor):
    """
    Specialized image processor for Anthropologie.com
    
    Addresses specific challenges:
    - Lazy-loading with color placeholders
    - Complex image URL patterns  
    - Multiple image variants per product
    - Anti-hotlinking protection
    """
    
    def __init__(self):
        super().__init__("anthropologie")  # Pass retailer name to parent
        self.base_domain = "anthropologie.com"
        self.cdn_domains = [
            "assets.anthropologie.com",
            "images.anthropologie.com", 
            "s7d2.scene7.com",  # Adobe Scene7 CDN
            "anthropologie.scene7.com"
        ]
        
        # Enhanced image quality thresholds for Anthropologie
        self.min_image_width = 600
        self.min_image_height = 600
        self.preferred_image_size = 1200
        
        logger.info(f"🎨 Initialized {self.__class__.__name__} for enhanced Anthropologie image processing")
    
    async def process_images_enhanced(self, image_urls: List[str], product_data: Dict[str, Any]) -> List[str]:
        """
        Enhanced image processing with lazy-loading awareness
        
        Args:
            image_urls: List of extracted image URLs
            product_data: Product information for context
            
        Returns:
            List of high-quality, processed image URLs
        """
        logger.info(f"🎨 Processing {len(image_urls)} Anthropologie images with enhanced lazy-loading support")
        
        if not image_urls:
            logger.warning("❌ No image URLs provided for processing")
            return []
        
        try:
            # Step 1: Filter and validate URLs
            valid_urls = await self._filter_valid_urls(image_urls)
            logger.debug(f"✅ Filtered to {len(valid_urls)} valid URLs")
            
            # Step 2: Enhance URLs for maximum quality
            enhanced_urls = await self._enhance_url_quality(valid_urls)
            logger.debug(f"✅ Enhanced {len(enhanced_urls)} URLs for quality")
            
            # Step 3: Remove duplicates and rank by quality
            final_urls = await self._deduplicate_and_rank(enhanced_urls, product_data)
            logger.debug(f"✅ Final selection: {len(final_urls)} high-quality images")
            
            # Step 4: Validate final quality
            validated_urls = await self._validate_final_quality(final_urls)
            
            logger.info(f"🎨 Anthropologie processing complete: {len(validated_urls)} quality images")
            return validated_urls[:5]  # Limit to top 5 images
            
        except Exception as e:
            logger.error(f"❌ Enhanced image processing failed: {e}")
            # Fallback to basic processing
            return await self._fallback_processing(image_urls)
    
    async def _filter_valid_urls(self, image_urls: List[str]) -> List[str]:
        """Filter URLs to exclude placeholders and low-quality images"""
        valid_urls = []
        
        # Patterns to exclude (placeholders, thumbnails, etc.)
        exclude_patterns = [
            r'placeholder',
            r'loading',
            r'spinner',
            r'_sw\.jpg',  # Small width thumbnails
            r'_xs\.jpg',  # Extra small
            r'_s\.jpg',   # Small  
            r'\.svg',     # Vector graphics (usually placeholders)
            r'data:image', # Base64 embedded (usually placeholders)
            r'blank\.gif',
            r'spacer\.gif',
            r'_thumb',
            r'_icon'
        ]
        
        for url in image_urls:
            if not url or len(url) < 10:
                continue
                
            # Check for exclusion patterns
            if any(re.search(pattern, url, re.IGNORECASE) for pattern in exclude_patterns):
                logger.debug(f"🚫 Excluded placeholder/thumbnail: {url[:100]}")
                continue
            
            # Must be from trusted domains
            if any(domain in url for domain in self.cdn_domains):
                valid_urls.append(url)
                logger.debug(f"✅ Valid Anthropologie URL: {url[:100]}")
            else:
                logger.debug(f"⚠️ External domain URL: {url[:100]}")
        
        return valid_urls
    
    async def _enhance_url_quality(self, image_urls: List[str]) -> List[str]:
        """
        Transform URLs to highest quality versions
        Based on Anthropologie's URL patterns
        """
        enhanced_urls = []
        
        for url in image_urls:
            try:
                enhanced_url = await self._transform_to_high_quality(url)
                if enhanced_url and enhanced_url not in enhanced_urls:
                    enhanced_urls.append(enhanced_url)
                    logger.debug(f"🔧 Enhanced: {url[:50]} → {enhanced_url[:50]}")
            except Exception as e:
                logger.warning(f"⚠️ URL enhancement failed for {url[:50]}: {e}")
                # Keep original URL as fallback
                if url not in enhanced_urls:
                    enhanced_urls.append(url)
        
        return enhanced_urls
    
    async def _transform_to_high_quality(self, url: str) -> str:
        """
        Transform Anthropologie image URL to highest quality version
        
        Anthropologie URL patterns:
        - Thumbnail: *_330_430.jpg
        - Medium: *_650_845.jpg  
        - Large: *_1094_1405.jpg
        - Zoom: *_1640_2100.jpg
        """
        
        # Pattern transformations for quality upgrade
        quality_transformations = [
            # Size-based transformations (width_height)
            (r'_(\d+)_(\d+)\.jpg', '_1094_1405.jpg'),  # Standard to large
            (r'_(\d+)_(\d+)\.jpeg', '_1094_1405.jpeg'),
            (r'_(\d+)_(\d+)\.png', '_1094_1405.png'),
            
            # Specific Anthropologie patterns
            (r'_sw\.jpg', '_xl.jpg'),          # Small width to extra large
            (r'_s\.jpg', '_l.jpg'),            # Small to large
            (r'_m\.jpg', '_xl.jpg'),           # Medium to extra large
            (r'_thumb\.jpg', '_main.jpg'),     # Thumbnail to main
            
            # Adobe Scene7 transformations
            (r'\$product\$', '$zoom$'),        # Product view to zoom
            (r'\$thumbnail\$', '$large$'),     # Thumbnail to large
            (r'wid=\d+', 'wid=1200'),         # Width parameter
            (r'hei=\d+', 'hei=1500'),         # Height parameter
        ]
        
        enhanced_url = url
        
        for pattern, replacement in quality_transformations:
            if re.search(pattern, enhanced_url, re.IGNORECASE):
                new_url = re.sub(pattern, replacement, enhanced_url, flags=re.IGNORECASE)
                logger.debug(f"🔧 Pattern match: {pattern} → {replacement}")
                enhanced_url = new_url
                break
        
        # If no transformations applied, try adding quality parameters
        if enhanced_url == url and '?' not in url:
            if 'scene7.com' in url:
                enhanced_url += '?wid=1200&hei=1500&fmt=jpeg&qlt=85'
            elif 'anthropologie.com' in url:
                enhanced_url += '?format=1200w'
        
        return enhanced_url
    
    async def _deduplicate_and_rank(self, image_urls: List[str], product_data: Dict[str, Any]) -> List[str]:
        """Remove duplicates and rank by quality indicators"""
        
        # Remove exact duplicates
        unique_urls = list(dict.fromkeys(image_urls))
        
        # Score each URL by quality indicators
        scored_urls = []
        for url in unique_urls:
            score = await self._calculate_image_quality_score(url, product_data)
            scored_urls.append((score, url))
        
        # Sort by score (highest first)
        scored_urls.sort(key=lambda x: x[0], reverse=True)
        
        # Extract URLs in quality order
        ranked_urls = [url for score, url in scored_urls]
        
        logger.debug(f"🏆 Ranked {len(ranked_urls)} URLs by quality score")
        return ranked_urls
    
    async def _calculate_image_quality_score(self, url: str, product_data: Dict[str, Any]) -> float:
        """
        Calculate quality score for an image URL
        Higher score = better quality
        """
        score = 0.0
        
        # Size indicators in URL (higher is better)
        size_matches = re.findall(r'_(\d+)_(\d+)', url)
        if size_matches:
            width, height = map(int, size_matches[0])
            score += (width * height) / 10000  # Normalize to reasonable range
        
        # Quality keywords (positive scoring)
        quality_keywords = {
            'zoom': 15, 'large': 10, 'xl': 8, 'main': 6, 
            '1094': 12, '1640': 15, 'high': 5
        }
        
        for keyword, points in quality_keywords.items():
            if keyword in url.lower():
                score += points
        
        # File format preferences
        if url.lower().endswith('.jpg') or url.lower().endswith('.jpeg'):
            score += 2
        elif url.lower().endswith('.png'):
            score += 1
        
        # CDN preferences (Anthropologie's main CDN gets priority)
        if 'assets.anthropologie.com' in url:
            score += 5
        elif 'scene7.com' in url:
            score += 3
        
        # Penalty for likely lower quality
        if any(term in url.lower() for term in ['thumb', 'small', 'icon', '_s_', '_xs_']):
            score -= 10
        
        logger.debug(f"📊 Quality score {score:.1f} for: {url[:80]}")
        return score
    
    async def _validate_final_quality(self, image_urls: List[str]) -> List[str]:
        """Final validation step to ensure image quality"""
        validated_urls = []
        
        for url in image_urls:
            # Basic URL validation
            if not url or len(url) < 20:
                continue
            
            # Must be HTTPS for security
            if not url.startswith('https://'):
                if url.startswith('http://'):
                    url = url.replace('http://', 'https://', 1)
                else:
                    continue
            
            # Final quality check
            if await self._passes_quality_check(url):
                validated_urls.append(url)
                logger.debug(f"✅ Validated: {url[:80]}")
            else:
                logger.debug(f"❌ Failed validation: {url[:80]}")
        
        return validated_urls
    
    async def _passes_quality_check(self, url: str) -> bool:
        """Check if URL meets final quality standards"""
        
        # Size indicators suggest good quality
        size_matches = re.findall(r'_(\d+)_(\d+)', url)
        if size_matches:
            width, height = map(int, size_matches[0])
            if width >= self.min_image_width and height >= self.min_image_height:
                return True
        
        # Quality keywords present
        quality_indicators = ['large', 'xl', 'zoom', 'main', '1094', '1640']
        if any(indicator in url.lower() for indicator in quality_indicators):
            return True
        
        # From trusted CDN and reasonable length
        if any(domain in url for domain in self.cdn_domains) and len(url) > 50:
            return True
        
        return False
    
    async def _fallback_processing(self, image_urls: List[str]) -> List[str]:
        """Fallback processing if enhanced processing fails"""
        logger.warning("🔄 Using fallback image processing for Anthropologie")
        
        # Basic filtering only
        basic_urls = []
        for url in image_urls:
            if (url and len(url) > 20 and 
                any(domain in url for domain in self.cdn_domains) and
                not any(term in url.lower() for term in ['placeholder', 'loading', '.svg'])):
                basic_urls.append(url)
        
        return basic_urls[:3]  # Return top 3 as fallback
    
    async def get_enhanced_wait_conditions(self) -> Dict[str, Any]:
        """
        Return enhanced wait conditions for Playwright agent
        Specifically designed for Anthropologie's lazy-loading
        """
        return {
            'wait_conditions': [
                'networkidle',  # Wait for all network requests
                'img[src*="anthropologie.com"]:not([src*="placeholder"])',  # Actual images loaded
                'img[data-src]:not([loading="lazy"])',  # Lazy-loading completed
                '.product-images img[src]:not([src=""])',  # Non-empty image sources
                '.hero-image img[src]:not([src*="loading"])',  # Hero image loaded
            ],
            'extended_timeout': 25000,  # 25 seconds for image loading
            'pre_screenshot_scroll': True,  # Trigger lazy loading
            'scroll_delay': 3000,  # Wait 3 seconds after scroll
            'image_load_verification': True,  # Verify images actually loaded
            'quality_validation': True  # Reject placeholder colors
        }
    
    def get_processor_info(self) -> Dict[str, Any]:
        """Return processor information and capabilities"""
        return {
            'processor_name': 'AnthropologieImageProcessor',
            'version': '1.0.0',
            'capabilities': [
                'lazy_loading_support',
                'placeholder_detection', 
                'quality_enhancement',
                'url_transformation',
                'duplicate_removal',
                'quality_ranking'
            ],
            'supported_domains': self.cdn_domains,
            'min_image_size': f"{self.min_image_width}x{self.min_image_height}",
            'max_images': 5,
            'specialization': 'Enhanced handling of Anthropologie lazy-loading and placeholder issues'
        }
    
    # Abstract method implementations from BaseImageProcessor
    async def reconstruct_image_urls(self, product_url: str, product_data: Dict) -> List[str]:
        """
        Reconstruct high-quality image URLs from product URL
        Anthropologie-specific URL pattern reconstruction
        """
        logger.info(f"🔧 Reconstructing Anthropologie image URLs from: {product_url}")
        
        try:
            # Extract product ID from URL
            # Anthropologie URLs typically: /shop/product-name?category=...&color=...&type=...
            import re
            
            # Try to extract product identifiers
            url_patterns = [
                r'/shop/([^/?]+)',  # Product name from shop URL
                r'color=([^&]+)',   # Color variant
                r'type=([^&]+)',    # Product type
                r'quantity=([^&]+)' # Quantity (sometimes has product info)
            ]
            
            extracted_info = {}
            for pattern in url_patterns:
                match = re.search(pattern, product_url)
                if match:
                    extracted_info[pattern] = match.group(1)
            
            if not extracted_info:
                logger.warning("⚠️ Could not extract product info from Anthropologie URL")
                return []
            
            # Build potential image URLs based on common Anthropologie patterns
            reconstructed_urls = []
            
            # If we have a product name, try common image URL patterns
            if '/shop/([^/?]+)' in extracted_info:
                product_name = extracted_info['/shop/([^/?]+)']
                
                # Common Anthropologie image URL patterns
                base_patterns = [
                    f"https://assets.anthropologie.com/is/image/Anthropologie/{product_name}_001_b.jpg",
                    f"https://assets.anthropologie.com/is/image/Anthropologie/{product_name}_002_b.jpg", 
                    f"https://assets.anthropologie.com/is/image/Anthropologie/{product_name}_003_b.jpg",
                    f"https://assets.anthropologie.com/is/image/Anthropologie/{product_name}_1094_1405.jpg",
                    f"https://s7d2.scene7.com/is/image/Anthropologie/{product_name}_001_b.jpg",
                ]
                
                reconstructed_urls.extend(base_patterns)
            
            # Try numeric product ID patterns (common in their system)
            numeric_matches = re.findall(r'\d{10,}', product_url)
            for product_id in numeric_matches:
                id_patterns = [
                    f"https://assets.anthropologie.com/is/image/Anthropologie/{product_id}_001_b.jpg",
                    f"https://assets.anthropologie.com/is/image/Anthropologie/{product_id}_1094_1405.jpg",
                    f"https://s7d2.scene7.com/is/image/Anthropologie/{product_id}_zoom.jpg",
                ]
                reconstructed_urls.extend(id_patterns)
            
            logger.info(f"🔧 Reconstructed {len(reconstructed_urls)} potential Anthropologie image URLs")
            return reconstructed_urls[:10]  # Limit to top 10 attempts
            
        except Exception as e:
            logger.error(f"❌ URL reconstruction failed: {e}")
            return []
    
    def _get_retailer_referer(self) -> str:
        """Return the referer header for Anthropologie requests"""
        return "https://www.anthropologie.com/"
    
    def _get_retailer_origin(self) -> str:
        """Return the origin header for Anthropologie requests"""
        return "https://www.anthropologie.com" 