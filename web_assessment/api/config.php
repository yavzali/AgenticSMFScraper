<?php
// Database configuration
define('DB_PATH', __DIR__ . '/../data/products.db');

// Shopify API configuration - UPDATE THESE WITH YOUR CREDENTIALS
// For local development, copy this file to config.local.php and add your actual credentials
define('SHOPIFY_STORE_URL', 'your-store.myshopify.com');
define('SHOPIFY_ACCESS_TOKEN', 'your-shopify-access-token');
define('SHOPIFY_API_VERSION', '2024-01');

// API endpoint base
define('SHOPIFY_API_BASE', 'https://' . SHOPIFY_STORE_URL . '/admin/api/' . SHOPIFY_API_VERSION);

// Helper functions
function jsonResponse($data, $status = 200) {
    http_response_code($status);
    header('Content-Type: application/json');
    echo json_encode($data);
    exit;
}

function getDatabase() {
    try {
        $pdo = new PDO('sqlite:' . DB_PATH);
        $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
        return $pdo;
    } catch (PDOException $e) {
        jsonResponse(['error' => 'Database connection failed: ' . $e->getMessage()], 500);
    }
}

function requireAuth() {
    session_start();
    if (!isset($_SESSION['authenticated']) || $_SESSION['authenticated'] !== true) {
        jsonResponse(['error' => 'Unauthorized'], 401);
    }
}
?>

