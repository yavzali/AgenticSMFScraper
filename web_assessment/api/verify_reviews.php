<?php
// Verify recently reviewed products
if (file_exists(__DIR__ . '/config.local.php')) {
    require_once 'config.local.php';
} else {
    require_once 'config.php';
}

header('Content-Type: text/plain');

try {
    $db = getDatabase();
    
    echo "=== ASSESSMENT QUEUE - RECENTLY REVIEWED ===\n\n";
    $stmt = $db->query("
        SELECT id, status, review_decision, reviewed_at, reviewed_by, product_data 
        FROM assessment_queue 
        WHERE status = 'reviewed' 
        ORDER BY reviewed_at DESC 
        LIMIT 3
    ");
    
    $reviewedProducts = [];
    while ($row = $stmt->fetch(PDO::FETCH_ASSOC)) {
        $productData = json_decode($row['product_data'], true);
        $shopifyId = $productData['shopify_id'] ?? null;
        $url = $productData['url'] ?? $productData['catalog_url'] ?? 'N/A';
        
        echo "Queue ID: " . $row['id'] . "\n";
        echo "  Status: " . $row['status'] . "\n";
        echo "  Decision: " . $row['review_decision'] . "\n";
        echo "  Reviewed At: " . $row['reviewed_at'] . "\n";
        echo "  Reviewed By: " . $row['reviewed_by'] . "\n";
        echo "  Title: " . ($productData['title'] ?? 'N/A') . "\n";
        echo "  Shopify ID: " . ($shopifyId ?? 'N/A') . "\n";
        echo "  URL: " . $url . "\n\n";
        
        if ($shopifyId) {
            $reviewedProducts[] = ['shopify_id' => $shopifyId, 'url' => $url];
        }
    }
    
    echo "\n=== PRODUCTS TABLE - RECENTLY ASSESSED ===\n\n";
    $stmt = $db->query("
        SELECT url, retailer, title, shopify_id, shopify_status, modesty_status, 
               lifecycle_stage, assessed_at, last_updated
        FROM products 
        WHERE assessed_at IS NOT NULL 
        ORDER BY assessed_at DESC 
        LIMIT 3
    ");
    
    while ($row = $stmt->fetch(PDO::FETCH_ASSOC)) {
        echo "Product: " . $row['title'] . "\n";
        echo "  Retailer: " . $row['retailer'] . "\n";
        echo "  Shopify ID: " . $row['shopify_id'] . "\n";
        echo "  Shopify Status: " . $row['shopify_status'] . "\n";
        echo "  Modesty Status: " . $row['modesty_status'] . "\n";
        echo "  Lifecycle Stage: " . $row['lifecycle_stage'] . "\n";
        echo "  Assessed At: " . $row['assessed_at'] . "\n";
        echo "  URL: " . $row['url'] . "\n\n";
    }
    
    echo "\n=== COUNTS ===\n\n";
    $counts = $db->query("
        SELECT 
            COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending,
            COUNT(CASE WHEN status = 'reviewed' THEN 1 END) as reviewed,
            COUNT(CASE WHEN status = 'reviewed' AND DATE(reviewed_at) = DATE('now') THEN 1 END) as reviewed_today
        FROM assessment_queue
    ")->fetch(PDO::FETCH_ASSOC);
    
    echo "Pending: " . $counts['pending'] . "\n";
    echo "Total Reviewed: " . $counts['reviewed'] . "\n";
    echo "Reviewed Today: " . $counts['reviewed_today'] . "\n";
    
} catch (Exception $e) {
    echo "Error: " . $e->getMessage() . "\n";
}
?>

