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
        Main entry point for image processing - Downloads ALL quality images like old script
        """
        logger.info(f"Starting image processing for {self.retailer} with {len(extracted_image_urls)} URLs")
        
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
        
        downloaded_images = []
        
        # Process ALL extracted URLs (like old script behavior)
        for i, url in enumerate(extracted_image_urls):
            if i >= 5:  # Limit to 5 images maximum
                break
            extracted_image = await self._try_download_and_validate(url, f"extracted_{i+1}")
            if extracted_image:
                downloaded_images.append(extracted_image['path'])
        
        # If we got good images from extraction, return them
        if downloaded_images:
            logger.info(f"Successfully downloaded {len(downloaded_images)} extracted images for {self.retailer}")
            return downloaded_images
        
        # Layer 2: URL Reconstruction (retailer-specific) if extraction failed
        reconstructed_urls = await self.reconstruct_image_urls(product_url, product_data)
        if reconstructed_urls:
            for i, url in enumerate(reconstructed_urls[:5]):  # Try up to 5 reconstructed URLs
                reconstructed_image = await self._try_download_and_validate(url, f"reconstructed_{i+1}")
                if reconstructed_image:
                    downloaded_images.append(reconstructed_image['path'])
        
        # If we got reconstructed images, return them
        if downloaded_images:
            logger.info(f"Successfully downloaded {len(downloaded_images)} reconstructed images for {self.retailer}")
            return downloaded_images
        
        # Layer 3: Browser Use fallback (anti-scraping + screenshots)
        logger.warning(f"Primary processing failed for {self.retailer}, trying legacy fallback")
        browser_images = await self.browser_use_fallback(product_url, product_data)
        if browser_images:
            downloaded_images.extend(browser_images)
            logger.info(f"Successfully got {len(browser_images)} fallback images for {self.retailer}")
            return downloaded_images
        
        logger.warning(f"No images successfully downloaded for {self.retailer}")
        return []
    
    async def _try_download_and_validate(self, url: str, source: str) -> Optional[Dict]:
        """Download an image and validate its quality"""
        try:
            # Download image with retry logic for anti-scraping
            headers = self._get_download_headers(url)
            
            max_retries = 2
            for attempt in range(max_retries):
                try:
                    async with self.session.get(url, headers=headers, allow_redirects=True) as response:
                        if response.status == 200:
                            # Check Content-Type first (from working script pattern)
                            content_type = response.headers.get("content-type", "").lower()
                            if "image" not in content_type:
                                logger.debug(f"Invalid content-type for {source} image: {content_type}")
                                return None
                            
                            content = await response.read()
                            
                            # Validate content signatures as secondary check
                            if not self._validate_image_content(content):
                                logger.debug(f"Invalid image content for {source} image")
                                return None
                            
                            # For successful downloads, assess quality but don't filter
                            quality_result = await self._assess_image_quality(content, url)
                            
                            # Save image regardless of quality score (like old script)
                            file_path = await self._save_image(content, source, quality_result)
                            
                            logger.debug(f"Downloaded {source} image: quality={quality_result.quality_score}, "
                                       f"size={quality_result.file_size}, resolution={quality_result.resolution}")
                            
                            return {
                                'path': file_path,
                                'quality': quality_result,
                                'source': source,
                                'original_url': url
                            }
                        
                        elif response.status == 403:
                            # Special handling for 403 - common with image CDNs
                            domain = url.lower()
                            if any(img_domain in domain for img_domain in ["img.", "image.", "media.", "hmgoepprod.azureedge.net", "revolveassets.com", "asos-media.com", "aritzia.com"]):
                                logger.warning(f"403 on image domain (attempt {attempt+1}/{max_retries}): {url}")
                                if attempt < max_retries - 1:
                                    # Try with different headers on retry
                                    headers['User-Agent'] = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                                    await asyncio.sleep(1)  # Brief delay
                                    continue
                            logger.debug(f"Failed to download {source} image: HTTP {response.status}")
                            return None
                        
                        else:
                            logger.debug(f"Failed to download {source} image: HTTP {response.status}")
                            return None
                
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.debug(f"Download attempt {attempt+1} failed for {source}: {e}, retrying...")
                        await asyncio.sleep(1)
                        continue
                    else:
                        raise e
                        
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
        """Get appropriate headers for image download with retailer-specific anti-scraping"""
        
        # Base headers (working pattern from old script)
        base_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'image/jpeg,image/png,image/webp,*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'DNT': '1',
            'Sec-Fetch-Dest': 'image',
            'Sec-Fetch-Mode': 'no-cors',
            'Sec-Fetch-Site': 'cross-site',
        }
        
        # Retailer-specific headers (from working old script)
        if self.retailer == "hm":
            base_headers.update({
                'Referer': 'https://www2.hm.com/',
                'Accept': 'image/jpeg,image/png,*/*',
            })
        elif self.retailer == "aritzia":
            base_headers.update({
                'Referer': 'https://www.aritzia.com/',
                'Origin': 'https://www.aritzia.com',
                'Accept': 'image/jpeg,image/png,*/*',
            })
        elif self.retailer == "abercrombie":
            base_headers.update({
                'Referer': 'https://www.abercrombie.com/',
                'sec-ch-ua': '"Chromium";v="112"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
            })
        elif self.retailer == "revolve":
            base_headers.update({
                'Referer': 'https://www.revolve.com/',
            })
        elif self.retailer == "asos":
            base_headers.update({
                'Referer': 'https://www.asos.com/',
            })
        else:
            # Generic referer for other retailers
            base_headers['Referer'] = self._get_retailer_referer()
            base_headers['Origin'] = self._get_retailer_origin()
        
        return base_headers
    
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
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None
    
    def __del__(self):
        """Cleanup on destruction - improved to avoid runtime warnings"""
        if hasattr(self, 'session') and self.session and not self.session.closed:
            # Only attempt cleanup if there's an active event loop
            try:
                loop = asyncio.get_running_loop()
                if loop and not loop.is_closed():
                    # Create task for cleanup if we have a running loop
                    asyncio.create_task(self.session.close())
            except RuntimeError:
                # No running event loop - just set to None
                self.session = None 