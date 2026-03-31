import pandas as pd
import streamlit as st

from frontend.config import get_database_uri
from frontend.crm_data import load_conversation_detail, load_crm_hub_snapshot
from frontend.ui import render_highlight, render_message, render_metric_card, render_page_hero, render_section_intro


def format_conversation_label(row):
    return f"#{row['id']} · {row['cliente']} · {row['intent']} · {row['estado']}"


def main():
    render_page_hero(
        "Ferreinox CRM",
        "Centro de Conversaciones",
        "Opera WhatsApp como una bandeja ejecutiva: identifica intención, prioridad, resumen y tareas relacionadas sin perder el hilo comercial del cliente.",
        badge="Seguimiento detallado por conversación",
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

    filter_col_1, filter_col_2, filter_col_3 = st.columns(3)
    estados = ["Todos"] + sorted(conversations_df["estado"].dropna().unique().tolist())
    intents = ["Todos"] + sorted(conversations_df["intent"].dropna().unique().tolist())
    priorities = ["Todos"] + sorted(conversations_df["prioridad"].dropna().unique().tolist())

    with filter_col_1:
        selected_estado = st.selectbox("Estado", estados)
    with filter_col_2:
        selected_intent = st.selectbox("Intención", intents)
    with filter_col_3:
        selected_priority = st.selectbox("Prioridad", priorities)

    filtered_df = conversations_df.copy()
    if selected_estado != "Todos":
        filtered_df = filtered_df[filtered_df["estado"] == selected_estado]
    if selected_intent != "Todos":
        filtered_df = filtered_df[filtered_df["intent"] == selected_intent]
    if selected_priority != "Todos":
        filtered_df = filtered_df[filtered_df["prioridad"] == selected_priority]

    if filtered_df.empty:
        st.warning("No hay conversaciones con esos filtros.")
        return

    render_highlight(
        f"<strong>Vista filtrada:</strong> {len(filtered_df)} conversaciones. "
        f"Elige una para revisar el historial completo, las tareas asociadas y el posible destino operativo."
    )

    selection_map = {format_conversation_label(row): int(row["id"]) for _, row in filtered_df.iterrows()}
    selected_label = st.selectbox("Conversación activa", list(selection_map.keys()))
    conversation_id = selection_map[selected_label]

    detail = load_conversation_detail(db_uri, conversation_id)
    if detail is None:
        st.error("No fue posible cargar el detalle de la conversación seleccionada.")
        return

    conversation = detail["conversation"]
    summary_cols = st.columns(4)
    summary_cards = [
        ("Cliente", conversation["cliente"], conversation["telefono"]),
        ("Estado", conversation["estado"], "Estado operativo actual de la conversación."),
        ("Intención", conversation["intent"], "Clasificación más reciente detectada por la IA."),
        ("Prioridad", conversation["prioridad"], "Señal usada para ordenar la atención interna."),
    ]
    for column, (label, value, caption) in zip(summary_cols, summary_cards):
        with column:
            render_metric_card(label, value, caption)

    render_section_intro(
        "Resumen operativo",
        "Aquí debe quedar claro qué pidió el cliente y qué espera el equipo interno sin tener que releer todo el chat.",
    )
    st.write(conversation.get("resumen") or "Sin resumen disponible todavía.")

    context_df = pd.DataFrame(
        [
            {"Clave": key, "Valor": value}
            for key, value in (conversation.get("contexto") or {}).items()
        ]
    )
    if not context_df.empty:
        st.dataframe(context_df, use_container_width=True)

    tab_historial, tab_tareas, tab_comercial = st.tabs(["Historial", "Tareas asociadas", "Cotizaciones y pedidos"])

    with tab_historial:
        render_section_intro(
            "Conversación completa",
            "La idea es que el supervisor entienda en segundos qué dijo el cliente, qué respondió el agente y si la salida fue suficiente.",
        )
        for row in detail["messages_df"].itertuples(index=False):
            render_message(row.direction, row.created_at, row.intent_detectado, row.contenido)

    with tab_tareas:
        tasks_df = detail["tasks_df"]
        if tasks_df.empty:
            st.info("Esta conversación todavía no ha generado tareas.")
        else:
            st.dataframe(tasks_df, use_container_width=True)

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