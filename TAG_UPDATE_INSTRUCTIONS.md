# Tag Update Instructions - Quick Reference

## 🎯 Overview

**What happened:** Tags were lowercase (`"modest", "revolve"`)  
**What's fixed:** Tags are now title case (`"Modest", "Revolve"`)  
**What to do now:** Update existing products and import remaining products

---

## 📋 Step-by-Step Guide

### Step 1: Preview Tag Updates (Dry Run)

**Preview what will change without making any changes:**

```bash
cd "/Users/yav/Agent Modest Scraper System/Shared"
python update_product_tags.py --dry-run
```

This will show you:
- How many products need updating
- First 10 examples of old → new tags
- No changes are made in dry-run mode

---

### Step 2: Apply Tag Updates to Existing Products

**Once you're happy with the preview, apply the changes:**

```bash
cd "/Users/yav/Agent Modest Scraper System/Shared"
python update_product_tags.py
```

This will:
- ✅ Update all existing products with correct title case tags
- ✅ Remove old lowercase tags
- ✅ Add new title case tags
- ✅ Save detailed results to JSON file
- ⏱️ Takes ~0.5 seconds per product (respects rate limits)

**Example output:**
```
✅ Updated: Willem Maxi Dress
   Old tags: modest, revolve, auto-scraped, dress
   New tags: Modest, Revolve, Auto-Scraped, Dress
```

---

### Step 3: Resume Product Imports with Correct Tags

**Import the remaining Revolve products:**

```bash
cd "/Users/yav/Agent Modest Scraper System/New Product Importer"

# Batch 1: Modest Dresses (50 URLs)
python new_product_importer.py \
  --batch-file "../Baseline URLs/batch_modest_dresses.json" \
  --modesty-level modest \
  --force-run-now

# Batch 2: Modest Dress Tops (35 URLs)
python new_product_importer.py \
  --batch-file "../Baseline URLs/batch_modest_dress_tops.json" \
  --modesty-level modest \
  --force-run-now

# Batch 3: Moderately Modest Dresses (23 URLs)
python new_product_importer.py \
  --batch-file "../Baseline URLs/batch_moderately_modest_dresses.json" \
  --modesty-level moderately_modest \
  --force-run-now

# Batch 4: Moderately Modest Dress Tops (17 URLs)
python new_product_importer.py \
  --batch-file "../Baseline URLs/batch_moderately_modest_dress_tops.json" \
  --modesty-level moderately_modest \
  --force-run-now
```

**All new imports will automatically use title case tags!**

---

## 🔍 Verification

### Verify in Shopify Admin

1. Go to your Shopify admin
2. Navigate to Products
3. Click any recently imported product
4. Check the Tags field - should show:
   - ✅ `Modest, Revolve, Auto-Scraped, Dress Top`
   - ❌ NOT `modest, revolve, auto-scraped, dress top`

### Verify Tag-Based Filters

Test your Shopify collections and filters:
1. Filter by tag `Modest` (title case)
2. Filter by tag `Revolve` (title case)
3. Should work correctly now

---

## ⚠️ Important Notes

1. **The update script is safe:**
   - Only updates tags (no other product data)
   - Can be run multiple times (idempotent)
   - Respects Shopify API rate limits

2. **New imports use correct tags automatically:**
   - No need to manually fix future imports
   - Code is updated permanently

3. **If you prefer to delete and re-import:**
   - You can delete existing products from Shopify admin
   - Re-run the import batches
   - New imports will have correct tags

---

## 📊 Expected Results

### Before (Lowercase)
```
Tags: modest, revolve, auto-scraped, dress top, on-sale
```

### After (Title Case)
```
Tags: Modest, Revolve, Auto-Scraped, Dress Top, On-Sale
```

---

## 🚨 Troubleshooting

### Issue: "Invalid API key or access token"
- Check your `.env` file has correct credentials
- Make sure `SHOPIFY_ACCESS_TOKEN` and `SHOPIFY_STORE_URL` are set

### Issue: Rate limit errors
- The script includes 0.5s delay between products
- If you still hit limits, the script will show the error
- Wait a few minutes and run again

### Issue: Want to start fresh instead
- Delete all auto-scraped products from Shopify admin
- Re-run all 4 batch imports
- All will have correct tags from the start

---

## ✅ Checklist

- [ ] Run dry-run to preview changes
- [ ] Apply tag updates to existing products
- [ ] Verify a few products in Shopify admin
- [ ] Resume batch imports (all 4 batches)
- [ ] Verify new imports have correct tags
- [ ] Test Shopify filtering with new tags

---

**Questions?** The system is ready to go! All new imports will use title case automatically. 🚀

