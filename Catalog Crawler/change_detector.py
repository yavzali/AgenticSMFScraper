"""
Change Detector - Handles new product detection and baseline comparison
Implements comprehensive matching strategy with confidence scoring
"""

# Add shared path for imports
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../Shared"))
sys.path.append(os.path.dirname(__file__))

import asyncio
import json
import aiosqlite
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, date
import difflib
import re
import io

# Image hash comparison imports
try:
    import imagehash
    from PIL import Image
    import requests
    IMAGE_HASH_AVAILABLE = True
except ImportError:
    IMAGE_HASH_AVAILABLE = False
    logger = None  # Will be set after setup_logging

from logger_config import setup_logging
from catalog_db_manager import CatalogDatabaseManager, CatalogProduct, MatchResult

logger = setup_logging(__name__)

@dataclass
class ChangeDetectionConfig:
    """Configuration for change detection"""
    confidence_threshold: float = 0.85  # <=85% = new product, >85% = existing
    enable_baseline_checking: bool = True
    enable_main_products_checking: bool = True
    enable_url_normalization: bool = True
    enable_product_id_extraction: bool = True
    enable_title_price_matching: bool = True
    enable_image_url_matching: bool = True
    require_manual_review_for_low_confidence: bool = True

@dataclass
class DetectionResult:
    """Result of change detection process"""
    total_products_analyzed: int
    new_products_found: int
    existing_products_found: int
    manual_review_required: int
    confidence_distribution: Dict[str, int]
    processing_time: float
    detection_metadata: Dict[str, Any]

class ChangeDetector:
    """
    Handles comprehensive new product detection using multiple matching strategies
    Integrates with existing duplicate_detector patterns but extends for catalog monitoring
    """
    
    def __init__(self, config: ChangeDetectionConfig = None):
        self.config = config or ChangeDetectionConfig()
        self.db_manager = CatalogDatabaseManager()
        
        logger.info(f"✅ Change detector initialized with confidence threshold: {self.config.confidence_threshold}")
    
    async def detect_changes(self, discovered_products: List[CatalogProduct], 
                           retailer: str, category: str, run_id: str) -> DetectionResult:
        """
        Main change detection workflow
        Analyzes all discovered products and categorizes them as new/existing
        """
        start_time = datetime.utcnow()
        
        logger.info(f"🔍 Starting change detection for {len(discovered_products)} products "
                   f"from {retailer} {category}")
        
        new_products = []
        existing_products = []
        manual_review_products = []
        confidence_distribution = {'high': 0, 'medium': 0, 'low': 0}
        
        # Pre-update existing products for accurate matching
        await self._update_existing_products(retailer)
        
        # Process each discovered product
        for i, product in enumerate(discovered_products):
            try:
                # Perform comprehensive matching
                match_result = await self._comprehensive_product_matching(
                    product, retailer, category)
                
                # Categorize based on confidence and user requirements
                if match_result.confidence_score <= self.config.confidence_threshold:
                    # This is likely a new product
                    new_products.append((product, match_result))
                    
                    if match_result.confidence_score <= 0.7:
                        confidence_distribution['low'] += 1
                        if self.config.require_manual_review_for_low_confidence:
                            manual_review_products.append((product, match_result))
                    else:
                        confidence_distribution['medium'] += 1
                else:
                    # This is likely an existing product
                    existing_products.append((product, match_result))
                    confidence_distribution['high'] += 1
                
                # Log progress for large batches
                if (i + 1) % 20 == 0:
                    logger.info(f"Processed {i + 1}/{len(discovered_products)} products")
                    
            except Exception as e:
                logger.error(f"Error processing product {i}: {e}")
                # Treat errors as requiring manual review
                manual_review_products.append((product, MatchResult(
                    is_new_product=True, confidence_score=0.5, 
                    match_type='processing_error',
                    similarity_details={'error': str(e)}
                )))
        
        # Store results in database
        await self._store_detection_results(
            new_products, existing_products, manual_review_products, run_id)
        
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        
        logger.info(f"✅ Change detection completed: {len(new_products)} new, "
                   f"{len(existing_products)} existing, "
                   f"{len(manual_review_products)} manual review, "
                   f"{processing_time:.1f}s")
        
        return DetectionResult(
            total_products_analyzed=len(discovered_products),
            new_products_found=len(new_products),
            existing_products_found=len(existing_products),
            manual_review_required=len(manual_review_products),
            confidence_distribution=confidence_distribution,
            processing_time=processing_time,
            detection_metadata={
                'run_id': run_id,
                'retailer': retailer,
                'category': category,
                'config': self.config.__dict__
            }
        )
    
    async def _comprehensive_product_matching(self, product: CatalogProduct, 
                                            retailer: str, category: str) -> MatchResult:
        """
        Comprehensive multi-factor product matching - Enhanced with full match details
        Uses all available matching methods with weighted confidence scoring
        """
        
        # Initialize matching scores
        match_scores = []
        match_details = {}
        potential_matches = []  # NEW: Store full details of all potential matches
        
        try:
            # 1. EXACT URL MATCH (highest confidence)
            exact_match = await self._check_exact_url_match(product, retailer)
            if exact_match:
                potential_matches.append(exact_match)
                return MatchResult(
                    is_new_product=False,
                    confidence_score=1.0,
                    match_type='exact_url',
                    existing_product_id=exact_match.get('shopify_id') or exact_match['id'],
                    similarity_details={
                        'potential_matches': [exact_match],
                        'best_match': exact_match,
                        'total_matches_found': 1
                    }
                )
            
            # 2. NORMALIZED URL MATCH
            if self.config.enable_url_normalization:
                normalized_match = await self._check_normalized_url_match(product, retailer)
                if normalized_match:
                    potential_matches.append(normalized_match)
                    match_scores.append(('normalized_url', 0.95, normalized_match))
                    match_details['normalized_url_match'] = normalized_match
            
            # 3. PRODUCT ID MATCH
            if self.config.enable_product_id_extraction:
                product_id_match = await self._check_product_id_match(product, retailer)
                if product_id_match:
                    potential_matches.append(product_id_match)
                    match_scores.append(('product_id', 0.93, product_id_match))
                    match_details['product_id_match'] = product_id_match
            
            # 4. TITLE + PRICE MATCH
            title_price_match = None
            if self.config.enable_title_price_matching:
                title_price_match = await self._check_title_price_match(product, retailer)
                if title_price_match:
                    potential_matches.append(title_price_match)
                    confidence = 0.80 + (title_price_match.get('similarity', 0.85) - 0.85) * 0.8
                    match_scores.append(('title_price', min(confidence, 0.88), title_price_match))
                    match_details['title_price_match'] = title_price_match
            
            # 4.5. FUZZY TITLE MATCHING (95% threshold) - NEW ENHANCEMENT
            if self.config.enable_title_price_matching and not title_price_match:
                fuzzy_title_match = await self._check_fuzzy_title_match(product, retailer)
                if fuzzy_title_match:
                    potential_matches.append(fuzzy_title_match)
                    match_scores.append(('fuzzy_title', fuzzy_title_match['confidence'], fuzzy_title_match))
                    match_details['fuzzy_title_match'] = fuzzy_title_match
            
            # 5. IMAGE URL MATCH
            if self.config.enable_image_url_matching and product.image_urls:
                image_match = await self._check_image_url_match(product, retailer)
                if image_match:
                    match_scores.append(('image_url', 0.82, image_match))
                    match_details['image_url_match'] = image_match
            
            # 5.5. IMAGE HASH COMPARISON (NEW ENHANCEMENT)
            # Only if URL matching failed to avoid unnecessary API calls
            if self.config.enable_image_url_matching and product.image_urls and not image_match:
                image_hash_match = await self._check_image_hash_match(product, retailer)
                if image_hash_match:
                    match_scores.append(('image_hash', image_hash_match['confidence'], image_hash_match))
                    match_details['image_hash_match'] = image_hash_match
            
            # 6. CATALOG BASELINE MATCH
            if self.config.enable_baseline_checking:
                baseline_match = await self._check_baseline_match(product, retailer, category)
                if baseline_match:
                    match_scores.append(('baseline', 0.90, baseline_match))
                    match_details['baseline_match'] = baseline_match
            
            # 7. MAIN PRODUCTS DATABASE MATCH (via existing duplicate_detector)
            if self.config.enable_main_products_checking:
                main_db_match = await self._check_main_products_db(product, retailer)
                if main_db_match:
                    match_scores.append(('main_products_db', 0.92, main_db_match))
                    match_details['main_db_match'] = main_db_match
            
            # DETERMINE FINAL MATCH RESULT
            if match_scores:
                # Use highest confidence match
                best_match = max(match_scores, key=lambda x: x[1])
                match_type, confidence, match_data = best_match
                
                return MatchResult(
                    is_new_product=False,
                    confidence_score=confidence,
                    match_type=match_type,
                    existing_product_id=match_data.get('shopify_id') or match_data.get('id'),
                    similarity_details={
                        'potential_matches': potential_matches,  # NEW: All potential matches
                        'best_match': match_data,
                        'total_matches_found': len(potential_matches),
                        **match_details  # Include individual match details for backward compatibility
                    }
                )
            else:
                # No matches found - likely a new product
                return MatchResult(
                    is_new_product=True,
                    confidence_score=0.95,  # High confidence it's new
                    match_type='no_match_found',
                    similarity_details={
                        'potential_matches': [],
                        'search_methods_used': ['exact_url', 'normalized_url', 'product_id', 'fuzzy_title']
                    }
                )
                
        except Exception as e:
            logger.error(f"Error in comprehensive matching: {e}")
            return MatchResult(
                is_new_product=True,
                confidence_score=0.5,  # Low confidence due to error
                match_type='matching_error',
                similarity_details={'error': str(e)}
            )
    
    # =================== INDIVIDUAL MATCHING METHODS ===================
    
    async def _check_exact_url_match(self, product: CatalogProduct, retailer: str) -> Optional[Dict]:
        """Check for exact URL match in main products database - Enhanced with full details"""
        try:
            # Check main products database
            from duplicate_detector import DuplicateDetector
            duplicate_detector = DuplicateDetector()
            
            result = await duplicate_detector.check_duplicate(product.catalog_url, retailer)
            
            if result.get('is_duplicate') and result.get('match_type') == 'exact_url':
                # Get full product details for the match
                async with aiosqlite.connect(self.db_manager.db_path) as conn:
                    cursor = await conn.cursor()
                    await cursor.execute("""
                        SELECT id, title, url, price, original_price, shopify_id 
                        FROM products WHERE id = ? AND retailer = ?
                    """, (result.get('existing_id'), retailer))
                    
                    match_details = await cursor.fetchone()
                    if match_details:
                        return {
                            'id': match_details[0],
                            'title': match_details[1] or 'Unknown Title',
                            'url': match_details[2] or product.catalog_url,
                            'price': match_details[3],
                            'original_price': match_details[4],
                            'shopify_id': match_details[5],
                            'source': 'main_products_db',
                            'match_reason': 'exact_url_match',
                            'similarity': 1.0
                        }
            
            return None
            
        except Exception as e:
            logger.warning(f"Error checking exact URL match: {e}")
            return None
    
    async def _check_normalized_url_match(self, product: CatalogProduct, retailer: str) -> Optional[Dict]:
        """Check for normalized URL match"""
        try:
            normalized_url = self._normalize_product_url(product.catalog_url, retailer)
            
            if normalized_url and normalized_url != product.catalog_url:
                # Check if normalized URL exists
                from duplicate_detector import DuplicateDetector
                duplicate_detector = DuplicateDetector()
                
                result = await duplicate_detector.check_duplicate(normalized_url, retailer)
                
                if result.get('is_duplicate'):
                    return {
                        'id': result.get('existing_id'),
                        'original_url': product.catalog_url,
                        'normalized_url': normalized_url,
                        'source': 'main_products_db'
                    }
            
            return None
            
        except Exception as e:
            logger.warning(f"Error checking normalized URL match: {e}")
            return None
    
    async def _check_product_id_match(self, product: CatalogProduct, retailer: str) -> Optional[Dict]:
        """Check for product ID match - Enhanced with full details"""
        try:
            if not product.product_code:
                # Try to extract product code from URL
                product.product_code = self._extract_product_code_from_url(
                    product.catalog_url, retailer)
            
            if product.product_code:
                # Query main products database by product code
                async with aiosqlite.connect(self.db_manager.db_path) as conn:
                    cursor = await conn.cursor()
                    await cursor.execute("""
                        SELECT id, title, url, price, original_price, shopify_id 
                        FROM products 
                        WHERE product_code = ? AND retailer = ?
                    """, (product.product_code, retailer))
                    
                    result = await cursor.fetchone()
                    if result:
                        return {
                            'id': result[0],
                            'title': result[1] or 'Unknown Title',
                            'url': result[2] or product.catalog_url,
                            'price': result[3],
                            'original_price': result[4],
                            'shopify_id': result[5],
                            'source': 'main_products_db',
                            'match_reason': 'product_code_match',
                            'similarity': 0.95,
                            'product_code': product.product_code
                        }
            
            return None
            
        except Exception as e:
            logger.warning(f"Error checking product ID match: {e}")
            return None
    
    async def _check_title_price_match(self, product: CatalogProduct, retailer: str) -> Optional[Dict]:
        """Check for title + price combination match - Enhanced with full details"""
        try:
            if not product.title or not product.price:
                return None
            
            async with aiosqlite.connect(self.db_manager.db_path) as conn:
                cursor = await conn.cursor()
                
                # Find products with similar price (within $0.01)
                await cursor.execute("""
                    SELECT id, title, url, price, original_price, shopify_id 
                    FROM products 
                    WHERE retailer = ? AND ABS(price - ?) < 0.01
                """, (retailer, product.price))
                
                price_matches = await cursor.fetchall()
                
                for match in price_matches:
                    title_similarity = difflib.SequenceMatcher(
                        None, product.title.lower(), match[1].lower()).ratio()
                    
                    if title_similarity > 0.85:  # High title similarity threshold
                        return {
                            'id': match[0],
                            'title': match[1] or 'Unknown Title',
                            'url': match[2] or product.catalog_url,
                            'price': match[3],
                            'original_price': match[4],
                            'shopify_id': match[5],
                            'source': 'main_products_db',
                            'match_reason': 'title_price_match',
                            'similarity': title_similarity,
                            'price_match': True
                        }
            
            return None
            
        except Exception as e:
            logger.warning(f"Error checking title+price match: {e}")
            return None
    
    async def _check_fuzzy_title_match(self, product: CatalogProduct, retailer: str) -> Optional[Dict]:
        """
        Check for fuzzy title matching with 95% threshold - Enhanced with full details
        If fuzzy similarity >= 95% but price differs -> confidence 0.75 (manual review as duplicate_uncertain)
        """
        try:
            if not product.title:
                return None
            
            async with aiosqlite.connect(self.db_manager.db_path) as conn:
                cursor = await conn.cursor()
                
                # Get all products from same retailer for fuzzy matching
                await cursor.execute("""
                    SELECT id, title, url, price, original_price, shopify_id 
                    FROM products 
                    WHERE retailer = ? AND title IS NOT NULL
                    ORDER BY last_updated DESC LIMIT 200
                """, (retailer,))
                
                all_products = await cursor.fetchall()
                
                best_match = None
                best_similarity = 0.0
                
                for match in all_products:
                    # Use difflib.SequenceMatcher for fuzzy matching
                    title_similarity = difflib.SequenceMatcher(
                        None, product.title.lower(), match[1].lower()).ratio()
                    
                    if title_similarity >= 0.95 and title_similarity > best_similarity:
                        best_similarity = title_similarity
                        best_match = match
                
                if best_match:
                    # Check if price matches or differs
                    price_match = False
                    if product.price and best_match[3]:
                        price_match = abs(product.price - best_match[3]) < 0.01
                    
                    # If fuzzy similarity >= 95% but price differs -> confidence 0.75
                    if best_similarity >= 0.95 and not price_match:
                        confidence = 0.75  # Will trigger manual review as duplicate_uncertain
                    elif best_similarity >= 0.95 and price_match:
                        confidence = 0.88  # High confidence match
                    else:
                        confidence = 0.70 + (best_similarity - 0.95) * 0.5
                    
                    return {
                        'id': best_match[0],
                        'title': best_match[1] or 'Unknown Title',
                        'url': best_match[2] or product.catalog_url,
                        'price': best_match[3],
                        'original_price': best_match[4],
                        'shopify_id': best_match[5],
                        'source': 'main_products_db',
                        'match_reason': 'fuzzy_title_match',
                        'similarity': best_similarity,
                        'price_match': price_match,
                        'confidence': confidence
                    }
            
            return None
            
        except Exception as e:
            logger.warning(f"Error checking fuzzy title match: {e}")
            return None
    
    async def _check_image_hash_match(self, product: CatalogProduct, retailer: str) -> Optional[Dict]:
        """
        Check for image hash similarity using perceptual hashing (pHash)
        If hash similarity >= 90% -> confidence 0.80 -> manual review as duplicate_uncertain
        """
        try:
            if not IMAGE_HASH_AVAILABLE:
                logger.debug("Image hash comparison not available (imagehash library not installed)")
                return None
            
            if not product.image_urls:
                return None
            
            # Get the first image URL for comparison
            catalog_image_url = product.image_urls[0] if isinstance(product.image_urls, list) else product.image_urls
            
            # Download and hash the catalog image
            catalog_hash = await self._get_image_hash(catalog_image_url)
            if not catalog_hash:
                return None
            
            async with aiosqlite.connect(self.db_manager.db_path) as conn:
                cursor = await conn.cursor()
                
                # Get products from same retailer with images
                # Note: This assumes we have image URLs stored in the products table
                # For now, we'll check against catalog_products which has image_urls
                await cursor.execute("""
                    SELECT id, catalog_url, title, price, image_urls FROM catalog_products 
                    WHERE retailer = ? AND image_urls IS NOT NULL
                """, (retailer,))
                
                products_with_images = await cursor.fetchall()
                
                best_match = None
                best_similarity = 0.0
                
                for match in products_with_images:
                    # Parse image URLs from JSON
                    try:
                        existing_image_urls = json.loads(match[4]) if match[4] else []
                        if not existing_image_urls:
                            continue
                        
                        existing_image_url = existing_image_urls[0] if isinstance(existing_image_urls, list) else existing_image_urls
                        
                        # Get hash for existing product image
                        existing_hash = await self._get_image_hash(existing_image_url)
                        if not existing_hash:
                            continue
                        
                        # Compare hashes (returns 0 for identical, higher for different)
                        hash_difference = catalog_hash - existing_hash
                        # Convert to similarity percentage (lower difference = higher similarity)
                        similarity = max(0, 1 - (hash_difference / 64.0))  # 64 is max hash difference
                        
                        if similarity >= 0.90 and similarity > best_similarity:
                            best_similarity = similarity
                            best_match = match
                            
                    except Exception as e:
                        logger.debug(f"Error comparing image hash: {e}")
                        continue
                
                if best_match and best_similarity >= 0.90:
                    # Image hash similarity >= 90% -> confidence 0.80 (duplicate_uncertain)
                    return {
                        'id': best_match[0],
                        'url': best_match[1],
                        'hash_similarity': best_similarity,
                        'confidence': 0.80,  # Will trigger manual review as duplicate_uncertain
                        'existing_title': best_match[2],
                        'source': 'catalog_products_image_hash'
                    }
            
            return None
            
        except Exception as e:
            logger.warning(f"Error checking image hash match: {e}")
            return None
    
    async def _get_image_hash(self, image_url: str) -> Optional[Any]:
        """
        Download image and compute perceptual hash
        Returns None if image cannot be processed
        Returns imagehash.ImageHash if successful
        """
        try:
            if not IMAGE_HASH_AVAILABLE:
                return None
            
            # Download image with timeout
            response = requests.get(image_url, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            })
            response.raise_for_status()
            
            # Open image and compute hash
            image = Image.open(io.BytesIO(response.content))
            # Use perceptual hash (pHash) for better similarity detection
            image_hash = imagehash.phash(image)
            
            return image_hash
            
        except Exception as e:
            logger.debug(f"Error getting image hash for {image_url}: {e}")
            return None
    
    async def _check_image_url_match(self, product: CatalogProduct, retailer: str) -> Optional[Dict]:
        """Check for image URL similarity"""
        try:
            if not product.image_urls:
                return None
            
            # This would require extending the main products database
            # to store image URLs for comparison
            # For now, we'll implement basic logic and enhance later
            
            # Extract image identifiers from URLs
            product_image_ids = []
            for img_url in product.image_urls:
                img_id = self._extract_image_identifier(img_url, retailer)
                if img_id:
                    product_image_ids.append(img_id)
            
            if product_image_ids:
                # Check if any of these image IDs match existing products
                # This is a placeholder for future implementation
                logger.debug(f"Image ID matching not fully implemented yet: {product_image_ids}")
            
            return None
            
        except Exception as e:
            logger.warning(f"Error checking image URL match: {e}")
            return None
    
    async def _check_baseline_match(self, product: CatalogProduct, retailer: str, category: str) -> Optional[Dict]:
        """Check against catalog baseline products (including immodest items)"""
        try:
            async with aiosqlite.connect(self.db_manager.db_path) as conn:
                cursor = await conn.cursor()
                
                # Check catalog_products table for baseline matches
                await cursor.execute("""
                    SELECT id, catalog_url, title, price FROM catalog_products 
                    WHERE retailer = ? AND category = ? AND review_status = 'baseline'
                """, (retailer, category))
                
                baseline_products = await cursor.fetchall()
                
                for baseline_product in baseline_products:
                    # Check URL similarity
                    if self._urls_are_similar(product.catalog_url, baseline_product[1], retailer):
                        return {
                            'id': baseline_product[0],
                            'url': baseline_product[1],
                            'source': 'catalog_baseline'
                        }
                    
                    # Check title similarity
                    if product.title and baseline_product[2]:
                        title_similarity = difflib.SequenceMatcher(
                            None, product.title.lower(), baseline_product[2].lower()).ratio()
                        
                        if title_similarity > 0.90:  # High threshold for baseline matches
                            return {
                                'id': baseline_product[0],
                                'title_similarity': title_similarity,
                                'source': 'catalog_baseline'
                            }
            
            return None
            
        except Exception as e:
            logger.warning(f"Error checking baseline match: {e}")
            return None
    
    async def _check_main_products_db(self, product: CatalogProduct, retailer: str) -> Optional[Dict]:
        """
        Check against main products database (Shopify products)
        Enhanced with title+price fuzzy matching for retailers with unstable URLs/codes
        """
        try:
            async with aiosqlite.connect(self.db_manager.db_path) as conn:
                cursor = await conn.cursor()
                
                # 1. Try exact URL match first
                await cursor.execute("""
                    SELECT id, title, url, price, product_code, shopify_id 
                    FROM products 
                    WHERE url = ? AND retailer = ? AND shopify_id IS NOT NULL
                """, (product.catalog_url, retailer))
                
                exact_match = await cursor.fetchone()
                if exact_match:
                    return {
                        'id': exact_match[0],
                        'title': exact_match[1],
                        'url': exact_match[2],
                        'shopify_id': exact_match[5],
                        'match_confidence': 1.0,
                        'match_method': 'exact_url',
                        'source': 'main_products_db'
                    }
                
                # 2. Try product code match
                if product.product_code:
                    await cursor.execute("""
                        SELECT id, title, url, price, product_code, shopify_id 
                        FROM products 
                        WHERE product_code = ? AND retailer = ? AND shopify_id IS NOT NULL
                    """, (product.product_code, retailer))
                    
                    code_match = await cursor.fetchone()
                    if code_match:
                        return {
                            'id': code_match[0],
                            'title': code_match[1],
                            'url': code_match[2],
                            'shopify_id': code_match[5],
                            'match_confidence': 0.93,
                            'match_method': 'product_code',
                            'source': 'main_products_db',
                            'product_code': product.product_code
                        }
                
                # 3. CRITICAL: Title + Price fuzzy matching (catches URL/code changes)
                if product.title and product.price:
                    await cursor.execute("""
                        SELECT id, title, url, price, product_code, shopify_id 
                        FROM products 
                        WHERE retailer = ? AND ABS(price - ?) < 1.0 AND shopify_id IS NOT NULL
                    """, (retailer, product.price))
                    
                    price_matches = await cursor.fetchall()
                    
                    for match in price_matches:
                        title_similarity = difflib.SequenceMatcher(
                            None, 
                            product.title.lower(), 
                            match[1].lower()
                        ).ratio()
                        
                        if title_similarity > 0.90:  # 90%+ similarity
                            confidence = 0.85 + (title_similarity - 0.90) * 0.5  # 0.85-0.90
                            return {
                                'id': match[0],
                                'title': match[1],
                                'url': match[2],
                                'shopify_id': match[5],
                                'match_confidence': min(confidence, 0.92),
                                'match_method': 'title_price_fuzzy',
                                'source': 'main_products_db',
                                'title_similarity': title_similarity
                            }
            
            return None
            
        except Exception as e:
            logger.warning(f"Error checking main products DB: {e}")
            return None
    
    # =================== UTILITY METHODS ===================
    
    def _normalize_product_url(self, url: str, retailer: str) -> str:
        """Normalize URLs for better matching (same logic as catalog_db_manager)"""
        # Remove tracking parameters
        tracking_params = ['navsrc', 'origin', 'breadcrumb', 'pagefm', 'src', 'pos', 
                          'campaign', 'utm_source', 'utm_medium', 'utm_campaign']
        
        normalized = url
        for param in tracking_params:
            normalized = re.sub(f'[?&]{param}=[^&]*', '', normalized)
        
        # Retailer-specific normalization
        if retailer == 'revolve':
            normalized = re.sub(r'\?.*', '', normalized)
        elif retailer == 'asos':
            normalized = re.sub(r'[?&](currentpricerange|sort)=[^&]*', '', normalized)
        elif retailer == 'aritzia':
            normalized = re.sub(r'\?.*', '', normalized)
        
        return normalized.rstrip('?&')
    
    def _extract_product_code_from_url(self, url: str, retailer: str) -> Optional[str]:
        """
        Extract product code from URL using retailer-specific patterns
        Updated with real URL analysis and validation
        """
        # Enhanced patterns based on actual URLs from the system
        PRODUCT_ID_PATTERNS = {
            'nordstrom': [
                r'/s/[^/]+/(\d+)',  # /s/crewneck-midi-dress/8172887
                r'product/(\d+)',
                r'/(\d{7,8})'
            ],
            'aritzia': [
                r'/product/[^/]+/(\d+)\.html',  # /product/utility-dress/115422.html
                r'/(\d{6})\.html',
                r'product/([^/]+)/(\d+)'
            ],
            'hm': [
                r'productpage\.(\d+)\.html',  # productpage.1232566001.html
                r'/(\d{10})\.html',
                r'product\.(\d+)'
            ],
            'uniqlo': [
                r'/products/([A-Z]\d+)-',  # /products/E479225-000/00
                r'/products/([A-Z]{1,2}\d{6})',
                r'products/([A-Z0-9-]+)'
            ],
            'abercrombie': [
                r'/p/[^/]+-(\d+)',  # /p/cowl-neck-draped-maxi-dress-59263319
                r'product-(\d{8})',
                r'/(\d{8})'
            ],
                         'anthropologie': [
                 r'/shop/([^?]+)',  # Extract from slug before query params
                 r'/([a-z0-9-]+)\?',
                 r'product/([a-z0-9-]+)'
             ],
            'urban_outfitters': [
                r'/shop/([^?]+)',  # /shop/97-nyc-applique-graphic-baby-tee
                r'product/([a-z0-9-]+)',
                r'/([a-z0-9-]+)\?'
            ],
            'mango': [
                r'/([a-z0-9-]+)_(\d+)',  # /short-button-down-linen-blend-dress_87039065
                r'_(\d{8})',
                r'/(\d{8})'
            ],
            'revolve': [
                r'/([a-z0-9-]+)/dp/([A-Z0-9-]+)',  # /lagence-sima-shirt-dress-in-pine/dp/LAGR-WD258/
                r'/dp/([A-Z0-9-]+)',
                r'product/([A-Z0-9-]+)'
            ],
            'asos': [
                r'/prd/(\d+)',
                r'product-(\d+)',
                r'/(\d{7,})'
            ]
        }
        
        retailer_patterns = PRODUCT_ID_PATTERNS.get(retailer, [])
        
        for pattern in retailer_patterns:
            match = re.search(pattern, url)
            if match:
                # For patterns with multiple groups, take the most specific one
                if len(match.groups()) > 1:
                    # Take the last group (usually the product ID)
                    product_id = match.group(match.lastindex)
                else:
                    product_id = match.group(1)
                
                # Validate the extracted ID
                if self._validate_product_id(product_id, retailer):
                    return product_id
        
        return None
    
    def _validate_product_id(self, product_id: str, retailer: str) -> bool:
        """
        Validate that extracted product ID looks correct for retailer
        """
        if not product_id or len(product_id) < 2:
            return False
        
        # Retailer-specific validation rules
        validation_rules = {
            'nordstrom': lambda pid: pid.isdigit() and 6 <= len(pid) <= 8,
            'aritzia': lambda pid: pid.isdigit() and 5 <= len(pid) <= 7,
            'hm': lambda pid: pid.isdigit() and 8 <= len(pid) <= 12,
            'uniqlo': lambda pid: len(pid) >= 6 and any(c.isalpha() for c in pid),
            'abercrombie': lambda pid: pid.isdigit() and 8 <= len(pid) <= 9,
            'anthropologie': lambda pid: len(pid) >= 10 and '-' in pid,
            'urban_outfitters': lambda pid: len(pid) >= 8 and '-' in pid,
            'mango': lambda pid: pid.isdigit() and 6 <= len(pid) <= 8,
            'revolve': lambda pid: len(pid) >= 6 and any(c.isupper() for c in pid),
            'asos': lambda pid: pid.isdigit() and 6 <= len(pid) <= 8
        }
        
        validator = validation_rules.get(retailer)
        if validator:
            try:
                return validator(product_id)
            except:
                return False
        
        # Default validation: not empty and reasonable length
        return 3 <= len(product_id) <= 20
    
    def _extract_image_identifier(self, image_url: str, retailer: str) -> Optional[str]:
        """Extract image identifier from image URL"""
        # This would extract unique identifiers from image URLs
        # Implementation depends on retailer image URL patterns
        
        # For now, extract filename as basic identifier
        try:
            filename = image_url.split('/')[-1].split('?')[0]
            return filename
        except:
            return None
    
    def _urls_are_similar(self, url1: str, url2: str, retailer: str) -> bool:
        """Check if two URLs represent the same product"""
        # Extract product identifiers and compare
        id1 = self._extract_product_code_from_url(url1, retailer)
        id2 = self._extract_product_code_from_url(url2, retailer)
        
        if id1 and id2:
            return id1 == id2
        
        # Fallback: basic URL similarity
        return difflib.SequenceMatcher(None, url1, url2).ratio() > 0.85
    
    async def _update_existing_products(self, retailer: str):
        """
        Update existing products in main database for accurate matching
        This ensures we have the latest titles/prices for comparison
        """
        try:
            # This would trigger updates of existing products in the main database
            # For now, we'll log the intent and implement as needed
            logger.info(f"🔄 Pre-crawl product update for {retailer} would happen here")
            
            # In full implementation, this would:
            # 1. Get list of products needing refresh
            # 2. Run extraction updates on those products
            # 3. Update main products database
            
        except Exception as e:
            logger.warning(f"Error updating existing products for {retailer}: {e}")
    
    async def _store_detection_results(self, new_products: List[Tuple[CatalogProduct, MatchResult]], 
                                     existing_products: List[Tuple[CatalogProduct, MatchResult]],
                                     manual_review_products: List[Tuple[CatalogProduct, MatchResult]], 
                                     run_id: str):
        """
        Store detection results with conditional processing based on review_type
        
        COST OPTIMIZATION:
        - modesty_assessment: Full scraping + Shopify draft creation
        - duplicate_uncertain: Lightweight storage only (no scraping)
        
        Review Type Logic:
        - confidence >= 0.95: 'modesty_assessment' (genuinely new products)
        - confidence 0.70-0.85: 'duplicate_uncertain' (uncertain duplicates)
        - confidence < 0.70: 'modesty_assessment' (very uncertain, treat as new for review)
        """
        try:
            # Import dependencies for conditional processing
            import sys
            import os
            sys.path.append(os.path.join(os.path.dirname(__file__), "../Shared"))
            
            # Process new products with conditional logic
            if new_products:
                products_for_db = []
                
                for product, match_result in new_products:
                    # Determine review_type based on confidence
                    if match_result.confidence_score >= 0.95:
                        review_type = 'modesty_assessment'
                    elif 0.70 <= match_result.confidence_score <= 0.85:
                        review_type = 'duplicate_uncertain'
                    else:
                        review_type = 'modesty_assessment'  # Very uncertain, treat as new
                    
                    if review_type == 'modesty_assessment':
                        # FULL PROCESSING: Scrape + Create Shopify draft
                        logger.info(f"🛍️  Full processing for modesty assessment: {product.catalog_url}")
                        
                        try:
                            from unified_extractor import UnifiedExtractor
                            from shopify_manager import ShopifyManager
                            
                            # Extract full product data
                            extractor = UnifiedExtractor()
                            extraction_result = await extractor.extract_product_data(
                                product.catalog_url, product.retailer
                            )
                            
                            if extraction_result.success:
                                # Create Shopify draft with "not-assessed" tag
                                shopify_manager = ShopifyManager()
                                shopify_result = await shopify_manager.create_product(
                                    extraction_result.data, product.retailer, "pending_review",  # Triggers "not-assessed" tag
                                    product.catalog_url, extraction_result.images or []
                                )
                                
                                if shopify_result['success']:
                                    shopify_draft_id = shopify_result['product_id']
                                    shopify_image_urls = shopify_result.get('shopify_image_urls', [])
                                    
                                    # Update tracking fields
                                    processing_stage = 'shopify_uploaded'
                                    cost_incurred = self._estimate_extraction_cost(extraction_result)
                                    
                                    # Store all tracking info on product object
                                    product.shopify_draft_id = shopify_draft_id
                                    product.processing_stage = processing_stage
                                    product.full_scrape_attempted = True
                                    product.full_scrape_completed = True
                                    product.cost_incurred = cost_incurred
                                    product.review_type = review_type
                                    product.shopify_image_urls = shopify_image_urls  # NEW: Store CDN URLs
                                    
                                    products_for_db.append((product, match_result))
                                else:
                                    logger.error(f"Shopify upload failed: {shopify_result.get('error')}")
                                    # Set error state
                                    product.processing_stage = 'shopify_failed'
                                    product.full_scrape_attempted = True
                                    product.full_scrape_completed = True
                                    product.cost_incurred = self._estimate_extraction_cost(extraction_result)
                                    product.review_type = review_type
                                    product.shopify_image_urls = None
                                    products_for_db.append((product, match_result))
                            else:
                                # Scraping failed
                                logger.warning(f"Scraping failed for {product.catalog_url}: {extraction_result.errors}")
                                product.processing_stage = 'scrape_failed'
                                product.full_scrape_attempted = True
                                product.full_scrape_completed = False
                                product.cost_incurred = 0
                                product.review_type = review_type
                                product.shopify_image_urls = None
                                products_for_db.append((product, match_result))
                                
                        except Exception as e:
                            logger.error(f"Error in full processing: {e}")
                            product.processing_stage = 'scrape_error'
                            product.full_scrape_attempted = True
                            product.full_scrape_completed = False
                            product.cost_incurred = 0
                            product.review_type = review_type
                            product.shopify_image_urls = None
                            products_for_db.append((product, match_result))
                    
                    elif review_type == 'duplicate_uncertain':
                        # LIGHTWEIGHT PROCESSING: Store catalog info only
                        logger.info(f"📝 Lightweight processing for duplicate review: {product.catalog_url}")
                        
                        products_for_db.append((
                            product, match_result, review_type, None,
                            'discovered', False, False, 0
                        ))
                
                # Store all products in database
                await self._store_products_with_tracking(products_for_db, run_id)
            
            # Store manual review products (same conditional processing)
            if manual_review_products:
                # Apply same conditional logic to manual review products
                await self._store_detection_results(manual_review_products, [], [], run_id)
            
            logger.info(f"✅ Detection results stored: {len(new_products)} new, "
                       f"{len(manual_review_products)} manual review, "
                       f"{len(existing_products)} existing")
            
        except Exception as e:
            logger.error(f"Error storing detection results: {e}")
            raise
    
    def _estimate_extraction_cost(self, extraction_result) -> float:
        """Estimate API cost for extraction"""
        try:
            method_used = getattr(extraction_result, 'method_used', 'unknown')
            if method_used == 'playwright':
                return 0.08  # Higher cost for Playwright
            elif method_used == 'markdown':
                return 0.02  # Lower cost for markdown
            else:
                return 0.05  # Default estimate
        except:
            return 0.05
    
    async def _store_products_with_tracking(self, products_data: List, run_id: str):
        """Store products with enhanced tracking information"""
        enhanced_products = []
        
        for item in products_data:
            # New simplified format: just (product, match_result)
            # Product already has all tracking attributes set
            if len(item) == 2:
                product, match_result = item
                # Ensure attributes exist with defaults if not set
                if not hasattr(product, 'review_type'):
                    product.review_type = 'modesty_assessment'
                if not hasattr(product, 'shopify_draft_id'):
                    product.shopify_draft_id = None
                if not hasattr(product, 'processing_stage'):
                    product.processing_stage = 'discovered'
                if not hasattr(product, 'full_scrape_attempted'):
                    product.full_scrape_attempted = False
                if not hasattr(product, 'full_scrape_completed'):
                    product.full_scrape_completed = False
                if not hasattr(product, 'cost_incurred'):
                    product.cost_incurred = 0
                if not hasattr(product, 'shopify_image_urls'):
                    product.shopify_image_urls = None
            else:  # Legacy format with tuple - should not happen anymore
                logger.warning(f"Legacy format detected in _store_products_with_tracking: {len(item)} items")
                product, match_result = item[0], item[1]
                product.review_type = 'modesty_assessment'
                product.shopify_draft_id = None
                product.processing_stage = 'discovered'
                product.full_scrape_attempted = False
                product.full_scrape_completed = False
                product.cost_incurred = 0
                product.shopify_image_urls = None
            
            enhanced_products.append((product, match_result))
        
        # Store using existing method
        await self.db_manager.store_new_products(enhanced_products, run_id)
    
    # =================== PUBLIC INTERFACE ===================
    
    async def get_detection_stats(self) -> Dict:
        """Get change detection statistics"""
        return {
            'detector_type': 'comprehensive_change_detector',
            'confidence_threshold': self.config.confidence_threshold,
            'matching_methods_enabled': {
                'url_normalization': self.config.enable_url_normalization,
                'product_id_extraction': self.config.enable_product_id_extraction,
                'title_price_matching': self.config.enable_title_price_matching,
                'image_url_matching': self.config.enable_image_url_matching,
                'baseline_checking': self.config.enable_baseline_checking,
                'main_products_checking': self.config.enable_main_products_checking
            },
            'manual_review_for_low_confidence': self.config.require_manual_review_for_low_confidence
        }
    
    async def update_confidence_threshold(self, new_threshold: float):
        """Update confidence threshold for new product detection"""
        if 0.0 <= new_threshold <= 1.0:
            old_threshold = self.config.confidence_threshold
            self.config.confidence_threshold = new_threshold
            logger.info(f"Updated confidence threshold: {old_threshold} → {new_threshold}")
        else:
            raise ValueError("Confidence threshold must be between 0.0 and 1.0")
    
    async def close(self):
        """Cleanup resources"""
        await self.db_manager.close()
        logger.debug("Change detector closed")