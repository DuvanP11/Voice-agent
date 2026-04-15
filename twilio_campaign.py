"""
Script de Campaña de Llamadas Masivas
Integración con Twilio para contactar pilotos
"""

import pandas as pd
from twilio.rest import Client
import time
from datetime import datetime
import logging
from typing import List, Dict
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'call_campaign_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class TwilioCampaignManager:
    """Gestor de campañas de llamadas con Twilio"""
    
    def __init__(self):
        # Credenciales de Twilio
        self.account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        self.auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        self.twilio_number = os.getenv('TWILIO_PHONE_NUMBER')
        self.webhook_base_url = os.getenv('WEBHOOK_BASE_URL')  # ej: https://tu-dominio.com
        
        if not all([self.account_sid, self.auth_token, self.twilio_number, self.webhook_base_url]):
            raise ValueError("Faltan credenciales de Twilio en .env")
        
        self.client = Client(self.account_sid, self.auth_token)
        
    def validate_phone_number(self, phone: str) -> str:
        """Valida y formatea número de teléfono colombiano"""
        # Limpiar el número
        clean = ''.join(filter(str.isdigit, str(phone)))
        
        # Formato colombiano: +57 + 10 dígitos
        if len(clean) == 10:
            return f'+57{clean}'
        elif len(clean) == 12 and clean.startswith('57'):
            return f'+{clean}'
        elif len(clean) == 13 and clean.startswith('+57'):
            return clean
        else:
            raise ValueError(f'Número inválido: {phone}')
    
    def make_call(self, to_number: str, pilot_id: int) -> Dict:
        """Realiza una llamada individual"""
        try:
            formatted_number = self.validate_phone_number(to_number)
            
            call = self.client.calls.create(
                to=formatted_number,
                from_=self.twilio_number,
                url=f'{self.webhook_base_url}/voice/incoming',
                method='POST',
                status_callback=f'{self.webhook_base_url}/voice/status',
                status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
                status_callback_method='POST',
                record=True,  # Grabar llamada para QA
                recording_status_callback=f'{self.webhook_base_url}/voice/recording',
                timeout=30,
                machine_detection='Enable'  # Detectar contestadoras
            )
            
            logger.info(f'Llamada iniciada - SID: {call.sid} - Piloto: {pilot_id} - Número: {formatted_number}')
            
            return {
                'success': True,
                'call_sid': call.sid,
                'pilot_id': pilot_id,
                'to_number': formatted_number,
                'status': call.status,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f'Error al llamar a {to_number} (Piloto {pilot_id}): {str(e)}')
            return {
                'success': False,
                'pilot_id': pilot_id,
                'to_number': to_number,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def run_campaign(
        self, 
        pilots_df: pd.DataFrame, 
        batch_size: int = 50,
        delay_seconds: int = 2,
        max_calls: int = None
    ) -> pd.DataFrame:
        """
        Ejecuta campaña de llamadas masivas
        
        Args:
            pilots_df: DataFrame con columnas ['pilot_id', 'phone_number']
            batch_size: Llamadas por lote
            delay_seconds: Segundos entre cada llamada
            max_calls: Límite máximo de llamadas (None = sin límite)
        """
        results = []
        total_pilots = len(pilots_df)
        
        if max_calls:
            total_pilots = min(total_pilots, max_calls)
            pilots_df = pilots_df.head(max_calls)
        
        logger.info(f'Iniciando campaña: {total_pilots} pilotos a contactar')
        
        for idx, row in pilots_df.iterrows():
            pilot_id = row['pilot_id']
            phone = row['phone_number']
            
            # Realizar llamada
            result = self.make_call(phone, pilot_id)
            results.append(result)
            
            # Log de progreso
            if (idx + 1) % 10 == 0:
                success_count = sum(1 for r in results if r['success'])
                logger.info(f'Progreso: {idx + 1}/{total_pilots} - Exitosas: {success_count}')
            
            # Delay entre llamadas
            if idx < total_pilots - 1:
                time.sleep(delay_seconds)
            
            # Pausar entre lotes para evitar rate limits
            if (idx + 1) % batch_size == 0:
                logger.info(f'Lote completado. Pausando 30 segundos...')
                time.sleep(30)
        
        # Convertir resultados a DataFrame
        results_df = pd.DataFrame(results)
        
        # Resumen
        total_success = results_df['success'].sum()
        total_failed = len(results_df) - total_success
        
        logger.info(f'\n=== RESUMEN DE CAMPAÑA ===')
        logger.info(f'Total procesados: {len(results_df)}')
        logger.info(f'Exitosas: {total_success}')
        logger.info(f'Fallidas: {total_failed}')
        logger.info(f'Tasa de éxito: {total_success/len(results_df)*100:.2f}%')
        
        # Guardar resultados
        output_file = f'campaign_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        results_df.to_excel(output_file, index=False)
        logger.info(f'Resultados guardados en: {output_file}')
        
        return results_df
    
    def get_call_status(self, call_sid: str) -> Dict:
        """Consulta estado de una llamada específica"""
        try:
            call = self.client.calls(call_sid).fetch()
            return {
                'call_sid': call.sid,
                'status': call.status,
                'duration': call.duration,
                'price': call.price,
                'direction': call.direction,
                'start_time': call.start_time,
                'end_time': call.end_time
            }
        except Exception as e:
            logger.error(f'Error consultando llamada {call_sid}: {str(e)}')
            return {'error': str(e)}
    
    def get_campaign_costs(self, call_sids: List[str]) -> Dict:
        """Calcula costos totales de una campaña"""
        total_cost = 0
        total_duration = 0
        successful_calls = 0
        
        for sid in call_sids:
            try:
                call = self.client.calls(sid).fetch()
                if call.price:
                    total_cost += abs(float(call.price))
                if call.duration:
                    total_duration += int(call.duration)
                if call.status == 'completed':
                    successful_calls += 1
            except Exception as e:
                logger.error(f'Error obteniendo costos de {sid}: {str(e)}')
        
        return {
            'total_calls': len(call_sids),
            'successful_calls': successful_calls,
            'total_cost_usd': round(total_cost, 2),
            'total_duration_minutes': round(total_duration / 60, 2),
            'avg_cost_per_call': round(total_cost / len(call_sids), 4) if call_sids else 0,
            'avg_duration_seconds': round(total_duration / len(call_sids), 2) if call_sids else 0
        }


# =====================================================
# Script principal de ejecución
# =====================================================

def main():
    """Script principal para ejecutar campaña"""
    
    # 1. Cargar lista de pilotos desde CSV (exportado de ClickHouse)
    print("Cargando lista de pilotos...")
    pilots_df = pd.read_csv('pilots_to_call.csv')
    
    # Validar columnas requeridas
    required_cols = ['pilot_id', 'phone_number']
    if not all(col in pilots_df.columns for col in required_cols):
        raise ValueError(f'CSV debe contener columnas: {required_cols}')
    
    print(f"Total de pilotos cargados: {len(pilots_df)}")
    
    # 2. Filtrar números válidos
    pilots_df['phone_number'] = pilots_df['phone_number'].astype(str)
    pilots_df = pilots_df[pilots_df['phone_number'].str.len() >= 10]
    
    print(f"Pilotos con teléfono válido: {len(pilots_df)}")
    
    # 3. Inicializar gestor de campaña
    campaign = TwilioCampaignManager()
    
    # 4. Ejecutar campaña
    # IMPORTANTE: Ajustar max_calls para pruebas iniciales
    results = campaign.run_campaign(
        pilots_df=pilots_df,
        batch_size=50,      # 50 llamadas por lote
        delay_seconds=2,    # 2 segundos entre llamadas
        max_calls=100       # CAMBIAR A None para campaña completa
    )
    
    # 5. Calcular costos
    successful_sids = results[results['success']]['call_sid'].tolist()
    
    if successful_sids:
        # Esperar 30 segundos para que las llamadas se completen
        print("\nEsperando 30 segundos para consultar costos...")
        time.sleep(30)
        
        costs = campaign.get_campaign_costs(successful_sids)
        print(f"\n=== COSTOS DE CAMPAÑA ===")
        print(f"Costo total: ${costs['total_cost_usd']} USD")
        print(f"Duración total: {costs['total_duration_minutes']} minutos")
        print(f"Costo promedio: ${costs['avg_cost_per_call']} USD/llamada")
        print(f"Duración promedio: {costs['avg_duration_seconds']} segundos/llamada")


if __name__ == '__main__':
    main()
