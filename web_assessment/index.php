<?php
// Session configuration
ini_set('session.cookie_path', '/');
ini_set('session.cookie_httponly', 1);
session_start();

// Check if already logged in
if (isset($_SESSION['authenticated']) && $_SESSION['authenticated'] === true) {
    header('Location: assess.php');
    exit;
}

// Handle login
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (($_POST['password'] ?? '') === 'clothing') {
        $_SESSION['authenticated'] = true;
        
        // Force session to save
        session_write_close();
        session_start();
        
        // Add debugging
        error_log("Login successful - Session ID: " . session_id());
        
        header('Location: assess.php');
        exit;
    }
    $error = 'Incorrect password';
}
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Assess Modesty - Login</title>
    <link rel="stylesheet" href="assets/style.css">
</head>
<body style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); display: flex; align-items: center; justify-content: center; min-height: 100vh;">
    <div style="background: white; padding: 2rem; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); width: 90%; max-width: 400px;">
        <div style="text-align: center; margin-bottom: 2rem;">
            <h1 style="color: #667eea; margin-bottom: 0.5rem;">🕷️ Assess Modesty</h1>
            <p style="color: #666;">Product Review Interface</p>
        </div>
        
        <form method="POST" style="width: 100%;">
            <div style="margin-bottom: 1.5rem;">
                <label for="password" style="display: block; margin-bottom: 0.5rem; font-weight: 600;">Enter Password:</label>
                <input type="password" id="password" name="password" required autofocus 
                       style="width: 100%; padding: 1rem; border: 2px solid #e0e0e0; border-radius: 8px; font-size: 1rem;">
            </div>
            
            <?php if (isset($error)): ?>
                <div style="background: #f8d7da; color: #721c24; padding: 0.75rem; border-radius: 6px; margin-bottom: 1rem; text-align: center;">
                    <?= htmlspecialchars($error) ?>
                </div>
            <?php endif; ?>
            
            <button type="submit" class="btn" style="width: 100%; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 1rem; border: none; border-radius: 8px; font-weight: 600; cursor: pointer;">
                Access Assessment Interface
            </button>
        </form>
    </div>
</body>
</html>

