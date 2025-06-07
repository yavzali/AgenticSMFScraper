"""
Image URL Enhancement System
Transforms low-resolution image URLs to high-resolution versions for better product images
"""

import re
import asyncio
import aiohttp
from typing import List, Dict, Optional, Tuple
from urllib.parse import urlparse, urljoin
import logging

from logger_config import setup_logging

logger = setup_logging(__name__)

class ImageURLEnhancer:
    """Enhance image URLs to high-resolution versions and validate quality"""
    
    def __init__(self):
        self.session = None
        self.transformation_rules = self._load_transformation_rules()
    
    def _load_transformation_rules(self) -> Dict[str, List[Dict]]:
        """Load retailer-specific image URL transformation rules"""
        return {
            "asos": [
                {
                    "pattern": r'\$S\$',
                    "replacement": '$XXL$',
                    "description": "Transform ASOS small to extra large"
                },
                {
                    "pattern": r'\$M\$',
                    "replacement": '$XXL$',
                    "description": "Transform ASOS medium to extra large"
                }
            ],
            "revolve": [
                {
                    "pattern": r'/n/ct/',
                    "replacement": '/n/z/',
                    "description": "Transform Revolve thumbnail to zoom"
                },
                {
                    "pattern": r'/n/d/',
                    "replacement": '/n/z/',
                    "description": "Transform Revolve detail to zoom"
                }
            ],
            "nordstrom": [
                {
                    "pattern": r'(\.[jpg|jpeg|png]+)$',
                    "replacement": r'?width=1200&height=1500\1',
                    "description": "Add high-res parameters to Nordstrom images"
                }
            ],
            "hm": [
                {
                    "pattern": r'(_\d+x\d+)(\.[jpg|jpeg|png]+)$',
                    "replacement": r'_2000x2000\2',
                    "description": "Transform H&M to highest resolution"
                }
            ],
            "uniqlo": [
                {
                    "pattern": r'(\.[jpg|jpeg|png]+)$',
                    "replacement": r'_l\1',
                    "description": "Add large suffix to Uniqlo images"
                }
            ],
            "urban_outfitters": [
                {
                    "pattern": r'(\.[jpg|jpeg|png]+)$',
                    "replacement": r'_xl\1',
                    "description": "Add extra large suffix to Urban Outfitters images"
                }
            ],
            "abercrombie": [
                {
                    "pattern": r'(\.[jpg|jpeg|png]+)$',
                    "replacement": r'_prod\1',
                    "description": "Add prod suffix to Abercrombie images"
                }
            ],
            "mango": [
                {
                    "pattern": r'(\.[jpg|jpeg|png]+)(\?.*)?$',
                    "replacement": r'\1?width=1200&height=1500',
                    "description": "Add size parameters to Mango images"
                }
            ],
            "anthropologie": [
                {
                    "pattern": r'(_\w+)(\.[jpg|jpeg|png]+)$',
                    "replacement": r'_xl\2',
                    "description": "Transform Anthropologie to extra large"
                }
            ],
            "aritzia": [
                {
                    "pattern": r'(_\d+x\d+)(\.[jpg|jpeg|png]+)$',
                    "replacement": r'_1200x1500\2',
                    "description": "Transform Aritzia to high resolution"
                }
            ]
        }
    
    async def enhance_image_urls(self, retailer: str, image_urls: List[str]) -> List[Dict]:
        """
        Enhance image URLs for a specific retailer
        Returns list of dicts with original, enhanced, and metadata
        """
        if not image_urls:
            return []
        
        results = []
        retailer_rules = self.transformation_rules.get(retailer.lower(), [])
        
        for original_url in image_urls:
            result = {
                'original_url': original_url,
                'enhanced_url': original_url,
                'transformations_applied': [],
                'quality_score': 0,
                'warnings': []
            }
            
            # Apply transformation rules
            enhanced_url = original_url
            for rule in retailer_rules:
                if re.search(rule['pattern'], enhanced_url):
                    enhanced_url = re.sub(rule['pattern'], rule['replacement'], enhanced_url)
                    result['transformations_applied'].append(rule['description'])
            
            result['enhanced_url'] = enhanced_url
            
            # Validate URL quality
            quality_info = self._assess_image_quality(enhanced_url)
            result.update(quality_info)
            
            results.append(result)
        
        return results
    
    def _assess_image_quality(self, url: str) -> Dict:
        """Assess image URL quality and detect potential issues"""
        quality_score = 0
        warnings = []
        
        # Check for high-resolution indicators
        high_res_indicators = [
            r'_xl\.',
            r'_l\.',
            r'_prod\.',
            r'\$XXL\$',
            r'/n/z/',
            r'width=\d{4,}',
            r'height=\d{4,}',
            r'_\d{4}x\d{4}',
            r'_2000x2000'
        ]
        
        for indicator in high_res_indicators:
            if re.search(indicator, url):
                quality_score += 20
                break
        
        # Check for thumbnail indicators (negative score)
        thumbnail_indicators = [
            r'thumb',
            r'_s\.',
            r'_small',
            r'\$S\$',
            r'/n/ct/',
            r'_\d{2,3}x\d{2,3}',
            r'_150x150'
        ]
        
        for indicator in thumbnail_indicators:
            if re.search(indicator, url):
                quality_score -= 30
                warnings.append(f"Detected thumbnail indicator: {indicator}")
        
        # Check domain reputation
        domain_scores = {
            'hmgoepprod.azureedge.net': 15,
            'image.uniqlo.com': 15,
            'n.nordstrommedia.com': 15,
            'images.urbndata.com': 15,
            'assets.anthropologie.com': 15,
            'media.aritzia.com': 15,
            'st.mngbcn.com': 10,
            'images.asos-media.com': 10
        }
        
        domain = urlparse(url).netloc
        if domain in domain_scores:
            quality_score += domain_scores[domain]
        
        # Check image format
        if url.lower().endswith(('.jpg', '.jpeg')):
            quality_score += 5
        elif url.lower().endswith('.png'):
            quality_score += 3
        elif url.lower().endswith('.webp'):
            quality_score += 8
        
        # Check for missing file extension
        if not re.search(r'\.(jpg|jpeg|png|webp)(\?|$)', url.lower()):
            warnings.append("Missing or unclear image file extension")
            quality_score -= 10
        
        return {
            'quality_score': max(0, min(100, quality_score)),
            'warnings': warnings
        }
    
    async def validate_image_urls(self, image_results: List[Dict]) -> List[Dict]:
        """
        Validate that enhanced URLs are accessible
        Returns results with accessibility information
        """
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        validated_results = []
        
        for result in image_results:
            enhanced_url = result['enhanced_url']
            
            try:
                async with self.session.head(enhanced_url, timeout=5) as response:
                    if response.status == 200:
                        result['url_accessible'] = True
                        result['content_type'] = response.headers.get('content-type', '')
                        result['content_length'] = response.headers.get('content-length', '')
                    else:
                        result['url_accessible'] = False
                        result['warnings'].append(f"Enhanced URL returned status {response.status}")
                        # Fall back to original URL
                        result['final_url'] = result['original_url']
                        
            except Exception as e:
                result['url_accessible'] = False
                result['warnings'].append(f"URL validation failed: {str(e)}")
                result['final_url'] = result['original_url']
            
            # Set final URL if not already set
            if 'final_url' not in result:
                result['final_url'] = result['enhanced_url']
            
            validated_results.append(result)
        
        return validated_results
    
    def get_best_image_urls(self, validated_results: List[Dict], max_images: int = 5) -> List[str]:
        """
        Get the best image URLs based on quality scores
        """
        # Sort by quality score descending
        sorted_results = sorted(validated_results, key=lambda x: x['quality_score'], reverse=True)
        
        # Return the final URLs for the top images
        return [result['final_url'] for result in sorted_results[:max_images]]
    
    def get_quality_report(self, validated_results: List[Dict]) -> Dict:
        """
        Generate a quality report for the image enhancement process
        """
        if not validated_results:
            return {'status': 'no_images', 'message': 'No images to analyze'}
        
        total_images = len(validated_results)
        enhanced_count = sum(1 for r in validated_results if r['transformations_applied'])
        accessible_count = sum(1 for r in validated_results if r.get('url_accessible', False))
        avg_quality = sum(r['quality_score'] for r in validated_results) / total_images
        
        all_warnings = []
        for result in validated_results:
            all_warnings.extend(result['warnings'])
        
        return {
            'status': 'completed',
            'total_images': total_images,
            'enhanced_count': enhanced_count,
            'accessible_count': accessible_count,
            'average_quality_score': round(avg_quality, 2),
            'enhancement_rate': round((enhanced_count / total_images) * 100, 2),
            'accessibility_rate': round((accessible_count / total_images) * 100, 2),
            'warnings': list(set(all_warnings)),
            'transformations_applied': list(set([
                t for r in validated_results 
                for t in r['transformations_applied']
            ]))
        }
    
    async def close(self):
        """Close the HTTP session"""
        if self.session:
            await self.session.close()
    
    def __del__(self):
        """Cleanup on destruction"""
        if self.session and not self.session.closed:
            asyncio.create_task(self.session.close())


# Convenience function for easy integration
async def enhance_product_images(retailer: str, image_urls: List[str]) -> Tuple[List[str], Dict]:
    """
    Convenience function to enhance image URLs and get quality report
    Returns (enhanced_urls, quality_report)
    """
    enhancer = ImageURLEnhancer()
    
    try:
        # Enhance URLs
        enhanced_results = await enhancer.enhance_image_urls(retailer, image_urls)
        
        # Validate URLs
        validated_results = await enhancer.validate_image_urls(enhanced_results)
        
        # Get best URLs
        best_urls = enhancer.get_best_image_urls(validated_results)
        
        # Generate quality report
        quality_report = enhancer.get_quality_report(validated_results)
        
        return best_urls, quality_report
        
    finally:
        await enhancer.close() 