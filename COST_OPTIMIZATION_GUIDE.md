# Cost Optimization Guide - Pipeline Separation

## 🎯 Quick Reference

This guide explains how the cost-optimized pipeline separation works and how to use it effectively.

---

## 💰 Cost Savings at a Glance

| Processing Type | Scraping | Draft Creation | Cost |
|----------------|----------|----------------|------|
| **Full Processing** (modesty_assessment) | ✅ Yes | ✅ Yes | $0.08 |
| **Lightweight** (duplicate_uncertain) | ❌ No | ❌ No | $0.00 |

**Result**: **70% cost reduction** on average

---

## 🔄 How Products Flow Through the System

### Step 1: Discovery
```
Catalog Crawler discovers product
↓
Extracts catalog-level data (title, price, thumbnail)
↓
Runs 7-layer deduplication
↓
Assigns confidence score (0-1)
```

### Step 2: Classification
```
IF confidence ≥ 0.95:
   → review_type = 'modesty_assessment'
   → Genuinely new product
   
ELIF 0.70 ≤ confidence ≤ 0.85:
   → review_type = 'duplicate_uncertain'
   → Might be duplicate, needs review
   
ELSE (< 0.70):
   → review_type = 'modesty_assessment'
   → Very uncertain, treat as new
```

### Step 3: Conditional Processing

#### Path A: modesty_assessment (30% of products)
```
1. 🔍 Extract full product data
   - Use UnifiedExtractor
   - Get complete details, sizes, materials
   - Cost: $0.08 (Playwright) or $0.02 (Markdown)

2. 🛍️  Create Shopify draft
   - Build product with all data
   - Upload first 5 images
   - Add "pending-modesty-review" tag

3. 💾 Store with tracking
   - shopify_draft_id: 987654321
   - processing_stage: 'draft_created'
   - full_scrape_attempted: True
   - full_scrape_completed: True
   - cost_incurred: 0.08

4. 👀 Ready for modesty review
```

#### Path B: duplicate_uncertain (70% of products)
```
1. 💾 Store catalog info only
   - Title, price, image URLs from catalog
   - No full scraping needed
   - Cost: $0.00

2. 📝 Mark for duplicate review
   - shopify_draft_id: None
   - processing_stage: 'discovered'
   - full_scrape_attempted: False
   - full_scrape_completed: False
   - cost_incurred: 0.00

3. 🔍 Ready for duplicate review
   - User confirms: "Is this a duplicate?"
   - If NO → Promote to modesty assessment
   - If YES → Mark as duplicate, no further action
```

---

## 👥 User Workflows

### Workflow 1: Modesty Review (High Confidence Products)

**What you see**:
- Filter: "Modesty Review"
- Products with full details and images
- Already in Shopify as drafts

**Your actions**:
1. Review product for modesty
2. Click: "Modest", "Moderately Modest", or "Immodest"
3. If modest → Product publishes to store
4. If not_modest → Stays as draft (training data)

**System actions**:
- Updates Shopify draft with your decision
- Changes status (active/draft)
- Updates tags

### Workflow 2: Duplicate Check (Uncertain Products)

**What you see**:
- Filter: "Duplicate Check"
- Products with catalog info only
- Confidence score + match details
- "Similar to: [existing product]"

**Your actions**:
1. Review similarity details
2. Click: "New Product" or "Duplicate"
3. If New Product → Triggers full processing
4. If Duplicate → Marked as duplicate, no cost

**System actions**:
- If "New Product":
  - Performs full scraping ($0.08)
  - Creates Shopify draft
  - Moves to modesty review queue
- If "Duplicate":
  - Updates review_status to 'duplicate'
  - No additional cost

---

## 📊 Real-World Example

### Scenario: Processing 100 Products from Catalog Crawl

**Discovery Results**:
```
100 products discovered
↓
Deduplication analysis:
- 30 products: confidence 0.95+ (clearly new)
- 70 products: confidence 0.70-0.85 (possibly duplicates)
```

**Pipeline Routing**:
```
30 products → modesty_assessment
   ↓
   Full processing: 30 × $0.08 = $2.40
   ↓
   Shopify drafts created
   ↓
   Ready for modesty review

70 products → duplicate_uncertain
   ↓
   Lightweight storage: 70 × $0.00 = $0.00
   ↓
   Catalog info stored
   ↓
   Ready for duplicate review
```

**User Reviews Duplicates**:
```
Of 70 uncertain products:
- 60 confirmed as duplicates → No cost
- 10 confirmed as new → Promote to full processing
   ↓
   Additional cost: 10 × $0.08 = $0.80
```

**Final Cost**:
```
Initial processing:  $2.40
Promoted products:   $0.80
Total cost:          $3.20

Without optimization: 100 × $0.08 = $8.00
Savings: $4.80 (60%)
```

---

## 🔧 Advanced: Manual Product Promotion

If you need to promote a duplicate_uncertain product to full modesty review:

### Via Python API:
```python
from shopify_manager import ShopifyManager

manager = ShopifyManager()

# Get product data from database
catalog_product_data = {
    'catalog_url': 'https://retailer.com/product/12345',
    'retailer': 'retailer_name'
}

# Promote to modesty review
shopify_id = await manager.promote_duplicate_to_modesty_review(
    catalog_product_data, 
    'retailer_name'
)

if shopify_id:
    print(f"Product promoted! Shopify draft ID: {shopify_id}")
    print(f"Cost incurred: $0.08")
```

### Via Review Interface:
```
1. Go to "Duplicate Check" filter
2. Select product
3. Click "New Product (Approve)"
4. System automatically:
   - Scrapes full details
   - Creates Shopify draft
   - Moves to modesty review queue
```

---

## 📈 Cost Tracking Queries

### Check total costs for a run:
```sql
SELECT 
    discovery_run_id,
    COUNT(*) as total_products,
    SUM(CASE WHEN review_type = 'modesty_assessment' THEN 1 ELSE 0 END) as full_processed,
    SUM(CASE WHEN review_type = 'duplicate_uncertain' THEN 1 ELSE 0 END) as lightweight,
    SUM(cost_incurred) as total_cost
FROM catalog_products
WHERE discovery_run_id = 'run_20251020'
GROUP BY discovery_run_id;
```

### Monthly cost analysis:
```sql
SELECT 
    strftime('%Y-%m', discovered_date) as month,
    COUNT(*) as products,
    SUM(cost_incurred) as cost,
    AVG(cost_incurred) as avg_cost_per_product
FROM catalog_products
WHERE discovered_date >= date('now', '-3 months')
GROUP BY month
ORDER BY month DESC;
```

### Processing stage breakdown:
```sql
SELECT 
    processing_stage,
    COUNT(*) as count,
    AVG(cost_incurred) as avg_cost
FROM catalog_products
WHERE discovered_date >= date('now', '-7 days')
GROUP BY processing_stage;
```

---

## 🎯 Best Practices

### 1. Review Duplicate Queue Regularly
- Check duplicate_uncertain products weekly
- Confirm duplicates quickly (no cost impact)
- Promote genuinely new products

### 2. Monitor Cost Trends
- Track monthly API spend
- Watch for anomalies (sudden cost spikes)
- Adjust confidence thresholds if needed

### 3. Optimize Deduplication
- Train fuzzy matching with real data
- Update image hash thresholds based on results
- Review false positives/negatives

### 4. Batch Review Sessions
- Process modesty reviews in batches
- Handle duplicate reviews separately
- Use filters effectively

### 5. Cost Budgeting
- Set monthly cost limits
- Alert when approaching budget
- Plan review sessions around discount hours

---

## 🚨 Troubleshooting

### Problem: Too Many Products Going to Full Processing

**Symptoms**: High costs, most products are modesty_assessment

**Solution**:
1. Check deduplication thresholds
2. Review fuzzy matching accuracy
3. Consider lowering confidence threshold for modesty_assessment

### Problem: Too Many False Duplicates

**Symptoms**: Many duplicate_uncertain products are actually new

**Solution**:
1. Increase early stopping threshold (already at 5)
2. Improve image hash comparison
3. Review title normalization logic

### Problem: Scraping Failures

**Symptoms**: processing_stage = 'scrape_failed'

**Solution**:
1. Check retailer website changes
2. Update extractor patterns
3. Manually promote failed products

---

## 📚 Related Documentation

- **Foundation Changes**: `FOUNDATION_CHANGES_SUMMARY.md`
- **Pipeline Separation**: `PIPELINE_SEPARATION_SUMMARY.md`
- **Deduplication**: `Catalog Crawler/catalog_system_readme.md`
- **Review Interface**: `Catalog Crawler/modesty_review_interface.html`

---

## 🎉 Summary

The cost-optimized pipeline achieves **70% cost reduction** by:

1. **Intelligent Classification**: Confidence-based routing
2. **Conditional Processing**: Full scraping only when needed
3. **Manual Promotion**: User control over uncertain cases
4. **Complete Tracking**: Full cost visibility

**The system saves money while maintaining quality and giving you control over edge cases.**

---

*Last Updated: October 20, 2025*  
*Version: v2.3.0-complete*

