"""
Quick Status Check - View last scan times and baseline status
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../Shared"))

import sqlite3
from datetime import datetime
from tabulate import tabulate

DB_PATH = os.path.join(os.path.dirname(__file__), "../Shared/products.db")

def check_status():
    """Display last scan status for all retailers/categories"""
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("=" * 100)
    print("📅 CATALOG CRAWLER STATUS")
    print("=" * 100)
    
    # Get baseline status
    cursor.execute("""
        SELECT 
            retailer,
            category,
            baseline_date,
            total_products_seen,
            baseline_status,
            created_at
        FROM catalog_baselines
        ORDER BY retailer, category
    """)
    
    baselines = cursor.fetchall()
    
    if baselines:
        print("\n📊 BASELINE STATUS:\n")
        table_data = []
        for retailer, category, baseline_date, total_products, status, created_at in baselines:
            # Calculate days since baseline
            if created_at:
                created_dt = datetime.fromisoformat(created_at)
                days_old = (datetime.now() - created_dt).days
            else:
                days_old = "?"
            
            table_data.append([
                retailer.title(),
                category.title(),
                baseline_date,
                total_products,
                status.upper(),
                f"{days_old} days ago"
            ])
        
        headers = ["Retailer", "Category", "Baseline Date", "Products", "Status", "Age"]
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
    else:
        print("\n⚠️  No baselines established yet")
        print("   Run: python catalog_main.py --establish-baseline <retailer> <category>")
    
    # Get most recent scans
    cursor.execute("""
        SELECT 
            retailer,
            category,
            run_type,
            actual_start_time,
            completed_at,
            run_status,
            total_products_crawled,
            new_products_found
        FROM catalog_monitoring_runs
        WHERE retailer IS NOT NULL AND category IS NOT NULL
        ORDER BY actual_start_time DESC
        LIMIT 10
    """)
    
    runs = cursor.fetchall()
    
    if runs:
        print("\n\n🕐 RECENT CRAWL HISTORY:\n")
        table_data = []
        for retailer, category, run_type, start_time, completed_at, status, total_products, new_products in runs:
            # Calculate time ago
            if start_time:
                start_dt = datetime.fromisoformat(start_time)
                hours_ago = (datetime.now() - start_dt).total_seconds() / 3600
                if hours_ago < 1:
                    time_ago = f"{int(hours_ago * 60)}m ago"
                elif hours_ago < 24:
                    time_ago = f"{int(hours_ago)}h ago"
                else:
                    time_ago = f"{int(hours_ago / 24)}d ago"
            else:
                time_ago = "?"
            
            table_data.append([
                retailer.title(),
                category.title(),
                run_type.replace('_', ' ').title(),
                time_ago,
                status or "running",
                total_products,
                new_products
            ])
        
        headers = ["Retailer", "Category", "Type", "Time Ago", "Status", "Total", "New"]
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
    else:
        print("\n\n⚠️  No crawl history yet")
    
    # Next scan recommendations
    print("\n\n💡 NEXT STEPS:\n")
    
    if not baselines:
        print("  1️⃣  Establish baselines first:")
        print("      python catalog_main.py --establish-baseline revolve dresses")
    else:
        # Check which baselines are ready for monitoring
        cursor.execute("""
            SELECT 
                b.retailer,
                b.category,
                b.created_at,
                MAX(r.actual_start_time) as last_scan
            FROM catalog_baselines b
            LEFT JOIN catalog_monitoring_runs r
                ON b.retailer = r.retailer 
                AND b.category = r.category
                AND r.run_type = 'weekly_monitoring'
            GROUP BY b.retailer, b.category
        """)
        
        ready_for_monitoring = []
        for retailer, category, baseline_created, last_scan in cursor.fetchall():
            if not last_scan:
                ready_for_monitoring.append(f"{retailer} {category}")
        
        if ready_for_monitoring:
            print(f"  📍 {len(ready_for_monitoring)} baseline(s) ready for first monitoring run:")
            for item in ready_for_monitoring[:5]:
                print(f"      python catalog_main.py --monitor {item}")
        else:
            print("  ✅ All baselines have been monitored at least once")
            print("      Continue with weekly monitoring as scheduled")
    
    print("\n" + "=" * 100)
    
    conn.close()

if __name__ == "__main__":
    try:
        check_status()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

