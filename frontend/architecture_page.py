from pathlib import Path

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, inspect, text

from frontend.config import get_database_uri, get_dropbox_sources
from frontend.data_catalog import CATALOG_SPECS, classify_source_role, get_canonical_spec, get_catalog_rows
from frontend.dropbox_sync_service import build_target_table_name, get_dropbox_client, list_csv_files


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
                "Rol": "Base oficial CSV",
                "Actualiza PostgREST": "Si" if spec["updates_postgrest"] else "No",
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
        st.write("Rol: Base oficial CSV")
        st.write(f"Tabla raw: {selected_spec['target_table']}")
        st.write(f"Columnas esperadas: {len(selected_spec['columns'])}")
        st.code("\n".join(selected_spec["columns"]), language="text")

    with right_col:
        st.markdown("**Salida para PostgREST y modelo**")
        st.write(f"Actualiza PostgREST: {'Si' if selected_spec['updates_postgrest'] else 'No'}")
        st.write(f"Vistas PostgREST: {', '.join(selected_spec['postgrest_views']) or 'Sin vista directa'}")
        st.write(f"Modelo alimentado: {', '.join(selected_spec['business_entities'])}")
        st.write(f"Notas operativas: {selected_spec['notes']}")

    st.subheader("Resumen funcional")
    st.dataframe(pd.DataFrame(get_catalog_rows()), use_container_width=True)

    st.subheader("Inventario vivo de Dropbox")
    dropbox_sources = get_dropbox_sources()
    if dropbox_sources:
        inventory_rows = []
        for source_label, dropbox_conf in dropbox_sources.items():
            try:
                dbx = get_dropbox_client(dropbox_conf)
                for entry in list_csv_files(dbx, dropbox_conf.get("folder", "/")):
                    canonical_spec = get_canonical_spec(source_label, entry.name)
                    inventory_rows.append(
                        {
                            "Fuente Dropbox": source_label,
                            "Archivo": entry.name,
                            "Rol": classify_source_role(entry.name, canonical_spec),
                            "Actualiza PostgREST": "Si" if canonical_spec and canonical_spec["updates_postgrest"] else "No",
                            "Tipo": entry.name.rsplit(".", 1)[-1].lower(),
                            "Path": entry.path_lower,
                            "Mapeado": "Si" if canonical_spec else "No",
                            "Tabla raw destino": canonical_spec["target_table"] if canonical_spec else build_target_table_name(source_label, entry.name),
                            "Vista objetivo": ", ".join(canonical_spec["postgrest_views"]) if canonical_spec else "Solo apoyo / pendiente de mapping",
                        }
                    )
            except Exception as exc:
                inventory_rows.append(
                    {
                        "Fuente Dropbox": source_label,
                        "Archivo": "<error>",
                        "Tipo": "n/a",
                        "Path": dropbox_conf.get("folder", "/"),
                        "Mapeado": "No",
                        "Tabla raw destino": "n/a",
                        "Vista objetivo": f"Error leyendo Dropbox: {exc}",
                    }
                )

        inventory_df = pd.DataFrame(inventory_rows)
        st.dataframe(inventory_df, use_container_width=True)
    else:
        st.info("No hay fuentes Dropbox configuradas para construir el inventario vivo.")

    views_file = Path(__file__).resolve().parent.parent / "backend" / "postgrest_views.sql"
    st.info(f"La capa SQL de PostgREST está definida en: {views_file}")