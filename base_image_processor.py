"""
Base Image Processor - Interface for all retailer-specific image processors
Implements the optimized 4-layer architecture with quality-first validation
"""

import os
import asyncio
import aiohttp
import aiofiles
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Tuple
from urllib.parse import urlparse
import uuid
from datetime import datetime
from PIL import Image
import io

from logger_config import setup_logging

logger = setup_logging(__name__)

class ImageQualityResult:
    """Result of image quality assessment"""
    def __init__(self, is_high_quality: bool, quality_score: int, resolution: Tuple[int, int], 
                 file_size: int, reasons: List[str]):
        self.is_high_quality = is_high_quality
        self.quality_score = quality_score
        self.resolution = resolution
        self.file_size = file_size
        self.reasons = reasons

class BaseImageProcessor(ABC):
    """Base class for all retailer-specific image processors"""
    
    def __init__(self, retailer: str):
        self.retailer = retailer
        self.download_dir = f"downloads/{retailer}_images"
        self.session = None
        self._ensure_download_directory()
        
        # Quality thresholds
        self.MIN_HIGH_QUALITY_RESOLUTION = (800, 800)
        self.MIN_HIGH_QUALITY_FILE_SIZE = 100 * 1024  # 100KB
        self.HIGH_QUALITY_SCORE_THRESHOLD = 80
        
    def _ensure_download_directory(self):
        """Ensure download directory exists"""
        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir, exist_ok=True)
            logger.debug(f"Created download directory: {self.download_dir}")
    
    async def process_images(self, extracted_image_urls: List[str], product_url: str, 
                           product_data: Dict) -> List[str]:
        """
        Main entry point for image processing with quality-first optimization
        """
        logger.info(f"Starting image processing for {self.retailer} with {len(extracted_image_urls)} URLs")
        
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
        
        downloaded_images = []
        
        # Layer 1: Try first extracted URL
        if extracted_image_urls:
            first_image = await self._try_download_and_validate(extracted_image_urls[0], "extracted_primary")
            if first_image and first_image['quality'].is_high_quality:
                logger.info(f"First extracted image is high quality, stopping here")
                downloaded_images.append(first_image['path'])
                return downloaded_images
            elif first_image:
                downloaded_images.append(first_image)
        
        # Layer 2: URL Reconstruction (retailer-specific)
        reconstructed_urls = await self.reconstruct_image_urls(product_url, product_data)
        if reconstructed_urls:
            for url in reconstructed_urls[:3]:  # Try up to 3 reconstructed URLs
                reconstructed_image = await self._try_download_and_validate(url, "reconstructed")
                if reconstructed_image and reconstructed_image['quality'].is_high_quality:
                    logger.info(f"Reconstructed image is high quality, stopping here")
                    downloaded_images = [reconstructed_image['path']]  # Replace with better image
                    return downloaded_images
                elif reconstructed_image:
                    downloaded_images.append(reconstructed_image)
        
        # Layer 3: Try remaining extracted URLs
        for url in extracted_image_urls[1:5]:  # Try up to 4 more extracted URLs
            extracted_image = await self._try_download_and_validate(url, "extracted_additional")
            if extracted_image and extracted_image['quality'].is_high_quality:
                logger.info(f"Additional extracted image is high quality, stopping here")
                downloaded_images = [extracted_image['path']]  # Replace with better image
                return downloaded_images
            elif extracted_image:
                downloaded_images.append(extracted_image)
        
        # Layer 4: Browser Use fallback (anti-scraping + screenshots)
        browser_images = await self.browser_use_fallback(product_url, product_data)
        downloaded_images.extend(browser_images)
        
        # Return best available image(s)
        if downloaded_images:
            # If we have multiple images, return the best quality one
            if len(downloaded_images) > 1 and isinstance(downloaded_images[0], dict):
                best_image = max(downloaded_images, key=lambda x: x['quality'].quality_score if isinstance(x, dict) else 0)
                return [best_image['path'] if isinstance(best_image, dict) else best_image]
            elif isinstance(downloaded_images[0], dict):
                return [downloaded_images[0]['path']]
            else:
                return downloaded_images[:1]  # Return just the first image
        
        logger.warning(f"No images successfully downloaded for {self.retailer}")
        return []
    
    async def _try_download_and_validate(self, url: str, source: str) -> Optional[Dict]:
        """Download an image and validate its quality"""
        try:
            # Download image
            headers = self._get_download_headers(url)
            
            async with self.session.get(url, headers=headers) as response:
                if response.status != 200:
                    logger.debug(f"Failed to download {source} image: HTTP {response.status}")
                    return None
                
                content = await response.read()
                
                # Validate content
                if not self._validate_image_content(content):
                    logger.debug(f"Invalid image content for {source} image")
                    return None
                
                # Assess quality
                quality_result = await self._assess_image_quality(content, url)
                
                # Save image
                file_path = await self._save_image(content, source, quality_result)
                
                logger.debug(f"Downloaded {source} image: quality={quality_result.quality_score}, "
                           f"size={quality_result.file_size}, resolution={quality_result.resolution}")
                
                return {
                    'path': file_path,
                    'quality': quality_result,
                    'source': source,
                    'original_url': url
                }
                
        except Exception as e:
            logger.debug(f"Error downloading {source} image from {url}: {e}")
            return None
    
    async def _assess_image_quality(self, content: bytes, url: str) -> ImageQualityResult:
        """Comprehensive image quality assessment"""
        
        quality_score = 0
        reasons = []
        
        # File size assessment
        file_size = len(content)
        if file_size >= self.MIN_HIGH_QUALITY_FILE_SIZE:
            quality_score += 30
        elif file_size >= 50 * 1024:  # 50KB
            quality_score += 15
            reasons.append("File size is moderate")
        else:
            reasons.append("File size is small (likely thumbnail)")
        
        # Resolution assessment
        try:
            image = Image.open(io.BytesIO(content))
            width, height = image.size
            
            if width >= self.MIN_HIGH_QUALITY_RESOLUTION[0] and height >= self.MIN_HIGH_QUALITY_RESOLUTION[1]:
                quality_score += 40
            elif width >= 400 and height >= 400:
                quality_score += 20
                reasons.append("Resolution is moderate")
            else:
                reasons.append(f"Resolution is low: {width}x{height}")
            
            # Aspect ratio check (prefer non-square for clothing)
            aspect_ratio = width / height
            if 0.6 <= aspect_ratio <= 0.9 or 1.1 <= aspect_ratio <= 1.67:  # Good clothing ratios
                quality_score += 10
            
        except Exception as e:
            width, height = 0, 0
            reasons.append(f"Could not determine resolution: {e}")
        
        # URL pattern assessment
        url_lower = url.lower()
        
        # Positive indicators
        high_res_indicators = ['_xl', '_l', '_large', '_big', '_hd', '_2000', '_1200', 'width=', 'high']
        for indicator in high_res_indicators:
            if indicator in url_lower:
                quality_score += 10
                break
        
        # Negative indicators (thumbnails)
        thumbnail_indicators = ['thumb', '_s', '_small', '_tiny', '_mini', '_150', '_300', 'ct/', 'preview']
        for indicator in thumbnail_indicators:
            if indicator in url_lower:
                quality_score -= 20
                reasons.append(f"URL contains thumbnail indicator: {indicator}")
                break
        
        # Domain reputation
        domain = urlparse(url).netloc
        trusted_domains = [
            'image.uniqlo.com', 'n.nordstrommedia.com', 'hmgoepprod.azureedge.net',
            'assets.anthropologie.com', 'media.aritzia.com', 'images.asos-media.com'
        ]
        if any(trusted in domain for trusted in trusted_domains):
            quality_score += 15
        
        # Final assessment
        quality_score = max(0, min(100, quality_score))
        is_high_quality = (
            quality_score >= self.HIGH_QUALITY_SCORE_THRESHOLD and
            file_size >= self.MIN_HIGH_QUALITY_FILE_SIZE and
            width >= self.MIN_HIGH_QUALITY_RESOLUTION[0] and
            height >= self.MIN_HIGH_QUALITY_RESOLUTION[1]
        )
        
        return ImageQualityResult(is_high_quality, quality_score, (width, height), file_size, reasons)
    
    async def _save_image(self, content: bytes, source: str, quality: ImageQualityResult) -> str:
        """Save image with descriptive filename"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        
        # Include quality info in filename
        quality_suffix = "HQ" if quality.is_high_quality else f"Q{quality.quality_score}"
        filename = f"{self.retailer}_{source}_{quality_suffix}_{timestamp}_{unique_id}.jpg"
        file_path = os.path.join(self.download_dir, filename)
        
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(content)
        
        return file_path
    
    def _validate_image_content(self, content: bytes) -> bool:
        """Validate that content is actually an image"""
        if len(content) < 100:
            return False
        
        # Check image signatures
        signatures = [
            b'\xFF\xD8\xFF',      # JPEG
            b'\x89PNG\r\n\x1a\n', # PNG
            b'GIF87a', b'GIF89a', # GIF
            b'RIFF'               # WebP
        ]
        
        for sig in signatures:
            if content.startswith(sig):
                return True
        
        # Additional WebP check
        if content.startswith(b'RIFF') and b'WEBP' in content[:12]:
            return True
        
        return False
    
    def _get_download_headers(self, url: str) -> Dict[str, str]:
        """Get appropriate headers for image download"""
        return {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept': 'image/avif,image/webp,image/png,image/svg+xml,image/*;q=0.8,*/*;q=0.5',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'image',
            'Sec-Fetch-Mode': 'no-cors',
            'Sec-Fetch-Site': 'cross-site',
            'Referer': self._get_retailer_referer(),
            'Origin': self._get_retailer_origin()
        }
    
    @abstractmethod
    async def reconstruct_image_urls(self, product_url: str, product_data: Dict) -> List[str]:
        """
        Retailer-specific URL reconstruction logic
        Should return list of high-quality image URLs built from product codes/patterns
        """
        pass
    
    @abstractmethod
    def _get_retailer_referer(self) -> str:
        """Get appropriate referer for this retailer"""
        pass
    
    @abstractmethod
    def _get_retailer_origin(self) -> str:
        """Get appropriate origin for this retailer"""
        pass
    
    async def browser_use_fallback(self, product_url: str, product_data: Dict) -> List[str]:
        """
        Browser Use fallback for anti-scraping and screenshots
        Default implementation - can be overridden by retailers
        """
        logger.info(f"Browser Use fallback not implemented for {self.retailer}")
        return []
    
    async def close(self):
        """Clean up resources"""
        if self.session:
            await self.session.close()
    
    def __del__(self):
        """Cleanup on destruction"""
        if hasattr(self, 'session') and self.session and not self.session.closed:
            asyncio.create_task(self.session.close()) 