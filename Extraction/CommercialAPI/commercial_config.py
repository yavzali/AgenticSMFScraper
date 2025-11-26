"""
Commercial API Configuration

Central configuration for Bright Data integration and parsing strategies
"""

import os
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

class CommercialAPIConfig:
    """
    Configuration for Commercial API Extraction Tower
    
    Key Features:
    - Bright Data credentials and settings
    - Retailer routing (which retailers use this tower)
    - HTML caching configuration (1-day debugging cache)
    - Parsing strategies (BeautifulSoup first, LLM fallback)
    - Pattern learning settings
    - Error handling and fallback configuration
    """
    
    # ============================================
    # BRIGHT DATA API CONFIGURATION
    # ============================================
    
    BRIGHTDATA_API_KEY = os.getenv(
        'BRIGHTDATA_API_KEY',
        ''  # Must be set in .env file
    )
    
    # Bright Data Web Unlocker endpoint
    BRIGHTDATA_PROXY_HOST = "brd.superproxy.io"
    BRIGHTDATA_PROXY_PORT = 33335  # Port from Bright Data dashboard
    
    # Bright Data credentials (username/password authentication)
    BRIGHTDATA_USERNAME = os.getenv('BRIGHTDATA_USERNAME', '')
    BRIGHTDATA_PASSWORD = os.getenv('BRIGHTDATA_PASSWORD', '')
    
    # Cost tracking (Bright Data pricing)
    COST_PER_1000_REQUESTS = 1.50  # $1.50 per 1,000 requests
    
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
    ACTIVE_RETAILERS = [
        'nordstrom',
        'revolve',  # TEMPORARY - for diagnostic testing (Revolve has no anti-bot)
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
    FALLBACK_TO_PATCHRIGHT = True
    
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

