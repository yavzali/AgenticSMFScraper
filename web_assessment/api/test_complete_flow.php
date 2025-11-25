<?php
// Test complete assessment flow
if (file_exists(__DIR__ . '/config.local.php')) {
    require_once 'config.local.php';
} else {
    require_once 'config.php';
}

// Prevent caching
header('Cache-Control: no-store, no-cache, must-revalidate, max-age=0');
header('Pragma: no-cache');
header('Content-Type: text/plain');

try {
    $db = getDatabase();
    
    echo "=== CURRENT STATS (REAL-TIME) ===\n\n";
    
    $stats = $db->query("
        SELECT 
            COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending,
            COUNT(CASE WHEN status = 'reviewed' THEN 1 END) as reviewed_total,
            COUNT(CASE WHEN status = 'reviewed' AND DATE(reviewed_at) = DATE('now') THEN 1 END) as reviewed_today
        FROM assessment_queue
    ")->fetch(PDO::FETCH_ASSOC);
    
    echo "Pending: " . $stats['pending'] . "\n";
    echo "Reviewed Total: " . $stats['reviewed_total'] . "\n";
    echo "Reviewed Today: " . $stats['reviewed_today'] . "\n";
    
    echo "\n=== CACHE-BUSTING CHECK ===\n\n";
    echo "Timestamp: " . time() . "\n";
    echo "Date: " . date('Y-m-d H:i:s') . "\n";
    echo "If you see different timestamps on each refresh, cache-busting is working!\n";
    
    echo "\n=== RECENT PRODUCTS TABLE UPDATES ===\n\n";
    
    $recentUpdates = $db->query("
        SELECT url, retailer, modesty_status, shopify_status, lifecycle_stage, 
               assessed_at, last_updated, source
        FROM products 
        WHERE assessed_at IS NOT NULL
        ORDER BY assessed_at DESC
        LIMIT 3
    ")->fetchAll(PDO::FETCH_ASSOC);
    
    if (!empty($recentUpdates)) {
        foreach ($recentUpdates as $product) {
            echo "URL: " . $product['url'] . "\n";
            echo "  Modesty: " . $product['modesty_status'] . "\n";
            echo "  Shopify Status: " . $product['shopify_status'] . "\n";
            echo "  Lifecycle: " . $product['lifecycle_stage'] . "\n";
            echo "  Assessed: " . $product['assessed_at'] . "\n";
            echo "  Source: " . $product['source'] . "\n\n";
        }
    } else {
        echo "NO ASSESSED PRODUCTS YET (This will populate after your next review)\n\n";
    }
    
    echo "\n=== ASSESSMENT PIPELINE STATUS ===\n\n";
    
    // Check if there are pending items to review
    $pendingByType = $db->query("
        SELECT review_type, COUNT(*) as count
        FROM assessment_queue
        WHERE status = 'pending'
        GROUP BY review_type
    ")->fetchAll(PDO::FETCH_ASSOC);
    
    if (!empty($pendingByType)) {
        echo "Pending items by type:\n";
        foreach ($pendingByType as $row) {
            echo "  " . $row['review_type'] . ": " . $row['count'] . "\n";
        }
    } else {
        echo "No pending items\n";
    }
    
    echo "\n=== NEXT STEPS ===\n\n";
    echo "1. Visit assessmodesty.com and hard refresh (Cmd+Shift+R)\n";
    echo "2. Stats should show: Pending=" . $stats['pending'] . ", Approved Today=" . $stats['reviewed_today'] . "\n";
    echo "3. Approve one product\n";
    echo "4. Product should disappear AND stats should update immediately\n";
    echo "5. Come back to this page - you should see the product in 'RECENT PRODUCTS TABLE UPDATES'\n";
    
} catch (Exception $e) {
    echo "Error: " . $e->getMessage() . "\n";
}
?>

