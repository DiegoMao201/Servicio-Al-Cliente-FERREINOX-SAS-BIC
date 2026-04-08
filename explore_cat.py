"""
Query CAT_PRODUCTO via admin SQL endpoint y mapear portafolio completo.
"""
import requests, json

BACKEND_URL = "https://apicrm.datovatenexuspro.com"
ADMIN_KEY = "ferreinox_admin_2024"
headers = {"x-admin-key": ADMIN_KEY, "Content-Type": "application/json"}

# Try admin SQL query endpoint
sql_queries = [
    {
        "label": "CAT_PRODUCTO distinct counts",
        "sql": "SELECT UPPER(TRIM(cat_producto)) as cat, COUNT(*) as cnt FROM articulos WHERE cat_producto IS NOT NULL AND TRIM(cat_producto) != '' GROUP BY UPPER(TRIM(cat_producto)) ORDER BY cnt DESC"
    },
    {
        "label": "Sample by CAT + marca",  
        "sql": "SELECT UPPER(TRIM(cat_producto)) as cat, marca, COUNT(*) as cnt FROM articulos WHERE cat_producto IS NOT NULL AND TRIM(cat_producto) != '' GROUP BY UPPER(TRIM(cat_producto)), marca ORDER BY cat, cnt DESC"
    },
    {
        "label": "All distinct marcas",
        "sql": "SELECT marca, COUNT(*) as cnt FROM articulos GROUP BY marca ORDER BY cnt DESC"
    }
]

for q in sql_queries:
    print(f"\n=== {q['label']} ===")
    r = requests.post(
        f"{BACKEND_URL}/admin/sql",
        headers=headers,
        json={"query": q["sql"]},
        timeout=15
    )
    if r.status_code == 200:
        data = r.json()
        rows = data.get("rows", data.get("results", data.get("data", [])))
        for row in rows[:60]:
            print(row)
    else:
        print(f"HTTP {r.status_code}: {r.text[:200]}")
