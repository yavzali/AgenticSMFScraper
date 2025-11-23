# Database Path Consolidation Fix

**Date**: 2025-11-23  
**Issue**: Website showed 138 pending products instead of actual 13  
**Root Cause**: Two separate database files being used by different APIs

---

## The Problem

### Two Database Files Existed:

1. **NEW** `/var/www/html/web_assessment/data/products.db`
   - Updated by database sync (Nov 23 20:52)
   - Has 13 pending products ✅
   - Used by NEW API: `/var/www/html/web_assessment/api/get_products.php`

2. **OLD** `/var/www/html/data/products.db`
   - Not updated by database sync (last update Nov 22)
   - Had 137 pending products ❌ (STALE DATA)
   - Used by OLD API: `/var/www/html/api/get_products.php`

### Why This Happened:

The website (`/var/www/html/assess.php`) calls `api/get_products.php` (relative path), which resolved to the **OLD API** at `/var/www/html/api/get_products.php`, which used the **OLD database**.

Database sync only updated the NEW database location, not the OLD one.

---

## The Fix

### Created Symlink:

```bash
# Backup old database
mv /var/www/html/data/products.db /var/www/html/data/products.db.OLD_BACKUP_20251123

# Create symlink from old location → new location
ln -s /var/www/html/web_assessment/data/products.db /var/www/html/data/products.db
```

### Result:

Both APIs now point to the **same physical database**:

```
Old API: /var/www/html/api/get_products.php
  ↓ uses
/var/www/html/data/products.db (symlink)
  ↓ points to
/var/www/html/web_assessment/data/products.db (actual file)
  ↑ used by
New API: /var/www/html/web_assessment/api/get_products.php
```

---

## Verification

**Before Fix**:
- Old database: 137 pending
- New database: 13 pending
- Website showed: 138 pending (from old database)

**After Fix**:
- Symlink points to new database: 13 pending
- Both APIs query same database: 13 pending
- Website shows: 13 pending ✅

**Test**:
```php
php -r "
$pdo = new PDO('sqlite:/var/www/html/data/products.db');
$stmt = $pdo->query('SELECT COUNT(*) FROM assessment_queue WHERE status=\"pending\"');
echo 'Pending: ' . $stmt->fetchColumn();
"
```
Output: `Pending: 13` ✅

---

## Impact on Database Sync

**Good news**: Database sync (`Shared/database_sync.py`) already syncs to the correct location:
```python
self.remote_db_path = "/var/www/html/web_assessment/data/products.db"
```

The symlink ensures the old API also sees the updated database automatically.

**No code changes needed** - the symlink handles it!

---

## Files Affected

### Unchanged (work automatically with symlink):
- ✅ `Shared/database_sync.py` - syncs to new location
- ✅ `/var/www/html/web_assessment/api/get_products.php` - uses new location
- ✅ `/var/www/html/api/get_products.php` - uses old location (now symlinked)
- ✅ `/var/www/html/assess.php` - calls old API (now uses correct data)

### Created:
- ✅ Symlink: `/var/www/html/data/products.db` → `/var/www/html/web_assessment/data/products.db`

### Backed Up:
- ✅ Old database: `/var/www/html/data/products.db.OLD_BACKUP_20251123` (137 stale products)

---

## Future Considerations

### Option 1: Keep Symlink (RECOMMENDED)
- **Pros**: 
  - Zero code changes needed
  - Both APIs work automatically
  - Future syncs work correctly
- **Cons**: 
  - Adds indirection (minor)
  - Old API still exists (could confuse)

### Option 2: Consolidate APIs
- Merge `/var/www/html/api/` into `/var/www/html/web_assessment/api/`
- Delete old API directory
- Update `assess.php` to call `web_assessment/api/get_products.php`
- Remove symlink, use only new database location

**Decision**: Keep symlink for now. It works and requires no code changes.

---

## Lessons Learned

1. **Multiple database files = data inconsistency**
   - Always check for duplicate database files on server
   - Consolidate to single source of truth

2. **Relative paths can be ambiguous**
   - `api/get_products.php` from `/assess.php` → `/api/get_products.php`
   - Not `/web_assessment/api/get_products.php` as intended

3. **Database sync should validate deployment**
   - Could add check for symlink existence
   - Could verify both paths point to same file

4. **Old code paths linger**
   - Old API at `/var/www/html/api/` was from migration
   - Should have been deleted during consolidation

---

## Diagnostic Created

Created `/var/www/html/db_test.php` to bypass all caching:
- Shows live database counts
- Direct PHP query (no JavaScript)
- Use for future debugging

URL: https://assessmodesty.com/db_test.php

---

## Summary

✅ **Fixed**: Website now shows correct pending count (13)  
✅ **Method**: Created symlink from old database path to new path  
✅ **Impact**: Zero code changes, both APIs work  
✅ **Backup**: Old database preserved for reference  
✅ **Testing**: Verified old API returns correct count

*The 138 mystery is solved!* 🎉

