"""
Patchright Tower - Retailer Strategies
Per-retailer configurations and strategies

Extracted from: Shared/playwright_agent.py (screenshot strategies, verification configs)
Target: <400 lines
"""

# Add shared path for imports
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../../Shared"))

from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


# Per-retailer anti-scraping configuration
ANTI_SCRAPING_CONFIG = {
    'anthropologie': {
        'enhanced_args': True,           # Browser arguments
        'webdriver_hiding': True,        # JavaScript injection
        'timing_variance': True,         # Randomized delays
        'randomized_verification': True, # Variable TAB/SPACE timing
        'notes': 'PerimeterX Press & Hold - needs all enhancements'
    },
    'abercrombie': {
        'enhanced_args': True,
        'webdriver_hiding': True,
        'timing_variance': False,  # Working perfectly, don't touch timing
        'randomized_verification': False,
        'notes': 'Already working at 100% - minimal changes'
    },
    'urban_outfitters': {
        'enhanced_args': True,
        'webdriver_hiding': True,
        'timing_variance': True,
        'randomized_verification': False,  # Uses Gemini click, not keyboard
        'notes': 'PerimeterX button click - Gemini handles it'
    },
    'aritzia': {
        'enhanced_args': True,
        'webdriver_hiding': True,
        'timing_variance': True,
        'randomized_verification': False,
        'notes': 'Cloudflare + polling - timing variance OK except polling loop'
    },
    'revolve': {
        'enhanced_args': False,  # Uses Markdown, not Patchright
        'webdriver_hiding': False,
        'timing_variance': False,
        'randomized_verification': False,
        'notes': 'Markdown extraction - not affected by browser changes'
    },
    'nordstrom': {
        'enhanced_args': True,
        'webdriver_hiding': True,
        'timing_variance': True,
        'randomized_verification': True,
        'notes': 'Blocked by IP - needs all enhancements + future proxy'
    },
    # Default for new retailers
    'default': {
        'enhanced_args': True,
        'webdriver_hiding': True,
        'timing_variance': False,  # Conservative default
        'randomized_verification': False,
        'notes': 'Safe defaults - enable features as needed'
    }
}


def get_anti_scraping_config(retailer: str) -> dict:
    """Get anti-scraping config for retailer, fallback to default"""
    return ANTI_SCRAPING_CONFIG.get(
        retailer.lower(), 
        ANTI_SCRAPING_CONFIG['default']
    )


# Retailer-specific strategies
RETAILER_STRATEGIES = {
    'anthropologie': {
        'verification': 'perimeterx_press_hold',
        'verification_method': 'keyboard',  # TAB + SPACE breakthrough
        'wait_strategy': 'domcontentloaded',  # Not networkidle (persistent activity)
        'extended_wait_after_verification': 4,  # seconds
        'catalog_mode': 'dom_first',  # Screenshot too tall (33,478px)
        'dom_first_reason': 'tall_page',  # Gemini resize makes products unreadable
        'product_selectors': [
            "a[href*='/shop/']",
            "a[class*='product']"
        ],
        'dom_extraction': {
            'title_selectors': ['img[alt]', 'a[aria-label]', '[class*="product-title"]', '[class*="product-name"]', 'h3', 'h2'],
            'price_selectors': [
                'span[data-testid*="price"]', 
                '[data-testid*="price"]',
                'span[class*="price"]', 
                'span[class*="Price"]', 
                'div[class*="price"]',
                '[aria-label*="price"]',
                'span[itemprop="price"]'
            ],
            'product_container': 'article[class*="product"], div[class*="product-card"], div[class*="product-tile"], [data-testid*="product"]'
        },
        'popup_selectors': [
            'button[aria-label*="close"]',
            'button:has-text("No Thanks")'
        ],
        'anti_bot_complexity': 'high',  # PerimeterX is sophisticated
        'notes': 'Use keyboard (TAB 10x + SPACE 10s) for Press & Hold. Wait naturally after verification.'
    },
    
    'urban_outfitters': {
        'verification': 'perimeterx_press_hold',
        'verification_method': 'keyboard',
        'wait_strategy': 'domcontentloaded',
        'extended_wait_after_verification': 4,
        'catalog_mode': 'dom_first',  # DOM extraction more reliable
        'product_selectors': [
            "a[href*='/products/']",
            "a[class*='product-card']"
        ],
        'dom_extraction': {
            'title_selectors': ['img[alt]', 'a[aria-label]', '[class*="product-name"]', 'h3', 'h2'],
            'price_selectors': ['[class*="price"]', 'span[class*="Price"]', '[data-price]'],
            'product_container': 'article[class*="product"], div[class*="product-card"]'
        },
        'anti_bot_complexity': 'high',
        'notes': 'Same PerimeterX as Anthropologie. Keyboard approach works.'
    },
    
    'aritzia': {
        'verification': 'cloudflare_automatic',
        'wait_strategy': 'domcontentloaded',  # Use standard wait
        'catalog_mode': 'dom_first',  # DOM extraction more reliable
        'use_active_polling': True,  # Use active polling AFTER page load
        'polling_config': {
            'enabled': True,
            'max_attempts': 30,
            'interval_seconds': 1,
            'catalog_selectors': [
                'a[href*="/product/"]',
                'a[class*="ProductCard"]',
                '[data-product-id]'
            ],
            'product_selectors': [
                'h1[class*="product"]',
                '[data-product-id]',
                'button[class*="add-to-cart"]',
                'div[class*="product-details"]'
            ]
        },
        'product_selectors': [
            "a[href*='/product/']",
            "a[class*='ProductCard']"
        ],
        'dom_extraction': {
            'title_selectors': ['[class*="ProductCard"] h3', '[class*="product-name"]', 'img[alt]', 'a[aria-label]'],
            'price_selectors': ['[class*="price"]', '[data-price]', 'span[class*="Price"]'],
            'product_container': '[class*="ProductCard"], [data-product-id]'
        },
        'anti_bot_complexity': 'very_high',
        'notes': 'Cloudflare + SPA with variable API delay (1-15s). Uses active polling instead of fixed waits for reliability. Polling detects products immediately when they appear.'
    },
    
    'abercrombie': {
        'verification': 'none',
        'wait_strategy': 'domcontentloaded',
        'catalog_mode': 'dom_first',  # DOM extraction more reliable
        'explicit_wait_for_products': True,  # JavaScript SPA
        'product_selectors': [
            "a[class*='product-tile']",
            "a[class*='ProductCard']"
        ],
        'dom_extraction': {
            'title_selectors': ['img[alt]', 'a[aria-label]', '[class*="product-title"]', '[class*="product-name"]', 'h3', 'h2', '[data-product-title]'],
            'price_selectors': [
                'span[data-price]',
                '[data-price]',
                'span[class*="price"]', 
                'span[class*="Price"]',
                'div[class*="price"]',
                '[itemprop="price"]',
                '[aria-label*="$"]'
            ],
            'product_container': '[class*="product-tile"], [class*="ProductCard"], [data-product-id]'
        },
        'wait_for_selector': "a[class*='product-tile']",
        'wait_timeout': 10000,
        'anti_bot_complexity': 'low',
        'notes': 'SPA requires explicit wait_for_selector for dynamic JS rendering'
    },
    
    'revolve': {
        'verification': 'none',
        'wait_strategy': 'domcontentloaded',  # Use domcontentloaded (popups prevent networkidle)
        'catalog_mode': 'dom_first',  # DOM-first for catalog (Markdown for single product)
        'headless': True,  # Safe to run headless (low anti-bot complexity)
        'product_selectors': [
            "a[href*='/dp/']"
        ],
        'dom_extraction': {
            'title_selectors': ['img[alt]', 'a[aria-label]'],  # Revolve uses img alt for titles
            'price_selectors': [],  # Prices in plain text nodes, extract from parent text
            'product_container': '#plp-prod-list',  # Main product grid
            'extract_price_from_text': True,  # Special flag: extract $ amounts from text content
            'max_parent_levels': 3,  # Traverse 3 levels up to reach product card with price
            'price_in_sibling': True  # Price might be in sibling element, not direct parent
        },
        'popup_selectors': [
            'button[aria-label*="Close"]',
            'button[aria-label*="close"]',
            'div[role="button"]:has-text("Close")',
            'button:has-text("Don\'t Allow")',
            'button:has-text("No Thanks")'
        ],
        'anti_bot_complexity': 'low',
        'notes': 'DOM-first for catalog URLs/titles. Markdown extraction for single product pages. Titles in img[alt], prices in text nodes. Has notification popups.'
    },
    
    'asos': {
        'verification': 'none',
        'wait_strategy': 'domcontentloaded',
        'catalog_mode': 'dom_first',  # DOM-first for catalog (Markdown for single product)
        'headless': True,  # Safe to run headless (low anti-bot complexity)
        'product_selectors': [
            "a[href*='/prd/']",  # ASOS product links use /prd/
            "a[data-auto-id='productTile']"
        ],
        'dom_extraction': {
            'title_selectors': ['img[alt]', 'h2', '[data-auto-id="productTile"] h2', 'h3'],
            'price_selectors': [
                '[data-testid="current-price"]',
                '[class*="price"]',
                'span[data-id*="price"]'
            ],
            'product_container': '[data-auto-id="productList"], .products, [class*="product-list"]'
        },
        'anti_bot_complexity': 'low',
        'notes': 'DOM-first for catalog URLs/titles/prices. Markdown extraction for single product pages.'
    },
    
    'nordstrom': {
        'verification': 'none',
        'wait_strategy': 'domcontentloaded',
        'catalog_mode': 'dom_first',  # DOM extraction more reliable
        'product_selectors': [
            "a[href*='/s/']",  # Primary: Nordstrom product links always use /s/
            "a.AFBJb",         # Backup: Product image links
            "a.dls-ogz194"     # Backup: Product title links
        ],
        'dom_extraction': {
            'title_selectors': ['img[alt]', 'a[aria-label]', '[class*="product"] h3', '[class*="product-name"]', 'h3', 'h2'],
            'price_selectors': [
                'span.qHz0a',  # Nordstrom obfuscated class
                'span[class*="qHz0a"]',
                'span.He8hw',  # Nordstrom obfuscated class
                'span[class*="He8hw"]',
                '[aria-label*="$"]',
                'span[itemprop="price"]',
                '[data-testid*="price"]',
                'span[class*="price"]',
                '[class*="price"]'
            ],
            'product_container': 'article[class*="product"], div[class*="product"], [data-product-id]'
        },
        'anti_bot_complexity': 'high',  # BLOCKED: "unusual activity" page
        'notes': 'BLOCKED by aggressive anti-bot protection (Nov 2024). Shows "unusual activity" warning and blocks automated traffic. Product URLs follow pattern: /s/{product-name}/{product-id}. May require residential proxies or manual session management.'
    },
    
    'hm': {
        'verification': 'none',
        'wait_strategy': 'domcontentloaded',
        'catalog_mode': 'dom_first',
        'product_selectors': [
            "a[href*='/productpage']",
            "a[class*='item-link']"
        ],
        'dom_extraction': {
            'title_selectors': ['h1[class*="product"]', '[class*="product-title"]', 'h1', 'h2'],
            'price_selectors': [
                '[class*="price"]',
                '[data-testid*="price"]',
                'span[itemprop="price"]'
            ],
            'product_container': 'article, [class*="product"], [data-product]'
        },
        'anti_bot_complexity': 'high',  # BLOCKED: "Access Denied"
        'notes': 'BLOCKED by anti-bot protection (Nov 2024). Single product pages show "Access Denied". May require residential proxies or different user agent strategy.'
    },
    
    'mango': {
        'verification': 'none',
        'wait_strategy': 'domcontentloaded',
        'catalog_mode': 'dom_first',  # DOM-first for catalog (Markdown for single product)
        'headless': True,  # Safe to run headless (low anti-bot complexity)
        'product_selectors': [
            "a[href*='/product']",
            "a.product-link",
            "a[class*='product']"
        ],
        'dom_extraction': {
            'title_selectors': ['h2', 'h3', 'img[alt]', '[class*="product-name"]', '[class*="title"]'],
            'price_selectors': [
                '[class*="price"]',
                'span[data-testid*="price"]',
                '[data-price]'
            ],
            'product_container': '[class*="products"], [class*="product-list"], .product-grid'
        },
        'anti_bot_complexity': 'low',
        'notes': 'DOM-first for catalog URLs/titles/prices. Markdown extraction for single product pages. Uses "What\'s New" section for monitoring workflow.'
    },
    
    'uniqlo': {
        'verification': 'none',
        'wait_strategy': 'domcontentloaded',
        'catalog_mode': 'dom_first',  # DOM-first for catalog (Markdown for single product)
        'headless': True,  # Safe to run headless (low anti-bot complexity)
        'product_selectors': [
            "a[href*='/products/']",
            "a.product-tile",
            "a[data-test*='product']"
        ],
        'dom_extraction': {
            'title_selectors': ['h3', 'h2', '[class*="product-name"]', 'img[alt]', '[class*="title"]'],
            'price_selectors': [
                '[class*="price"]',
                'span[data-test*="price"]',
                '[aria-label*="$"]'
            ],
            'product_container': '[class*="product-grid"], [class*="product-list"], .products'
        },
        'anti_bot_complexity': 'low',
        'notes': 'DOM-first for catalog URLs/titles/prices. Markdown extraction for single product pages.'
    }
}


# Screenshot strategies per retailer (for multi-screenshot capture)
SCREENSHOT_STRATEGIES = {
    'anthropologie': {
        'strategy': 'full_page',  # Tall SPA
        'regions': ['full'],
        'scroll_between': False
    },
    
    'urban_outfitters': {
        'strategy': 'full_page',
        'regions': ['full'],
        'scroll_between': False
    },
    
    'aritzia': {
        'strategy': 'multi_region',
        'regions': ['header', 'mid', 'footer'],
        'scroll_between': True,
        'scroll_pause': 1000
    },
    
    'abercrombie': {
        'strategy': 'full_page',
        'regions': ['full'],
        'scroll_between': False
    },
    
    'nordstrom': {
        'strategy': 'multi_region',
        'regions': ['header', 'mid', 'footer'],
        'scroll_between': True
    },
    
    'default': {
        'strategy': 'multi_region',
        'regions': ['header', 'mid', 'footer'],
        'scroll_between': True,
        'scroll_pause': 1000
    }
}


class PatchrightRetailerStrategies:
    """
    Retailer-specific strategies and configurations
    
    Provides:
    - Verification methods per retailer
    - Wait strategies
    - Product selectors
    - Screenshot strategies
    - Anti-bot complexity levels
    """
    
    def __init__(self):
        self.strategies = RETAILER_STRATEGIES
        self.screenshot_strategies = SCREENSHOT_STRATEGIES
        logger.info(f"✅ Loaded strategies for {len(self.strategies)} retailers")
    
    def get_strategy(self, retailer: str) -> Dict:
        """
        Get strategy for retailer
        
        Args:
            retailer: Retailer name (lowercase)
            
        Returns:
            Strategy dict with defaults if retailer not found
        """
        retailer = retailer.lower()
        
        if retailer in self.strategies:
            return self.strategies[retailer]
        
        # Default strategy
        logger.warning(f"No strategy found for {retailer}, using default")
        return {
            'verification': 'none',
            'wait_strategy': 'domcontentloaded',
            'catalog_mode': 'gemini_first',
            'product_selectors': [
                "a[href*='/product']",
                "a[class*='product']"
            ],
            'anti_bot_complexity': 'unknown'
        }
    
    def get_screenshot_strategy(self, retailer: str) -> Dict:
        """
        Get screenshot strategy for retailer
        
        Returns:
            Screenshot strategy dict
        """
        retailer = retailer.lower()
        
        if retailer in self.screenshot_strategies:
            return self.screenshot_strategies[retailer]
        
        return self.screenshot_strategies['default']
    
    def requires_verification(self, retailer: str) -> bool:
        """Check if retailer requires verification handling"""
        strategy = self.get_strategy(retailer)
        return strategy.get('verification', 'none') != 'none'
    
    def get_verification_method(self, retailer: str) -> str:
        """
        Get verification method
        
        Returns:
            'keyboard', 'mouse', 'gemini', 'none'
        """
        strategy = self.get_strategy(retailer)
        return strategy.get('verification_method', 'gemini')
    
    def get_wait_strategy(self, retailer: str) -> str:
        """
        Get page load wait strategy
        
        Returns:
            'networkidle', 'domcontentloaded', 'load'
        """
        strategy = self.get_strategy(retailer)
        return strategy.get('wait_strategy', 'domcontentloaded')
    
    def get_catalog_mode(self, retailer: str) -> str:
        """
        Get catalog extraction mode
        
        Returns:
            'gemini_first', 'dom_first', 'markdown'
        """
        strategy = self.get_strategy(retailer)
        return strategy.get('catalog_mode', 'gemini_first')
    
    def get_product_selectors(self, retailer: str) -> List[str]:
        """Get product selectors for retailer"""
        strategy = self.get_strategy(retailer)
        return strategy.get('product_selectors', [
            "a[href*='/product']",
            "a[class*='product']"
        ])
    
    def get_anti_bot_complexity(self, retailer: str) -> str:
        """
        Get anti-bot complexity level
        
        Returns:
            'low', 'medium', 'high', 'unknown'
        """
        strategy = self.get_strategy(retailer)
        return strategy.get('anti_bot_complexity', 'unknown')
    
    def should_use_extended_wait(self, retailer: str) -> bool:
        """Check if retailer needs extended wait"""
        strategy = self.get_strategy(retailer)
        return 'extended_wait' in strategy or 'extended_wait_after_verification' in strategy
    
    def get_extended_wait_duration(self, retailer: str) -> int:
        """
        Get extended wait duration in seconds
        
        Returns:
            Wait duration (default: 0)
        """
        strategy = self.get_strategy(retailer)
        return strategy.get('extended_wait', 
                          strategy.get('extended_wait_after_verification', 0))
    
    def should_scroll_trigger(self, retailer: str) -> bool:
        """Check if retailer needs scroll to trigger lazy load"""
        strategy = self.get_strategy(retailer)
        return strategy.get('scroll_trigger', False)
    
    def get_scroll_amount(self, retailer: str) -> int:
        """Get scroll amount in pixels"""
        strategy = self.get_strategy(retailer)
        return strategy.get('scroll_amount', 1000)
