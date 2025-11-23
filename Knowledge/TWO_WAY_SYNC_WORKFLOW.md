# Two-Way Database Sync: Complete Workflow

**Created**: 2025-11-23  
**Status**: ✅ IMPLEMENTED  
**Related**: Phase 1-6 Lifecycle Tracking

---

## Quick Commands (Run Anytime)

### Check Status (Start of Day)
```bash
python3 check_status.py
```
- Compares server vs local databases
- Shows pending reviews on server (from phone)
- Shows new products on local (not yet synced)
- Tells you if sync is needed

### Manual Sync
```bash
python3 sync_now.py
```
- Pulls assessments from server → merges into local
- Pushes local database → uploads to server
- Run this anytime you want to sync

### Automatic Sync (Within Workflows)
- Catalog monitor **automatically syncs** at the end
- Two-way sync (pull then push) happens automatically
- You don't need to run sync separately after catalog monitor

---

## The Scenario: You're on the Train

You're on a train with your phone, no laptop. You open AssessModesty.com and start reviewing products.

---

## PHASE 1: You Assess Products on Phone 📱

**Location**: Train, using phone  
**Time**: 10:30 AM  
**Database**: Server database at `/var/www/html/web_assessment/data/products.db`

### What Happens:

1. **You open AssessModesty.com** on your phone
   - PHP loads products from **server database**
   - Shows 13 products pending review

2. **You review 5 products**:
   - Product A: Approve as "modest" ✅
   - Product B: Approve as "moderately_modest" ✅
   - Product C: Reject as "not_modest" ❌
   - Product D: Approve as "modest" ✅
   - Product E: Reject as "not_modest" ❌

3. **PHP updates SERVER database** (`submit_review.php`):
   ```php
   // For approved products (A, B, D)
   UPDATE products SET
       lifecycle_stage = 'assessed_approved',
       assessed_at = '2025-11-23 10:35:00',
       modesty_status = 'modest',
       shopify_status = 'published'
   WHERE url = ?
   
   // For rejected products (C, E)
   UPDATE products SET
       lifecycle_stage = 'assessed_rejected',
       assessed_at = '2025-11-23 10:36:00',
       modesty_status = 'not_modest',
       shopify_status = 'draft'
   WHERE url = ?
   ```

4. **SERVER database now has**:
   - 5 products with `lifecycle_stage` = 'assessed_approved' or 'assessed_rejected'
   - 5 products with `assessed_at` = '2025-11-23 10:35:00' or '10:36:00'
   - 8 products still pending

---

## PHASE 2: You Close Your Laptop at Home 💤

**Location**: Home  
**Time**: 11:00 AM  
**Database**: Local database at `Shared/products.db`

### Current State:

- **Local database**: Still has 13 products with `lifecycle_stage` = 'pending_assessment'
- **Server database**: Has 5 assessed, 8 pending
- **Your phone assessments are ONLY on server** (not yet synced to laptop)

---

## PHASE 3: You Open Laptop and Run Workflow 🔄

**Location**: Home, you open laptop  
**Time**: 3:00 PM (next day, or whenever)  
**Workflow**: You manually tell Cursor to run `catalog_monitor.py`

**IMPORTANT**: Nothing runs automatically! You control when workflows run.

### What Happens:

**STEP 1: Catalog Monitor Finds New Products**

```python
# catalog_monitor.py runs
monitor = CatalogMonitor()
monitor.run_monitoring()

# Finds 7 new Anthropologie dresses
# Uploads them to Shopify as drafts
# Adds them to assessment_queue with lifecycle_stage='pending_assessment'

logger.info(f"Sent {7} products to modesty review")
```

**STEP 2: Automatic Two-Way Sync Triggered**

```python
# catalog_monitor.py calls database sync
if sent_to_modesty_review > 0:
    logger.info("🔄 Syncing database to web server...")
    await sync_database_async()
```

**STEP 3A: PULL Assessments from Server (NEW!)**

```python
# DatabaseSync.pull_assessments_from_server()

# 1. Download server database to temp file
scp.get('/var/www/html/web_assessment/data/products.db', '/tmp/server.db')

# 2. Query server for assessed products
SELECT url, lifecycle_stage, assessed_at, modesty_status, shopify_status
FROM products
WHERE lifecycle_stage IN ('assessed_approved', 'assessed_rejected')
AND assessed_at IS NOT NULL

# Returns 5 products (A, B, C, D, E from your phone)

# 3. For each server assessment, check local database
for assessment in server_assessments:
    SELECT lifecycle_stage, assessed_at FROM products WHERE url = ?
    
    # Local product is still 'pending_assessment' with NULL assessed_at
    # Server assessment is NEWER
    
    # Update local database
    UPDATE products SET
        lifecycle_stage = 'assessed_approved',  # or 'assessed_rejected'
        assessed_at = '2025-11-23 10:35:00',
        modesty_status = 'modest',
        shopify_status = 'published'
    WHERE url = ?

logger.info(f"✅ Applied 5 assessments to local database")
```

**STEP 3B: PUSH Local Database to Server**

```python
# DatabaseSync.sync_to_server()

# Local database now has:
# - 5 assessed products (from phone) ← MERGED IN
# - 7 new products (from catalog monitor) ← JUST ADDED
# - 8 pending products (unchanged)

# Upload merged database to server
scp.put('Shared/products.db', '/var/www/html/web_assessment/data/products.db')

logger.info(f"✅ Upload complete")
```

---

## PHASE 4: Server Database is Now Complete ✅

**Location**: Server  
**Time**: 3:05 PM  
**Database**: Server database has everything

### Final State:

**Server database now contains**:
- ✅ 5 products assessed on phone (preserved!)
- ✅ 7 new products from catalog monitor (added!)
- ⏳ 8 products still pending (unchanged)

**No data loss!** Both your phone assessments AND the laptop's new products are in the server database.

---

## PHASE 5: You Open AssessModesty.com Again 📱

**Location**: Train home, 5:00 PM  
**Database**: Server database (updated)

### What You See:

```
📊 Assessment Dashboard

Total Pending: 15
- 8 from earlier batch (unchanged)
- 7 new Anthropologie dresses (just added by laptop)

Total Reviewed Today: 5
- Product A (modest) ✅
- Product B (moderately_modest) ✅
- Product C (not_modest) ❌
- Product D (modest) ✅
- Product E (not_modest) ❌
```

**Your phone assessments are still there!** They weren't overwritten.

---

## Why This Works: Lifecycle Tracking

The two-way sync uses the lifecycle tracking fields we added in Phase 1-6:

### Fields Used:

| Field | Purpose | Example Values |
|-------|---------|----------------|
| `lifecycle_stage` | Track product state | `'pending_assessment'`, `'assessed_approved'`, `'assessed_rejected'` |
| `assessed_at` | When human reviewed it | `'2025-11-23 10:35:00'` or `NULL` |
| `last_updated` | Last database modification | `'2025-11-23 15:00:00'` |

### Merge Logic:

```python
# Only update local product if server assessment is newer
should_update = (
    # Local hasn't been assessed yet
    local_lifecycle not in ('assessed_approved', 'assessed_rejected') or
    # Server assessment is newer
    server_assessed_at > local_assessed_at
)

if should_update:
    # Apply server assessment to local database
    UPDATE products SET ...
```

**This prevents**:
- Overwriting phone assessments with stale local data ✅
- Losing laptop's new products ✅
- Creating duplicate entries ✅

---

## Comparison: Before vs After

### ❌ Before Two-Way Sync:

```
1. Phone: Assess 5 products on server database
2. Laptop: Find 7 new products, add to local database
3. Laptop: Upload local database to server (OVERWRITES!)
4. Result: 5 phone assessments LOST ❌
```

### ✅ After Two-Way Sync:

```
1. Phone: Assess 5 products on server database
2. Laptop: Find 7 new products, add to local database
3. Laptop: Pull 5 assessments from server → merge into local
4. Laptop: Upload merged database to server
5. Result: 5 phone assessments + 7 new products = ALL PRESERVED ✅
```

---

## Technical Implementation

### Key Files Modified:

**`Shared/database_sync.py`**:
- Added `pull_assessments_from_server()` method
- Modified `sync_to_server()` to pull first, then push
- Uses `lifecycle_stage` and `assessed_at` for merge logic

**`Workflows/catalog_monitor.py`**:
- Already calls `sync_database_async()` after adding products
- No changes needed (automatically uses new two-way sync)

**`web_assessment/api/submit_review.php`**:
- Already sets `lifecycle_stage` and `assessed_at` on assessment
- No changes needed (Phase 5 implementation)

---

## Manual Testing

To test the two-way sync manually:

```bash
# 1. Make a fake assessment on server (simulate phone)
ssh root@167.172.148.145
sqlite3 /var/www/html/web_assessment/data/products.db
UPDATE products SET
    lifecycle_stage = 'assessed_approved',
    assessed_at = datetime('now'),
    modesty_status = 'modest'
WHERE url = 'https://example.com/test-product';
.exit

# 2. On laptop, run sync
cd ~/Agent\ Modest\ Scraper\ System
python3 Shared/database_sync.py

# Expected output:
# ✅ Applied 1 assessments to local database

# 3. Verify local database has the assessment
sqlite3 Shared/products.db
SELECT lifecycle_stage, assessed_at FROM products 
WHERE url = 'https://example.com/test-product';
# Should show: assessed_approved | 2025-11-23 ...
```

---

## Performance Implications

**Added Operations**:
- Download server database (4.4 MB) → ~2 seconds
- Query for assessments → ~0.1 seconds
- Update local database → ~0.5 seconds
- **Total overhead: ~3 seconds**

**Worth it?**: YES
- Prevents data loss
- Uses existing infrastructure (SSH/SCP)
- Only runs when products are added to queue
- Non-blocking (doesn't stop workflows)

---

## Future Enhancements (Optional)

### 1. Incremental Sync (Performance Optimization)

Instead of downloading entire server database, only pull changed rows:

```python
# Add last_sync_timestamp tracking
last_sync = get_last_sync_timestamp()

# Only pull assessments newer than last sync
SELECT * FROM products
WHERE assessed_at > ?
AND lifecycle_stage IN ('assessed_approved', 'assessed_rejected')
```

**Benefit**: Faster sync (only transfers changed data)  
**Complexity**: Requires timestamp tracking  
**Priority**: LOW (current implementation is fast enough)

### 2. Conflict Resolution (Edge Case)

If both laptop AND phone modify same product:

```python
# Current: Server wins (server_assessed_at > local_assessed_at)
# Alternative: Most recent wins (compare timestamps)
# Alternative: Human review (flag for manual resolution)
```

**Priority**: LOW (unlikely scenario, current behavior is reasonable)

---

## Summary

✅ **Two-way sync is IMPLEMENTED and WORKING**

**What it does**:
1. Pulls assessments from server before pushing
2. Merges server assessments into local database
3. Uploads merged database to server
4. Preserves both phone and laptop changes

**When it runs**:
- Automatically after catalog monitor runs
- Manually via `python3 Shared/database_sync.py`

**What it prevents**:
- Losing phone assessments when laptop syncs
- Data overwriting
- Assessment conflicts

**Built on**:
- Phase 1-6 lifecycle tracking (`lifecycle_stage`, `assessed_at`)
- Existing SSH/SCP infrastructure
- SQLite timestamp comparison

**Performance**: ~3 seconds overhead per sync (acceptable)

---

## Typical Daily Workflow

### Morning: Start of Day
```bash
# 1. Open laptop, open Cursor
# 2. Check status
python3 check_status.py

# Output shows:
#   ⚠️  SERVER HAS 5 MORE ASSESSMENTS
#   (You assessed products on phone yesterday)
#   → Run: python3 sync_now.py

# 3. If sync needed, run it
python3 sync_now.py
```

### During Day: Run Workflows
```bash
# Tell me in Cursor:
# "Run catalog monitor for Revolve dresses"

# I run:
catalog_monitor.py
  → Finds 7 new products
  → Adds to local database
  → Automatically syncs to server (two-way sync)
  → No manual sync needed!
```

### Evening: On Train
```bash
# Open AssessModesty.com on phone
# Review pending products
# Your assessments save to server database
# Will sync next time you run check_status.py or catalog_monitor
```

---

## When to Run What

| Scenario | Command | Why |
|----------|---------|-----|
| Just opened laptop | `python3 check_status.py` | See if phone assessments need syncing |
| Status shows differences | `python3 sync_now.py` | Manually sync before starting work |
| Running catalog monitor | (automatic) | Sync happens automatically at end |
| Need to push local changes | `python3 sync_now.py` | Force sync without running workflow |
| Before closing laptop | (optional) | Ensure server has latest if you assessed locally |

---

*You can now safely assess products on your phone while your laptop is offline. Everything syncs correctly when you run workflows or manual sync!* 🎉

