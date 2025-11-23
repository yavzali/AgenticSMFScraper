#!/usr/bin/env python3
"""
Database Sync Module
Syncs local products.db to web server for assessment pipeline
"""

import paramiko
from scp import SCPClient
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple
import os

logger = logging.getLogger(__name__)


class DatabaseSync:
    """
    Handles syncing local products.db to web server
    Used by catalog monitoring workflow to keep assessment pipeline updated
    """
    
    def __init__(self, local_db_path: Optional[str] = None):
        """
        Initialize database sync
        
        Args:
            local_db_path: Path to local database (defaults to Shared/products.db)
        """
        if local_db_path is None:
            # Default to Shared/products.db
            self.local_db_path = Path(__file__).parent / "products.db"
        else:
            self.local_db_path = Path(local_db_path)
        
        # Server configuration
        self.server_ip = "167.172.148.145"
        self.server_user = "root"
        self.server_password = "modestyassessor"
        self.remote_db_path = "/var/www/html/web_assessment/data/products.db"
        
        logger.info(f"DatabaseSync initialized: {self.local_db_path} -> {self.remote_db_path}")
    
    def validate_local_db(self) -> Tuple[bool, str]:
        """
        Validate local database exists and is accessible
        
        Returns:
            (success, message)
        """
        if not self.local_db_path.exists():
            return False, f"Local database not found: {self.local_db_path}"
        
        if not os.access(self.local_db_path, os.R_OK):
            return False, f"Local database not readable: {self.local_db_path}"
        
        size_mb = self.local_db_path.stat().st_size / (1024 * 1024)
        if size_mb == 0:
            return False, "Local database is empty"
        
        return True, f"Local database valid ({size_mb:.2f} MB)"
    
    def sync_to_server(
        self,
        create_backup: bool = True,
        verify: bool = True
    ) -> bool:
        """
        Sync local database to web server
        
        Args:
            create_backup: Create backup of server DB before overwriting
            verify: Verify upload after completion
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate local database
            valid, message = self.validate_local_db()
            if not valid:
                logger.error(f"❌ Database sync failed: {message}")
                return False
            
            logger.info(f"✅ {message}")
            logger.info("🔌 Connecting to web server...")
            
            # Connect via SSH
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(
                self.server_ip,
                username=self.server_user,
                password=self.server_password,
                timeout=10
            )
            logger.info("✅ Connected to web server")
            
            # Create backup if requested
            if create_backup:
                logger.info("📦 Creating backup of server database...")
                backup_name = f"{self.remote_db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                stdin, stdout, stderr = ssh.exec_command(
                    f"cp {self.remote_db_path} {backup_name} 2>&1 || echo 'No existing file'"
                )
                backup_output = stdout.read().decode()
                
                if "No existing file" in backup_output:
                    logger.info("ℹ️  No existing database to backup (first sync)")
                else:
                    logger.info(f"✅ Backup created: {backup_name}")
            
            # Upload database
            logger.info("📤 Uploading database to server...")
            with SCPClient(ssh.get_transport(), progress=self._progress) as scp:
                scp.put(str(self.local_db_path), self.remote_db_path)
            logger.info("✅ Upload complete")
            
            # Set correct permissions
            logger.info("🔐 Setting file permissions...")
            stdin, stdout, stderr = ssh.exec_command(
                f"chmod 644 {self.remote_db_path} && chown www-data:www-data {self.remote_db_path}"
            )
            stdout.channel.recv_exit_status()  # Wait for completion
            logger.info("✅ Permissions set (644, www-data:www-data)")
            
            # Verify upload if requested
            if verify:
                logger.info("🔍 Verifying upload...")
                stdin, stdout, stderr = ssh.exec_command(f"ls -lh {self.remote_db_path}")
                verify_output = stdout.read().decode().strip()
                logger.info(f"Server file info: {verify_output}")
            
            ssh.close()
            
            logger.info("=" * 60)
            logger.info("✅ DATABASE SYNC COMPLETE")
            logger.info("=" * 60)
            return True
            
        except paramiko.AuthenticationException:
            logger.error("❌ Authentication failed - check credentials")
            return False
        except paramiko.SSHException as e:
            logger.error(f"❌ SSH connection failed: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Database sync failed: {e}")
            return False
    
    def _progress(self, filename, size, sent):
        """Progress callback for SCP upload"""
        if size > 0:
            percent = (sent / size) * 100
            if percent % 25 == 0 or sent == size:  # Log at 25%, 50%, 75%, 100%
                logger.info(f"Upload progress: {percent:.0f}% ({sent}/{size} bytes)")


# Async wrapper for use in async workflows
async def sync_database_async(local_db_path: Optional[str] = None) -> bool:
    """
    Async wrapper for database sync (for use in catalog monitor workflow)
    
    Args:
        local_db_path: Path to local database
        
    Returns:
        True if successful
    """
    import asyncio
    
    def _sync():
        sync = DatabaseSync(local_db_path)
        return sync.sync_to_server()
    
    # Run in thread pool to avoid blocking
    return await asyncio.to_thread(_sync)


if __name__ == "__main__":
    # Manual sync when run directly
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    sync = DatabaseSync()
    success = sync.sync_to_server()
    
    if success:
        print("\n✅ Sync completed successfully!")
        print("Visit https://assessmodesty.com/assess.php to verify")
    else:
        print("\n❌ Sync failed - check logs above")
    
    sys.exit(0 if success else 1)

