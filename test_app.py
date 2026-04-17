from flask import Flask, jsonify
from datetime import datetime
import os

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        'status': 'ok',
        'message': 'Picap Voice Agent - Running',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'env': {
            'twilio_configured': bool(os.getenv('TWILIO_ACCOUNT_SID')),
            'flask_env': os.getenv('FLASK_ENV', 'development')
        }
    })

@app.route('/voice/incoming', methods=['POST'])
def voice_incoming():
    from twilio.twiml.voice_response import VoiceResponse
    
    response = VoiceResponse()
    response.say(
        "Hola, bienvenido a Picap. Este es el agente de voz en modo de prueba.",
        language='es-MX',
        voice='Polly.Mia'
    )
    response.hangup()
    
    return str(response), 200, {'Content-Type': 'text/xml'}

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
