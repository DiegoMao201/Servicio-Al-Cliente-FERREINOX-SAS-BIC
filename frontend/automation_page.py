import streamlit as st

from frontend.config import get_database_uri
from frontend.crm_data import load_crm_hub_snapshot
from frontend.ui import render_flow_step, render_highlight, render_metric_card, render_page_hero, render_section_intro


def main():
    render_page_hero(
        "Ferreinox CRM",
        "Flujo CRM y Automatización",
        "Define con claridad qué debe hacer el sistema cuando la IA entiende una venta, una consulta de cartera, un reclamo o una solicitud que debe salir por correo a otra área.",
        badge="Diseño operativo del agente",
    )

    try:
        db_uri = get_database_uri()
    except RuntimeError as exc:
        st.error(str(exc))
        return

    try:
        snapshot = load_crm_hub_snapshot(db_uri)
    except Exception as exc:
        st.error(f"No fue posible cargar el flujo CRM: {exc}")
        return

    if not snapshot.get("available"):
        st.error("Las tablas del agente aún no existen en esta base.")
        return

    metrics = snapshot["metrics"]
    metric_cols = st.columns(4)
    cards = [
        ("Contactos CRM", metrics["contactos"], "Base actual de contactos de WhatsApp ya relacionados con el CRM."),
        ("Cotizaciones activas", metrics["cotizaciones_activas"], "Negocios que el agente ya puede dejar listos para seguimiento comercial."),
        ("Pedidos abiertos", metrics["pedidos_abiertos"], "Pedidos que deben terminar en ERP o confirmación humana."),
        ("Tareas en cola", metrics["tareas_pendientes"], "Acciones pendientes que hoy requieren organización por área."),
    ]
    for column, (label, value, caption) in zip(metric_cols, cards):
        with column:
            render_metric_card(label, value, caption)

    render_highlight(
        "<strong>Diseño esperado:</strong> la respuesta del agente no debe quedar aislada. Debe producir una salida operativa clara: tarea, correo, cotización, pedido o cierre con aprendizaje confiable."
    )

    render_section_intro(
        "Ruta crítica para un reclamo",
        "Este es el flujo que conviene dejar fijo para que el cliente sienta una respuesta inmediata y el equipo interno reciba el caso con contexto completo.",
    )
    flow_cols = st.columns(5)
    flow_steps = [
        (1, "Cliente reporta", "Escribe inconformidad, retraso, devolución o error de facturación por WhatsApp."),
        (2, "IA clasifica", "Marca el caso como reclamo, eleva prioridad y resume el problema con lenguaje ejecutivo."),
        (3, "Respuesta inmediata", "El agente acusa recibo y comunica tiempo estimado o siguiente paso al cliente."),
        (4, "Salida interna", "Se crea tarea y se prepara correo con conversación, cliente, resumen y área destino."),
        (5, "Aprendizaje", "Al cerrar, el motivo real y la solución final alimentan la memoria operativa del agente."),
    ]
    for column, step in zip(flow_cols, flow_steps):
        with column:
            render_flow_step(*step)

    left_col, right_col = st.columns([1.1, 1])
    with left_col:
        render_section_intro(
            "Matriz de enrutamiento",
            "Esta tabla deja explícita la lógica que luego debe ejecutar el backend para correo, tareas y escalamiento por área.",
        )
        st.dataframe(snapshot["routing_rules_df"], use_container_width=True)

    with right_col:
        render_section_intro(
            "Lo que ya está ocurriendo",
            "Estos son los tipos de intención y carga operativa que ya existen en la base del agente y que deben gobernar el nuevo frontend.",
        )
        if snapshot["intents_df"].empty:
            st.info("Aún no hay intenciones suficientes para resumir.")
        else:
            st.dataframe(snapshot["intents_df"], use_container_width=True)
        if snapshot["areas_df"].empty:
            st.info("Aún no hay tareas suficientes para resumir por área.")
        else:
            st.dataframe(snapshot["areas_df"], use_container_width=True)

    st.markdown("### Salida esperada por caso")
    st.markdown(
        """
        1. Venta o cotización: responder, dejar cotización estructurada y alertar a ventas si requiere intervención.
        2. Cartera o facturación: validar identidad, resolver y crear seguimiento a contabilidad si hay vencidos o inconsistencias.
        3. Reclamo: responder de inmediato, crear tarea prioritaria y preparar correo completo al área responsable.
        4. Compra especial o abastecimiento: consolidar requerimiento y elevarlo a compras con contexto del cliente.
        5. Caso resuelto: cerrar, resumir y guardar lo aprendido para no repetir fricción en conversaciones futuras.
        """
    )