"""
Database Sync Utility - Simple sync for future web deployment
"""

import os
import subprocess
import json
from pathlib import Path
from datetime import datetime

from logger_config import setup_logging

logger = setup_logging(__name__)

class DatabaseSync:
    def __init__(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.local_db_path = os.path.join(script_dir, '../Shared/products.db')
        
    def sync_to_server(self, server_host: str, server_user: str, server_path: str) -> bool:
        """Simple sync to server using scp"""
        try:
            # Create backup on server first
            backup_cmd = [
                'ssh', f"{server_user}@{server_host}",
                f"cp {server_path} {server_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')} 2>/dev/null || true"
            ]
            
            # Upload database
            scp_cmd = [
                'scp', self.local_db_path,
                f"{server_user}@{server_host}:{server_path}"
            ]
            
            # Execute backup (ignore errors)
            subprocess.run(backup_cmd, capture_output=True)
            
            # Execute upload
            result = subprocess.run(scp_cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info(f"✅ Database synced to {server_host} successfully")
                return True
            else:
                logger.error(f"Database sync failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Exception during database sync: {e}")
            return False

# Simple function for future integration
def sync_database_to_web():
    """Placeholder for automatic sync after crawling"""
    logger.info("🔄 Database sync to web server (manual configuration required)")
    return True

