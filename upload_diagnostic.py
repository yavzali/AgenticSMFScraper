#!/usr/bin/env python3
"""
Upload diagnostic script to DigitalOcean server

This script uploads the debug_db.php diagnostic file to your server
so you can run web-based database diagnostics.
"""

import paramiko
import os
import getpass
from pathlib import Path
import argparse

def upload_diagnostic(hostname=None, username=None, password=None, ssh_key=None):
    """Upload debug_db.php to DigitalOcean server"""
    
    print("🚀 Diagnostic File Upload Tool")
    print("=" * 50)
    
    # Get credentials if not provided
    if not hostname:
        hostname = input("DigitalOcean hostname (e.g., assessmodesty.com or IP): ").strip()
    if not username:
        username = input("SSH username (usually 'root'): ").strip()
    
    # Set up SSH connection
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    print(f"🔌 Connecting to {hostname}...")
    
    try:
        if ssh_key and os.path.exists(ssh_key):
            ssh.connect(hostname, username=username, key_filename=ssh_key)
            print("✅ Connected using SSH key")
        elif password:
            ssh.connect(hostname, username=username, password=password)
            print("✅ Connected using password")
        else:
            password = getpass.getpass("Password: ")
            ssh.connect(hostname, username=username, password=password)
            print("✅ Connected using password")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False
    
    try:
        # Check local file exists
        local_file = 'web_assessment/debug_db.php'
        if not os.path.exists(local_file):
            print(f"❌ Local file not found: {local_file}")
            return False
        
        print(f"📁 Local file found: {local_file}")
        
        # Ensure remote directory exists
        print("📂 Ensuring remote directory exists...")
        ssh.exec_command('mkdir -p /var/www/html/web_assessment')
        
        # Upload file using SFTP
        sftp = ssh.open_sftp()
        remote_file = '/var/www/html/web_assessment/debug_db.php'
        
        print(f"📤 Uploading {local_file} to {remote_file}...")
        sftp.put(local_file, remote_file)
        
        # Set permissions
        print("🔧 Setting file permissions...")
        sftp.chmod(remote_file, 0o644)
        
        # Also upload a simple index.html for directory listing
        index_content = """<!DOCTYPE html>
<html>
<head><title>Web Assessment Debug</title></head>
<body>
    <h1>Web Assessment Debug Tools</h1>
    <ul>
        <li><a href="debug_db.php">🔍 Database Diagnostic</a></li>
    </ul>
</body>
</html>"""
        
        with sftp.open('/var/www/html/web_assessment/index.html', 'w') as f:
            f.write(index_content)
        sftp.chmod('/var/www/html/web_assessment/index.html', 0o644)
        
        sftp.close()
        
        print("✅ Upload complete!")
        print("\n" + "=" * 50)
        print("🌐 DIAGNOSTIC URLS:")
        print("=" * 50)
        print(f"📊 Main diagnostic: http://{hostname}/web_assessment/debug_db.php")
        print(f"📋 Directory index: http://{hostname}/web_assessment/")
        
        # Try to detect if it's an IP or domain
        if hostname.replace('.', '').isdigit():
            print(f"\n💡 Tip: If this is your domain IP, you can also try:")
            print(f"   http://your-domain.com/web_assessment/debug_db.php")
        
        print("\n📋 Next Steps:")
        print("1. Visit the diagnostic URL above")
        print("2. Look for any red ERROR messages")
        print("3. Run the auto-fix script if issues are found")
        
        return True
        
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return False
    finally:
        ssh.close()

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Upload diagnostic script to server')
    parser.add_argument('--host', help='Server hostname or IP')
    parser.add_argument('--username', help='SSH username')
    parser.add_argument('--password', help='SSH password')
    parser.add_argument('--ssh-key', help='Path to SSH private key')
    
    args = parser.parse_args()
    
    success = upload_diagnostic(args.host, args.username, args.password, args.ssh_key)
    
    if success:
        print("\n🎉 Diagnostic upload successful!")
    else:
        print("\n💥 Upload failed. Please check the errors above.")
    
    return success

if __name__ == '__main__':
    main()
