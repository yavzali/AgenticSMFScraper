#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('/var/www/html/web_assessment/data/products.db')
cursor = conn.cursor()

print("=== MIGRATION VERIFICATION ===")

# Total pending
cursor.execute("SELECT COUNT(*) FROM assessment_queue WHERE status = 'pending'")
total = cursor.fetchone()[0]
print(f"Total pending: {total}")

# By source
cursor.execute("""
SELECT source_workflow, retailer, COUNT(*) 
FROM assessment_queue 
WHERE status = 'pending' 
GROUP BY source_workflow, retailer
""")
results = cursor.fetchall()
print("\nBy source:")
for row in results:
    print(f"  {row[0]} - {row[1]}: {row[2]}")

# Catalog status
cursor.execute("SELECT review_status, COUNT(*) FROM catalog_products GROUP BY review_status")
catalog = cursor.fetchall()
print("\nCatalog status:")
for row in catalog:
    print(f"  {row[0]}: {row[1]}")

conn.close()
