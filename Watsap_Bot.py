from flask import Flask, request, make_response
import json
import os # Importante para Render

app = Flask(__name__)

# El token lo pondremos como variable de entorno en Render
VERIFY_TOKEN = os.environ.get('WHATSAPP_VERIFY_TOKEN')

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        # Verificación del Webhook
        print("Recibiendo solicitud GET de verificación...")
        if request.args.get('hub.mode') == 'subscribe' and request.args.get('hub.verify_token') == VERIFY_TOKEN:
            print("¡Webhook verificado!")
            challenge = request.args.get('hub.challenge')
            return make_response(challenge, 200)
        else:
            print("Error de verificación. Tokens no coinciden.")
            return make_response('Error de verificación', 403)

    if request.method == 'POST':
        # Recepción de mensajes
        data = request.get_json()
        print("¡Mensaje recibido!")
        print(json.dumps(data, indent=2)) # Imprime el mensaje en los logs de Render

        # (Aquí llamaremos a Gemini)

        return make_response('EVENT_RECEIVED', 200)

if __name__ == '__main__':
    # Render maneja el puerto automáticamente, pero lo definimos
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
