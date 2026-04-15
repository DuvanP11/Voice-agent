"""
Agente de Voz para Activación de Pilotos - Picap v2.0
Actualizado con datos reales de ClickHouse
"""

from flask import Flask, request, Response
from twilio.twiml.voice_response import VoiceResponse, Gather
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
from clickhouse_driver import Client

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Cargar configuración de documentos
with open('document_configs_real.json', 'r', encoding='utf-8') as f:
    CONFIG = json.load(f)

# ClickHouse client
ch_client = Client(
    host='localhost',  # Ajustar según tu config
    port=9000,
    database='picapmongoprod',
    user='default',
    password='tu_password'
)


class DocumentAnalyzer:
    """Analiza documentos rechazados del piloto desde ClickHouse"""
    
    def __init__(self, passenger_id: str):
        self.passenger_id = passenger_id
        self.rejected_docs = []
        self.pilot_info = {}
        
    def fetch_rejected_documents(self) -> List[Dict]:
        """Obtiene documentos rechazados del piloto desde ClickHouse"""
        query = """
        SELECT 
            defs.driver_enrollment_document_form_id,
            dedf.form_key,
            defs.status_cd,
            defs.rejected_reason_id,
            defs.comment,
            defs.created_at,
            defs.updated_at,
            rr.name as rejection_reason_name
        FROM picapmongoprod.driver_enrollment_document_form_solutions defs
        LEFT JOIN picapmongoprod.driver_enrollment_document_forms dedf 
            ON defs.driver_enrollment_document_form_id = dedf._id
        LEFT JOIN picapmongoprod.rejected_reasons rr
            ON defs.rejected_reason_id = rr._id
        WHERE defs.passenger_id = %(passenger_id)s
        AND defs.status_cd = 3  -- Rechazado
        ORDER BY defs.updated_at DESC
        LIMIT 20
        """
        
        results = ch_client.execute(query, {'passenger_id': self.passenger_id})
        
        self.rejected_docs = [
            {
                'form_id': row[0],
                'form_key': row[1],
                'status': row[2],
                'rejected_reason_id': row[3],
                'comment': row[4],
                'created_at': row[5],
                'updated_at': row[6],
                'rejection_reason': row[7]
            }
            for row in results
        ]
        
        return self.rejected_docs
    
    def fetch_pilot_info(self) -> Dict:
        """Obtiene información del piloto"""
        query = """
        SELECT 
            p._id,
            p.name,
            pwd.txt_phone,
            p.country_code_phone,
            pwd.txt_email,
            p.driver_enrollment_status_cd,
            CASE 
                WHEN p.country_code_phone = '57' THEN 'CO'
                WHEN p.country_code_phone = '52' THEN 'MX'
                WHEN p.country_code_phone = '54' THEN 'AR'
                WHEN p.country_code_phone = '593' THEN 'EC'
                WHEN p.country_code_phone = '502' THEN 'GT'
                WHEN p.country_code_phone = '505' THEN 'NI'
                WHEN p.country_code_phone = '58' THEN 'VE'
                ELSE 'UNKNOWN'
            END as country
        FROM picapmongoprod.passengers p
        LEFT JOIN picapmongoprod.passengers_w_data pwd ON p._id = pwd._id
        WHERE p._id = %(passenger_id)s
        LIMIT 1
        """
        
        result = ch_client.execute(query, {'passenger_id': self.passenger_id})
        
        if result:
            row = result[0]
            self.pilot_info = {
                'passenger_id': row[0],
                'name': row[1],
                'phone': row[2],
                'country_code': row[3],
                'email': row[4],
                'enrollment_status': row[5],
                'country': row[6]
            }
        
        return self.pilot_info
    
    def get_documents_to_explain(self) -> List[str]:
        """Retorna lista de form_keys únicos rechazados"""
        unique_forms = list(set([doc['form_key'] for doc in self.rejected_docs]))
        return unique_forms


class VoiceAgentV2:
    """Motor principal del agente de voz v2.0"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.form_mapping = config['form_key_mapping']
        self.countries = config['documents_by_country']
        
    def generate_welcome(self, pilot_name: str = None) -> str:
        """Genera mensaje de bienvenida personalizado"""
        greeting = f"Hola {pilot_name}, " if pilot_name else "Hola, "
        
        return (
            f"{greeting}bienvenido a Picap. "
            "Te habla tu asistente automático de activación. "
            "He detectado que algunos de tus documentos fueron rechazados, "
            "pero no te preocupes, voy a guiarte paso a paso para que los subas correctamente "
            "y puedas activar tu cuenta como piloto. "
            "Este proceso te tomará solo unos minutos. "
            "Presiona 1 si estás listo y tienes tus documentos a la mano, "
            "o presiona 2 si prefieres que te llamemos en otro momento."
        )
    
    def generate_rejection_context(self, rejected_docs: List[Dict]) -> str:
        """Genera contexto sobre documentos rechazados"""
        doc_names = []
        for doc in rejected_docs:
            form_key = doc['form_key']
            if form_key in self.form_mapping:
                display_name = self.form_mapping[form_key]['display_name']
                if isinstance(display_name, dict):
                    display_name = "tu documento"
                doc_names.append(display_name)
        
        unique_docs = list(set(doc_names))
        
        if len(unique_docs) == 1:
            return f"He visto que tu {unique_docs[0]} fue rechazado. "
        elif len(unique_docs) == 2:
            return f"He visto que tu {unique_docs[0]} y tu {unique_docs[1]} fueron rechazados. "
        else:
            docs_list = ", ".join(unique_docs[:-1]) + f" y tu {unique_docs[-1]}"
            return f"He visto que los siguientes documentos fueron rechazados: {docs_list}. "
    
    def generate_general_instructions(self) -> str:
        """Genera instrucciones generales de calidad"""
        return (
            "Perfecto. Antes de revisar cada documento, "
            "déjame recordarte las reglas más importantes: "
            "Uno: usa buena iluminación, preferiblemente luz natural. "
            "Dos: evita reflejos y sombras sobre los documentos. "
            "Tres: toma la foto de frente, sin inclinaciones. "
            "Cuatro: asegúrate que todo el documento esté visible, sin cortar bordes. "
            "Y cinco: NO uses capturas de pantalla, deben ser fotos originales. "
            "Si sigues estas reglas, tu proceso será aprobado rápidamente. "
            "Presiona 1 para continuar."
        )
    
    def generate_document_instructions(
        self, 
        form_key: str, 
        country_code: str,
        position: int, 
        total: int,
        rejection_comment: str = None
    ) -> str:
        """Genera instrucciones específicas para un tipo de documento"""
        
        # Buscar país
        country_docs = self.countries.get(country_code, {}).get('required_documents', [])
        
        # Buscar documento específico
        doc_config = None
        for doc in country_docs:
            if doc['form_key'] == form_key:
                doc_config = doc
                break
        
        if not doc_config:
            # Fallback genérico
            logger.warning(f"No se encontró config para {form_key} en país {country_code}")
            return f"Documento {position} de {total}. Asegúrate de seguir las instrucciones generales. "
        
        instructions = doc_config['instructions']
        
        # Intro con contador
        script = f"Documento {position} de {total}. {instructions['intro']} "
        
        # Contexto de rechazo si existe
        if rejection_comment:
            script += f"La razón del rechazo fue: {rejection_comment}. "
            script += "Presta especial atención a esto. "
        
        # Requisitos
        script += "Escucha con atención estos puntos importantes: "
        for idx, req in enumerate(instructions['requirements'], 1):
            script += f"Punto {idx}: {req}. "
        
        # Pausar
        script += "Ahora te diré los errores más comunes que debes evitar: "
        
        # Errores comunes
        for error in instructions['common_errors']:
            script += f"{error}. "
        
        # Validación automática si aplica
        if 'auto_validation' in instructions:
            script += f"Nota importante: {instructions['auto_validation']}. "
        
        # Cierre de sección
        script += (
            f"¿Quedó claro cómo debes fotografiar este documento? "
            "Presiona 1 si entendiste, o presiona 2 si necesitas que repita las instrucciones."
        )
        
        return script
    
    def generate_summary(self, documents_explained: List[str], country_code: str) -> str:
        """Genera resumen final"""
        country_name = self.countries.get(country_code, {}).get('country_name', 'tu país')
        
        return (
            f"Excelente. Hemos revisado cómo corregir tus documentos rechazados. "
            "Recuerda los puntos clave: buena iluminación, sin reflejos, "
            "documento completo y visible, y fotos originales sin edición ni capturas de pantalla. "
            f"Ahora ya puedes ingresar a la app de Picap en {country_name} "
            "y subir nuevamente tus documentos siguiendo las instrucciones que acabamos de revisar. "
            "Si sigues estos pasos, tu proceso de activación será rápido y sin contratiempos. "
            "¡Muchos éxitos como piloto de Picap! "
            "Esta llamada terminará en 3 segundos."
        )


# Almacenamiento en memoria de estado de llamadas
call_states = {}


@app.route('/voice/incoming', methods=['POST'])
def incoming_call():
    """Webhook inicial cuando entra una llamada"""
    call_sid = request.form.get('CallSid')
    from_number = request.form.get('From')
    
    logger.info(f"Nueva llamada: {call_sid} desde {from_number}")
    
    # Buscar piloto por número
    # NOTA: Aquí deberías tener el passenger_id desde tu sistema de campaña
    # Por ahora usamos un parámetro que debe venir en la URL
    passenger_id = request.args.get('passenger_id')
    
    if not passenger_id:
        logger.error("No se proporcionó passenger_id")
        response = VoiceResponse()
        response.say(
            "Lo sentimos, hubo un error al identificar tu cuenta. "
            "Por favor contacta a soporte.",
            language='es-MX',
            voice='Polly.Mia'
        )
        response.hangup()
        return Response(str(response), mimetype='text/xml')
    
    # Analizar documentos del piloto
    analyzer = DocumentAnalyzer(passenger_id)
    rejected_docs = analyzer.fetch_rejected_documents()
    pilot_info = analyzer.fetch_pilot_info()
    
    if not rejected_docs:
        response = VoiceResponse()
        response.say(
            "No hemos encontrado documentos rechazados en tu cuenta. "
            "Si necesitas ayuda, contacta a soporte.",
            language='es-MX',
            voice='Polly.Mia'
        )
        response.hangup()
        return Response(str(response), mimetype='text/xml')
    
    # Inicializar estado
    documents_to_explain = analyzer.get_documents_to_explain()
    
    call_states[call_sid] = {
        'step': 'welcome',
        'passenger_id': passenger_id,
        'pilot_info': pilot_info,
        'rejected_docs': rejected_docs,
        'documents_to_explain': documents_to_explain,
        'documents_explained': [],
        'current_doc_index': 0,
        'started_at': datetime.now().isoformat()
    }
    
    agent = VoiceAgentV2(CONFIG)
    response = VoiceResponse()
    
    # Bienvenida personalizada
    pilot_name = pilot_info.get('name', '').split()[0] if pilot_info.get('name') else None
    
    gather = Gather(
        num_digits=1,
        action='/voice/welcome-response',
        timeout=10,
        method='POST'
    )
    
    welcome_msg = agent.generate_welcome(pilot_name)
    rejection_context = agent.generate_rejection_context(rejected_docs[:3])  # Top 3
    
    gather.say(
        welcome_msg + rejection_context,
        language='es-MX',
        voice='Polly.Mia'
    )
    response.append(gather)
    
    # Si no presiona nada
    response.say(
        "No recibimos tu respuesta. Te llamaremos en otro momento. Hasta pronto.",
        language='es-MX',
        voice='Polly.Mia'
    )
    response.hangup()
    
    return Response(str(response), mimetype='text/xml')


@app.route('/voice/welcome-response', methods=['POST'])
def welcome_response():
    """Procesa respuesta de bienvenida"""
    call_sid = request.form.get('CallSid')
    digits = request.form.get('Digits')
    
    logger.info(f"Respuesta welcome: {call_sid} - Dígitos: {digits}")
    
    response = VoiceResponse()
    agent = VoiceAgentV2(CONFIG)
    
    if digits == '1':
        call_states[call_sid]['step'] = 'general_instructions'
        
        gather = Gather(
            num_digits=1,
            action='/voice/start-documents',
            timeout=10,
            method='POST'
        )
        gather.say(
            agent.generate_general_instructions(),
            language='es-MX',
            voice='Polly.Mia'
        )
        response.append(gather)
        
    elif digits == '2':
        response.say(
            "Entendido. Te llamaremos cuando sea más conveniente. Hasta pronto.",
            language='es-MX',
            voice='Polly.Mia'
        )
        response.hangup()
    else:
        response.say(
            "No reconocí tu opción. Por favor llama de nuevo. Hasta pronto.",
            language='es-MX',
            voice='Polly.Mia'
        )
        response.hangup()
    
    return Response(str(response), mimetype='text/xml')


@app.route('/voice/start-documents', methods=['POST'])
def start_documents():
    """Inicia explicación de documentos"""
    call_sid = request.form.get('CallSid')
    digits = request.form.get('Digits')
    
    if digits != '1':
        response = VoiceResponse()
        response.say(
            "No recibimos confirmación. Hasta pronto.",
            language='es-MX',
            voice='Polly.Mia'
        )
        response.hangup()
        return Response(str(response), mimetype='text/xml')
    
    call_states[call_sid]['step'] = 'explaining_document'
    call_states[call_sid]['current_doc_index'] = 0
    
    return explain_current_document(call_sid)


@app.route('/voice/document-response', methods=['POST'])
def document_response():
    """Procesa respuesta después de explicar un documento"""
    call_sid = request.form.get('CallSid')
    digits = request.form.get('Digits')
    
    state = call_states.get(call_sid)
    
    if not state:
        response = VoiceResponse()
        response.say("Error en el sistema. Hasta pronto.", language='es-MX', voice='Polly.Mia')
        response.hangup()
        return Response(str(response), mimetype='text/xml')
    
    current_index = state['current_doc_index']
    docs_to_explain = state['documents_to_explain']
    
    if digits == '1':
        # Entendió, pasar al siguiente
        state['documents_explained'].append(docs_to_explain[current_index])
        state['current_doc_index'] += 1
        
        if state['current_doc_index'] >= len(docs_to_explain):
            return finish_call(call_sid)
        else:
            return explain_current_document(call_sid)
            
    elif digits == '2':
        # Repetir instrucciones
        return explain_current_document(call_sid)
    else:
        # Opción inválida, repetir
        return explain_current_document(call_sid)


def explain_current_document(call_sid: str) -> Response:
    """Explica el documento actual según el índice"""
    state = call_states[call_sid]
    current_index = state['current_doc_index']
    docs_to_explain = state['documents_to_explain']
    total_docs = len(docs_to_explain)
    
    current_form_key = docs_to_explain[current_index]
    country_code = state['pilot_info'].get('country', 'CO')
    
    # Buscar comentario de rechazo para este documento
    rejection_comment = None
    for doc in state['rejected_docs']:
        if doc['form_key'] == current_form_key:
            rejection_comment = doc.get('comment') or doc.get('rejection_reason')
            break
    
    agent = VoiceAgentV2(CONFIG)
    response = VoiceResponse()
    
    gather = Gather(
        num_digits=1,
        action='/voice/document-response',
        timeout=15,
        method='POST'
    )
    
    script = agent.generate_document_instructions(
        current_form_key,
        country_code,
        current_index + 1,
        total_docs,
        rejection_comment
    )
    
    gather.say(script, language='es-MX', voice='Polly.Mia')
    response.append(gather)
    
    return Response(str(response), mimetype='text/xml')


def finish_call(call_sid: str) -> Response:
    """Finaliza la llamada con resumen"""
    state = call_states[call_sid]
    country_code = state['pilot_info'].get('country', 'CO')
    
    agent = VoiceAgentV2(CONFIG)
    response = VoiceResponse()
    
    summary = agent.generate_summary(state['documents_explained'], country_code)
    response.say(summary, language='es-MX', voice='Polly.Mia')
    
    response.pause(length=3)
    response.hangup()
    
    # Registrar en ClickHouse
    # TODO: Guardar en tabla voice_calls
    logger.info(f"Llamada completada: {call_sid} - {len(state['documents_explained'])} documentos explicados")
    
    return Response(str(response), mimetype='text/xml')


@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint de salud"""
    return {'status': 'healthy', 'timestamp': datetime.now().isoformat()}


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
