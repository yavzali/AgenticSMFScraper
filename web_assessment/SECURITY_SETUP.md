# Security Setup for Web Assessment Interface

## 🔒 Credentials Protection

Your Shopify credentials have been secured and will NOT be uploaded to GitHub.

### What Was Done:

1. **✅ Removed credentials from `config.php`**
   - Replaced with placeholder values
   - Added instructions for local development

2. **✅ Created `config.local.php` with your actual credentials**
   - Contains your real Shopify store URL and access token
   - Added to `.gitignore` to prevent accidental commits

3. **✅ Updated `.gitignore`**
   - Added `web_assessment/api/config.local.php` to ignore list
   - Ensures credentials never get committed

### For Local Development:

Use `config.local.php` which contains your actual credentials:
- Store URL: `your-store.myshopify.com`
- Access Token: `your-shopify-access-token`

### For Production Deployment:

1. Copy `config.php` to your server
2. Update with your production credentials:
   ```php
   define('SHOPIFY_STORE_URL', 'your-production-store.myshopify.com');
   define('SHOPIFY_ACCESS_TOKEN', 'your-production-access-token');
   ```

### Security Best Practices:

- ✅ Credentials never committed to GitHub
- ✅ Local development file ignored by git
- ✅ Production credentials stored securely on server
- ✅ Placeholder values in public repository

## 🚀 Ready to Push

You can now safely commit and push to GitHub without exposing your credentials!

**Files to commit:**
- ✅ `config.php` (with placeholder credentials)
- ✅ `.gitignore` (updated to ignore local config)
- ❌ `config.local.php` (ignored by git)

**Your credentials are safe!** 🔒
