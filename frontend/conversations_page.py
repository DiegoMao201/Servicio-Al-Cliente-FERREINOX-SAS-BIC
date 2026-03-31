import pandas as pd
import streamlit as st

from frontend.config import get_database_uri
from frontend.crm_data import (
    load_conversation_detail,
    load_crm_hub_snapshot,
    mark_conversation_as_managed,
    reopen_conversation_for_followup,
)
from frontend.ui import render_highlight, render_message, render_metric_card, render_page_hero, render_section_intro, render_status_pill


def format_conversation_label(row):
    return f"#{row['id']} · {row['cliente']} · {row['intent']} · {row['estado_operativo']}"


def main():
    render_page_hero(
        "Ferreinox CRM",
        "Centro de Conversaciones",
        "Esta vista debe decirle al operador exactamente qué revisar, qué resolver y cuándo dejar una conversación como gestionada sin perder trazabilidad.",
        badge="Operación diaria del CRM",
    )

    try:
        db_uri = get_database_uri()
    except RuntimeError as exc:
        st.error(str(exc))
        return

    try:
        snapshot = load_crm_hub_snapshot(db_uri)
    except Exception as exc:
        st.error(f"No fue posible cargar las conversaciones: {exc}")
        return

    if not snapshot.get("available"):
        st.error("Las tablas del agente aún no existen en esta base.")
        return

    conversations_df = snapshot["conversations_df"].copy()
    if conversations_df.empty:
        st.info("Aún no hay conversaciones registradas.")
        return

    queue_col, priority_col, intent_col = st.columns([1.1, 1, 1])
    queue_options = [
        "Pendientes de operar",
        "Listas para gestionar",
        "Gestionadas",
        "Todas",
    ]
    priorities = ["Todas"] + sorted(conversations_df["prioridad"].dropna().unique().tolist())
    intents = ["Todas"] + sorted(conversations_df["intent"].dropna().unique().tolist())

    with queue_col:
        selected_queue = st.selectbox("Bandeja", queue_options)
    with priority_col:
        selected_priority = st.selectbox("Prioridad", priorities)
    with intent_col:
        selected_intent = st.selectbox("Intención", intents)

    filtered_df = conversations_df.copy()
    if selected_queue == "Pendientes de operar":
        filtered_df = filtered_df[filtered_df["estado"] != "cerrada"]
        filtered_df = filtered_df[filtered_df["necesita_cierre"] == False]
    elif selected_queue == "Listas para gestionar":
        filtered_df = filtered_df[filtered_df["necesita_cierre"]]
    elif selected_queue == "Gestionadas":
        filtered_df = filtered_df[filtered_df["estado"] == "cerrada"]

    if selected_intent != "Todas":
        filtered_df = filtered_df[filtered_df["intent"] == selected_intent]
    if selected_priority != "Todas":
        filtered_df = filtered_df[filtered_df["prioridad"] == selected_priority]

    if filtered_df.empty:
        st.warning("No hay conversaciones con esos filtros.")
        return

    pending_count = int((filtered_df["estado"] != "cerrada").sum())
    managed_count = int((filtered_df["estado"] == "cerrada").sum())
    ready_to_close_count = int(filtered_df["necesita_cierre"].sum())
    metric_cols = st.columns(3)
    metric_cards = [
        ("En operación", pending_count, "Conversaciones que todavía requieren lectura o seguimiento."),
        ("Listas para gestionar", ready_to_close_count, "Clientes que ya dieron cierre y solo necesitan gestión final."),
        ("Gestionadas", managed_count, "Conversaciones ya cerradas o gestionadas dentro del CRM."),
    ]
    for column, (label, value, caption) in zip(metric_cols, metric_cards):
        with column:
            render_metric_card(label, value, caption)

    render_highlight(
        f"<strong>Bandeja activa:</strong> {len(filtered_df)} conversaciones. "
        f"La ruta correcta es leer el resumen, validar si la salida ya se ejecutó y luego dejar la conversación en seguimiento o gestionada."
    )

    selection_map = {format_conversation_label(row): int(row["id"]) for _, row in filtered_df.iterrows()}
    selected_label = st.selectbox("Conversación activa", list(selection_map.keys()))
    conversation_id = selection_map[selected_label]

    detail = load_conversation_detail(db_uri, conversation_id)
    if detail is None:
        st.error("No fue posible cargar el detalle de la conversación seleccionada.")
        return

    conversation = detail["conversation"]
    closure_recommendation = detail["closure_recommendation"]
    summary_cols = st.columns(4)
    summary_cards = [
        ("Cliente", conversation["cliente"], conversation["telefono"]),
        ("Estado", conversation["estado_operativo"], "Estado operativo que debe ver el equipo en el CRM."),
        ("Intención", conversation["intent"], "Clasificación más reciente detectada por la IA."),
        ("Prioridad", conversation["prioridad"], "Señal usada para ordenar la atención interna."),
    ]
    for column, (label, value, caption) in zip(summary_cols, summary_cards):
        with column:
            render_metric_card(label, value, caption)

    st.markdown(
        " ".join(
            [
                render_status_pill(f"Pendientes: {conversation.get('pending_tasks', 0)}", "warn" if conversation.get("pending_tasks", 0) else "good"),
                render_status_pill(f"Gestionadas: {conversation.get('resolved_tasks', 0)}", "good"),
                render_status_pill(conversation["estado_operativo"], "good" if conversation.get("estado") == "cerrada" else "warn"),
            ]
        ),
        unsafe_allow_html=True,
    )

    render_section_intro(
        "Resumen operativo",
        "Aquí debe quedar claro qué pidió el cliente, qué respondió la IA y si todavía falta una gestión humana o ya se puede dejar el caso como gestionado.",
    )
    st.write(conversation.get("resumen") or "Sin resumen disponible todavía.")

    render_section_intro(
        "Acción del operador",
        "Si el cliente ya cerró la interacción y las salidas internas ya se ejecutaron, aquí es donde se deja la conversación como gestionada.",
    )
    if closure_recommendation["already_managed"]:
        st.success(closure_recommendation["reason"])
    elif closure_recommendation["should_close"]:
        st.success(closure_recommendation["reason"])
    else:
        st.info(closure_recommendation["reason"])

    resolution_note = st.text_area(
        "Nota de gestión",
        value="",
        placeholder="Ejemplo: Cotización enviada, correo despachado y caso cerrado por agradecimiento del cliente.",
        height=90,
    )

    action_col_1, action_col_2 = st.columns(2)
    with action_col_1:
        close_disabled = bool(closure_recommendation["already_managed"])
        if st.button("Marcar como gestionada y cerrar", use_container_width=True, disabled=close_disabled):
            result = mark_conversation_as_managed(
                db_uri,
                conversation_id,
                resolution_note=resolution_note or None,
                resolve_tasks=True,
            )
            st.success(f"Conversación cerrada. {result['resolved_tasks']} tareas quedaron gestionadas.")
            st.rerun()
    with action_col_2:
        reopen_disabled = conversation.get("estado") != "cerrada"
        if st.button("Reabrir para seguimiento", use_container_width=True, disabled=reopen_disabled):
            reopen_conversation_for_followup(db_uri, conversation_id, note=resolution_note or None)
            st.success("La conversación volvió a seguimiento.")
            st.rerun()

    context_df = pd.DataFrame(
        [
            {"Clave": key, "Valor": value}
            for key, value in (conversation.get("contexto") or {}).items()
        ]
    )

    tab_historial, tab_tareas, tab_comercial, tab_contexto = st.tabs(["Historial", "Tareas", "Cotizaciones y pedidos", "Contexto técnico"])

    with tab_historial:
        render_section_intro(
            "Conversación completa",
            "La idea es que el operador entienda en segundos qué dijo el cliente, qué respondió el agente y si la salida ya está ejecutada.",
        )
        for row in detail["messages_df"].itertuples(index=False):
            render_message(row.direction, row.created_at, row.intent_detectado, row.contenido)

    with tab_tareas:
        tasks_df = detail["tasks_df"]
        if tasks_df.empty:
            st.info("Esta conversación todavía no ha generado tareas.")
        else:
            operator_tasks_df = tasks_df.copy()
            operator_tasks_df["estado"] = operator_tasks_df["estado_operativo"]
            st.dataframe(
                operator_tasks_df[["tipo_tarea", "prioridad", "estado", "area_destino", "resumen", "updated_at"]],
                use_container_width=True,
            )

    with tab_comercial:
        left_col, right_col = st.columns(2)
        with left_col:
            st.markdown("### Cotizaciones")
            if detail["quotes_df"].empty:
                st.info("No hay cotizaciones asociadas a esta conversación.")
            else:
                st.dataframe(detail["quotes_df"], use_container_width=True)
        with right_col:
            st.markdown("### Pedidos")
            if detail["orders_df"].empty:
                st.info("No hay pedidos asociados a esta conversación.")
            else:
                st.dataframe(detail["orders_df"], use_container_width=True)

    with tab_contexto:
        if context_df.empty:
            st.info("Esta conversación no tiene contexto técnico adicional.")
        else:
            st.dataframe(context_df, use_container_width=True)