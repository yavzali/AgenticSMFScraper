#!/usr/bin/env python3
"""
Start of Day Status Check

Compares local and server databases to show:
- Pending products on server (waiting for your review)
- Assessments on server (made on phone, not yet synced locally)
- New products on local (not yet synced to server)

Usage:
    python3 check_status.py
"""

import sys
import sqlite3
import tempfile
import os
from pathlib import Path
from datetime import datetime

# Add Shared to path
sys.path.insert(0, str(Path(__file__).parent / 'Shared'))

import paramiko
from scp import SCPClient

# Server config
SERVER_IP = "167.172.148.145"
SERVER_USER = "root"
SERVER_PASSWORD = "modestyassessor"
REMOTE_DB_PATH = "/var/www/html/web_assessment/data/products.db"
LOCAL_DB_PATH = Path(__file__).parent / "Shared" / "products.db"


def download_server_db():
    """Download server database to temp file"""
    print("📥 Downloading server database...")
    
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER_IP, username=SERVER_USER, password=SERVER_PASSWORD, timeout=10)
    
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_db.close()
    
    with SCPClient(ssh.get_transport()) as scp:
        scp.get(REMOTE_DB_PATH, temp_db.name)
    
    ssh.close()
    return temp_db.name


def query_db(db_path, query):
    """Execute query and return results"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query)
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results


def main():
    print("=" * 60)
    print("📊 START OF DAY STATUS CHECK")
    print("=" * 60)
    print()
    
    try:
        # Download server database
        server_db_temp = download_server_db()
        print("✅ Server database downloaded\n")
        
        # Query server for pending assessments
        print("=" * 60)
        print("SERVER STATUS (AssessModesty.com)")
        print("=" * 60)
        
        server_pending = query_db(server_db_temp, """
            SELECT COUNT(*) as count FROM assessment_queue WHERE status = 'pending'
        """)[0]['count']
        
        server_pending_by_retailer = query_db(server_db_temp, """
            SELECT retailer, COUNT(*) as count 
            FROM assessment_queue 
            WHERE status = 'pending' 
            GROUP BY retailer
            ORDER BY count DESC
        """)
        
        server_assessments = query_db(server_db_temp, """
            SELECT COUNT(*) as count 
            FROM products 
            WHERE lifecycle_stage IN ('assessed_approved', 'assessed_rejected')
            AND assessed_at IS NOT NULL
        """)[0]['count']
        
        print(f"  📝 Pending reviews: {server_pending}")
        if server_pending_by_retailer:
            for row in server_pending_by_retailer:
                print(f"     - {row['retailer']}: {row['count']}")
        
        print(f"  ✅ Total assessed (all time): {server_assessments}")
        print()
        
        # Query server for recent assessments (not yet synced locally)
        recent_assessments = query_db(server_db_temp, """
            SELECT 
                url,
                lifecycle_stage,
                assessed_at,
                modesty_status
            FROM products
            WHERE lifecycle_stage IN ('assessed_approved', 'assessed_rejected')
            AND assessed_at IS NOT NULL
            ORDER BY assessed_at DESC
            LIMIT 10
        """)
        
        if recent_assessments:
            print("  🆕 Recent assessments on server:")
            for assessment in recent_assessments[:5]:
                assessed_time = assessment['assessed_at'][:19] if assessment['assessed_at'] else 'Unknown'
                status = "✅" if assessment['lifecycle_stage'] == 'assessed_approved' else "❌"
                url_short = assessment['url'][:50] + "..." if len(assessment['url']) > 50 else assessment['url']
                print(f"     {status} {assessed_time}: {url_short}")
            
            if len(recent_assessments) > 5:
                print(f"     ... and {len(recent_assessments) - 5} more")
        print()
        
        # Query local database
        print("=" * 60)
        print("LOCAL STATUS (Your Laptop)")
        print("=" * 60)
        
        local_pending = query_db(str(LOCAL_DB_PATH), """
            SELECT COUNT(*) as count FROM assessment_queue WHERE status = 'pending'
        """)[0]['count']
        
        local_assessments = query_db(str(LOCAL_DB_PATH), """
            SELECT COUNT(*) as count 
            FROM products 
            WHERE lifecycle_stage IN ('assessed_approved', 'assessed_rejected')
            AND assessed_at IS NOT NULL
        """)[0]['count']
        
        print(f"  📝 Pending reviews: {local_pending}")
        print(f"  ✅ Total assessed: {local_assessments}")
        print()
        
        # Compare and recommend action
        print("=" * 60)
        print("SYNC STATUS")
        print("=" * 60)
        
        assessments_diff = server_assessments - local_assessments
        pending_diff = server_pending - local_pending
        
        if assessments_diff > 0:
            print(f"  ⚠️  SERVER HAS {assessments_diff} MORE ASSESSMENTS")
            print(f"     (You likely assessed products on phone)")
            print(f"     → Run: python3 sync_now.py")
            print()
        
        if pending_diff > 0:
            print(f"  ⚠️  SERVER HAS {pending_diff} MORE PENDING")
            print(f"     (Products added while laptop was off)")
            print(f"     → Run: python3 sync_now.py")
            print()
        
        if pending_diff < 0:
            print(f"  ⚠️  LOCAL HAS {abs(pending_diff)} MORE PENDING")
            print(f"     (Local changes not yet synced to server)")
            print(f"     → Run: python3 sync_now.py")
            print()
        
        if assessments_diff == 0 and pending_diff == 0:
            print(f"  ✅ LOCAL AND SERVER ARE IN SYNC")
            print(f"     No sync needed")
            print()
        
        # Clean up temp file
        os.unlink(server_db_temp)
        
        print("=" * 60)
        print("You can now:")
        print("  • Run catalog monitor: Tell me 'Run catalog monitor for [retailer] [clothing_type]'")
        print("  • Sync databases: python3 sync_now.py")
        print("  • Check website: https://assessmodesty.com/assess.php")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

