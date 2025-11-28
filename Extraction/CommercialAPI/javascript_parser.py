"""
JavaScript Data Parser for Commercial API Tower
Extracts product data embedded in JavaScript variables and JSON-LD

Handles retailers that embed product data in:
- JavaScript objects (Abercrombie, Urban Outfitters, Aritzia)
- JSON-LD structured data
- window.__INITIAL_STATE__ patterns
"""

import re
import json
import logging
from typing import Dict, List, Optional, Any
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class JavaScriptDataParser:
    """
    Extracts product data from JavaScript embedded in HTML
    """
    
    def __init__(self):
        pass
    
    def extract_abercrombie_data(self, html: str, soup: BeautifulSoup) -> Optional[Dict]:
        """
        Extract Abercrombie product data from JavaScript objects
        
        Abercrombie embeds data in:
        - productPrices[productId] = {...}
        - productCatalog[productId] = {...}
        """
        try:
            logger.debug("🔍 Extracting Abercrombie JavaScript data")
            
            # Find all script tags
            script_tags = soup.find_all('script', string=re.compile(r'productCatalog|productPrices'))
            
            product_data = {}
            
            for script in script_tags:
                script_content = script.string
                if not script_content:
                    continue
                
                # Extract productCatalog data
                catalog_match = re.search(
                    r'productCatalog\[(\d+)\]\s*=\s*({[^;]+});',
                    script_content,
                    re.DOTALL
                )
                if catalog_match:
                    try:
                        catalog_json = json.loads(catalog_match.group(2))
                        product_data['catalog'] = catalog_json
                        logger.debug(f"✅ Extracted productCatalog: {catalog_json.get('name', 'N/A')}")
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse productCatalog JSON: {e}")
                
                # Extract productPrices data
                prices_match = re.search(
                    r'productPrices\[(\d+)\]\s*=\s*({[^;]+});',
                    script_content,
                    re.DOTALL
                )
                if prices_match:
                    try:
                        prices_json = json.loads(prices_match.group(2))
                        product_data['prices'] = prices_json
                        logger.debug(f"✅ Extracted productPrices: {len(prices_json.get('items', {}))} items")
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse productPrices JSON: {e}")
            
            if not product_data:
                logger.warning("⚠️ No Abercrombie JavaScript data found")
                return None
            
            # Convert to standard format
            return self._format_abercrombie_data(product_data)
            
        except Exception as e:
            logger.error(f"Error extracting Abercrombie JavaScript data: {e}")
            return None
    
    def _format_abercrombie_data(self, data: Dict) -> Dict:
        """Convert Abercrombie JavaScript data to standard product format"""
        try:
            catalog = data.get('catalog', {})
            prices = data.get('prices', {})
            
            # Extract basic info
            title = catalog.get('name', '') or catalog.get('name_EN', '')
            description = catalog.get('longDesc', '') or catalog.get('shortDesc', '')
            
            # Extract price
            price = None
            sale_price = None
            
            # Get first item's pricing
            items = prices.get('items', {})
            if items:
                first_item = next(iter(items.values()))
                sale_price = first_item.get('offerPrice')
                list_price = first_item.get('listPrice')
                
                if sale_price and sale_price < list_price:
                    price = sale_price
                else:
                    price = list_price
            
            # Extract images from imageSets
            image_urls = []
            image_sets = catalog.get('imageSets', {})
            
            # Get model images first (best quality)
            model_images = image_sets.get('model', [])
            for img in model_images:
                img_id = img.get('id', '')
                if img_id:
                    # Abercrombie uses anf.scene7.com
                    image_url = f"https://img.abercrombie.com/is/image/anf/{img_id}?policy=product-large"
                    image_urls.append(image_url)
            
            # Add product images if model images not available
            if not image_urls:
                prod_images = image_sets.get('prod', [])
                for img in prod_images:
                    img_id = img.get('id', '')
                    if img_id:
                        image_url = f"https://img.abercrombie.com/is/image/anf/{img_id}?policy=product-large"
                        image_urls.append(image_url)
            
            # Stock status
            stock_status = 'in_stock'  # Abercrombie shows pages for available items
            
            # Brand
            brand = catalog.get('productAttrs', {}).get('brand', 'Abercrombie & Fitch')
            
            return {
                'title': title,
                'price': price,
                'original_price': None,  # Will be extracted from first item if on sale
                'description': description,
                'image_urls': image_urls,
                'stock_status': stock_status,
                'brand': brand,
                'product_id': catalog.get('productId'),
                'color': catalog.get('colorFamily'),
                'style': catalog.get('productAttrs', {}).get('Style')
            }
            
        except Exception as e:
            logger.error(f"Error formatting Abercrombie data: {e}")
            return {}
    
    def extract_urban_outfitters_data(self, html: str, soup: BeautifulSoup) -> Optional[Dict]:
        """
        Extract Urban Outfitters product data from JavaScript
        
        Urban Outfitters uses similar structure to Anthropologie
        """
        try:
            logger.debug("🔍 Extracting Urban Outfitters JavaScript data")
            
            # Try window.__INITIAL_STATE__ pattern
            script_tags = soup.find_all('script', string=re.compile(r'window\.__INITIAL_STATE__|__NUXT__'))
            
            for script in script_tags:
                script_content = script.string
                if not script_content:
                    continue
                
                # Extract JSON data
                state_match = re.search(
                    r'(?:window\.__INITIAL_STATE__|__NUXT__)\s*=\s*({.+?});?\s*(?:</script|$)',
                    script_content,
                    re.DOTALL
                )
                
                if state_match:
                    try:
                        state_json = json.loads(state_match.group(1))
                        logger.debug("✅ Extracted Urban Outfitters state data")
                        return self._format_urban_outfitters_data(state_json)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse Urban Outfitters state JSON: {e}")
            
            # Fallback: Try JSON-LD
            return self._extract_json_ld(soup)
            
        except Exception as e:
            logger.error(f"Error extracting Urban Outfitters JavaScript data: {e}")
            return None
    
    def _format_urban_outfitters_data(self, data: Dict) -> Dict:
        """Convert Urban Outfitters state data to standard format"""
        try:
            # Navigate the nested structure
            product = data
            
            # Try different paths
            if 'product' in data:
                product = data['product']
            elif 'data' in data and 'product' in data['data']:
                product = data['data']['product']
            
            return {
                'title': product.get('name', ''),
                'price': product.get('price', {}).get('current') or product.get('currentPrice'),
                'original_price': product.get('price', {}).get('regular') or product.get('regularPrice'),
                'description': product.get('description', ''),
                'image_urls': [img.get('url') for img in product.get('images', []) if img.get('url')],
                'stock_status': 'in_stock' if product.get('inStock') else 'out_of_stock',
                'brand': product.get('brand', 'Urban Outfitters'),
                'product_id': product.get('id') or product.get('productId')
            }
            
        except Exception as e:
            logger.error(f"Error formatting Urban Outfitters data: {e}")
            return {}
    
    def extract_aritzia_data(self, html: str, soup: BeautifulSoup) -> Optional[Dict]:
        """
        Extract Aritzia product data from JavaScript
        
        Aritzia embeds data in window.__INITIAL_STATE__ or similar
        """
        try:
            logger.debug("🔍 Extracting Aritzia JavaScript data")
            
            # Find script tags with product data
            script_tags = soup.find_all('script', string=re.compile(r'window\.__INITIAL_STATE__|productData|__NEXT_DATA__'))
            
            for script in script_tags:
                script_content = script.string
                if not script_content:
                    continue
                
                # Try __NEXT_DATA__ (Next.js pattern)
                next_match = re.search(
                    r'__NEXT_DATA__\s*=\s*({.+?});?\s*(?:</script|$)',
                    script_content,
                    re.DOTALL
                )
                
                if next_match:
                    try:
                        next_json = json.loads(next_match.group(1))
                        logger.debug("✅ Extracted Aritzia __NEXT_DATA__")
                        return self._format_aritzia_data(next_json)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse Aritzia __NEXT_DATA__: {e}")
                
                # Try window.__INITIAL_STATE__
                state_match = re.search(
                    r'window\.__INITIAL_STATE__\s*=\s*({.+?});?\s*(?:</script|$)',
                    script_content,
                    re.DOTALL
                )
                
                if state_match:
                    try:
                        state_json = json.loads(state_match.group(1))
                        logger.debug("✅ Extracted Aritzia state data")
                        return self._format_aritzia_data(state_json)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse Aritzia state JSON: {e}")
            
            # Fallback: JSON-LD
            return self._extract_json_ld(soup)
            
        except Exception as e:
            logger.error(f"Error extracting Aritzia JavaScript data: {e}")
            return None
    
    def _format_aritzia_data(self, data: Dict) -> Dict:
        """Convert Aritzia state/NEXT data to standard format"""
        try:
            # Navigate nested structure
            product = data
            
            # Common Next.js structure
            if 'props' in data and 'pageProps' in data['props']:
                product = data['props']['pageProps'].get('product', {})
            elif 'product' in data:
                product = data['product']
            
            # Extract images
            image_urls = []
            if 'images' in product:
                image_urls = [img.get('url') or img.get('src') for img in product['images'] if img.get('url') or img.get('src')]
            elif 'media' in product:
                image_urls = [img.get('url') or img.get('src') for img in product['media'] if img.get('url') or img.get('src')]
            
            return {
                'title': product.get('name', '') or product.get('title', ''),
                'price': product.get('price', {}).get('current') or product.get('currentPrice') or product.get('price'),
                'original_price': product.get('price', {}).get('regular') or product.get('regularPrice'),
                'description': product.get('description', ''),
                'image_urls': image_urls,
                'stock_status': 'in_stock' if product.get('available') or product.get('inStock') else 'out_of_stock',
                'brand': 'Aritzia',
                'product_id': product.get('id') or product.get('productId') or product.get('sku')
            }
            
        except Exception as e:
            logger.error(f"Error formatting Aritzia data: {e}")
            return {}
    
    def _extract_json_ld(self, soup: BeautifulSoup) -> Optional[Dict]:
        """
        Extract product data from JSON-LD structured data
        Fallback method for all retailers
        """
        try:
            logger.debug("🔍 Looking for JSON-LD structured data")
            
            json_ld_scripts = soup.find_all('script', type='application/ld+json')
            
            for script in json_ld_scripts:
                try:
                    json_data = json.loads(script.string)
                    
                    # Handle both single objects and arrays
                    if isinstance(json_data, list):
                        for item in json_data:
                            if item.get('@type') == 'Product':
                                json_data = item
                                break
                    
                    if json_data.get('@type') == 'Product':
                        logger.debug("✅ Found Product JSON-LD")
                        return self._format_json_ld_data(json_data)
                        
                except (json.JSONDecodeError, AttributeError) as e:
                    logger.debug(f"Skipping invalid JSON-LD: {e}")
                    continue
            
            logger.debug("⚠️ No JSON-LD product data found")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting JSON-LD: {e}")
            return None
    
    def _format_json_ld_data(self, data: Dict) -> Dict:
        """Convert JSON-LD Product schema to standard format"""
        try:
            # Extract offers (price data)
            offers = data.get('offers', {})
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            
            # Handle AggregateOffer (multiple variants)
            if offers.get('@type') == 'AggregateOffer':
                # Use lowPrice from aggregate offer
                price = offers.get('lowPrice') or offers.get('highPrice')
                # Also check nested offers array
                if not price and 'offers' in offers and isinstance(offers['offers'], list):
                    price = offers['offers'][0].get('price')
            else:
                # Regular Offer
                price = offers.get('price')
            
            currency = offers.get('priceCurrency', 'USD')
            
            # Convert price to float if it's a string
            if isinstance(price, str):
                price = float(price.replace(currency, '').strip())
            
            # Extract images
            image_urls = []
            images = data.get('image', [])
            if isinstance(images, str):
                image_urls = [images]
            elif isinstance(images, list):
                image_urls = images
            
            # Stock status
            availability = offers.get('availability', '').lower()
            stock_status = 'in_stock'
            if 'outofstock' in availability or 'discontinued' in availability:
                stock_status = 'out_of_stock'
            
            return {
                'title': data.get('name', ''),
                'price': price,
                'original_price': None,
                'description': data.get('description', ''),
                'image_urls': image_urls,
                'stock_status': stock_status,
                'brand': data.get('brand', {}).get('name') if isinstance(data.get('brand'), dict) else data.get('brand'),
                'product_id': data.get('sku') or data.get('productID')
            }
            
        except Exception as e:
            logger.error(f"Error formatting JSON-LD data: {e}")
            return {}
    
    def extract_product_data(self, html: str, soup: BeautifulSoup, retailer: str) -> Optional[Dict]:
        """
        Main entry point - extract product data based on retailer
        
        Args:
            html: Raw HTML string
            soup: BeautifulSoup object
            retailer: Retailer name
            
        Returns:
            Dict with product data or None if extraction fails
        """
        retailer_lower = retailer.lower().replace(' ', '').replace('&', '')
        
        logger.info(f"🔍 Attempting JavaScript extraction for {retailer}")
        
        # Route to retailer-specific extractor
        if 'abercrombie' in retailer_lower or 'anf' in retailer_lower:
            result = self.extract_abercrombie_data(html, soup)
        elif 'urban' in retailer_lower or 'urbanoutfitters' in retailer_lower:
            result = self.extract_urban_outfitters_data(html, soup)
        elif 'aritzia' in retailer_lower:
            result = self.extract_aritzia_data(html, soup)
        else:
            # Generic fallback to JSON-LD
            result = self._extract_json_ld(soup)
        
        if result and result.get('title'):
            logger.info(f"✅ JavaScript extraction successful: {result.get('title', 'N/A')[:50]}...")
            return result
        else:
            logger.warning(f"⚠️ JavaScript extraction failed for {retailer}")
            return None

