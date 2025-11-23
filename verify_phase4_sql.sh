#!/bin/bash
# Phase 4 SQL Verification Queries
# Run this after a catalog monitor test run

echo "==========================================================="
echo "PHASE 4: CATALOG MONITOR SQL VERIFICATION"
echo "==========================================================="

DB_PATH="Shared/products.db"

echo ""
echo "Query 1: Verify monitor snapshots created"
echo "-----------------------------------------------------------"
sqlite3 -header -column "$DB_PATH" << 'EOF'
SELECT scan_type, COUNT(*) as count
FROM catalog_products 
WHERE retailer = 'revolve'
AND discovered_date >= date('now', '-1 hour')
GROUP BY scan_type;
EOF

echo ""
echo "Query 2: Check price change detection"
echo "-----------------------------------------------------------"
sqlite3 -header -column "$DB_PATH" << 'EOF'
SELECT 
    product_url,
    priority,
    reason,
    catalog_price,
    products_price,
    ROUND(price_difference, 2) as price_diff,
    detected_at
FROM product_update_queue 
WHERE detected_at >= datetime('now', '-1 hour')
LIMIT 5;
EOF

echo ""
echo "Query 3: Verify lifecycle_stage on new products"
echo "-----------------------------------------------------------"
sqlite3 -header -column "$DB_PATH" << 'EOF'
SELECT 
    lifecycle_stage, 
    data_completeness, 
    last_workflow,
    COUNT(*) as count
FROM products
WHERE first_seen >= datetime('now', '-1 hour')
AND source = 'monitor'
GROUP BY lifecycle_stage, data_completeness, last_workflow;
EOF

echo ""
echo "Query 4: Check snapshot count vs detected products"
echo "-----------------------------------------------------------"
sqlite3 -header -column "$DB_PATH" << 'EOF'
SELECT 
    (SELECT COUNT(*) FROM catalog_products WHERE scan_type='monitor' AND discovered_date >= date('now', '-1 hour')) as monitor_snapshots,
    (SELECT COUNT(*) FROM catalog_products WHERE scan_type='baseline' AND discovered_date >= date('now', '-1 hour')) as baseline_snapshots,
    (SELECT COUNT(*) FROM products WHERE source='monitor' AND first_seen >= datetime('now', '-1 hour')) as new_products;
EOF

echo ""
echo "Query 5: Sample snapshot products with all new fields"
echo "-----------------------------------------------------------"
sqlite3 -header -column "$DB_PATH" << 'EOF'
SELECT 
    catalog_url,
    scan_type,
    image_url_source,
    review_status,
    SUBSTR(title, 1, 40) as title_truncated,
    price
FROM catalog_products 
WHERE scan_type = 'monitor'
AND discovered_date >= date('now', '-1 hour')
LIMIT 5;
EOF

echo ""
echo "Query 6: Sample new products with lifecycle fields"
echo "-----------------------------------------------------------"
sqlite3 -header -column "$DB_PATH" << 'EOF'
SELECT 
    SUBSTR(url, 1, 50) as url_truncated,
    lifecycle_stage,
    data_completeness,
    last_workflow,
    SUBSTR(extracted_at, 1, 16) as extracted
FROM products 
WHERE source = 'monitor'
AND first_seen >= datetime('now', '-1 hour')
LIMIT 3;
EOF

echo ""
echo "==========================================================="
echo "VERIFICATION COMPLETE"
echo "==========================================================="
echo ""
echo "Expected Results:"
echo "  • Query 1: Should show scan_type='monitor' entries"
echo "  • Query 2: Shows any price changes detected"
echo "  • Query 3: lifecycle_stage='pending_assessment', data_completeness='full'"
echo "  • Query 4: monitor_snapshots >> new_products"
echo "  • Query 5: All fields populated for monitor snapshots"
echo "  • Query 6: All lifecycle fields populated for new products"
echo ""

