import streamlit as st

from frontend.config import get_database_uri
from frontend.crm_data import load_crm_hub_snapshot, load_data_readiness
from frontend.ui import render_flow_step, render_highlight, render_metric_card, render_page_hero, render_section_intro


def main():
    render_page_hero(
        "Ferreinox CRM",
        "Centro Operativo",
        "El operador debe entrar aquí, ver qué conversaciones siguen activas, cuáles ya están listas para gestionarse y cómo está la base oficial que sostiene todo el CRM.",
        badge="Vista principal del operador",
    )

    try:
        db_uri = get_database_uri()
    except RuntimeError as exc:
        st.error(str(exc))
        return

    try:
        crm_snapshot = load_crm_hub_snapshot(db_uri)
        readiness = load_data_readiness(db_uri)
    except Exception as exc:
        st.error(f"No fue posible construir el resumen ejecutivo: {exc}")
        return

    if not crm_snapshot.get("available"):
        missing_tables = ", ".join(crm_snapshot.get("missing_tables", []))
        st.error(f"Faltan tablas del CRM agente en esta base: {missing_tables}. Primero aplica backend/agent_schema.sql.")
        return

    metrics = crm_snapshot["metrics"]
    base_status = (
        "Base oficial lista"
        if readiness["raw_with_data"] == readiness["raw_total"]
        else "Base oficial incompleta"
    )
    postgrest_status = f"{readiness['views_ready']}/{readiness['views_total']} vistas PostgREST activas"

    render_highlight(
        f"<strong>Situación actual:</strong> {metrics['conversaciones_activas']} conversaciones activas, "
        f"{metrics['conversaciones_por_cerrar']} listas para gestión final, {metrics['tareas_pendientes']} tareas pendientes y {postgrest_status}. Estado de base: <strong>{base_status}</strong>."
    )

    metric_cols = st.columns(7)
    cards = [
        ("Conversaciones activas", metrics["conversaciones_activas"], "Clientes que hoy siguen abiertos o pendientes."),
        ("Listas para gestionar", metrics["conversaciones_por_cerrar"], "Clientes que ya dieron cierre y solo necesitan gestión final."),
        ("Tareas pendientes", metrics["tareas_pendientes"], "Casos que todavía requieren una acción operativa."),
        ("Tareas críticas", metrics["tareas_criticas"], "Cola prioritaria para venta, cartera o reclamos."),
        ("Gestionadas", metrics["conversaciones_gestionadas"], "Conversaciones cerradas con cumplimiento operativo."),
        ("Base oficial", f"{readiness['raw_with_data']}/{readiness['raw_total']}", "Tablas raw oficiales con datos útiles."),
        ("PostgREST", f"{readiness['views_ready']}/{readiness['views_total']}", "Vistas SQL publicadas para consumo operativo."),
    ]
    for column, (label, value, caption) in zip(metric_cols, cards):
        with column:
            render_metric_card(label, value, caption)

    render_section_intro(
        "Ruta operativa que sí debe seguir el usuario",
        "La operación no necesita ver todo el sistema. Necesita una ruta clara para atender, gestionar y cerrar sin perder orden.",
    )
    flow_cols = st.columns(5)
    flow_steps = [
        (1, "Entrar al Centro Operativo", "Ver cuántas conversaciones siguen activas y cuántas ya están listas para gestionarse."),
        (2, "Abrir Conversaciones", "Leer el resumen, validar intención y revisar si el cliente ya quedó atendido."),
        (3, "Confirmar salida", "Verificar si ya salió cotización, correo, ficha técnica, cartera o reclamo a su área."),
        (4, "Gestionar cierre", "Si el cliente ya agradeció y la salida ya ocurrió, marcar la conversación como gestionada."),
        (5, "Escalar solo lo necesario", "Todo lo técnico y administrativo queda para el perfil Administrador, no para el operador."),
    ]
    for column, step in zip(flow_cols, flow_steps):
        with column:
            render_flow_step(*step)

    tab_resumen, tab_cierre, tab_datos = st.tabs(["Bandeja principal", "Listas para gestionar", "Base y PostgREST"])

    with tab_resumen:
        render_section_intro(
            "Conversaciones que siguen en operación",
            "Esta tabla deja primero las conversaciones que todavía requieren lectura, respuesta o seguimiento del equipo.",
        )
        open_queue_df = crm_snapshot["conversations_df"][crm_snapshot["conversations_df"]["estado"] != "cerrada"].copy()
        st.dataframe(
            open_queue_df[["cliente", "estado_operativo", "intent", "prioridad", "pendientes_operativos", "mensajes", "last_message_at"]].head(20),
            use_container_width=True,
        )

        if not crm_snapshot["intents_df"].empty:
            chart_df = crm_snapshot["intents_df"].set_index("intent")
            st.bar_chart(chart_df)

    with tab_cierre:
        render_section_intro(
            "Conversaciones listas para gestión final",
            "Estas son las que el operador debería revisar primero para dejar el CRM limpio cuando el cliente ya cerró la interacción.",
        )
        closure_queue_df = crm_snapshot["conversations_df"][crm_snapshot["conversations_df"]["necesita_cierre"]].copy()
        if closure_queue_df.empty:
            st.info("Ahora mismo no hay conversaciones marcadas como listas para gestionarse.")
        else:
            st.dataframe(
                closure_queue_df[["cliente", "intent", "prioridad", "pendientes_operativos", "resumen", "last_message_at"]].head(20),
                use_container_width=True,
            )

        render_section_intro(
            "Carga actual por destino",
            "La conversación cerrada no debe dejar basura operativa. Aquí ves si todavía hay áreas acumulando tareas pendientes.",
        )
        if crm_snapshot["areas_df"].empty:
            st.info("Aún no hay tareas suficientes para resumir por área.")
        else:
            st.dataframe(crm_snapshot["areas_df"], use_container_width=True)

    with tab_datos:
        render_section_intro(
            "Estado de la base oficial",
            "Aquí queda explícito si la base raw está completa y si la capa SQL de PostgREST ya fue reaplicada después de Dropbox.",
        )
        st.dataframe(readiness["raw_df"], use_container_width=True)
        st.markdown("### Últimos eventos")
        if readiness["latest_runs_df"].empty:
            st.info("Aún no hay registros en sync_run_log para esta base.")
        else:
            st.dataframe(readiness["latest_runs_df"], use_container_width=True)