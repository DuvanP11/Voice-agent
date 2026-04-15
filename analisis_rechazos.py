"""
Análisis de Errores Comunes y Métricas
Basado en datos reales de ClickHouse
"""

from clickhouse_driver import Client
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List
import json


class DocumentRejectionAnalyzer:
    """Analiza patrones de rechazo de documentos"""
    
    def __init__(self):
        self.ch_client = Client(
            host='localhost',
            port=9000,
            database='picapmongoprod',
            user='default',
            password='tu_password'
        )
    
    def get_top_rejection_reasons(self, days: int = 30) -> pd.DataFrame:
        """Obtiene las razones de rechazo más comunes"""
        query = f"""
        SELECT 
            dedf.form_key as tipo_documento,
            rr.name as razon_rechazo,
            defs.comment as comentario_detalle,
            COUNT(*) as cantidad_rechazos,
            COUNT(DISTINCT defs.passenger_id) as pilotos_afectados,
            round(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY dedf.form_key), 2) as porcentaje_del_documento
        FROM picapmongoprod.driver_enrollment_document_form_solutions defs
        LEFT JOIN picapmongoprod.driver_enrollment_document_forms dedf 
            ON defs.driver_enrollment_document_form_id = dedf._id
        LEFT JOIN picapmongoprod.rejected_reasons rr 
            ON defs.rejected_reason_id = rr._id
        WHERE defs.status_cd = 3  -- Rechazado
        AND defs.created_at >= now() - INTERVAL {days} DAY
        GROUP BY tipo_documento, razon_rechazo, comentario_detalle
        ORDER BY cantidad_rechazos DESC
        LIMIT 100
        """
        
        result = self.ch_client.execute(query)
        
        df = pd.DataFrame(result, columns=[
            'tipo_documento', 'razon_rechazo', 'comentario', 
            'cantidad_rechazos', 'pilotos_afectados', 'porcentaje'
        ])
        
        return df
    
    def get_rejection_by_country(self, days: int = 30) -> pd.DataFrame:
        """Analiza rechazos por país"""
        query = f"""
        SELECT 
            CASE 
                WHEN p.country_code_phone = '57' THEN 'Colombia'
                WHEN p.country_code_phone = '52' THEN 'México'
                WHEN p.country_code_phone = '54' THEN 'Argentina'
                WHEN p.country_code_phone = '593' THEN 'Ecuador'
                WHEN p.country_code_phone = '502' THEN 'Guatemala'
                WHEN p.country_code_phone = '505' THEN 'Nicaragua'
                WHEN p.country_code_phone = '58' THEN 'Venezuela'
                ELSE 'Otro'
            END as pais,
            dedf.form_key as tipo_documento,
            COUNT(*) as total_rechazos,
            COUNT(DISTINCT defs.passenger_id) as pilotos_afectados,
            round(AVG(dateDiff('day', p.created_at, defs.created_at)), 2) as dias_promedio_hasta_rechazo
        FROM picapmongoprod.driver_enrollment_document_form_solutions defs
        JOIN picapmongoprod.passengers p ON defs.passenger_id = p._id
        LEFT JOIN picapmongoprod.driver_enrollment_document_forms dedf 
            ON defs.driver_enrollment_document_form_id = dedf._id
        WHERE defs.status_cd = 3
        AND defs.created_at >= now() - INTERVAL {days} DAY
        GROUP BY pais, tipo_documento
        ORDER BY pais, total_rechazos DESC
        """
        
        result = self.ch_client.execute(query)
        
        df = pd.DataFrame(result, columns=[
            'pais', 'tipo_documento', 'total_rechazos', 
            'pilotos_afectados', 'dias_promedio_rechazo'
        ])
        
        return df
    
    def get_repeat_offenders(self, min_rejections: int = 3) -> pd.DataFrame:
        """Identifica pilotos con múltiples rechazos (candidatos a llamada)"""
        query = f"""
        WITH rechazos_por_piloto AS (
            SELECT 
                p._id as passenger_id,
                p.name as nombre,
                pwd.txt_phone as telefono,
                p.country_code_phone as codigo_pais,
                COUNT(DISTINCT defs.driver_enrollment_document_form_id) as docs_diferentes,
                COUNT(*) as total_rechazos,
                MAX(defs.updated_at) as ultimo_rechazo,
                groupArray(dedf.form_key) as documentos_rechazados
            FROM picapmongoprod.driver_enrollment_document_form_solutions defs
            JOIN picapmongoprod.passengers p ON defs.passenger_id = p._id
            LEFT JOIN picapmongoprod.passengers_w_data pwd ON p._id = pwd._id
            LEFT JOIN picapmongoprod.driver_enrollment_document_forms dedf 
                ON defs.driver_enrollment_document_form_id = dedf._id
            WHERE defs.status_cd = 3
            AND defs.created_at >= now() - INTERVAL 14 DAY
            GROUP BY p._id, p.name, pwd.txt_phone, p.country_code_phone
            HAVING total_rechazos >= {min_rejections}
        )
        SELECT 
            passenger_id,
            nombre,
            telefono,
            codigo_pais,
            docs_diferentes,
            total_rechazos,
            toDate(ultimo_rechazo) as fecha_ultimo_rechazo,
            dateDiff('day', ultimo_rechazo, now()) as dias_desde_rechazo,
            arrayStringConcat(documentos_rechazados, ', ') as documentos
        FROM rechazos_por_piloto
        ORDER BY total_rechazos DESC, ultimo_rechazo DESC
        LIMIT 500
        """
        
        result = self.ch_client.execute(query)
        
        df = pd.DataFrame(result, columns=[
            'passenger_id', 'nombre', 'telefono', 'codigo_pais',
            'docs_diferentes', 'total_rechazos', 'fecha_ultimo_rechazo',
            'dias_desde_rechazo', 'documentos'
        ])
        
        return df
    
    def get_soat_tecno_auto_rejections(self, days: int = 7) -> pd.DataFrame:
        """Analiza rechazos automáticos de SOAT y Tecnomecánica"""
        query = f"""
        SELECT 
            p._id as passenger_id,
            p.name as nombre,
            pwd.txt_phone as telefono,
            defs.should_reject_soat_form as rechazo_soat_auto,
            defs.should_reject_tecno_form as rechazo_tecno_auto,
            defs.soat_expiration_date as fecha_vencimiento_soat,
            defs.tecnomecanica_expiration_date as fecha_vencimiento_tecno,
            defs.runt_mssg as mensaje_runt,
            defs.comment as comentario
        FROM picapmongoprod.driver_enrollment_document_form_solutions defs
        JOIN picapmongoprod.passengers p ON defs.passenger_id = p._id
        LEFT JOIN picapmongoprod.passengers_w_data pwd ON p._id = pwd._id
        WHERE (defs.should_reject_soat_form = 1 OR defs.should_reject_tecno_form = 1)
        AND defs.created_at >= now() - INTERVAL {days} DAY
        ORDER BY defs.created_at DESC
        LIMIT 200
        """
        
        result = self.ch_client.execute(query)
        
        df = pd.DataFrame(result, columns=[
            'passenger_id', 'nombre', 'telefono', 'rechazo_soat_auto',
            'rechazo_tecno_auto', 'fecha_vencimiento_soat', 
            'fecha_vencimiento_tecno', 'mensaje_runt', 'comentario'
        ])
        
        return df
    
    def generate_comprehensive_report(self, output_file: str = 'analisis_rechazos.xlsx'):
        """Genera reporte completo en Excel"""
        
        print("📊 Generando análisis completo de rechazos...")
        
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            # Sheet 1: Top razones de rechazo
            print("  → Analizando razones de rechazo...")
            top_reasons = self.get_top_rejection_reasons(days=30)
            top_reasons.to_excel(writer, sheet_name='Top Razones Rechazo', index=False)
            
            # Sheet 2: Rechazos por país
            print("  → Analizando rechazos por país...")
            by_country = self.get_rejection_by_country(days=30)
            by_country.to_excel(writer, sheet_name='Rechazos por País', index=False)
            
            # Sheet 3: Pilotos con múltiples rechazos
            print("  → Identificando pilotos con múltiples rechazos...")
            repeat_offenders = self.get_repeat_offenders(min_rejections=2)
            repeat_offenders.to_excel(writer, sheet_name='Candidatos a Llamada', index=False)
            
            # Sheet 4: Rechazos automáticos SOAT/Tecno
            print("  → Analizando rechazos automáticos...")
            auto_rejections = self.get_soat_tecno_auto_rejections(days=7)
            auto_rejections.to_excel(writer, sheet_name='Rechazos Automáticos', index=False)
            
            # Sheet 5: Resumen ejecutivo
            print("  → Generando resumen ejecutivo...")
            summary_data = {
                'Métrica': [
                    'Total Pilotos con Rechazos (14d)',
                    'Total Rechazos (30d)',
                    'Documentos Rechazados más Comunes',
                    'País con más Rechazos',
                    'Promedio Rechazos por Piloto',
                    'Rechazos Automáticos SOAT (7d)',
                    'Rechazos Automáticos Tecno (7d)'
                ],
                'Valor': [
                    len(repeat_offenders),
                    top_reasons['cantidad_rechazos'].sum(),
                    top_reasons.nlargest(3, 'cantidad_rechazos')['tipo_documento'].tolist()[0] if not top_reasons.empty else 'N/A',
                    by_country.groupby('pais')['total_rechazos'].sum().idxmax() if not by_country.empty else 'N/A',
                    round(repeat_offenders['total_rechazos'].mean(), 2) if not repeat_offenders.empty else 0,
                    auto_rejections['rechazo_soat_auto'].sum() if not auto_rejections.empty else 0,
                    auto_rejections['rechazo_tecno_auto'].sum() if not auto_rejections.empty else 0
                ]
            }
            
            pd.DataFrame(summary_data).to_excel(writer, sheet_name='Resumen Ejecutivo', index=False)
        
        print(f"✅ Reporte generado: {output_file}")
        return output_file
    
    def get_actionable_insights(self) -> Dict:
        """Genera insights accionables para el agente de voz"""
        
        # Top 5 errores más comunes
        top_reasons = self.get_top_rejection_reasons(days=30)
        
        insights = {
            'top_5_errores': [],
            'documentos_problematicos': [],
            'recomendaciones_agente': []
        }
        
        # Top 5 errores
        for _, row in top_reasons.head(5).iterrows():
            insights['top_5_errores'].append({
                'documento': row['tipo_documento'],
                'razon': row['razon_rechazo'],
                'cantidad': int(row['cantidad_rechazos']),
                'porcentaje': float(row['porcentaje'])
            })
        
        # Documentos más problemáticos
        doc_problems = top_reasons.groupby('tipo_documento')['cantidad_rechazos'].sum().nlargest(5)
        for doc, count in doc_problems.items():
            insights['documentos_problematicos'].append({
                'documento': doc,
                'total_rechazos': int(count)
            })
        
        # Recomendaciones para el agente
        if 'DriverSignupForm' in doc_problems.index:
            insights['recomendaciones_agente'].append(
                "CRÍTICO: Foto de perfil es el documento más rechazado. "
                "Enfatizar: sin filtros, sin accesorios, buena iluminación."
            )
        
        if any('blur' in str(row['comentario']).lower() for _, row in top_reasons.iterrows()):
            insights['recomendaciones_agente'].append(
                "ERROR COMÚN: Fotos borrosas. "
                "Enfatizar: mantener celular estable, buena luz, foto enfocada."
            )
        
        return insights


# Script principal
if __name__ == '__main__':
    analyzer = DocumentRejectionAnalyzer()
    
    print("=== ANÁLISIS DE RECHAZOS DE DOCUMENTOS ===\n")
    
    # Generar reporte completo
    report_file = analyzer.generate_comprehensive_report()
    
    # Obtener insights
    print("\n📋 Insights Accionables:")
    insights = analyzer.get_actionable_insights()
    
    print("\n🔴 Top 5 Errores:")
    for error in insights['top_5_errores']:
        print(f"  - {error['documento']}: {error['razon']} ({error['cantidad']} casos, {error['porcentaje']}%)")
    
    print("\n📄 Documentos Más Problemáticos:")
    for doc in insights['documentos_problematicos']:
        print(f"  - {doc['documento']}: {doc['total_rechazos']} rechazos")
    
    print("\n💡 Recomendaciones para el Agente:")
    for rec in insights['recomendaciones_agente']:
        print(f"  - {rec}")
    
    # Guardar insights en JSON
    with open('insights_rechazos.json', 'w', encoding='utf-8') as f:
        json.dump(insights, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Insights guardados en: insights_rechazos.json")
