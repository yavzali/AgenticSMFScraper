"""
Retailer URL/Product Code Stability Tracker

Monitors URL and product_code stability across catalog crawls and product updates
to determine reliable deduplication strategies per retailer.

This helps us understand:
1. Do URLs change for the same product? (Revolve: YES)
2. Do product codes change? (Revolve: YES - SELF-WD318 → SELF-WD101)
3. How often? What patterns?
4. Which retailers need title+price matching instead?
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../Shared"))

import aiosqlite
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict
import difflib

from logger_config import setup_logging

logger = setup_logging(__name__)

@dataclass
class StabilityMetrics:
    """Metrics for URL/product code stability"""
    retailer: str
    total_products_tracked: int
    url_changes_detected: int
    product_code_changes_detected: int
    url_stability_score: float  # 0-1, 1=perfectly stable
    product_code_stability_score: float  # 0-1, 1=perfectly stable
    sample_url_changes: List[Dict]  # Examples of URL changes
    sample_code_changes: List[Dict]  # Examples of code changes
    last_analyzed: datetime
    recommendation: str  # "use_url", "use_code", "use_title_price", "use_all"


class RetailerStabilityTracker:
    """
    Tracks and analyzes URL/product_code stability per retailer
    """
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.path.join(os.path.dirname(__file__), "../Shared/products.db")
        self.db_path = db_path
    
    async def analyze_retailer_stability(self, retailer: str, 
                                        lookback_days: int = 30) -> StabilityMetrics:
        """
        Analyze URL and product_code stability for a retailer
        
        Strategy:
        1. Find products with same title+price (high confidence same product)
        2. Check if their URLs or product_codes differ
        3. Calculate stability scores
        """
        
        logger.info(f"Analyzing stability for {retailer} (last {lookback_days} days)")
        
        cutoff_date = (datetime.utcnow() - timedelta(days=lookback_days)).isoformat()
        
        async with aiosqlite.connect(self.db_path) as conn:
            # Get all products from this retailer with recent activity
            cursor = await conn.cursor()
            
            # Query: Products that might be duplicates (same title, similar price)
            await cursor.execute("""
                SELECT p1.id as id1, p1.title as title1, p1.price as price1, 
                       p1.url as url1, p1.product_code as code1,
                       p1.last_updated as updated1,
                       p2.id as id2, p2.title as title2, p2.price as price2,
                       p2.url as url2, p2.product_code as code2,
                       p2.last_updated as updated2
                FROM products p1
                JOIN products p2 ON p1.retailer = p2.retailer 
                    AND p1.id < p2.id
                    AND ABS(p1.price - p2.price) < 1.0
                WHERE p1.retailer = ?
                    AND (p1.last_updated > ? OR p2.last_updated > ?)
                ORDER BY p1.title, p1.price
            """, (retailer, cutoff_date, cutoff_date))
            
            potential_duplicates = await cursor.fetchall()
            
            # Analyze for stability issues
            url_changes = []
            code_changes = []
            total_tracked = 0
            
            for row in potential_duplicates:
                title1, title2 = row[1], row[7]
                url1, url2 = row[3], row[9]
                code1, code2 = row[4], row[10]
                price1, price2 = row[2], row[8]
                
                # Check if titles are very similar (likely same product)
                title_similarity = difflib.SequenceMatcher(
                    None, title1.lower(), title2.lower()
                ).ratio()
                
                if title_similarity > 0.90:  # 90%+ = likely same product
                    total_tracked += 1
                    
                    # Check URL stability
                    if url1 != url2:
                        url_changes.append({
                            'title': title1,
                            'price': price1,
                            'old_url': url1,
                            'new_url': url2,
                            'title_similarity': round(title_similarity, 3)
                        })
                    
                    # Check product code stability
                    if code1 and code2 and code1 != code2:
                        code_changes.append({
                            'title': title1,
                            'price': price1,
                            'old_code': code1,
                            'new_code': code2,
                            'old_url': url1,
                            'new_url': url2,
                            'title_similarity': round(title_similarity, 3)
                        })
            
            # Calculate stability scores
            url_stability = 1.0 if total_tracked == 0 else (total_tracked - len(url_changes)) / total_tracked
            code_stability = 1.0 if total_tracked == 0 else (total_tracked - len(code_changes)) / total_tracked
            
            # Determine recommendation
            recommendation = self._determine_recommendation(
                url_stability, code_stability, len(url_changes), len(code_changes)
            )
            
            return StabilityMetrics(
                retailer=retailer,
                total_products_tracked=total_tracked,
                url_changes_detected=len(url_changes),
                product_code_changes_detected=len(code_changes),
                url_stability_score=url_stability,
                product_code_stability_score=code_stability,
                sample_url_changes=url_changes[:5],  # Top 5 examples
                sample_code_changes=code_changes[:5],
                last_analyzed=datetime.utcnow(),
                recommendation=recommendation
            )
    
    def _determine_recommendation(self, url_stability: float, code_stability: float,
                                 url_changes: int, code_changes: int) -> str:
        """
        Determine best deduplication strategy based on stability
        
        Rules:
        - URL stability > 95% AND code stability > 95%: use_all (both reliable)
        - URL stability > 95%, code stability < 90%: use_url
        - Code stability > 95%, URL stability < 90%: use_code  
        - Both < 90%: use_title_price (neither reliable)
        """
        
        if url_stability > 0.95 and code_stability > 0.95:
            return "use_all"
        elif url_stability > 0.95:
            return "use_url_primary"
        elif code_stability > 0.95:
            return "use_code_primary"
        else:
            return "use_title_price_primary"
    
    async def analyze_catalog_vs_products_discrepancies(self, retailer: str, 
                                                       category: str) -> Dict:
        """
        Compare catalog_products vs products table to find mismatches
        
        This detects cases where:
        1. Same product (by title+price) has different codes in catalog vs products
        2. URLs changed between baseline and current catalog
        """
        
        logger.info(f"Analyzing catalog vs products discrepancies for {retailer} {category}")
        
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.cursor()
            
            # Find products in both tables with similar title+price but different codes
            await cursor.execute("""
                SELECT 
                    cp.product_code as catalog_code,
                    cp.title as catalog_title,
                    cp.price as catalog_price,
                    cp.catalog_url as catalog_url,
                    cp.discovered_date,
                    p.product_code as products_code,
                    p.title as products_title,
                    p.price as products_price,
                    p.url as products_url,
                    p.shopify_id
                FROM catalog_products cp
                JOIN products p ON p.retailer = cp.retailer
                    AND ABS(p.price - cp.price) < 1.0
                WHERE cp.retailer = ? AND cp.category = ?
                    AND cp.product_code IS NOT NULL
                    AND p.product_code IS NOT NULL
                    AND p.shopify_id IS NOT NULL
            """, (retailer, category))
            
            rows = await cursor.fetchall()
            
            discrepancies = []
            for row in rows:
                catalog_code, catalog_title, catalog_price, catalog_url = row[0], row[1], row[2], row[3]
                products_code, products_title, products_price, products_url, shopify_id = row[5], row[6], row[7], row[8], row[9]
                
                # Check title similarity
                title_similarity = difflib.SequenceMatcher(
                    None, catalog_title.lower(), products_title.lower()
                ).ratio()
                
                if title_similarity > 0.85:  # Likely same product
                    if catalog_code != products_code:
                        discrepancies.append({
                            'type': 'code_mismatch',
                            'catalog_code': catalog_code,
                            'products_code': products_code,
                            'title': catalog_title,
                            'price': catalog_price,
                            'title_similarity': round(title_similarity, 3),
                            'shopify_id': shopify_id,
                            'catalog_url': catalog_url,
                            'products_url': products_url
                        })
            
            return {
                'retailer': retailer,
                'category': category,
                'total_discrepancies': len(discrepancies),
                'discrepancies': discrepancies[:10],  # Top 10 examples
                'analysis_date': datetime.utcnow().isoformat()
            }
    
    async def store_stability_analysis(self, metrics: StabilityMetrics):
        """Store stability analysis in database for historical tracking"""
        
        async with aiosqlite.connect(self.db_path) as conn:
            # Create table if not exists
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS retailer_stability_tracking (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    retailer VARCHAR(100) NOT NULL,
                    analysis_date DATE NOT NULL,
                    total_products_tracked INTEGER,
                    url_changes_detected INTEGER,
                    product_code_changes_detected INTEGER,
                    url_stability_score DECIMAL(3,2),
                    product_code_stability_score DECIMAL(3,2),
                    recommendation VARCHAR(50),
                    sample_url_changes TEXT,
                    sample_code_changes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(retailer, analysis_date)
                )
            """)
            
            await conn.execute("""
                INSERT OR REPLACE INTO retailer_stability_tracking 
                (retailer, analysis_date, total_products_tracked, url_changes_detected,
                 product_code_changes_detected, url_stability_score, product_code_stability_score,
                 recommendation, sample_url_changes, sample_code_changes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metrics.retailer,
                metrics.last_analyzed.date(),
                metrics.total_products_tracked,
                metrics.url_changes_detected,
                metrics.product_code_changes_detected,
                metrics.url_stability_score,
                metrics.product_code_stability_score,
                metrics.recommendation,
                json.dumps(metrics.sample_url_changes),
                json.dumps(metrics.sample_code_changes)
            ))
            
            await conn.commit()
            logger.info(f"Stored stability analysis for {metrics.retailer}")
    
    async def get_stability_recommendation(self, retailer: str) -> Optional[str]:
        """Get current stability recommendation for a retailer"""
        
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.cursor()
            await cursor.execute("""
                SELECT recommendation, analysis_date 
                FROM retailer_stability_tracking 
                WHERE retailer = ? 
                ORDER BY analysis_date DESC 
                LIMIT 1
            """, (retailer,))
            
            result = await cursor.fetchone()
            if result:
                return result[0]
            return None
    
    async def generate_stability_report(self, retailers: List[str] = None) -> Dict:
        """Generate comprehensive stability report for all or specific retailers"""
        
        if retailers is None:
            # Get all retailers from products table
            async with aiosqlite.connect(self.db_path) as conn:
                cursor = await conn.cursor()
                await cursor.execute("SELECT DISTINCT retailer FROM products")
                retailers = [row[0] for row in await cursor.fetchall()]
        
        report = {
            'generated_at': datetime.utcnow().isoformat(),
            'retailers_analyzed': len(retailers),
            'retailer_metrics': {}
        }
        
        for retailer in retailers:
            metrics = await self.analyze_retailer_stability(retailer)
            report['retailer_metrics'][retailer] = asdict(metrics)
            
            # Store for future reference
            await self.store_stability_analysis(metrics)
        
        return report


# CLI Interface
async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Retailer URL/Product Code Stability Tracker")
    parser.add_argument('--retailer', type=str, help="Specific retailer to analyze")
    parser.add_argument('--all', action='store_true', help="Analyze all retailers")
    parser.add_argument('--check-discrepancies', action='store_true', 
                       help="Check catalog vs products discrepancies")
    parser.add_argument('--category', type=str, default='dresses', 
                       help="Category for discrepancy check")
    parser.add_argument('--lookback-days', type=int, default=30,
                       help="Days to look back for analysis")
    parser.add_argument('--report', action='store_true', 
                       help="Generate comprehensive report")
    
    args = parser.parse_args()
    
    tracker = RetailerStabilityTracker()
    
    if args.check_discrepancies and args.retailer:
        logger.info(f"Checking discrepancies for {args.retailer} {args.category}")
        result = await tracker.analyze_catalog_vs_products_discrepancies(
            args.retailer, args.category)
        print(json.dumps(result, indent=2))
        
    elif args.all or args.report:
        logger.info("Generating comprehensive stability report")
        report = await tracker.generate_stability_report()
        print(json.dumps(report, indent=2, default=str))
        
    elif args.retailer:
        logger.info(f"Analyzing stability for {args.retailer}")
        metrics = await tracker.analyze_retailer_stability(
            args.retailer, args.lookback_days)
        await tracker.store_stability_analysis(metrics)
        print(json.dumps(asdict(metrics), indent=2, default=str))
        
        # Display human-readable summary
        print(f"\n📊 STABILITY ANALYSIS: {metrics.retailer.upper()}")
        print(f"=" * 60)
        print(f"Products Tracked: {metrics.total_products_tracked}")
        print(f"URL Stability: {metrics.url_stability_score:.1%} ({metrics.url_changes_detected} changes)")
        print(f"Code Stability: {metrics.product_code_stability_score:.1%} ({metrics.product_code_changes_detected} changes)")
        print(f"\n🎯 RECOMMENDATION: {metrics.recommendation.upper().replace('_', ' ')}")
        
        if metrics.sample_code_changes:
            print(f"\n🚨 Sample Product Code Changes:")
            for change in metrics.sample_code_changes[:3]:
                print(f"  • {change['old_code']} → {change['new_code']}")
                print(f"    Title: {change['title'][:60]}...")
                print(f"    Price: ${change['price']}")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

