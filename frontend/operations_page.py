from urllib.parse import urlparse

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

from frontend.config import get_database_uri, get_dropbox_sources
from frontend.data_catalog import CATALOG_SPECS
from frontend.sync_dropbox_streamlit import refresh_official_base_and_postgrest


def summarize_db_target(db_uri):
    parsed = urlparse(db_uri)
    host = parsed.hostname or "desconocido"
    port = parsed.port or "desconocido"
    database = parsed.path.lstrip("/") or "desconocida"
    return {"host": host, "port": port, "database": database}


@st.cache_data(show_spinner=False, ttl=30)
def load_operational_snapshot(db_uri):
    engine = create_engine(db_uri)
    raw_tables = [spec["target_table"] for spec in CATALOG_SPECS]
    postgrest_views = sorted({view_name for spec in CATALOG_SPECS for view_name in spec["postgrest_views"]})

    with engine.connect() as connection:
        existing_objects = {
            row[0]
            for row in connection.execute(
                text(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    UNION
                    SELECT table_name
                    FROM information_schema.views
                    WHERE table_schema = 'public'
                    """
                )
            ).fetchall()
        }

        sync_log_exists = "sync_run_log" in existing_objects
        raw_rows = []
        for spec in CATALOG_SPECS:
            exists = spec["target_table"] in existing_objects
            row_count = None
            if exists:
                row_count = connection.execute(text(f'SELECT COUNT(*) FROM public."{spec["target_table"]}"')).scalar_one()
            raw_rows.append(
                {
                    "Fuente": spec["source_label"],
                    "Archivo": spec["file_name"],
                    "Tabla raw": spec["target_table"],
                    "Existe": "Si" if exists else "No",
                    "Filas": row_count if row_count is not None else 0,
                }
            )

        latest_runs = []
        if sync_log_exists:
            latest_runs = connection.execute(
                text(
                    """
                    SELECT source_label, file_name, target_table, status, row_count, message, executed_at
                    FROM public.sync_run_log
                    ORDER BY executed_at DESC
                    LIMIT 10
                    """
                )
            ).mappings().all()

    raw_df = pd.DataFrame(raw_rows)
    views_ready = sum(1 for view_name in postgrest_views if view_name in existing_objects)
    raw_ready = int((raw_df["Existe"] == "Si").sum()) if not raw_df.empty else 0
    raw_with_data = int((raw_df["Filas"] > 0).sum()) if not raw_df.empty else 0

    return {
        "raw_df": raw_df,
        "latest_runs_df": pd.DataFrame(latest_runs),
        "raw_ready": raw_ready,
        "raw_with_data": raw_with_data,
        "raw_total": len(CATALOG_SPECS),
        "views_ready": views_ready,
        "views_total": len(postgrest_views),
        "sync_log_exists": sync_log_exists,
    }


def main():
    st.title("Centro Operativo")
    st.caption("Una sola vista para entender si la base oficial está lista, si PostgREST está actualizado y cuándo ejecutar la actualización completa.")

    try:
        db_uri = get_database_uri()
    except RuntimeError as exc:
        st.error(str(exc))
        return

    dropbox_sources = get_dropbox_sources()
    db_target = summarize_db_target(db_uri)

    try:
        snapshot = load_operational_snapshot(db_uri)
    except Exception as exc:
        st.error(f"No fue posible leer el estado operativo de la base: {exc}")
        return

    status_label = "Base oficial lista" if snapshot["raw_with_data"] == snapshot["raw_total"] else "Base oficial incompleta"
    status_detail = (
        "Todas las tablas raw oficiales existen y tienen datos."
        if snapshot["raw_with_data"] == snapshot["raw_total"]
        else "Todavía faltan tablas raw oficiales o siguen vacías en esta base."
    )
    using_local_stack_db = db_target["host"] == "db"

    metric_1, metric_2, metric_3, metric_4 = st.columns(4)
    metric_1.metric("Tablas raw creadas", f"{snapshot['raw_ready']}/{snapshot['raw_total']}")
    metric_2.metric("Tablas raw con datos", f"{snapshot['raw_with_data']}/{snapshot['raw_total']}")
    metric_3.metric("Vistas PostgREST", f"{snapshot['views_ready']}/{snapshot['views_total']}")
    metric_4.metric("Fuentes Dropbox", len(dropbox_sources))

    st.info(
        f"Base conectada: host {db_target['host']}, puerto {db_target['port']}, base {db_target['database']}. Estado actual: {status_label}. {status_detail}"
    )

    if using_local_stack_db:
        st.warning(
            "La app está apuntando a la base local del stack (`db`). Si tu base oficial real vive en otro servidor, todavía no has conectado Coolify a esa base y por eso aquí todo aparece vacío."
        )

    if snapshot["raw_with_data"] < snapshot["raw_total"]:
        st.warning(
            "La app está conectada a una base donde faltan tablas raw oficiales o están vacías. Si esta es la base correcta, usa el botón único de abajo para cargar Dropbox y refrescar PostgREST. Si no es la base correcta, primero corrige DATABASE_URL en Coolify."
        )
    else:
        st.success("La base oficial ya tiene datos cargados. Puedes revisar el detalle abajo o relanzar la actualización oficial cuando Dropbox cambie.")

    st.subheader("Acción única")
    st.caption("Este botón hace todo el flujo operativo: lee los CSV oficiales desde Dropbox, actualiza las tablas raw y reaplica la capa SQL de PostgREST.")

    if st.button("Actualizar base oficial y PostgREST", disabled=not dropbox_sources):
        with st.spinner("Ejecutando actualización oficial completa..."):
            results, preflight_results, views_path = refresh_official_base_and_postgrest(db_uri, dropbox_sources)

        st.write("Validación previa")
        for success, message in preflight_results:
            if success:
                st.success(message)
            else:
                st.error(message)

        if not results:
            st.error("La actualización no se ejecutó porque la validación previa encontró problemas.")
            st.stop()

        st.write("Resultado de la actualización")
        for success, message in results:
            if success:
                st.success(message)
            else:
                st.error(message)

        if views_path:
            st.success(f"PostgREST actualizado correctamente desde {views_path}.")

        load_operational_snapshot.clear()
        st.info("Recarga la página para ver el nuevo estado consolidado.")

    if not dropbox_sources:
        st.error("No hay fuentes Dropbox configuradas. Para operar este botón debes cargar variables DROPBOX_* o usar STREAMLIT_SECRETS_TOML.")

    st.markdown("---")
    st.subheader("Qué mirar")
    st.markdown(
        """
        1. Si `Tablas raw con datos` es menor a 5, la base oficial aún no está lista.
        2. Si `Vistas PostgREST` es menor al total esperado, falta refrescar la capa SQL.
        3. Si el host mostrado arriba es `db`, estás en la base local del stack y no en la base oficial remota.
        4. Si Dropbox no aparece configurado, el botón único no podrá ejecutar la actualización.
        """
    )

    st.subheader("Detalle actual de la base oficial")
    st.dataframe(snapshot["raw_df"], use_container_width=True)

    st.subheader("Últimos eventos de sincronización")
    if snapshot["latest_runs_df"].empty:
        st.info("Aún no hay registros recientes en sync_run_log para esta base.")
    else:
        st.dataframe(snapshot["latest_runs_df"], use_container_width=True)