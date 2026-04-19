import pandas as pd

df = pd.read_csv("data/abracol_productos.csv", dtype=str)

print("=== PORTAFOLIO -> FAMILIAS ===")
for port in sorted(df["PORTAFOLIO"].dropna().unique()):
    subset = df[df["PORTAFOLIO"] == port]
    fams = subset["FAMILIA"].dropna().unique()[:8]
    print(f"{port} ({len(subset)} prods): {list(fams)}")
print()

search_families = df.groupby("FAMILIA").agg(count=("CODIGO", "count")).reset_index().sort_values("count", ascending=False).head(25)
print("=== TOP 25 FAMILIAS MÁS BUSCADAS ===")
for _, row in search_families.iterrows():
    sample = df[df["FAMILIA"] == row["FAMILIA"]]["NOMBRE COMERCIAL"].head(3).tolist()
    print(f"  {row['FAMILIA']} ({row['count']}): {sample}")

# Check DESCRIPCION_LARGA quality
non_null_desc = df["DESCRIPCION_LARGA"].dropna()
print(f"\nDESCRIPCION_LARGA: {len(non_null_desc)} de {len(df)} tienen descripción")
print(f"Largo promedio: {non_null_desc.str.len().mean():.0f} chars")
