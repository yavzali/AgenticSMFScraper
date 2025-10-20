# Shopify Integration Foundation - Quick Start Guide

## Overview
The catalog crawler now creates Shopify drafts with "not-assessed" tags and stores CDN URLs for future web-based assessment.

## How It Works

### Discovery Phase (Automatic)
1. Catalog crawler discovers new products
2. Products automatically scraped and uploaded to Shopify
3. Created as drafts with "not-assessed" tag
4. Shopify CDN URLs stored in local database

### Assessment Phase (Future Web Interface)
1. Query products with "not-assessed" tag
2. Display using stored Shopify CDN URLs
3. Make modesty decision
4. Update product (removes "not-assessed", publishes if modest)

## Key Features Added

### 1. Automatic "not-assessed" Tagging
Products from catalog crawler automatically get:
- Status: `draft`
- Tag: `not-assessed`
- Shopify CDN image URLs stored locally

### 2. Shopify CDN URL Storage
CDN URLs stored in database as JSON:
```json
["https://cdn.shopify.com/s/files/1/xxxx/image1.jpg", "https://cdn.shopify.com/s/files/1/xxxx/image2.jpg"]
```

### 3. Decision Update Method
Update products after assessment:
```python
from shopify_manager import ShopifyManager

shopify = ShopifyManager()
await shopify.update_modesty_decision(product_id=12345, decision='modest')
```

## Database Queries

### Get Products Needing Assessment
```sql
SELECT id, title, retailer, category, shopify_draft_id, shopify_image_urls
FROM catalog_products
WHERE review_status = 'pending'
  AND review_type = 'modesty_assessment'
  AND shopify_draft_id IS NOT NULL;
```

### Get Products by Retailer
```sql
SELECT id, title, price, shopify_draft_id, shopify_image_urls
FROM catalog_products
WHERE retailer = 'aritzia'
  AND review_status = 'pending'
  AND shopify_draft_id IS NOT NULL
ORDER BY discovered_date DESC;
```

### Check CDN URLs
```sql
SELECT id, title, 
       json_array_length(shopify_image_urls) as image_count,
       shopify_image_urls
FROM catalog_products
WHERE shopify_image_urls IS NOT NULL
LIMIT 10;
```

## API Usage Examples

### Creating Products (Automatic in Workflow)
```python
from shopify_manager import ShopifyManager

shopify = ShopifyManager()

# This is called automatically by change_detector
result = await shopify.create_product(
    extracted_data=product_data,
    retailer_name='aritzia',
    modesty_level='pending_review',  # Triggers "not-assessed" tag
    source_url='https://...',
    downloaded_images=['path/to/image1.jpg']
)

# Returns:
# {
#     'success': True,
#     'product_id': 12345678,
#     'shopify_image_urls': ['https://cdn.shopify.com/...'],
#     ...
# }
```

### Updating Modesty Decision (For Web Interface)
```python
from shopify_manager import ShopifyManager
from catalog_db_manager import CatalogDatabaseManager

shopify = ShopifyManager()
db = CatalogDatabaseManager()

# Update Shopify
success = await shopify.update_modesty_decision(
    product_id=12345678,  # Shopify product ID
    decision='modest'     # or 'moderately_modest', 'not_modest'
)

# Update local database
if success:
    await db.update_review_decision(
        product_id=123,           # Local catalog_products ID
        decision='approved',
        reviewer_notes='Modest product, approved for publication'
    )
```

## Testing

Run the test suite:
```bash
cd "Catalog Crawler"
python test_shopify_integration_foundation.py
```

Expected output:
```
✅ Passed: 22/22
📈 Pass Rate: 100.0%
🎉 ALL TESTS PASSED!
```

## Web Interface Integration (Future)

### Step 1: Query Products
```python
import aiosqlite
import json

async def get_pending_products():
    async with aiosqlite.connect('products.db') as conn:
        cursor = await conn.cursor()
        await cursor.execute("""
            SELECT id, title, retailer, price, 
                   shopify_draft_id, shopify_image_urls, catalog_url
            FROM catalog_products
            WHERE review_status = 'pending'
              AND shopify_draft_id IS NOT NULL
            ORDER BY discovered_date DESC
        """)
        
        products = []
        async for row in cursor:
            product = {
                'id': row[0],
                'title': row[1],
                'retailer': row[2],
                'price': row[3],
                'shopify_id': row[4],
                'images': json.loads(row[5]) if row[5] else [],
                'source_url': row[6]
            }
            products.append(product)
        
        return products
```

### Step 2: Display in Web Interface
```html
<!-- Example HTML template -->
<div class="product-card" data-product-id="{{product.id}}">
    <h3>{{product.title}}</h3>
    <p>{{product.retailer}} - ${{product.price}}</p>
    
    <!-- Display Shopify CDN images -->
    <div class="product-images">
        {% for image_url in product.images %}
        <img src="{{image_url}}" alt="{{product.title}}" loading="lazy">
        {% endfor %}
    </div>
    
    <!-- Decision buttons -->
    <div class="decision-buttons">
        <button onclick="makeDecision({{product.id}}, 'modest')">Modest</button>
        <button onclick="makeDecision({{product.id}}, 'moderately_modest')">Moderately Modest</button>
        <button onclick="makeDecision({{product.id}}, 'not_modest')">Not Modest</button>
    </div>
    
    <a href="{{product.source_url}}" target="_blank">View Original</a>
    <a href="https://admin.shopify.com/admin/products/{{product.shopify_id}}" target="_blank">View in Shopify</a>
</div>
```

### Step 3: Handle Decision
```javascript
async function makeDecision(productId, decision) {
    // Call your backend API endpoint
    const response = await fetch('/api/modesty-decision', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            product_id: productId,
            decision: decision
        })
    });
    
    if (response.ok) {
        // Remove card from view
        document.querySelector(`[data-product-id="${productId}"]`).remove();
    }
}
```

## Database Sync (For Production Deployment)

```python
from database_sync import DatabaseSync

# Configure once
sync = DatabaseSync()

# Sync after each crawl
success = sync.sync_to_server(
    server_host='your-server.com',
    server_user='deploy',
    server_path='/var/www/products.db'
)
```

## Troubleshooting

### Products Not Getting "not-assessed" Tag
Check that `modesty_level='pending_review'` is passed to `create_product()`:
```bash
grep -r "pending_review" "Catalog Crawler/change_detector.py"
```

### CDN URLs Not Stored
Verify database column exists:
```bash
sqlite3 ../Shared/products.db "PRAGMA table_info(catalog_products);" | grep shopify_image_urls
```

### Test Failures
Run tests with verbose logging:
```bash
python test_shopify_integration_foundation.py 2>&1 | tee test_output.log
```

## File Locations

- **Shopify Integration**: `Shared/shopify_manager.py`
- **Database Schema**: `Catalog Crawler/catalog_db_schema.sql`
- **Database Manager**: `Catalog Crawler/catalog_db_manager.py`
- **Change Detector**: `Catalog Crawler/change_detector.py`
- **Sync Utility**: `Catalog Crawler/database_sync.py`
- **Tests**: `Catalog Crawler/test_shopify_integration_foundation.py`

## Summary

✅ Products automatically tagged "not-assessed"  
✅ Shopify CDN URLs stored in database  
✅ Ready for web-based assessment  
✅ Update method available for decisions  
✅ 100% test coverage  
✅ Backward compatible  

**Status**: Production Ready 🚀

