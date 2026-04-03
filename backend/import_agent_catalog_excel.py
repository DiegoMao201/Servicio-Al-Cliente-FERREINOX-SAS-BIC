import argparse
import os
from pathlib import Path
import re
import sys
import tomllib

import pandas as pd
from sqlalchemy import create_engine, text

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from frontend.dropbox_sync_service import ensure_postgrest_access, execute_sql_script


PRODUCT_SHEET = "productos_priorizados"
ALIAS_SHEET = "alias_y_desambiguacion_v2"
FAMILY_SHEET = "familias_sugeridas"
PRESENTATION_SHEET = "presentaciones_canonicas"
RULE_SHEET = "reglas_agente_v2"
WORKBOOK_VERSION = "v2"
ALIAS_SHEET_CANDIDATES = ["alias_y_desambiguacion_v3", "alias_y_desambiguacion_v2"]
FAMILY_SHEET_CANDIDATES = ["familias_sugeridas_v3", "familias_sugeridas", "familias_sugeridas_v2"]


def resolve_secrets_path(cli_path=None):
    if cli_path:
        path = Path(cli_path).resolve()
        if path.exists():
            return path
        raise FileNotFoundError(f"No se encontró el archivo de secrets: {path}")

    candidates = [
        Path("frontend/.streamlit/secrets.toml").resolve(),
        Path(".streamlit/secrets.toml").resolve(),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def load_secrets(secrets_path):
    return tomllib.loads(Path(secrets_path).read_text(encoding="utf-8"))


def resolve_db_uri(secrets_path=None):
    env_db_uri = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_DB_URI")
    if env_db_uri:
        return env_db_uri, None

    resolved_secrets = resolve_secrets_path(secrets_path)
    if not resolved_secrets:
        raise RuntimeError("No se encontró DATABASE_URL/POSTGRES_DB_URI ni un archivo secrets.toml válido.")

    secrets = load_secrets(resolved_secrets)
    return secrets["postgres"]["db_uri"], resolved_secrets


def clean_scalar(value):
    if pd.isna(value):
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    return value


def clean_text(value):
    value = clean_scalar(value)
    if value is None:
        return None
    return str(value).strip()


def clean_catalog_text(value, drop_zero_only=False, strip_leading_zero_token=False):
    value = clean_text(value)
    if value is None:
        return None

    normalized = re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()
    if drop_zero_only and normalized in {"0", "0.0"}:
        return None
    if strip_leading_zero_token:
        normalized = re.sub(r"^0(?:[_\s-]+)", "", normalized).strip()
        normalized = re.sub(r"_+", "_", normalized)
    if normalized in {"", "0", "0.0"}:
        return None
    return normalized


def clean_bool(value):
    value = clean_scalar(value)
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    normalized = str(value).strip().lower()
    return normalized in {"1", "true", "t", "si", "sí", "yes", "y", "activo"}


def clean_numeric(value):
    value = clean_scalar(value)
    if value is None:
        return None
    if isinstance(value, str):
        value = value.replace(",", ".")
    return value


def clean_date(value):
    value = clean_scalar(value)
    if value is None:
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date()


def normalize_workbook_path(excel_path):
    candidate = Path(excel_path)
    if candidate.is_absolute() and candidate.exists():
        return candidate

    project_root = Path(__file__).resolve().parent.parent
    search_paths = [
        Path.cwd() / candidate,
        project_root / candidate,
        project_root / "artifacts" / candidate.name,
    ]
    for search_path in search_paths:
        resolved = search_path.resolve()
        if resolved.exists():
            return resolved
    raise FileNotFoundError(f"No se encontró el archivo Excel: {excel_path}")


def resolve_sheet_name(workbook_path, candidates, required=True):
    excel_file = pd.ExcelFile(workbook_path)
    for candidate in candidates:
        if candidate in excel_file.sheet_names:
            return candidate
    if required:
        raise ValueError(f"No se encontró ninguna hoja válida entre: {', '.join(candidates)}")
    return None


def build_product_dataframe(workbook_path):
    dataframe = pd.read_excel(workbook_path, sheet_name=PRODUCT_SHEET)
    records = []
    for row in dataframe.to_dict(orient="records"):
        producto_codigo = clean_text(row.get("producto_codigo"))
        if not producto_codigo:
            continue
        records.append(
            {
                "producto_codigo": producto_codigo,
                "referencia": clean_text(row.get("referencia")),
                "descripcion_base": clean_text(row.get("descripcion_base")),
                "descripcion_inventario": clean_text(row.get("descripcion_inventario")),
                "marca": clean_catalog_text(row.get("marca"), drop_zero_only=True),
                "linea_producto": clean_text(row.get("linea_producto")),
                "categoria_producto": clean_text(row.get("categoria_producto")),
                "super_categoria": clean_text(row.get("super_categoria")),
                "departamentos": clean_text(row.get("departamentos")),
                "stock_total": clean_numeric(row.get("stock_total")),
                "stock_por_tienda": clean_text(row.get("stock_por_tienda")),
                "costo_promedio_und": clean_numeric(row.get("costo_promedio_und")),
                "inventario_unidades_metric": clean_numeric(row.get("inventario_unidades_metric")),
                "ventas_unidades_total": clean_numeric(row.get("ventas_unidades_total")),
                "ventas_valor_total": clean_numeric(row.get("ventas_valor_total")),
                "ultima_venta": clean_date(row.get("ultima_venta")),
                "prioridad_origen": clean_text(row.get("prioridad_origen")),
                "tiene_stock": clean_bool(row.get("tiene_stock")),
                "tiene_historial_ventas": clean_bool(row.get("tiene_historial_ventas")),
                "color_detectado": clean_text(row.get("color_detectado")),
                "color_raiz": clean_text(row.get("color_raiz")),
                "acabado_detectado": clean_text(row.get("acabado_detectado")),
                "presentacion_canonica": clean_text(row.get("presentacion_canonica")),
                "core_descriptor": clean_text(row.get("core_descriptor")),
                "producto_padre_busqueda_sugerido": clean_catalog_text(
                    row.get("producto_padre_busqueda_sugerido"),
                    strip_leading_zero_token=True,
                ),
                "familia_consulta_sugerida": clean_catalog_text(
                    row.get("familia_consulta_sugerida"),
                    strip_leading_zero_token=True,
                ),
                "variant_label": clean_text(row.get("variant_label")),
                "workbook_version": WORKBOOK_VERSION,
                "source_file": workbook_path.name,
            }
        )

    products_df = pd.DataFrame.from_records(records).drop_duplicates(subset=["producto_codigo"], keep="first")
    return products_df


def build_alias_dataframe(workbook_path, sheet_name):
    dataframe = pd.read_excel(workbook_path, sheet_name=sheet_name)
    alias_records = []

    alias_groups = [
        ("producto", ["alias_producto_1", "alias_producto_2", "alias_producto_3", "alias_producto_4", "alias_producto_5"]),
        ("presentacion", ["alias_presentacion_1", "alias_presentacion_2", "alias_presentacion_3", "alias_presentacion_4", "alias_presentacion_5"]),
        ("color", ["alias_color_1", "alias_color_2", "alias_color_3"]),
    ]

    for row in dataframe.to_dict(orient="records"):
        producto_codigo = clean_text(row.get("producto_codigo"))
        if not producto_codigo:
            continue

        common_fields = {
            "producto_codigo": producto_codigo,
            "referencia": clean_text(row.get("referencia")),
            "familia_consulta": clean_catalog_text(
                row.get("familia_consulta"),
                strip_leading_zero_token=True,
            ) or clean_catalog_text(
                row.get("familia_consulta_sugerida"),
                strip_leading_zero_token=True,
            ),
            "producto_padre_busqueda": clean_catalog_text(
                row.get("producto_padre_busqueda"),
                strip_leading_zero_token=True,
            ) or clean_catalog_text(
                row.get("producto_padre_busqueda_sugerido"),
                strip_leading_zero_token=True,
            ),
            "pregunta_desambiguacion": clean_text(row.get("pregunta_desambiguacion")),
            "estrategia_busqueda": clean_text(row.get("estrategia_busqueda")),
            "variantes_familia": clean_text(row.get("variantes_familia")),
            "terminos_excluir": clean_text(row.get("terminos_excluir")),
            "activo_agente": clean_bool(row.get("activo_agente")),
            "observaciones_equipo": clean_text(row.get("observaciones_equipo")),
            "workbook_version": WORKBOOK_VERSION,
        }

        for alias_type, columns in alias_groups:
            for alias_order, column_name in enumerate(columns, start=1):
                alias_value = clean_catalog_text(
                    row.get(column_name),
                    drop_zero_only=True,
                    strip_leading_zero_token=True,
                )
                if not alias_value:
                    continue
                alias_records.append(
                    {
                        **common_fields,
                        "alias_type": alias_type,
                        "alias_value": alias_value,
                        "alias_order": alias_order,
                    }
                )

    alias_df = pd.DataFrame.from_records(alias_records)
    if alias_df.empty:
        return alias_df
    alias_df = alias_df.drop_duplicates(subset=["producto_codigo", "alias_type", "alias_value"], keep="first")
    return alias_df


def build_family_dataframe(workbook_path, sheet_name):
    dataframe = pd.read_excel(workbook_path, sheet_name=sheet_name)
    records = []
    for row in dataframe.to_dict(orient="records"):
        familia = clean_text(row.get("familia_consulta_sugerida"))
        if not familia:
            continue
        records.append(
            {
                "familia_consulta_sugerida": clean_catalog_text(familia, strip_leading_zero_token=True),
                "producto_padre_busqueda": clean_catalog_text(
                    row.get("producto_padre_busqueda"),
                    strip_leading_zero_token=True,
                ),
                "marca": clean_catalog_text(row.get("marca"), drop_zero_only=True),
                "core_descriptor": clean_text(row.get("core_descriptor")),
                "color_raiz": clean_text(row.get("color_raiz")),
                "productos": clean_numeric(row.get("productos")),
                "ventas_unidades_total": clean_numeric(row.get("ventas_unidades_total")),
                "ventas_valor_total": clean_numeric(row.get("ventas_valor_total")),
                "stock_total": clean_numeric(row.get("stock_total")),
                "requiere_desambiguacion": clean_bool(row.get("requiere_desambiguacion")),
                "pregunta_desambiguacion_sugerida": clean_text(row.get("pregunta_desambiguacion_sugerida")),
                "estrategia_busqueda": clean_text(row.get("estrategia_busqueda")),
                "variantes_top": clean_text(row.get("variantes_top")),
                "workbook_version": WORKBOOK_VERSION,
            }
        )

    family_df = pd.DataFrame.from_records(records)
    family_df = family_df.drop_duplicates(
        subset=["familia_consulta_sugerida", "marca", "color_raiz"],
        keep="first",
    )
    return family_df


def build_presentation_dataframe(workbook_path):
    dataframe = pd.read_excel(workbook_path, sheet_name=PRESENTATION_SHEET)
    records = []
    for row in dataframe.to_dict(orient="records"):
        canonical = clean_text(row.get("presentacion_canonica"))
        if not canonical:
            continue
        for alias_order, column_name in enumerate(["alias_1", "alias_2", "alias_3", "alias_4", "alias_5"], start=1):
            alias_value = clean_text(row.get(column_name))
            if not alias_value:
                continue
            records.append(
                {
                    "presentacion_canonica": canonical,
                    "alias_presentacion": alias_value,
                    "tokens_regla": clean_text(row.get("usar_para_desambiguar")),
                    "prioridad": alias_order,
                    "workbook_version": WORKBOOK_VERSION,
                }
            )

    presentation_df = pd.DataFrame.from_records(records)
    presentation_df = presentation_df.drop_duplicates(subset=["presentacion_canonica", "alias_presentacion"], keep="first")
    return presentation_df


def build_rule_dataframe(workbook_path):
    dataframe = pd.read_excel(workbook_path, sheet_name=RULE_SHEET)
    records = []
    for index, row in enumerate(dataframe.to_dict(orient="records"), start=1):
        rule_key = clean_text(row.get("regla_id"))
        if not rule_key:
            continue
        records.append(
            {
                "regla_clave": rule_key,
                "tipo_regla": clean_text(row.get("objetivo")),
                "aplicacion": clean_text(row.get("ejemplo_cliente")),
                "valor_regla": clean_text(row.get("respuesta_esperada")),
                "detalle": clean_text(row.get("descripcion")),
                "prioridad": index,
                "activo": True,
                "workbook_version": WORKBOOK_VERSION,
            }
        )

    rule_df = pd.DataFrame.from_records(records)
    rule_df = rule_df.drop_duplicates(subset=["regla_clave", "tipo_regla", "aplicacion"], keep="first")
    return rule_df


def truncate_catalog_tables(connection):
    connection.execute(
        text(
            """
            TRUNCATE TABLE
                public.agent_catalog_alias,
                public.agent_catalog_family,
                public.agent_catalog_presentation_alias,
                public.agent_catalog_rule,
                public.agent_catalog_product
            RESTART IDENTITY CASCADE
            """
        )
    )


def upload_frame(connection, dataframe, table_name):
    if dataframe.empty:
        return 0
    dataframe = dataframe.where(pd.notnull(dataframe), None)
    dataframe.to_sql(table_name, connection, schema="public", if_exists="append", index=False)
    return len(dataframe)


def apply_catalog_schema(db_uri):
    execute_sql_script(db_uri, "backend/agent_schema.sql")
    ensure_postgrest_access(db_uri)
    execute_sql_script(db_uri, "backend/postgrest_views.sql")


def import_catalog(db_uri, workbook_path):
    alias_sheet_name = resolve_sheet_name(workbook_path, ALIAS_SHEET_CANDIDATES)
    family_sheet_name = resolve_sheet_name(workbook_path, FAMILY_SHEET_CANDIDATES)
    products_df = build_product_dataframe(workbook_path)
    alias_df = build_alias_dataframe(workbook_path, alias_sheet_name)
    family_df = build_family_dataframe(workbook_path, family_sheet_name)
    presentation_df = build_presentation_dataframe(workbook_path)
    rule_df = build_rule_dataframe(workbook_path)

    engine = create_engine(db_uri)
    with engine.begin() as connection:
        truncate_catalog_tables(connection)
        counts = {
            "agent_catalog_product": upload_frame(connection, products_df, "agent_catalog_product"),
            "agent_catalog_alias": upload_frame(connection, alias_df, "agent_catalog_alias"),
            "agent_catalog_family": upload_frame(connection, family_df, "agent_catalog_family"),
            "agent_catalog_presentation_alias": upload_frame(connection, presentation_df, "agent_catalog_presentation_alias"),
            "agent_catalog_rule": upload_frame(connection, rule_df, "agent_catalog_rule"),
        }
    return counts


def print_table_counts(db_uri):
    engine = create_engine(db_uri)
    tables = [
        "agent_catalog_product",
        "agent_catalog_alias",
        "agent_catalog_family",
        "agent_catalog_presentation_alias",
        "agent_catalog_rule",
    ]
    with engine.connect() as connection:
        for table_name in tables:
            row_count = connection.execute(text(f'SELECT COUNT(*) FROM public."{table_name}"')).scalar_one()
            print(f"{table_name}: {row_count} filas")


def main():
    parser = argparse.ArgumentParser(description="Importa el catálogo curado del agente desde el Excel V2 a PostgreSQL.")
    parser.add_argument(
        "--excel",
        type=str,
        default="artifacts/Plantilla_Agente_Catalogo_Ferreinox_v2.xlsx",
        help="Ruta al Excel V2 del catálogo curado",
    )
    parser.add_argument("--secrets", type=str, default=None, help="Ruta al archivo secrets.toml")
    parser.add_argument("--skip-views", action="store_true", help="No reaplica esquema y vistas antes de cargar")
    args = parser.parse_args()

    workbook_path = normalize_workbook_path(args.excel)
    db_uri, resolved_secrets = resolve_db_uri(args.secrets)
    alias_sheet_name = resolve_sheet_name(workbook_path, ALIAS_SHEET_CANDIDATES)
    family_sheet_name = resolve_sheet_name(workbook_path, FAMILY_SHEET_CANDIDATES)

    print(f"Usando Excel: {workbook_path}")
    print(f"Usando hoja alias: {alias_sheet_name}")
    print(f"Usando hoja familias: {family_sheet_name}")
    if resolved_secrets:
        print(f"Usando secrets: {resolved_secrets}")
    else:
        print("Usando DATABASE_URL/POSTGRES_DB_URI del entorno")

    if not args.skip_views:
        print("Aplicando esquema del catálogo del agente...")
        apply_catalog_schema(db_uri)
        print("OK | esquema y vistas actualizados")

    print("Cargando catálogo curado desde Excel...")
    counts = import_catalog(db_uri, workbook_path)
    for table_name, row_count in counts.items():
        print(f"OK | {table_name} | {row_count} filas")

    print("Conteo final:")
    print_table_counts(db_uri)


if __name__ == "__main__":
    main()