<?php
// Diagnostic script to debug database connection issues
header('Content-Type: text/html; charset=utf-8');
?>
<!DOCTYPE html>
<html>
<head>
    <title>Database Diagnostic</title>
    <style>
        body { font-family: monospace; padding: 20px; background: #f5f5f5; }
        .success { color: green; font-weight: bold; }
        .error { color: red; font-weight: bold; }
        .info { color: blue; }
        .section { background: white; padding: 15px; margin: 10px 0; border-radius: 5px; }
        pre { background: #eee; padding: 10px; overflow-x: auto; }
    </style>
</head>
<body>
    <h1>🔍 Database Connection Diagnostic</h1>

<?php
// Test 1: PHP Info
echo "<div class='section'>";
echo "<h2>Test 1: Current Directory Context</h2>";
echo "<pre>";
echo "Current file: " . __FILE__ . "\n";
echo "Current directory (__DIR__): " . __DIR__ . "\n";
echo "Working directory (getcwd): " . getcwd() . "\n";
echo "Script filename: " . $_SERVER['SCRIPT_FILENAME'] . "\n";
echo "</pre>";
echo "</div>";

// Test 2: Database Path Resolution
echo "<div class='section'>";
echo "<h2>Test 2: Database Path Resolution</h2>";

$paths_to_test = [
    'Relative from config.php' => __DIR__ . '/api/../data/products.db',
    'Relative simplified' => __DIR__ . '/data/products.db',
    'Absolute path' => '/var/www/html/web_assessment/data/products.db',
    'Alt absolute' => '/var/www/web_assessment/data/products.db',
];

echo "<pre>";
foreach ($paths_to_test as $label => $path) {
    echo "\n<strong>$label:</strong>\n";
    echo "Path: $path\n";
    
    $resolved = realpath($path);
    echo "Realpath: " . ($resolved ? $resolved : "NOT FOUND") . "\n";
    
    if (file_exists($path)) {
        echo "✅ File exists: <span class='success'>YES</span>\n";
        echo "Readable: " . (is_readable($path) ? "<span class='success'>YES</span>" : "<span class='error'>NO</span>") . "\n";
        echo "Writable: " . (is_writable($path) ? "<span class='success'>YES</span>" : "<span class='error'>NO</span>") . "\n";
        echo "Size: " . filesize($path) . " bytes\n";
        echo "Permissions: " . substr(sprintf('%o', fileperms($path)), -4) . "\n";
        
        $stat = stat($path);
        if ($stat) {
            $owner = posix_getpwuid($stat['uid']);
            echo "Owner: " . ($owner ? $owner['name'] : $stat['uid']) . "\n";
        }
    } else {
        echo "❌ File exists: <span class='error'>NO</span>\n";
    }
    echo "---\n";
}
echo "</pre>";
echo "</div>";

// Test 3: Parent Directory Check
echo "<div class='section'>";
echo "<h2>Test 3: Parent Directory (data/) Permissions</h2>";

$data_dirs = [
    __DIR__ . '/data',
    '/var/www/html/web_assessment/data',
];

echo "<pre>";
foreach ($data_dirs as $dir) {
    if (is_dir($dir)) {
        echo "\n<strong>Directory: $dir</strong>\n";
        echo "Readable: " . (is_readable($dir) ? "<span class='success'>YES</span>" : "<span class='error'>NO</span>") . "\n";
        echo "Writable: " . (is_writable($dir) ? "<span class='success'>YES</span>" : "<span class='error'>NO</span>") . "\n";
        echo "Permissions: " . substr(sprintf('%o', fileperms($dir)), -4) . "\n";
        
        $stat = stat($dir);
        if ($stat) {
            $owner = posix_getpwuid($stat['uid']);
            echo "Owner: " . ($owner ? $owner['name'] : $stat['uid']) . "\n";
        }
        echo "---\n";
    }
}
echo "</pre>";
echo "</div>";

// Test 4: PHP Extensions
echo "<div class='section'>";
echo "<h2>Test 4: PHP SQLite Extension</h2>";
echo "<pre>";
echo "PDO Available: " . (extension_loaded('pdo') ? "<span class='success'>YES</span>" : "<span class='error'>NO</span>") . "\n";
echo "PDO SQLite Available: " . (extension_loaded('pdo_sqlite') ? "<span class='success'>YES</span>" : "<span class='error'>NO</span>") . "\n";
echo "SQLite3 Available: " . (extension_loaded('sqlite3') ? "<span class='success'>YES</span>" : "<span class='error'>NO</span>") . "\n";
echo "</pre>";
echo "</div>";

// Test 5: PHP Restrictions
echo "<div class='section'>";
echo "<h2>Test 5: PHP Security Restrictions</h2>";
echo "<pre>";
$open_basedir = ini_get('open_basedir');
echo "open_basedir: " . ($open_basedir ? "<span class='error'>$open_basedir</span>" : "<span class='success'>Not set (good)</span>") . "\n";
echo "safe_mode: " . (ini_get('safe_mode') ? "<span class='error'>ON</span>" : "<span class='success'>OFF</span>") . "\n";
echo "</pre>";
echo "</div>";

// Test 6: Actual PDO Connection Attempts
echo "<div class='section'>";
echo "<h2>Test 6: PDO Connection Attempts</h2>";

foreach ($paths_to_test as $label => $path) {
    if (file_exists($path)) {
        echo "<h3>Testing: $label</h3>";
        echo "<pre>";
        
        try {
            $pdo = new PDO('sqlite:' . $path);
            $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
            
            echo "✅ <span class='success'>Connection SUCCESSFUL!</span>\n";
            
            // Try a simple query
            $result = $pdo->query("SELECT name FROM sqlite_master WHERE type='table' LIMIT 5");
            echo "Tables found:\n";
            while ($row = $result->fetch(PDO::FETCH_ASSOC)) {
                echo "  - " . $row['name'] . "\n";
            }
            
        } catch (PDOException $e) {
            echo "❌ <span class='error'>Connection FAILED</span>\n";
            echo "Error: " . $e->getMessage() . "\n";
        }
        
        echo "</pre>";
    }
}

echo "</div>";

// Test 7: Current User Info
echo "<div class='section'>";
echo "<h2>Test 7: Current PHP Process User</h2>";
echo "<pre>";
if (function_exists('posix_geteuid')) {
    $processUser = posix_getpwuid(posix_geteuid());
    echo "PHP running as: " . ($processUser ? $processUser['name'] : 'Unknown') . "\n";
    echo "UID: " . posix_geteuid() . "\n";
    echo "GID: " . posix_getegid() . "\n";
} else {
    echo "POSIX functions not available\n";
}
echo "</pre>";
echo "</div>";

?>

<div class='section'>
    <h2>📋 Recommended Fix</h2>
    <p>Based on the diagnostics above, the most likely fixes are:</p>
    <ol>
        <li><strong>If database file doesn't exist:</strong> Upload it via SCP</li>
        <li><strong>If permissions are wrong:</strong> Run chmod/chown commands</li>
        <li><strong>If path is wrong in config.php:</strong> Use the absolute path that worked above</li>
    </ol>
</div>

</body>
</html>
