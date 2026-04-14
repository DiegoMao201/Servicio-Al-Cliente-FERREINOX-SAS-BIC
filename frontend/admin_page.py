import streamlit as st
import requests
import os

from frontend.config import get_database_uri
from frontend.crm_data import load_crm_hub_snapshot, load_data_readiness
from frontend.ui import render_highlight, render_metric_card, render_page_hero, render_section_intro


def main():
    render_page_hero(
        "Ferreinox CRM",
        "Panel Administrador",
        "Esta vista concentra el control del sistema completo: operación del CRM, estado de base, automatización y módulos técnicos que no necesita el operador diario.",
        badge="Vista avanzada para supervisión y soporte",
    )

    try:
        db_uri = get_database_uri()
        crm_snapshot = load_crm_hub_snapshot(db_uri)
        readiness = load_data_readiness(db_uri)
    except Exception as exc:
        st.error(f"No fue posible cargar el panel administrador: {exc}")
        return

    if not crm_snapshot.get("available"):
        st.error("Las tablas del agente aún no existen en esta base.")
        return

    metrics = crm_snapshot["metrics"]
    metric_cols = st.columns(5)
    cards = [
        ("Conversaciones activas", metrics["conversaciones_activas"], "Carga viva del CRM conversacional."),
        ("Listas para gestionar", metrics["conversaciones_por_cerrar"], "Casos donde el cliente ya dio cierre y falta orden final."),
        ("Tareas pendientes", metrics["tareas_pendientes"], "Trabajo operativo todavía abierto."),
        ("Base oficial", f"{readiness['raw_with_data']}/{readiness['raw_total']}", "Cobertura de tablas raw oficiales con datos."),
        ("PostgREST", f"{readiness['views_ready']}/{readiness['views_total']}", "Vistas SQL listas para consumo del CRM y del agente."),
    ]
    for column, (label, value, caption) in zip(metric_cols, cards):
        with column:
            render_metric_card(label, value, caption)

    render_highlight(
        "<strong>Uso recomendado:</strong> deja al operador solo con Centro Operativo, Conversaciones y Base Oficial. Todo lo demás debe vivir aquí como capa de administración y soporte."
    )

    left_col, right_col = st.columns([1.15, 1])
    with left_col:
        render_section_intro(
            "Módulos administrativos",
            "Estas son las áreas avanzadas que se conservan visibles solo para supervisión, despliegue y diagnóstico.",
        )
        st.markdown(
            """
            1. Flujo CRM: reglas de enrutamiento, tareas, correos y automatización.
            2. Centro del Agente: monitoreo del comportamiento del agente y sus entidades operativas.
            3. WhatsApp y Webhook: conectividad del canal y recepción de eventos.
            4. Estado de Cargas y Sincronización Dropbox: control de fuentes, logs y recargas.
            5. Arquitectura de Datos, Operación SQL y Diagnóstico: soporte técnico y revisión profunda.
            """
        )

    with right_col:
        render_section_intro(
            "Señales que sí debe vigilar el administrador",
            "Aquí se resume la salud general del sistema para decidir cuándo intervenir o cuándo dejar operar solo al equipo.",
        )
        st.dataframe(crm_snapshot["areas_df"], width="stretch")
        if readiness["latest_runs_df"].empty:
            st.info("No hay eventos recientes en sync_run_log para mostrar.")
        else:
            st.dataframe(readiness["latest_runs_df"].head(8), width="stretch")

        # Botón para actualizar PostgREST desde el frontend (requiere `ADMIN_API_KEY` en secrets o env)
        try:
            admin_key = st.secrets.get("ADMIN_API_KEY") if hasattr(st, "secrets") else None
        except Exception:
            admin_key = None
        admin_key = admin_key or os.getenv("ADMIN_API_KEY")
        backend_url = None
        try:
            backend_url = st.secrets.get("BACKEND_URL")
        except Exception:
            backend_url = None
        backend_url = backend_url or os.getenv("BACKEND_URL") or "https://apicrm.datovatenexuspro.com"

        if st.button("🔁 Actualizar PostgREST (admin)"):
            if not admin_key:
                st.error("No ADMIN_API_KEY configurada en Streamlit Secrets o en la variable de entorno ADMIN_API_KEY.")
            else:
                with st.spinner("Solicitando actualización de vistas a backend..."):
                    try:
                        resp = requests.post(f"{backend_url}/admin/apply-postgrest-views", headers={"x-admin-key": admin_key}, json={}, timeout=30)
                        try:
                            body = resp.json()
                        except Exception:
                            body = resp.text
                        if resp.status_code in (200,202):
                            st.success(f"Actualización solicitada: {body}")
                        else:
                            st.error(f"Error {resp.status_code}: {body}")
                    except Exception as exc:
                        st.error(f"Fallo al llamar al backend: {exc}")
