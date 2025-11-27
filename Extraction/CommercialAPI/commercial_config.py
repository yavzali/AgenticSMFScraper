"""
Commercial API Configuration

Central configuration for Commercial scraping APIs (ZenRows, ScraperAPI, Bright Data, etc.)
Service-agnostic configuration with pluggable providers
"""

import os
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

class CommercialAPIConfig:
    """
    Configuration for Commercial API Extraction Tower
    
    Key Features:
    - Service provider selection (ZenRows, ScraperAPI, Bright Data, etc.)
    - Service-specific credentials and settings
    - Retailer routing (which retailers use this tower)
    - HTML caching configuration (1-day debugging cache)
    - Parsing strategies (BeautifulSoup first, LLM fallback)
    - Pattern learning settings
    - Error handling and fallback configuration
    """
    
    # ============================================
    # PROVIDER SELECTION
    # ============================================
    
    # Active provider: 'zenrows', 'scraperapi', or 'brightdata'
    ACTIVE_PROVIDER = os.getenv('COMMERCIAL_API_PROVIDER', 'zenrows')
    
    # ============================================
    # ZENROWS API CONFIGURATION
    # ============================================
    
    ZENROWS_API_KEY = os.getenv('ZENROWS_API_KEY', '')
    ZENROWS_API_ENDPOINT = 'https://api.zenrows.com/v1/'
    
    # ZenRows pricing: ~$0.01 per request with js_render + premium_proxy
    # Pricing: https://www.zenrows.com/pricing
    # 1,000 API credits = $9 = 100 requests with js_render+premium_proxy
    # ~$0.09 per request, or ~$0.01 with lower settings
    ZENROWS_COST_PER_REQUEST = 0.01  # Approximate cost per request
    
    # ============================================
    # SCRAPERAPI CONFIGURATION
    # ============================================
    
    SCRAPERAPI_KEY = os.getenv('SCRAPERAPI_KEY', '')
    SCRAPERAPI_ENDPOINT = 'http://api.scraperapi.com'
    
    # ScraperAPI pricing: $49/month for 100,000 requests = $0.00049 per request
    SCRAPERAPI_COST_PER_REQUEST = 0.0005
    
    # ============================================
    # BRIGHT DATA API CONFIGURATION (Legacy)
    # ============================================
    
    BRIGHTDATA_API_KEY = os.getenv('BRIGHTDATA_API_KEY', '')
    BRIGHTDATA_PROXY_HOST = "brd.superproxy.io"
    BRIGHTDATA_PROXY_PORT = 33335
    BRIGHTDATA_USERNAME = os.getenv('BRIGHTDATA_USERNAME', '')
    BRIGHTDATA_PASSWORD = os.getenv('BRIGHTDATA_PASSWORD', '')
    
    # Bright Data pricing: $1.50 per 1,000 requests = $0.0015 per request
    BRIGHTDATA_COST_PER_REQUEST = 0.0015
    
    # ============================================
    # COST TRACKING (Provider-agnostic)
    # ============================================
    
    @property
    def COST_PER_REQUEST(self):
        """Get cost per request for active provider"""
        if self.ACTIVE_PROVIDER == 'zenrows':
            return self.ZENROWS_COST_PER_REQUEST
        elif self.ACTIVE_PROVIDER == 'scraperapi':
            return self.SCRAPERAPI_COST_PER_REQUEST
        elif self.ACTIVE_PROVIDER == 'brightdata':
            return self.BRIGHTDATA_COST_PER_REQUEST
        else:
            return 0.01  # Default estimate
    
    # ============================================
    # RETAILER ROUTING CONFIGURATION
    # ============================================
    
    # All retailers that CAN use Commercial API tower
    SUPPORTED_RETAILERS = [
        'nordstrom',           # Phase 1 - ACTIVE NOW
        'anthropologie',       # Phase 2 - PerimeterX
        'urban_outfitters',    # Phase 2 - PerimeterX
        'aritzia',             # Phase 3 - Cloudflare
        'hm',                  # Phase 3 - Basic anti-bot
        'revolve',             # Phase 4 - Migration
        'abercrombie',         # Phase 4 - Migration
        'mango',               # Phase 4 - Migration
        'uniqlo',              # Phase 4 - Migration
        'asos',                # Phase 4 - Migration
    ]
    
    # Retailers CURRENTLY ACTIVE on Commercial API tower
    # Start with Nordstrom only, expand gradually
    # NOTE: Revolve tested successfully (4.3MB HTML, 100 products, 3.3s, $0.0015)
    # but keeping on Markdown tower until final architecture decisions made
    ACTIVE_RETAILERS = [
        'nordstrom',       # ✅ 67 products  - Akamai Bot Manager
        'anthropologie',   # ✅ 78 products  - PerimeterX Press & Hold
        'abercrombie',     # ✅ 180 products - JavaScript rendering
        'hm',              # ✅ 48 products  - "Blocked" false positive
        'aritzia',         # ✅ 84 products  - Cloudflare Turnstile (VERIFIED!)
        'urban_outfitters', # ✅ 72 products - Fixed with correct URL! 🎉
    ]
    
    @classmethod
    def should_use_commercial_api(cls, retailer: str) -> bool:
        """Check if retailer should use Commercial API tower"""
        return retailer.lower() in [r.lower() for r in cls.ACTIVE_RETAILERS]
    
    # ============================================
    # HTML CACHING CONFIGURATION
    # ============================================
    
    # Enable HTML caching (for debugging only)
    HTML_CACHING_ENABLED = True
    
    # Cache duration: 1 day (24 hours) for debugging
    HTML_CACHE_DURATION_HOURS = 24
    
    # Cache database location
    HTML_CACHE_DB_PATH = os.path.join(
        os.path.dirname(__file__),
        'html_cache.db'
    )
    
    # ============================================
    # PARSING STRATEGY CONFIGURATION
    # ============================================
    
    # Primary parsing method per retailer
    # Options: 'beautifulsoup_first' (try BS4, fallback to LLM if fails)
    #          'llm_only' (always use LLM - more expensive)
    PARSING_STRATEGY = {
        'nordstrom': 'beautifulsoup_first',
        'anthropologie': 'beautifulsoup_first',
        'urban_outfitters': 'beautifulsoup_first',
        'aritzia': 'beautifulsoup_first',
        'hm': 'beautifulsoup_first',
        'revolve': 'beautifulsoup_first',
        'abercrombie': 'beautifulsoup_first',
        'mango': 'beautifulsoup_first',
        'uniqlo': 'beautifulsoup_first',
        'asos': 'beautifulsoup_first',
    }
    
    # LLM provider for fallback parsing
    LLM_PROVIDER = 'gemini'  # Options: 'gemini', 'deepseek'
    
    # LLM API keys
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
    DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '')
    
    # LLM model selection
    GEMINI_MODEL = 'gemini-1.5-flash'  # Fast and cheap for fallback
    DEEPSEEK_MODEL = 'deepseek-chat'
    
    # ============================================
    # PATTERN LEARNING CONFIGURATION
    # ============================================
    
    # Enable pattern learning for HTML selectors
    # System learns which CSS selectors work best per retailer
    PATTERN_LEARNING_ENABLED = True
    
    # Minimum successful extractions before trusting a pattern
    PATTERN_LEARNING_MIN_SUCCESSES = 3
    
    # Maximum failed attempts before marking pattern as unreliable
    PATTERN_LEARNING_MAX_FAILURES = 5
    
    # Pattern confidence threshold (0.0-1.0)
    # Pattern must succeed this % of times to be considered reliable
    PATTERN_CONFIDENCE_THRESHOLD = 0.7
    
    # Pattern learning database (reuses existing Shared/pattern_learning.py)
    PATTERN_DB_PATH = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'Shared',
        'pattern_learning.db'
    )
    
    # ============================================
    # ERROR HANDLING & FALLBACK
    # ============================================
    
    # Enable fallback to Patchright tower if Commercial API fails
    FALLBACK_TO_PATCHRIGHT = False  # Disabled: Commercial API retailers should not fall back to Patchright
    
    # Maximum retry attempts before fallback
    MAX_RETRIES = 2
    
    # Request timeout for Bright Data API
    REQUEST_TIMEOUT_SECONDS = 60  # Increased from 30 to 60 for complex sites like Nordstrom
    
    # Retry delay (exponential backoff)
    RETRY_BASE_DELAY = 2  # seconds
    
    # ============================================
    # EXTRACTION SUCCESS CRITERIA
    # ============================================
    
    # Product extraction: Required fields
    REQUIRED_PRODUCT_FIELDS = {
        'title': True,           # Must have
        'price': True,           # Must have
        'description': False,    # Nice to have
        'stock_status': False,   # Nice to have
        'image_urls': False,     # Nice to have (but important)
    }
    
    # Catalog extraction: Required fields
    REQUIRED_CATALOG_FIELDS = {
        'url': True,             # Must have
        'title': False,          # Nice to have
        'price': False,          # Nice to have
    }
    
    # Minimum images for successful product extraction
    MIN_PRODUCT_IMAGES = 3
    
    # Minimum products for successful catalog extraction
    MIN_CATALOG_PRODUCTS = 10
    
    # ============================================
    # LOGGING CONFIGURATION
    # ============================================
    
    # Log file for Commercial API tower
    LOG_FILE = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        'commercial_api.log'
    )
    
    # Verbose logging (set False in production)
    VERBOSE_LOGGING = True

