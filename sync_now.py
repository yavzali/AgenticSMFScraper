#!/usr/bin/env python3
"""
Manual Database Sync Command

Run this anytime to sync databases:
- Pulls assessments from server (merges into local)
- Pushes local database to server

Usage:
    python3 sync_now.py
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
    print("🔄 MANUAL DATABASE SYNC")
    print("=" * 60)
    print()
    print("This will:")
    print("  1. Pull assessments from server → merge into local")
    print("  2. Push local database → upload to server")
    print()
    
    response = input("Continue? [Y/n]: ").strip().lower()
    if response and response != 'y':
        print("❌ Sync cancelled")
        return
    
    print()
    
    # Run sync
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
        print("Visit https://assessmodesty.com/assess.php to verify")
    else:
        print()
        print("=" * 60)
        print("❌ SYNC FAILED")
        print("=" * 60)
        print()
        print("Check logs above for details")
        sys.exit(1)

if __name__ == '__main__':
    main()

