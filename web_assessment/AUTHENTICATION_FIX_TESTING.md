# Web Assessment Authentication Fix - Testing Guide

## Changes Applied

All authentication bug fixes have been implemented:

### ✅ Fixed Files

1. **`web_assessment/api/config.php`**
   - Added session configuration at top (cookie path, httponly, strict mode, samesite)
   - Updated `requireAuth()` to check session status before starting
   - Added debugging error_log statements

2. **`web_assessment/assess.php`**
   - Added session configuration before session_start()
   - Added debugging error_log statements

3. **`web_assessment/index.php`**
   - Added session configuration
   - Added session_write_close() and restart to force session save
   - Added debugging error_log on successful login

4. **`web_assessment/assets/app.js`**
   - Updated `submitReview()` to include `credentials: 'same-origin'`
   - Added better error handling for response errors
   - Updated `loadProducts()` to include `credentials: 'same-origin'`
   - Added error text logging for debugging

5. **`web_assessment/api/debug_session.php`** (NEW)
   - Created debug endpoint to check session state
   - Visit `/api/debug_session.php` to see session info

---

## Testing Procedure

### Step 1: Deploy Changes to Server

Upload all modified files to the web server:
```bash
# If using rsync or scp
rsync -av web_assessment/ user@assessmodesty.com:/var/www/html/
```

### Step 2: Clear Browser Data

Before testing, clear:
- All cookies for assessmodesty.com
- Browser cache
- Close and reopen browser

### Step 3: Test Login Flow

1. **Navigate to**: `https://assessmodesty.com`
2. **Enter password**: `clothing`
3. **Click**: "Access Assessment Interface"
4. **Expected**: Redirect to `assess.php` successfully

### Step 4: Check Browser Console

Open browser DevTools (F12) and look for:
- No JavaScript errors
- Successful fetch requests
- Check Network tab: Look for `Set-Cookie` headers in responses

### Step 5: Check Session Debug Endpoint

1. **Navigate to**: `https://assessmodesty.com/api/debug_session.php`
2. **Expected JSON output**:
```json
{
  "session_id": "abc123...",
  "session_data": {
    "authenticated": true
  },
  "cookies": {
    "PHPSESSID": "abc123..."
  },
  "authenticated": true,
  "session_status": 2,
  "session_status_text": "ACTIVE"
}
```

### Step 6: Test Product Review Submission

1. **Go to**: `https://assessmodesty.com/assess.php`
2. **Wait for products to load**
3. **Select a clothing type** from dropdown (e.g., "Dress")
4. **Click**: Any modesty button (Modest/Moderately/Not Modest)
5. **Expected**:
   - Success toast notification
   - Product disappears from list
   - No console errors
   - **NO 401 error**

### Step 7: Check Network Tab

In browser DevTools Network tab, check the `submit_review.php` request:
- **Request Headers** should include: `Cookie: PHPSESSID=...`
- **Response Status** should be: `200 OK`
- **Response Body** should be: `{"success":true,"message":"..."}`

### Step 8: Check Server Logs

On the server, check PHP error logs:
```bash
# Check for session debugging messages
tail -f /var/log/php/error.log
# OR
tail -f /var/www/html/error_log

# Look for:
# "Login successful - Session ID: ..."
# "Assess.php - Session ID: ..."
# "Assess.php - Authenticated: YES"
# "Session ID: ..."
# "Authenticated: YES"
```

---

## Expected Behavior

### ✅ Success Indicators

1. **Login**:
   - Redirects to assess.php
   - Logs show: "Login successful - Session ID: [id]"

2. **Page Load**:
   - Products load without errors
   - Logs show: "Assess.php - Authenticated: YES"

3. **Review Submission**:
   - Button click succeeds
   - Product removed from view
   - Toast shows success message
   - Logs show: "Authenticated: YES" (from requireAuth())

4. **Session Persistence**:
   - Refresh page → still logged in
   - Navigate between pages → still logged in
   - AJAX requests → authenticated

### ❌ Failure Indicators

If you see:
- **401 Unauthorized**: Session not being sent or recognized
- **Session ID mismatch**: Different IDs in logs
- **Authenticated: NO**: Session lost between requests
- **No cookies in Network tab**: Browser not storing session cookie

---

## Troubleshooting

### Issue: Still Getting 401 Errors

**Check 1**: Verify session cookies are being set
```bash
# In browser console:
document.cookie
# Should show: "PHPSESSID=..."
```

**Check 2**: Verify server session configuration
```bash
# On server, check PHP session settings:
php -i | grep session

# Look for:
# session.cookie_path => /
# session.cookie_httponly => 1
# session.save_path => (should be writable directory)
```

**Check 3**: Test session file permissions
```bash
# Check session save path
php -r "echo session_save_path();"

# Check it's writable
ls -ld /var/lib/php/sessions  # or wherever save_path points
# Should show: drwx-wx-wt (or similar)

# Test writing a session
php -r "session_start(); \$_SESSION['test'] = 'works'; session_write_close();"
# Should succeed without errors
```

### Issue: Session Not Persisting

**Check 4**: Verify session files are being created
```bash
# List session files
ls -lt /var/lib/php/sessions/ | head -10

# Check if your session ID exists
ls /var/lib/php/sessions/sess_[your_session_id]
```

**Check 5**: Verify session garbage collection isn't too aggressive
```bash
php -i | grep session.gc

# Look for:
# session.gc_maxlifetime => 1440 (seconds = 24 minutes)
# session.gc_probability => 1
# session.gc_divisor => 1000
```

### Issue: Cookies Not Being Sent

**Check 6**: Verify cookie domain/path
- Open browser DevTools → Application tab → Cookies
- Look for PHPSESSID cookie
- Check Domain, Path, SameSite, HttpOnly flags

**Check 7**: Test with debug endpoint
```bash
# Visit in browser:
https://assessmodesty.com/api/debug_session.php

# Check:
# - Is session_id present?
# - Is authenticated = true?
# - Are cookies listed?
```

---

## Server-Level Fixes (If Needed)

### If session.save_path is not writable:

```bash
# Create writable session directory
sudo mkdir -p /var/lib/php/sessions
sudo chown www-data:www-data /var/lib/php/sessions
sudo chmod 733 /var/lib/php/sessions
```

### If PHP-FPM is being used:

```bash
# Edit PHP-FPM pool config
sudo nano /etc/php/8.x/fpm/pool.d/www.conf

# Add:
php_admin_value[session.save_path] = /var/lib/php/sessions

# Restart PHP-FPM
sudo systemctl restart php8.x-fpm
```

### If Apache is being used:

```bash
# Edit Apache config
sudo nano /etc/apache2/sites-available/assessmodesty.conf

# Add in <VirtualHost> block:
php_admin_value session.save_path "/var/lib/php/sessions"

# Restart Apache
sudo systemctl restart apache2
```

---

## Cleanup After Testing

Once authentication is working:

### Remove Debug Statements

1. **`web_assessment/api/config.php`** - Remove error_log() lines in requireAuth()
2. **`web_assessment/assess.php`** - Remove error_log() lines at top
3. **`web_assessment/index.php`** - Remove error_log() line in login handler
4. **`web_assessment/api/debug_session.php`** - Delete or restrict access

---

## Success Criteria

✅ Authentication fix is successful when:

1. User can login without errors
2. Session persists across page loads
3. AJAX requests include session cookies
4. Reviews submit successfully (200 response, not 401)
5. Products update in real-time
6. No "Unauthorized" errors in console or network tab

---

## Contact

If issues persist after following all troubleshooting steps, provide:
- PHP version (`php -v`)
- Web server (Apache/Nginx)
- Session configuration (`php -i | grep session`)
- Error logs from server
- Browser console errors
- Network tab screenshot of failed request

