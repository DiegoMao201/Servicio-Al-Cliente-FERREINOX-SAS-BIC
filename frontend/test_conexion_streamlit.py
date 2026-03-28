from datetime import datetime
from pathlib import Path

import dropbox
import streamlit as st
from sqlalchemy import create_engine, text

from frontend.config import get_database_uri, get_dropbox_sources


LOG_PATH = Path(__file__).resolve().parent.parent / "sync_log.txt"


def log_event(event):
    """Guarda eventos operativos simples para diagnóstico manual."""
    with LOG_PATH.open("a", encoding="utf-8") as file_handle:
        file_handle.write(f"[{datetime.now()}] {event}\n")


def test_postgres(db_uri):
    """Valida conexión básica contra PostgreSQL."""
    try:
        engine = create_engine(db_uri)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        st.success("Conexión a PostgreSQL exitosa.")
        log_event("Conexión a PostgreSQL exitosa.")
    except Exception as exc:
        st.error(f"Error conectando a PostgreSQL: {exc}")
        log_event(f"Error conectando a PostgreSQL: {exc}")


def test_dropbox_connection(dropbox_conf):
    """Valida autenticación y acceso a la carpeta configurada de Dropbox."""
    try:
        dbx = dropbox.Dropbox(
            oauth2_refresh_token=dropbox_conf["refresh_token"],
            app_key=dropbox_conf["app_key"],
            app_secret=dropbox_conf["app_secret"],
        )
        files = dbx.files_list_folder(dropbox_conf["folder"]).entries
        st.success(f"Conexión a Dropbox exitosa. Elementos encontrados: {len(files)}")
        log_event(f"Conexión a Dropbox exitosa en {dropbox_conf['folder']}. Elementos: {len(files)}")
    except Exception as exc:
        st.error(f"Error conectando a Dropbox: {exc}")
        log_event(f"Error conectando a Dropbox: {exc}")


def main():
    """Renderiza el módulo de diagnóstico técnico."""
    st.title("Diagnóstico de Conexiones")
    st.caption("Pruebas rápidas para validar PostgreSQL, Dropbox y revisar el log operativo.")

    try:
        db_uri = get_database_uri()
    except RuntimeError as exc:
        st.warning(str(exc))
        db_uri = None

    dropbox_sources = get_dropbox_sources()

    if st.button("Probar conexión a PostgreSQL", disabled=db_uri is None):
        test_postgres(db_uri)

    if dropbox_sources:
        source_name = st.selectbox("Fuente Dropbox", list(dropbox_sources.keys()))
        if st.button("Probar conexión a Dropbox"):
            test_dropbox_connection(dropbox_sources[source_name])
    else:
        st.warning("No hay fuentes de Dropbox configuradas en Streamlit Secrets.")

    st.markdown("---")
    st.subheader("Eventos recientes")
    if LOG_PATH.exists():
        with LOG_PATH.open("r", encoding="utf-8") as file_handle:
            log_lines = file_handle.readlines()[-20:]
        for line in log_lines:
            st.text(line.strip())
    else:
        st.info("Aún no hay registros de log.")


if __name__ == "__main__":
    main()
