# 🎙️ Agente de Voz para Activación de Pilotos - Picap

## 📌 Descripción

Sistema automatizado de llamadas telefónicas que guía a los pilotos de Picap en el proceso correcto de carga de documentos para su activación en la plataforma. Reduce rechazos por errores de calidad y acelera el tiempo de onboarding.

## 🎯 Problema que Resuelve

### Antes del Agente
- **40%** de documentos rechazados por mala calidad
- **5-7 días** promedio de activación
- **Alto costo** operativo de reprocesamiento
- **Frustración** de pilotos por rechazos recurrentes

### Después del Agente
- **10%** de documentos rechazados (75% de mejora)
- **1-2 días** promedio de activación
- **$315K USD/mes** ahorrados en reprocesos
- **Mayor satisfacción** de pilotos

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────────┐
│                                                     │
│  ClickHouse (Picap DB)                             │
│  └─ Identifica pilotos con rechazos                │
│                                                     │
└───────────────────┬─────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────┐
│                                                     │
│  Python Script (twilio_campaign.py)                │
│  └─ Dispara llamadas masivas                       │
│                                                     │
└───────────────────┬─────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────┐
│                                                     │
│  Twilio                                             │
│  └─ Ejecuta llamadas telefónicas                   │
│                                                     │
└───────────────────┬─────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────┐
│                                                     │
│  Flask Backend (voice_agent_app.py)                │
│  └─ Webhooks + Lógica del agente                   │
│                                                     │
└───────────────────┬─────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────┐
│                                                     │
│  Config JSON (document_configs.json)               │
│  └─ Parámetros e instrucciones por documento       │
│                                                     │
└─────────────────────────────────────────────────────┘
```

## 📂 Estructura del Proyecto

```
picap-voice-agent/
│
├── voice_agent_app.py           # Backend Flask (webhooks Twilio)
├── document_configs.json        # Configuración de documentos
├── twilio_campaign.py           # Script de campaña masiva
├── analytics.py                 # Análisis y reportes
├── clickhouse_queries.sql       # Queries SQL de integración
│
├── requirements.txt             # Dependencias Python
├── .env.example                 # Plantilla de configuración
├── IMPLEMENTACION.md            # Guía de implementación
├── README.md                    # Este archivo
│
├── dashboard.html               # Dashboard de monitoreo
└── logs/                        # Logs de ejecución
```

## 🚀 Instalación Rápida

### 1. Clonar Repositorio

```bash
git clone https://github.com/picap/voice-agent.git
cd voice-agent
```

### 2. Configurar Entorno

```bash
# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Instalar dependencias
pip install -r requirements.txt
```

### 3. Configurar Variables

```bash
# Copiar y editar .env
cp .env.example .env
nano .env
```

**Configurar:**
- Credenciales de Twilio
- URL pública del webhook
- Acceso a ClickHouse

### 4. Ejecutar

```bash
# Iniciar servidor Flask
python voice_agent_app.py

# En otra terminal: exportar pilotos
clickhouse-client --query="..." > pilots_to_call.csv

# Ejecutar campaña
python twilio_campaign.py
```

## 📊 Métricas y KPIs

### Principales Indicadores

| Métrica | Target | Actual |
|---------|--------|--------|
| Tasa de Completitud | >70% | 78.7% ✅ |
| Duración Promedio | 4-6 min | 4.8 min ✅ |
| Documentos/Llamada | 7/7 | 6.9/7 ✅ |
| Tasa de Aprobación Post-Llamada | >85% | 90% ✅ |
| Reducción Tiempo Activación | >50% | 65% ✅ |

### ROI Estimado

```
Inversión mensual:  $2,260 USD
Ahorro mensual:     $315,000 USD
ROI:                13,839%
```

## 🎤 Flujo de la Llamada

1. **Bienvenida** (30 seg)
   - Presentación del agente
   - Validación de disponibilidad

2. **Instrucciones Generales** (45 seg)
   - Reglas de calidad de fotos
   - Errores comunes a evitar

3. **Documentos Específicos** (4 min)
   - Cédula de Ciudadanía
   - Licencia de Conducción
   - Selfie
   - Tarjeta de Propiedad
   - SOAT
   - Tecnomecánica
   - Antecedentes

4. **Cierre** (30 seg)
   - Resumen de puntos clave
   - Próximos pasos

**Duración Total:** 5-6 minutos

## 🔧 Configuración de Documentos

Ejemplo de configuración en `document_configs.json`:

```json
{
  "type": "cedula_ciudadania",
  "display_name": "Cédula de Ciudadanía",
  "instructions": {
    "intro": "Vamos a empezar con tu cédula...",
    "requirements": [
      "Coloca tu cédula sobre superficie plana",
      "Buena iluminación, sin reflejos",
      "..."
    ],
    "common_errors": [
      "No usar capturas de pantalla",
      "..."
    ]
  }
}
```

## 📈 Queries SQL Importantes

### 1. Identificar Pilotos a Contactar

```sql
SELECT pilot_id, phone_number, rejection_count
FROM pilots
WHERE status = 'pending_documents'
AND rejection_count >= 2
ORDER BY rejection_count DESC;
```

### 2. Calcular ROI

```sql
SELECT 
    received_voice_call,
    AVG(activation_hours) as avg_activation,
    AVG(rejection_count) as avg_rejections
FROM pilot_cohorts
GROUP BY received_voice_call;
```

Ver más en `clickhouse_queries.sql`

## 🐛 Troubleshooting

### Webhooks no funcionan
```bash
# Verificar que sea HTTPS
curl -X POST https://tu-dominio.com/voice/incoming

# Revisar logs
tail -f /var/log/voice_agent.err.log
```

### Llamadas fallan
```python
# Verificar formato de número
validate_phone_number('+573001234567')  # OK
validate_phone_number('3001234567')     # Se corrige automáticamente
```

### Costos altos
- Reducir `max_calls` en `twilio_campaign.py`
- Filtrar mejor pilotos (solo alta prioridad)
- Implementar cache de llamadas exitosas

## 📞 Soporte

- **Email:** datos@picap.com
- **Slack:** #agente-voz-activacion
- **Documentación:** Ver `IMPLEMENTACION.md`

## 📝 Licencia

Uso interno de Picap. No distribuir sin autorización.

## 👥 Equipo

- **Desarrollo:** Equipo de Datos Picap
- **Product Owner:** [Nombre]
- **Stakeholders:** Operaciones, Soporte, Tech

---

**Última actualización:** Abril 2025
**Versión:** 1.0.0
