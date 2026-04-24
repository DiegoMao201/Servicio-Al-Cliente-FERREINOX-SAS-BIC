import argparse
import json
import re
from pathlib import Path
import sys
from typing import Optional

import pandas as pd
from sqlalchemy import create_engine, text

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.import_agent_catalog_excel import apply_catalog_schema, resolve_db_uri


WORKBOOK_VERSION = "variaciones_abril_24"
ARTICLE_FILE_DEFAULT = "ARTICULOS 24 ABRIL.xls"
VARIATION_FILE_DEFAULT = "VARIACIONES 24 ABRIL.xls"

BRAND_TOKENS = {
    "pintuco", "terinsa", "protecto", "international", "montana", "yale", "goya", "abracol",
}
COLOR_TOKENS = {
    "blanco", "negro", "gris", "rojo", "verde", "azul", "amarillo", "marron", "marrón",
    "cafe", "café", "beige", "aluminio", "transparente", "white", "silver", "gold",
}
PRESENTATION_HINTS = {
    "cuñete": ["cuñete", "cunete", "caneca", "cubeta", "18.93", "20 kg", "27 kg", "cane"],
    "galon": ["galon", "galón", "3.79", "5 kg", "1 gl"],
    "cuarto": ["cuarto", "0.95", "0.946", "1/4"],
    "balde": ["balde", "15 kg", "9.46"],
    "caja": ["caja"],
}


def clean_text(value) -> Optional[str]:
    if pd.isna(value):
        return None
    text_value = str(value).strip()
    return text_value or None


def normalize_text(value: Optional[str]) -> str:
    if not value:
        return ""
    lowered = value.lower().replace("\xa0", " ")
    lowered = re.sub(r"[^a-z0-9ñáéíóúü/+.-]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def canonicalize_presentation(*values: Optional[str]) -> Optional[str]:
    joined = " ".join(normalize_text(value) for value in values if value)
    if not joined:
        return None
    for canonical, hints in PRESENTATION_HINTS.items():
        if any(hint in joined for hint in hints):
            return canonical
    return None


def detect_color(text_value: Optional[str]) -> Optional[str]:
    normalized = normalize_text(text_value)
    if not normalized:
        return None
    for token in COLOR_TOKENS:
        if f" {token} " in f" {normalized} ":
            return token
    return None


def build_family_candidates(title: Optional[str], brand: Optional[str], presentation: Optional[str], color: Optional[str]) -> list[str]:
    normalized = normalize_text(title)
    if not normalized:
        return []

    candidates: list[str] = []

    def add(candidate: Optional[str]):
        normalized_candidate = normalize_text(candidate)
        if len(normalized_candidate) < 4:
            return
        if normalized_candidate not in candidates:
            candidates.append(normalized_candidate)

    add(normalized)

    stripped = normalized
    for token in BRAND_TOKENS | ({normalize_text(brand)} if brand else set()):
        if token:
            stripped = re.sub(rf"\b{re.escape(token)}\b", " ", stripped)
    add(stripped)

    without_presentation = stripped
    if presentation:
        for hint in PRESENTATION_HINTS.get(presentation, []):
            without_presentation = re.sub(rf"\b{re.escape(normalize_text(hint))}\b", " ", without_presentation)
    add(without_presentation)

    without_color = without_presentation
    if color:
        without_color = re.sub(rf"\b{re.escape(normalize_text(color))}\b", " ", without_color)
    add(without_color)

    without_numbers = re.sub(r"\b\d{4,6}\b", " ", without_color)
    add(without_numbers)

    return candidates


def build_article_maps(article_path: Path):
    article_df = pd.read_excel(article_path, sheet_name="Worksheet")
    article_map = {}
    for row in article_df.to_dict(orient="records"):
        reference = clean_text(row.get("referencia"))
        if not reference:
            continue
        article_map[reference] = {
            "referencia": reference,
            "titulo": clean_text(row.get("titulo")),
            "marca": clean_text(row.get("marca")),
            "descripcion": clean_text(row.get("descripcion")),
            "precio": row.get("precio"),
            "precio_oferta": row.get("precio_oferta"),
            "precio_distribuidor": row.get("precio_distribuidor"),
            "precio_distribuidor_oferta": row.get("precio_distribuidor_oferta"),
            "impuesto_iva": row.get("impuesto_iva"),
            "unidades_disponibles": row.get("unidades_disponibles"),
            "codigo_categoria": clean_text(row.get("codigo_categoria")),
            "publicado": row.get("publicado"),
            "variaciones_tipo": row.get("variaciones_tipo"),
        }
    return article_map


def build_records(article_map: dict[str, dict], variation_path: Path):
    variation_df = pd.read_excel(variation_path)
    product_records: dict[str, dict] = {}
    alias_records: list[dict] = []

    def add_alias(product_code: str, alias_type: str, alias_value: Optional[str], alias_order: int, family_value: Optional[str], parent_value: Optional[str], presentation_value: Optional[str], color_value: Optional[str], metadata: dict):
        normalized_alias = normalize_text(alias_value)
        if len(normalized_alias) < 2:
            return
        alias_records.append(
            {
                "producto_codigo": product_code,
                "referencia": product_code,
                "alias_type": alias_type,
                "alias_value": normalized_alias,
                "alias_order": alias_order,
                "familia_consulta": family_value,
                "producto_padre_busqueda": parent_value,
                "pregunta_desambiguacion": None,
                "estrategia_busqueda": "variaciones_xls",
                "variantes_familia": presentation_value,
                "terminos_excluir": None,
                "activo_agente": True,
                "observaciones_equipo": "Generado desde ARTICULOS 24 ABRIL + VARIACIONES 24 ABRIL",
                "workbook_version": WORKBOOK_VERSION,
                "metadata": json.dumps(metadata, ensure_ascii=False),
            }
        )

    for row in variation_df.to_dict(orient="records"):
        parent_reference = clean_text(row.get("Referencia:_articulo"))
        variant_reference = clean_text(row.get("Referencia:"))
        if not variant_reference:
            continue

        article_row = article_map.get(parent_reference) or article_map.get(variant_reference) or {}
        title = clean_text(row.get("nombre_articulo")) or article_row.get("titulo") or variant_reference
        brand = clean_text(article_row.get("marca"))
        presentation_hint = canonicalize_presentation(clean_text(row.get("v1")), clean_text(row.get("v2")), clean_text(row.get("v3")))
        color_hint = detect_color(title)
        family_candidates = build_family_candidates(title, brand, presentation_hint, color_hint)
        family_value = family_candidates[-1] if family_candidates else normalize_text(title)
        parent_value = family_candidates[-2] if len(family_candidates) >= 2 else family_value
        variant_label = " | ".join(value for value in [clean_text(row.get("v1")), clean_text(row.get("v2")), clean_text(row.get("v3"))] if value)
        stock_total = row.get("disponibles")
        metadata = {
            "source": "variaciones_24_abril",
            "parent_reference": parent_reference,
            "variant_reference": variant_reference,
            "raw_title": title,
            "presentation_fields": [clean_text(row.get("v1")), clean_text(row.get("v2")), clean_text(row.get("v3"))],
        }

        product_records[variant_reference] = {
            "producto_codigo": variant_reference,
            "referencia": variant_reference,
            "descripcion_base": title,
            "descripcion_inventario": title,
            "marca": brand,
            "linea_producto": None,
            "categoria_producto": article_row.get("codigo_categoria"),
            "super_categoria": None,
            "departamentos": None,
            "stock_total": stock_total,
            "stock_por_tienda": None,
            "costo_promedio_und": None,
            "inventario_unidades_metric": stock_total,
            "ventas_unidades_total": None,
            "ventas_valor_total": None,
            "ultima_venta": None,
            "prioridad_origen": "abril_24_xls",
            "tiene_stock": bool((stock_total or 0) > 0),
            "tiene_historial_ventas": False,
            "color_detectado": color_hint,
            "color_raiz": color_hint,
            "acabado_detectado": None,
            "presentacion_canonica": presentation_hint,
            "core_descriptor": family_value,
            "producto_padre_busqueda_sugerido": parent_value,
            "familia_consulta_sugerida": family_value,
            "variant_label": variant_label or None,
            "workbook_version": WORKBOOK_VERSION,
            "source_file": variation_path.name,
            "metadata": json.dumps({**metadata, "article": article_row}, ensure_ascii=False),
        }

        for alias_order, alias_value in enumerate(family_candidates, start=1):
            add_alias(variant_reference, "producto", alias_value, alias_order, family_value, parent_value, presentation_hint, color_hint, metadata)

        if title:
            add_alias(variant_reference, "producto", title, 20, family_value, parent_value, presentation_hint, color_hint, metadata)
        if presentation_hint:
            for alias_order, alias_value in enumerate(sorted(set(PRESENTATION_HINTS.get(presentation_hint, [])) | {presentation_hint}), start=1):
                add_alias(variant_reference, "presentacion", alias_value, alias_order, family_value, parent_value, presentation_hint, color_hint, metadata)
        if color_hint:
            add_alias(variant_reference, "color", color_hint, 1, family_value, parent_value, presentation_hint, color_hint, metadata)

    for article_reference, article_row in article_map.items():
        if article_reference in product_records:
            continue
        title = article_row.get("titulo") or article_reference
        brand = article_row.get("marca")
        color_hint = detect_color(title)
        family_candidates = build_family_candidates(title, brand, None, color_hint)
        family_value = family_candidates[-1] if family_candidates else normalize_text(title)
        parent_value = family_candidates[-2] if len(family_candidates) >= 2 else family_value
        stock_total = article_row.get("unidades_disponibles")
        metadata = {"source": "articulos_24_abril", "article": article_row}

        product_records[article_reference] = {
            "producto_codigo": article_reference,
            "referencia": article_reference,
            "descripcion_base": title,
            "descripcion_inventario": title,
            "marca": brand,
            "linea_producto": None,
            "categoria_producto": article_row.get("codigo_categoria"),
            "super_categoria": None,
            "departamentos": None,
            "stock_total": stock_total,
            "stock_por_tienda": None,
            "costo_promedio_und": None,
            "inventario_unidades_metric": stock_total,
            "ventas_unidades_total": None,
            "ventas_valor_total": None,
            "ultima_venta": None,
            "prioridad_origen": "abril_24_xls",
            "tiene_stock": bool((stock_total or 0) > 0),
            "tiene_historial_ventas": False,
            "color_detectado": color_hint,
            "color_raiz": color_hint,
            "acabado_detectado": None,
            "presentacion_canonica": None,
            "core_descriptor": family_value,
            "producto_padre_busqueda_sugerido": parent_value,
            "familia_consulta_sugerida": family_value,
            "variant_label": None,
            "workbook_version": WORKBOOK_VERSION,
            "source_file": article_path.name if (article_path := Path(ARTICLE_FILE_DEFAULT)) else ARTICLE_FILE_DEFAULT,
            "metadata": json.dumps(metadata, ensure_ascii=False),
        }
        for alias_order, alias_value in enumerate(family_candidates, start=1):
            add_alias(article_reference, "producto", alias_value, alias_order, family_value, parent_value, None, color_hint, metadata)
        if title:
            add_alias(article_reference, "producto", title, 20, family_value, parent_value, None, color_hint, metadata)
        if color_hint:
            add_alias(article_reference, "color", color_hint, 1, family_value, parent_value, None, color_hint, metadata)

    product_df = pd.DataFrame.from_records(list(product_records.values()))
    alias_df = pd.DataFrame.from_records(alias_records)
    if not alias_df.empty:
        alias_df = alias_df.drop_duplicates(subset=["producto_codigo", "alias_type", "alias_value"], keep="first")
    return product_df, alias_df


PRODUCT_UPSERT_SQL = text(
    """
    INSERT INTO public.agent_catalog_product (
        producto_codigo, referencia, descripcion_base, descripcion_inventario, marca,
        linea_producto, categoria_producto, super_categoria, departamentos, stock_total,
        stock_por_tienda, costo_promedio_und, inventario_unidades_metric, ventas_unidades_total,
        ventas_valor_total, ultima_venta, prioridad_origen, tiene_stock, tiene_historial_ventas,
        color_detectado, color_raiz, acabado_detectado, presentacion_canonica, core_descriptor,
        producto_padre_busqueda_sugerido, familia_consulta_sugerida, variant_label, workbook_version,
        source_file, metadata
    ) VALUES (
        :producto_codigo, :referencia, :descripcion_base, :descripcion_inventario, :marca,
        :linea_producto, :categoria_producto, :super_categoria, :departamentos, :stock_total,
        :stock_por_tienda, :costo_promedio_und, :inventario_unidades_metric, :ventas_unidades_total,
        :ventas_valor_total, :ultima_venta, :prioridad_origen, :tiene_stock, :tiene_historial_ventas,
        :color_detectado, :color_raiz, :acabado_detectado, :presentacion_canonica, :core_descriptor,
        :producto_padre_busqueda_sugerido, :familia_consulta_sugerida, :variant_label, :workbook_version,
        :source_file, CAST(:metadata AS jsonb)
    )
    ON CONFLICT (producto_codigo) DO UPDATE SET
        referencia = COALESCE(EXCLUDED.referencia, public.agent_catalog_product.referencia),
        descripcion_base = COALESCE(EXCLUDED.descripcion_base, public.agent_catalog_product.descripcion_base),
        descripcion_inventario = COALESCE(EXCLUDED.descripcion_inventario, public.agent_catalog_product.descripcion_inventario),
        marca = COALESCE(EXCLUDED.marca, public.agent_catalog_product.marca),
        categoria_producto = COALESCE(EXCLUDED.categoria_producto, public.agent_catalog_product.categoria_producto),
        stock_total = COALESCE(EXCLUDED.stock_total, public.agent_catalog_product.stock_total),
        inventario_unidades_metric = COALESCE(EXCLUDED.inventario_unidades_metric, public.agent_catalog_product.inventario_unidades_metric),
        prioridad_origen = COALESCE(EXCLUDED.prioridad_origen, public.agent_catalog_product.prioridad_origen),
        tiene_stock = EXCLUDED.tiene_stock OR public.agent_catalog_product.tiene_stock,
        color_detectado = COALESCE(EXCLUDED.color_detectado, public.agent_catalog_product.color_detectado),
        color_raiz = COALESCE(EXCLUDED.color_raiz, public.agent_catalog_product.color_raiz),
        presentacion_canonica = COALESCE(EXCLUDED.presentacion_canonica, public.agent_catalog_product.presentacion_canonica),
        core_descriptor = COALESCE(EXCLUDED.core_descriptor, public.agent_catalog_product.core_descriptor),
        producto_padre_busqueda_sugerido = COALESCE(EXCLUDED.producto_padre_busqueda_sugerido, public.agent_catalog_product.producto_padre_busqueda_sugerido),
        familia_consulta_sugerida = COALESCE(EXCLUDED.familia_consulta_sugerida, public.agent_catalog_product.familia_consulta_sugerida),
        variant_label = COALESCE(EXCLUDED.variant_label, public.agent_catalog_product.variant_label),
        workbook_version = EXCLUDED.workbook_version,
        source_file = EXCLUDED.source_file,
        metadata = COALESCE(public.agent_catalog_product.metadata, '{}'::jsonb) || EXCLUDED.metadata,
        updated_at = now()
    """
)


ALIAS_UPSERT_SQL = text(
    """
    INSERT INTO public.agent_catalog_alias (
        producto_codigo, referencia, alias_type, alias_value, alias_order, familia_consulta,
        producto_padre_busqueda, pregunta_desambiguacion, estrategia_busqueda, variantes_familia,
        terminos_excluir, activo_agente, observaciones_equipo, workbook_version, metadata
    ) VALUES (
        :producto_codigo, :referencia, :alias_type, :alias_value, :alias_order, :familia_consulta,
        :producto_padre_busqueda, :pregunta_desambiguacion, :estrategia_busqueda, :variantes_familia,
        :terminos_excluir, :activo_agente, :observaciones_equipo, :workbook_version, CAST(:metadata AS jsonb)
    )
    ON CONFLICT (producto_codigo, alias_type, alias_value) DO UPDATE SET
        alias_order = LEAST(public.agent_catalog_alias.alias_order, EXCLUDED.alias_order),
        familia_consulta = COALESCE(EXCLUDED.familia_consulta, public.agent_catalog_alias.familia_consulta),
        producto_padre_busqueda = COALESCE(EXCLUDED.producto_padre_busqueda, public.agent_catalog_alias.producto_padre_busqueda),
        estrategia_busqueda = COALESCE(EXCLUDED.estrategia_busqueda, public.agent_catalog_alias.estrategia_busqueda),
        variantes_familia = COALESCE(EXCLUDED.variantes_familia, public.agent_catalog_alias.variantes_familia),
        activo_agente = true,
        workbook_version = EXCLUDED.workbook_version,
        metadata = COALESCE(public.agent_catalog_alias.metadata, '{}'::jsonb) || EXCLUDED.metadata,
        updated_at = now()
    """
)


def import_support_catalog(db_uri: str, article_path: Path, variation_path: Path):
    apply_catalog_schema(db_uri)
    article_map = build_article_maps(article_path)
    product_df, alias_df = build_records(article_map, variation_path)
    engine = create_engine(db_uri)
    with engine.begin() as connection:
        if not product_df.empty:
            connection.execute(PRODUCT_UPSERT_SQL, product_df.to_dict(orient="records"))
        if not alias_df.empty:
            connection.execute(ALIAS_UPSERT_SQL, alias_df.to_dict(orient="records"))
        counts = connection.execute(
            text(
                """
                SELECT
                    (SELECT COUNT(*) FROM public.agent_catalog_product WHERE workbook_version = :version) AS products_loaded,
                    (SELECT COUNT(*) FROM public.agent_catalog_alias WHERE workbook_version = :version) AS aliases_loaded
                """
            ),
            {"version": WORKBOOK_VERSION},
        ).mappings().one()
    return dict(counts)


def main():
    parser = argparse.ArgumentParser(description="Importa soporte de artículos/variaciones Abril 24 al catálogo curado del agente.")
    parser.add_argument("--articles", default=ARTICLE_FILE_DEFAULT, help="Ruta al archivo ARTICULOS 24 ABRIL.xls")
    parser.add_argument("--variations", default=VARIATION_FILE_DEFAULT, help="Ruta al archivo VARIACIONES 24 ABRIL.xls")
    parser.add_argument("--secrets", default=None, help="Ruta opcional a secrets.toml")
    args = parser.parse_args()

    db_uri, _ = resolve_db_uri(args.secrets)
    article_path = Path(args.articles).resolve()
    variation_path = Path(args.variations).resolve()
    counts = import_support_catalog(db_uri, article_path, variation_path)
    print(json.dumps(counts, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()