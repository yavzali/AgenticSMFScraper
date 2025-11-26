"""
Bright Data API Client

Handles all HTTP communication with Bright Data Web Unlocker
"""

import aiohttp
import asyncio
import logging
from typing import Optional, Dict
from datetime import datetime
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from Shared.logger_config import setup_logging
from commercial_config import CommercialAPIConfig

logger = setup_logging(__name__)

class BrightDataClient:
    """
    Bright Data API Client for Web Unlocker
    
    Features:
    - Fetch HTML via proxy with API key authentication
    - Automatic retry with exponential backoff
    - Request logging and cost tracking
    - Error detection and handling
    - Session management
    
    Usage:
        client = BrightDataClient()
        html = await client.fetch_html(url, 'nordstrom', 'product')
        await client.close()
    """
    
    def __init__(self):
        self.config = CommercialAPIConfig()
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Statistics tracking
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.total_cost = 0.0
        self.total_bytes_downloaded = 0
        
        # Per-retailer statistics
        self.retailer_stats = {}
        
        logger.info("✅ Bright Data client initialized")
        logger.info(f"📍 Proxy: {self.config.BRIGHTDATA_PROXY_HOST}:{self.config.BRIGHTDATA_PROXY_PORT}")
    
    async def _ensure_session(self):
        """Create aiohttp session if not exists"""
        if self.session is None or self.session.closed:
            # Create session with timeout
            timeout = aiohttp.ClientTimeout(
                total=self.config.REQUEST_TIMEOUT_SECONDS,
                connect=10,
                sock_read=self.config.REQUEST_TIMEOUT_SECONDS
            )
            self.session = aiohttp.ClientSession(timeout=timeout)
            logger.debug("🔌 Created new aiohttp session")
    
    async def fetch_html(
        self,
        url: str,
        retailer: str,
        page_type: str = 'product'
    ) -> str:
        """
        Fetch HTML from URL using Bright Data Web Unlocker
        
        Args:
            url: Target URL to scrape
            retailer: Retailer name (for logging and stats)
            page_type: 'product' or 'catalog'
        
        Returns:
            Raw HTML string (ready for BeautifulSoup parsing)
        
        Raises:
            Exception: If all retries fail
        
        Process:
        1. Try to fetch with retries (exponential backoff)
        2. Validate HTML (not error page)
        3. Track statistics and cost
        4. Log results
        """
        await self._ensure_session()
        
        logger.info(
            f"🌐 Bright Data fetch: {page_type.upper()} "
            f"{url[:70]}... ({retailer})"
        )
        
        # Initialize retailer stats if needed
        if retailer not in self.retailer_stats:
            self.retailer_stats[retailer] = {
                'requests': 0,
                'successes': 0,
                'failures': 0,
                'cost': 0.0
            }
        
        # Try with retries
        last_exception = None
        for attempt in range(1, self.config.MAX_RETRIES + 1):
            try:
                html = await self._fetch_with_proxy(url, retailer, page_type, attempt)
                
                # Success! Update stats
                self.total_requests += 1
                self.successful_requests += 1
                self.retailer_stats[retailer]['requests'] += 1
                self.retailer_stats[retailer]['successes'] += 1
                
                # Track cost ($1.50 per 1,000 requests)
                request_cost = self.config.COST_PER_1000_REQUESTS / 1000
                self.total_cost += request_cost
                self.retailer_stats[retailer]['cost'] += request_cost
                
                # Track bytes
                html_size = len(html.encode('utf-8'))
                self.total_bytes_downloaded += html_size
                
                logger.info(
                    f"✅ Bright Data SUCCESS: "
                    f"{html_size:,} bytes, "
                    f"${request_cost:.4f}, "
                    f"attempt {attempt}/{self.config.MAX_RETRIES}"
                )
                
                return html
            
            except Exception as e:
                last_exception = e
                logger.warning(
                    f"⚠️ Bright Data attempt {attempt}/{self.config.MAX_RETRIES} failed: {e}"
                )
                
                if attempt < self.config.MAX_RETRIES:
                    # Exponential backoff
                    wait_time = self.config.RETRY_BASE_DELAY ** attempt
                    logger.info(f"🔄 Retrying in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
        
        # All retries failed
        self.total_requests += 1
        self.failed_requests += 1
        self.retailer_stats[retailer]['requests'] += 1
        self.retailer_stats[retailer]['failures'] += 1
        
        logger.error(
            f"❌ Bright Data FAILED after {self.config.MAX_RETRIES} attempts: "
            f"{url[:70]}..."
        )
        
        raise Exception(
            f"Bright Data fetch failed after {self.config.MAX_RETRIES} attempts: "
            f"{last_exception}"
        )
    
    def _get_expect_selector(self, retailer: str) -> str:
        """
        Get CSS selector for JavaScript rendering wait
        
        Bright Data will wait for this element to appear before returning HTML.
        This ensures JavaScript-loaded content is fully rendered.
        
        Based on Bright Data documentation:
        https://docs.brightdata.com/scraping-automation/web-unlocker/request-response/expect-elements
        
        Args:
            retailer: Retailer name (e.g., 'nordstrom', 'anthropologie')
        
        Returns:
            JSON string with element selector for x-unblock-expect header
        """
        selectors = {
            'nordstrom': '{"element": "a[data-testid=\'product-link\']"}',
            'anthropologie': '{"element": "a[href*=\'/shop/\']"}',
            'urban_outfitters': '{"element": "a[href*=\'/products/\']"}',
            'urbanoutfitters': '{"element": "a[href*=\'/products/\']"}',  # Alias
            'abercrombie': '{"element": "a[data-testid=\'product-card-link\']"}',
            'aritzia': '{"element": "div[class*=\'product-tile\']"}',
            'hm': '{"element": "article[class*=\'product\']"}',
            'h&m': '{"element": "article[class*=\'product\']"}',  # Alias
        }
        
        # Get selector for retailer (case-insensitive)
        retailer_lower = retailer.lower().replace(' ', '').replace('&', '')
        selector = selectors.get(retailer_lower, '{"element": "a[href]"}')
        
        logger.debug(f"🎯 x-unblock-expect selector for {retailer}: {selector}")
        
        return selector
    
    async def _fetch_with_proxy(
        self,
        url: str,
        retailer: str,
        page_type: str,
        attempt: int
    ) -> str:
        """
        Internal: Fetch HTML using Bright Data HTTP Proxy
        
        Bright Data HTTP Proxy (Web Unlocker):
        - Proxy server: brd.superproxy.io:33335
        - Authentication: Username = zone credentials, Password = zone password
        - Proxy handles all anti-bot bypass automatically
        - Format: http://username:password@host:port
        """
        # Construct proxy URL with authentication
        # Format: http://username:password@host:port
        proxy_url = (
            f"http://{self.config.BRIGHTDATA_USERNAME}:"
            f"{self.config.BRIGHTDATA_PASSWORD}@"
            f"{self.config.BRIGHTDATA_PROXY_HOST}:"
            f"{self.config.BRIGHTDATA_PROXY_PORT}"
        )
        
        # Headers with JavaScript rendering support (x-unblock-expect)
        # Bright Data will wait for the specified element to appear before returning HTML
        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            ),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'x-unblock-expect': self._get_expect_selector(retailer),  # JavaScript rendering
        }
        
        try:
            logger.debug(f"📡 Sending request via Bright Data HTTP Proxy (attempt {attempt})")
            logger.debug(f"   Proxy: {self.config.BRIGHTDATA_PROXY_HOST}:{self.config.BRIGHTDATA_PROXY_PORT}")
            logger.debug(f"   URL: {url[:70]}...")
            logger.info(f"🎯 JavaScript rendering enabled with x-unblock-expect header")
            
            async with self.session.get(
                url,
                proxy=proxy_url,
                headers=headers,
                ssl=False,  # Bright Data handles SSL termination
                allow_redirects=True,
            ) as response:
                
                # Log response status
                logger.debug(f"📥 Bright Data proxy response: HTTP {response.status}")
                
                # Check status code
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Bright Data proxy error {response.status}: {error_text[:500]}")
                    raise Exception(
                        f"HTTP {response.status}: {error_text[:200]}"
                    )
                
                # Get HTML
                html = await response.text()
                logger.debug(f"📥 Received {len(html):,} bytes from Bright Data proxy")
                
                # Check if response is empty
                if not html or len(html) == 0:
                    logger.error("❌ Bright Data proxy returned empty response (0 bytes)")
                    raise Exception("Empty response from Bright Data proxy")
                
                # Validate HTML (not an error page)
                await self._validate_html(html, url, retailer)
                
                return html
        
        except asyncio.TimeoutError:
            raise Exception(
                f"Bright Data proxy timeout after {self.config.REQUEST_TIMEOUT_SECONDS}s"
            )
        
        except aiohttp.ClientError as e:
            raise Exception(f"Bright Data proxy connection error: {e}")
        
        except Exception as e:
            raise Exception(f"Bright Data proxy request failed: {e}")
    
    async def _validate_html(self, html: str, url: str, retailer: str):
        """
        Validate fetched HTML is not an error page
        
        Checks:
        - Minimum length (not empty)
        - Not blocked/CAPTCHA page
        - Contains expected retailer indicators
        """
        html_size = len(html)
        
        # Check minimum size
        if html_size < 1000:
            raise Exception(
                f"HTML too short ({html_size} bytes) - likely error page"
            )
        
        html_lower = html.lower()
        
        # Check for common error indicators (but be careful with false positives)
        # Only fail if these appear in suspicious contexts (not in meta tags)
        critical_error_indicators = [
            'access denied',
            'you have been blocked',
            'captcha',
            'security check required',
            'unusual traffic detected',
            'verification required',
            '403 forbidden',
            '503 service unavailable',
            'please verify you are a human',
            'cloudflare',  # Only if blocking, not just using Cloudflare
        ]
        
        for indicator in critical_error_indicators:
            if indicator in html_lower:
                # Check if it's in an error context (not just meta tags)
                if 'access denied' in indicator or 'blocked' in indicator or 'captcha' in indicator:
                    logger.warning(
                        f"⚠️ HTML contains potential error indicator: '{indicator}'"
                    )
                    raise Exception(
                        f"HTML contains error indicator: '{indicator}'"
                    )
        
        # Check for retailer-specific indicators (basic validation)
        retailer_indicators = {
            'nordstrom': ['nordstrom', 'data-reactroot', 'product'],
            'anthropologie': ['anthropologie', 'product', 'anf'],
            'revolve': ['revolve', 'revolveassets', 'product'],
            'aritzia': ['aritzia', 'product', 'productinfo'],
            # Add others as needed
        }
        
        if retailer in retailer_indicators:
            indicators = retailer_indicators[retailer]
            found = any(ind in html_lower for ind in indicators)
            if not found:
                logger.warning(
                    f"⚠️ HTML missing expected retailer indicators: {indicators}"
                )
                # Don't fail, just warn (might be legitimate page)
        
        logger.debug(f"✅ HTML validation passed ({html_size:,} bytes)")
    
    def get_usage_stats(self) -> Dict:
        """
        Get usage statistics
        
        Returns:
            Dict with overall and per-retailer statistics
        """
        return {
            'total_requests': self.total_requests,
            'successful_requests': self.successful_requests,
            'failed_requests': self.failed_requests,
            'success_rate': (
                self.successful_requests / max(self.total_requests, 1)
            ),
            'total_cost': self.total_cost,
            'avg_cost_per_request': (
                self.total_cost / max(self.total_requests, 1)
            ),
            'total_bytes': self.total_bytes_downloaded,
            'retailer_stats': self.retailer_stats,
        }
    
    def log_usage_summary(self):
        """Log summary of usage statistics"""
        stats = self.get_usage_stats()
        
        logger.info("=" * 60)
        logger.info("📊 BRIGHT DATA USAGE SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total Requests: {stats['total_requests']}")
        logger.info(f"Successful: {stats['successful_requests']}")
        logger.info(f"Failed: {stats['failed_requests']}")
        logger.info(f"Success Rate: {stats['success_rate']*100:.1f}%")
        logger.info(f"Total Cost: ${stats['total_cost']:.2f}")
        logger.info(f"Avg Cost/Request: ${stats['avg_cost_per_request']:.4f}")
        logger.info(f"Total Data: {stats['total_bytes']/1024/1024:.1f} MB")
        
        if stats['retailer_stats']:
            logger.info("-" * 60)
            logger.info("Per-Retailer Stats:")
            for retailer, rstats in stats['retailer_stats'].items():
                success_rate = (
                    rstats['successes'] / max(rstats['requests'], 1)
                ) * 100
                logger.info(
                    f"  {retailer}: "
                    f"{rstats['requests']} requests, "
                    f"{success_rate:.1f}% success, "
                    f"${rstats['cost']:.2f}"
                )
        
        logger.info("=" * 60)
    
    async def close(self):
        """Clean up resources and log final statistics"""
        # Log summary
        self.log_usage_summary()
        
        # Close session
        if self.session and not self.session.closed:
            await self.session.close()
            logger.debug("🔌 Closed aiohttp session")
        
        logger.info("✅ Bright Data client closed")

