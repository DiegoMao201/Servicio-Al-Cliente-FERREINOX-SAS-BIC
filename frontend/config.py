import os

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError


DROPBOX_SECRET_MAP = {
    "dropbox_rotacion": "Rotación Inventarios",
    "dropbox_cartera": "Cartera Ferreinox",
    "dropbox_ventas": "Ventas Ferreinox",
}

DROPBOX_ENV_MAP = {
    "dropbox_rotacion": {
        "label": "Rotación Inventarios",
        "app_key": "DROPBOX_ROTACION_APP_KEY",
        "app_secret": "DROPBOX_ROTACION_APP_SECRET",
        "refresh_token": "DROPBOX_ROTACION_REFRESH_TOKEN",
        "folder": "DROPBOX_ROTACION_FOLDER",
    },
    "dropbox_cartera": {
        "label": "Cartera Ferreinox",
        "app_key": "DROPBOX_CARTERA_APP_KEY",
        "app_secret": "DROPBOX_CARTERA_APP_SECRET",
        "refresh_token": "DROPBOX_CARTERA_REFRESH_TOKEN",
        "folder": "DROPBOX_CARTERA_FOLDER",
    },
    "dropbox_ventas": {
        "label": "Ventas Ferreinox",
        "app_key": "DROPBOX_VENTAS_APP_KEY",
        "app_secret": "DROPBOX_VENTAS_APP_SECRET",
        "refresh_token": "DROPBOX_VENTAS_REFRESH_TOKEN",
        "folder": "DROPBOX_VENTAS_FOLDER",
    },
}


def get_streamlit_secrets():
    """Devuelve los secretos de Streamlit si existen; si no, retorna un dict vacío."""
    try:
        return dict(st.secrets)
    except (StreamlitSecretNotFoundError, Exception):
        return {}


def get_dropbox_sources():
    """Devuelve las fuentes Dropbox configuradas en Streamlit Secrets."""
    sources = {}
    secrets = get_streamlit_secrets()
    for secret_name, label in DROPBOX_SECRET_MAP.items():
        if secret_name in secrets:
            sources[label] = dict(secrets[secret_name])

    for config in DROPBOX_ENV_MAP.values():
        label = config["label"]
        if label in sources:
            continue

        app_key = os.getenv(config["app_key"])
        app_secret = os.getenv(config["app_secret"])
        refresh_token = os.getenv(config["refresh_token"])
        folder = os.getenv(config["folder"], "/data")

        if app_key and app_secret and refresh_token:
            sources[label] = {
                "app_key": app_key,
                "app_secret": app_secret,
                "refresh_token": refresh_token,
                "folder": folder,
            }

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