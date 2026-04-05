"""
Importa articulos.xlsx → tabla public.articulos_maestro en PostgreSQL.

Uso:
    python import_articulos_maestro.py                  # upsert incremental
    python import_articulos_maestro.py --full            # trunca y reimporta todo
    python import_articulos_maestro.py --dry-run         # solo muestra stats

Requisitos: pandas, openpyxl, sqlalchemy, psycopg2
"""

import os
import re
import sys
import unicodedata

import pandas as pd
from sqlalchemy import create_engine, text

EXCEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "articulos.xlsx")

# Mapeo COLUMNA_EXCEL → columna_db  (por nombre de header)
HEADER_TO_DB = {
    "Descripción": "descripcion",
    "Cód. Barras": "codigo_barras",
    "Código Artículo": "codigo_articulo",
    "Referencia": "referencia",
    "Descripción Adicional": "descripcion_adicional",
    "Departamento": "departamento",
    "Seccion": "seccion",
    "Família": "familia",
    "SubFamilia": "subfamilia",
    "Marca": "marca_erp",
    "Linea": "linea_erp",
    "PROVEEDOR": "proveedor",
    "DESCRIPCION_EBS": "descripcion_ebs",
    "UDM": "udm",
    "CAT_PRODUCTO": "cat_producto",
    "APLICACION": "aplicacion",
    "LINEA": "linea_clasificacion",
    "SUBLINEA": "sublinea",
    "MARCA": "marca_clasificacion",
    "FAMILIA": "familia_clasificacion",
    "SUBFAMILIA": "subfamilia_clasificacion",
    "TIPO": "tipo",
}

DB_COLUMNS = [
    "codigo_articulo",
    "referencia",
    "referencia_normalizada",
    "codigo_barras",
    "descripcion",
    "descripcion_adicional",
    "descripcion_ebs",
    "departamento",
    "seccion",
    "familia",
    "subfamilia",
    "marca_erp",
    "linea_erp",
    "proveedor",
    "udm",
    "cat_producto",
    "aplicacion",
    "linea_clasificacion",
    "sublinea",
    "marca_clasificacion",
    "familia_clasificacion",
    "subfamilia_clasificacion",
    "tipo",
]

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS public.articulos_maestro (
    id bigserial PRIMARY KEY,
    codigo_articulo text,
    referencia text NOT NULL,
    referencia_normalizada text,
    codigo_barras text,
    descripcion text,
    descripcion_adicional text,
    descripcion_ebs text,
    departamento text,
    seccion text,
    familia text,
    subfamilia text,
    marca_erp text,
    linea_erp text,
    proveedor text,
    udm text,
    cat_producto text,
    aplicacion text,
    linea_clasificacion text,
    sublinea text,
    marca_clasificacion text,
    familia_clasificacion text,
    subfamilia_clasificacion text,
    tipo text,
    activo boolean DEFAULT true,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_articulos_maestro_ref
    ON public.articulos_maestro (referencia);
CREATE INDEX IF NOT EXISTS idx_articulos_maestro_ref_norm
    ON public.articulos_maestro (referencia_normalizada);
CREATE INDEX IF NOT EXISTS idx_articulos_maestro_codigo
    ON public.articulos_maestro (codigo_articulo);
"""

UPSERT_SQL = """
INSERT INTO public.articulos_maestro (
    codigo_articulo, referencia, referencia_normalizada, codigo_barras,
    descripcion, descripcion_adicional, descripcion_ebs,
    departamento, seccion, familia, subfamilia, marca_erp, linea_erp,
    proveedor, udm, cat_producto, aplicacion,
    linea_clasificacion, sublinea, marca_clasificacion,
    familia_clasificacion, subfamilia_clasificacion, tipo
) VALUES (
    :codigo_articulo, :referencia, :referencia_normalizada, :codigo_barras,
    :descripcion, :descripcion_adicional, :descripcion_ebs,
    :departamento, :seccion, :familia, :subfamilia, :marca_erp, :linea_erp,
    :proveedor, :udm, :cat_producto, :aplicacion,
    :linea_clasificacion, :sublinea, :marca_clasificacion,
    :familia_clasificacion, :subfamilia_clasificacion, :tipo
)
ON CONFLICT (referencia) DO UPDATE SET
    codigo_articulo = EXCLUDED.codigo_articulo,
    referencia_normalizada = EXCLUDED.referencia_normalizada,
    codigo_barras = EXCLUDED.codigo_barras,
    descripcion = EXCLUDED.descripcion,
    descripcion_adicional = EXCLUDED.descripcion_adicional,
    descripcion_ebs = EXCLUDED.descripcion_ebs,
    departamento = EXCLUDED.departamento,
    seccion = EXCLUDED.seccion,
    familia = EXCLUDED.familia,
    subfamilia = EXCLUDED.subfamilia,
    marca_erp = EXCLUDED.marca_erp,
    linea_erp = EXCLUDED.linea_erp,
    proveedor = EXCLUDED.proveedor,
    udm = EXCLUDED.udm,
    cat_producto = EXCLUDED.cat_producto,
    aplicacion = EXCLUDED.aplicacion,
    linea_clasificacion = EXCLUDED.linea_clasificacion,
    sublinea = EXCLUDED.sublinea,
    marca_clasificacion = EXCLUDED.marca_clasificacion,
    familia_clasificacion = EXCLUDED.familia_clasificacion,
    subfamilia_clasificacion = EXCLUDED.subfamilia_clasificacion,
    tipo = EXCLUDED.tipo,
    updated_at = now()
"""


def get_db_url():
    return (
        os.getenv("DATABASE_URL")
        or os.getenv("POSTGRES_DB_URI")
        or "postgresql://postgres:postgres@localhost:5432/ferreinox"
    )


def keep_alnum(text_val):
    """Replica public.fn_keep_alnum de PostgreSQL."""
    if not text_val or str(text_val).strip() in ("", "None"):
        return None
    s = str(text_val).strip().upper()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^A-Z0-9]", "", s)
    return s or None


def clean_cell(val):
    """Limpia celdas del Excel: quita whitespace, convierte vacíos/nulos a None."""
    if val is None or pd.isna(val):
        return None
    s = str(val).strip()
    if s in ("", "None", "0", " ", "nan"):
        return None
    return s


def main():
    full_mode = "--full" in sys.argv
    dry_run = "--dry-run" in sys.argv

    excel_path = EXCEL_PATH
    if not os.path.exists(excel_path):
        # Intentar ruta alternativa
        alt = os.path.join(os.getcwd(), "articulos.xlsx")
        if os.path.exists(alt):
            excel_path = alt
        else:
            print(f"ERROR: No se encontró {EXCEL_PATH}")
            sys.exit(1)

    print(f"Leyendo {excel_path} ...")
    df = pd.read_excel(excel_path, sheet_name="Hoja1", header=0, dtype=str)
    print(f"  Filas totales en Excel: {len(df)}")

    # --- Seleccionar y renombrar columnas ---
    rename_map = {}
    available_headers = list(df.columns)
    for header, db_col in HEADER_TO_DB.items():
        matches = [h for h in available_headers if h.strip() == header.strip()]
        if matches:
            # Si hay duplicados (e.g. "MARCA" aparece 2 veces), tomar el último (el de clasificación)
            rename_map[matches[-1]] = db_col
        else:
            print(f"  WARN: columna '{header}' no encontrada en Excel")

    df_sel = df[list(rename_map.keys())].copy()
    df_sel.columns = [rename_map[c] for c in df_sel.columns]

    # --- Limpiar datos ---
    for col in df_sel.columns:
        df_sel[col] = df_sel[col].apply(clean_cell)

    # --- Filtrar: debe tener referencia ---
    df_sel = df_sel[df_sel["referencia"].notna()].copy()
    print(f"  Con referencia: {len(df_sel)}")

    # --- Dedup por referencia (conservar primer registro) ---
    df_sel = df_sel.drop_duplicates(subset="referencia", keep="first")
    print(f"  Únicas por referencia: {len(df_sel)}")

    # --- Calcular referencia_normalizada ---
    df_sel["referencia_normalizada"] = df_sel["referencia"].apply(keep_alnum)

    # --- Asegurar todas las columnas existen ---
    for col in DB_COLUMNS:
        if col not in df_sel.columns:
            df_sel[col] = None

    # --- Stats ---
    non_null = {col: df_sel[col].notna().sum() for col in DB_COLUMNS if col != "referencia_normalizada"}
    print("\n  Columnas con datos:")
    for col, cnt in sorted(non_null.items(), key=lambda x: -x[1]):
        if cnt > 0:
            print(f"    {col}: {cnt:,}")

    # --- Muestras de clasificación ---
    print("\n  Muestra MARCA_CLASIFICACION (top 10):")
    top_marca = df_sel["marca_clasificacion"].value_counts().head(10)
    for val, cnt in top_marca.items():
        print(f"    {val}: {cnt}")

    print("\n  Muestra LINEA_CLASIFICACION (top 10):")
    top_linea = df_sel["linea_clasificacion"].value_counts().head(10)
    for val, cnt in top_linea.items():
        print(f"    {val}: {cnt}")

    if dry_run:
        print("\n  [DRY RUN] No se ejecutan cambios en la base de datos.")
        return

    # --- Conexión y carga ---
    db_url = get_db_url()
    print(f"\n  Conectando a la base de datos...")
    engine = create_engine(db_url)

    with engine.begin() as conn:
        # Crear tabla si no existe
        for stmt in CREATE_TABLE_SQL.split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(text(stmt))
        print("  Tabla articulos_maestro verificada/creada.")

        if full_mode:
            conn.execute(text("TRUNCATE public.articulos_maestro RESTART IDENTITY"))
            print("  Tabla truncada (modo --full).")

        # Upsert en batches
        records = df_sel[DB_COLUMNS].to_dict("records")
        batch_size = 500
        total_batches = (len(records) + batch_size - 1) // batch_size
        inserted = 0

        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]
            conn.execute(text(UPSERT_SQL), batch)
            inserted += len(batch)
            batch_num = (i // batch_size) + 1
            if batch_num % 10 == 0 or batch_num == total_batches:
                print(f"    Batch {batch_num}/{total_batches} — {inserted:,} registros procesados")

        print(f"\n  COMPLETADO: {inserted:,} artículos importados/actualizados.")

        # Verificar
        count = conn.execute(text("SELECT COUNT(*) FROM public.articulos_maestro")).scalar()
        print(f"  Total en tabla: {count:,}")

    engine.dispose()
    print("  Conexión cerrada.")


if __name__ == "__main__":
    main()
