<?php
require_once 'config.php';
requireAuth();

$retailer = $_GET['retailer'] ?? '';
$category = $_GET['category'] ?? '';
$confidence = $_GET['confidence'] ?? '';
$reviewType = $_GET['review_type'] ?? '';

try {
    $db = getDatabase();
    
    // Build WHERE clause based on filters
    $where = ["review_status = 'pending'"];
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
    
    if ($confidence) {
        switch($confidence) {
            case 'low':
                $where[] = "confidence_score <= 0.7";
                break;
            case 'medium':
                $where[] = "confidence_score > 0.7 AND confidence_score <= 0.85";
                break;
            case 'high':
                $where[] = "confidence_score > 0.85";
                break;
        }
    }
    
    $whereClause = implode(' AND ', $where);
    
    $sql = "
        SELECT 
            id, title, retailer, category, price, original_price, sale_status,
            catalog_url, image_urls, shopify_image_urls, shopify_draft_id,
            review_type, confidence_score, similarity_matches, discovered_date,
            processing_stage
        FROM catalog_products 
        WHERE $whereClause 
        ORDER BY discovered_date DESC, confidence_score ASC 
        LIMIT 50
    ";
    
    $stmt = $db->prepare($sql);
    $stmt->execute($params);
    
    $products = [];
    while ($row = $stmt->fetch(PDO::FETCH_ASSOC)) {
        // Parse JSON fields
        $row['image_urls'] = json_decode($row['image_urls'] ?: '[]', true);
        $row['shopify_image_urls'] = json_decode($row['shopify_image_urls'] ?: '[]', true);
        $row['similarity_matches'] = json_decode($row['similarity_matches'] ?: '{}', true);
        
        // Determine which images to use
        if ($row['review_type'] === 'modesty_assessment') {
            // Use Shopify CDN URLs for modesty assessment
            $row['display_images'] = $row['shopify_image_urls'] ?: $row['image_urls'];
        } else {
            // Use thumbnail URLs for duplicate detection
            $row['display_images'] = $row['image_urls'];
        }
        
        $products[] = $row;
    }
    
    // Get stats
    $statsQuery = "
        SELECT 
            COUNT(*) as total_pending,
            COUNT(CASE WHEN DATE(reviewed_date) = DATE('now') THEN 1 END) as approved_today,
            COUNT(CASE WHEN review_status != 'pending' THEN 1 END) as total_processed,
            COUNT(CASE WHEN confidence_score <= 0.7 THEN 1 END) as low_confidence
        FROM catalog_products
    ";
    $stats = $db->query($statsQuery)->fetch(PDO::FETCH_ASSOC);
    
    jsonResponse([
        'products' => $products,
        'stats' => $stats
    ]);
    
} catch (Exception $e) {
    jsonResponse(['error' => 'Failed to fetch products: ' . $e->getMessage()], 500);
}
?>

