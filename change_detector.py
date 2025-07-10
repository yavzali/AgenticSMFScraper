"""
Change Detector - Handles new product detection and baseline comparison
Implements comprehensive matching strategy with confidence scoring
"""

import asyncio
import json
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, date
import difflib
import re

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
        Comprehensive multi-factor product matching
        Uses all available matching methods with weighted confidence scoring
        """
        
        # Initialize matching scores
        match_scores = []
        match_details = {}
        
        try:
            # 1. EXACT URL MATCH (highest confidence)
            exact_match = await self._check_exact_url_match(product, retailer)
            if exact_match:
                return MatchResult(
                    is_new_product=False,
                    confidence_score=1.0,
                    match_type='exact_url',
                    existing_product_id=exact_match['id'],
                    similarity_details={'exact_url_match': exact_match['url']}
                )
            
            # 2. NORMALIZED URL MATCH
            if self.config.enable_url_normalization:
                normalized_match = await self._check_normalized_url_match(product, retailer)
                if normalized_match:
                    match_scores.append(('normalized_url', 0.95, normalized_match))
                    match_details['normalized_url_match'] = normalized_match
            
            # 3. PRODUCT ID MATCH
            if self.config.enable_product_id_extraction:
                product_id_match = await self._check_product_id_match(product, retailer)
                if product_id_match:
                    match_scores.append(('product_id', 0.93, product_id_match))
                    match_details['product_id_match'] = product_id_match
            
            # 4. TITLE + PRICE MATCH
            if self.config.enable_title_price_matching:
                title_price_match = await self._check_title_price_match(product, retailer)
                if title_price_match:
                    confidence = 0.80 + (title_price_match['title_similarity'] - 0.85) * 0.8
                    match_scores.append(('title_price', min(confidence, 0.88), title_price_match))
                    match_details['title_price_match'] = title_price_match
            
            # 5. IMAGE URL MATCH
            if self.config.enable_image_url_matching and product.image_urls:
                image_match = await self._check_image_url_match(product, retailer)
                if image_match:
                    match_scores.append(('image_url', 0.82, image_match))
                    match_details['image_url_match'] = image_match
            
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
                    existing_product_id=match_data.get('id'),
                    similarity_details=match_details
                )
            else:
                # No matches found - likely a new product
                return MatchResult(
                    is_new_product=True,
                    confidence_score=0.95,  # High confidence it's new
                    match_type='no_match_found',
                    similarity_details={'search_methods_used': list(match_details.keys())}
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
        """Check for exact URL match in main products database"""
        try:
            # Check main products database
            from duplicate_detector import DuplicateDetector
            duplicate_detector = DuplicateDetector()
            
            result = await duplicate_detector.check_duplicate(product.catalog_url, retailer)
            
            if result.get('is_duplicate') and result.get('match_type') == 'exact_url':
                return {
                    'id': result.get('existing_id'),
                    'url': product.catalog_url,
                    'source': 'main_products_db'
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
        """Check for product ID match"""
        try:
            if not product.product_code:
                # Try to extract product code from URL
                product.product_code = self._extract_product_code_from_url(
                    product.catalog_url, retailer)
            
            if product.product_code:
                # Query main products database by product code
                async with self.db_manager.db_connection() as conn:
                    cursor = await conn.cursor()
                    await cursor.execute("""
                        SELECT id, url, title, price FROM products 
                        WHERE product_code = ? AND retailer = ?
                    """, (product.product_code, retailer))
                    
                    result = await cursor.fetchone()
                    if result:
                        return {
                            'id': result[0],
                            'url': result[1],
                            'product_code': product.product_code,
                            'source': 'main_products_db'
                        }
            
            return None
            
        except Exception as e:
            logger.warning(f"Error checking product ID match: {e}")
            return None
    
    async def _check_title_price_match(self, product: CatalogProduct, retailer: str) -> Optional[Dict]:
        """Check for title + price combination match"""
        try:
            if not product.title or not product.price:
                return None
            
            async with self.db_manager.db_connection() as conn:
                cursor = await conn.cursor()
                
                # Find products with similar price (within $0.01)
                await cursor.execute("""
                    SELECT id, url, title, price FROM products 
                    WHERE retailer = ? AND ABS(price - ?) < 0.01
                """, (retailer, product.price))
                
                price_matches = await cursor.fetchall()
                
                for match in price_matches:
                    title_similarity = difflib.SequenceMatcher(
                        None, product.title.lower(), match[2].lower()).ratio()
                    
                    if title_similarity > 0.85:  # High title similarity threshold
                        return {
                            'id': match[0],
                            'url': match[1],
                            'title_similarity': title_similarity,
                            'price_match': True,
                            'existing_title': match[2],
                            'source': 'main_products_db'
                        }
            
            return None
            
        except Exception as e:
            logger.warning(f"Error checking title+price match: {e}")
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
            async with self.db_manager.db_connection() as conn:
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
        """Check against main products database using existing duplicate detector"""
        try:
            from duplicate_detector import DuplicateDetector
            duplicate_detector = DuplicateDetector()
            
            # Use existing sophisticated duplicate detection
            result = await duplicate_detector.check_for_duplicates(
                title=product.title,
                price=product.price,
                retailer=retailer,
                url=product.catalog_url
            )
            
            if result.get('is_duplicate'):
                return {
                    'id': result.get('existing_id'),
                    'match_confidence': result.get('confidence', 0.8),
                    'match_method': result.get('match_type'),
                    'source': 'main_products_db_enhanced'
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
        """Extract product code from URL using retailer-specific patterns"""
        PRODUCT_ID_PATTERNS = {
            'revolve': r'/([A-Z0-9-]+)\.html',
            'asos': r'/prd/(\d+)',
            'aritzia': r'/product/[^/]+/(\d+)\.html',
            'hm': r'productpage\.(\d+)\.html',
            'uniqlo': r'/products/([A-Z0-9]+)-',
            'anthropologie': r'/products/([^?]+)',
            'abercrombie': r'/products/([^?]+)',
            'nordstrom': r'/s/([^?]+)',
            'urban_outfitters': r'/products/([^?]+)',
            'mango': r'/([0-9]+)\.html'
        }
        
        pattern = PRODUCT_ID_PATTERNS.get(retailer)
        if pattern:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
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
        """Store detection results in database"""
        try:
            # Store new products for review
            if new_products:
                await self.db_manager.store_new_products(new_products, run_id)
            
            # Store manual review products with special flag
            if manual_review_products:
                for product, match_result in manual_review_products:
                    # Mark as needing manual review
                    await self.db_manager.store_new_products(
                        [(product, match_result)], run_id)
            
            # Log existing products (but don't store them as they're already in system)
            logger.info(f"Detection results stored: {len(new_products)} new, "
                       f"{len(manual_review_products)} manual review, "
                       f"{len(existing_products)} existing")
            
        except Exception as e:
            logger.error(f"Error storing detection results: {e}")
            raise
    
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