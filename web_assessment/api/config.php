<?php
// Session configuration - MUST be before session_start()
ini_set('session.cookie_path', '/');
ini_set('session.cookie_httponly', 1);
ini_set('session.use_strict_mode', 1);
ini_set('session.cookie_samesite', 'Lax');

// Database configuration
// Both assessment_queue and products tables are in the same database
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
        $pdo->setAttribute(PDO::ATTR_TIMEOUT, 10); // 10 second timeout
        
        // Enable WAL mode for better concurrency
        $pdo->exec('PRAGMA journal_mode = WAL');
        $pdo->exec('PRAGMA busy_timeout = 10000'); // 10 second busy timeout
        
        return $pdo;
    } catch (PDOException $e) {
        jsonResponse(['error' => 'Database connection failed: ' . $e->getMessage()], 500);
    }
}

function requireAuth() {
    // Only start session if not already started
    if (session_status() === PHP_SESSION_NONE) {
        session_start();
    }
    
    // Add debugging (remove after testing)
    error_log("Session ID: " . session_id());
    error_log("Authenticated: " . (isset($_SESSION['authenticated']) ? 'YES' : 'NO'));
    
    if (!isset($_SESSION['authenticated']) || $_SESSION['authenticated'] !== true) {
        error_log("Authentication failed - returning 401");
        jsonResponse(['error' => 'Unauthorized - Session not found or expired'], 401);
    }
}
?>

