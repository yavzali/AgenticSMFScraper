"""
Commercial API Retailer Strategies

CSS selectors and extraction patterns for HTML parsing (BeautifulSoup)

This file parallels patchright_retailer_strategies.py but uses CSS selectors
for static HTML parsing instead of live DOM queries.

CRITICAL: Read Extraction/Patchright/patchright_retailer_strategies.py first
and reuse proven patterns where possible.
"""

import logging
from typing import Dict, List, Optional, Tuple
from bs4 import BeautifulSoup
import re
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from Shared.logger_config import setup_logging

logger = setup_logging(__name__)

class CommercialRetailerStrategies:
    """
    Retailer-specific HTML parsing strategies
    
    For each retailer, defines:
    - CSS selectors for product fields (title, price, description, images)
    - CSS selectors for catalog fields (product URLs, titles, prices)
    - Field extraction logic (cleaning, parsing)
    - Validation rules
    
    Usage:
        strategies = CommercialRetailerStrategies()
        product_data = strategies.extract_product(soup, 'nordstrom')
        catalog_data = strategies.extract_catalog(soup, 'nordstrom')
    """
    
    def __init__(self):
        # Initialize selector mappings for each retailer
        self._init_product_selectors()
        self._init_catalog_selectors()
        
        logger.info("✅ Retailer strategies initialized")
    
    # ============================================
    # PRODUCT PAGE SELECTORS
    # ============================================
    
    def _init_product_selectors(self):
        """
        Initialize CSS selectors for product page fields
        
        Format:
        {
            'retailer_name': {
                'title': ['selector1', 'selector2', ...],  # Try in order
                'price': ['selector1', 'selector2', ...],
                'description': ['selector1', 'selector2', ...],
                'images': ['selector1', 'selector2', ...],
                'stock': ['selector1', 'selector2', ...],
            }
        }
        
        Selectors tried in order until one succeeds
        """
        self.PRODUCT_SELECTORS = {
            'nordstrom': {
                'title': [
                    'h1[data-testid="product-title"]',
                    'h1.product-title',
                    'h1[itemprop="name"]',
                    'h1',
                ],
                'price': [
                    'span[data-testid="product-price"]',
                    '.product-price',
                    '[itemprop="price"]',
                    'span.price',
                ],
                'original_price': [
                    'span[data-testid="original-price"]',
                    '.original-price',
                    's.price',
                ],
                'description': [
                    'div[data-testid="product-description"]',
                    '.product-description',
                    '[itemprop="description"]',
                ],
                'images': [
                    'img[data-testid="product-image"]',
                    'img.product-image',
                    'img[src*="nordstrommedia"]',
                    'img[itemprop="image"]',
                ],
                'stock': [
                    'span[data-testid="availability"]',
                    '.availability',
                    '[itemprop="availability"]',
                ],
            },
            
            'anthropologie': {
                'title': [
                    'h1.product-name',
                    'h1[data-productname]',
                    'h1',
                ],
                'price': [
                    'span.product-sale-price',
                    'span.product-standard-price',
                    'span[data-price]',
                    '.price',
                ],
                'original_price': [
                    'span.product-standard-price',
                    's.price',
                ],
                'description': [
                    'div.product-description',
                    'div[data-description]',
                ],
                'images': [
                    'img[src*="anthropologie"]',
                    'img.product-image',
                    'img[data-zoom-image]',
                ],
                'stock': [
                    'span.availability',
                    'button[data-addtobag]',  # If button exists, in stock
                ],
            },
            
            'revolve': {
                'title': [
                    'h1.pdp_title',
                    'h1[itemprop="name"]',
                    'h1',
                ],
                'price': [
                    'span.pdp_price',
                    'span[itemprop="price"]',
                    '.price',
                ],
                'original_price': [
                    'span.pdp_price_original',
                    's.price',
                ],
                'description': [
                    'div.pdp_description',
                    'div[itemprop="description"]',
                ],
                'images': [
                    'img[src*="revolveassets"]',
                    'img.pdp_image',
                    'img[data-zoom]',
                ],
                'stock': [
                    'select#size',  # If size selector exists, in stock
                    'button.add-to-bag',
                ],
            },
            
            'aritzia': {
                'title': [
                    'h1.product-title',
                    'h1[data-product-name]',
                    'h1',
                ],
                'price': [
                    'span.product-price',
                    'span[data-price]',
                    '.price',
                ],
                'original_price': [
                    'span.product-price-original',
                    's.price',
                ],
                'description': [
                    'div.product-description',
                    'div.product-details',
                ],
                'images': [
                    'img[src*="aritzia"]',
                    'img.product-image',
                ],
                'stock': [
                    'button.add-to-bag',
                    'select.size-selector',
                ],
            },
            
            'hm': {
                'title': ['h1.product-item-headline', 'h1'],
                'price': ['span.price-value', '.price'],
                'description': ['div.product-description', 'div.product-detail'],
                'images': ['img[src*="hmgoepprod"]', 'img.product-image'],
                'stock': ['button.add-to-bag', 'select#picker-1'],
            },
            
            'abercrombie': {
                'title': ['h1.product-title', 'h1'],
                'price': ['span.product-price', '.price'],
                'description': ['div.product-long-description'],
                'images': ['img[src*="anf.scene7"]', 'img.product-image'],
                'stock': ['button.add-to-bag'],
            },
            
            'urban_outfitters': {
                'title': ['h1.product-title', 'h1'],
                'price': ['span.product-price', '.price'],
                'description': ['div.product-description'],
                'images': ['img[src*="urbanoutfitters"]', 'img.product-image'],
                'stock': ['button.add-to-bag'],
            },
            
            'mango': {
                'title': ['h1.product-name', 'h1'],
                'price': ['span.product-price', '.price'],
                'description': ['div.product-info'],
                'images': ['img[src*="mango"]', 'img.product-image'],
                'stock': ['button.add-to-cart'],
            },
            
            'uniqlo': {
                'title': ['h1.product-title', 'h1'],
                'price': ['span.product-price', '.price'],
                'description': ['div.product-description'],
                'images': ['img[src*="uniqlo"]', 'img.product-image'],
                'stock': ['button.add-to-cart'],
            },
            
            'asos': {
                'title': ['h1', 'h1.product-hero__title'],
                'price': ['span[data-testid="current-price"]', '.current-price'],
                'description': ['div.product-description'],
                'images': ['img[src*="asos"]', 'img.gallery-image'],
                'stock': ['button[data-testid="add-button"]'],
            },
        }
    
    # ============================================
    # CATALOG PAGE SELECTORS
    # ============================================
    
    def _init_catalog_selectors(self):
        """
        Initialize CSS selectors for catalog page fields
        
        Format:
        {
            'retailer_name': {
                'product_links': ['selector1', 'selector2', ...],
                'product_titles': ['selector1', 'selector2', ...],
                'product_prices': ['selector1', 'selector2', ...],
            }
        }
        """
        self.CATALOG_SELECTORS = {
            'nordstrom': {
                'product_links': [
                    'a[data-testid="product-link"]',
                    'a[href*="/s/"]',  # Nordstrom product URLs contain /s/
                    'a.product-link',
                ],
                'product_titles': [
                    'h3[data-testid="product-title"]',
                    '.product-title',
                ],
                'product_prices': [
                    'span[data-testid="product-price"]',
                    '.product-price',
                ],
            },
            
            'anthropologie': {
                'product_links': [
                    'a[href*="/shop/"]',  # Anthropologie product URLs contain /shop/
                    'a.product-link',
                ],
                'product_titles': [
                    'h3.product-name',
                    '.product-title',
                ],
                'product_prices': [
                    'span.product-price',
                    '.price',
                ],
            },
            
            'revolve': {
                'product_links': [
                    'a[href*="/dp/"]',  # Revolve product URLs contain /dp/
                    'a.product-link',
                ],
                'product_titles': [
                    'div.product-title',
                    '.product-name',
                ],
                'product_prices': [
                    'span.product-price',
                    '.price',
                ],
            },
            
            'aritzia': {
                'product_links': [
                    'a[href*="/product/"]',  # Aritzia product URLs
                    'a.product-tile__link',
                ],
                'product_titles': [
                    'h3.product-title',
                ],
                'product_prices': [
                    'span.product-price',
                ],
            },
            
            'hm': {
                'product_links': ['a[href*="/productpage"]'],
                'product_titles': ['h3.product-item-link'],
                'product_prices': ['span.price-value'],
            },
            
            'abercrombie': {
                'product_links': ['a[href*="/p/"]'],
                'product_titles': ['h3.product-title'],
                'product_prices': ['span.product-price'],
            },
            
            'urban_outfitters': {
                'product_links': ['a[href*="/shop/"]'],
                'product_titles': ['h3.product-title'],
                'product_prices': ['span.product-price'],
            },
            
            'mango': {
                'product_links': ['a[href*="/product"]'],
                'product_titles': ['h2.product-name'],
                'product_prices': ['span.product-price'],
            },
            
            'uniqlo': {
                'product_links': ['a[href*="/product"]'],
                'product_titles': ['h3.product-title'],
                'product_prices': ['span.price'],
            },
            
            'asos': {
                'product_links': ['a[data-testid="product-link"]'],
                'product_titles': ['h2[data-testid="product-title"]'],
                'product_prices': ['span[data-testid="product-price"]'],
            },
        }
    
    # ============================================
    # PRODUCT EXTRACTION
    # ============================================
    
    def extract_product(
        self,
        soup: BeautifulSoup,
        retailer: str
    ) -> Dict:
        """
        Extract product data from parsed HTML
        
        Args:
            soup: BeautifulSoup parsed HTML
            retailer: Retailer name
        
        Returns:
            Dict with extracted product data:
            {
                'title': str,
                'price': float,
                'original_price': float (optional),
                'description': str,
                'image_urls': [str],
                'stock_status': str,
            }
        """
        retailer_lower = retailer.lower()
        
        if retailer_lower not in self.PRODUCT_SELECTORS:
            raise ValueError(f"No product selectors for retailer: {retailer}")
        
        selectors = self.PRODUCT_SELECTORS[retailer_lower]
        
        product_data = {}
        
        # Extract title
        product_data['title'] = self._extract_text_field(
            soup, selectors['title'], 'title'
        )
        
        # Extract price
        price_text = self._extract_text_field(
            soup, selectors['price'], 'price'
        )
        product_data['price'] = self._parse_price(price_text)
        
        # Extract original price (if on sale)
        if 'original_price' in selectors:
            original_price_text = self._extract_text_field(
                soup, selectors['original_price'], 'original_price', required=False
            )
            if original_price_text:
                product_data['original_price'] = self._parse_price(original_price_text)
        
        # Extract description
        product_data['description'] = self._extract_text_field(
            soup, selectors['description'], 'description', required=False
        )
        
        # Extract images
        product_data['image_urls'] = self._extract_images(
            soup, selectors['images'], retailer_lower
        )
        
        # Extract stock status
        stock_text = self._extract_text_field(
            soup, selectors['stock'], 'stock', required=False
        )
        product_data['stock_status'] = self._parse_stock_status(
            stock_text, soup, selectors['stock']
        )
        
        logger.info(
            f"✅ Extracted product: {product_data.get('title', 'Unknown')[:50]}... "
            f"(${product_data.get('price', 0)}, {len(product_data.get('image_urls', []))} images)"
        )
        
        return product_data
    
    def _extract_text_field(
        self,
        soup: BeautifulSoup,
        selectors: List[str],
        field_name: str,
        required: bool = True
    ) -> Optional[str]:
        """
        Extract text field trying selectors in order
        
        Returns:
            Extracted text (cleaned), or None if not found
        """
        for selector in selectors:
            try:
                elem = soup.select_one(selector)
                if elem:
                    text = elem.get_text(strip=True)
                    if text:
                        logger.debug(f"✅ Found {field_name} with selector: {selector}")
                        return text
            except Exception as e:
                logger.debug(f"⚠️ Selector {selector} failed: {e}")
                continue
        
        if required:
            logger.warning(f"⚠️ Could not find {field_name} (tried {len(selectors)} selectors)")
        
        return None
    
    def _extract_images(
        self,
        soup: BeautifulSoup,
        selectors: List[str],
        retailer: str
    ) -> List[str]:
        """
        Extract image URLs from HTML
        
        Returns:
            List of image URLs (deduplicated, filtered)
        """
        image_urls = []
        
        for selector in selectors:
            try:
                images = soup.select(selector)
                
                for img in images:
                    # Try different attributes
                    src = (
                        img.get('src') or
                        img.get('data-src') or
                        img.get('data-zoom-image') or
                        img.get('data-large-image')
                    )
                    
                    if src and self._is_valid_image_url(src, retailer):
                        # Make absolute URL if relative
                        if src.startswith('//'):
                            src = 'https:' + src
                        elif src.startswith('/'):
                            src = f"https://www.{retailer}.com{src}"
                        
                        if src not in image_urls:
                            image_urls.append(src)
                
                if image_urls:
                    logger.debug(
                        f"✅ Found {len(image_urls)} images with selector: {selector}"
                    )
                    break
            
            except Exception as e:
                logger.debug(f"⚠️ Image selector {selector} failed: {e}")
                continue
        
        logger.info(f"📸 Extracted {len(image_urls)} image URLs")
        return image_urls
    
    def _is_valid_image_url(self, url: str, retailer: str) -> bool:
        """Check if image URL is valid (not placeholder, icon, etc.)"""
        url_lower = url.lower()
        
        # Exclude common invalid patterns
        invalid_patterns = [
            'placeholder',
            'loading',
            'spinner',
            'icon',
            'logo',
            'svg',
            '1x1',
            'data:image',
        ]
        
        for pattern in invalid_patterns:
            if pattern in url_lower:
                return False
        
        # Must contain image extension or CDN
        valid_patterns = [
            '.jpg', '.jpeg', '.png', '.webp',
            'scene7', 'cloudinary', 'imgix',
            retailer.lower(),
        ]
        
        return any(pattern in url_lower for pattern in valid_patterns)
    
    def _parse_price(self, price_text: Optional[str]) -> Optional[float]:
        """Parse price from text"""
        if not price_text:
            return None
        
        try:
            # Remove currency symbols and commas
            price_clean = re.sub(r'[^\d.]', '', price_text)
            return float(price_clean)
        except (ValueError, TypeError):
            logger.warning(f"⚠️ Could not parse price: {price_text}")
            return None
    
    def _parse_stock_status(
        self,
        stock_text: Optional[str],
        soup: BeautifulSoup,
        selectors: List[str]
    ) -> str:
        """
        Parse stock status from text or element presence
        
        Returns:
            'in_stock', 'out_of_stock', or 'unknown'
        """
        # Check text
        if stock_text:
            stock_lower = stock_text.lower()
            if 'in stock' in stock_lower or 'available' in stock_lower:
                return 'in_stock'
            elif 'out of stock' in stock_lower or 'sold out' in stock_lower:
                return 'out_of_stock'
        
        # Check element presence (e.g., "Add to Bag" button)
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                # Button exists = in stock
                return 'in_stock'
        
        return 'unknown'
    
    # ============================================
    # CATALOG EXTRACTION
    # ============================================
    
    def extract_catalog(
        self,
        soup: BeautifulSoup,
        retailer: str,
        max_products: int = 100
    ) -> List[Dict]:
        """
        Extract product listings from catalog page
        
        Args:
            soup: BeautifulSoup parsed HTML
            retailer: Retailer name
            max_products: Maximum products to extract
        
        Returns:
            List of dicts:
            [
                {
                    'url': str,
                    'title': str (optional),
                    'price': float (optional),
                },
                ...
            ]
        """
        retailer_lower = retailer.lower()
        
        if retailer_lower not in self.CATALOG_SELECTORS:
            raise ValueError(f"No catalog selectors for retailer: {retailer}")
        
        selectors = self.CATALOG_SELECTORS[retailer_lower]
        
        products = []
        
        # Extract product links
        for selector in selectors['product_links']:
            try:
                links = soup.select(selector)
                
                for link in links[:max_products]:
                    href = link.get('href')
                    if not href:
                        continue
                    
                    # Make absolute URL
                    if href.startswith('/'):
                        href = f"https://www.{retailer}.com{href}"
                    elif not href.startswith('http'):
                        continue
                    
                    # Get title (if available)
                    title = link.get_text(strip=True) if link.get_text() else None
                    
                    products.append({
                        'url': href,
                        'title': title,
                    })
                
                if products:
                    logger.debug(
                        f"✅ Found {len(products)} products with selector: {selector}"
                    )
                    break
            
            except Exception as e:
                logger.debug(f"⚠️ Catalog selector {selector} failed: {e}")
                continue
        
        logger.info(f"📋 Extracted {len(products)} products from catalog")
        return products

