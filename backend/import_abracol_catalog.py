"""
Importar catálogo Abracol desde Dropbox (hoja Productos) a PostgreSQL.
Crea tabla abracol_productos y enriquece búsquedas del agente.

Uso:
    python backend/import_abracol_catalog.py [--secrets PATH]

Requiere:
    - Dropbox access (via secrets.toml o env vars)
    - PostgreSQL access (DATABASE_URL, POSTGRES_DB_URI, o secrets.toml)
"""
import argparse
import os
import sys
from pathlib import Path
from io import BytesIO

import pandas as pd
from sqlalchemy import create_engine, text

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from frontend.config import get_dropbox_sources
from frontend.dropbox_sync_service import get_dropbox_client


# ══════════════════════════════════════════════════════════════════════
# SQL
# ══════════════════════════════════════════════════════════════════════

CREATE_TABLE_SQL = """
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
    -- Campos derivados
    search_keywords text,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_abracol_productos_portafolio
    ON public.abracol_productos (portafolio);
CREATE INDEX IF NOT EXISTS idx_abracol_productos_familia
    ON public.abracol_productos (familia);
CREATE INDEX IF NOT EXISTS idx_abracol_search_keywords_trgm
    ON public.abracol_productos USING GIN (search_keywords gin_trgm_ops);

COMMENT ON TABLE public.abracol_productos IS
    'Catálogo enriquecido de productos complementarios (Abracol, Goya, Yale, Tekbond, etc.) '
    'importado desde Excel Dropbox. Contiene nombre comercial, familia, descripción larga '
    'para mejorar la búsqueda del agente.';
"""

UPSERT_SQL = """
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

# Patch mv_productos to include abracol data in search_blob
# This adds nombre_comercial + familia_abracol + descripcion_larga to search
PATCH_MV_SQL = """
-- Add abracol enrichment to mv_productos search_blob
-- Run after creating abracol_productos table
-- This is done via a separate enrichment view that LEFT JOINs

DROP VIEW IF EXISTS public.vw_abracol_search_enrichment CASCADE;
CREATE OR REPLACE VIEW public.vw_abracol_search_enrichment AS
SELECT
    a.codigo,
    LOWER(
        COALESCE(a.nombre_comercial, '') || ' ' ||
        COALESCE(a.familia, '') || ' ' ||
        COALESCE(a.descripcion_larga, '') || ' ' ||
        COALESCE(a.portafolio, '') || ' ' ||
        COALESCE(a.grano, '') || ' ' ||
        COALESCE(a.medida, '')
    ) AS abracol_search_text
FROM public.abracol_productos a;
"""


def resolve_db_uri(secrets_path=None):
    """Resolve database URI from env or secrets."""
    env_db_uri = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_DB_URI")
    if env_db_uri:
        return env_db_uri

    import tomllib
    candidates = [
        Path(secrets_path) if secrets_path else None,
        PROJECT_ROOT / "frontend" / ".streamlit" / "secrets.toml",
        PROJECT_ROOT / ".streamlit" / "secrets.toml",
    ]
    for candidate in candidates:
        if candidate and candidate.exists():
            secrets = tomllib.loads(candidate.read_text(encoding="utf-8"))
            if "postgres" in secrets:
                return secrets["postgres"]["db_uri"]
    raise RuntimeError("No se encontró DATABASE_URL ni secrets.toml con postgres.db_uri")


def build_search_keywords(row):
    """Build a combined search text from all fields for trigram matching."""
    parts = [
        row.get("NOMBRE COMERCIAL") or "",
        row.get("DESCRIPCION") or "",
        row.get("FAMILIA") or "",
        row.get("PORTAFOLIO") or "",
        row.get("GRANO") or "",
        row.get("MEDIDA") or "",
        row.get("DESCRIPCION_LARGA") or "",
    ]
    return " ".join(p.strip() for p in parts if p.strip()).lower()


def download_abracol_from_dropbox():
    """Download and parse Abracol Excel from Dropbox."""
    sources = get_dropbox_sources()
    rotacion = None
    for key, cfg in sources.items():
        if "rotaci" in key.lower():
            rotacion = cfg
            break
    if not rotacion:
        raise RuntimeError("No se encontró config dropbox_rotacion")

    dbx = get_dropbox_client(rotacion)
    folder = rotacion.get("folder", "/data")

    # Find Abracol file
    result = dbx.files_list_folder(folder)
    abracol_path = None
    for entry in result.entries:
        if "abracol" in entry.name.lower() and entry.name.lower().endswith((".xlsx", ".xls")):
            abracol_path = entry.path_lower
            break

    if not abracol_path:
        raise FileNotFoundError(f"No se encontró archivo Abracol en {folder}")

    print(f"Descargando {abracol_path}...")
    _, response = dbx.files_download(abracol_path)
    df = pd.read_excel(BytesIO(response.content), sheet_name="Productos", dtype=str)
    print(f"  {len(df)} filas x {len(df.columns)} columnas")
    return df


def import_to_db(df, db_uri):
    """Import Abracol catalog to PostgreSQL."""
    engine = create_engine(db_uri)

    with engine.begin() as conn:
        # Create table
        for stmt in CREATE_TABLE_SQL.split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(text(stmt))
        print("Tabla abracol_productos creada/verificada")

        # Prepare rows
        rows = []
        for _, row in df.iterrows():
            codigo = (row.get("CODIGO") or "").strip()
            if not codigo:
                continue
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
                "search_keywords": build_search_keywords(row),
            })

        # Batch upsert
        batch_size = 200
        total = 0
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            conn.execute(text(UPSERT_SQL), batch)
            total += len(batch)
            print(f"  Upserted {total}/{len(rows)}...")

        # Create enrichment view
        for stmt in PATCH_MV_SQL.split(";"):
            stmt = stmt.strip()
            if stmt and not stmt.startswith("--"):
                conn.execute(text(stmt))
        print("Vista vw_abracol_search_enrichment creada")

    print(f"\nImportación completada: {len(rows)} productos Abracol")
    return len(rows)


def main():
    parser = argparse.ArgumentParser(description="Importar catálogo Abracol desde Dropbox")
    parser.add_argument("--secrets", help="Path to secrets.toml")
    parser.add_argument("--local-csv", help="Use local CSV instead of Dropbox download")
    args = parser.parse_args()

    if args.local_csv:
        print(f"Leyendo CSV local: {args.local_csv}")
        df = pd.read_csv(args.local_csv, dtype=str)
    else:
        df = download_abracol_from_dropbox()

    db_uri = resolve_db_uri(args.secrets)
    count = import_to_db(df, db_uri)
    print(f"\n✅ {count} productos Abracol importados exitosamente")


if __name__ == "__main__":
    main()
