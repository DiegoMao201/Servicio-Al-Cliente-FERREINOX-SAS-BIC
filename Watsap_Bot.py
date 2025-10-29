import os
import json
import requests
import google.generativeai as genai
from flask import Flask, request, make_response

# --- Configuración ---
app = Flask(__name__)

# Cargar las variables de entorno
# Asegúrate de que estas variables estén configurADAS en tu entorno
WHATSAPP_VERIFY_TOKEN = os.environ.get('WHATSAPP_VERIFY_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
WHATSAPP_ACCESS_TOKEN = os.environ.get('WHATSAPP_ACCESS_TOKEN')
WHATSAPP_PHONE_NUMBER_ID = os.environ.get('WHATSAPP_PHONE_NUMBER_ID')

# Validar que las variables de entorno existan
if not all([WHATSAPP_VERIFY_TOKEN, GEMINI_API_KEY, WHATSAPP_ACCESS_TOKEN, WHATSAPP_PHONE_NUMBER_ID]):
    print("Error: Faltan una o más variables de entorno.")
    # En un escenario real, querrías que la app falle si no tiene la configuración
    # exit(1) 

# Configurar Gemini
try:
    genai.configure(api_key=GEMINI_API_KEY)
    
    # Configuración de seguridad (ajusta según sea necesario)
    generation_config = {
        "temperature": 0.8,
        "top_p": 0.95,
        "top_k": 40,
    }
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    ]

    model = genai.GenerativeModel(
        model_name='gemini-1.5-pro-latest',
        generation_config=generation_config,
        safety_settings=safety_settings
    )
    print("Modelo Gemini cargado exitosamente.")
except Exception as e:
    print(f"Error al configurar Gemini: {e}")

# Diccionario para almacenar los historiales de chat por usuario
# NOTA: En producción, esto se reinicia si el servidor se reinicia.
# Para persistencia, deberías usar una base de datos (como Redis o Firestore).
user_chats = {}

# --- Funciones Auxiliares ---

def send_whatsapp_message(to_number, message_text):
    """
    Función para enviar un mensaje de vuelta al usuario.
    """
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
        response.raise_for_status() # Lanza un error si la solicitud falla
        print(f"Respuesta enviada a {to_number}: {response.json()}")
    except requests.exceptions.RequestException as e:
        # Imprime el error pero no rompe el flujo
        print(f"Error al enviar mensaje de WhatsApp: {e}")
        if e.response is not None:
            print(f"Respuesta del error de WhatsApp: {e.response.text}")

# --- Rutas del Webhook ---

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        # Verificación del Webhook (Configuración inicial en Meta)
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
                
                # Extraer la información relevante
                message_info = data['entry'][0]['changes'][0]['value']['messages'][0]
                
                # Asegurarse de que es un mensaje de texto
                if message_info['type'] == 'text':
                    user_message = message_info['text']['body']
                    user_phone_number = message_info['from']
                    
                    print(f"Mensaje de {user_phone_number}: {user_message}")

                    # --- Lógica del Chatbot con Memoria ---

                    # 1. Obtener o crear el historial de chat para este usuario
                    if user_phone_number not in user_chats:
                        print(f"Creando nuevo historial de chat para {user_phone_number}")
                        user_chats[user_phone_number] = model.start_chat(history=[])
                    
                    chat = user_chats[user_phone_number]

                    # 2. Enviar el mensaje a Gemini y manejar posibles errores
                    try:
                        print("Enviando a Gemini...")
                        response_gemini = chat.send_message(user_message)
                        gemini_reply = response_gemini.text
                        print(f"Respuesta de Gemini: {gemini_reply}")

                    except Exception as e:
                        print(f"Error al llamar a Gemini: {e}")
                        # Informar al usuario que algo salió mal con la IA
                        gemini_reply = "Lo siento, tuve un problema al procesar tu solicitud. Intenta de nuevo."
                        # Opcional: reiniciar el historial de chat si la conversación se corrompe
                        # del user_chats[user_phone_number]
                    
                    # 3. Enviar la respuesta de Gemini de vuelta a WhatsApp
                    send_whatsapp_message(user_phone_number, gemini_reply)

        except KeyError as e:
            print(f"KeyError: El payload no tiene la estructura esperada. Error en la clave: {e}")
        except Exception as e:
            print(f"Error general procesando el webhook POST: {e}")
            # No hagas 'pass' en silencio, imprime el error
        
        # Siempre devuelve 200 a Meta para que sepa que recibiste el evento
        return make_response('EVENT_RECEIVED', 200)

if __name__ == '__main__':
    # El puerto 5000 es común, pero algunos servicios de despliegue
    # (como Heroku o Render) te asignan un puerto en la variable 'PORT'
    port = int(os.environ.get('PORT', 8080)) # Cambiado a 8080, un puerto común
    app.run(host='0.0.0.0', port=port, debug=True) # debug=True es útil para desarrollo
