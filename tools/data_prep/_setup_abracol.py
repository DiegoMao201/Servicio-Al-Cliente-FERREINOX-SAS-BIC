"""
Quick setup: Create abracol_productos table + import from local CSV.
Run this locally to populate the production DB.
"""
import os
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Get DB URI from secrets.toml
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib
secrets_path = PROJECT_ROOT / "frontend" / ".streamlit" / "secrets.toml"
secrets = tomllib.loads(secrets_path.read_text(encoding="utf-8"))
db_uri = secrets["postgres"]["db_uri"]

engine = create_engine(db_uri)

# 1. Create table
print("Creating abracol_productos table...")
with engine.begin() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS public.abracol_productos (
            codigo varchar(20) PRIMARY KEY,
            nombre_comercial text,
            descripcion text,
            grano varchar(60),
            medida varchar(120),
            familia varchar(200),
            empaque varchar(20),
            portafolio varchar(60),
            descripcion_larga text,
            search_keywords text,
            created_at timestamptz DEFAULT now(),
            updated_at timestamptz DEFAULT now()
        )
    """))
    # Create indexes
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_abracol_productos_portafolio ON public.abracol_productos (portafolio)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_abracol_productos_familia ON public.abracol_productos (familia)"))
    try:
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_abracol_search_keywords_trgm ON public.abracol_productos USING GIN (search_keywords gin_trgm_ops)"))
    except Exception as e:
        print(f"  Trigram index skipped: {e}")
    print("  Table created/verified.")

# 2. Load CSV
csv_path = PROJECT_ROOT / "data" / "abracol_productos.csv"
print(f"Loading {csv_path}...")
df = pd.read_csv(csv_path, dtype=str)
print(f"  {len(df)} rows loaded.")

# 3. Upsert
upsert_sql = """
INSERT INTO public.abracol_productos (
    codigo, nombre_comercial, descripcion, grano, medida,
    familia, empaque, portafolio, descripcion_larga, search_keywords
) VALUES (
    :codigo, :nombre_comercial, :descripcion, :grano, :medida,
    :familia, :empaque, :portafolio, :descripcion_larga, :search_keywords
)
ON CONFLICT (codigo) DO UPDATE SET
    nombre_comercial = EXCLUDED.nombre_comercial,
    descripcion = EXCLUDED.descripcion,
    grano = EXCLUDED.grano,
    medida = EXCLUDED.medida,
    familia = EXCLUDED.familia,
    empaque = EXCLUDED.empaque,
    portafolio = EXCLUDED.portafolio,
    descripcion_larga = EXCLUDED.descripcion_larga,
    search_keywords = EXCLUDED.search_keywords,
    updated_at = now();
"""

rows = []
for _, row in df.iterrows():
    codigo = (row.get("CODIGO") or "").strip()
    if not codigo:
        continue
    sk_parts = [row.get(c) or "" for c in ["NOMBRE COMERCIAL", "DESCRIPCION", "FAMILIA", "PORTAFOLIO", "GRANO", "MEDIDA", "DESCRIPCION_LARGA"]]
    rows.append({
        "codigo": codigo,
        "nombre_comercial": (row.get("NOMBRE COMERCIAL") or "").strip() or None,
        "descripcion": (row.get("DESCRIPCION") or "").strip() or None,
        "grano": (row.get("GRANO") or "").strip() or None,
        "medida": (row.get("MEDIDA") or "").strip() or None,
        "familia": (row.get("FAMILIA") or "").strip() or None,
        "empaque": (row.get("EMPAQUE") or "").strip() or None,
        "portafolio": (row.get("PORTAFOLIO") or "").strip() or None,
        "descripcion_larga": (row.get("DESCRIPCION_LARGA") or "").strip() or None,
        "search_keywords": " ".join(p.strip() for p in sk_parts if p.strip()).lower(),
    })

print(f"Upserting {len(rows)} products...")
with engine.begin() as conn:
    batch_size = 200
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        conn.execute(text(upsert_sql), batch)
        print(f"  {min(i + batch_size, len(rows))}/{len(rows)}...")

# 4. Verify
with engine.connect() as conn:
    count = conn.execute(text("SELECT COUNT(*) FROM public.abracol_productos")).scalar()
    print(f"\n✅ abracol_productos: {count} rows")
    
    # Show portafolio distribution
    dist = conn.execute(text("""
        SELECT portafolio, COUNT(*) as cnt 
        FROM public.abracol_productos 
        GROUP BY portafolio 
        ORDER BY cnt DESC
    """)).fetchall()
    for p, c in dist:
        print(f"  {p}: {c}")

# 5. Now recreate mv_productos with Abracol join
print("\nRecreating mv_productos with Abracol enrichment...")
views_sql_path = PROJECT_ROOT / "backend" / "postgrest_views.sql"
views_sql = views_sql_path.read_text(encoding="utf-8")

# Extract just the mv_productos section
import re
# Find the mv_productos block
mv_match = re.search(
    r'(CREATE TABLE IF NOT EXISTS public\.abracol_productos.*?)(CREATE UNIQUE INDEX.*?idx_mv_productos.*?COMMIT;)',
    views_sql, re.DOTALL
)
if mv_match:
    # We need to run: DROP + CREATE matview + indexes
    # Extract from DROP MATERIALIZED VIEW to COMMIT
    mv_section = re.search(
        r'(DROP MATERIALIZED VIEW IF EXISTS mv_productos.*?CREATE INDEX.*?idx_mv_productos_referencia.*?;)',
        views_sql, re.DOTALL
    )
    if mv_section:
        with engine.begin() as conn:
            for stmt in mv_section.group(1).split(';'):
                stmt = stmt.strip()
                if stmt and not stmt.startswith('--'):
                    try:
                        conn.execute(text(stmt))
                    except Exception as e:
                        print(f"  WARN: {e}")
        print("  mv_productos recreated with Abracol JOIN.")
    else:
        print("  WARN: Could not extract mv_productos SQL section.")
else:
    print("  WARN: Could not find mv_productos in postgrest_views.sql")

# Verify enrichment
with engine.connect() as conn:
    enriched = conn.execute(text("""
        SELECT COUNT(*) FROM mv_productos 
        WHERE nombre_comercial_abracol IS NOT NULL
    """)).scalar()
    total = conn.execute(text("SELECT COUNT(*) FROM mv_productos")).scalar()
    print(f"\n✅ mv_productos: {total} total, {enriched} with Abracol enrichment")
    
    # Sample enriched product
    sample = conn.execute(text("""
        SELECT producto_codigo, descripcion, nombre_comercial_abracol, familia_abracol, portafolio_abracol
        FROM mv_productos
        WHERE nombre_comercial_abracol IS NOT NULL
        LIMIT 3
    """)).fetchall()
    for s in sample:
        print(f"  {s[0]}: {s[1]} → {s[2]} | {s[3]} | {s[4]}")

print("\n✅ Abracol integration complete!")
engine.dispose()
