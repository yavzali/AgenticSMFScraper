"""
Image Processor - Centralized image handling for all workflows
Handles URL enhancement, downloading, validation, and quality ranking

Preserves retailer-specific logic from:
- anthropologie_image_processor.py (URL transformations, lazy-loading)
- aritzia_image_processor.py (CDN patterns)
- uniqlo_image_processor.py (URL patterns)
- base_image_processor.py (quality ranking, validation)

Integrates with pattern learning for continuous improvement
"""

import os
import sys
import re
import asyncio
import aiohttp
import hashlib
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from PIL import Image
from io import BytesIO
import logging

# Add shared path for imports
sys.path.append(os.path.dirname(__file__))
from logger_config import setup_logging

logger = setup_logging(__name__)


class ImageProcessor:
    """
    Centralized image processing with retailer-specific enhancements
    
    Capabilities:
    1. URL Enhancement: Transform URLs to highest quality versions
    2. Quality Ranking: Score and rank images by quality indicators
    3. Validation: Filter out placeholders, thumbnails, broken URLs
    4. Download: Fetch images from URLs and save to disk
    5. Pattern Learning: Track successful transformations per retailer
    """
    
    def __init__(self, download_base_dir: str = None):
        self.download_base_dir = download_base_dir or os.path.join(
            os.path.dirname(__file__), "downloads"
        )
        
        # Ensure download directories exist
        os.makedirs(self.download_base_dir, exist_ok=True)
        
        # Pattern learning database path
        self.pattern_db_path = os.path.join(
            os.path.dirname(__file__), "image_patterns.db"
        )
        
        # Initialize pattern learning
        self._init_pattern_learning()
        
        logger.info(f"✅ ImageProcessor initialized (downloads: {self.download_base_dir})")
    
    def _init_pattern_learning(self):
        """Initialize SQLite database for tracking image processing patterns"""
        import sqlite3
        
        try:
            conn = sqlite3.connect(self.pattern_db_path)
            cursor = conn.cursor()
            
            # Table: Track URL transformation success
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS url_transformations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    retailer TEXT NOT NULL,
                    original_pattern TEXT,
                    transformed_pattern TEXT,
                    success_count INTEGER DEFAULT 0,
                    failure_count INTEGER DEFAULT 0,
                    avg_quality_score REAL DEFAULT 0.0,
                    last_used TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Table: Track download success rates per retailer
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS download_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    retailer TEXT NOT NULL,
                    url_pattern TEXT,
                    download_success INTEGER DEFAULT 0,
                    download_failure INTEGER DEFAULT 0,
                    avg_file_size INTEGER DEFAULT 0,
                    avg_dimensions TEXT,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Table: Track placeholder patterns (to avoid)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS placeholder_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    retailer TEXT NOT NULL,
                    pattern TEXT NOT NULL,
                    detection_count INTEGER DEFAULT 0,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            conn.close()
            
            logger.debug("📊 Image pattern learning database initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize pattern learning: {e}")
    
    async def process_images(
        self,
        image_urls: List[str],
        retailer: str,
        product_title: str = "Product"
    ) -> List[str]:
        """
        Complete image processing pipeline
        
        Args:
            image_urls: Raw image URLs from extraction
            retailer: Retailer name (for specific transformations)
            product_title: Product title (for filename generation)
        
        Returns:
            List of local file paths (ready for Shopify upload)
        
        Process:
        1. Filter invalid/placeholder URLs
        2. Enhance URLs (retailer-specific transformations)
        3. Rank by quality indicators
        4. Download top 5 images
        5. Validate downloaded images
        6. Learn from results
        """
        logger.info(f"🖼️ Processing {len(image_urls)} images for {retailer}")
        
        if not image_urls:
            logger.warning("⚠️ No image URLs provided")
            return []
        
        try:
            # Step 1: Filter out invalid URLs
            valid_urls = await self._filter_valid_urls(image_urls, retailer)
            logger.debug(f"✅ Filtered to {len(valid_urls)} valid URLs")
            
            if not valid_urls:
                logger.warning("⚠️ No valid URLs after filtering")
                return []
            
            # Step 2: Enhance URLs (retailer-specific)
            enhanced_urls = await self._enhance_urls(valid_urls, retailer)
            logger.debug(f"✅ Enhanced {len(enhanced_urls)} URLs")
            
            # Step 3: Rank by quality
            ranked_urls = self._rank_by_quality(enhanced_urls, retailer)[:5]
            logger.debug(f"✅ Ranked and selected top {len(ranked_urls)} images")
            
            # Step 4: Download images
            file_paths = await self._download_images(ranked_urls, retailer, product_title)
            logger.info(f"✅ Successfully downloaded {len(file_paths)} images")
            
            # Step 5: Learn from results
            await self._learn_from_results(ranked_urls, file_paths, retailer)
            
            return file_paths
            
        except Exception as e:
            logger.error(f"❌ Image processing failed: {e}")
            return []
    
    async def _filter_valid_urls(self, image_urls: List[str], retailer: str) -> List[str]:
        """
        Filter out placeholder, thumbnail, and invalid URLs
        Uses learned patterns + static exclusion rules
        """
        valid_urls = []
        
        # Load learned placeholder patterns for this retailer
        learned_patterns = await self._get_placeholder_patterns(retailer)
        
        # Static exclusion patterns (common across retailers)
        static_exclude_patterns = [
            r'placeholder',
            r'loading',
            r'spinner',
            r'blank\.gif',
            r'spacer\.gif',
            r'data:image',  # Base64 embedded images
            r'\.svg$',  # Vector graphics (usually placeholders)
            r'_icon',
            r'logo',
            r'badge',
            r'/icons?/',
            r'/badges?/',
            # NOTE: _V\d+ patterns (Revolve) are NOT excluded here
            # They are kept and transformed to full-size in _enhance_urls()
        ]
        
        all_exclude_patterns = static_exclude_patterns + learned_patterns
        
        for url in image_urls:
            if not url or len(url) < 10:
                continue
            
            # Check exclusion patterns
            if any(re.search(pattern, url, re.IGNORECASE) for pattern in all_exclude_patterns):
                logger.debug(f"🚫 Excluded (placeholder/icon): {url[:80]}")
                continue
            
            # Must be HTTP/HTTPS
            if not url.startswith(('http://', 'https://')):
                logger.debug(f"🚫 Excluded (invalid protocol): {url[:80]}")
                continue
            
            valid_urls.append(url)
        
        return valid_urls
    
    async def _enhance_urls(self, image_urls: List[str], retailer: str) -> List[str]:
        """
        Apply retailer-specific URL transformations to get highest quality
        Uses learned patterns + static transformation rules
        """
        enhanced_urls = []
        
        for url in image_urls:
            try:
                # Apply retailer-specific transformation
                if retailer == 'anthropologie':
                    enhanced_url = self._transform_anthropologie_url(url)
                elif retailer == 'aritzia':
                    enhanced_url = self._transform_aritzia_url(url)
                elif retailer == 'uniqlo':
                    enhanced_url = self._transform_uniqlo_url(url)
                elif retailer == 'abercrombie':
                    enhanced_url = self._transform_abercrombie_url(url)
                elif retailer == 'revolve':
                    enhanced_url = self._transform_revolve_url(url)
                elif retailer == 'urban_outfitters':
                    enhanced_url = self._transform_urban_outfitters_url(url)
                elif retailer == 'nordstrom':
                    enhanced_url = self._transform_nordstrom_url(url)
                else:
                    # Generic enhancement
                    enhanced_url = self._transform_generic_url(url)
                
                if enhanced_url and enhanced_url not in enhanced_urls:
                    enhanced_urls.append(enhanced_url)
                    if enhanced_url != url:
                        logger.debug(f"🔧 Enhanced: {url[:50]} → {enhanced_url[:50]}")
                
            except Exception as e:
                logger.warning(f"⚠️ Enhancement failed for {url[:50]}: {e}")
                # Keep original on failure
                if url not in enhanced_urls:
                    enhanced_urls.append(url)
        
        return enhanced_urls
    
    def _transform_anthropologie_url(self, url: str) -> str:
        """
        Anthropologie-specific transformations
        
        URL patterns:
        - Thumbnail: *_330_430.jpg
        - Medium: *_650_845.jpg
        - Large: *_1094_1405.jpg (TARGET)
        - Zoom: *_1640_2100.jpg
        - Adobe Scene7: $product$ → $zoom$, wid/hei params
        """
        enhanced = url
        
        # Size-based transformations
        enhanced = re.sub(r'_(\d+)_(\d+)\.(jpg|jpeg|png)', r'_1094_1405.\3', enhanced, flags=re.IGNORECASE)
        
        # Suffix transformations
        enhanced = re.sub(r'_sw\.(jpg|jpeg)', r'_xl.\1', enhanced, flags=re.IGNORECASE)
        enhanced = re.sub(r'_s\.(jpg|jpeg)', r'_l.\1', enhanced, flags=re.IGNORECASE)
        enhanced = re.sub(r'_m\.(jpg|jpeg)', r'_xl.\1', enhanced, flags=re.IGNORECASE)
        enhanced = re.sub(r'_thumb\.(jpg|jpeg)', r'_main.\1', enhanced, flags=re.IGNORECASE)
        
        # Adobe Scene7 transformations
        enhanced = enhanced.replace('$product$', '$zoom$')
        enhanced = enhanced.replace('$thumbnail$', '$large$')
        enhanced = re.sub(r'wid=\d+', 'wid=1200', enhanced)
        enhanced = re.sub(r'hei=\d+', 'hei=1500', enhanced)
        
        # Add quality parameters if none exist
        if enhanced == url and '?' not in enhanced:
            if 'scene7.com' in enhanced:
                enhanced += '?wid=1200&hei=1500&fmt=jpeg&qlt=85'
            elif 'anthropologie.com' in enhanced:
                enhanced += '?format=1200w'
        
        return enhanced
    
    def _transform_aritzia_url(self, url: str) -> str:
        """
        Aritzia-specific transformations
        
        URL patterns:
        - Uses media.aritzia.com CDN
        - Size indicators: _small, _medium, _large
        """
        enhanced = url
        
        # Size transformations
        enhanced = re.sub(r'_small\.(jpg|jpeg|png)', r'_large.\1', enhanced, flags=re.IGNORECASE)
        enhanced = re.sub(r'_medium\.(jpg|jpeg|png)', r'_large.\1', enhanced, flags=re.IGNORECASE)
        enhanced = re.sub(r'_thumb\.(jpg|jpeg|png)', r'_large.\1', enhanced, flags=re.IGNORECASE)
        
        # Width parameter transformations
        enhanced = re.sub(r'w=\d+', 'w=1200', enhanced)
        enhanced = re.sub(r'width=\d+', 'width=1200', enhanced)
        
        return enhanced
    
    def _transform_uniqlo_url(self, url: str) -> str:
        """
        Uniqlo-specific transformations
        
        URL patterns:
        - Size indicators in path
        - Width parameters
        """
        enhanced = url
        
        # Size transformations
        enhanced = re.sub(r'/\d{3}w/', '/1200w/', enhanced)
        enhanced = re.sub(r'_\d{3}\.(jpg|jpeg|png)', r'_1200.\1', enhanced, flags=re.IGNORECASE)
        
        # Width parameters
        enhanced = re.sub(r'w=\d+', 'w=1200', enhanced)
        
        return enhanced
    
    def _transform_abercrombie_url(self, url: str) -> str:
        """
        Abercrombie-specific transformations
        
        URL patterns:
        - Adobe Scene7 CDN (anf.scene7.com)
        - Size parameters
        """
        enhanced = url
        
        # Scene7 transformations
        enhanced = re.sub(r'wid=\d+', 'wid=1200', enhanced)
        enhanced = re.sub(r'hei=\d+', 'hei=1500', enhanced)
        enhanced = re.sub(r'qlt=\d+', 'qlt=90', enhanced)
        
        # Size suffixes
        enhanced = re.sub(r'_product\.(jpg|jpeg)', r'_prod.\1', enhanced, flags=re.IGNORECASE)
        
        return enhanced
    
    def _transform_revolve_url(self, url: str) -> str:
        """
        Revolve-specific transformations
        
        VERIFIED WORKING PATTERNS (2025-11):
        - /n/d/ = ✅ HTTP 200 (detail view - WORKING)
        - /n/c/ = ✅ HTTP 200 (catalog view - WORKING)
        - /n/z/ = ❌ HTTP 404 (zoom - BROKEN, do NOT use)
        - /n/f/ = ❌ HTTP 404 (full - BROKEN, do NOT use)
        
        STRATEGY: Keep original paths OR convert to /n/d/ (detail view)
        """
        enhanced = url
        
        # DO NOT transform to /n/z/ - it returns 404!
        # Instead, convert problematic patterns to /n/d/ (detail view, which works)
        
        # Only transform known problematic patterns to /n/d/
        enhanced = re.sub(r'/n/ct/', '/n/d/', enhanced)  # Thumbnail to Detail
        enhanced = re.sub(r'/n/uv/', '/n/d/', enhanced)  # UV to Detail
        enhanced = re.sub(r'/n/p/', '/n/d/', enhanced)   # Preview to Detail
        enhanced = re.sub(r'/n/r/', '/n/d/', enhanced)   # Regular to Detail
        enhanced = re.sub(r'/n/t/', '/n/d/', enhanced)   # Thumb to Detail
        enhanced = re.sub(r'/n/z/', '/n/d/', enhanced)   # Zoom to Detail (broken URL fix)
        enhanced = re.sub(r'/n/f/', '/n/d/', enhanced)   # Full to Detail (broken URL fix)
        
        # KEEP /n/d/, /n/c/, /n/dp/, /n/d5/ and similar - they work!
        # No transformation needed for these
        
        # Size suffix transformations
        enhanced = re.sub(r'_sm\.(jpg|jpeg|png)', r'_lg.\1', enhanced, flags=re.IGNORECASE)
        enhanced = re.sub(r'_md\.(jpg|jpeg|png)', r'_lg.\1', enhanced, flags=re.IGNORECASE)
        enhanced = re.sub(r'_thumb\.(jpg|jpeg|png)', r'_lg.\1', enhanced, flags=re.IGNORECASE)
        
        # Version suffix transformations (_V1, _V2, _V3 → full-size)
        # These are often used in newer Revolve product URLs
        enhanced = re.sub(r'_V\d+\.(jpg|jpeg|png)', r'.\1', enhanced, flags=re.IGNORECASE)
        
        # REMOVED: /n/z/ → /n/f/ conversion (those URLs don't exist!)
        # The /n/z/ (zoom) URLs work fine as-is, verified from old architecture
        # Old architecture downloaded URLs as-is without transformation
        
        return enhanced
    
    def _transform_urban_outfitters_url(self, url: str) -> str:
        """
        Urban Outfitters-specific transformations
        
        URL patterns:
        - Similar to Anthropologie (same parent company)
        - Size indicators
        """
        enhanced = url
        
        # Size transformations
        enhanced = re.sub(r'_(\d+)x(\d+)\.(jpg|jpeg|png)', r'_1200x1500.\3', enhanced, flags=re.IGNORECASE)
        enhanced = re.sub(r'_small\.(jpg|jpeg)', r'_xlarge.\1', enhanced, flags=re.IGNORECASE)
        
        return enhanced
    
    def _transform_nordstrom_url(self, url: str) -> str:
        """
        Nordstrom-specific transformations
        
        URL patterns:
        - nordstrommedia.com CDN
        - Size indicators in path
        """
        enhanced = url
        
        # Size transformations
        enhanced = re.sub(r'/\d{3}/', '/1200/', enhanced)
        enhanced = re.sub(r'_\d{3}\.(jpg|jpeg)', r'_1200.\1', enhanced, flags=re.IGNORECASE)
        
        return enhanced
    
    def _transform_generic_url(self, url: str) -> str:
        """
        Generic transformations for unknown retailers
        """
        enhanced = url
        
        # Common size transformations
        enhanced = re.sub(r'_small\.(jpg|jpeg|png)', r'_large.\1', enhanced, flags=re.IGNORECASE)
        enhanced = re.sub(r'_thumb\.(jpg|jpeg|png)', r'_full.\1', enhanced, flags=re.IGNORECASE)
        enhanced = re.sub(r'_\d{2,3}\.(jpg|jpeg|png)', r'_1200.\1', enhanced, flags=re.IGNORECASE)
        
        # Common width parameters
        enhanced = re.sub(r'w=\d+', 'w=1200', enhanced)
        enhanced = re.sub(r'width=\d+', 'width=1200', enhanced)
        
        return enhanced
    
    def _rank_by_quality(self, image_urls: List[str], retailer: str) -> List[str]:
        """
        Rank image URLs by quality indicators
        
        Scoring factors:
        - Size indicators (1000, 2000, 3000 = higher quality)
        - Keywords ('large', 'zoom', 'detail', 'main' = positive)
        - Keywords ('thumb', 'small', 'icon' = negative)
        - URL length (longer often means more parameters = higher quality)
        - File type (jpg/png preferred over gif/webp)
        """
        def quality_score(url: str) -> int:
            score = 0
            url_lower = url.lower()
            
            # Positive indicators
            if 'large' in url_lower or 'big' in url_lower or 'xlarge' in url_lower:
                score += 10
            if 'zoom' in url_lower or 'detail' in url_lower:
                score += 8
            if any(size in url for size in ['1000', '1200', '1500', '2000', '3000']):
                score += 12
            if 'product' in url_lower or 'main' in url_lower or 'hero' in url_lower:
                score += 5
            if '.jpg' in url_lower or '.png' in url_lower:
                score += 3
            if 'high' in url_lower or 'hq' in url_lower:
                score += 7
            
            # Negative indicators
            if 'thumb' in url_lower or 'thumbnail' in url_lower:
                score -= 15
            if 'small' in url_lower or 'tiny' in url_lower or 'mini' in url_lower:
                score -= 10
            if any(size in url for size in ['_50', '_100', '_200', '_300']):
                score -= 8
            if 'icon' in url_lower or 'badge' in url_lower:
                score -= 20
            if '.gif' in url_lower:
                score -= 5
            
            # URL length (longer often = more parameters = higher quality)
            if len(url) > 200:
                score += 3
            elif len(url) > 150:
                score += 2
            
            # Retailer-specific bonuses
            if retailer == 'anthropologie' and '1094_1405' in url:
                score += 15
            if retailer == 'aritzia' and '_large' in url_lower:
                score += 10
            if 'scene7.com' in url and 'zoom' in url_lower:
                score += 10
            
            return score
        
        # Sort by quality score (highest first)
        ranked = sorted(image_urls, key=quality_score, reverse=True)
        
        # Log top 3 for debugging
        for i, url in enumerate(ranked[:3]):
            logger.debug(f"Rank {i+1} (score={quality_score(url)}): {url[:80]}")
        
        return ranked
    
    async def _download_images(
        self,
        image_urls: List[str],
        retailer: str,
        product_title: str
    ) -> List[str]:
        """
        Download images from URLs to disk
        
        Returns:
            List of local file paths
        """
        # Create retailer-specific download directory
        retailer_dir = os.path.join(self.download_base_dir, f"{retailer}_images")
        os.makedirs(retailer_dir, exist_ok=True)
        
        file_paths = []
        
        # Download concurrently
        async with aiohttp.ClientSession() as session:
            tasks = []
            for i, url in enumerate(image_urls[:5]):  # Max 5 images
                task = self._download_single_image(
                    session, url, retailer, retailer_dir, product_title, i
                )
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, str):  # Success (file path)
                    file_paths.append(result)
                elif isinstance(result, Exception):
                    logger.warning(f"Download failed: {result}")
        
        logger.info(f"📥 Downloaded {len(file_paths)}/{len(image_urls)} images for {retailer}")
        return file_paths
    
    async def _download_single_image(
        self,
        session: aiohttp.ClientSession,
        url: str,
        retailer: str,
        save_dir: str,
        product_title: str,
        index: int
    ) -> str:
        """
        Download a single image from URL
        
        Returns:
            Local file path on success
        
        Raises:
            Exception on failure
        """
        try:
            # Generate safe filename
            safe_title = re.sub(r'[^\w\s-]', '', product_title)[:50]
            safe_title = re.sub(r'[-\s]+', '_', safe_title)
            
            # Use URL hash for uniqueness
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            
            # Determine file extension
            ext = 'jpg'
            if url.lower().endswith('.png'):
                ext = 'png'
            elif url.lower().endswith('.webp'):
                ext = 'webp'
            
            filename = f"{safe_title}_{url_hash}_{index}.{ext}"
            file_path = os.path.join(save_dir, filename)
            
            # Download image
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    image_data = await response.read()
                    
                    # Validate image data
                    try:
                        img = Image.open(BytesIO(image_data))
                        width, height = img.size
                        
                        # Minimum size check
                        if width < 100 or height < 100:
                            raise ValueError(f"Image too small: {width}x{height}")
                        
                        # Save to disk
                        with open(file_path, 'wb') as f:
                            f.write(image_data)
                        
                        logger.debug(f"✅ Downloaded: {filename} ({width}x{height})")
                        return file_path
                        
                    except Exception as img_error:
                        raise ValueError(f"Invalid image data: {img_error}")
                else:
                    raise ValueError(f"HTTP {response.status}")
                    
        except Exception as e:
            logger.warning(f"❌ Failed to download {url[:80]}: {e}")
            raise
    
    async def _get_placeholder_patterns(self, retailer: str) -> List[str]:
        """Load learned placeholder patterns for retailer"""
        import sqlite3
        
        try:
            conn = sqlite3.connect(self.pattern_db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT pattern FROM placeholder_patterns
                WHERE retailer = ?
                ORDER BY detection_count DESC
                LIMIT 20
            ''', (retailer,))
            
            patterns = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            return patterns
            
        except Exception as e:
            logger.debug(f"Could not load placeholder patterns: {e}")
            return []
    
    async def _learn_from_results(
        self,
        attempted_urls: List[str],
        successful_paths: List[str],
        retailer: str
    ):
        """
        Learn from download results to improve future processing
        
        Tracks:
        - Which URL patterns successfully downloaded
        - Which transformations worked
        - Download success rates per pattern
        """
        import sqlite3
        
        try:
            success_count = len(successful_paths)
            total_count = len(attempted_urls)
            
            if total_count == 0:
                return
            
            conn = sqlite3.connect(self.pattern_db_path)
            cursor = conn.cursor()
            
            # Extract URL patterns and update stats
            for url in attempted_urls:
                is_success = any(url in path for path in successful_paths)
                
                # Extract pattern (domain + path structure)
                pattern = self._extract_url_pattern(url)
                
                # Update download stats
                cursor.execute('''
                    INSERT INTO download_stats (retailer, url_pattern, download_success, download_failure)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(retailer, url_pattern) DO UPDATE SET
                        download_success = download_success + ?,
                        download_failure = download_failure + ?,
                        last_updated = CURRENT_TIMESTAMP
                ''', (
                    retailer, pattern,
                    1 if is_success else 0,
                    0 if is_success else 1,
                    1 if is_success else 0,
                    0 if is_success else 1
                ))
            
            conn.commit()
            conn.close()
            
            logger.debug(f"📊 Learned from {total_count} URLs ({success_count} successful)")
            
        except Exception as e:
            logger.debug(f"Pattern learning failed: {e}")
    
    def _extract_url_pattern(self, url: str) -> str:
        """Extract general pattern from URL for learning"""
        try:
            # Remove protocol
            url = re.sub(r'^https?://', '', url)
            
            # Extract domain + first path segment
            match = re.match(r'([^/]+)(/[^/]+)?', url)
            if match:
                return match.group(0)
            
            return url[:100]
            
        except Exception:
            return url[:50]


# Singleton instance for easy importing
image_processor = ImageProcessor()

