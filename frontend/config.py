import os

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError


DROPBOX_SECRET_MAP = {
    "dropbox_rotacion": "Rotación Inventarios",
    "dropbox_cartera": "Cartera Ferreinox",
    "dropbox_ventas": "Ventas Ferreinox",
}


def get_streamlit_secrets():
    """Devuelve los secretos de Streamlit si existen; si no, retorna un dict vacío."""
    try:
        return st.secrets
    except StreamlitSecretNotFoundError:
        return {}


def get_dropbox_sources():
    """Devuelve las fuentes Dropbox configuradas en Streamlit Secrets."""
    sources = {}
    secrets = get_streamlit_secrets()
    for secret_name, label in DROPBOX_SECRET_MAP.items():
        if secret_name in secrets:
            sources[label] = dict(secrets[secret_name])
    return sources


def get_database_uri(required=True):
    """Obtiene el URI de PostgreSQL desde Streamlit Secrets o variables de entorno."""
    secrets = get_streamlit_secrets()
    if "postgres" in secrets and "db_uri" in secrets["postgres"]:
        return secrets["postgres"]["db_uri"]

    env_uri = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_DB_URI")
    if env_uri:
        return env_uri

    if required:
        raise RuntimeError(
            "No se encontró la configuración de PostgreSQL. Define postgres.db_uri en Secrets o DATABASE_URL en variables de entorno."
        )
    return None