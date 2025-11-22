import sqlite3

print("Starting duplicate cleanup...")

conn = sqlite3.connect("/var/www/html/web_assessment/data/products.db")
cursor = conn.cursor()

# Before cleanup
cursor.execute("SELECT COUNT(*) FROM assessment_queue WHERE status = 'pending'")
before = cursor.fetchone()[0]
print(f"Before: {before} pending products")

# Remove duplicates
cursor.execute("""
DELETE FROM assessment_queue
WHERE product_url IN (
  SELECT q.product_url 
  FROM assessment_queue q
  INNER JOIN products p ON q.product_url = p.url
  WHERE q.status = 'pending' AND p.shopify_id IS NOT NULL
)
""")

deleted = cursor.rowcount
print(f"Deleted: {deleted} duplicates")

# After cleanup
cursor.execute("SELECT COUNT(*) FROM assessment_queue WHERE status = 'pending'")
after = cursor.fetchone()[0]
print(f"After: {after} pending products")

# Show breakdown
cursor.execute("""
SELECT source_workflow, retailer, COUNT(*) 
FROM assessment_queue WHERE status = 'pending'
GROUP BY source_workflow, retailer
""")

results = cursor.fetchall()
print("\nRemaining products:")
for row in results:
    print(f"  {row[0]} - {row[1]}: {row[2]}")

conn.commit()
conn.close()
print("\nCleanup complete!")
