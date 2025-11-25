<?php
// Load local configuration if it exists, otherwise fall back to config.php
if (file_exists(__DIR__ . '/config.local.php')) {
    require_once 'config.local.php';
} else {
    require_once 'config.php';
}

class ShopifyAPI {
    
    public static function updateProductDecision($productId, $decision) {
        try {
            // Get current product from Shopify
            $product = self::getProduct($productId);
            if (!$product) {
                return ['success' => false, 'error' => 'Product not found in Shopify'];
            }
            
            // Update tags: remove "not-assessed", add decision
            $currentTags = array_filter(array_map('trim', explode(',', $product['tags'] ?? '')));
            $updatedTags = array_values(array_filter($currentTags, fn($tag) => $tag !== 'not-assessed'));
            
            if (!in_array($decision, $updatedTags)) {
                $updatedTags[] = $decision;
            }
            
            // Determine new status
            $newStatus = self::determineProductStatus($decision);
            
            // Update product
            $updateData = [
                'product' => [
                    'id' => $productId,
                    'tags' => implode(', ', $updatedTags),
                    'status' => $newStatus
                ]
            ];
            
            $response = self::apiRequest("products/{$productId}.json", 'PUT', $updateData);
            
            return [
                'success' => $response !== false,
                'status' => $newStatus,
                'tags' => $updatedTags
            ];
            
        } catch (Exception $e) {
            return ['success' => false, 'error' => $e->getMessage()];
        }
    }
    
    private static function getProduct($productId) {
        $response = self::apiRequest("products/{$productId}.json");
        return $response ? $response['product'] : null;
    }
    
    private static function determineProductStatus($decision) {
        if (in_array($decision, ['modest', 'moderately_modest'])) {
            return 'active'; // Publish to store
        } elseif ($decision === 'not_modest') {
            return 'draft'; // Keep as draft for training
        }
        return 'draft'; // Default to draft
    }
    
    private static function apiRequest($endpoint, $method = 'GET', $data = null) {
        $url = SHOPIFY_API_BASE . '/' . $endpoint;
        
        $headers = [
            'X-Shopify-Access-Token: ' . SHOPIFY_ACCESS_TOKEN,
            'Content-Type: application/json'
        ];
        
        $ch = curl_init();
        curl_setopt_array($ch, [
            CURLOPT_URL => $url,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_HTTPHEADER => $headers,
            CURLOPT_CUSTOMREQUEST => $method,
            CURLOPT_SSL_VERIFYPEER => true,
            CURLOPT_TIMEOUT => 30
        ]);
        
        if ($data && in_array($method, ['POST', 'PUT', 'PATCH'])) {
            curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($data));
        }
        
        $response = curl_exec($ch);
        $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        $error = curl_error($ch);
        curl_close($ch);
        
        if ($error) {
            throw new Exception('cURL error: ' . $error);
        }
        
        if ($httpCode >= 200 && $httpCode < 300) {
            return json_decode($response, true);
        }
        
        throw new Exception('Shopify API error: ' . $httpCode . ' - ' . $response);
    }
}
?>

