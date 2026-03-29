from pathlib import Path

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, inspect, text

from frontend.config import get_database_uri
from frontend.data_catalog import CATALOG_SPECS, get_catalog_rows


def get_database_status(db_uri):
    engine = create_engine(db_uri)
    inspector = inspect(engine)
    tables = set(inspector.get_table_names(schema="public"))
    views = set(inspector.get_view_names(schema="public"))
    registry_rows = []
    if "sync_schema_registry" in tables:
        with engine.connect() as connection:
            registry_rows = connection.execute(
                text(
                    """
                    SELECT source_label, file_name, target_table
                    FROM public.sync_schema_registry
                    WHERE is_active = true
                    """
                )
            ).mappings().all()

    registry_keys = {(row["source_label"], row["file_name"].lower(), row["target_table"]) for row in registry_rows}
    return tables, views, registry_keys


def build_status_dataframe(db_uri=None):
    tables, views, registry_keys = set(), set(), set()
    if db_uri:
        tables, views, registry_keys = get_database_status(db_uri)

    rows = []
    for spec in CATALOG_SPECS:
        rows.append(
            {
                "Fuente Dropbox": spec["source_label"],
                "Archivo": spec["file_name"],
                "Tabla raw": spec["target_table"],
                "Tabla raw creada": "Si" if spec["target_table"] in tables else "No",
                "Esquema registrado": "Si" if (spec["source_label"], spec["file_name"].lower(), spec["target_table"]) in registry_keys else "No",
                "Vistas PostgREST": ", ".join(spec["postgrest_views"]) or "Sin vista directa",
                "Vistas creadas": "Si" if all(view in views for view in spec["postgrest_views"]) else "No",
                "Modelo alimentado": ", ".join(spec["business_entities"]),
            }
        )
    return pd.DataFrame(rows)


def main():
    st.title("Arquitectura ELT y PostgREST")
    st.caption("Visualiza cómo entra cada archivo Dropbox, a qué tabla raw llega, qué vistas PostgREST expone y qué parte del modelo alimenta.")

    try:
        db_uri = get_database_uri(required=False)
    except Exception:
        db_uri = None

    status_df = build_status_dataframe(db_uri)
    metric_1, metric_2, metric_3 = st.columns(3)
    metric_1.metric("Archivos canónicos", len(CATALOG_SPECS))
    metric_2.metric("Tablas raw", status_df["Tabla raw"].nunique())
    metric_3.metric("Vistas PostgREST", sum(1 for spec in CATALOG_SPECS if spec["postgrest_views"]))

    st.subheader("Mapa completo")
    st.dataframe(status_df, use_container_width=True)

    st.subheader("Detalle por archivo")
    catalog_labels = [f'{spec["source_label"]} | {spec["file_name"]}' for spec in CATALOG_SPECS]
    selected_label = st.selectbox("Archivo de Dropbox", catalog_labels)
    selected_spec = CATALOG_SPECS[catalog_labels.index(selected_label)]

    left_col, right_col = st.columns([1, 1])
    with left_col:
        st.markdown("**Entrada a PostgreSQL**")
        st.write(f"Fuente: {selected_spec['source_label']}")
        st.write(f"Archivo: {selected_spec['file_name']}")
        st.write(f"Tabla raw: {selected_spec['target_table']}")
        st.write(f"Columnas esperadas: {len(selected_spec['columns'])}")
        st.code("\n".join(selected_spec["columns"]), language="text")

    with right_col:
        st.markdown("**Salida para PostgREST y modelo**")
        st.write(f"Vistas PostgREST: {', '.join(selected_spec['postgrest_views']) or 'Sin vista directa'}")
        st.write(f"Modelo alimentado: {', '.join(selected_spec['business_entities'])}")
        st.write(f"Notas operativas: {selected_spec['notes']}")

    st.subheader("Resumen funcional")
    st.dataframe(pd.DataFrame(get_catalog_rows()), use_container_width=True)

    views_file = Path(__file__).resolve().parent.parent / "backend" / "postgrest_views.sql"
    st.info(f"La capa SQL de PostgREST está definida en: {views_file}")