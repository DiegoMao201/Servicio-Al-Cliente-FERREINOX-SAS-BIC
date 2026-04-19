import psycopg2, json

conn = psycopg2.connect(host='192.81.216.49', port=3000, dbname='postgres', user='postgres', password='Ferreinox2024*')
cur = conn.cursor()

# All distinct CAT_PRODUCTO with counts
cur.execute("""
    SELECT UPPER(TRIM(cat_producto)) as cat, COUNT(*) as cnt
    FROM articulos
    WHERE cat_producto IS NOT NULL AND TRIM(cat_producto) != ''
    GROUP BY UPPER(TRIM(cat_producto))
    ORDER BY COUNT(*) DESC
""")
rows = cur.fetchall()
print(f"=== CAT_PRODUCTO ({len(rows)} categorías distintas) ===")
for r in rows:
    print(f"{r[1]:5d}  {r[0]}")

# Also get sample of each CAT with brand and name
print("\n=== SAMPLE POR CATEGORÍA ===")
cur.execute("""
    SELECT UPPER(TRIM(cat_producto)) as cat, marca, descripcion
    FROM articulos
    WHERE cat_producto IS NOT NULL AND TRIM(cat_producto) != ''
    ORDER BY cat_producto, marca, descripcion
    LIMIT 300
""")
rows2 = cur.fetchall()
prev = None
for r in rows2:
    if r[0] != prev:
        print(f"\n--- {r[0]} ---")
        prev = r[0]
    print(f"  [{r[1]}] {r[2]}")

conn.close()
