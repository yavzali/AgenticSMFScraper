<?php
// Temporary test file to debug stats
if (file_exists(__DIR__ . '/config.local.php')) {
    require_once 'config.local.php';
} else {
    require_once 'config.php';
}

header('Content-Type: text/plain');

try {
    $db = getDatabase();
    
    echo "=== REVIEWED ITEMS ===\n";
    $stmt = $db->query("
        SELECT id, status, reviewed_at, 
               DATE(reviewed_at) as review_date, 
               DATE('now') as today 
        FROM assessment_queue 
        WHERE status = 'reviewed' 
        LIMIT 5
    ");
    while ($row = $stmt->fetch(PDO::FETCH_ASSOC)) {
        echo json_encode($row) . "\n";
    }
    
    echo "\n=== STATS QUERY ===\n";
    $statsQuery = "
        SELECT 
            COUNT(CASE WHEN status = 'pending' THEN 1 END) as total_pending,
            COUNT(CASE WHEN status = 'reviewed' AND DATE(reviewed_at) = DATE('now') THEN 1 END) as approved_today,
            COUNT(CASE WHEN status = 'reviewed' THEN 1 END) as total_processed
        FROM assessment_queue
    ";
    $stats = $db->query($statsQuery)->fetch(PDO::FETCH_ASSOC);
    echo json_encode($stats, JSON_PRETTY_PRINT) . "\n";
    
    echo "\n=== ALL COUNTS ===\n";
    $counts = $db->query("SELECT status, COUNT(*) as count FROM assessment_queue GROUP BY status")->fetchAll(PDO::FETCH_ASSOC);
    echo json_encode($counts, JSON_PRETTY_PRINT) . "\n";
    
} catch (Exception $e) {
    echo "Error: " . $e->getMessage() . "\n";
}
?>

