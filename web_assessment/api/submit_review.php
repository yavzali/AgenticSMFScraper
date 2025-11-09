<?php
/**
 * Submit Review API - Record review decisions
 * 
 * Updated to use new assessment_queue table (Phase 5)
 * Supports both modesty and duplication review types
 */

require_once 'config.php';
require_once 'shopify_api.php';
requireAuth();

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    jsonResponse(['error' => 'Method not allowed'], 405);
}

$data = json_decode(file_get_contents('php://input'), true);
$queueId = $data['product_id'] ?? $data['queue_id'] ?? null;  // Support both product_id and queue_id
$decision = $data['decision'] ?? null;
$notes = $data['notes'] ?? '';
$clothingTypeVerified = $data['clothing_type'] ?? null;  // NEW: Capture verified clothing type

if (!$queueId || !$decision) {
    jsonResponse(['error' => 'Missing queue_id or decision'], 400);
}

// Validate decision
$validDecisions = ['modest', 'moderately_modest', 'not_modest', 'duplicate', 'not_duplicate'];
if (!in_array($decision, $validDecisions)) {
    jsonResponse(['error' => 'Invalid decision'], 400);
}

try {
    $db = getDatabase();
    
    // Get queue item
    $stmt = $db->prepare("
        SELECT id, product_url, retailer, review_type, product_data
        FROM assessment_queue 
        WHERE id = :id AND status = 'pending'
    ");
    $stmt->bindParam(':id', $queueId);
    $stmt->execute();
    $queueItem = $stmt->fetch(PDO::FETCH_ASSOC);
    
    if (!$queueItem) {
        jsonResponse(['error' => 'Queue item not found or already reviewed'], 404);
    }
    
    $reviewType = $queueItem['review_type'];
    $productData = json_decode($queueItem['product_data'], true);
    
    // Update product data with verified clothing type (if provided)
    if ($clothingTypeVerified) {
        $productData['clothing_type'] = $clothingTypeVerified;
        $productData['clothing_type_verified'] = true;
        $productData['clothing_type_verified_by'] = 'web_interface';
        $productData['clothing_type_verified_at'] = date('Y-m-d H:i:s');
    }
    
    // Handle different review types
    if ($reviewType === 'duplication') {
        // Duplication review
        if ($decision === 'duplicate') {
            // Mark as duplicate in queue
            $stmt = $db->prepare("
                UPDATE assessment_queue 
                SET status = 'reviewed',
                    review_decision = :decision,
                    reviewer_notes = :notes,
                    product_data = :product_data,
                    reviewed_at = datetime('now'),
                    reviewed_by = 'web_interface'
                WHERE id = :id
            ");
            $stmt->bindParam(':id', $queueId);
            $stmt->bindParam(':decision', $decision);
            $stmt->bindParam(':notes', $notes);
            $stmt->bindValue(':product_data', json_encode($productData));
            $stmt->execute();
            
            jsonResponse(['success' => true, 'action' => 'marked_duplicate']);
            
        } elseif ($decision === 'not_duplicate') {
            // Mark as not duplicate - promote to modesty assessment
            $stmt = $db->prepare("
                UPDATE assessment_queue 
                SET status = 'reviewed',
                    review_decision = :decision,
                    reviewer_notes = :notes,
                    product_data = :product_data,
                    reviewed_at = datetime('now'),
                    reviewed_by = 'web_interface'
                WHERE id = :id
            ");
            $stmt->bindParam(':id', $queueId);
            $stmt->bindParam(':decision', $decision);
            $stmt->bindParam(':notes', $notes);
            $stmt->bindValue(':product_data', json_encode($productData));
            $stmt->execute();
            
            // Add to modesty queue
            $stmt = $db->prepare("
                INSERT INTO assessment_queue 
                (product_url, retailer, category, review_type, priority, product_data, source_workflow)
                SELECT product_url, retailer, category, 'modesty', 'high', product_data, 'duplicate_review'
                FROM assessment_queue WHERE id = :id
            ");
            $stmt->bindParam(':id', $queueId);
            $stmt->execute();
            
            jsonResponse(['success' => true, 'action' => 'promoted_to_modesty', 'message' => 'Product promoted to modesty assessment']);
        }
        
    } else {
        // Modesty assessment
        // TODO: Integrate with Shopify upload logic here
        //  For now, just mark as reviewed in queue
        
        $stmt = $db->prepare("
            UPDATE assessment_queue 
            SET status = 'reviewed',
                review_decision = :decision,
                reviewer_notes = :notes,
                product_data = :product_data,
                reviewed_at = datetime('now'),
                reviewed_by = 'web_interface'
            WHERE id = :id
        ");
        $stmt->bindParam(':id', $queueId);
        $stmt->bindParam(':decision', $decision);
        $stmt->bindParam(':notes', $notes);
        $stmt->bindValue(':product_data', json_encode($productData));
        $stmt->execute();
        
        jsonResponse(['success' => true, 'action' => 'modesty_reviewed', 'decision' => $decision]);
    }
    
} catch (Exception $e) {
    jsonResponse(['error' => 'Failed to submit review: ' . $e->getMessage()], 500);
}
?>
