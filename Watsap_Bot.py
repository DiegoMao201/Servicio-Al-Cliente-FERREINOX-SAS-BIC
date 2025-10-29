import os
import json
import requests
import google.generativeai as genai
from flask import Flask, request, make_response

app = Flask(__name__)

# Cargar las variables de entorno
WHATSAPP_VERIFY_TOKEN = os.environ.get('WHATSAPP_VERIFY_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
WHATSAPP_ACCESS_TOKEN = os.environ.get('WHATSAPP_ACCESS_TOKEN')
WHATSAPP_PHONE_NUMBER_ID = os.environ.get('WHATSAPP_PHONE_NUMBER_ID')

# Configurar Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.0-pro')

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
        print(f"Error al enviar mensaje: {e}")

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
        print("¡Mensaje recibido!")
        print(json.dumps(data, indent=2))
        
        try:
            # Extraer la información relevante del JSON
            # La estructura puede variar, esto es para mensajes de texto
            message_info = data['entry'][0]['changes'][0]['value']['messages'][0]
            
            # Asegurarse de que es un mensaje de texto
            if message_info['type'] == 'text':
                user_message = message_info['text']['body']
                user_phone_number = message_info['from']
                
                print(f"Mensaje de {user_phone_number}: {user_message}")
                
                # 1. Enviar el mensaje a Gemini
                print("Enviando a Gemini...")
                response_gemini = model.generate_content(user_message)
                gemini_reply = response_gemini.text
                print(f"Respuesta de Gemini: {gemini_reply}")
                
                # 2. Enviar la respuesta de Gemini de vuelta a WhatsApp
                send_whatsapp_message(user_phone_number, gemini_reply)

        except Exception as e:
            print(f"Error procesando el mensaje: {e}")
            # Imprime el error pero no rompe el webhook
            pass

        return make_response('EVENT_RECEIVED', 200)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
