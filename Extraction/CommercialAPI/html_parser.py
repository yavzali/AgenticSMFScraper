"""
HTML Parser

BeautifulSoup coordinator for parsing HTML with CSS selectors
Tracks pattern success/failure, falls back to LLM if parsing fails
"""

import logging
from typing import Dict, List, Optional, Tuple
from bs4 import BeautifulSoup
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from Shared.logger_config import setup_logging
from Extraction.CommercialAPI.commercial_config import CommercialAPIConfig
from Extraction.CommercialAPI.commercial_retailer_strategies import CommercialRetailerStrategies
from Extraction.CommercialAPI.javascript_parser import JavaScriptDataParser

logger = setup_logging(__name__)

class HTMLParser:
    """
    HTML Parser using BeautifulSoup + CSS selectors
    
    Features:
    - Parse product and catalog pages
    - Try CSS selectors from strategies
    - Track selector success/failure for pattern learning
    - Validate extracted data
    - Fall back to LLM if parsing fails
    
    Usage:
        parser = HTMLParser()
        product = await parser.parse_product(html, 'nordstrom', url)
        catalog = await parser.parse_catalog(html, 'nordstrom', url)
    """
    
    def __init__(self):
        self.config = CommercialAPIConfig()
        self.strategies = CommercialRetailerStrategies()
        self.js_parser = JavaScriptDataParser()
        
        # Import pattern learner if enabled
        self.pattern_learner = None
        if self.config.PATTERN_LEARNING_ENABLED:
            try:
                from .pattern_learner import PatternLearner
                self.pattern_learner = PatternLearner()
                logger.info("✅ Pattern learning enabled for HTML parser")
            except Exception as e:
                logger.warning(f"⚠️ Pattern learning initialization failed: {e}")
        
        logger.info("✅ HTML Parser initialized")
    
    async def parse_product(
        self,
        html: str,
        retailer: str,
        url: str
    ) -> Tuple[Optional[Dict], bool]:
        """
        Parse product page HTML
        
        Args:
            html: Raw HTML content
            retailer: Retailer name
            url: Product URL (for logging)
        
        Returns:
            Tuple of (product_data, success)
            - product_data: Dict with extracted fields, or None if failed
            - success: True if parsing succeeded, False if needs LLM fallback
        
        Process:
        1. Create BeautifulSoup object
        2. Extract fields using CSS selectors
        3. Validate extracted data
        4. Record pattern success/failure
        5. Return result
        """
        logger.info(f"🔍 Parsing product HTML: {url[:70]}... ({retailer})")
        
        try:
            # Create BeautifulSoup object
            soup = BeautifulSoup(html, 'html.parser')
            
            # Try JavaScript extraction first (for Abercrombie, Urban Outfitters, Aritzia)
            product_data = self.js_parser.extract_product_data(html, soup, retailer)
            
            # If JavaScript extraction failed, fall back to CSS selectors
            if not product_data or not product_data.get('title'):
                logger.debug("JavaScript extraction failed or incomplete, trying CSS selectors")
                product_data = self.strategies.extract_product(soup, retailer)
            
            # Validate extracted data
            is_valid, validation_errors = self._validate_product(product_data, retailer)
            
            if is_valid:
                # Success! Record pattern success
                if self.pattern_learner:
                    await self._record_pattern_success(
                        retailer, 'product', url, product_data
                    )
                
                logger.info(
                    f"✅ Product parsed successfully: "
                    f"{product_data.get('title', 'Unknown')[:50]}... "
                    f"(${product_data.get('price', 0)}, "
                    f"{len(product_data.get('image_urls', []))} images)"
                )
                
                return product_data, True
            
            else:
                # Validation failed - needs LLM fallback
                logger.warning(
                    f"⚠️ Product validation failed: {', '.join(validation_errors)}"
                )
                
                # Record pattern failure
                if self.pattern_learner:
                    await self._record_pattern_failure(
                        retailer, 'product', url, validation_errors
                    )
                
                return None, False
        
        except Exception as e:
            logger.error(f"❌ Product parsing error: {e}")
            
            # Record pattern failure
            if self.pattern_learner:
                await self._record_pattern_failure(
                    retailer, 'product', url, [str(e)]
                )
            
            return None, False
    
    async def parse_catalog(
        self,
        html: str,
        retailer: str,
        url: str,
        max_products: int = 100
    ) -> Tuple[Optional[List[Dict]], bool]:
        """
        Parse catalog page HTML
        
        Args:
            html: Raw HTML content
            retailer: Retailer name
            url: Catalog URL (for logging)
            max_products: Maximum products to extract
        
        Returns:
            Tuple of (products, success)
            - products: List of product dicts, or None if failed
            - success: True if parsing succeeded, False if needs LLM fallback
        
        Process:
        1. Create BeautifulSoup object
        2. Extract product listings using CSS selectors
        3. Validate extracted data
        4. Record pattern success/failure
        5. Return result
        """
        logger.info(f"🔍 Parsing catalog HTML: {url[:70]}... ({retailer})")
        
        try:
            # Create BeautifulSoup object
            soup = BeautifulSoup(html, 'html.parser')
            
            # Extract catalog data using strategies
            products = self.strategies.extract_catalog(soup, retailer, max_products)
            
            # Validate extracted data
            is_valid, validation_errors = self._validate_catalog(products, retailer)
            
            if is_valid:
                # Success! Record pattern success
                if self.pattern_learner:
                    await self._record_pattern_success(
                        retailer, 'catalog', url, {'product_count': len(products)}
                    )
                
                logger.info(
                    f"✅ Catalog parsed successfully: {len(products)} products"
                )
                
                return products, True
            
            else:
                # Validation failed - needs LLM fallback
                logger.warning(
                    f"⚠️ Catalog validation failed: {', '.join(validation_errors)}"
                )
                
                # Record pattern failure
                if self.pattern_learner:
                    await self._record_pattern_failure(
                        retailer, 'catalog', url, validation_errors
                    )
                
                return None, False
        
        except Exception as e:
            logger.error(f"❌ Catalog parsing error: {e}")
            
            # Record pattern failure
            if self.pattern_learner:
                await self._record_pattern_failure(
                    retailer, 'catalog', url, [str(e)]
                )
            
            return None, False
    
    def _validate_product(
        self,
        product_data: Dict,
        retailer: str
    ) -> Tuple[bool, List[str]]:
        """
        Validate extracted product data
        
        Returns:
            Tuple of (is_valid, errors)
        """
        errors = []
        
        # Check required fields
        required_fields = self.config.REQUIRED_PRODUCT_FIELDS
        
        for field, is_required in required_fields.items():
            if is_required:
                value = product_data.get(field)
                if not value:
                    errors.append(f"Missing required field: {field}")
        
        # Check title is not generic
        title = product_data.get('title', '')
        if title:
            generic_titles = [
                'product', 'item', 'untitled', 'n/a', 'loading',
                'skip to', 'main content'
            ]
            if any(generic in title.lower() for generic in generic_titles):
                errors.append(f"Generic title detected: {title}")
        
        # Check price is reasonable
        price = product_data.get('price')
        if price is not None:
            if price < 1 or price > 10000:
                errors.append(f"Unreasonable price: ${price}")
        
        # Check image count
        image_urls = product_data.get('image_urls', [])
        if len(image_urls) < self.config.MIN_PRODUCT_IMAGES:
            errors.append(
                f"Insufficient images: {len(image_urls)} "
                f"(minimum: {self.config.MIN_PRODUCT_IMAGES})"
            )
        
        is_valid = len(errors) == 0
        
        if not is_valid:
            logger.debug(f"Validation errors: {errors}")
        
        return is_valid, errors
    
    def _validate_catalog(
        self,
        products: List[Dict],
        retailer: str
    ) -> Tuple[bool, List[str]]:
        """
        Validate extracted catalog data
        
        Returns:
            Tuple of (is_valid, errors)
        """
        errors = []
        
        # Check minimum product count
        if len(products) < self.config.MIN_CATALOG_PRODUCTS:
            errors.append(
                f"Insufficient products: {len(products)} "
                f"(minimum: {self.config.MIN_CATALOG_PRODUCTS})"
            )
        
        # Check all products have required fields
        required_fields = self.config.REQUIRED_CATALOG_FIELDS
        
        missing_urls = 0
        for product in products:
            for field, is_required in required_fields.items():
                if is_required and not product.get(field):
                    missing_urls += 1
                    break
        
        if missing_urls > 0:
            errors.append(f"{missing_urls} products missing required fields")
        
        # Check for duplicate URLs
        urls = [p.get('url') for p in products if p.get('url')]
        unique_urls = set(urls)
        if len(urls) != len(unique_urls):
            duplicates = len(urls) - len(unique_urls)
            errors.append(f"{duplicates} duplicate URLs detected")
        
        is_valid = len(errors) == 0
        
        if not is_valid:
            logger.debug(f"Validation errors: {errors}")
        
        return is_valid, errors
    
    async def _record_pattern_success(
        self,
        retailer: str,
        page_type: str,
        url: str,
        data: Dict
    ):
        """Record successful pattern usage for learning"""
        if not self.pattern_learner:
            return
        
        try:
            await self.pattern_learner.record_success(
                retailer=retailer,
                page_type=page_type,
                url=url,
                extracted_data=data
            )
        except Exception as e:
            logger.warning(f"⚠️ Failed to record pattern success: {e}")
    
    async def _record_pattern_failure(
        self,
        retailer: str,
        page_type: str,
        url: str,
        errors: List[str]
    ):
        """Record failed pattern usage for learning"""
        if not self.pattern_learner:
            return
        
        try:
            await self.pattern_learner.record_failure(
                retailer=retailer,
                page_type=page_type,
                url=url,
                errors=errors
            )
        except Exception as e:
            logger.warning(f"⚠️ Failed to record pattern failure: {e}")
    
    def get_parsing_stats(self) -> Dict:
        """
        Get parsing statistics
        
        Returns:
            Dict with success rates, common failures, etc.
        """
        if not self.pattern_learner:
            return {}
        
        try:
            return self.pattern_learner.get_stats()
        except Exception as e:
            logger.warning(f"⚠️ Failed to get pattern stats: {e}")
            return {}

