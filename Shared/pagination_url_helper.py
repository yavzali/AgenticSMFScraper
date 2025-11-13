"""
Pagination URL Helper
Manages multi-page catalog URLs for retailers with pagination
This uses EXACT URLs provided by the user - no URL construction or reconstruction.
"""

from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

# Pagination URLs for each retailer (pages 1 and 2)
# These are EXACT URLs - do not modify or reconstruct
PAGINATION_URLS = {
    'anthropologie': {
        'dresses': {
            'page_1': 'https://www.anthropologie.com/dresses?sort=tile.product.newestColorDate&order=Descending',
            'page_2': 'https://www.anthropologie.com/dresses?order=Descending&page=2&sort=tile.product.newestColorDate'
        },
        'tops': {
            'page_1': 'https://www.anthropologie.com/tops?sort=tile.product.newestColorDate&order=Descending',
            'page_2': 'https://www.anthropologie.com/tops?order=Descending&page=2&sort=tile.product.newestColorDate'
        }
    },
    'urban_outfitters': {
        'dresses': {
            'page_1': 'https://www.urbanoutfitters.com/dresses?sort=tile.product.newestColorDate&order=Descending&sleeve=Long+Sleeve,3/4+Sleeve,Short+Sleeve',
            'page_2': 'https://www.urbanoutfitters.com/dresses?order=Descending&page=2&sleeve=Long%20Sleeve%2C3%2F4%20Sleeve%2CShort%20Sleeve&sort=tile.product.newestColorDate'
        },
        'tops': {
            'page_1': 'https://www.urbanoutfitters.com/womens-tops?sort=tile.product.newestColorDate&order=Descending&sleeve=Long+Sleeve,3/4+Sleeve,Short+Sleeve',
            'page_2': 'https://www.urbanoutfitters.com/womens-tops?order=Descending&page=2&sleeve=Long%20Sleeve%2C3%2F4%20Sleeve%2CShort%20Sleeve&sort=tile.product.newestColorDate'
        }
    },
    'nordstrom': {
        'dresses': {
            'page_1': 'https://www.nordstrom.com/browse/women/clothing/dresses?breadcrumb=Home%2FWomen%2FClothing%2FDresses&preferredStore=210&preferredPostalCode=10451&sort=Newest&postalCodeAvailability=10451&filterByNeckStyle=boat-neck&filterByNeckStyle=collared&filterByNeckStyle=cowl-neck&filterByNeckStyle=crewneck&filterByNeckStyle=henley&filterByNeckStyle=high-neck&filterByNeckStyle=mock-neck&filterByNeckStyle=quarter-zip&filterByNeckStyle=shawl-collar&filterByNeckStyle=tie-neck&filterByNeckStyle=turtleneck&filterBySleeveLength=cap-sleeve&filterBySleeveLength=short-sleeve&filterBySleeveLength=3-4-sleeve&filterBySleeveLength=long-sleeve',
            'page_2': 'https://www.nordstrom.com/browse/women/clothing/dresses?breadcrumb=Home%2FWomen%2FClothing%2FDresses&preferredStore=210&preferredPostalCode=10451&page=2&sort=Newest&postalCodeAvailability=10451&filterByNeckStyle=boat-neck&filterByNeckStyle=collared&filterByNeckStyle=cowl-neck&filterByNeckStyle=crewneck&filterByNeckStyle=henley&filterByNeckStyle=high-neck&filterByNeckStyle=mock-neck&filterByNeckStyle=quarter-zip&filterByNeckStyle=shawl-collar&filterByNeckStyle=tie-neck&filterByNeckStyle=turtleneck&filterBySleeveLength=cap-sleeve&filterBySleeveLength=short-sleeve&filterBySleeveLength=3-4-sleeve&filterBySleeveLength=long-sleeve'
        },
        'tops': {
            'page_1': 'https://www.nordstrom.com/browse/women/clothing/tops?breadcrumb=Home%2FWomen%2FClothing%2FTops&preferredStore=210&preferredPostalCode=10451&sort=Newest&postalCodeAvailability=10451&filterByNeckStyle=boat-neck&filterByNeckStyle=collared&filterByNeckStyle=cowl-neck&filterByNeckStyle=crewneck&filterByNeckStyle=henley&filterByNeckStyle=high-neck&filterByNeckStyle=mock-neck&filterByNeckStyle=quarter-zip&filterByNeckStyle=shawl-collar&filterByNeckStyle=tie-neck&filterByNeckStyle=turtleneck&filterBySleeveLength=cap-sleeve&filterBySleeveLength=short-sleeve&filterBySleeveLength=3-4-sleeve&filterBySleeveLength=long-sleeve',
            'page_2': 'https://www.nordstrom.com/browse/women/clothing/tops?breadcrumb=Home%2FWomen%2FClothing%2FTops&preferredStore=210&preferredPostalCode=10451&page=2&sort=Newest&postalCodeAvailability=10451&filterByNeckStyle=boat-neck&filterByNeckStyle=collared&filterByNeckStyle=cowl-neck&filterByNeckStyle=crewneck&filterByNeckStyle=henley&filterByNeckStyle=high-neck&filterByNeckStyle=mock-neck&filterByNeckStyle=quarter-zip&filterByNeckStyle=shawl-collar&filterByNeckStyle=tie-neck&filterByNeckStyle=turtleneck&filterBySleeveLength=cap-sleeve&filterBySleeveLength=short-sleeve&filterBySleeveLength=3-4-sleeve&filterBySleeveLength=long-sleeve'
        }
    },
    'abercrombie': {
        'dresses': {
            'page_1': 'https://www.abercrombie.com/shop/us/womens-dresses-and-jumpsuits?pagefm=navigation-left+nav&rows=90&sort=newest&start=0',
            'page_2': 'https://www.abercrombie.com/shop/us/womens-dresses-and-jumpsuits?pagefm=navigation-left+nav&rows=90&sort=newest&start=90'
        },
        'tops': {
            'page_1': 'https://www.abercrombie.com/shop/us/womens-tops--1?rows=90&sort=newest&start=0',
            'page_2': 'https://www.abercrombie.com/shop/us/womens-tops--1?rows=90&sort=newest&start=90'
        }
    }
}

# Retailers that use pagination (scan 2 pages)
PAGINATED_RETAILERS = ['anthropologie', 'urban_outfitters', 'nordstrom', 'abercrombie']

# Retailers that use infinite scroll (scan 1 page)
INFINITE_SCROLL_RETAILERS = ['revolve', 'asos', 'mango', 'uniqlo', 'hm', 'aritzia']


def get_pagination_urls(retailer: str, category: str) -> Optional[List[str]]:
    """
    Get pagination URLs for a retailer and category
    
    Args:
        retailer: Retailer name (lowercase)
        category: Category name (dresses, tops)
    
    Returns:
        List of URLs to scan (1 URL for infinite scroll, 2 URLs for pagination)
        None if retailer uses infinite scroll (signal to use standard single-page flow)
    """
    retailer = retailer.lower()
    category = category.lower()
    
    # Check if retailer uses pagination
    if retailer not in PAGINATED_RETAILERS:
        logger.debug(f"{retailer} uses infinite scroll - single page scan")
        # For infinite scroll retailers, return None
        # (This signals caller to use standard single-page flow)
        return None
    
    # Get pagination URLs
    if retailer in PAGINATION_URLS:
        retailer_config = PAGINATION_URLS[retailer]
        
        if category in retailer_config:
            urls = [
                retailer_config[category]['page_1'],
                retailer_config[category]['page_2']
            ]
            logger.info(f"✅ {retailer} {category}: Scanning 2 pages")
            return urls
        else:
            logger.warning(f"Category '{category}' not configured for {retailer}")
            return None
    
    logger.warning(f"No pagination URLs configured for {retailer}")
    return None


def should_use_pagination(retailer: str) -> bool:
    """
    Check if retailer uses pagination (vs infinite scroll)
    
    Args:
        retailer: Retailer name (lowercase)
    
    Returns:
        True if retailer uses pagination, False if infinite scroll
    """
    return retailer.lower() in PAGINATED_RETAILERS

