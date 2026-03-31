import streamlit as st

from frontend import admin_page
from frontend import app as dashboard_page
from frontend import agent_page
from frontend import ai_agent_page
from frontend import automation_page
from frontend import architecture_page
from frontend import conversations_page
from frontend import executive_page
from frontend import operations_page
from frontend import sync_dropbox_streamlit as sync_page
from frontend import test_conexion_streamlit as diagnostics_page
from frontend import ui
from frontend import update_status_page
from frontend import webhook_page


OPERATOR_PAGES = {
    "01 Centro Operativo": executive_page.main,
    "02 Conversaciones": conversations_page.main,
    "03 Base Oficial y PostgREST": operations_page.main,
}

ADMIN_PAGES = {
    "01 Panel Administrador": admin_page.main,
    "02 Centro Operativo": executive_page.main,
    "03 Conversaciones": conversations_page.main,
    "04 Flujo CRM": automation_page.main,
    "05 Base Oficial y PostgREST": operations_page.main,
    "06 Centro del Agente": agent_page.main,
    "07 WhatsApp y Webhook": webhook_page.main,
    "08 Estado de Cargas": update_status_page.main,
    "09 Arquitectura de Datos": architecture_page.main,
    "10 Operación SQL": dashboard_page.main,
    "11 Sincronización Dropbox": sync_page.main,
    "12 Agente IA": ai_agent_page.main,
    "13 Diagnóstico": diagnostics_page.main,
}


def main():
    """Entry point principal para Streamlit Cloud y operación local."""
    st.set_page_config(
        page_title="CRM Ferreinox",
        page_icon="FX",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    ui.inject_brand_theme()

    st.sidebar.title("Ferreinox CRM")
    st.sidebar.caption("Atención conversacional, operación comercial y base oficial en una sola consola.")
    profile = st.sidebar.radio("Perfil", ["Operador", "Administrador"])

    if profile == "Operador":
        pages = OPERATOR_PAGES
        st.sidebar.markdown("### Ruta sugerida")
        st.sidebar.markdown(
            """
            1. Centro Operativo
            2. Conversaciones
            3. Base Oficial y PostgREST
            """
        )
        st.sidebar.caption("El operador solo ve lo necesario para atender, gestionar y cerrar el CRM sin ruido técnico.")
    else:
        pages = ADMIN_PAGES
        st.sidebar.markdown("### Modo administrador")
        st.sidebar.caption("Aquí quedan las vistas avanzadas de automatización, canal, datos y diagnóstico.")

    selected_page = st.sidebar.radio("Vista", list(pages.keys()))

    pages[selected_page]()


if __name__ == "__main__":
    main()