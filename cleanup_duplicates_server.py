#!/usr/bin/env python3
"""
Server Duplicate Cleanup Script
Removes duplicate products from assessment_queue on the server database
"""

import paramiko
import getpass

def cleanup_server_duplicates():
    print("🧹 Server Duplicate Cleanup Tool")
    print("=" * 50)
    
    # Get server credentials
    hostname = input("DigitalOcean hostname (167.172.148.145): ").strip() or "167.172.148.145"
    username = input("SSH username (root): ").strip() or "root"
    password = getpass.getpass("Password: ")
    
    # Connect to server
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print(f"\n🔌 Connecting to {hostname}...")
        ssh.connect(hostname, username=username, password=password)
        print("✅ Connected successfully")
        
        # Create cleanup script
        cleanup_script = '''
import sqlite3

print("🗑️  Starting duplicate cleanup on server database...")

# Connect to server database
conn = sqlite3.connect('/var/www/html/web_assessment/data/products.db')
cursor = conn.cursor()

# Check before cleanup
cursor.execute("SELECT COUNT(*) FROM assessment_queue WHERE status = 'pending'")
before_count = cursor.fetchone()[0]
print(f"Before cleanup: {before_count} pending products")

# Find duplicates (products that exist in main products table)
cursor.execute("""
SELECT COUNT(*) 
FROM assessment_queue q
INNER JOIN products p ON q.product_url = p.url
WHERE q.status = 'pending'
AND p.shopify_id IS NOT NULL
""")
duplicate_count = cursor.fetchone()[0]
print(f"Duplicates to remove: {duplicate_count}")

# Remove duplicates
cursor.execute("""
DELETE FROM assessment_queue
WHERE product_url IN (
  SELECT q.product_url 
  FROM assessment_queue q
  INNER JOIN products p ON q.product_url = p.url
  WHERE q.status = 'pending'
  AND p.shopify_id IS NOT NULL
)
""")

deleted_count = cursor.rowcount
print(f"✅ Deleted {deleted_count} duplicate products")

# Check after cleanup
cursor.execute("SELECT COUNT(*) FROM assessment_queue WHERE status = 'pending'")
after_count = cursor.fetchone()[0]
print(f"After cleanup: {after_count} pending products")

# Show breakdown by source
cursor.execute("""
SELECT 
  source_workflow,
  retailer,
  COUNT(*) as count
FROM assessment_queue 
WHERE status = 'pending'
GROUP BY source_workflow, retailer
ORDER BY count DESC
""")

results = cursor.fetchall()
print("\\nRemaining products by source:")
for row in results:
    print(f"  {row[0]} - {row[1]}: {row[2]} products")

# Commit changes
conn.commit()
conn.close()

print("\\n🎉 Cleanup complete!")
'''
        
        # Write and execute cleanup script on server
        print("\n🚀 Running cleanup script on server...")
        stdin, stdout, stderr = ssh.exec_command(f'python3 -c "{cleanup_script}"')
        
        output = stdout.read().decode()
        error = stderr.read().decode()
        
        print("CLEANUP OUTPUT:")
        print(output)
        
        if error:
            print("ERRORS:")
            print(error)
        
        ssh.close()
        print("\n✅ Server duplicate cleanup complete!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    cleanup_server_duplicates()
