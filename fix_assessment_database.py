#!/usr/bin/env python3
"""
Assessment Database Diagnostic and Fix Script

This script diagnoses and fixes database connectivity issues for the web assessment interface
by checking local database existence, connecting to DigitalOcean server, and fixing permissions.
"""

import os
import sys
import getpass
import stat
from pathlib import Path
import paramiko
from paramiko import SSHClient, AutoAddPolicy
from scp import SCPClient
import sqlite3

class AssessmentDatabaseFixer:
    def __init__(self):
        self.ssh_client = None
        self.local_db_path = "Shared/products.db"
        self.remote_data_dir = "/var/www/html/web_assessment/data"
        self.remote_db_path = f"{self.remote_data_dir}/products.db"
        self.issues_found = []
        self.fixes_applied = []
        
    def print_step(self, step_num, description):
        """Print a formatted step header"""
        print(f"\n{'='*60}")
        print(f"STEP {step_num}: {description}")
        print('='*60)
    
    def print_success(self, message):
        """Print success message in green"""
        print(f"✅ {message}")
    
    def print_error(self, message):
        """Print error message in red"""
        print(f"❌ {message}")
        
    def print_warning(self, message):
        """Print warning message in yellow"""
        print(f"⚠️  {message}")
    
    def check_local_database(self):
        """Step 1: Verify local database exists and is valid"""
        self.print_step(1, "Checking Local Database")
        
        if not os.path.exists(self.local_db_path):
            self.print_error(f"Local database not found at: {self.local_db_path}")
            return False
            
        # Check if it's a valid SQLite database
        try:
            conn = sqlite3.connect(self.local_db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            conn.close()
            
            self.print_success(f"Local database found: {self.local_db_path}")
            print(f"   📊 Tables found: {[table[0] for table in tables]}")
            
            # Get file size
            size = os.path.getsize(self.local_db_path)
            print(f"   📏 File size: {size:,} bytes ({size/1024/1024:.1f} MB)")
            
            return True
            
        except sqlite3.Error as e:
            self.print_error(f"Local database is corrupted: {e}")
            return False
    
    def get_credentials(self):
        """Get DigitalOcean credentials interactively"""
        self.print_step(2, "Getting Server Credentials")
        
        print("Please provide your DigitalOcean server credentials:")
        host = input("Server IP/hostname: ").strip()
        username = input("Username: ").strip()
        
        # Try SSH key first, then password
        ssh_key_path = input("SSH private key path (press Enter for password auth): ").strip()
        
        if ssh_key_path and os.path.exists(ssh_key_path):
            password = None
            key_filename = ssh_key_path
            print(f"Using SSH key: {ssh_key_path}")
        else:
            password = getpass.getpass("Password: ")
            key_filename = None
            print("Using password authentication")
        
        return host, username, password, key_filename
    
    def connect_ssh(self, host, username, password, key_filename):
        """Step 3: Connect to DigitalOcean server"""
        self.print_step(3, "Connecting to DigitalOcean Server")
        
        try:
            self.ssh_client = SSHClient()
            self.ssh_client.set_missing_host_key_policy(AutoAddPolicy())
            
            if key_filename:
                self.ssh_client.connect(host, username=username, key_filename=key_filename)
            else:
                self.ssh_client.connect(host, username=username, password=password)
            
            self.print_success(f"Connected to {host} as {username}")
            return True
            
        except Exception as e:
            self.print_error(f"Failed to connect: {e}")
            return False
    
    def execute_command(self, command, description=None, sudo=False):
        """Execute a command on the remote server"""
        if description:
            print(f"   🔍 {description}")
        
        try:
            if sudo:
                command = f"sudo {command}"
            
            stdin, stdout, stderr = self.ssh_client.exec_command(command)
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
    
    def diagnose_remote_database(self):
        """Step 4: Diagnose database issues on server"""
        self.print_step(4, "Diagnosing Remote Database")
        
        # Check if data directory exists
        success, output = self.execute_command(
            f"ls -la {self.remote_data_dir}",
            "Checking data directory"
        )
        
        if not success:
            self.issues_found.append("Data directory does not exist")
            self.print_warning(f"Data directory {self.remote_data_dir} does not exist")
        else:
            self.print_success("Data directory exists")
        
        # Check if database file exists
        success, output = self.execute_command(
            f"ls -la {self.remote_db_path}",
            "Checking database file"
        )
        
        if not success:
            self.issues_found.append("Database file does not exist")
            self.print_warning("Database file does not exist")
            return False
        else:
            self.print_success("Database file exists")
            print(f"   📄 {output}")
        
        # Check file ownership and permissions
        success, output = self.execute_command(
            f"stat {self.remote_db_path}",
            "Checking file permissions"
        )
        
        if success:
            print(f"   📊 File stats:\n{output}")
        
        # Test PHP user read access
        success, output = self.execute_command(
            f"test -r {self.remote_db_path} && echo 'readable' || echo 'NOT readable'",
            "Testing PHP user read access",
            sudo=True
        )
        
        if "NOT readable" in output:
            self.issues_found.append("Database not readable by www-data")
            self.print_warning("Database not readable by www-data user")
        else:
            self.print_success("Database is readable by www-data")
        
        # Test directory write access
        success, output = self.execute_command(
            f"test -w {self.remote_data_dir} && echo 'writable' || echo 'NOT writable'",
            "Testing directory write access",
            sudo=True
        )
        
        if "NOT writable" in output:
            self.issues_found.append("Data directory not writable by www-data")
            self.print_warning("Data directory not writable by www-data user")
        else:
            self.print_success("Data directory is writable by www-data")
        
        return True
    
    def create_remote_directory(self):
        """Create remote data directory if it doesn't exist"""
        print("   🔧 Creating data directory...")
        
        success, output = self.execute_command(
            f"mkdir -p {self.remote_data_dir}",
            "Creating data directory",
            sudo=True
        )
        
        if success:
            self.fixes_applied.append("Created data directory")
            self.print_success("Data directory created")
            return True
        else:
            self.print_error("Failed to create data directory")
            return False
    
    def upload_database(self):
        """Step 5: Upload database if missing"""
        self.print_step(5, "Uploading Database")
        
        if "Database file does not exist" not in self.issues_found:
            print("   ℹ️  Database already exists, skipping upload")
            return True
        
        try:
            # Create directory first if needed
            if "Data directory does not exist" in self.issues_found:
                if not self.create_remote_directory():
                    return False
            
            print(f"   📤 Uploading {self.local_db_path} to {self.remote_db_path}")
            
            with SCPClient(self.ssh_client.get_transport()) as scp:
                scp.put(self.local_db_path, f"/tmp/products.db")
            
            # Move to final location with sudo
            success, output = self.execute_command(
                f"mv /tmp/products.db {self.remote_db_path}",
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
            self.print_error(f"Failed to upload database: {e}")
            return False
    
    def fix_permissions(self):
        """Step 6: Fix database permissions"""
        self.print_step(6, "Fixing Permissions")
        
        # Fix database file ownership
        success, output = self.execute_command(
            f"chown www-data:www-data {self.remote_db_path}",
            "Setting database file ownership",
            sudo=True
        )
        
        if success:
            self.fixes_applied.append("Fixed database file ownership")
            self.print_success("Database file ownership fixed")
        
        # Fix database file permissions
        success, output = self.execute_command(
            f"chmod 644 {self.remote_db_path}",
            "Setting database file permissions",
            sudo=True
        )
        
        if success:
            self.fixes_applied.append("Fixed database file permissions")
            self.print_success("Database file permissions fixed")
        
        # Fix directory permissions
        success, output = self.execute_command(
            f"chmod 755 {self.remote_data_dir}",
            "Setting directory permissions",
            sudo=True
        )
        
        if success:
            self.fixes_applied.append("Fixed directory permissions")
            self.print_success("Directory permissions fixed")
        
        # Fix directory ownership
        success, output = self.execute_command(
            f"chown www-data:www-data {self.remote_data_dir}",
            "Setting directory ownership",
            sudo=True
        )
        
        if success:
            self.fixes_applied.append("Fixed directory ownership")
            self.print_success("Directory ownership fixed")
    
    def create_htaccess(self):
        """Create .htaccess file to protect data directory"""
        print("   🔧 Creating .htaccess file...")
        
        htaccess_content = """# Deny access to database files
<Files "*.db">
    Require all denied
</Files>

<Files "*.sqlite">
    Require all denied
</Files>

# Deny access to sensitive files
<Files "*.log">
    Require all denied
</Files>
"""
        
        # Create .htaccess file
        success, output = self.execute_command(
            f"echo '{htaccess_content}' > {self.remote_data_dir}/.htaccess",
            "Creating .htaccess file",
            sudo=True
        )
        
        if success:
            self.fixes_applied.append("Created .htaccess protection")
            self.print_success(".htaccess file created")
            
            # Fix .htaccess permissions
            self.execute_command(
                f"chown www-data:www-data {self.remote_data_dir}/.htaccess",
                sudo=True
            )
            self.execute_command(
                f"chmod 644 {self.remote_data_dir}/.htaccess",
                sudo=True
            )
    
    def test_database_connection(self):
        """Step 7: Test database connection from PHP perspective"""
        self.print_step(7, "Testing Database Connection")
        
        # Create a simple PHP test script
        php_test_script = f"""<?php
try {{
    $db = new PDO('sqlite:{self.remote_db_path}');
    $db->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    
    // Test basic query
    $stmt = $db->query("SELECT name FROM sqlite_master WHERE type='table'");
    $tables = $stmt->fetchAll(PDO::FETCH_COLUMN);
    
    echo "SUCCESS: Database connection established\\n";
    echo "Tables found: " . implode(', ', $tables) . "\\n";
    
    // Test a sample query if assessment_queue table exists
    if (in_array('assessment_queue', $tables)) {{
        $stmt = $db->query("SELECT COUNT(*) as count FROM assessment_queue");
        $count = $stmt->fetch(PDO::FETCH_ASSOC);
        echo "Assessment queue items: " . $count['count'] . "\\n";
    }}
    
}} catch (Exception $e) {{
    echo "ERROR: " . $e->getMessage() . "\\n";
}}
?>"""
        
        # Write test script to server
        success, output = self.execute_command(
            f"echo '{php_test_script}' > /tmp/test_db.php",
            "Creating PHP test script"
        )
        
        if success:
            # Run PHP test script
            success, output = self.execute_command(
                "php /tmp/test_db.php",
                "Testing database connection with PHP",
                sudo=True
            )
            
            if success and "SUCCESS" in output:
                self.print_success("Database connection test passed!")
                print(f"   📊 {output}")
            else:
                self.print_error("Database connection test failed")
                print(f"   ❌ {output}")
            
            # Clean up test script
            self.execute_command("rm /tmp/test_db.php")
    
    def print_summary(self):
        """Print final summary of issues found and fixes applied"""
        self.print_step("FINAL", "Summary Report")
        
        if self.issues_found:
            print("\n🔍 ISSUES FOUND:")
            for i, issue in enumerate(self.issues_found, 1):
                print(f"   {i}. {issue}")
        else:
            print("\n✅ NO ISSUES FOUND")
        
        if self.fixes_applied:
            print("\n🔧 FIXES APPLIED:")
            for i, fix in enumerate(self.fixes_applied, 1):
                print(f"   {i}. {fix}")
        else:
            print("\n ℹ️  NO FIXES NEEDED")
        
        print(f"\n📍 Database location: {self.remote_db_path}")
        print(f"📁 Data directory: {self.remote_data_dir}")
        print("\n🎯 Your web assessment interface should now be able to connect to the database!")
    
    def cleanup(self):
        """Clean up SSH connection"""
        if self.ssh_client:
            self.ssh_client.close()
    
    def run(self):
        """Main execution flow"""
        try:
            print("🚀 Assessment Database Diagnostic and Fix Tool")
            print("=" * 60)
            
            # Step 1: Check local database
            if not self.check_local_database():
                print("\n❌ Cannot proceed without valid local database")
                return False
            
            # Step 2 & 3: Get credentials and connect
            host, username, password, key_filename = self.get_credentials()
            if not self.connect_ssh(host, username, password, key_filename):
                return False
            
            # Step 4: Diagnose remote issues
            self.diagnose_remote_database()
            
            # Step 5: Upload database if needed
            self.upload_database()
            
            # Step 6: Fix permissions
            self.fix_permissions()
            
            # Create .htaccess protection
            self.create_htaccess()
            
            # Step 7: Test connection
            self.test_database_connection()
            
            # Final summary
            self.print_summary()
            
            return True
            
        except KeyboardInterrupt:
            print("\n\n⚠️  Operation cancelled by user")
            return False
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            return False
        finally:
            self.cleanup()

def main():
    """Main entry point"""
    # Check if paramiko and scp are installed
    try:
        import paramiko
        from scp import SCPClient
    except ImportError as e:
        print("❌ Missing required dependencies!")
        print("Please install them with:")
        print("   pip install paramiko scp")
        return False
    
    fixer = AssessmentDatabaseFixer()
    success = fixer.run()
    
    if success:
        print("\n🎉 All done! Your assessment database should be working now.")
    else:
        print("\n💥 Some issues occurred. Please check the output above.")
    
    return success

if __name__ == "__main__":
    main()
