"""
Shopify Manager - Handles all Shopify operations including product creation, updates, and image uploads
"""

# Add shared path for imports
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../Shared"))
sys.path.append(os.path.dirname(__file__))

import json
import base64
import aiohttp
import asyncio
import re
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
from PIL import Image
import os
from dotenv import load_dotenv

from logger_config import setup_logging

logger = setup_logging(__name__)

class ShopifyManager:
    def __init__(self):
        # Load environment variables from .env file
        # Look for .env file in project root (parent of Shared directory)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.join(script_dir, '..')
        env_path = os.path.join(project_root, '.env')
        load_dotenv(env_path)
        
        # Load configuration
        config_path = os.path.join(script_dir, '../Shared/config.json')
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        self.shopify_config = config['shopify']
        
        # Load credentials from environment variables (with config.json as fallback)
        self.store_url = os.getenv('SHOPIFY_STORE_URL') or self.shopify_config['store_url']
        self.api_version = self.shopify_config['api_version']
        self.access_token = os.getenv('SHOPIFY_ACCESS_TOKEN') or self.shopify_config['access_token']
        
        # Validate that we have actual credentials (not placeholder text)
        if not self.access_token or self.access_token.startswith('SHOPIFY_') or self.access_token == 'YOUR_':
            raise ValueError(
                "Invalid Shopify credentials. Please set SHOPIFY_ACCESS_TOKEN in your .env file "
                "or update config.json with valid credentials."
            )
        
        self.base_api_url = f"https://{self.store_url}/admin/api/{self.api_version}"
        self.headers = {
            'X-Shopify-Access-Token': self.access_token,
            'Content-Type': 'application/json'
        }
        
        logger.info(f"✅ ShopifyManager initialized for store: {self.store_url}")
    
    async def create_product(self, extracted_data: Dict, retailer_name: str, modesty_level: str, 
                           source_url: str, downloaded_images: List[str], product_type_override: str = None,
                           published: bool = True) -> Dict[str, Any]:
        """
        Create a new Shopify product with all data and images
        
        Args:
            published: If False, creates product as draft regardless of modesty_level
                      If True, uses modesty_level to determine status (backward compatible)
        """
        
        try:
            # Build product payload
            product_payload = self._build_product_payload(
                extracted_data, retailer_name, modesty_level, product_type_override, published
            )
            
            # Create product
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_api_url}/products.json",
                    headers=self.headers,
                    data=json.dumps(product_payload)
                ) as response:
                    
                    if response.status == 201:
                        product_data = await response.json()
                        product_id = product_data['product']['id']
                        variant_id = product_data['product']['variants'][0]['id']
                        
                        logger.info(f"Created Shopify product: {product_id}")
                        
                        # Upload images and collect CDN URLs
                        uploaded_images = []
                        shopify_image_urls = []
                        
                        if downloaded_images:
                            uploaded_images = await self._upload_images(session, product_id, downloaded_images, extracted_data.get('title', 'Product'))
                            
                            # Extract CDN URLs from uploaded images
                            for image_info in uploaded_images:
                                if isinstance(image_info, dict) and 'src' in image_info:
                                    shopify_image_urls.append(image_info['src'])
                                elif isinstance(image_info, str):
                                    shopify_image_urls.append(image_info)
                        
                        # Add metafields
                        await self._add_metafields(session, product_id, extracted_data, source_url, modesty_level, retailer_name)
                        
                        return {
                            'success': True,
                            'product_id': product_id,
                            'variant_id': variant_id,
                            'product_url': f"https://{self.store_url}/admin/products/{product_id}",
                            'images_uploaded': len(uploaded_images),
                            'shopify_image_urls': shopify_image_urls,  # NEW: Return CDN URLs
                            'shopify_data': product_data['product']
                        }
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to create Shopify product: {response.status} - {error_text}")
                        return {
                            'success': False,
                            'error': f"Shopify API error: {response.status} - {error_text}",
                            'shopify_image_urls': []  # Return empty list on failure
                        }
        
        except Exception as e:
            logger.error(f"Exception creating Shopify product: {e}")
            return {
                'success': False,
                'error': str(e),
                'shopify_image_urls': []  # Return empty list on failure
            }
    
    async def update_product(self, product_id: int, new_data: Dict, retailer_name: str) -> Dict[str, Any]:
        """Update an existing Shopify product"""
        
        try:
            async with aiohttp.ClientSession() as session:
                # Get current product data
                async with session.get(
                    f"{self.base_api_url}/products/{product_id}.json",
                    headers=self.headers
                ) as response:
                    
                    if response.status != 200:
                        return {'success': False, 'error': f"Could not fetch product {product_id}"}
                    
                    current_product = await response.json()
                    product = current_product['product']
                    
                    # Check if sale status changed for tag management
                    current_tags = product.get('tags', '').split(', ') if product.get('tags') else []
                    new_sale_status = new_data.get('sale_status', 'not on sale')
                    
                    # Update tags for sale status
                    updated_tags = [tag for tag in current_tags if tag != 'on-sale']
                    if new_sale_status == 'on sale':
                        updated_tags.append('on-sale')
                    
                    # Build update payload
                    update_payload = {
                        "product": {
                            "id": product_id,
                            "tags": ', '.join(updated_tags),
                            "variants": [{
                                "id": product['variants'][0]['id'],
                                "price": str(new_data.get('price', product['variants'][0]['price'])),
                                "compare_at_price": str(new_data.get('original_price', '')) if new_sale_status == 'on sale' else None,
                                "inventory_quantity": self._map_inventory_quantity(new_data.get('stock_status', 'in stock'))
                            }]
                        }
                    }
                    
                    # Update product
                    async with session.put(
                        f"{self.base_api_url}/products/{product_id}.json",
                        headers=self.headers,
                        data=json.dumps(update_payload)
                    ) as update_response:
                        
                        if update_response.status == 200:
                            # Update metafields
                            await self._update_metafields(session, product_id, new_data, retailer_name)
                            
                            logger.info(f"Updated Shopify product: {product_id}")
                            return {
                                'success': True,
                                'product_id': product_id,
                                'action': 'updated'
                            }
                        else:
                            error_text = await update_response.text()
                            return {'success': False, 'error': f"Update failed: {error_text}"}
        
        except Exception as e:
            logger.error(f"Exception updating product {product_id}: {e}")
            return {'success': False, 'error': str(e)}
    
    async def publish_product(self, product_id: int) -> Dict[str, Any]:
        """
        Publish a draft product to make it live on the store
        
        Args:
            product_id: Shopify product ID
            
        Returns:
            Dict with success status and details
        """
        try:
            async with aiohttp.ClientSession() as session:
                update_payload = {
                    "product": {
                        "id": product_id,
                        "status": "active"
                    }
                }
                
                async with session.put(
                    f"{self.base_api_url}/products/{product_id}.json",
                    headers=self.headers,
                    data=json.dumps(update_payload)
                ) as response:
                    
                    if response.status == 200:
                        logger.info(f"✅ Published product {product_id} to store")
                        return {
                            'success': True,
                            'product_id': product_id,
                            'action': 'published'
                        }
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Failed to publish product {product_id}: {error_text}")
                        return {
                            'success': False,
                            'error': f"Publish failed: {response.status} - {error_text}"
                        }
        
        except Exception as e:
            logger.error(f"Exception publishing product {product_id}: {e}")
            return {'success': False, 'error': str(e)}
    
    async def unpublish_product(self, product_id: int) -> Dict[str, Any]:
        """
        Unpublish a product (change to draft status)
        
        Args:
            product_id: Shopify product ID
            
        Returns:
            Dict with success status and details
        """
        try:
            async with aiohttp.ClientSession() as session:
                update_payload = {
                    "product": {
                        "id": product_id,
                        "status": "draft"
                    }
                }
                
                async with session.put(
                    f"{self.base_api_url}/products/{product_id}.json",
                    headers=self.headers,
                    data=json.dumps(update_payload)
                ) as response:
                    
                    if response.status == 200:
                        logger.info(f"✅ Unpublished product {product_id} (set to draft)")
                        return {
                            'success': True,
                            'product_id': product_id,
                            'action': 'unpublished'
                        }
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Failed to unpublish product {product_id}: {error_text}")
                        return {
                            'success': False,
                            'error': f"Unpublish failed: {response.status} - {error_text}"
                        }
        
        except Exception as e:
            logger.error(f"Exception unpublishing product {product_id}: {e}")
            return {'success': False, 'error': str(e)}
    
    def _standardize_product_type(self, clothing_type: str) -> str:
        """Standardize product type for Shopify consistency"""
        if not clothing_type:
            return 'Clothing'
            
        type_mapping = {
            'dress': 'Dresses',
            'dresses': 'Dresses',
            'dress top': 'Dress Tops',        # Space-separated singular
            'dress tops': 'Dress Tops',       # Space-separated plural
            'dress-top': 'Dress Tops',        # Hyphenated singular
            'dress-tops': 'Dress Tops',       # Hyphenated plural
            'dress_top': 'Dress Tops',        # NEW - Underscore singular
            'dress_tops': 'Dress Tops',       # NEW - Underscore plural (for safety)
            'top': 'Tops',
            'tops': 'Tops',
            'shirt': 'Tops',
            'shirts': 'Tops',
            'blouse': 'Tops',
            'blouses': 'Tops',
            'bottom': 'Bottoms',
            'bottoms': 'Bottoms',
            'pants': 'Bottoms',
            'jeans': 'Bottoms',
            'skirt': 'Bottoms',
            'skirts': 'Bottoms',
            'outerwear': 'Outerwear',
            'jacket': 'Outerwear',
            'jackets': 'Outerwear',
            'coat': 'Outerwear',
            'coats': 'Outerwear',
            'activewear': 'Activewear',
            'sportswear': 'Activewear',
            'swimwear': 'Swimwear',
            'lingerie': 'Lingerie',
            'underwear': 'Lingerie',
            'accessories': 'Accessories',
            'shoes': 'Shoes',
            'footwear': 'Shoes'
        }
        
        clothing_type_lower = clothing_type.lower().strip()
        return type_mapping.get(clothing_type_lower, clothing_type.title())
    
    def _determine_product_status(self, modesty_level: str) -> str:
        """Determine if product should be published or stay as draft"""
        if modesty_level in ['modest', 'moderately_modest']:
            return "active"  # Publish to store
        elif modesty_level == 'not_modest':
            return "draft"   # Keep as draft for training data
        else:
            return "draft"   # Default to draft for unknown levels
    
    def _clean_price(self, price_value: Any) -> str:
        """Clean and format price for Shopify API"""
        if not price_value:
            return "0.00"
        
        # Convert to string if it's a number
        price_str = str(price_value)
        
        # Remove currency symbols and extra whitespace
        price_str = re.sub(r'[$£€¥\s,]', '', price_str)
        
        # Handle empty or invalid strings
        if not price_str or price_str == 'None':
            return "0.00"
        
        try:
            # Convert to float and format to 2 decimal places
            price_float = float(price_str)
            return f"{price_float:.2f}"
        except ValueError:
            logger.warning(f"Could not parse price: {price_value}, defaulting to 0.00")
            return "0.00"

    def _build_product_payload(self, extracted_data: Dict, retailer_name: str, modesty_level: str, 
                              product_type_override: str = None, published: bool = True) -> Dict:
        """
        Build Shopify product payload with proper compliance
        
        Args:
            published: If False, forces status to 'draft' regardless of modesty_level
        """
        
        # Calculate compare at price for sales
        compare_at_price = None
        if extracted_data.get('sale_status') == 'on sale' and extracted_data.get('original_price'):
            compare_at_price = self._clean_price(extracted_data['original_price'])
        
        # Determine product type - use override if provided, otherwise use AI-extracted type
        if product_type_override:
            product_type = product_type_override
            logger.info(f"Using product type override: {product_type}")
        else:
            product_type = self._standardize_product_type(extracted_data.get('clothing_type', 'Clothing'))
        
        # Build tags - Handle "not-assessed" workflow
        tags = self._build_product_tags(modesty_level, retailer_name, extracted_data, product_type)
        
        # Determine product status
        if not published:
            # Force draft if explicitly requested (e.g., for assessment pipeline)
            product_status = "draft"
            tags.append("Awaiting Assessment")  # Tag to indicate needs review
        elif modesty_level == "pending_review":
            # For products from catalog crawler needing assessment
            tags.append("not-assessed")
            product_status = "draft"
        else:
            # Use modesty level to determine status (original behavior)
            product_status = self._determine_product_status(modesty_level)
        
        # Generate SKU if needed
        sku = extracted_data.get('product_code') or self._generate_sku(extracted_data, retailer_name)
        
        return {
            "product": {
                "title": extracted_data.get('title', 'Untitled Product'),
                "body_html": self._format_product_description(extracted_data.get('description', '')),
                "vendor": extracted_data.get('brand', retailer_name),
                "product_type": product_type,
                "status": product_status,
                "tags": ', '.join(tags),
                "variants": [{
                    "option1": "Default",
                    "price": self._clean_price(extracted_data.get('price', 0)),
                    "compare_at_price": compare_at_price,
                    "sku": sku,
                    "inventory_quantity": self._map_inventory_quantity(extracted_data.get('stock_status', 'in stock')),
                    "inventory_management": "shopify",
                    "inventory_policy": "deny",
                    "fulfillment_service": "manual",
                    "requires_shipping": True,
                    "taxable": True,
                    "weight": 0.5,
                    "weight_unit": "kg"
                }],
                "options": [{
                    "name": "Title",
                    "position": 1,
                    "values": ["Default"]
                }],
                "images": []  # Will be populated after creation
            }
        }
    
    def _format_product_description(self, description: str) -> str:
        """Format description following Shopify HTML best practices"""
        if not description:
            return "<p>Product description coming soon.</p>"
        
        # Clean and format description
        formatted_desc = description.replace('\n', '</p><p>')
        formatted_desc = f"<p>{formatted_desc}</p>"
        
        # Remove empty paragraphs
        formatted_desc = re.sub(r'<p>\s*</p>', '', formatted_desc)
        
        return formatted_desc
    
    def _build_product_tags(self, modesty_level: str, retailer_name: str, extracted_data: Dict, product_type: str = None) -> List[str]:
        """Build comprehensive tag list following Shopify tagging best practices with title case"""
        
        # Format modesty level to title case
        # Handle underscores: modest -> Modest, moderately_modest -> Moderately Modest
        modesty_tag = modesty_level.replace('_', ' ').title()
        
        # Format retailer name to title case
        # e.g., revolve -> Revolve, urban_outfitters -> Urban Outfitters
        retailer_tag = retailer_name.replace('_', ' ').title()
        
        # Format product type to SINGULAR form for tag
        # Use product_type if provided (from override), otherwise use extracted clothing_type
        if product_type:
            # Convert plural Shopify Product Type to singular tag
            # e.g., "Dress Tops" -> "Dress Top", "Dresses" -> "Dress"
            product_type_tag = self._convert_product_type_to_singular_tag(product_type)
        else:
            # Fallback to extracted clothing type
            clothing_type = extracted_data.get('clothing_type', 'clothing')
            product_type_tag = clothing_type.replace('_', ' ').replace('-', ' ').title()
        
        tags = [
            modesty_tag,           # e.g., "Modest", "Moderately Modest", "Not Modest"
            retailer_tag,          # e.g., "Revolve", "Asos", "Urban Outfitters"
            "Auto-Scraped",        # System tag in title case
            product_type_tag       # e.g., "Dress", "Top", "Dress Top" (singular)
        ]
        
        # Add sale tag if applicable
        if extracted_data.get('sale_status') == 'on sale':
            tags.append('On Sale')
        
        # Add brand tag if different from retailer
        brand = extracted_data.get('brand', '')
        if brand and brand.lower() != retailer_name.lower():
            tags.append(brand.title())  # Title case for brand names
        
        # Add stock status tag (keep lowercase with underscores as is)
        stock_status = extracted_data.get('stock_status')
        if stock_status:
            tags.append(stock_status)
        
        return tags
    
    def _convert_product_type_to_singular_tag(self, product_type: str) -> str:
        """Convert plural Product Type to singular form for tagging"""
        # Mapping of plural product types to singular tags
        singular_mapping = {
            'Dresses': 'Dress',
            'Dress Tops': 'Dress Top',
            'Tops': 'Top',
            'Bottoms': 'Bottom',
            'Pants': 'Pant',
            'Jeans': 'Jean',
            'Skirts': 'Skirt',
            'Shorts': 'Short',
            'Outerwear': 'Outerwear',  # Keep as-is
            'Jackets': 'Jacket',
            'Coats': 'Coat',
            'Activewear': 'Activewear',  # Keep as-is
            'Swimwear': 'Swimwear',  # Keep as-is
            'Lingerie': 'Lingerie',  # Keep as-is
            'Underwear': 'Underwear',  # Keep as-is
            'Accessories': 'Accessory',
            'Shoes': 'Shoe',
            'Clothing': 'Clothing'  # Keep as-is
        }
        
        return singular_mapping.get(product_type, product_type)
    
    def _generate_sku(self, extracted_data: Dict, retailer_name: str) -> str:
        """Generate SKU if not available from product code"""
        retailer_prefix = retailer_name[:3].upper()
        title_words = extracted_data.get('title', 'PRODUCT').split()[:2]
        title_suffix = ''.join(title_words).upper()[:6]
        timestamp_suffix = str(int(datetime.now().timestamp()))[-6:]
        
        return f"{retailer_prefix}-{title_suffix}-{timestamp_suffix}"
    
    def _map_inventory_quantity(self, stock_status: str) -> int:
        """Map stock status to Shopify inventory quantities"""
        status_mapping = {
            'in stock': 100,      # Ample inventory
            'low in stock': 5,    # Low inventory warning
            'out of stock': 0     # No inventory
        }
        return status_mapping.get(stock_status, 100)
    
    async def _upload_images(self, session: aiohttp.ClientSession, product_id: int, 
                           image_paths: List[str], product_title: str) -> List[Dict]:
        """Upload images to Shopify product"""
        
        uploaded_images = []
        
        for i, image_path in enumerate(image_paths[:5]):  # Max 5 images per Shopify limits
            try:
                # Validate and optimize image
                if not self._validate_shopify_image_requirements(image_path):
                    logger.warning(f"Image {image_path} does not meet Shopify requirements, skipping")
                    continue
                
                # Optimize image for Shopify
                optimized_image_path = await self._optimize_image_for_shopify(image_path)
                
                # Encode image
                with open(optimized_image_path, 'rb') as img_file:
                    image_data = base64.b64encode(img_file.read()).decode('utf-8')
                
                image_payload = {
                    "image": {
                        "attachment": image_data,
                        "position": i + 1,
                        "alt": f"{product_title} - Image {i + 1}"
                    }
                }
                
                async with session.post(
                    f"{self.base_api_url}/products/{product_id}/images.json",
                    headers=self.headers,
                    data=json.dumps(image_payload)
                ) as response:
                    
                    # Handle successful status codes (200-299 range)
                    if 200 <= response.status < 300:
                        image_data = await response.json()
                        uploaded_images.append(image_data['image'])
                        logger.info(f"✅ Successfully uploaded image {i + 1} for product {product_id} (HTTP {response.status})")
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Failed to upload image {i + 1} (HTTP {response.status}): {error_text}")
                
                # Clean up optimized image if different from original
                if optimized_image_path != image_path and os.path.exists(optimized_image_path):
                    os.remove(optimized_image_path)
            
            except Exception as e:
                logger.error(f"Error uploading image {image_path}: {e}")
                continue
        
        return uploaded_images
    
    def _validate_shopify_image_requirements(self, image_path: str) -> bool:
        """Validate image meets Shopify requirements"""
        try:
            if not os.path.exists(image_path):
                return False
            
            with Image.open(image_path) as img:
                width, height = img.size
                file_size = os.path.getsize(image_path)
                
                # Shopify image requirements
                if file_size > 20 * 1024 * 1024:  # 20MB max
                    return False
                if width < 100 or height < 100:  # Minimum dimensions
                    return False
                if width > 5760 or height > 5760:  # Maximum dimensions
                    return False
                
                return True
        except Exception as e:
            logger.error(f"Error validating image {image_path}: {e}")
            return False
    
    async def _optimize_image_for_shopify(self, image_path: str) -> str:
        """Optimize image for Shopify upload"""
        try:
            with Image.open(image_path) as img:
                # Convert to RGB if necessary
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                
                # Resize if too large (maintain aspect ratio)
                max_dimension = 2048
                if max(img.size) > max_dimension:
                    img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
                
                # Save optimized version
                optimized_path = image_path.replace('.jpg', '_optimized.jpg')
                img.save(optimized_path, 'JPEG', quality=85, optimize=True)
                
                return optimized_path
        except Exception as e:
            logger.error(f"Error optimizing image {image_path}: {e}")
            return image_path  # Return original if optimization fails
    
    async def _add_metafields(self, session: aiohttp.ClientSession, product_id: int, 
                            extracted_data: Dict, source_url: str, modesty_level: str, retailer_name: str):
        """Add custom metafields to product"""
        
        # Handle multiple product codes
        product_codes = []
        if extracted_data.get('product_code'):
            if isinstance(extracted_data['product_code'], list):
                product_codes = extracted_data['product_code']
            else:
                product_codes = [extracted_data['product_code']]
        
        metafields = [
            {
                "namespace": "custom",
                "key": "stock_status", 
                "value": extracted_data.get('stock_status', 'in stock'),
                "type": "single_line_text_field"
            },
            {
                "namespace": "inventory", 
                "key": "source_urls",
                "value": json.dumps([source_url]),
                "type": "json"
            },
            {
                "namespace": "custom",
                "key": "last_updated",
                "value": datetime.utcnow().isoformat() + "Z",
                "type": "date_time"
            },
            {
                "namespace": "custom",
                "key": "product_id",
                "value": json.dumps(product_codes),
                "type": "json"
            },
            {
                "namespace": "custom", 
                "key": "modesty_level",
                "value": modesty_level,
                "type": "single_line_text_field"
            },
            {
                "namespace": "custom",
                "key": "retailer_source", 
                "value": retailer_name,
                "type": "single_line_text_field"
            },
            {
                "namespace": "custom",
                "key": "scraping_method_used",
                "value": "openmanus",  # This should come from the actual method used
                "type": "single_line_text_field"
            },
            {
                "namespace": "custom",
                "key": "sale_status",
                "value": extracted_data.get('sale_status', 'not on sale'),
                "type": "single_line_text_field"
            },
            {
                "namespace": "custom",
                "key": "original_price",
                "value": str(extracted_data.get('original_price', '')),
                "type": "single_line_text_field"
            },
            # NEW: Visual analysis fields
            {
                "namespace": "clothing",
                "key": "neckline",
                "value": extracted_data.get('neckline', 'unknown'),
                "type": "single_line_text_field"
            },
            {
                "namespace": "clothing",
                "key": "sleeve_length", 
                "value": extracted_data.get('sleeve_length', 'unknown'),
                "type": "single_line_text_field"
            },
            {
                "namespace": "clothing",
                "key": "visual_analysis_confidence",
                "value": str(extracted_data.get('visual_analysis_confidence', '')),
                "type": "single_line_text_field"
            },
            {
                "namespace": "clothing",
                "key": "visual_analysis_source",
                "value": extracted_data.get('visual_analysis_source', ''),
                "type": "single_line_text_field"
            }
        ]
        
        for metafield in metafields:
            try:
                metafield_payload = {
                    "metafield": {
                        "namespace": metafield["namespace"],
                        "key": metafield["key"],
                        "value": metafield["value"],
                        "type": metafield["type"],
                        "owner_id": product_id,
                        "owner_resource": "product"
                    }
                }
                
                async with session.post(
                    f"{self.base_api_url}/products/{product_id}/metafields.json",
                    headers=self.headers,
                    data=json.dumps(metafield_payload)
                ) as response:
                    
                    if response.status != 201:
                        error_text = await response.text()
                        logger.warning(f"Failed to create metafield {metafield['key']}: {error_text}")
                    else:
                        logger.debug(f"Created metafield {metafield['key']} for product {product_id}")
            
            except Exception as e:
                logger.error(f"Error creating metafield {metafield['key']}: {e}")
    
    async def _update_metafields(self, session: aiohttp.ClientSession, product_id: int, 
                               new_data: Dict, retailer_name: str):
        """Update metafields for existing product"""
        
        # Update key metafields
        update_metafields = [
            ("custom", "stock_status", new_data.get('stock_status', 'in stock')),
            ("custom", "last_updated", datetime.utcnow().isoformat() + "Z"),
            ("custom", "sale_status", new_data.get('sale_status', 'not on sale')),
            ("custom", "original_price", str(new_data.get('original_price', '')))
        ]
        
        for namespace, key, value in update_metafields:
            try:
                # Get existing metafield first
                async with session.get(
                    f"{self.base_api_url}/products/{product_id}/metafields.json",
                    headers=self.headers
                ) as response:
                    
                    if response.status == 200:
                        metafields_data = await response.json()
                        metafields = metafields_data.get('metafields', [])
                        
                        # Find the metafield to update
                        metafield_id = None
                        for mf in metafields:
                            if mf['namespace'] == namespace and mf['key'] == key:
                                metafield_id = mf['id']
                                break
                        
                        if metafield_id:
                            # Update existing metafield
                            update_payload = {
                                "metafield": {
                                    "id": metafield_id,
                                    "value": value
                                }
                            }
                            
                            async with session.put(
                                f"{self.base_api_url}/products/{product_id}/metafields/{metafield_id}.json",
                                headers=self.headers,
                                data=json.dumps(update_payload)
                            ) as update_response:
                                
                                if update_response.status == 200:
                                    logger.debug(f"Updated metafield {key} for product {product_id}")
                                else:
                                    error_text = await update_response.text()
                                    logger.warning(f"Failed to update metafield {key}: {error_text}")
            
            except Exception as e:
                logger.error(f"Error updating metafield {key}: {e}")
    
    async def get_product(self, product_id: int) -> Optional[Dict]:
        """Get product data from Shopify"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_api_url}/products/{product_id}.json",
                    headers=self.headers
                ) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        return data['product']
                    else:
                        logger.error(f"Failed to get product {product_id}: {response.status}")
                        return None
        
        except Exception as e:
            logger.error(f"Error getting product {product_id}: {e}")
            return None
    
    def get_admin_url(self, product_id: int) -> str:
        """Get Shopify admin URL for product"""
        return f"https://{self.store_url}/admin/products/{product_id}"
    
    # =================== PIPELINE SEPARATION METHODS ===================
    
    async def create_draft_for_review(self, extracted_data: Dict, retailer_name: str) -> Optional[int]:
        """
        Create Shopify draft specifically for modesty review
        Returns shopify_product_id for tracking, or None if failed
        """
        try:
            # Create draft with special "pending-modesty-review" tag
            payload = self._build_product_payload(extracted_data, retailer_name, "pending_review")
            
            # Add pending-modesty-review tag
            current_tags = payload["product"].get("tags", "")
            if current_tags:
                payload["product"]["tags"] = current_tags + ", pending-modesty-review"
            else:
                payload["product"]["tags"] = "pending-modesty-review"
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_api_url}/products.json",
                    headers=self.headers,
                    data=json.dumps(payload)
                ) as response:
                    if response.status == 201:
                        result = await response.json()
                        shopify_id = result['product']['id']
                        
                        # Upload images if available
                        if extracted_data.get('image_urls'):
                            try:
                                # Download and upload images
                                image_urls = extracted_data['image_urls']
                                if isinstance(image_urls, str):
                                    image_urls = json.loads(image_urls) if image_urls.startswith('[') else [image_urls]
                                
                                # Upload first few images (limit to 5 for cost optimization)
                                for img_url in image_urls[:5]:
                                    await self._upload_image_from_url(session, shopify_id, img_url)
                            except Exception as img_error:
                                logger.warning(f"Failed to upload images for draft {shopify_id}: {img_error}")
                        
                        logger.info(f"Created Shopify draft for review: {shopify_id}")
                        return shopify_id
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to create Shopify draft: {error_text}")
                        return None
                        
        except Exception as e:
            logger.error(f"Exception creating Shopify draft: {e}")
            return None
    
    async def _upload_image_from_url(self, session: aiohttp.ClientSession, product_id: int, image_url: str):
        """Upload a single image from URL to Shopify product"""
        try:
            image_payload = {
                "image": {
                    "src": image_url
                }
            }
            
            async with session.post(
                f"{self.base_api_url}/products/{product_id}/images.json",
                headers=self.headers,
                data=json.dumps(image_payload)
            ) as response:
                if response.status == 201:
                    logger.debug(f"Uploaded image to product {product_id}")
                else:
                    logger.warning(f"Failed to upload image: {response.status}")
        except Exception as e:
            logger.warning(f"Error uploading image: {e}")
    
    async def update_review_decision(self, shopify_id: int, decision: str) -> bool:
        """
        Update draft product based on modesty review decision
        decision: 'modest', 'moderately_modest', 'not_modest'
        """
        try:
            async with aiohttp.ClientSession() as session:
                # Get current product
                async with session.get(
                    f"{self.base_api_url}/products/{shopify_id}.json",
                    headers=self.headers
                ) as response:
                    if response.status != 200:
                        return False
                        
                    result = await response.json()
                    product = result['product']
                    
                    # Update tags and status
                    current_tags = [tag.strip() for tag in product.get('tags', '').split(',') if tag.strip()]
                    # Remove pending-modesty-review tag
                    updated_tags = [tag for tag in current_tags if tag != 'pending-modesty-review']
                    # Add modesty decision tag
                    updated_tags.append(decision)
                    
                    # Determine new status
                    new_status = self._determine_product_status(decision)
                    
                    # Update product
                    update_payload = {
                        "product": {
                            "id": shopify_id,
                            "tags": ', '.join(updated_tags),
                            "status": new_status
                        }
                    }
                    
                    async with session.put(
                        f"{self.base_api_url}/products/{shopify_id}.json",
                        headers=self.headers,
                        data=json.dumps(update_payload)
                    ) as update_response:
                        if update_response.status == 200:
                            logger.info(f"Updated product {shopify_id} with decision: {decision}")
                            return True
                        else:
                            error_text = await update_response.text()
                            logger.error(f"Failed to update product: {error_text}")
                            return False
                        
        except Exception as e:
            logger.error(f"Exception updating review decision: {e}")
            return False
    
    async def promote_duplicate_to_modesty_review(self, catalog_product_data: Dict, retailer_name: str) -> Optional[int]:
        """
        Promote a duplicate_uncertain product to full modesty review
        Triggers full scraping + Shopify draft creation
        """
        try:
            # Import here to avoid circular dependency
            sys.path.append(os.path.join(os.path.dirname(__file__), "../Shared"))
            from unified_extractor import UnifiedExtractor
            
            # Perform full product scraping
            extractor = UnifiedExtractor()
            result = await extractor.extract_product_data(
                catalog_product_data['catalog_url'], 
                retailer_name
            )
            
            if result.success:
                # Create Shopify draft for review
                shopify_id = await self.create_draft_for_review(result.data, retailer_name)
                return shopify_id
            else:
                logger.error(f"Failed to scrape product for promotion: {result.errors}")
                return None
                
        except Exception as e:
            logger.error(f"Exception promoting duplicate to review: {e}")
            return None
    
    async def update_modesty_decision(self, product_id: int, decision: str) -> bool:
        """
        Update product with modesty decision and remove not-assessed tag
        decision: 'modest', 'moderately_modest', 'not_modest'
        """
        try:
            async with aiohttp.ClientSession() as session:
                # Get current product
                async with session.get(
                    f"{self.base_api_url}/products/{product_id}.json",
                    headers=self.headers
                ) as response:
                    if response.status != 200:
                        logger.error(f"Failed to get product {product_id}: {response.status}")
                        return False
                        
                    result = await response.json()
                    product = result['product']
                    
                    # Update tags: remove "not-assessed", add modesty decision
                    current_tags = [tag.strip() for tag in product.get('tags', '').split(',') if tag.strip()]
                    updated_tags = [tag for tag in current_tags if tag != 'not-assessed']
                    
                    # Add the modesty decision tag if not already present
                    if decision not in updated_tags:
                        updated_tags.append(decision)
                    
                    # Determine new status based on decision
                    new_status = self._determine_product_status(decision)
                    
                    # Update product
                    update_payload = {
                        "product": {
                            "id": product_id,
                            "tags": ', '.join(updated_tags),
                            "status": new_status
                        }
                    }
                    
                    async with session.put(
                        f"{self.base_api_url}/products/{product_id}.json",
                        headers=self.headers,
                        data=json.dumps(update_payload)
                    ) as update_response:
                        
                        success = update_response.status == 200
                        if success:
                            logger.info(f"Updated product {product_id} with decision: {decision} (status: {new_status})")
                        else:
                            error_text = await update_response.text()
                            logger.error(f"Failed to update product {product_id}: {error_text}")
                        return success
                        
        except Exception as e:
            logger.error(f"Exception updating modesty decision for product {product_id}: {e}")
            return False