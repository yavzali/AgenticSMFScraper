<?php
// Trace where products came from and why they're not in products table
if (file_exists(__DIR__ . '/config.local.php')) {
    require_once 'config.local.php';
} else {
    require_once 'config.php';
}

header('Content-Type: text/plain');

try {
    $db = getDatabase();
    
    echo "=== ASSESSMENT QUEUE SOURCE ANALYSIS ===\n\n";
    
    // Get the reviewed products and their source
    $stmt = $db->query("
        SELECT id, source_workflow, added_at, product_data, review_decision
        FROM assessment_queue 
        WHERE status = 'reviewed'
        ORDER BY added_at DESC
        LIMIT 5
    ");
    
    while ($row = $stmt->fetch(PDO::FETCH_ASSOC)) {
        $productData = json_decode($row['product_data'], true);
        echo "Queue ID: " . $row['id'] . "\n";
        echo "  Source Workflow: " . ($row['source_workflow'] ?? 'NULL') . "\n";
        echo "  Added At: " . $row['added_at'] . "\n";
        echo "  Decision: " . $row['review_decision'] . "\n";
        echo "  Title: " . ($productData['title'] ?? 'N/A') . "\n";
        echo "  URL: " . ($productData['url'] ?? $productData['catalog_url'] ?? 'N/A') . "\n";
        echo "  Shopify ID: " . ($productData['shopify_id'] ?? 'NULL') . "\n\n";
    }
    
    echo "\n=== PRODUCTS TABLE CHECK ===\n\n";
    $productCount = $db->query("SELECT COUNT(*) as count FROM products")->fetch(PDO::FETCH_ASSOC);
    echo "Total products in table: " . $productCount['count'] . "\n\n";
    
    // Check if ANY products have lifecycle_stage = 'pending_assessment'
    $pendingAssessment = $db->query("
        SELECT COUNT(*) as count, retailer 
        FROM products 
        WHERE lifecycle_stage = 'pending_assessment'
        GROUP BY retailer
    ")->fetchAll(PDO::FETCH_ASSOC);
    
    echo "Products with lifecycle_stage='pending_assessment':\n";
    foreach ($pendingAssessment as $row) {
        echo "  " . $row['retailer'] . ": " . $row['count'] . "\n";
    }
    
    if (empty($pendingAssessment)) {
        echo "  NONE FOUND\n";
    }
    
    echo "\n=== REVOLVE PRODUCTS SAMPLE ===\n\n";
    $revolveProducts = $db->query("
        SELECT url, title, shopify_id, shopify_status, modesty_status, lifecycle_stage, source, last_workflow
        FROM products
        WHERE retailer = 'revolve'
        ORDER BY first_seen DESC
        LIMIT 5
    ")->fetchAll(PDO::FETCH_ASSOC);
    
    if (!empty($revolveProducts)) {
        foreach ($revolveProducts as $product) {
            echo "Title: " . $product['title'] . "\n";
            echo "  Shopify ID: " . $product['shopify_id'] . "\n";
            echo "  Lifecycle: " . ($product['lifecycle_stage'] ?? 'NULL') . "\n";
            echo "  Source: " . ($product['source'] ?? 'NULL') . "\n";
            echo "  Last Workflow: " . ($product['last_workflow'] ?? 'NULL') . "\n\n";
        }
    } else {
        echo "NO REVOLVE PRODUCTS FOUND\n";
    }
    
} catch (Exception $e) {
    echo "Error: " . $e->getMessage() . "\n";
    echo "Stack trace:\n" . $e->getTraceAsString() . "\n";
}
?>

