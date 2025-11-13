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
            'title_selectors': ['img[alt]', 'a[aria-label]', '[class*="product-title"]', '[class*="product-name"]'],
            'price_selectors': ['[class*="price"]', 'span[class*="Price"]', 'div[class*="price"]'],
            'product_container': 'article[class*="product"], div[class*="product-card"], div[class*="product-tile"]'
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
            'title_selectors': ['img[alt]', '[class*="product-title"]', '[class*="product-name"]', 'h3', 'h2'],
            'price_selectors': ['[class*="price"]', 'span[class*="Price"]', '[data-price]'],
            'product_container': '[class*="product-tile"], [class*="ProductCard"]'
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
        'product_selectors': [
            "a[href*='/dp/']"
        ],
        'dom_extraction': {
            'title_selectors': ['img[alt]', 'a[aria-label]'],  # Revolve uses img alt for titles
            'price_selectors': [],  # Prices in plain text nodes, extract from parent text
            'product_container': 'div[class*="grid__product"], article',
            'extract_price_from_text': True  # Special flag: extract $ amounts from text content
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
        'wait_strategy': 'networkidle',
        'catalog_mode': 'markdown',
        'anti_bot_complexity': 'low',
        'notes': 'Markdown extraction preferred'
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
            'title_selectors': ['img[alt]', 'a[aria-label]', '[class*="product"] h3', '[class*="product-name"]'],
            'price_selectors': ['span.qHz0a', 'span[class*="qHz0a"]', 'span.He8hw', '[class*="price"]'],  # Nordstrom-specific
            'product_container': 'article[class*="product"], div[class*="product"]'
        },
        'anti_bot_complexity': 'low',
        'notes': 'Product URLs follow pattern: /s/{product-name}/{product-id}. Multiple links per product card. Uses obfuscated price classes.'
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
