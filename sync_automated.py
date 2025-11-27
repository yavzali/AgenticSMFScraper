#!/usr/bin/env python3
"""
Automated Database Sync (No Prompts)
Runs two-way sync: pull assessments from server, then push local DB
"""

import sys
import logging
from pathlib import Path

# Add Shared to path
sys.path.insert(0, str(Path(__file__).parent / 'Shared'))

from database_sync import DatabaseSync

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def main():
    print("=" * 60)
    print("🔄 AUTOMATED DATABASE SYNC (TWO-WAY)")
    print("=" * 60)
    print()
    print("Running:")
    print("  1. Pull assessments from server → merge into local")
    print("  2. Push local database → upload to server")
    print()
    
    # Run sync without prompt
    sync = DatabaseSync()
    success = sync.sync_to_server(
        create_backup=True,
        verify=True,
        pull_first=True  # Two-way sync enabled
    )
    
    if success:
        print()
        print("=" * 60)
        print("✅ SYNC COMPLETE")
        print("=" * 60)
        print()
        print("📊 Local and server databases are now synchronized")
        print("🌐 Visit https://assessmodesty.com/assess.php to verify")
        return 0
    else:
        print()
        print("=" * 60)
        print("❌ SYNC FAILED")
        print("=" * 60)
        print()
        print("Check logs above for details")
        return 1

if __name__ == '__main__':
    sys.exit(main())

