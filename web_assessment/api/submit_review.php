<?php
require_once 'config.php';
require_once 'shopify_api.php';
requireAuth();

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    jsonResponse(['error' => 'Method not allowed'], 405);
}

$data = json_decode(file_get_contents('php://input'), true);
$productId = $data['product_id'] ?? null;
$decision = $data['decision'] ?? null;
$notes = $data['notes'] ?? '';

if (!$productId || !$decision) {
    jsonResponse(['error' => 'Missing product_id or decision'], 400);
}

// Validate decision
$validDecisions = ['modest', 'moderately_modest', 'not_modest', 'duplicate', 'new_product'];
if (!in_array($decision, $validDecisions)) {
    jsonResponse(['error' => 'Invalid decision'], 400);
}

try {
    $db = getDatabase();
    
    // Get product info
    $stmt = $db->prepare("
        SELECT shopify_draft_id, review_type 
        FROM catalog_products 
        WHERE id = :id
    ");
    $stmt->bindParam(':id', $productId);
    $stmt->execute();
    $product = $stmt->fetch(PDO::FETCH_ASSOC);
    
    if (!$product) {
        jsonResponse(['error' => 'Product not found'], 404);
    }
    
    // Handle different decision types
    if ($product['review_type'] === 'duplicate_uncertain') {
        if ($decision === 'duplicate') {
            // Mark as duplicate - no Shopify update needed
            $stmt = $db->prepare("
                UPDATE catalog_products 
                SET review_status = 'duplicate', reviewed_date = datetime('now'), review_notes = :notes
                WHERE id = :id
            ");
            $stmt->bindParam(':id', $productId);
            $stmt->bindParam(':notes', $notes);
            $stmt->execute();
            
            jsonResponse(['success' => true, 'action' => 'marked_duplicate']);
        } elseif ($decision === 'new_product') {
            // Promote to modesty assessment - would need full scraping
            $stmt = $db->prepare("
                UPDATE catalog_products 
                SET review_type = 'modesty_assessment', review_notes = :notes
                WHERE id = :id
            ");
            $stmt->bindParam(':id', $productId);
            $stmt->bindParam(':notes', $notes);
            $stmt->execute();
            
            jsonResponse(['success' => true, 'action' => 'promoted_to_assessment', 'message' => 'Product promoted to modesty assessment queue']);
        }
    } else {
        // Modesty assessment - update Shopify
        if ($product['shopify_draft_id']) {
            $shopifyResult = ShopifyAPI::updateProductDecision($product['shopify_draft_id'], $decision);
            
            if ($shopifyResult['success']) {
                // Update local database
                $stmt = $db->prepare("
                    UPDATE catalog_products 
                    SET review_status = :decision, reviewed_date = datetime('now'), review_notes = :notes
                    WHERE id = :id
                ");
                $stmt->bindParam(':id', $productId);
                $stmt->bindParam(':decision', $decision);
                $stmt->bindParam(':notes', $notes);
                $stmt->execute();
                
                jsonResponse([
                    'success' => true, 
                    'action' => 'shopify_updated',
                    'status' => $shopifyResult['status'],
                    'message' => 'Product updated in Shopify and published'
                ]);
            } else {
                jsonResponse(['error' => 'Shopify update failed: ' . $shopifyResult['error']], 500);
            }
        } else {
            jsonResponse(['error' => 'No Shopify product ID found'], 400);
        }
    }
    
} catch (Exception $e) {
    jsonResponse(['error' => 'Database error: ' . $e->getMessage()], 500);
}
?>

