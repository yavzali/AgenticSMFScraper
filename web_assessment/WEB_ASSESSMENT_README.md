# Web Assessment Interface - Setup Guide

## Quick Start

This web interface converts the existing `modesty_review_interface.html` into a live web application with database integration and Shopify API connectivity.

## Installation Steps

### 1. Upload Files to Web Server
```bash
# Upload entire web_assessment/ directory to your web server
scp -r web_assessment/ user@assessmodesty.com:/var/www/html/
```

### 2. Configure Database
```bash
# Copy synced database to data directory
cp /path/to/Shared/products.db web_assessment/data/
chmod 644 web_assessment/data/products.db
```

### 3. Configure Shopify API
Edit `api/config.php` and update:
```php
define('SHOPIFY_STORE_URL', 'your-store.myshopify.com');
define('SHOPIFY_ACCESS_TOKEN', 'your-shopify-access-token');
```

### 4. Set Permissions
```bash
cd web_assessment/
chmod 755 api/ assets/ data/
chmod 644 *.php api/*.php assets/*
chmod 600 data/products.db
```

### 5. Access the Interface
1. Navigate to `https://assessmodesty.com/`
2. Enter password: `clothing`
3. Start reviewing products!

## Features

✅ **Password Authentication** - Secure access with "clothing" password  
✅ **Real Database Integration** - Reads from synced SQLite database  
✅ **Shopify API Integration** - Updates products directly in Shopify  
✅ **Mobile-First Design** - Fully responsive interface  
✅ **Separate Workflows** - Modesty assessment vs duplicate detection  
✅ **Image Display** - Uses Shopify CDN URLs for modesty, thumbnails for duplicates  

## File Structure

```
web_assessment/
├── index.php               # Login page
├── assess.php              # Main assessment interface (TO BE CREATED)
├── api/
│   ├── config.php         # Configuration ✅
│   ├── get_products.php   # Fetch products from DB (TO BE CREATED)
│   ├── submit_review.php  # Submit decisions (TO BE CREATED)
│   ├── shopify_api.php    # Shopify integration (TO BE CREATED)
│   └── logout.php         # Logout handler (TO BE CREATED)
├── assets/
│   ├── style.css          # Extracted CSS ✅
│   └── app.js             # Frontend JavaScript (TO BE CREATED)
└── data/
    ├── products.db        # Synced database
    └── .htaccess          # Protection (TO BE CREATED)
```

## Security

1. **Password Protection** - Simple password authentication
2. **Session Management** - PHP sessions for auth
3. **Database Protection** - .htaccess prevents direct access
4. **HTTPS Required** - Use SSL certificate in production

## Database Sync

### Automated Sync (Recommended)
Add to crontab after each crawl:
```bash
0 */6 * * * /path/to/sync_to_web.sh
```

### Manual Sync
```bash
cd /path/to/Agent\ Modest\ Scraper\ System/Catalog\ Crawler/
python -c "from database_sync import DatabaseSync; DatabaseSync().sync_to_server('assessmodesty.com', 'deploy', '/var/www/html/web_assessment/data/products.db')"
```

## API Endpoints

### GET /api/get_products.php
**Parameters:**
- `retailer` - Filter by retailer
- `category` - Filter by category
- `confidence` - Filter by confidence (low/medium/high)
- `review_type` - Filter by review type

**Response:**
```json
{
  "products": [...],
  "stats": {
    "total_pending": 42,
    "approved_today": 5,
    "total_processed": 150,
    "low_confidence": 8
  }
}
```

### POST /api/submit_review.php
**Body:**
```json
{
  "product_id": 123,
  "decision": "modest",
  "notes": "Optional notes"
}
```

**Response:**
```json
{
  "success": true,
  "action": "shopify_updated"
}
```

## Workflow

### Modesty Assessment
1. Product appears with Shopify CDN images
2. Reviewer selects: Modest / Moderately Modest / Not Modest
3. System updates Shopify (removes "not-assessed", adds decision tag)
4. Product published or kept as draft based on decision

### Duplicate Detection
1. Product appears with thumbnail images
2. System shows potential matches with similarity scores
3. Reviewer selects: Duplicate / New Product
4. If duplicate: marked in database
5. If new product: promoted to full scraping (future feature)

## Troubleshooting

### Products Not Loading
- Check database path in `api/config.php`
- Verify database permissions (644)
- Check PHP error logs

### Shopify Updates Failing
- Verify API credentials in `api/config.php`
- Check Shopify access token permissions
- Review PHP error logs for API responses

### Login Not Working
- Clear browser cookies/cache
- Check session handling in PHP
- Verify password is exactly "clothing"

## Next Steps

1. Complete remaining PHP files (assess.php, API endpoints, app.js)
2. Test locally with XAMPP/MAMP
3. Deploy to production server
4. Configure SSL certificate
5. Set up database sync schedule

## Status

**Current Progress:**
- ✅ Directory structure created
- ✅ CSS extracted from HTML
- ✅ Login page created
- ✅ API configuration created
- ⏳ Main interface (assess.php) - IN PROGRESS
- ⏳ API endpoints - PENDING
- ⏳ JavaScript conversion - PENDING

**Remaining Work:**
Due to token limits, the remaining files need to be created:
1. `assess.php` - Convert modesty_review_interface.html to PHP
2. `api/get_products.php` - Database query endpoint
3. `api/submit_review.php` - Decision submission
4. `api/shopify_api.php` - Shopify integration
5. `api/logout.php` - Logout handler
6. `assets/app.js` - Frontend JavaScript
7. `data/.htaccess` - Database protection

## References

- Original Interface: `Catalog Crawler/modesty_review_interface.html`
- Database Schema: `Catalog Crawler/catalog_db_schema.sql`
- Shopify Integration: `Shared/shopify_manager.py`

## Support

For issues or questions, refer to:
- `SHOPIFY_INTEGRATION_FOUNDATION_SUMMARY.md`
- `ENHANCED_DUPLICATE_DISPLAY_SUMMARY.md`

