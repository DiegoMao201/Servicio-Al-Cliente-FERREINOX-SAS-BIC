from urllib.parse import urlparse

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

from frontend.config import get_database_uri, get_dropbox_sources
from frontend.data_catalog import CATALOG_SPECS
from frontend.sync_dropbox_streamlit import refresh_official_base_and_postgrest
from frontend.ui import render_flow_step, render_highlight, render_metric_card, render_page_hero, render_section_intro


def summarize_db_target(db_uri):
    parsed = urlparse(db_uri)
    host = parsed.hostname or "desconocido"
    port = parsed.port or "desconocido"
    database = parsed.path.lstrip("/") or "desconocida"
    return {"host": host, "port": port, "database": database}


def _load_existing_objects(connection):
    return {
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


@st.cache_data(show_spinner=False, ttl=30)
def load_operational_snapshot(db_uri):
    engine = create_engine(db_uri)
    raw_tables = [spec["target_table"] for spec in CATALOG_SPECS]
    postgrest_views = sorted({view_name for spec in CATALOG_SPECS for view_name in spec["postgrest_views"]})

    with engine.connect() as connection:
        existing_objects = _load_existing_objects(connection)

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


@st.cache_data(show_spinner=False, ttl=30)
def load_chat_order_snapshot(db_uri):
    engine = create_engine(db_uri)
    with engine.connect() as connection:
        existing_objects = _load_existing_objects(connection)

        metrics = {
            "pedidos_chat": 0,
            "pedidos_abiertos": 0,
            "pedidos_exportados": 0,
            "despachos_pendientes": 0,
            "traslados_activos": 0,
            "compras_abiertas": 0,
        }
        orders_df = pd.DataFrame()
        dispatches_df = pd.DataFrame()
        transfers_df = pd.DataFrame()
        procurement_df = pd.DataFrame()

        if "agent_order" in existing_objects:
            order_metrics = connection.execute(
                text(
                    """
                    SELECT
                        COUNT(*) FILTER (WHERE canal = 'whatsapp') AS pedidos_chat,
                        COUNT(*) FILTER (WHERE canal = 'whatsapp' AND estado IN ('borrador', 'pendiente_confirmacion', 'confirmado')) AS pedidos_abiertos,
                        COUNT(*) FILTER (WHERE canal = 'whatsapp' AND estado = 'enviado_erp') AS pedidos_exportados
                    FROM public.agent_order
                    """
                )
            ).mappings().one()
            metrics.update({key: int(order_metrics.get(key) or 0) for key in metrics if key in order_metrics})

            orders_df = pd.read_sql_query(
                text(
                    """
                    SELECT
                        o.id,
                        o.estado,
                        o.numero_externo,
                        o.almacen_nombre,
                        o.resumen,
                        o.observaciones,
                        o.canal,
                        o.origen,
                        COALESCE(o.metadata ->> 'delivery_channel', '') AS canal_entrega,
                        COALESCE((o.metadata -> 'facturador' ->> 'name'), '') AS facturador_asignado,
                        wc.nombre_visible AS contacto,
                        (
                            SELECT COUNT(*)
                            FROM public.agent_order_line line
                            WHERE line.order_id = o.id
                        ) AS lineas,
                        o.created_at,
                        o.updated_at
                    FROM public.agent_order o
                    LEFT JOIN public.whatsapp_contacto wc ON wc.id = o.contacto_id
                    WHERE o.canal = 'whatsapp'
                    ORDER BY o.updated_at DESC
                    LIMIT 80
                    """
                ),
                connection,
            )

        if "agent_order_dispatch" in existing_objects:
            metrics["despachos_pendientes"] = int(
                connection.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM public.agent_order_dispatch
                        WHERE status IN ('pendiente', 'en_transito')
                        """
                    )
                ).scalar_one()
            )
            dispatches_df = pd.read_sql_query(
                text(
                    """
                    SELECT
                        d.id,
                        d.order_id,
                        d.destination_store_name,
                        d.facturador_name,
                        d.facturador_email,
                        d.status,
                        d.export_filename,
                        d.dropbox_path,
                        d.observations,
                        wc.nombre_visible AS contacto,
                        d.created_at,
                        d.notified_email_at,
                        d.notified_whatsapp_at
                    FROM public.agent_order_dispatch d
                    LEFT JOIN public.whatsapp_contacto wc ON wc.id = d.contacto_id
                    WHERE d.status IN ('pendiente', 'en_transito')
                    ORDER BY d.created_at DESC
                    LIMIT 80
                    """
                ),
                connection,
            )

        if "vw_agent_transfer_request_active" in existing_objects:
            metrics["traslados_activos"] = int(connection.execute(text("SELECT COUNT(*) FROM public.vw_agent_transfer_request_active")).scalar_one())
            transfers_df = pd.read_sql_query(
                text(
                    """
                    SELECT
                        tr.id,
                        tr.order_id,
                        tr.source_store_name,
                        tr.destination_store_name,
                        tr.referencia,
                        tr.descripcion,
                        tr.quantity_requested,
                        tr.status,
                        au.full_name AS solicitado_por,
                        tr.notes,
                        tr.created_at,
                        tr.updated_at
                    FROM public.vw_agent_transfer_request_active tr
                    LEFT JOIN public.agent_user au ON au.id = tr.requested_by_user_id
                    ORDER BY tr.created_at DESC
                    LIMIT 80
                    """
                ),
                connection,
            )

        if "agent_task" in existing_objects:
            metrics["compras_abiertas"] = int(
                connection.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM public.agent_task
                        WHERE tipo_tarea = 'abastecimiento_compras'
                          AND estado IN ('pendiente', 'en_progreso')
                        """
                    )
                ).scalar_one()
            )
            procurement_df = pd.read_sql_query(
                text(
                    """
                    SELECT
                        id,
                        prioridad,
                        estado,
                        resumen,
                        detalle,
                        updated_at,
                        created_at
                    FROM public.agent_task
                    WHERE tipo_tarea = 'abastecimiento_compras'
                    ORDER BY created_at DESC
                    LIMIT 80
                    """
                ),
                connection,
            )

    return {
        "metrics": metrics,
        "orders_df": orders_df,
        "dispatches_df": dispatches_df,
        "transfers_df": transfers_df,
        "procurement_df": procurement_df,
    }


def _render_orders_queue(snapshot):
    orders_df = snapshot["orders_df"].copy()
    if orders_df.empty:
        st.info("Todavía no hay pedidos de WhatsApp almacenados en la base para esta vista.")
        return

    status_options = ["Todos"] + sorted(orders_df["estado"].dropna().astype(str).unique().tolist())
    store_options = ["Todas"] + sorted([value for value in orders_df["almacen_nombre"].dropna().astype(str).unique().tolist() if value])
    col_1, col_2 = st.columns(2)
    with col_1:
        selected_status = st.selectbox("Estado del pedido", status_options, index=0)
    with col_2:
        selected_store = st.selectbox("Sede destino", store_options, index=0)

    filtered_df = orders_df
    if selected_status != "Todos":
        filtered_df = filtered_df[filtered_df["estado"] == selected_status]
    if selected_store != "Todas":
        filtered_df = filtered_df[filtered_df["almacen_nombre"] == selected_store]

    render_highlight(
        f"<strong>Pedidos visibles:</strong> {len(filtered_df)}. Esta bandeja muestra pedidos creados desde chat y permite leer qué ya quedó confirmado, exportado o todavía requiere gestión humana."
    )
    st.dataframe(filtered_df, use_container_width=True)


def _render_dispatch_transfer_queue(snapshot):
    dispatches_df = snapshot["dispatches_df"]
    transfers_df = snapshot["transfers_df"]
    procurement_df = snapshot["procurement_df"]

    left_col, right_col, third_col = st.columns(3)
    with left_col:
        st.markdown("### Despachos pendientes")
        if dispatches_df.empty:
            st.info("No hay despachos pendientes o en tránsito en este momento.")
        else:
            st.dataframe(dispatches_df, use_container_width=True)
    with right_col:
        st.markdown("### Traslados activos")
        if transfers_df.empty:
            st.info("No hay solicitudes de traslado activas.")
        else:
            st.dataframe(transfers_df, use_container_width=True)
    with third_col:
        st.markdown("### Compras / Abastecimiento")
        if procurement_df.empty:
            st.info("No hay solicitudes abiertas de abastecimiento a compras.")
        else:
            st.dataframe(procurement_df, use_container_width=True)


def _render_base_status(snapshot, dropbox_sources, db_target):
    status_label = "Base oficial lista" if snapshot["raw_with_data"] == snapshot["raw_total"] else "Base oficial incompleta"
    status_detail = (
        "Todas las tablas raw oficiales existen y tienen datos."
        if snapshot["raw_with_data"] == snapshot["raw_total"]
        else "Todavía faltan tablas raw oficiales o siguen vacías en esta base."
    )
    using_local_stack_db = db_target["host"] == "db"

    metric_1, metric_2, metric_3, metric_4 = st.columns(4)
    with metric_1:
        render_metric_card("Tablas raw creadas", f"{snapshot['raw_ready']}/{snapshot['raw_total']}", "Estructuras oficiales creadas en PostgreSQL.")
    with metric_2:
        render_metric_card("Tablas con datos", f"{snapshot['raw_with_data']}/{snapshot['raw_total']}", "Fuentes listas para generar la capa operativa.")
    with metric_3:
        render_metric_card("Vistas PostgREST", f"{snapshot['views_ready']}/{snapshot['views_total']}", "Objetos SQL ya publicados para consumo del agente.")
    with metric_4:
        render_metric_card("Fuentes Dropbox", len(dropbox_sources), "Orígenes configurados para construir la base oficial.")

    render_highlight(
        f"<strong>Base conectada:</strong> host {db_target['host']}, puerto {db_target['port']}, base {db_target['database']}. "
        f"<strong>Estado:</strong> {status_label}. {status_detail}"
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

    render_section_intro(
        "Orden correcto de actualización",
        "Cuando aquí algo falla, todo el CRM se desordena. La regla es actualizar raw, reaplicar esquema del agente y solo después refrescar PostgREST.",
    )
    flow_cols = st.columns(4)
    flow_steps = [
        (1, "Validar Dropbox", "Confirmar que existen los archivos oficiales y que el ancho de columnas coincide con el catálogo canónico."),
        (2, "Actualizar raw", "Cargar o reemplazar las tablas raw oficiales en PostgreSQL conservando el esquema textual correcto."),
        (3, "Reaplicar agente", "Volver a aplicar agent_schema.sql para asegurar tareas, conversaciones y tablas del CRM."),
        (4, "Refrescar PostgREST", "Ejecutar postgrest_views.sql para publicar la capa SQL que usa el resto del sistema."),
    ]
    for column, step in zip(flow_cols, flow_steps):
        with column:
            render_flow_step(*step)

    render_section_intro(
        "Acción única",
        "Este botón ejecuta el flujo completo de actualización oficial y deja la ruta clara para operación y soporte.",
    )

    if st.button("Actualizar base oficial y PostgREST", disabled=not dropbox_sources):
        with st.spinner("Ejecutando actualización oficial completa..."):
            results, preflight_results, views_path = refresh_official_base_and_postgrest(db_target.get("uri") or get_database_uri(), dropbox_sources)

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
        load_chat_order_snapshot.clear()
        st.info("Recarga la página para ver el nuevo estado consolidado.")

    if not dropbox_sources:
        st.error("No hay fuentes Dropbox configuradas. Para operar este botón debes cargar variables DROPBOX_* o usar STREAMLIT_SECRETS_TOML.")

    st.markdown("---")
    render_section_intro(
        "Qué revisar cuando algo no cuadra",
        "Estas cuatro señales te dicen si el problema está en Dropbox, en la base oficial o en la capa SQL que publica PostgREST.",
    )
    st.markdown(
        """
        1. Si `Tablas raw con datos` es menor a 5, la base oficial aún no está lista.
        2. Si `Vistas PostgREST` es menor al total esperado, falta refrescar la capa SQL.
        3. Si el host mostrado arriba es `db`, estás en la base local del stack y no en la base oficial remota.
        4. Si Dropbox no aparece configurado, el botón único no podrá ejecutar la actualización.
        """
    )

    st.dataframe(snapshot["raw_df"], use_container_width=True)


def main():
    render_page_hero(
        "Ferreinox Data Ops",
        "Bandeja Operativa y Base Oficial",
        "Aquí puedes leer los pedidos que entran por WhatsApp, ver qué ya salió a despacho o traslado y controlar la salud de la base oficial/PostgREST desde la misma consola.",
        badge="Pedidos chat -> PostgreSQL/PostgREST -> despacho -> traslado",
    )

    try:
        db_uri = get_database_uri()
    except RuntimeError as exc:
        st.error(str(exc))
        return

    dropbox_sources = get_dropbox_sources()
    db_target = summarize_db_target(db_uri)
    db_target["uri"] = db_uri

    try:
        base_snapshot = load_operational_snapshot(db_uri)
        chat_snapshot = load_chat_order_snapshot(db_uri)
    except Exception as exc:
        st.error(f"No fue posible leer el estado operativo de la base: {exc}")
        return

    metrics = chat_snapshot["metrics"]
    metric_1, metric_2, metric_3, metric_4, metric_5 = st.columns(5)
    with metric_1:
        render_metric_card("Pedidos WhatsApp", metrics["pedidos_chat"], "Pedidos almacenados desde conversaciones del chat.")
    with metric_2:
        render_metric_card("Pedidos abiertos", metrics["pedidos_abiertos"], "Borradores o confirmados que todavía requieren seguimiento operativo.")
    with metric_3:
        render_metric_card("Despachos pendientes", metrics["despachos_pendientes"], "Pedidos ya exportados que siguen pendientes o en tránsito.")
    with metric_4:
        render_metric_card("Traslados activos", metrics["traslados_activos"], "Solicitudes entre sedes que aún no se cierran.")
    with metric_5:
        render_metric_card("Compras abiertas", metrics["compras_abiertas"], "Faltantes sin origen interno ya escalados a compras.")

    render_highlight(
        "<strong>Lectura operativa:</strong> esta bandeja toma como fuente los pedidos generados por chat en PostgreSQL. Desde aquí sale la siguiente fase: priorizar despachos, revisar faltantes y activar traslados/compras según la lógica operativa."
    )

    tab_orders, tab_dispatch, tab_base, tab_logs = st.tabs(["Pedidos WhatsApp", "Despachos y Traslados", "Base Oficial", "Últimos Eventos"])

    with tab_orders:
        render_section_intro(
            "Pedidos entrantes por chat",
            "Esta vista resume los pedidos que el agente ya persistió en la base. Es el punto de partida para despacho, faltantes, compras y traslados guiados por IA.",
        )
        _render_orders_queue(chat_snapshot)

    with tab_dispatch:
        render_section_intro(
            "Despachos y solicitudes entre sedes",
            "Aquí se consolidan los archivos exportados, los facturadores asignados y los traslados internos en curso.",
        )
        _render_dispatch_transfer_queue(chat_snapshot)

    with tab_base:
        _render_base_status(base_snapshot, dropbox_sources, db_target)

    with tab_logs:
        render_section_intro(
            "Últimos eventos de actualización",
            "Los eventos de sincronización siguen siendo clave para saber si lo que ves en la bandeja operativa realmente está soportado por una base oficial sana.",
        )
        if base_snapshot["latest_runs_df"].empty:
            st.info("Aún no hay registros recientes en sync_run_log para esta base.")
        else:
            st.dataframe(base_snapshot["latest_runs_df"], use_container_width=True)