import streamlit as st

from frontend.config import get_database_uri
from frontend.crm_data import load_crm_hub_snapshot, load_data_readiness
from frontend.ui import render_flow_step, render_highlight, render_metric_card, render_page_hero, render_section_intro


def main():
    render_page_hero(
        "Ferreinox CRM",
        "Centro Ejecutivo de Conversaciones",
        "Controla en una sola vista la conversación del cliente, la respuesta del agente, la creación de tareas y el estado de la base oficial que alimenta PostgREST.",
        badge="Operación comercial + IA + datos",
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
        f"{metrics['tareas_pendientes']} tareas pendientes y {postgrest_status}. Estado de base: <strong>{base_status}</strong>."
    )

    metric_cols = st.columns(6)
    cards = [
        ("Conversaciones activas", metrics["conversaciones_activas"], "Clientes que hoy siguen abiertos o pendientes."),
        ("Tareas pendientes", metrics["tareas_pendientes"], "Casos que ya requieren seguimiento operativo."),
        ("Tareas críticas", metrics["tareas_criticas"], "Cola prioritaria para venta, cartera o reclamos."),
        ("Mensajes registrados", metrics["mensajes"], "Historial que ya puede alimentar el aprendizaje del agente."),
        ("Base oficial", f"{readiness['raw_with_data']}/{readiness['raw_total']}", "Tablas raw oficiales con datos útiles."),
        ("PostgREST", f"{readiness['views_ready']}/{readiness['views_total']}", "Vistas SQL publicadas para consumo operativo."),
    ]
    for column, (label, value, caption) in zip(metric_cols, cards):
        with column:
            render_metric_card(label, value, caption)

    render_section_intro(
        "Flujo objetivo del CRM",
        "La app debe dejar visible el paso exacto en que va cada conversación para que la operación comercial no dependa de revisar WhatsApp a mano.",
    )
    flow_cols = st.columns(5)
    flow_steps = [
        (1, "Entrada", "El cliente escribe por WhatsApp y la conversación queda persistida con su contexto y contacto."),
        (2, "Clasificación", "La IA detecta intención, prioridad y si debe crear tarea o escalar a un área."),
        (3, "Resolución", "El agente responde o solicita validación cuando la conversación toca cartera, compras o documentos."),
        (4, "Ejecución", "La salida correcta es tarea, correo estructurado o cotización/pedido según el caso."),
        (5, "Aprendizaje", "Cada caso resuelto debe quedar resumido para mejorar futuras respuestas del agente."),
    ]
    for column, step in zip(flow_cols, flow_steps):
        with column:
            render_flow_step(*step)

    tab_resumen, tab_tareas, tab_datos = st.tabs(["Cola ejecutiva", "Ruteo operativo", "Base y PostgREST"])

    with tab_resumen:
        render_section_intro(
            "Conversaciones más recientes",
            "Esta tabla ya muestra cliente, intención detectada, prioridad y tamaño de historial para decidir a quién atender primero.",
        )
        st.dataframe(crm_snapshot["conversations_df"].head(20), use_container_width=True)

        if not crm_snapshot["intents_df"].empty:
            chart_df = crm_snapshot["intents_df"].set_index("intent")
            st.bar_chart(chart_df)

    with tab_tareas:
        left_col, right_col = st.columns([1.3, 1])
        with left_col:
            render_section_intro(
                "Tareas pendientes por área",
                "La meta es que cada conversación importante termine en una acción clara para ventas, contabilidad, compras o servicio.",
            )
            st.dataframe(crm_snapshot["tasks_df"].head(25), use_container_width=True)
        with right_col:
            render_section_intro(
                "Carga actual por destino",
                "El sistema ya puede sugerir a qué área debe salir la conversación según el tipo de tarea generado.",
            )
            if crm_snapshot["areas_df"].empty:
                st.info("Aún no hay tareas suficientes para resumir por área.")
            else:
                st.dataframe(crm_snapshot["areas_df"], use_container_width=True)
            st.markdown("### Reglas objetivo")
            st.dataframe(crm_snapshot["routing_rules_df"], use_container_width=True)

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