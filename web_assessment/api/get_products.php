<?php
/**
 * Get Products API - Fetch products from assessment queue
 * 
 * Updated to use new assessment_queue table (Phase 5)
 * Supports both modesty and duplication review types
 */

// Load local configuration if it exists, otherwise fall back to config.php
if (file_exists(__DIR__ . '/config.local.php')) {
    require_once 'config.local.php';
} else {
    require_once 'config.php';
}
requireAuth();

// Prevent caching - CRITICAL for real-time stats updates
header('Cache-Control: no-store, no-cache, must-revalidate, max-age=0');
header('Cache-Control: post-check=0, pre-check=0', false);
header('Pragma: no-cache');
header('Expires: 0');

$retailer = $_GET['retailer'] ?? '';
$category = $_GET['category'] ?? '';
$reviewType = $_GET['review_type'] ?? 'modesty';  // Default to modesty
$priority = $_GET['priority'] ?? '';

try {
    $db = getDatabase();
    
    // Build WHERE clause based on filters
    $where = ["status = 'pending'"];
    $params = [];
    
    if ($retailer) {
        $where[] = "retailer = :retailer";
        $params['retailer'] = $retailer;
    }
    
    if ($category) {
        $where[] = "category = :category";
        $params['category'] = $category;
    }
    
    if ($reviewType) {
        $where[] = "review_type = :review_type";
        $params['review_type'] = $reviewType;
    }
    
    if ($priority) {
        $where[] = "priority = :priority";
        $params['priority'] = $priority;
    }
    
    $whereClause = implode(' AND ', $where);
    
    // Order by priority then FIFO
    $sql = "
        SELECT 
            id, product_url, retailer, category, review_type, priority,
            product_data, suspected_match_data, added_at, source_workflow
        FROM assessment_queue 
        WHERE $whereClause 
        ORDER BY 
            CASE priority 
                WHEN 'high' THEN 1 
                WHEN 'normal' THEN 2 
                WHEN 'low' THEN 3 
            END,
            added_at ASC 
        LIMIT 50
    ";
    
    $stmt = $db->prepare($sql);
    $stmt->execute($params);
    
    $products = [];
    while ($row = $stmt->fetch(PDO::FETCH_ASSOC)) {
        // Parse JSON fields
        $productData = json_decode($row['product_data'], true);
        $suspectedMatch = $row['suspected_match_data'] ? json_decode($row['suspected_match_data'], true) : null;
        
        // Determine which images to display
        // Prefer Shopify CDN URLs (faster, more reliable) over retailer URLs
        $displayImages = [];
        if (!empty($productData['shopify_image_urls'])) {
            $displayImages = $productData['shopify_image_urls'];
        } elseif (!empty($productData['image_urls'])) {
            $displayImages = $productData['image_urls'];
        } elseif (!empty($productData['images'])) {
            // Fallback to legacy 'images' field
            $displayImages = $productData['images'];
        }
        
        // Flatten product data into row
        $product = [
            'id' => $row['id'],  // ADD: For JavaScript compatibility
            'queue_id' => $row['id'],
            'url' => $row['product_url'],
            'retailer' => $row['retailer'],
            'category' => $row['category'],
            'review_type' => $row['review_type'],
            'priority' => $row['priority'],
            'added_at' => $row['added_at'],
            'source' => $row['source_workflow'],
            
            // Product fields
            'title' => $productData['title'] ?? 'N/A',
            'price' => $productData['price'] ?? 'N/A',
            'images' => $productData['images'] ?? [],
            'display_images' => $displayImages,  // NEW: For web interface
            'shopify_id' => $productData['shopify_id'] ?? null,  // NEW: Track Shopify ID
            'brand' => $productData['brand'] ?? '',
            'description' => $productData['description'] ?? '',
            'confidence_score' => $productData['confidence_score'] ?? 1.0,  // ADD: For display
            'clothing_type' => $productData['clothing_type'] ?? 'unknown',  // ADD: For dropdown
            
            // For duplication review
            'suspected_match' => $suspectedMatch,
            'similarity_matches' => $suspectedMatch ? [$suspectedMatch] : []  // ADD: For compatibility
        ];
        
        $products[] = $product;
    }
    
    // Get stats (matching JavaScript field names)
    $statsQuery = "
        SELECT 
            COUNT(CASE WHEN status = 'pending' THEN 1 END) as total_pending,
            COUNT(CASE WHEN review_type = 'modesty' AND status = 'pending' THEN 1 END) as pending_modesty,
            COUNT(CASE WHEN review_type = 'duplication' AND status = 'pending' THEN 1 END) as pending_duplication,
            COUNT(CASE WHEN status = 'reviewed' AND DATE(reviewed_at) = DATE('now') THEN 1 END) as approved_today,
            COUNT(CASE WHEN status = 'reviewed' THEN 1 END) as total_processed,
            COUNT(CASE WHEN priority = 'high' AND status = 'pending' THEN 1 END) as high_priority,
            0 as low_confidence
        FROM assessment_queue
    ";
    $stats = $db->query($statsQuery)->fetch(PDO::FETCH_ASSOC);
    
    jsonResponse([
        'products' => $products,
        'stats' => $stats,
        'filters_applied' => [
            'retailer' => $retailer ?: 'all',
            'category' => $category ?: 'all',
            'review_type' => $reviewType,
            'priority' => $priority ?: 'all'
        ]
    ]);
    
} catch (Exception $e) {
    jsonResponse(['error' => 'Failed to fetch products: ' . $e->getMessage()], 500);
}
?>

