"""
Commercial API Client - Abstract Base Class
Service-agnostic interface for commercial scraping APIs
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional
import logging
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from Shared.logger_config import setup_logging

logger = setup_logging(__name__)


class CommercialAPIClient(ABC):
    """
    Abstract base class for commercial API clients
    
    Allows easy swapping of service providers (ZenRows, ScraperAPI, Bright Data, etc.)
    All providers must implement these methods to be compatible with the
    Commercial API Extraction Tower.
    """
    
    @abstractmethod
    async def fetch_html(
        self,
        url: str,
        retailer: str,
        page_type: str = 'product'
    ) -> str:
        """
        Fetch HTML from URL using the commercial API
        
        Args:
            url: Target URL to scrape
            retailer: Retailer name (for logging and stats)
            page_type: Type of page ('product' or 'catalog')
        
        Returns:
            Raw HTML string (ready for BeautifulSoup parsing)
        
        Raises:
            Exception: If fetch fails after retries
        """
        pass
    
    @abstractmethod
    def get_usage_stats(self) -> Dict:
        """
        Get usage statistics
        
        Returns:
            Dict with keys:
                - total_requests: int
                - successful_requests: int
                - failed_requests: int
                - success_rate: float (0.0-1.0)
                - total_cost: float (USD)
                - total_bytes: int
                - provider_specific: dict (custom stats per provider)
        """
        pass
    
    @abstractmethod
    def log_usage_summary(self):
        """Log summary of usage statistics"""
        pass
    
    @abstractmethod
    async def close(self):
        """Clean up resources (close sessions, connections, etc.)"""
        pass
    
    @abstractmethod
    async def initialize(self):
        """Initialize client resources (create sessions, etc.)"""
        pass


def get_client(config) -> CommercialAPIClient:
    """
    Factory function to get the configured API client
    
    Args:
        config: CommercialAPIConfig instance
    
    Returns:
        CommercialAPIClient subclass instance for the active provider
    
    Raises:
        ValueError: If unknown provider specified
    """
    provider = config.ACTIVE_PROVIDER.lower()
    
    logger.info(f"🏭 Creating Commercial API client: {provider}")
    
    if provider == 'zenrows':
        from .providers.zenrows_provider import ZenRowsClient
        return ZenRowsClient(config)
    
    elif provider == 'scraperapi':
        from .providers.scraperapi_provider import ScraperAPIClient
        return ScraperAPIClient(config)
    
    elif provider == 'brightdata':
        from .providers.brightdata_provider import BrightDataClient
        return BrightDataClient(config)
    
    else:
        raise ValueError(
            f"Unknown Commercial API provider: '{provider}'. "
            f"Supported providers: zenrows, scraperapi, brightdata"
        )


__all__ = [
    'CommercialAPIClient',
    'get_client',
]

