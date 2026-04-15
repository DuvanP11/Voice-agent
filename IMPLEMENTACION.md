# GUÍA DE IMPLEMENTACIÓN - AGENTE DE VOZ PICAP

## 📋 TABLA DE CONTENIDOS
1. [Configuración Inicial](#configuración-inicial)
2. [Configuración de Twilio](#configuración-de-twilio)
3. [Despliegue del Backend](#despliegue-del-backend)
4. [Integración con ClickHouse](#integración-con-clickhouse)
5. [Ejecución de Campañas](#ejecución-de-campañas)
6. [Monitoreo y Métricas](#monitoreo-y-métricas)
7. [Troubleshooting](#troubleshooting)

---

## 1. CONFIGURACIÓN INICIAL

### Requisitos Previos
- Python 3.9+
- Cuenta de Twilio (con créditos)
- Acceso a ClickHouse de Picap
- Servidor con IP pública (para webhooks)

### Instalación de Dependencias

```bash
# Clonar proyecto
cd /ruta/del/proyecto

# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Instalar dependencias
pip install -r requirements.txt
```

### Configurar Variables de Entorno

```bash
# Copiar archivo de ejemplo
cp .env.example .env

# Editar con tus credenciales reales
nano .env
```

**Variables críticas:**
- `TWILIO_ACCOUNT_SID`: Obtener de Twilio Console
- `TWILIO_AUTH_TOKEN`: Obtener de Twilio Console
- `TWILIO_PHONE_NUMBER`: Número de Twilio (formato: +57XXXXXXXXXX)
- `WEBHOOK_BASE_URL`: URL pública de tu servidor

---

## 2. CONFIGURACIÓN DE TWILIO

### Paso 1: Crear Cuenta en Twilio
1. Ir a https://www.twilio.com/
2. Crear cuenta (trial o paid)
3. Verificar email y número de teléfono

### Paso 2: Obtener Número de Teléfono
1. En Twilio Console → Phone Numbers → Buy a Number
2. Buscar número colombiano (+57)
3. Verificar que tenga capacidad de VOICE
4. Comprar número

### Paso 3: Configurar Webhooks
1. En Phone Numbers → Manage → Active Numbers
2. Seleccionar tu número
3. En "Voice & Fax" → Configure:
   - **A CALL COMES IN**: Webhook → `https://tu-dominio.com/voice/incoming`
   - **METHOD**: HTTP POST
   - **STATUS CALLBACK URL**: `https://tu-dominio.com/voice/status`

### Costos Estimados (Twilio)
- Número telefónico: ~$1 USD/mes
- Llamada saliente Colombia: ~$0.015 USD/minuto
- **Ejemplo**: 1000 llamadas de 5 min = $75 USD

---

## 3. DESPLIEGUE DEL BACKEND

### Opción A: Desarrollo Local (con ngrok)

```bash
# Instalar ngrok
# Descargar de: https://ngrok.com/download

# Ejecutar Flask
python voice_agent_app.py

# En otra terminal, exponer con ngrok
ngrok http 5000

# Copiar URL de ngrok (ej: https://xxxx-xx-xx.ngrok.io)
# Actualizar WEBHOOK_BASE_URL en .env y en Twilio Console
```

### Opción B: Producción (con Gunicorn)

```bash
# Ejecutar con Gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 voice_agent_app:app

# Con supervisor para auto-restart
sudo apt-get install supervisor

# Crear config en /etc/supervisor/conf.d/voice_agent.conf
[program:voice_agent]
command=/ruta/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 voice_agent_app:app
directory=/ruta/del/proyecto
user=tu_usuario
autostart=true
autorestart=true
stderr_logfile=/var/log/voice_agent.err.log
stdout_logfile=/var/log/voice_agent.out.log
```

### Opción C: Docker

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "voice_agent_app:app"]
```

```bash
# Construir y ejecutar
docker build -t voice-agent .
docker run -d -p 5000:5000 --env-file .env voice-agent
```

### Nginx como Reverse Proxy

```nginx
server {
    listen 80;
    server_name tu-dominio.com;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

**IMPORTANTE:** Twilio requiere HTTPS. Usar Let's Encrypt:

```bash
sudo apt-get install certbot python3-certbot-nginx
sudo certbot --nginx -d tu-dominio.com
```

---

## 4. INTEGRACIÓN CON CLICKHOUSE

### Crear Tabla de Llamadas

```sql
-- Conectar a ClickHouse
clickhouse-client --host localhost --user default --password 'tu_password'

-- Crear tabla
CREATE TABLE IF NOT EXISTS voice_calls (
    call_sid String,
    pilot_id UInt32,
    phone_number String,
    status Enum8('initiated'=1, 'ringing'=2, 'in_progress'=3, 'completed'=4, 'failed'=5),
    duration_seconds UInt32,
    documents_explained Array(String),
    call_recording_url String,
    created_at DateTime DEFAULT now(),
    completed_at Nullable(DateTime)
) ENGINE = MergeTree()
ORDER BY (created_at, pilot_id);
```

### Exportar Lista de Pilotos a Contactar

```bash
# Ejecutar query desde archivo
clickhouse-client --host localhost --user default --password 'tu_password' \
  --database picapmongoprod \
  --query="$(cat clickhouse_queries.sql | grep -A 50 'EXPORTAR LISTA')" \
  --format CSVWithNames > pilots_to_call.csv
```

### Automatizar Extracción Diaria

```bash
# Crear script exportar_pilotos.sh
#!/bin/bash
DATE=$(date +%Y%m%d)
clickhouse-client --host localhost --user default --password 'tu_password' \
  --database picapmongoprod \
  --query="SELECT pilot_id, phone_number, full_name 
           FROM pilots 
           WHERE status='pending_documents' 
           AND created_at >= today() - 7" \
  --format CSVWithNames > "pilots_${DATE}.csv"

# Dar permisos
chmod +x exportar_pilotos.sh

# Agregar a crontab (ejecutar diariamente a las 8am)
crontab -e
# Agregar línea:
0 8 * * * /ruta/exportar_pilotos.sh
```

---

## 5. EJECUCIÓN DE CAMPAÑAS

### Prueba Inicial (Modo Test)

```python
# Editar twilio_campaign.py línea ~300
max_calls=5  # Solo 5 llamadas de prueba

# Ejecutar
python twilio_campaign.py
```

### Campaña Completa

```python
# En twilio_campaign.py cambiar:
max_calls=None  # Sin límite

# Ejecutar
python twilio_campaign.py

# Monitorear logs
tail -f call_campaign_YYYYMMDD.log
```

### Programar Campaña Diaria

```bash
# Crear script launch_campaign.sh
#!/bin/bash
source /ruta/venv/bin/activate
cd /ruta/del/proyecto
python twilio_campaign.py

# Crontab (ejecutar lunes a viernes a las 10am)
0 10 * * 1-5 /ruta/launch_campaign.sh
```

### Parámetros Ajustables

En `twilio_campaign.py`:

```python
results = campaign.run_campaign(
    pilots_df=pilots_df,
    batch_size=50,      # Llamadas por lote antes de pausar
    delay_seconds=2,    # Delay entre llamadas (evitar rate limit)
    max_calls=1000      # Límite diario
)
```

---

## 6. MONITOREO Y MÉTRICAS

### Dashboard en Tiempo Real

```bash
# Ejecutar analytics.py
python analytics.py

# Salida:
=== REPORTE DE AGENTE DE VOZ ===
Total de llamadas (7d): 1500
Tasa de completitud: 78.5%
Duración promedio: 287 segundos
...
```

### Generar Reporte Excel

```python
from analytics import VoiceAgentAnalytics

analytics = VoiceAgentAnalytics()
analytics.generate_daily_report(output_file='reporte_diario.xlsx')
analytics.close()
```

### Métricas Clave a Monitorear

1. **Tasa de Completitud**: > 70% es bueno
2. **Duración Promedio**: 4-6 minutos ideal
3. **Documentos por Llamada**: Objetivo 7 (todos)
4. **Tasa de Aprobación Post-Llamada**: > 85%
5. **Tiempo a Activación**: Reducción > 50%

### Alertas Automáticas

```python
# Agregar en analytics.py
def check_alerts():
    completion = get_call_completion_rate(days=1)
    
    if completion['completion_rate'] < 60:
        send_slack_alert(f"⚠️ Tasa de completitud baja: {completion['completion_rate']}%")
    
    if completion['avg_duration_seconds'] < 180:
        send_slack_alert(f"⚠️ Duración muy corta: {completion['avg_duration_seconds']}s")
```

---

## 7. TROUBLESHOOTING

### Problema: Webhooks no funcionan

**Síntomas**: Llamadas se cuelgan, no hay respuesta del agente

**Solución**:
1. Verificar que `WEBHOOK_BASE_URL` sea HTTPS
2. Verificar que el servidor esté accesible públicamente
3. Revisar logs de Flask: `tail -f /var/log/voice_agent.err.log`
4. Probar webhook manualmente:
   ```bash
   curl -X POST https://tu-dominio.com/voice/incoming \
     -d "CallSid=TEST123" \
     -d "From=+573001234567"
   ```

### Problema: Llamadas no se completan

**Síntomas**: Status = 'failed' o 'no-answer'

**Posibles causas**:
1. Número inválido → Verificar formato (+57XXXXXXXXXX)
2. Número bloqueado → Revisar en Twilio Console
3. Horario inadecuado → Llamar entre 9am-8pm
4. Rate limit de Twilio → Reducir `batch_size`

### Problema: Audio no se escucha bien

**Síntomas**: Usuarios reportan que no entienden

**Solución**:
1. Cambiar voz en `voice_agent_app.py`:
   ```python
   voice='Polly.Lupe'  # Otra voz femenina
   # o
   voice='Polly.Miguel'  # Voz masculina
   ```
2. Ajustar velocidad:
   ```python
   gather.say(text, language='es-MX', voice='Polly.Mia')
   gather.pause(length=1)  # Agregar pausas
   ```

### Problema: Costos muy altos

**Síntomas**: Gasto mayor al esperado

**Optimización**:
1. Reducir `max_calls` diario
2. Filtrar mejor pilotos (solo alta prioridad)
3. Implementar cache de llamadas exitosas
4. Evitar rellamadas innecesarias

### Problema: Base de datos lenta

**Síntomas**: Queries de ClickHouse tardan mucho

**Solución**:
1. Agregar índices:
   ```sql
   ALTER TABLE pilot_documents 
   ADD INDEX idx_status (status) TYPE set(0) GRANULARITY 4;
   ```
2. Usar PREWHERE en lugar de WHERE
3. Particionar por fecha:
   ```sql
   PARTITION BY toYYYYMM(created_at)
   ```

---

## 8. CHECKLIST PRE-LANZAMIENTO

- [ ] Twilio configurado y con saldo
- [ ] Webhooks apuntando a HTTPS
- [ ] Base de datos creada y accesible
- [ ] Variables de entorno configuradas
- [ ] Prueba de 5 llamadas exitosa
- [ ] Logs funcionando correctamente
- [ ] Monitoreo configurado
- [ ] Alertas configuradas
- [ ] Backup de configuración
- [ ] Documentación entregada al equipo

---

## 9. ESTIMACIÓN DE ROI

### Costos

| Item | Costo Mensual |
|------|---------------|
| Twilio (1000 llamadas/día × 5min) | $2,250 USD |
| Servidor (2GB RAM) | $10 USD |
| Desarrollo inicial | $0 (ya incluido) |
| **TOTAL** | **$2,260 USD/mes** |

### Beneficios

Asumiendo:
- 1000 pilotos contactados/día
- 7 documentos promedio/piloto
- 40% de rechazo sin llamada
- 10% de rechazo con llamada
- Costo operativo de reproceso: $5 USD/documento rechazado

**Rechazos evitados por día:**
- Sin agente: 1000 × 7 × 0.40 = 2,800 documentos rechazados
- Con agente: 1000 × 7 × 0.10 = 700 documentos rechazados
- **Diferencia: 2,100 rechazos evitados/día**

**Ahorro mensual:**
- 2,100 × 30 días × $5 = **$315,000 USD ahorrados**

**ROI = ($315,000 - $2,260) / $2,260 × 100 = 13,839%**

---

## CONTACTO Y SOPORTE

Para preguntas o problemas:
- Equipo de Datos Picap
- Email: datos@picap.com
- Slack: #agente-voz-activacion
