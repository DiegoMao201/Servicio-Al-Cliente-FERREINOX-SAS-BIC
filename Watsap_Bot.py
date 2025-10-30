import os
import json
import requests
from flask import Flask, request, make_response

# --- NUEVAS LIBRERÍAS DE GOOGLE CLOUD ---
import vertexai
from vertexai.generative_models import GenerativeModel, Part
from google.oauth2 import service_account
from google.auth.exceptions import DefaultCredentialsError

# --- AGREGA ESTAS DOS LÍNEAS AQUÍ ---
try:
    import google.generativeai
    print(f"--- DEBUG: Versión de genai (antigua): {google.generativeai.__version__}")
except ImportError:
    print("--- DEBUG: google-generativeai (antigua) no está instalada.")

try:
    import vertexai
    print(f"--- DEBUG: Versión de vertexai (nueva): {vertexai.__version__}")
except Exception as e:
    print(f"--- DEBUG: Error al importar vertexai: {e}")
# -------------------------------------

# --- Configuración ---
app = Flask(__name__)

# Cargar las variables de entorno
WHATSAPP_VERIFY_TOKEN = os.environ.get('WHATSAPP_VERIFY_TOKEN')
WHATSAPP_ACCESS_TOKEN = os.environ.get('WHATSAPP_ACCESS_TOKEN')
WHATSAPP_PHONE_NUMBER_ID = os.environ.get('WHATSAPP_PHONE_NUMBER_ID')

# --- NUEVA CONFIGURACIÓN DE GOOGLE CLOUD (VERTEX AI) ---
model = None
user_chats = {} # Diccionario para almacenar los historiales de chat

try:
    print("Configurando Vertex AI (Google Cloud)...")

    # 1. Lee el JSON de la variable de entorno que creamos en Render
    credentials_json_str = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS_JSON')

    if not credentials_json_str:
        raise ValueError("Error: La variable 'GOOGLE_APPLICATION_CREDENTIALS_JSON' no está configurada.")

    # 2. Convierte el texto JSON en credenciales
    credentials_info = json.loads(credentials_json_str)
    credentials = service_account.Credentials.from_service_account_info(credentials_info)

    # 3. Obtiene el ID del Proyecto del JSON
    PROJECT_ID = credentials_info.get("project_id")
    if not PROJECT_ID:
        raise ValueError("Error: 'project_id' no encontrado en las credenciales JSON.")

    # 4. Inicializa Vertex AI (CON LA REGIÓN CORRECTA!)
    vertexai.init(project=PROJECT_ID, credentials=credentials, location="us-east1")

    # 5. Carga el modelo (¡USAMOS EL MODELO DE TU IMAGEN!)
    model = GenerativeModel("gemini-2.5-pro") 

    print(f"Vertex AI inicializado. Proyecto: {PROJECT_ID} en Región: us-east1")
    print("Modelo Gemini (gemini-2.5-pro) cargado exitosamente.")

except Exception as e:
    print(f"Error fatal al configurar Vertex AI: {e}")

# --- Funciones Auxiliares ---

def send_whatsapp_message(to_number, message_text):
    """
    Función para enviar un mensaje de vuelta al usuario.
    """
    if not WHATSAPP_ACCESS_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
        print("Error: Tokens de WhatsApp no configurados. No se puede enviar mensaje.")
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
        print(f"Respuesta enviada a {to_number}: {response.json()}")
    except requests.exceptions.RequestException as e:
        print(f"Error al enviar mensaje de WhatsApp: {e}")
        if e.response is not None:
            print(f"Respuesta del error de WhatsApp: {e.response.text}")

# --- Ruta de Depuración ---

@app.route('/version')
def version():
    """
    Una ruta de depuración para verificar la versión de la biblioteca instalada.
    """
    try:
        version_num = vertexai.__version__
        return f"La versión de google-cloud-aiplatform (vertexai) instalada es: {version_num}"
    except Exception as e:
        return f"Error al obtener la versión: {e}"

# --- Rutas del Webhook ---

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        # Verificación del Webhook
        print("Recibiendo solicitud GET de verificación...")
        if request.args.get('hub.mode') == 'subscribe' and request.args.get('hub.verify_token') == WHATSAPP_VERIFY_TOKEN:
            print("¡Webhook verificado!")
            challenge = request.args.get('hub.challenge')
            return make_response(challenge, 200)
        else:
            print("Error de verificación. Tokens no coinciden.")
            return make_response('Error de verificación', 403)

    if request.method == 'POST':
        # Recepción de mensajes del usuario
        data = request.get_json()
        print("¡Mensaje POST recibido!")
        print(json.dumps(data, indent=2))

        try:
            # Asegurarse de que el payload tiene la estructura esperada
            if (data.get('entry') and 
                data['entry'][0].get('changes') and 
                data['entry'][0]['changes'][0].get('value') and 
                data['entry'][0]['changes'][0]['value'].get('messages')):

                message_info = data['entry'][0]['changes'][0]['value']['messages'][0]

                # Asegurarse de que es un mensaje de texto
                if message_info['type'] == 'text':
                    user_message = message_info['text']['body']
                    user_phone_number = message_info['from']

                    print(f"Mensaje de {user_phone_number}: {user_message}")

                    # Verificar si el modelo de Vertex AI se cargó correctamente al inicio
                    if model is None:
                        print("Error: El modelo Vertex AI no está inicializado. Enviando mensaje de error.")
                        send_whatsapp_message(user_phone_number, "Lo siento, el servicio de IA no está disponible en este momento.")
                        return make_response('EVENT_RECEIVED', 200)

                    # --- NUEVA LÓGICA DEL CHATBOT CON VERTEX AI ---

                    # 1. Obtener o crear el historial de chat
                    if user_phone_number not in user_chats:
                        print(f"Creando nuevo historial de chat para {user_phone_number}")
                        # La biblioteca de Vertex AI maneja el historial de forma diferente
                        user_chats[user_phone_number] = [] 

                    history = user_chats[user_phone_number]

                    # 2. Enviar el mensaje a Gemini y manejar posibles errores
                    try:
                        # --- ¡CAMBIADO AL MODELO DE TU IMAGEN! ---
                        print(f"Enviando a Vertex AI (gemini-2.5-pro)...") 

                        # Manejar comandos especiales
                        if user_message.strip().lower() == "/reset":
                            user_chats[user_phone_number] = []
                            gemini_reply = "He olvidado nuestra conversación anterior. ¡Empecemos de nuevo!"
                            print("Historial de chat reseteado.")

                        else:
                            # --- Lógica de generación de Vertex AI ---
                            # Construimos el historial para la API
                            chat_history_parts = []
                            for item in history:
                                chat_history_parts.append(Part.from_text(item["text"]))
                                chat_history_parts.append(Part.from_text(item["response"]))

                            # Iniciamos una nueva sesión de chat con el historial
                            chat = model.start_chat(history=chat_history_parts)

                            response_gemini = chat.send_message(user_message)
                            gemini_reply = response_gemini.text

                            # Guardamos el nuevo turno en nuestro historial simple
                            history.append({"text": user_message, "response": gemini_reply})

                        print(f"Respuesta de Vertex AI: {gemini_reply}")

                    except Exception as e:
                        print(f"Error al llamar a Vertex AI: {e}")
                        gemini_reply = "Lo siento, tuve un problema al procesar tu solicitud. Intenta de nuevo."
                        # Opcional: reiniciar el historial si falla
                        if user_phone_number in user_chats:
                            del user_chats[user_phone_number]

                    # 3. Enviar la respuesta de Gemini de vuelta a WhatsApp
                    send_whatsapp_message(user_phone_number, gemini_reply)

        except KeyError as e:
            print(f"KeyError: El payload no tiene la estructura esperada. Error en la clave: {e}")
        except Exception as e:
            print(f"Error general procesando el webhook POST: {e}")

        return make_response('EVENT_RECEIVED', 200)

if __name__ == '__main__':
    # Render (o tu proveedor de hosting) te dará el puerto
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
