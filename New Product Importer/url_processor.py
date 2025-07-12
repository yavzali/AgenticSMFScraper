"""
URL Processor - Handles URL validation, retailer detection, and routing.
"""

# Add shared path for imports
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../Shared"))
sys.path.append(os.path.dirname(__file__))

import re
import time
from urllib.parse import urlparse
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

from logger_config import setup_logging
from duplicate_detector import DuplicateDetector

logger = setup_logging(__name__)

@dataclass
class ProcessedURL:
    url: str
    retailer: str
    clean_url: str
    modesty_level: str
    is_duplicate: bool = False
    duplicate_action: str = None
    existing_product_id: Optional[int] = None

class URLProcessor:
    def __init__(self):
        self.duplicate_detector = DuplicateDetector()
        self.rate_limiters = {}
        
        # Retailer domain mapping
        self.retailer_domains = {
            "aritzia.com": "aritzia",
            "asos.com": "asos", 
            "hm.com": "hm",
            "uniqlo.com": "uniqlo",
            "revolve.com": "revolve",
            "mango.com": "mango",
            "anthropologie.com": "anthropologie",
            "abercrombie.com": "abercrombie",
            "nordstrom.com": "nordstrom",
            "urbanoutfitters.com": "urban_outfitters"
        }
        
        # Tracking parameters to remove
        self.tracking_params = [
            'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term',
            'gclid', 'fbclid', 'ref', 'source', 'campaign', 'medium'
        ]
    
    async def process_url(self, url: str, modesty_level: str) -> ProcessedURL:
        """Process a single URL with validation, cleaning, and duplicate detection"""
        try:
            # Validate and clean URL
            clean_url = self._clean_url(url)
            if not self._validate_url(clean_url):
                raise ValueError(f"Invalid URL format: {url}")
            
            # Detect retailer
            retailer = self._detect_retailer(clean_url)
            if not retailer:
                raise ValueError(f"Unsupported retailer: {url}")
            
            # Rate limiting check
            self._check_rate_limit(retailer)
            
            # Check for duplicates
            duplicate_info = await self.duplicate_detector.check_duplicate(clean_url, retailer)
            
            result = ProcessedURL(
                url=url,
                retailer=retailer,
                clean_url=clean_url,
                modesty_level=modesty_level,
                is_duplicate=duplicate_info['is_duplicate'],
                duplicate_action=duplicate_info.get('action'),
                existing_product_id=duplicate_info.get('existing_id')
            )
            
            logger.debug(f"Processed URL: {url} -> {retailer} (duplicate: {result.is_duplicate})")
            return result
            
        except Exception as e:
            logger.error(f"Error processing URL {url}: {e}")
            raise
    
    def _clean_url(self, url: str) -> str:
        """Clean URL by removing tracking parameters and normalizing"""
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        parsed = urlparse(url)
        
        # Remove tracking parameters
        if parsed.query:
            query_params = []
            for param in parsed.query.split('&'):
                if '=' in param:
                    key = param.split('=')[0]
                    if key not in self.tracking_params:
                        query_params.append(param)
            
            query = '&'.join(query_params) if query_params else ''
        else:
            query = ''
        
        # Reconstruct clean URL
        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if query:
            clean_url += f"?{query}"
        
        return clean_url
    
    def _validate_url(self, url: str) -> bool:
        """Validate URL format and accessibility"""
        try:
            parsed = urlparse(url)
            return all([
                parsed.scheme in ['http', 'https'],
                parsed.netloc,
                len(url) < 2000,  # Reasonable URL length
                not any(char in url for char in ['<', '>', '"', ' '])  # No invalid chars
            ])
        except Exception:
            return False
    
    def _detect_retailer(self, url: str) -> Optional[str]:
        """Detect retailer from URL domain"""
        try:
            domain = urlparse(url).netloc.lower()
            
            # Remove www. prefix
            if domain.startswith('www.'):
                domain = domain[4:]
            
            # Direct domain match
            if domain in self.retailer_domains:
                return self.retailer_domains[domain]
            
            # Subdomain match (e.g., shop.domain.com)
            for retailer_domain, retailer in self.retailer_domains.items():
                if domain.endswith(retailer_domain):
                    return retailer
            
            return None
            
        except Exception as e:
            logger.error(f"Error detecting retailer for {url}: {e}")
            return None
    
    def _check_rate_limit(self, retailer: str):
        """Check and enforce rate limiting per retailer"""
        current_time = time.time()
        
        if retailer not in self.rate_limiters:
            self.rate_limiters[retailer] = {
                'last_request': 0,
                'request_count': 0,
                'window_start': current_time
            }
        
        limiter = self.rate_limiters[retailer]
        
        # Rate limits per retailer (requests per second)
        rate_limits = {
            'aritzia': 0.5,    # 1 request per 2 seconds
            'asos': 0.67,      # 1 request per 1.5 seconds
            'hm': 0.5,         # 1 request per 2 seconds
            'uniqlo': 0.56,    # 1 request per 1.8 seconds
            'revolve': 0.83,   # 1 request per 1.2 seconds
            'mango': 0.5,      # 1 request per 2 seconds
            'anthropologie': 0.67,  # 1 request per 1.5 seconds
            'abercrombie': 0.56,    # 1 request per 1.8 seconds
            'nordstrom': 1.0,       # 1 request per 1 second
            'urban_outfitters': 0.67  # 1 request per 1.5 seconds
        }
        
        min_interval = 1 / rate_limits.get(retailer, 0.5)
        time_since_last = current_time - limiter['last_request']
        
        if time_since_last < min_interval:
            sleep_time = min_interval - time_since_last
            logger.debug(f"Rate limiting {retailer}: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)
        
        limiter['last_request'] = time.time()
        limiter['request_count'] += 1
    
    def get_retailer_config(self, retailer: str) -> Dict:
        """Get retailer-specific configuration"""
        configs = {
            'aritzia': {
                'base_url': 'aritzia.com',
                'currency': 'CAD',
                'extraction_hints': 'Canadian pricing, TNA/Wilfred/Babaton brands',
                'anti_scraping': True
            },
            'asos': {
                'base_url': 'asos.com',
                'currency': 'USD',
                'extraction_hints': 'Multiple designer brands, sale indicators',
                'anti_scraping': True
            },
            'hm': {
                'base_url': 'hm.com',
                'currency': 'USD',
                'extraction_hints': 'European sizing, conscious collection',
                'anti_scraping': True
            },
            'uniqlo': {
                'base_url': 'uniqlo.com',
                'currency': 'USD',
                'extraction_hints': 'Japanese brand, collaboration collections',
                'anti_scraping': False
            },
            'revolve': {
                'base_url': 'revolve.com',
                'currency': 'USD',
                'extraction_hints': 'Designer brands, revolve exclusive',
                'anti_scraping': True
            },
            'mango': {
                'base_url': 'mango.com',
                'currency': 'USD',
                'extraction_hints': 'European brand, outlet pricing',
                'anti_scraping': False
            },
            'anthropologie': {
                'base_url': 'anthropologie.com',
                'currency': 'USD',
                'extraction_hints': 'Anthropologie/Free People brands',
                'anti_scraping': True
            },
            'abercrombie': {
                'base_url': 'abercrombie.com',
                'currency': 'USD',
                'extraction_hints': 'A&F/Abercrombie Kids, clearance pricing',
                'anti_scraping': True
            },
            'nordstrom': {
                'base_url': 'nordstrom.com',
                'currency': 'USD',
                'extraction_hints': 'Designer brands, compare-at pricing',
                'anti_scraping': True
            },
            'urban_outfitters': {
                'base_url': 'urbanoutfitters.com',
                'currency': 'USD',
                'extraction_hints': 'UO exclusive, multiple brands',
                'anti_scraping': True
            }
        }
        
        return configs.get(retailer, {})
    
    def get_processing_stats(self) -> Dict:
        """Get processing statistics"""
        return {
            'rate_limiters': {k: v['request_count'] for k, v in self.rate_limiters.items()},
            'supported_retailers': list(self.retailer_domains.values())
        }