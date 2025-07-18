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

from logger_config import setup_logging

logger = setup_logging(__name__)

class ShopifyManager:
    def __init__(self):
        # Load configuration
        # Get the directory where this script is located
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, '../Shared/config.json')
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        self.shopify_config = config['shopify']
        self.store_url = self.shopify_config['store_url']
        self.api_version = self.shopify_config['api_version']
        self.access_token = self.shopify_config['access_token']
        
        self.base_api_url = f"https://{self.store_url}/admin/api/{self.api_version}"
        self.headers = {
            'X-Shopify-Access-Token': self.access_token,
            'Content-Type': 'application/json'
        }
    
    async def create_product(self, extracted_data: Dict, retailer_name: str, modesty_level: str, 
                           source_url: str, downloaded_images: List[str]) -> Dict[str, Any]:
        """Create a new Shopify product with all data and images"""
        
        try:
            # Build product payload
            product_payload = self._build_product_payload(extracted_data, retailer_name, modesty_level)
            
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
                        
                        # Upload images
                        uploaded_images = []
                        if downloaded_images:
                            uploaded_images = await self._upload_images(session, product_id, downloaded_images, extracted_data.get('title', 'Product'))
                        
                        # Add metafields
                        await self._add_metafields(session, product_id, extracted_data, source_url, modesty_level, retailer_name)
                        
                        return {
                            'success': True,
                            'product_id': product_id,
                            'variant_id': variant_id,
                            'product_url': f"https://{self.store_url}/admin/products/{product_id}",
                            'images_uploaded': len(uploaded_images),
                            'shopify_data': product_data['product']
                        }
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to create Shopify product: {response.status} - {error_text}")
                        return {
                            'success': False,
                            'error': f"Shopify API error: {response.status} - {error_text}"
                        }
        
        except Exception as e:
            logger.error(f"Exception creating Shopify product: {e}")
            return {
                'success': False,
                'error': str(e)
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
    
    def _standardize_product_type(self, clothing_type: str) -> str:
        """Standardize product type for Shopify consistency"""
        if not clothing_type:
            return 'Clothing'
            
        type_mapping = {
            'dress': 'Dresses',
            'dresses': 'Dresses',
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

    def _build_product_payload(self, extracted_data: Dict, retailer_name: str, modesty_level: str) -> Dict:
        """Build Shopify product payload with proper compliance"""
        
        # Calculate compare at price for sales
        compare_at_price = None
        if extracted_data.get('sale_status') == 'on sale' and extracted_data.get('original_price'):
            compare_at_price = str(extracted_data['original_price'])
        
        # Build tags
        tags = self._build_product_tags(modesty_level, retailer_name, extracted_data)
        
        # Generate SKU if needed
        sku = extracted_data.get('product_code') or self._generate_sku(extracted_data, retailer_name)
        
        return {
            "product": {
                "title": extracted_data.get('title', 'Untitled Product'),
                "body_html": self._format_product_description(extracted_data.get('description', '')),
                "vendor": extracted_data.get('brand', retailer_name),
                "product_type": self._standardize_product_type(extracted_data.get('clothing_type', 'Clothing')),
                "status": "draft",  # Always create as draft for review
                "tags": ', '.join(tags),
                "variants": [{
                    "option1": "Default",
                    "price": str(extracted_data.get('price', 0)),
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
    
    def _build_product_tags(self, modesty_level: str, retailer_name: str, extracted_data: Dict) -> List[str]:
        """Build comprehensive tag list following Shopify tagging best practices"""
        tags = [
            modesty_level,
            retailer_name.lower(),  # Always add retailer as tag
            "auto-scraped",
            extracted_data.get('clothing_type', 'clothing').lower()
        ]
        
        # Add sale tag if applicable
        if extracted_data.get('sale_status') == 'on sale':
            tags.append('on-sale')
        
        # Add brand tag if different from retailer
        brand = extracted_data.get('brand', '')
        if brand and brand.lower() != retailer_name.lower():
            tags.append(brand.lower())
        
        # Add stock status tag
        stock_status = extracted_data.get('stock_status')
        if stock_status:
            tags.append(stock_status.replace(' ', '_'))
        
        return tags
    
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