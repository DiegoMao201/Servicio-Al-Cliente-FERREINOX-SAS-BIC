import streamlit as st

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


PAGES = {
    "01 Resumen Ejecutivo": executive_page.main,
    "02 Conversaciones": conversations_page.main,
    "03 Flujo CRM": automation_page.main,
    "04 Base Oficial y PostgREST": operations_page.main,
    "05 Centro del Agente": agent_page.main,
    "06 WhatsApp y Webhook": webhook_page.main,
    "07 Estado de Cargas": update_status_page.main,
    "08 Arquitectura de Datos": architecture_page.main,
    "09 Operación SQL": dashboard_page.main,
    "10 Sincronización Dropbox": sync_page.main,
    "11 Agente IA": ai_agent_page.main,
    "12 Diagnóstico": diagnostics_page.main,
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
    st.sidebar.markdown("### Ruta sugerida")
    st.sidebar.markdown(
        """
        1. Resumen Ejecutivo
        2. Conversaciones
        3. Flujo CRM
        4. Base Oficial y PostgREST
        """
    )
    selected_page = st.sidebar.radio("Vista", list(PAGES.keys()))

    PAGES[selected_page]()


if __name__ == "__main__":
    main()