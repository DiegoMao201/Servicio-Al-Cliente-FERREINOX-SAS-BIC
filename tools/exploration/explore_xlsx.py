"""
Explorar articulos.xlsx y mapear CAT_PRODUCTO completo.
"""
import pandas as pd, json

df = pd.read_excel("articulos.xlsx", dtype=str)
df.columns = [c.strip().upper() for c in df.columns]
print(f"Columnas: {list(df.columns)}")
print(f"Total filas: {len(df)}")
print()

# Check which column is CAT_PRODUCTO
cat_col = None
for c in df.columns:
    if "CAT" in c and "PROD" in c:
        cat_col = c
        break
if not cat_col:
    # Look for any column with similar name
    for c in df.columns:
        print(f"  Column: {c!r}")
    raise ValueError("No CAT_PRODUCTO column found")

print(f"=== CAT_PRODUCTO column: {cat_col!r} ===\n")

# Count distinct CAT values
cats = df[cat_col].fillna("").str.upper().str.strip()
dist = cats.value_counts()
print(f"Distinct values: {len(dist)}\n")
for cat, cnt in dist.items():
    if cat:
        print(f"{cnt:5d}  {cat}")

print("\n=== MUESTRA POR CATEGORÍA (top 5 per cat) ===")

# Find marca and descripcion columns
marca_col = next((c for c in df.columns if "MARCA" in c), None)
desc_col = next((c for c in df.columns if "DESCRIPCION" in c or "DESC" in c), None)
name_col = next((c for c in df.columns if "NOMBRE" in c or "NAME" in c), None)

print(f"Marca col: {marca_col}, Desc col: {desc_col}")
print()

for cat in dist.index:
    if not cat:
        continue
    subset = df[cats == cat]
    print(f"\n--- {cat} ({len(subset)} items) ---")
    for _, row in subset.head(8).iterrows():
        desc = row.get(desc_col, "") if desc_col else ""
        marca = row.get(marca_col, "") if marca_col else ""
        print(f"  [{marca}] {desc}")
