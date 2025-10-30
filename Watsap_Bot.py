import os
import json
import requests
import logging
import threading  # Corregido: Reemplazado el espacio invisible U+00A0 con un espacio normal
import gspread    # Para Google Sheets
from google.oauth2.service_account import Credentials  # Para Google Sheets
from datetime import datetime  # Para la marca de tiempo
from flask import Flask, request, make_response
import google.generativeai as genai

# --- Configuración de Logging y Flask ---
app = Flask(__name__)
app.logger.setLevel(logging.INFO)

# --- Cargar Variables de Entorno ---

# WhatsApp
WHATSAPP_VERIFY_TOKEN = os.environ.get('WHATSAPP_VERIFY_TOKEN')
WHATSAPP_ACCESS_TOKEN = os.environ.get('WHATSAPP_ACCESS_TOKEN')
WHATSAPP_PHONE_NUMBER_ID = os.environ.get('WHATSAPP_PHONE_NUMBER_ID')

# Gemini
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# Google Sheets
GCP_JSON_STR = os.environ.get('GCP_SERVICE_ACCOUNT_JSON')
GOOGLE_SHEET_NAME = os.environ.get('GOOGLE_SHEET_NAME')
GOOGLE_WORKSHEET_NAME = os.environ.get('GOOGLE_WORKSHEET_NAME')

# --- Estado en Memoria (¡ADVERTENCIA!) ---
# Estas variables se reiniciarán con cada despliegue.
# Y NO funcionarán correctamente si Gunicorn usa más de 1 worker (proceso).
# Para una solución de producción real, esto debería usar una base de datos (ej. Redis).
user_chats = {}
processed_message_ids = set() # Para evitar procesar duplicados

# --- Inicialización de Google Sheets ---
worksheet = None # Hoja de cálculo de Google
try:
    if not GCP_JSON_STR or not GOOGLE_SHEET_NAME or not GOOGLE_WORKSHEET_NAME:
        app.logger.warning("Variables de Google Sheets no configuradas. El log de chats está desactivado.")
    else:
        # Cargar las credenciales desde el string JSON en la variable de entorno
        creds_dict = json.loads(GCP_JSON_STR)
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive.file'
        ]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client_gspread = gspread.authorize(creds)
        
        # Abrir la hoja de cálculo y la pestaña
        sheet = client_gspread.open(GOOGLE_SHEET_NAME)
        worksheet = sheet.worksheet(GOOGLE_WORKSHEET_NAME)
        
        # (Opcional) Añadir cabeceras si la hoja está vacía
        if not worksheet.get_all_values():
              worksheet.append_row(["Timestamp", "Numero_Usuario", "Mensaje_Usuario", "Respuesta_Bot"])
        
        app.logger.info(f"Conectado a Google Sheets: {GOOGLE_SHEET_NAME} -> {GOOGLE_WORKSHEET_NAME}")

except Exception as e:
    app.logger.error(f"Error al inicializar Google Sheets: {e}")
    worksheet = None # Desactivar si falla

# --- Inicialización de Gemini ---
model = None
try:
    if not GEMINI_API_KEY:
        raise ValueError("Error: La variable 'GEMINI_API_KEY' no está configurada.")

    genai.configure(api_key=GEMINI_API_KEY)

    # --- Instrucción de Sistema para el Tono ---
    # Aquí definimos la "personalidad" del bot.
    # ¡Personaliza el "[Nombre de tu Empresa]"!
    system_instruction = (
        "Eres un asistente de servicio al cliente de [Nombre de tu Empresa]. "
        "Habla de forma amable, cercana y natural, como lo haría una persona. "
        "Tus respuestas deben ser cortas y directas al punto, resumiendo la información. "
        "Nunca digas que eres un bot o una inteligencia artificial. "
        "Trata al cliente con familiaridad (tuteándolo)."
    )
    
    # Usamos el modelo con la instrucción de sistema
    model = genai.GenerativeModel(
        model_name="gemini-pro-latest", # O "gemini-1.5-flash-latest" si lo prefieres
        system_instruction=system_instruction
    )

    # Verificación rápida del modelo
    model.generate_content("Test")
    app.logger.info("Modelo Gemini ('gemini-pro-latest' con System Instruction) inicializado exitosamente.")

except Exception as e:
    app.logger.error(f"Error fatal al configurar Google AI Studio: {e}")

# --- Funciones Auxiliares ---

def send_whatsapp_message(to_number, message_text):
    """Envía un mensaje de texto de WhatsApp."""
    if not WHATSAPP_ACCESS_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
        app.logger.error("Error: Tokens de WhatsApp no configurados.")
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

def log_to_google_sheet(timestamp, phone, user_msg, bot_msg):
    """Registra la conversación en la hoja de Google Sheets."""
    global worksheet
    if worksheet is None:
        app.logger.warning("Intento de loggear, pero Google Sheets no está configurado.")
        return

    try:
        # Añade una nueva fila al final de la hoja
        worksheet.append_row([timestamp, phone, user_msg, bot_msg])
        app.logger.info(f"Chat loggeado en Google Sheets para {phone}")
    except Exception as e:
        # Si falla (ej. permisos, API caída), solo registra el error y continúa
        app.logger.error(f"Error al escribir en Google Sheets: {e}")

def process_message_in_thread(user_phone_number, user_message, message_id):
    """
    Esta función se ejecuta en un hilo separado para procesar el mensaje
    y responder, evitando el timeout de WhatsApp.
    """
    global model, user_chats, processed_message_ids

    try:
        # --- SOLUCIÓN DUPLICADOS (Paso 1) ---
        # Si ya hemos procesado este ID, lo ignoramos.
        if message_id in processed_message_ids:
            app.logger.warning(f"Mensaje duplicado recibido (ID: {message_id}). Ignorando.")
            return
        
        # Añadimos el ID al set para no procesarlo de nuevo.
        # (Limitamos el set a 1000 IDs para que no crezca indefinidamente)
        if len(processed_message_ids) > 1000:
            processed_message_ids.clear()
        processed_message_ids.add(message_id)
        # --- FIN SOLUCIÓN DUPLICADOS ---

        if model is None:
            app.logger.error("Error: El modelo Google AI Studio no está inicializado.")
            send_whatsapp_message(user_phone_number, "Lo siento, el servicio de IA no está disponible en este momento.")
            return

        # --- Lógica de Chatbot ---
        if user_phone_number not in user_chats:
            app.logger.info(f"Creando nueva sesión de chat para {user_phone_number}")
            user_chats[user_phone_number] = model.start_chat(history=[])
        
        chat_session = user_chats[user_phone_number]
        
        gemini_reply = "" # Inicializar variable
        
        try:
            app.logger.info(f"Enviando a Google AI Studio...")

            if user_message.strip().lower() == "/reset":
                user_chats[user_phone_number] = model.start_chat(history=[])
                gemini_reply = "¡Listo! Empecemos de nuevo. ¿En qué te puedo ayudar?"
                app.logger.info(f"Historial de chat reseteado para {user_phone_number}.")
            else:
                # Aquí es donde Gemini usa la "system_instruction" para el tono
                response_gemini = chat_session.send_message(user_message)
                gemini_reply = response_gemini.text

            app.logger.info(f"Respuesta de Google AI Studio: {gemini_reply[:50]}...")

        except Exception as e:
            app.logger.error(f"Error al llamar a Google AI Studio: {e}")
            gemini_reply = "Perdona, se me fue la idea. ¿Puedes repetirme eso?"
            # Reiniciamos el chat si falla Gemini
            if user_phone_number in user_chats:
                del user_chats[user_phone_number]

        # 1. Enviar respuesta a WhatsApp
        send_whatsapp_message(user_phone_number, gemini_reply)

        # 2. Registrar en Google Sheets
        timestamp = datetime.now().isoformat()
        log_to_google_sheet(timestamp, user_phone_number, user_message, gemini_reply)

    except Exception as e:
        app.logger.error(f"Error fatal en el hilo de procesamiento: {e}", exc_info=True)

# --- Rutas del Webhook ---
@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        # Verificación del Webhook
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
            # Estructura de un mensaje de texto normal
            if (data.get('entry') and 
                data['entry'][0].get('changes') and 
                data['entry'][0]['changes'][0].get('value') and 
                data['entry'][0]['changes'][0]['value'].get('messages') and
                data['entry'][0]['changes'][0]['value']['messages'][0]):

                message_info = data['entry'][0]['changes'][0]['value']['messages'][0]

                if message_info['type'] == 'text':
                    user_message = message_info['text']['body']
                    user_phone_number = message_info['from']
                    message_id = message_info['id'] # ID único del mensaje

                    app.logger.info(f"Mensaje de {user_phone_number} (ID: {message_id}): {user_message}")

                    # --- SOLUCIÓN A MÚLTIPLES RESPUESTAS ---
                    # 1. Creamos un hilo (thread) que ejecutará la función 'process_message_in_thread'
                    processing_thread = threading.Thread(
                        target=process_message_in_thread,
                        args=(user_phone_number, user_message, message_id)
                    )
                    
                    # 2. Iniciamos el hilo (se ejecutará en segundo plano)
                    processing_thread.start()
                    
                    # 3. Respondemos INMEDIATAMENTE a WhatsApp con 200 (OK)
                    # Esto le dice a WhatsApp "Recibido, gracias", y ya no lo volverá a enviar.
                    return make_response('EVENT_RECEIVED', 200)

            # Si no es un mensaje de texto o tiene otra estructura, lo ignoramos pero damos OK
            app.logger.info("Payload recibido, pero no es un mensaje de texto procesable.")
            return make_response('EVENT_RECEIVED', 200)

        except KeyError as e:
            app.logger.error(f"KeyError: El payload no tiene la estructura esperada. Clave: {e}")
            return make_response('EVENT_RECEIVED', 200) # Igual respondemos 200
        except Exception as e:
            app.logger.error(f"Error general procesando el webhook POST: {e}", exc_info=True)
            return make_response('EVENT_RECEIVED', 200) # Igual respondemos 200

# --- Ruta de Depuración (Opcional) ---
@app.route('/version')
def version():
    try:
        version_num = genai.__version__
        return f"Versión de google-generativeai: {version_num}"
    except Exception as e:
        return f"Error al obtener la versión: {e}"

# --- Inicio de la Aplicación ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    # 'debug=False' es crucial para producción
    app.run(host='0.0.0.0', port=port, debug=False)
