import os

import streamlit as st


def is_configured(value):
    return "Si" if value else "No"


def main():
    st.title("Agente IA")
    st.caption("Esta página resume qué hace ya el agente, qué depende de OpenAI y WhatsApp, y qué revisar antes de dejarlo respondiendo solo.")

    openai_key = os.getenv("OPENAI_API_KEY")
    openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    whatsapp_access_token = os.getenv("WHATSAPP_ACCESS_TOKEN")
    whatsapp_phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    sendgrid_api_key = os.getenv("SENDGRID_API_KEY")
    sendgrid_from_email = os.getenv("SENDGRID_FROM_EMAIL")

    metric_1, metric_2, metric_3, metric_4 = st.columns(4)
    metric_1.metric("OpenAI configurado", is_configured(openai_key))
    metric_2.metric("Modelo activo", openai_model)
    metric_3.metric("WhatsApp salida listo", "Si" if whatsapp_access_token and whatsapp_phone_number_id else "No")
    metric_4.metric("SendGrid listo", "Si" if sendgrid_api_key and sendgrid_from_email else "No")

    st.subheader("Qué hace ya el agente")
    st.markdown(
        """
        1. Recibe el mensaje entrante desde WhatsApp.
        2. Guarda el mensaje y la conversación en PostgreSQL.
        3. Pide cédula, NIT, código de cliente o nombre registrado antes de responder cartera, ventas u otros datos sensibles.
        4. Busca contexto comercial del cliente en PostgREST cuando puede relacionarlo.
        5. Busca contexto de productos cuando la conversación habla de referencias, artículos o inventario.
        6. Envía el historial reciente y el contexto ERP al modelo de OpenAI.
        7. Detecta tono, intención y prioridad.
        8. Genera una respuesta y la envía de vuelta por WhatsApp.
        9. Guarda también la respuesta saliente en `agent_message`.
        10. Puede crear tareas básicas de seguimiento cuando el modelo lo indique.
        11. Ya detecta mejor cambios de tema entre cartera, compras, productos, cotizaciones, pedidos y reclamos.
        12. Ya guía reclamos paso a paso: producto, detalle del problema, evidencia o lote y correo antes de radicar el caso.
        13. Ya consolida listas de pedido o cotización en un solo mensaje, pide tienda y canal de entrega, y guarda borradores reales en `agent_order` o `agent_quote`.
        14. Si SendGrid está configurado, puede escalar reclamos al correo operativo, enviar constancia elegante al cliente y mandar resumen comercial por correo cuando el cliente lo prefiera.
        """
    )

    st.subheader("Variables obligatorias para dejarlo respondiendo")
    st.markdown(
        """
        1. `OPENAI_API_KEY`
        2. `WHATSAPP_ACCESS_TOKEN`
        3. `WHATSAPP_PHONE_NUMBER_ID`
        4. `DATABASE_URL`
        5. `PGRST_URL`
        6. `SENDGRID_API_KEY`
        7. `SENDGRID_FROM_EMAIL`
        8. `SENDGRID_FROM_NAME`
        9. `SENDGRID_RECLAMOS_TO_EMAIL`
        10. `SENDGRID_VENTAS_TO_EMAIL`
        """
    )

    st.subheader("Configuración de correo operativo")
    st.code(
        """[sendgrid]
api_key = \"SG.xxxxxxxxxxxxxxxxx\"
from_email = \"tiendapintucopereira@ferreinox.co\"
from_name = \"Ferreinox S.A.S. BIC\"
reclamos_to_email = "tiendapintucopereira@ferreinox.co"
ventas_to_email = "tiendapintucopereira@ferreinox.co"
""",
        language="toml",
    )
    st.caption("En producción conviene cargar estas mismas variables en Coolify como variables de entorno y no dejar la llave en archivos locales.")

    st.subheader("Modelo recomendado ahora")
    st.info(
        "El backend ya usa `gpt-4o-mini` por defecto. Es una opción económica y suficiente para esta primera fase de atención, clasificación de tono e intención."
    )

    st.subheader("Checklist antes de dejarlo en automático")
    st.markdown(
        """
        1. Confirmar que `Centro Operativo` muestra la base oficial correcta.
        2. Confirmar que `Centro del Agente` ya registra mensajes entrantes.
        3. Confirmar que el backend responde en `/health`.
        4. Confirmar que `OPENAI_API_KEY` está cargada en Coolify.
        5. Confirmar que `WHATSAPP_ACCESS_TOKEN` y `WHATSAPP_PHONE_NUMBER_ID` están cargados en Coolify.
        6. Probar con un mensaje real y revisar si aparece también un mensaje `outbound` en `Centro del Agente`.
        7. Revisar el tono y el contenido de las primeras respuestas antes de escalar uso.
        """
    )

    st.subheader("Siguiente nivel")
    st.markdown(
        """
        1. Añadir reglas de negocio por intención: cartera, pedidos, inventario, pagos.
        2. Convertir borradores de cotización y pedido en documentos finales con PDF y envío por WhatsApp o correo.
        3. Crear tareas automáticas con más criterio y prioridad real.
        4. Añadir escalamiento a humano.
        5. Añadir plantillas y límites para respuestas sensibles.
        """
    )