import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

from frontend.config import get_database_uri


@st.cache_data(show_spinner=False, ttl=30)
def load_agent_snapshot(db_uri):
    engine = create_engine(db_uri)
    with engine.connect() as connection:
        required_tables = ["whatsapp_contacto", "agent_conversation", "agent_message", "agent_task"]
        existing_tables = {
            row[0]
            for row in connection.execute(
                text(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = ANY(:table_names)
                    """
                ),
                {"table_names": required_tables},
            ).fetchall()
        }

        if set(required_tables) - existing_tables:
            return None, None, None, None

        metrics = {
            "contactos": connection.execute(text("SELECT COUNT(*) FROM public.whatsapp_contacto")).scalar_one(),
            "conversaciones_abiertas": connection.execute(
                text("SELECT COUNT(*) FROM public.agent_conversation WHERE estado IN ('abierta', 'pendiente')")
            ).scalar_one(),
            "mensajes": connection.execute(text("SELECT COUNT(*) FROM public.agent_message")).scalar_one(),
            "tareas_pendientes": connection.execute(
                text("SELECT COUNT(*) FROM public.agent_task WHERE estado IN ('pendiente', 'en_progreso')")
            ).scalar_one(),
        }

        conversations = pd.read_sql_query(
            text(
                """
                SELECT
                    ac.id,
                    wc.telefono_e164,
                    wc.nombre_visible,
                    ac.estado,
                    ac.started_at,
                    ac.last_message_at,
                    ac.resumen
                FROM public.agent_conversation ac
                JOIN public.whatsapp_contacto wc ON wc.id = ac.contacto_id
                ORDER BY ac.updated_at DESC
                LIMIT 50
                """
            ),
            connection,
        )

        messages = pd.read_sql_query(
            text(
                """
                SELECT
                    am.id,
                    am.conversation_id,
                    am.direction,
                    am.message_type,
                    am.intent_detectado,
                    am.contenido,
                    am.estado,
                    am.created_at
                FROM public.agent_message am
                ORDER BY am.created_at DESC
                LIMIT 100
                """
            ),
            connection,
        )

        tasks = pd.read_sql_query(
            text(
                """
                SELECT
                    id,
                    conversation_id,
                    tipo_tarea,
                    prioridad,
                    estado,
                    resumen,
                    due_at,
                    updated_at
                FROM public.agent_task
                ORDER BY updated_at DESC
                LIMIT 50
                """
            ),
            connection,
        )

    return metrics, conversations, messages, tasks


def main():
    st.title("Centro del Agente")
    st.caption("Monitorea conversaciones, mensajes y tareas del agente conectados a WhatsApp y a la base operativa.")

    try:
        db_uri = get_database_uri()
    except RuntimeError as exc:
        st.error(str(exc))
        return

    try:
        metrics, conversations, messages, tasks = load_agent_snapshot(db_uri)
    except Exception as exc:
        st.error(f"No fue posible cargar el centro del agente: {exc}")
        return

    if metrics is None:
        st.info("Las tablas del agente aún no existen en esta base. Ejecuta una actualización oficial o aplica backend/agent_schema.sql en el servidor.")
        return

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Contactos", metrics["contactos"])
    col2.metric("Conversaciones abiertas", metrics["conversaciones_abiertas"])
    col3.metric("Mensajes", metrics["mensajes"])
    col4.metric("Tareas pendientes", metrics["tareas_pendientes"])

    tab1, tab2, tab3 = st.tabs(["Conversaciones", "Mensajes", "Tareas"])

    with tab1:
        if conversations.empty:
            st.info("Aún no hay conversaciones registradas.")
        else:
            st.dataframe(conversations, use_container_width=True)

    with tab2:
        if messages.empty:
            st.info("Aún no hay mensajes registrados.")
        else:
            st.dataframe(messages, use_container_width=True)

    with tab3:
        if tasks.empty:
            st.info("Aún no hay tareas registradas.")
        else:
            st.dataframe(tasks, use_container_width=True)