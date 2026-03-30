import streamlit as st

from frontend import app as dashboard_page
from frontend import agent_page
from frontend import architecture_page
from frontend import operations_page
from frontend import sync_dropbox_streamlit as sync_page
from frontend import test_conexion_streamlit as diagnostics_page
from frontend import update_status_page
from frontend import webhook_page


PAGES = {
    "Centro Operativo": operations_page.main,
    "Webhook WhatsApp": webhook_page.main,
    "Centro del Agente": agent_page.main,
    "Estado de Actualización": update_status_page.main,
    "Dashboard Operativo": dashboard_page.main,
    "Sincronización Dropbox": sync_page.main,
    "Arquitectura ELT": architecture_page.main,
    "Diagnóstico de Conexiones": diagnostics_page.main,
}


def main():
    """Entry point principal para Streamlit Cloud y operación local."""
    st.set_page_config(
        page_title="CRM Ferreinox",
        page_icon="CRM",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.sidebar.title("CRM Ferreinox")
    st.sidebar.caption("Primero usa Centro Operativo. Luego usa Webhook WhatsApp. Las demás páginas quedan como vista avanzada.")
    selected_page = st.sidebar.radio("Módulo", list(PAGES.keys()))

    PAGES[selected_page]()


if __name__ == "__main__":
    main()