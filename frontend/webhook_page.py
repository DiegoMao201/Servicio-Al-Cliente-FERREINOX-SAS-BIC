import os

import streamlit as st


def mask_value(value):
    if not value:
        return "No configurado"
    if len(value) <= 6:
        return "Configurado"
    return f"{value[:3]}...{value[-3:]}"


def main():
    st.title("Webhook WhatsApp")
    st.caption("Esta página existe para que tengas claro qué debes publicar, qué variable debe existir y en qué orden probar Meta.")

    backend_url = os.getenv("BACKEND_URL", "https://apicrm.datovatenexuspro.com").rstrip("/")
    verify_token = os.getenv("WHATSAPP_VERIFY_TOKEN")
    access_token = os.getenv("WHATSAPP_ACCESS_TOKEN")
    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")

    metric_1, metric_2, metric_3 = st.columns(3)
    metric_1.metric("Backend público", backend_url)
    metric_2.metric("Verify token", mask_value(verify_token))
    metric_3.metric("API envío", "Lista" if access_token and phone_number_id else "Pendiente")

    st.subheader("URL que debes usar en Meta")
    st.code(f"{backend_url}/webhooks/whatsapp")

    st.subheader("Prueba manual de verificación")
    if verify_token:
        st.code(
            f"{backend_url}/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token={verify_token}&hub.challenge=12345"
        )
    else:
        st.warning("Aún no existe WHATSAPP_VERIFY_TOKEN en este servicio. Sin esa variable no podrás verificar Meta.")

    st.subheader("Orden correcto")
    st.markdown(
        """
        1. Confirmar que el backend responde en `/health`.
        2. Confirmar que `WHATSAPP_VERIFY_TOKEN` está configurado en Coolify.
        3. Abrir la URL manual de verificación y validar que devuelva `12345`.
        4. Copiar la misma URL en Meta for Developers.
        5. Pegar exactamente el mismo verify token en Meta.
        6. Verificar el webhook.
        7. Suscribir el evento `messages`.
        8. Probar un mensaje real.
        """
    )

    st.subheader("Variables que deben existir en Coolify")
    st.markdown(
        """
        1. `DATABASE_URL`
        2. `PGRST_URL`
        3. `WHATSAPP_VERIFY_TOKEN`
        4. `WHATSAPP_ACCESS_TOKEN` si luego vas a responder mensajes
        5. `WHATSAPP_PHONE_NUMBER_ID` si luego vas a responder mensajes
        """
    )

    st.subheader("Qué hace hoy el backend")
    st.markdown(
        """
        1. Verifica la suscripción del webhook.
        2. Recibe mensajes entrantes de Meta.
        3. Crea o reutiliza el contacto.
        4. Crea o reutiliza la conversación.
        5. Guarda el mensaje entrante en la base.
        """
    )