import streamlit as st

from frontend import app as dashboard_page
from frontend import architecture_page
from frontend import sync_dropbox_streamlit as sync_page
from frontend import test_conexion_streamlit as diagnostics_page
from frontend import update_status_page


PAGES = {
    "Arquitectura ELT": architecture_page.main,
    "Sincronización Dropbox": sync_page.main,
    "Estado de Actualización": update_status_page.main,
    "Dashboard Operativo": dashboard_page.main,
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
    st.sidebar.caption("Control operativo, sincronización y pruebas técnicas")
    selected_page = st.sidebar.radio("Módulo", list(PAGES.keys()))

    PAGES[selected_page]()


if __name__ == "__main__":
    main()