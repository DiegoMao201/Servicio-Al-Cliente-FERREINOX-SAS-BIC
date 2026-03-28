import os

import streamlit as st


DROPBOX_SECRET_MAP = {
    "dropbox_rotacion": "Rotación Inventarios",
    "dropbox_cartera": "Cartera Ferreinox",
    "dropbox_ventas": "Ventas Ferreinox",
}


def get_dropbox_sources():
    """Devuelve las fuentes Dropbox configuradas en Streamlit Secrets."""
    sources = {}
    for secret_name, label in DROPBOX_SECRET_MAP.items():
        if secret_name in st.secrets:
            sources[label] = dict(st.secrets[secret_name])
    return sources


def get_database_uri(required=True):
    """Obtiene el URI de PostgreSQL desde Streamlit Secrets o variables de entorno."""
    if "postgres" in st.secrets and "db_uri" in st.secrets["postgres"]:
        return st.secrets["postgres"]["db_uri"]

    env_uri = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_DB_URI")
    if env_uri:
        return env_uri

    if required:
        raise RuntimeError(
            "No se encontró la configuración de PostgreSQL. Define postgres.db_uri en Secrets o DATABASE_URL en variables de entorno."
        )
    return None