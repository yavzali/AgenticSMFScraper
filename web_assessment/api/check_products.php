<?php
// Check if products exist and their status
if (file_exists(__DIR__ . '/config.local.php')) {
    require_once 'config.local.php';
} else {
    require_once 'config.php';
}

header('Content-Type: text/plain');

try {
    $db = getDatabase();
    
    $urls = [
        'https://www.revolve.com/halsey-ankle-dress/dp/CLEO-WD127/',
        'https://www.revolve.com/lea-printed-mesh-dress/dp/BARD-WD208/'
    ];
    
    echo "=== CHECKING PRODUCTS BY URL ===\n\n";
    
    foreach ($urls as $url) {
        echo "URL: $url\n";
        $stmt = $db->prepare("SELECT * FROM products WHERE url = :url");
        $stmt->execute(['url' => $url]);
        $product = $stmt->fetch(PDO::FETCH_ASSOC);
        
        if ($product) {
            echo "  FOUND in products table\n";
            echo "  Shopify ID: " . $product['shopify_id'] . "\n";
            echo "  Shopify Status: " . $product['shopify_status'] . "\n";
            echo "  Modesty Status: " . ($product['modesty_status'] ?? 'NULL') . "\n";
            echo "  Lifecycle Stage: " . ($product['lifecycle_stage'] ?? 'NULL') . "\n";
            echo "  Assessed At: " . ($product['assessed_at'] ?? 'NULL') . "\n";
        } else {
            echo "  NOT FOUND in products table\n";
        }
        echo "\n";
    }
    
    echo "=== CHECKING BY SHOPIFY ID ===\n\n";
    
    $shopifyIds = [14832595403122, 14832595566962];
    
    foreach ($shopifyIds as $shopifyId) {
        echo "Shopify ID: $shopifyId\n";
        $stmt = $db->prepare("SELECT url, shopify_status, modesty_status, lifecycle_stage, assessed_at FROM products WHERE shopify_id = :id");
        $stmt->execute(['id' => $shopifyId]);
        $product = $stmt->fetch(PDO::FETCH_ASSOC);
        
        if ($product) {
            echo "  FOUND\n";
            echo "  URL: " . $product['url'] . "\n";
            echo "  Shopify Status: " . $product['shopify_status'] . "\n";
            echo "  Modesty Status: " . ($product['modesty_status'] ?? 'NULL') . "\n";
            echo "  Lifecycle Stage: " . ($product['lifecycle_stage'] ?? 'NULL') . "\n";
            echo "  Assessed At: " . ($product['assessed_at'] ?? 'NULL') . "\n";
        } else {
            echo "  NOT FOUND\n";
        }
        echo "\n";
    }
    
} catch (Exception $e) {
    echo "Error: " . $e->getMessage() . "\n";
}
?>

