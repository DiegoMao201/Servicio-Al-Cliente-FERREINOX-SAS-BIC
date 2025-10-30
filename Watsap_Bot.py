import os
import json
import requests
import logging 
from flask import Flask, request, make_response
import google.generativeai as genai

# --- Configuración ---
app = Flask(__name__)
app.logger.setLevel(logging.INFO) 

# Cargar las variables de entorno
WHATSAPP_VERIFY_TOKEN = os.environ.get('WHATSAPP_VERIFY_TOKEN')
WHATSAPP_ACCESS_TOKEN = os.environ.get('WHATSAPP_ACCESS_TOKEN')
WHATSAPP_PHONE_NUMBER_ID = os.environ.get('WHATSAPP_PHONE_NUMBER_ID')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

model = None
user_chats = {} # Advertencia: Esto fallará en producción con Gunicorn (usar Redis)

try:
    if not GEMINI_API_KEY:
        raise ValueError("Error: La variable 'GEMINI_API_KEY' no está configurada.")

    genai.configure(api_key=GEMINI_API_KEY)

    # --- CORRECCIÓN ---
    # Basado en la lista que obtuviste, tu API Key tiene acceso a los
    # modelos más nuevos. Usaremos "gemini-pro-latest", que SÍ está 
    # en tu lista y soporta 'generateContent'.
    model = genai.GenerativeModel("gemini-pro-latest")
    # --- FIN CORRECCIÓN ---

    # (Opcional) Puedes verificar si el modelo carga antes de arrancar
    model.generate_content("Test") 
    
    app.logger.info("Google AI Studio (Gemini Gratuito) inicializado exitosamente.")
    app.logger.info("Modelo 'gemini-pro-latest' cargado y verificado.")

except Exception as e:
    app.logger.error(f"Error fatal al configurar Google AI Studio: {e}")


# --- Funciones Auxiliares ---

def send_whatsapp_message(to_number, message_text):
    if not WHATSAPP_ACCESS_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
        app.logger.error("Error: Tokens de WhatsApp no configurados. No se puede enviar mensaje.")
        return

    url = f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    data = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": message_text},
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status() 
        app.logger.info(f"Respuesta enviada a {to_number}: {response.json()}")
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error al enviar mensaje de WhatsApp: {e}")
        if e.response is not None:
            app.logger.error(f"Respuesta del error de WhatsApp: {e.response.text}")

# --- Ruta de Depuración (Opcional) ---
@app.route('/version')
def version():
    try:
        version_num = genai.__version__
        return f"Versión de google-generativeai: {version_num}"
    except Exception as e:
        return f"Error al obtener la versión: {e}"

# --- Rutas del Webhook ---
@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        app.logger.info("Recibiendo solicitud GET de verificación...")
        if request.args.get('hub.mode') == 'subscribe' and request.args.get('hub.verify_token') == WHATSAPP_VERIFY_TOKEN:
            app.logger.info("¡Webhook verificado!")
            challenge = request.args.get('hub.challenge')
            return make_response(challenge, 200)
        else:
            app.logger.warning("Error de verificación. Tokens no coinciden.")
            return make_response('Error de verificación', 403)

    if request.method == 'POST':
        data = request.get_json()
        app.logger.info("¡Mensaje POST recibido!")

        try:
            if (data.get('entry') and 
                data['entry'][0].get('changes') and 
                data['entry'][0]['changes'][0].get('value') and 
                data['entry'][0]['changes'][0]['value'].get('messages')):

                message_info = data['entry'][0]['changes'][0]['value']['messages'][0]

                if message_info['type'] == 'text':
                    user_message = message_info['text']['body']
                    user_phone_number = message_info['from']

                    app.logger.info(f"Mensaje de {user_phone_number}: {user_message}")

                    if model is None:
                        app.logger.error("Error: El modelo Google AI Studio no está inicializado.")
                        send_whatsapp_message(user_phone_number, "Lo siento, el servicio de IA no está disponible en este momento.")
                        return make_response('EVENT_RECEIVED', 200)

                    # --- Lógica de Chatbot ---
                    if user_phone_number not in user_chats:
                        app.logger.info(f"Creando nueva sesión de chat para {user_phone_number}")
                        user_chats[user_phone_number] = model.start_chat(history=[])
                    
                    chat_session = user_chats[user_phone_number]

                    try:
                        app.logger.info(f"Enviando a Google AI Studio (gemini-pro-latest)...") 

                        if user_message.strip().lower() == "/reset":
                            user_chats[user_phone_number] = model.start_chat(history=[])
                            gemini_reply = "He olvidado nuestra conversación anterior. ¡Empecemos de nuevo!"
                            app.logger.info(f"Historial de chat reseteado para {user_phone_number}.")
                        else:
                            response_gemini = chat_session.send_message(user_message)
                            gemini_reply = response_gemini.text

                        app.logger.info(f"Respuesta de Google AI Studio: {gemini_reply[:50]}...")

                    except Exception as e:
                        # Aquí es donde ya no deberías ver el error 404
                        app.logger.error(f"Error al llamar a Google AI Studio: {e}")
                        gemini_reply = "Lo siento, tuve un problema al procesar tu solicitud. Intenta de nuevo."
                        if user_phone_number in user_chats:
                            del user_chats[user_phone_number]

                    send_whatsapp_message(user_phone_number, gemini_reply)

        except KeyError as e:
            app.logger.error(f"KeyError: El payload no tiene la estructura esperada. Clave: {e}")
        except Exception as e:
            app.logger.error(f"Error general procesando el webhook POST: {e}", exc_info=True)

        return make_response('EVENT_RECEIVED', 200)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
