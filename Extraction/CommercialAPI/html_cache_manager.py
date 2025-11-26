"""
HTML Cache Manager

1-day caching of fetched HTML for debugging purposes
"""

import aiosqlite
import hashlib
import logging
from typing import Optional
from datetime import datetime, timedelta
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from Shared.logger_config import setup_logging
from commercial_config import CommercialAPIConfig

logger = setup_logging(__name__)

class HTMLCacheManager:
    """
    HTML Cache Manager
    
    Features:
    - 1-day caching of fetched HTML (debugging only)
    - SQLite storage
    - Automatic expiration
    - Cache statistics
    
    Purpose:
    - Avoid repeated Bright Data requests during development
    - Save costs during testing
    - Speed up iteration
    
    Usage:
        cache = HTMLCacheManager()
        
        # Try to get from cache
        html = await cache.get(url, 'nordstrom')
        if not html:
            # Not cached, fetch and store
            html = await brightdata_client.fetch_html(url, 'nordstrom')
            await cache.set(url, 'nordstrom', html)
    """
    
    def __init__(self):
        self.config = CommercialAPIConfig()
        self.db_path = self.config.HTML_CACHE_DB_PATH
        self.enabled = self.config.HTML_CACHING_ENABLED
        
        # Statistics
        self.cache_hits = 0
        self.cache_misses = 0
        
        if not self.enabled:
            logger.info("⚠️ HTML caching DISABLED")
        else:
            logger.info(f"💾 HTML caching ENABLED (1-day expiration)")
            logger.info(f"📂 Cache DB: {self.db_path}")
    
    async def initialize(self):
        """Initialize cache database"""
        if not self.enabled:
            return
        
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS html_cache (
                        url_hash TEXT PRIMARY KEY,
                        url TEXT NOT NULL,
                        retailer TEXT NOT NULL,
                        html TEXT NOT NULL,
                        cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        accessed_count INTEGER DEFAULT 0,
                        last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Create index for faster lookups
                await db.execute('''
                    CREATE INDEX IF NOT EXISTS idx_cached_at 
                    ON html_cache(cached_at)
                ''')
                
                await db.commit()
            
            logger.debug("✅ HTML cache database initialized")
        
        except Exception as e:
            logger.error(f"❌ Failed to initialize HTML cache: {e}")
            self.enabled = False
    
    def _hash_url(self, url: str) -> str:
        """Generate hash for URL (for primary key)"""
        return hashlib.sha256(url.encode('utf-8')).hexdigest()
    
    async def get(self, url: str, retailer: str) -> Optional[str]:
        """
        Get HTML from cache if exists and not expired
        
        Returns:
            HTML string if found and fresh, None otherwise
        """
        if not self.enabled:
            return None
        
        try:
            url_hash = self._hash_url(url)
            expiration_time = datetime.now() - timedelta(
                hours=self.config.HTML_CACHE_DURATION_HOURS
            )
            
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    '''
                    SELECT html, cached_at, accessed_count 
                    FROM html_cache 
                    WHERE url_hash = ? AND cached_at > ?
                    ''',
                    (url_hash, expiration_time.isoformat())
                )
                row = await cursor.fetchone()
                
                if row:
                    html, cached_at, accessed_count = row
                    
                    # Update access stats
                    await db.execute(
                        '''
                        UPDATE html_cache 
                        SET accessed_count = accessed_count + 1,
                            last_accessed = CURRENT_TIMESTAMP
                        WHERE url_hash = ?
                        ''',
                        (url_hash,)
                    )
                    await db.commit()
                    
                    # Statistics
                    self.cache_hits += 1
                    
                    logger.info(
                        f"💾 CACHE HIT: {url[:70]}... "
                        f"(cached {cached_at}, accessed {accessed_count + 1} times)"
                    )
                    
                    return html
                else:
                    # Cache miss
                    self.cache_misses += 1
                    logger.debug(f"❌ Cache miss: {url[:70]}...")
                    return None
        
        except Exception as e:
            logger.warning(f"⚠️ Cache get failed: {e}")
            return None
    
    async def set(self, url: str, retailer: str, html: str):
        """
        Store HTML in cache
        
        Args:
            url: Source URL
            retailer: Retailer name
            html: HTML content to cache
        """
        if not self.enabled:
            return
        
        try:
            url_hash = self._hash_url(url)
            html_size = len(html.encode('utf-8'))
            
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    '''
                    INSERT OR REPLACE INTO html_cache 
                    (url_hash, url, retailer, html, cached_at, accessed_count, last_accessed)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, 0, CURRENT_TIMESTAMP)
                    ''',
                    (url_hash, url, retailer, html)
                )
                await db.commit()
            
            logger.debug(
                f"💾 Cached HTML: {url[:70]}... "
                f"({html_size:,} bytes, retailer: {retailer})"
            )
        
        except Exception as e:
            logger.warning(f"⚠️ Cache set failed: {e}")
    
    async def cleanup_expired(self):
        """Remove expired cache entries"""
        if not self.enabled:
            return
        
        try:
            expiration_time = datetime.now() - timedelta(
                hours=self.config.HTML_CACHE_DURATION_HOURS
            )
            
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    'DELETE FROM html_cache WHERE cached_at < ?',
                    (expiration_time.isoformat(),)
                )
                deleted_count = cursor.rowcount
                await db.commit()
            
            if deleted_count > 0:
                logger.info(f"🗑️ Removed {deleted_count} expired cache entries")
        
        except Exception as e:
            logger.warning(f"⚠️ Cache cleanup failed: {e}")
    
    async def clear_all(self):
        """Clear entire cache (for testing)"""
        if not self.enabled:
            return
        
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('DELETE FROM html_cache')
                await db.commit()
            
            logger.info("🗑️ Cleared entire HTML cache")
        
        except Exception as e:
            logger.warning(f"⚠️ Cache clear failed: {e}")
    
    async def get_stats(self) -> dict:
        """Get cache statistics"""
        if not self.enabled:
            return {}
        
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Total entries
                cursor = await db.execute('SELECT COUNT(*) FROM html_cache')
                total_entries = (await cursor.fetchone())[0]
                
                # Total size
                cursor = await db.execute('SELECT SUM(LENGTH(html)) FROM html_cache')
                total_bytes = (await cursor.fetchone())[0] or 0
                
                # Most accessed
                cursor = await db.execute(
                    '''
                    SELECT url, accessed_count 
                    FROM html_cache 
                    ORDER BY accessed_count DESC 
                    LIMIT 5
                    '''
                )
                most_accessed = await cursor.fetchall()
            
            hit_rate = (
                self.cache_hits / max(self.cache_hits + self.cache_misses, 1)
            ) * 100
            
            return {
                'enabled': self.enabled,
                'total_entries': total_entries,
                'total_size_mb': total_bytes / 1024 / 1024,
                'cache_hits': self.cache_hits,
                'cache_misses': self.cache_misses,
                'hit_rate': hit_rate,
                'most_accessed': most_accessed,
            }
        
        except Exception as e:
            logger.warning(f"⚠️ Failed to get cache stats: {e}")
            return {}
    
    async def log_stats(self):
        """Log cache statistics"""
        stats = await self.get_stats()
        
        if not stats:
            return
        
        logger.info("=" * 60)
        logger.info("💾 HTML CACHE STATISTICS")
        logger.info("=" * 60)
        logger.info(f"Total Entries: {stats['total_entries']}")
        logger.info(f"Total Size: {stats['total_size_mb']:.1f} MB")
        logger.info(f"Cache Hits: {stats['cache_hits']}")
        logger.info(f"Cache Misses: {stats['cache_misses']}")
        logger.info(f"Hit Rate: {stats['hit_rate']:.1f}%")
        
        if stats['most_accessed']:
            logger.info("-" * 60)
            logger.info("Most Accessed URLs:")
            for url, count in stats['most_accessed']:
                logger.info(f"  {count}× {url[:60]}...")
        
        logger.info("=" * 60)

