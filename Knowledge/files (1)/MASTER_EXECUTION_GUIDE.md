# MASTER EXECUTION GUIDE - PRODUCT LIFECYCLE IMPLEMENTATION

**Created**: November 23, 2025  
**System**: Agent Modest E-commerce Scraper  
**Status**: Ready for execution

---

## 📋 OVERVIEW

This implementation adds comprehensive product lifecycle management, cross-table linking, URL stability tracking, and price change detection to your scraping system.

**Total Time**: 2-3 hours (6 phases)  
**Risk Level**: LOW to MEDIUM (phased approach minimizes risk)  
**Production Impact**: Minimal (changes are additive, not destructive)

---

## 🎯 WHAT THIS IMPLEMENTS

1. **Cross-Table Linking**: Links catalog_products ↔ products table
2. **URL Stability Tracking**: Learns which retailers have stable URLs (Anthropologie) vs unstable (Revolve)
3. **Lifecycle Management**: Tracks products through 7 stages from detection → assessment → publication
4. **Price Change Detection**: Automatically flags products when catalog prices change
5. **Historical Snapshots**: Every catalog monitor run saves complete snapshot
6. **Image Consistency**: Tracks which retailers have matching catalog/product images
7. **Auto-Learning System**: Automatically adjusts deduplication strategy per retailer

---

## 📊 THE 6 PHASES

| Phase | What It Does | Time | Risk | Can Stop? |
|-------|--------------|------|------|-----------|
| **1** | Add database columns/tables | 10 min | LOW | ✅ Yes |
| **2** | Update db_manager.py foundation | 15 min | LOW | ✅ Yes |
| **3** | Update baseline scanner | 20 min | LOW | ✅ Yes |
| **4** | Update catalog monitor (complex) | 40 min | MEDIUM | ✅ Yes |
| **5** | Update assessment & importer | 25 min | LOW | ✅ Yes |
| **6** | Backfill existing data | 30 min | LOW | ✅ Yes |

**Total**: 2-2.5 hours

---

## ⚡ EXECUTION INSTRUCTIONS

### IMPORTANT: Complete Each Phase Before Moving to Next

Each phase has:
- ✅ Clear prerequisites
- ✅ Exact changes needed
- ✅ Verification steps
- ✅ Success criteria
- ✅ What to show you

**DO NOT skip phases or combine them.**

---

## 📁 FILES PROVIDED

You have 7 files in `/mnt/user-data/outputs/`:

1. `CURSOR_PROMPT_COMPLETE_IMPLEMENTATION.md` - Original comprehensive prompt (reference only)
2. `PHASE_1_SCHEMA.md` - Database changes
3. `PHASE_2_DB_MANAGER.md` - Foundation updates
4. `PHASE_3_BASELINE_SCANNER.md` - Simpler workflow first
5. `PHASE_4_CATALOG_MONITOR.md` - Complex workflow
6. `PHASE_5_ASSESSMENT_IMPORTER.md` - Independent changes
7. `PHASE_6_BACKFILL.md` - Analyze existing data

---

## 🚀 HOW TO EXECUTE

### Step 1: Add Reference Document

```bash
# Copy the comprehensive prompt to your system
cp /path/to/CURSOR_PROMPT_COMPLETE_IMPLEMENTATION.md \
   "/Users/yav/Agent Modest Scraper System/Knowledge/"
```

This gives Cursor context if it needs to reference the complete design.

---

### Step 2: Execute Phase 1

**Open**: `PHASE_1_SCHEMA.md`  
**Copy entire contents to Cursor**

**What Cursor will do**:
- Run SQL statements on products.db
- Add 8 columns to catalog_products
- Add 6 columns to products
- Create 2 new tables
- Run verification queries

**What you should see**:
- ✅ All ALTER TABLE successful
- ✅ Both tables created
- ✅ Verification queries show new columns
- ✅ Existing data counts unchanged

**If successful**: Proceed to Phase 2  
**If errors**: Fix errors, don't proceed

---

### Step 3: Execute Phase 2

**Open**: `PHASE_2_DB_MANAGER.md`  
**Copy entire contents to Cursor**

**What Cursor will do**:
- Update save_product method (add 5 parameters)
- Update save_catalog_product method (add 2 parameters)
- Create test script
- Run test to verify

**What you should see**:
- ✅ Methods updated without syntax errors
- ✅ Test script passes
- ✅ Data saves with new fields

**If successful**: Commit and proceed to Phase 3  
**If errors**: Fix errors, don't proceed

---

### Step 4: Execute Phase 3

**Open**: `PHASE_3_BASELINE_SCANNER.md`  
**Copy entire contents to Cursor**

**What Cursor will do**:
- Modify catalog_baseline_scanner.py
- Add scan_type, image_url_source parameters
- Add image verification logging
- Run test on Revolve

**What you should see**:
- ✅ Test baseline scan completes
- ✅ scan_type='baseline' in database
- ✅ Image extraction working (>80%)

**If successful**: Commit and proceed to Phase 4  
**If errors**: Fix errors, don't proceed

---

### Step 5: Execute Phase 4 (CAREFUL - Most Complex)

**Open**: `PHASE_4_CATALOG_MONITOR.md`  
**Copy entire contents to Cursor**

**What Cursor will do**:
- Add 3 new methods to catalog_monitor.py
- Modify monitor_catalog method
- Modify product creation code
- Run test on Revolve

**What you should see**:
- ✅ Snapshot saved with scan_type='monitor'
- ✅ Price changes detected (if any)
- ✅ New products have lifecycle_stage
- ✅ No errors during execution

**This is the critical phase - review carefully before proceeding**

**If successful**: Commit and proceed to Phase 5  
**If errors**: Fix errors, DON'T proceed

---

### Step 6: Execute Phase 5

**Open**: `PHASE_5_ASSESSMENT_IMPORTER.md`  
**Copy entire contents to Cursor**

**What Cursor will do**:
- Modify submit_review.php (assessment interface)
- Modify new_product_importer.py
- Create test cases
- Run tests

**What you should see**:
- ✅ Assessment updates lifecycle_stage correctly
- ✅ Import sets lifecycle_stage='imported_direct'
- ✅ No PHP or Python errors

**If successful**: Commit and proceed to Phase 6  
**If errors**: Fix errors, don't proceed

---

### Step 7: Execute Phase 6

**Open**: `PHASE_6_BACKFILL.md`  
**Copy entire contents to Cursor**

**What Cursor will do**:
- Create 3 backfill scripts
- Run all 3 scripts
- Generate reports
- Run verification queries

**What you should see**:
- ✅ 80-95% of catalog products linked
- ✅ Revolve shows low URL stability
- ✅ All products have lifecycle_stage
- ✅ Statistics make sense

**If successful**: Implementation complete! 🎉

---

## ✅ VERIFICATION CHECKLIST

After Phase 6, verify everything works:

```bash
cd "/Users/yav/Agent Modest Scraper System"

# Test 1: Baseline scan
python3 -m Workflows.catalog_baseline_scanner mango dresses modest

# Test 2: Monitor scan
python3 -m Workflows.catalog_monitor mango dresses modest --max-pages 1

# Test 3: Check database
sqlite3 Shared/products.db << EOF
SELECT 'Scan Types:' as metric, scan_type, COUNT(*) 
FROM catalog_products 
GROUP BY scan_type;

SELECT 'Lifecycle Stages:' as metric, lifecycle_stage, COUNT(*) 
FROM products 
WHERE lifecycle_stage IS NOT NULL 
GROUP BY lifecycle_stage;

SELECT 'URL Stability:' as metric, retailer, url_stability_score 
FROM retailer_url_patterns 
ORDER BY url_stability_score ASC 
LIMIT 5;
EOF
```

**Expected Results**:
- Scan types: 'baseline' and 'monitor' both present
- Lifecycle stages: All 4-5 stages represented
- URL stability: Revolve shows <0.50, others >0.80

---

## 🔄 IF SOMETHING BREAKS

### Rollback Strategy

**Phase 1-2**: Easy - just revert schema changes
```bash
# Backup database first
cp Shared/products.db Shared/products.db.backup

# Then can DROP columns if needed
```

**Phase 3-5**: Easy - git revert files
```bash
git log --oneline  # Find commit
git revert <commit-hash>
```

**Phase 6**: Easy - just re-run scripts
```bash
# Backfill scripts are idempotent
# Can run multiple times safely
```

---

## 📊 EXPECTED OUTCOMES

After complete implementation:

### Database
- ✅ 14 new columns across 2 tables
- ✅ 2 new tables (retailer_url_patterns, product_update_queue)
- ✅ All existing data preserved
- ✅ 80-95% cross-table linking

### Workflows
- ✅ Catalog monitor saves snapshots every run
- ✅ Price changes automatically detected
- ✅ New products have lifecycle_stage
- ✅ Assessment updates lifecycle correctly

### Learning System
- ✅ Revolve identified as unstable (<0.50 stability)
- ✅ System automatically uses fuzzy matching for Revolve
- ✅ Other retailers use URL matching when stable
- ✅ Can track changes over time

### Querying
- ✅ Can see product lifecycle at any point
- ✅ Can track products across tables
- ✅ Can identify price changes
- ✅ Can view historical catalog snapshots

---

## 💾 GIT COMMITS

After each phase:
```bash
git add <modified_files>
git commit -m "Phase X: <description>"
git push origin main
```

**Commit messages**:
- Phase 1: "Add lifecycle tracking schema"
- Phase 2: "Update db_manager for lifecycle tracking"
- Phase 3: "Update baseline scanner for lifecycle tracking"
- Phase 4: "Update catalog monitor for lifecycle tracking and snapshots"
- Phase 5: "Update assessment and importer for lifecycle tracking"
- Phase 6: "Add backfill scripts for lifecycle system"

---

## 📞 SUPPORT

### If You Get Stuck

**Check**:
1. Did previous phase complete successfully?
2. Are verification queries passing?
3. Any errors in terminal output?
4. Check git status - what files changed?

**Common Issues**:
- "Column not found" → Phase 1 not completed
- "Method not found" → Phase 2 not completed
- Syntax errors → Copy/paste error, check file

---

## 🎯 FINAL NOTES

1. **Take your time**: Each phase is independent, no rush
2. **Verify each phase**: Don't skip verification steps
3. **Commit after each phase**: Easy rollback if needed
4. **Test on small retailers first**: Use Mango or Revolve
5. **Production system**: Changes are additive, existing workflows still work

**This is a well-designed, low-risk implementation. Follow the phases and you'll be fine.**

---

## 📈 POST-IMPLEMENTATION

After successful completion:

1. **Monitor for a week**: Watch workflows, check logs
2. **Review priority queue**: Check price change detections
3. **Verify Revolve**: Confirm fuzzy matching working
4. **Update docs**: Add lifecycle info to SYSTEM_OVERVIEW.md
5. **Celebrate**: You've built a sophisticated learning system! 🎉

---

**Ready to begin? Start with Phase 1!**
