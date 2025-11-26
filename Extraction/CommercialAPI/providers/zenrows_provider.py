"""
ZenRows Provider
Commercial API client for ZenRows scraping service
"""

import aiohttp
import asyncio
import logging
from typing import Optional, Dict
from datetime import datetime
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
from Shared.logger_config import setup_logging
from Extraction.CommercialAPI.commercial_api_client import CommercialAPIClient

logger = setup_logging(__name__)


class ZenRowsClient(CommercialAPIClient):
    """
    ZenRows API Client
    
    Features:
    - JavaScript rendering with headless browser
    - Premium residential proxies
    - Anti-bot bypass (CAPTCHA solving, PerimeterX, Cloudflare, Akamai)
    - Automatic retries with exponential backoff
    - Cost tracking and usage statistics
    
    ZenRows Documentation:
    https://docs.zenrows.com/universal-scraper-api/
    """
    
    def __init__(self, config):
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Statistics tracking
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.total_cost = 0.0
        self.total_bytes_downloaded = 0
        
        # Per-retailer statistics
        self.retailer_stats = {}
        
        logger.info("✅ ZenRows client initialized")
        logger.info(f"📍 API Endpoint: {config.ZENROWS_API_ENDPOINT}")
        logger.info(f"🔑 API Key: {config.ZENROWS_API_KEY[:10]}...{config.ZENROWS_API_KEY[-4:]}")
    
    async def initialize(self):
        """Initialize aiohttp session"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(
                total=self.config.REQUEST_TIMEOUT_SECONDS,
                connect=15,
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
        Fetch HTML from URL using ZenRows API
        
        Args:
            url: Target URL to scrape
            retailer: Retailer name (for logging and stats)
            page_type: Type of page ('product' or 'catalog')
        
        Returns:
            Raw HTML string (ready for BeautifulSoup parsing)
        
        Raises:
            Exception: If all retries fail
        """
        await self.initialize()
        
        logger.info(
            f"🌐 ZenRows fetch: {page_type.upper()} "
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
                html = await self._fetch_with_zenrows(url, retailer, page_type, attempt)
                
                # Success! Update stats
                self.total_requests += 1
                self.successful_requests += 1
                self.retailer_stats[retailer]['requests'] += 1
                self.retailer_stats[retailer]['successes'] += 1
                
                # Track cost (ZenRows pricing: ~$0.01 per request with js_render + premium_proxy)
                request_cost = self.config.COST_PER_REQUEST
                self.total_cost += request_cost
                self.retailer_stats[retailer]['cost'] += request_cost
                
                # Track bytes
                html_size = len(html.encode('utf-8'))
                self.total_bytes_downloaded += html_size
                
                logger.info(
                    f"✅ ZenRows SUCCESS: "
                    f"{html_size:,} bytes, "
                    f"${request_cost:.4f}, "
                    f"attempt {attempt}/{self.config.MAX_RETRIES}"
                )
                
                return html
            
            except Exception as e:
                last_exception = e
                logger.warning(
                    f"⚠️ ZenRows attempt {attempt}/{self.config.MAX_RETRIES} failed: {e}"
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
            f"❌ ZenRows FAILED after {self.config.MAX_RETRIES} attempts: "
            f"{url[:70]}..."
        )
        
        raise Exception(
            f"ZenRows fetch failed after {self.config.MAX_RETRIES} attempts: "
            f"{last_exception}"
        )
    
    async def _fetch_with_zenrows(
        self,
        url: str,
        retailer: str,
        page_type: str,
        attempt: int
    ) -> str:
        """
        Internal: Fetch HTML using ZenRows API
        
        ZenRows API Parameters:
        - url: Target URL to scrape
        - apikey: Your ZenRows API key
        - js_render: 'true' - JavaScript rendering (essential for anti-bot)
        - premium_proxy: 'true' - Residential IPs (essential for anti-bot)
        - proxy_country: 'us' - Use US proxies for US retailers
        - wait: milliseconds - Wait after page load (optional)
        - wait_for: CSS selector - Wait for element (optional)
        """
        # Build query parameters
        params = {
            'url': url,
            'apikey': self.config.ZENROWS_API_KEY,
            'js_render': 'true',       # JavaScript rendering (headless browser)
            'premium_proxy': 'true',   # Residential IPs
            'proxy_country': 'us',     # US proxies for US retailers
        }
        
        # Dynamic content loading: Wait for product grids (lesson from Patchright)
        if page_type == 'catalog':
            # Get wait_for selector (waits for specific element to appear)
            wait_selector = self._get_wait_selector(retailer)
            if wait_selector:
                params['wait_for'] = wait_selector
                logger.info(f"🎯 wait_for: {wait_selector}")
            
            # Add fixed wait for stability (5-8 seconds recommended for dynamic content)
            wait_time = self._get_wait_time(retailer)
            if wait_time:
                params['wait'] = wait_time
                logger.info(f"⏱️  wait: {wait_time}ms")
        
        try:
            logger.debug(f"📡 Sending request to ZenRows API (attempt {attempt})")
            logger.debug(f"   URL: {url[:70]}...")
            logger.debug(f"   JS Render: {params['js_render']}")
            logger.debug(f"   Premium Proxy: {params['premium_proxy']}")
            
            async with self.session.get(
                self.config.ZENROWS_API_ENDPOINT,
                params=params,
                ssl=True,
            ) as response:
                # Log response status
                logger.debug(f"📥 ZenRows API response: HTTP {response.status}")
                
                # Check status code
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"ZenRows API error {response.status}: {error_text[:500]}")
                    raise Exception(
                        f"HTTP {response.status}: {error_text[:200]}"
                    )
                
                # Get HTML
                html = await response.text()
                logger.debug(f"📥 Received {len(html):,} bytes from ZenRows API")
                
                # Check if response is empty
                if not html or len(html) == 0:
                    logger.error("❌ ZenRows API returned empty response (0 bytes)")
                    raise Exception("Empty response from ZenRows API")
                
                # Validate HTML (not an error page)
                await self._validate_html(html, url, retailer)
                
                return html
        
        except asyncio.TimeoutError:
            raise Exception(
                f"ZenRows API timeout after {self.config.REQUEST_TIMEOUT_SECONDS}s"
            )
        
        except aiohttp.ClientError as e:
            raise Exception(f"ZenRows API connection error: {e}")
        
        except Exception as e:
            raise Exception(f"ZenRows API request failed: {e}")
    
    def _get_wait_selector(self, retailer: str) -> Optional[str]:
        """
        Get CSS selector to wait for (dynamic waiting)
        
        This tells ZenRows to wait for a specific element to appear
        before returning the HTML. Waits up to 30 seconds for element.
        
        Based on actual product card selectors from each retailer's HTML.
        """
        wait_selectors = {
            # Nordstrom: Wait for product link cards (data-testid attribute)
            'nordstrom': 'a[data-testid="product-link"]',
            
            # Anthropologie: Wait for product shop links
            'anthropologie': 'a[href*="/shop/"]',
            
            # Urban Outfitters: Wait for product shop links (FIXED with correct URL!)
            'urban_outfitters': 'a[href*="/shop/"]',
            'urbanoutfitters': 'a[href*="/shop/"]',
            
            # Abercrombie: Wait for product card links (data-testid)
            'abercrombie': 'a[href*="/shop/us/p/"]',
            
            # Aritzia: Wait for product links (Patchright's primary selector)
            # Cloudflare + SPA - products load via API with variable 1-15s delay
            'aritzia': 'a[href*="/product/"]',
            
            # H&M: Wait for product page links (Patchright's selector)
            # High anti-bot complexity, may be blocked
            'hm': 'a[href*="/productpage"]',
            'h&m': 'a[href*="/productpage"]',
        }
        
        retailer_lower = retailer.lower().replace(' ', '').replace('&', '')
        return wait_selectors.get(retailer_lower)
    
    def _get_wait_time(self, retailer: str) -> Optional[int]:
        """
        Get fixed wait time in milliseconds (stability wait)
        
        ZenRows docs recommend 5000-8000ms for dynamic content.
        Use after wait_for to ensure all products have loaded.
        
        Returns:
            Milliseconds to wait, or None for no fixed wait
        """
        # Wait times in milliseconds (5-20 seconds based on Patchright's proven timings)
        wait_times = {
            # Nordstrom: Heavy JavaScript, needs 8s for product grid to fully load
            'nordstrom': 8000,
            
            # Anthropologie: PerimeterX + dynamic loading, needs 7s
            'anthropologie': 7000,
            
            # Aritzia: Cloudflare + React SPA with VARIABLE API delay (1-15s)
            # Patchright uses active polling up to 30s - we need maximum wait
            'aritzia': 30000,  # 30 seconds (MAXIMUM) to handle worst-case 15s+ API delay
            
            # Urban Outfitters: PerimeterX (same as Anthropologie), needs 7s
            'urban_outfitters': 7000,
            'urbanoutfitters': 7000,
            
            # Abercrombie: Medium complexity, needs 6s
            'abercrombie': 6000,
            
            # H&M: HIGH anti-bot complexity, may be blocked entirely
            # Patchright shows "Access Denied" - try longer wait
            'hm': 15000,  # 15 seconds to give maximum time
            'h&m': 15000,
        }
        
        retailer_lower = retailer.lower().replace(' ', '').replace('&', '')
        return wait_times.get(retailer_lower)
    
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
        
        # Check for ACTUAL error indicators (not JavaScript variable names)
        # Based on Patchright's validation approach - check for real error messages
        critical_error_phrases = [
            'access denied',
            'you have been blocked',
            'security check required',
            'unusual traffic detected',
            'verification required',
            'please verify you are a human',
            'captcha challenge',
            'we apologize',  # Common in error pages
        ]
        
        for phrase in critical_error_phrases:
            if phrase in html_lower:
                logger.warning(
                    f"⚠️ HTML may contain error message: '{phrase}'"
                )
                # Only fail if we also have a small HTML size (likely error page)
                # Large HTML (>500KB) with these phrases is likely legitimate content
                if html_size < 500000:  # 500 KB threshold
                    raise Exception(
                        f"HTML contains error indicator: '{phrase}' (size: {html_size:,} bytes)"
                    )
        
        # Check for retailer-specific indicators (basic validation)
        retailer_indicators = {
            'nordstrom': ['nordstrom', 'data-reactroot', 'product'],
            'anthropologie': ['anthropologie', 'product', 'anf'],
            'revolve': ['revolve', 'revolveassets', 'product'],
            'aritzia': ['aritzia', 'product', 'productinfo'],
            'hm': ['h&m', 'hm.com', 'product'],
            'abercrombie': ['abercrombie', 'product', 'anf'],
            'urban_outfitters': ['urban outfitters', 'urbanoutfitters', 'product'],
            'urbanoutfitters': ['urban outfitters', 'urbanoutfitters', 'product'],
            'asos': ['asos', 'product'],
            'mango': ['mango', 'product'],
            'uniqlo': ['uniqlo', 'product'],
        }
        
        retailer_lower = retailer.lower().replace(' ', '').replace('&', '')
        if retailer_lower in retailer_indicators:
            indicators = retailer_indicators[retailer_lower]
            found = any(ind in html_lower for ind in indicators)
            if not found:
                logger.warning(
                    f"⚠️ HTML missing expected retailer indicators: {indicators}"
                )
                # Don't fail, just warn (might be legitimate page)
        
        logger.debug(f"✅ HTML validation passed ({html_size:,} bytes)")
    
    def get_usage_stats(self) -> Dict:
        """Get usage statistics"""
        return {
            'provider': 'zenrows',
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
        logger.info("📊 ZENROWS USAGE SUMMARY")
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
        
        logger.info("✅ ZenRows client closed")


__all__ = ['ZenRowsClient']

