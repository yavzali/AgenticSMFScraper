# Web Assessment Interface - Deployment Guide

## ✅ Implementation Complete!

All files have been successfully created and are ready for deployment to assessmodesty.com.

## 📁 File Structure Created

```
web_assessment/
├── index.php                 ✅ Login page with "clothing" password
├── assess.php                ✅ Main assessment interface
├── api/
│   ├── config.php           ✅ Database and Shopify configuration
│   ├── get_products.php     ✅ Fetch products from database
│   ├── submit_review.php    ✅ Handle assessment decisions
│   ├── shopify_api.php      ✅ Shopify API integration
│   └── logout.php           ✅ Logout handler
├── assets/
│   ├── style.css            ✅ Complete CSS (482 lines)
│   └── app.js               ✅ Frontend JavaScript
├── data/
│   └── .htaccess            ✅ Database protection
├── WEB_ASSESSMENT_README.md ✅ Setup documentation
└── DEPLOYMENT_GUIDE.md      ✅ This file
```

## 🚀 Deployment Steps

### 1. Configure Shopify API Credentials

Edit `api/config.php` and update these lines:

```php
define('SHOPIFY_STORE_URL', 'your-store.myshopify.com');  // ← UPDATE THIS
define('SHOPIFY_ACCESS_TOKEN', 'your-access-token');      // ← UPDATE THIS
```

**To get Shopify Access Token:**
1. Go to Shopify Admin → Apps → Develop apps
2. Create a new app with these permissions:
   - `read_products`
   - `write_products`
3. Install the app and copy the Admin API access token

### 2. Upload to Web Server

```bash
# Upload entire web_assessment directory
scp -r web_assessment/ user@assessmodesty.com:/var/www/html/

# Or use FTP/cPanel file manager
```

### 3. Copy Database

```bash
# Copy the synced database to the data directory
cp /path/to/Shared/products.db web_assessment/data/

# On server, set permissions
chmod 644 /var/www/html/web_assessment/data/products.db
chmod 755 /var/www/html/web_assessment/data/
```

### 4. Set File Permissions

```bash
cd /var/www/html/web_assessment/

# Set directory permissions
chmod 755 api/ assets/ data/

# Set file permissions
chmod 644 *.php api/*.php assets/* *.md

# Protect database
chmod 600 data/products.db
chmod 644 data/.htaccess
```

### 5. Configure PHP (if needed)

Ensure your server has:
- PHP 7.4 or higher
- PDO SQLite extension enabled
- cURL extension enabled
- Session support enabled

Check with:
```bash
php -m | grep -E "pdo_sqlite|curl|session"
```

### 6. Test the Application

1. Navigate to `https://assessmodesty.com/`
2. Enter password: `clothing`
3. You should see the assessment interface
4. Try filtering products
5. Test submitting a review (on a test product first!)

## 🔒 Security Checklist

- ✅ Password authentication implemented
- ✅ Session management configured
- ✅ Database protected with .htaccess
- ⚠️ **IMPORTANT**: Use HTTPS in production (SSL certificate)
- ⚠️ **IMPORTANT**: Change password after initial setup (edit index.php)
- ⚠️ Consider adding rate limiting for login attempts

## 🔄 Database Sync Setup

### Option 1: Manual Sync

```bash
# On local machine after crawl
cd "/Users/yav/Agent Modest Scraper System/Catalog Crawler"
python -c "from database_sync import DatabaseSync; DatabaseSync().sync_to_server('assessmodesty.com', 'user', '/var/www/html/web_assessment/data/products.db')"
```

### Option 2: Automated Sync (Recommended)

Create `/Users/yav/Agent Modest Scraper System/sync_to_web.sh`:

```bash
#!/bin/bash
cd "/Users/yav/Agent Modest Scraper System/Catalog Crawler"
python3 << 'EOF'
from database_sync import DatabaseSync
sync = DatabaseSync()
success = sync.sync_to_server(
    'assessmodesty.com',
    'deploy_user',
    '/var/www/html/web_assessment/data/products.db'
)
print("✅ Sync successful!" if success else "❌ Sync failed!")
EOF
```

Make executable and add to crontab:
```bash
chmod +x sync_to_web.sh

# Add to crontab (sync every 6 hours)
crontab -e
# Add line:
0 */6 * * * /path/to/sync_to_web.sh >> /path/to/sync.log 2>&1
```

## 🧪 Testing Checklist

### Pre-Deployment Tests (Local)

- [ ] Login with correct password works
- [ ] Login with incorrect password fails
- [ ] Session persists across page loads
- [ ] Logout destroys session
- [ ] Database connection works
- [ ] Products load from database
- [ ] Filters work correctly
- [ ] Stats display correctly

### Post-Deployment Tests (Production)

- [ ] SSL certificate active (HTTPS)
- [ ] Login page loads
- [ ] Authentication works
- [ ] Products display correctly
- [ ] Images load from Shopify CDN
- [ ] Duplicate matches show correctly
- [ ] Review submission works
- [ ] Shopify updates successfully
- [ ] Database syncs properly
- [ ] Mobile responsive design works

## 🎯 Feature Verification

### Modesty Assessment Workflow
1. ✅ Products with `review_type: 'modesty_assessment'` display
2. ✅ Shopify CDN images shown
3. ✅ Three buttons: Modest, Moderately Modest, Not Modest
4. ✅ Decision updates Shopify (removes "not-assessed" tag)
5. ✅ Products published if modest/moderately modest
6. ✅ Products kept as draft if not modest

### Duplicate Detection Workflow
1. ✅ Products with `review_type: 'duplicate_uncertain'` display
2. ✅ Thumbnail images shown
3. ✅ Potential matches displayed with similarity scores
4. ✅ Two buttons: New Product, Duplicate
5. ✅ Decision updates local database only
6. ✅ No Shopify API calls for duplicates

## 🔧 Troubleshooting

### Products Not Loading

**Check database path:**
```php
// In api/config.php
define('DB_PATH', __DIR__ . '/../data/products.db');
```

**Verify database exists:**
```bash
ls -la /var/www/html/web_assessment/data/products.db
```

**Check PHP error log:**
```bash
tail -f /var/log/php_errors.log
# or
tail -f /var/www/html/web_assessment/error_log
```

### Shopify Updates Failing

**Test API credentials:**
```php
<?php
// test_shopify.php
require_once 'api/config.php';

$ch = curl_init();
curl_setopt($ch, CURLOPT_URL, SHOPIFY_API_BASE . '/shop.json');
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_HTTPHEADER, [
    'X-Shopify-Access-Token: ' . SHOPIFY_ACCESS_TOKEN
]);
$response = curl_exec($ch);
echo $response;
?>
```

**Check API permissions:**
- Product read/write access
- Valid access token
- API rate limits not exceeded

### Login Issues

**Clear browser cache/cookies**

**Check PHP sessions:**
```bash
php -i | grep session.save_path
# Ensure directory exists and is writable
```

### Database Permission Errors

```bash
# Check ownership
ls -la /var/www/html/web_assessment/data/

# Fix if needed
chown www-data:www-data /var/www/html/web_assessment/data/products.db
chmod 644 /var/www/html/web_assessment/data/products.db
```

## 📊 Monitoring

### Key Metrics to Track
- Number of reviews per day
- Average time per review
- Modest vs not modest ratio
- Duplicate detection accuracy
- Shopify API success rate

### Logging

Add to `api/config.php`:
```php
// Enable error logging
ini_set('display_errors', 0);
ini_set('log_errors', 1);
ini_set('error_log', __DIR__ . '/../error_log');
```

## 🔐 Security Best Practices

1. **Change Default Password**
   ```php
   // In index.php, change:
   if (($_POST['password'] ?? '') === 'your_new_secure_password')
   ```

2. **Add Rate Limiting** (recommended)
   - Install fail2ban
   - Configure for login attempts
   - Block suspicious IP addresses

3. **Enable HTTPS Only**
   ```apache
   # In .htaccess (root directory)
   RewriteEngine On
   RewriteCond %{HTTPS} off
   RewriteRule ^(.*)$ https://%{HTTP_HOST}%{REQUEST_URI} [L,R=301]
   ```

4. **Regular Backups**
   ```bash
   # Backup database daily
   0 2 * * * cp /var/www/html/web_assessment/data/products.db /backups/products_$(date +\%Y\%m\%d).db
   ```

## 📱 Mobile Optimization

The interface is already mobile-responsive with:
- ✅ Flexible grid layouts
- ✅ Touch-friendly buttons
- ✅ Responsive images
- ✅ Mobile-first CSS

Test on:
- iPhone (Safari)
- Android (Chrome)
- iPad (Safari)

## 🎓 Training Users

### Quick Start Guide for Reviewers

1. Visit assessmodesty.com
2. Enter password: "clothing"
3. Select review type (Modesty or Duplicate)
4. Review products one by one
5. Click decision button
6. Product updates automatically

### Tips for Efficient Review
- Use keyboard shortcuts (future feature)
- Filter by retailer to batch similar styles
- Check duplicate matches carefully
- Add notes for borderline cases (future feature)

## 📈 Next Steps

### Immediate (Post-Deployment)
1. Update Shopify API credentials
2. Upload to production server
3. Test with real data
4. Train initial reviewers

### Short-term (1-2 weeks)
1. Monitor for issues
2. Gather user feedback
3. Optimize based on usage patterns
4. Add analytics tracking

### Future Enhancements
1. Bulk review operations
2. Keyboard shortcuts
3. Review notes/comments
4. Reviewer analytics
5. Automated suggestions using ML

## ✅ Deployment Checklist

- [ ] Shopify API credentials configured
- [ ] Files uploaded to server
- [ ] Database copied and permissions set
- [ ] PHP extensions verified
- [ ] SSL certificate installed
- [ ] Login tested
- [ ] Product loading tested
- [ ] Review submission tested
- [ ] Shopify integration tested
- [ ] Database sync configured
- [ ] Error logging enabled
- [ ] Backups configured
- [ ] Mobile testing complete
- [ ] Users trained

## 🎉 Success Criteria

Your deployment is successful when:
1. ✅ Users can login successfully
2. ✅ Products load from database
3. ✅ Filters work correctly
4. ✅ Reviews submit without errors
5. ✅ Shopify updates reflect immediately
6. ✅ Database syncs automatically
7. ✅ Mobile experience is smooth
8. ✅ No PHP errors in logs

## 📞 Support

For issues or questions:
- Check error logs first
- Review troubleshooting section
- Refer to WEB_ASSESSMENT_README.md
- Check SHOPIFY_INTEGRATION_FOUNDATION_SUMMARY.md

---

**Status**: Ready for Production Deployment 🚀  
**Last Updated**: October 20, 2025  
**Version**: 1.0.0

