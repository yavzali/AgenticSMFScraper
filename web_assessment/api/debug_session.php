<?php
require_once 'config.php';

// Start session
if (session_status() === PHP_SESSION_NONE) {
    session_start();
}

header('Content-Type: application/json');
echo json_encode([
    'session_id' => session_id(),
    'session_data' => $_SESSION,
    'cookies' => $_COOKIE,
    'authenticated' => isset($_SESSION['authenticated']) ? $_SESSION['authenticated'] : null,
    'session_status' => session_status(),
    'session_status_text' => session_status() === PHP_SESSION_ACTIVE ? 'ACTIVE' : 'NONE'
]);
?>

