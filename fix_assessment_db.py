#!/usr/bin/env python3
"""
Comprehensive Assessment Database Auto-Fix Script

This script diagnoses and automatically fixes database connectivity issues
for the web assessment interface on DigitalOcean servers.
"""

import paramiko
import os
import getpass
import argparse
from pathlib import Path
import time

class AssessmentDatabaseFixer:
    def __init__(self):
        self.ssh = None
        self.sftp = None
        self.issues_found = []
        self.fixes_applied = []
        
    def print_section(self, title):
        """Print formatted section header"""
        print(f"\n{'='*60}")
        print(f"🔧 {title}")
        print('='*60)
    
    def print_success(self, message):
        """Print success message"""
        print(f"✅ {message}")
    
    def print_error(self, message):
        """Print error message"""
        print(f"❌ {message}")
    
    def print_warning(self, message):
        """Print warning message"""
        print(f"⚠️  {message}")
    
    def execute_command(self, command, description=None, sudo=False):
        """Execute command on remote server"""
        if description:
            print(f"   🔍 {description}")
        
        try:
            if sudo:
                command = f"sudo {command}"
            
            stdin, stdout, stderr = self.ssh.exec_command(command)
            exit_code = stdout.channel.recv_exit_status()
            
            output = stdout.read().decode().strip()
            error = stderr.read().decode().strip()
            
            if exit_code == 0:
                if output:
                    print(f"   📤 {output}")
                return True, output
            else:
                if error:
                    print(f"   ❌ {error}")
                return False, error
        except Exception as e:
            print(f"   ❌ Command failed: {e}")
            return False, str(e)
    
    def connect(self, hostname, username, password=None, ssh_key=None):
        """Connect to server"""
        self.print_section("Connecting to Server")
        
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            if ssh_key and os.path.exists(ssh_key):
                self.ssh.connect(hostname, username=username, key_filename=ssh_key)
                print(f"✅ Connected to {hostname} using SSH key")
            elif password:
                self.ssh.connect(hostname, username=username, password=password)
                print(f"✅ Connected to {hostname} using password")
            else:
                password = getpass.getpass("Password: ")
                self.ssh.connect(hostname, username=username, password=password)
                print(f"✅ Connected to {hostname} using password")
            
            self.sftp = self.ssh.open_sftp()
            return True
        except Exception as e:
            self.print_error(f"Connection failed: {e}")
            return False
    
    def diagnose_database(self):
        """Comprehensive database diagnostics"""
        self.print_section("Database Diagnostics")
        
        # Check if database file exists
        success, output = self.execute_command(
            'ls -la /var/www/html/web_assessment/data/products.db',
            "Checking database file existence"
        )
        
        if not success:
            self.issues_found.append("Database file does not exist")
            self.print_warning("Database file missing")
        else:
            self.print_success("Database file exists")
            print(f"   📄 {output}")
        
        # Check data directory permissions
        success, output = self.execute_command(
            'ls -la /var/www/html/web_assessment/data/',
            "Checking data directory permissions"
        )
        
        if success:
            print(f"   📁 Directory listing:\n{output}")
        
        # Check web server user access
        success, output = self.execute_command(
            'sudo -u www-data test -r /var/www/html/web_assessment/data/products.db && echo "readable" || echo "NOT readable"',
            "Testing www-data read access"
        )
        
        if "NOT readable" in output:
            self.issues_found.append("Database not readable by www-data")
            self.print_warning("Database not readable by web server")
        
        # Check directory write access for journal files
        success, output = self.execute_command(
            'sudo -u www-data test -w /var/www/html/web_assessment/data/ && echo "writable" || echo "NOT writable"',
            "Testing www-data write access to directory"
        )
        
        if "NOT writable" in output:
            self.issues_found.append("Data directory not writable by www-data")
            self.print_warning("Data directory not writable by web server")
        
        # Check PHP extensions
        success, output = self.execute_command(
            'php -m | grep -E "(pdo|sqlite)" || echo "SQLite extensions not found"',
            "Checking PHP SQLite extensions"
        )
        
        if "SQLite extensions not found" in output:
            self.issues_found.append("PHP SQLite extensions missing")
            self.print_warning("PHP SQLite extensions not available")
        
        return len(self.issues_found) == 0
    
    def fix_missing_database(self):
        """Upload database if missing"""
        if "Database file does not exist" not in self.issues_found:
            return True
        
        self.print_section("Uploading Database")
        
        local_db_path = 'Shared/products.db'
        if not os.path.exists(local_db_path):
            self.print_error(f"Local database not found: {local_db_path}")
            return False
        
        try:
            # Ensure directory exists
            self.execute_command('mkdir -p /var/www/html/web_assessment/data', sudo=True)
            
            # Upload database
            print(f"📤 Uploading {local_db_path}...")
            remote_temp = '/tmp/products.db'
            self.sftp.put(local_db_path, remote_temp)
            
            # Move to final location
            success, output = self.execute_command(
                f'mv {remote_temp} /var/www/html/web_assessment/data/products.db',
                "Moving database to final location",
                sudo=True
            )
            
            if success:
                self.fixes_applied.append("Uploaded database file")
                self.print_success("Database uploaded successfully")
                return True
            else:
                self.print_error("Failed to move database to final location")
                return False
                
        except Exception as e:
            self.print_error(f"Database upload failed: {e}")
            return False
    
    def fix_permissions(self):
        """Fix file and directory permissions"""
        self.print_section("Fixing Permissions")
        
        commands = [
            ('chown www-data:www-data /var/www/html/web_assessment/data/products.db', 'Setting database file ownership'),
            ('chmod 644 /var/www/html/web_assessment/data/products.db', 'Setting database file permissions'),
            ('chown www-data:www-data /var/www/html/web_assessment/data/', 'Setting directory ownership'),
            ('chmod 755 /var/www/html/web_assessment/data/', 'Setting directory permissions'),
        ]
        
        for command, description in commands:
            success, output = self.execute_command(command, description, sudo=True)
            if success:
                self.fixes_applied.append(description)
        
        # Create .htaccess for security
        htaccess_content = '''# Protect database files from web access
<Files "*.db">
    Require all denied
</Files>
<Files "*.sqlite">
    Require all denied
</Files>'''
        
        try:
            with self.sftp.open('/var/www/html/web_assessment/data/.htaccess', 'w') as f:
                f.write(htaccess_content)
            
            self.execute_command('chown www-data:www-data /var/www/html/web_assessment/data/.htaccess', sudo=True)
            self.execute_command('chmod 644 /var/www/html/web_assessment/data/.htaccess', sudo=True)
            
            self.fixes_applied.append("Created .htaccess security file")
            self.print_success("Security .htaccess file created")
        except Exception as e:
            self.print_warning(f"Could not create .htaccess: {e}")
    
    def fix_php_config(self):
        """Fix config.php to use absolute path"""
        self.print_section("Updating Configuration")
        
        # Check if config.php exists
        success, output = self.execute_command(
            'ls -la /var/www/html/web_assessment/api/config.php',
            "Checking config.php existence"
        )
        
        if not success:
            self.print_warning("config.php not found, creating basic version...")
            
            # Create basic config.php
            config_content = """<?php
// Database configuration
define('DB_PATH', '/var/www/html/web_assessment/data/products.db');

// Error reporting
ini_set('display_errors', 1);
error_reporting(E_ALL);
?>"""
            
            try:
                # Ensure api directory exists
                self.execute_command('mkdir -p /var/www/html/web_assessment/api', sudo=True)
                
                with self.sftp.open('/var/www/html/web_assessment/api/config.php', 'w') as f:
                    f.write(config_content)
                
                self.execute_command('chown www-data:www-data /var/www/html/web_assessment/api/config.php', sudo=True)
                self.execute_command('chmod 644 /var/www/html/web_assessment/api/config.php', sudo=True)
                
                self.fixes_applied.append("Created config.php with absolute path")
                self.print_success("Created config.php")
            except Exception as e:
                self.print_error(f"Could not create config.php: {e}")
        else:
            # Update existing config.php to use absolute path
            success, output = self.execute_command(
                "sed -i \"s|define('DB_PATH', __DIR__ . '/../data/products.db');|define('DB_PATH', '/var/www/html/web_assessment/data/products.db');|g\" /var/www/html/web_assessment/api/config.php",
                "Updating config.php to use absolute path",
                sudo=True
            )
            
            if success:
                self.fixes_applied.append("Updated config.php to use absolute path")
                self.print_success("Config.php updated with absolute path")
    
    def test_connection(self):
        """Test database connection using PHP"""
        self.print_section("Testing Database Connection")
        
        test_script = """<?php
try {
    $pdo = new PDO('sqlite:/var/www/html/web_assessment/data/products.db');
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    
    $result = $pdo->query("SELECT name FROM sqlite_master WHERE type='table' LIMIT 5");
    $tables = $result->fetchAll(PDO::FETCH_COLUMN);
    
    echo "SUCCESS: Database connection works!\\n";
    echo "Tables found: " . implode(', ', $tables) . "\\n";
    
    // Test specific table
    if (in_array('assessment_queue', $tables)) {
        $stmt = $pdo->query("SELECT COUNT(*) as count FROM assessment_queue");
        $count = $stmt->fetch(PDO::FETCH_ASSOC);
        echo "Assessment queue items: " . $count['count'] . "\\n";
    }
    
} catch (PDOException $e) {
    echo "FAILED: " . $e->getMessage() . "\\n";
}
?>"""
        
        try:
            # Write and execute test script
            with self.sftp.open('/tmp/test_db_connection.php', 'w') as f:
                f.write(test_script)
            
            success, output = self.execute_command(
                'php /tmp/test_db_connection.php',
                "Running PHP database test"
            )
            
            if success and "SUCCESS" in output:
                self.print_success("Database connection test PASSED!")
                print(f"   📊 {output}")
            else:
                self.print_error("Database connection test FAILED")
                print(f"   ❌ {output}")
            
            # Clean up test file
            self.execute_command('rm -f /tmp/test_db_connection.php')
            
        except Exception as e:
            self.print_error(f"Could not run connection test: {e}")
    
    def install_php_extensions(self):
        """Install missing PHP SQLite extensions"""
        if "PHP SQLite extensions missing" not in self.issues_found:
            return
        
        self.print_section("Installing PHP SQLite Extensions")
        
        # Detect OS and install appropriate packages
        success, output = self.execute_command('cat /etc/os-release | grep "^ID="')
        
        if "ubuntu" in output.lower() or "debian" in output.lower():
            commands = [
                ('apt-get update', 'Updating package list'),
                ('apt-get install -y php-sqlite3 php-pdo-sqlite', 'Installing SQLite extensions'),
                ('systemctl reload apache2 || systemctl reload nginx || service apache2 reload || service nginx reload', 'Reloading web server'),
            ]
        else:
            # Try generic commands
            commands = [
                ('yum install -y php-pdo php-sqlite3 || dnf install -y php-pdo php-sqlite3', 'Installing SQLite extensions'),
                ('systemctl reload httpd || systemctl reload apache2 || systemctl reload nginx', 'Reloading web server'),
            ]
        
        for command, description in commands:
            success, output = self.execute_command(command, description, sudo=True)
            if success:
                self.fixes_applied.append(description)
    
    def print_summary(self):
        """Print comprehensive summary"""
        self.print_section("Fix Summary Report")
        
        if self.issues_found:
            print("\n🔍 ISSUES FOUND:")
            for i, issue in enumerate(self.issues_found, 1):
                print(f"   {i}. {issue}")
        else:
            print("\n✅ NO CRITICAL ISSUES FOUND")
        
        if self.fixes_applied:
            print("\n🔧 FIXES APPLIED:")
            for i, fix in enumerate(self.fixes_applied, 1):
                print(f"   {i}. {fix}")
        else:
            print("\n📝 NO FIXES NEEDED")
        
        print(f"\n📍 Database: /var/www/html/web_assessment/data/products.db")
        print(f"📁 Web root: /var/www/html/web_assessment/")
        print(f"⚙️  Config: /var/www/html/web_assessment/api/config.php")
    
    def cleanup(self):
        """Clean up connections"""
        if self.sftp:
            self.sftp.close()
        if self.ssh:
            self.ssh.close()
    
    def run_full_fix(self, hostname, username, password=None, ssh_key=None):
        """Run complete diagnostic and fix process"""
        try:
            print("🚀 Assessment Database Auto-Fix Tool")
            print("=" * 60)
            
            # Connect
            if not self.connect(hostname, username, password, ssh_key):
                return False
            
            # Diagnose
            self.diagnose_database()
            
            # Fix issues
            self.fix_missing_database()
            self.install_php_extensions()
            self.fix_permissions()
            self.fix_php_config()
            
            # Test
            self.test_connection()
            
            # Summary
            self.print_summary()
            
            print(f"\n🌐 Try your web assessment interface now!")
            print(f"   http://{hostname}/web_assessment/assess.php")
            
            return True
            
        except Exception as e:
            self.print_error(f"Unexpected error: {e}")
            return False
        finally:
            self.cleanup()

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Auto-fix assessment database issues')
    parser.add_argument('--host', help='Server hostname or IP', required=True)
    parser.add_argument('--username', help='SSH username', default='root')
    parser.add_argument('--password', help='SSH password')
    parser.add_argument('--ssh-key', help='Path to SSH private key')
    
    args = parser.parse_args()
    
    fixer = AssessmentDatabaseFixer()
    success = fixer.run_full_fix(args.host, args.username, args.password, args.ssh_key)
    
    if success:
        print("\n🎉 Assessment database fix complete!")
    else:
        print("\n💥 Fix process encountered errors. Check output above.")
    
    return success

if __name__ == '__main__':
    main()
