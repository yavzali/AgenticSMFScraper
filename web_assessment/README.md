# Assessment Database Diagnostic and Fix System

Comprehensive tools to diagnose and fix database connectivity issues for the web assessment interface on DigitalOcean servers.

## 📁 Files Created

- `debug_db.php` - Web-based diagnostic script
- `../upload_diagnostic.py` - Uploads diagnostic script to server  
- `../fix_assessment_db.py` - Comprehensive auto-fix script

## 🚀 Quick Start

### Step 1: Upload Diagnostic Script

```bash
python3 upload_diagnostic.py --host 167.172.148.145 --username root --password modestyassessor
```

### Step 2: Run Web Diagnostic

Visit: `http://167.172.148.145/web_assessment/debug_db.php`

Look for any red ERROR messages in the output.

### Step 3: Auto-Fix Issues

```bash
python3 fix_assessment_db.py --host 167.172.148.145 --username root --password modestyassessor
```

## 🔍 What the Diagnostic Tests

The `debug_db.php` script tests:

1. **File Paths** - Checks multiple possible database locations
2. **Permissions** - Tests file/directory read/write access
3. **PHP Extensions** - Verifies SQLite PDO modules are loaded
4. **Security Restrictions** - Checks for `open_basedir` limitations
5. **Connection Tests** - Attempts actual PDO database connections
6. **Process User** - Shows which user PHP runs as

## 🔧 What the Auto-Fix Does

The `fix_assessment_db.py` script:

1. **Uploads Database** - Transfers `Shared/products.db` if missing
2. **Fixes Permissions** - Sets correct ownership (`www-data:www-data`)
3. **Installs Extensions** - Adds missing PHP SQLite modules
4. **Updates Config** - Sets absolute path in `config.php`  
5. **Creates Security** - Adds `.htaccess` protection
6. **Tests Connection** - Verifies PHP can connect to database

## 📋 Expected Directory Structure

After running the fix, your server should have:

```
/var/www/html/web_assessment/
├── data/
│   ├── products.db          # Main database (4.3MB)
│   └── .htaccess           # Security protection
├── api/
│   └── config.php          # Database configuration
├── debug_db.php            # Diagnostic script
└── assess.php              # Main assessment interface
```

## 🛠️ Manual Troubleshooting

If the auto-fix doesn't work, run these commands manually on your server:

### Check Database Exists
```bash
ls -la /var/www/html/web_assessment/data/products.db
```

### Fix Permissions  
```bash
sudo chown www-data:www-data /var/www/html/web_assessment/data/products.db
sudo chmod 644 /var/www/html/web_assessment/data/products.db
sudo chown www-data:www-data /var/www/html/web_assessment/data/
sudo chmod 755 /var/www/html/web_assessment/data/
```

### Test PHP Connection
```bash
php -r "
try {
    \$pdo = new PDO('sqlite:/var/www/html/web_assessment/data/products.db');
    echo 'SUCCESS: Database connection works!';
} catch (PDOException \$e) {
    echo 'FAILED: ' . \$e->getMessage();
}
"
```

### Install Missing PHP Extensions (Ubuntu/Debian)
```bash
sudo apt-get update
sudo apt-get install -y php-sqlite3 php-pdo-sqlite
sudo systemctl reload apache2
```

## 🔒 Security Notes

- Database files are protected by `.htaccess`
- Only `www-data` user has access to database
- Diagnostic script shows system information (remove after use)

## 📊 Database Contents

The `products.db` contains these tables:
- `products` - Main product data
- `assessment_queue` - Items awaiting modesty assessment  
- `catalog_products` - Catalog monitoring data
- `catalog_baselines` - Baseline snapshots
- `catalog_monitoring_runs` - Run history
- `catalog_errors` - Error logs
- `retailer_stability_tracking` - Stability metrics

## 🌐 Testing Your Fix

After running the auto-fix:

1. Visit: `http://your-server/web_assessment/assess.php`
2. You should see products ready for assessment
3. No database connection errors should appear

## 🆘 Common Issues

### "Database file not found"
- Run `fix_assessment_db.py` to upload database

### "Permission denied"  
- Run permission fixes in the auto-fix script

### "PDO SQLite not available"
- Install PHP SQLite extensions (script does this automatically)

### "No such file or directory in config.php"
- Script creates/updates config.php with absolute path

## 📞 Support

If issues persist after running the auto-fix:

1. Re-run the diagnostic: `debug_db.php`
2. Check the auto-fix summary output
3. Try manual commands listed above
4. Verify web server is running: `sudo systemctl status apache2`

Your assessment interface should be working after following these steps! 🎉
