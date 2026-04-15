"""
Verificador de Configuración para Render.com
Genera los archivos necesarios y verifica la estructura
"""

import os
import json
from pathlib import Path


class RenderConfigChecker:
    """Verifica configuración para Render.com"""
    
    def __init__(self):
        self.issues = []
        self.fixes = []
    
    def check_file_structure(self):
        """Verifica que existan todos los archivos necesarios"""
        print("\n🔍 Verificando estructura de archivos...")
        print("-" * 50)
        
        required_files = [
            'voice_agent_v2_real.py',
            'document_configs_real.json',
            'requirements.txt',
            '.env.example'
        ]
        
        for file in required_files:
            if os.path.exists(file):
                print(f"✅ {file} - Encontrado")
            else:
                print(f"❌ {file} - FALTA")
                self.issues.append(f"Falta archivo: {file}")
    
    def check_requirements(self):
        """Verifica requirements.txt"""
        print("\n🔍 Verificando requirements.txt...")
        print("-" * 50)
        
        required_packages = [
            'Flask',
            'twilio',
            'clickhouse-driver',
            'gunicorn'
        ]
        
        if os.path.exists('requirements.txt'):
            with open('requirements.txt', 'r') as f:
                content = f.read()
            
            for package in required_packages:
                if package.lower() in content.lower():
                    print(f"✅ {package} - Presente")
                else:
                    print(f"❌ {package} - FALTA")
                    self.issues.append(f"Falta paquete: {package}")
        else:
            print("❌ requirements.txt no existe")
            self.issues.append("requirements.txt no existe")
    
    def generate_render_yaml(self):
        """Genera render.yaml para configuración automática"""
        print("\n📝 Generando render.yaml...")
        print("-" * 50)
        
        render_config = """# Render.yaml - Configuración para Render.com
services:
  - type: web
    name: picap-voice-agent
    env: python
    plan: starter
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn voice_agent_v2_real:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
    envVars:
      - key: PYTHON_VERSION
        value: 3.9.0
      - key: FLASK_ENV
        value: production
      - key: CLICKHOUSE_HOST
        sync: false
      - key: CLICKHOUSE_PORT
        value: 9000
      - key: CLICKHOUSE_USER
        sync: false
      - key: CLICKHOUSE_PASSWORD
        sync: false
      - key: TWILIO_ACCOUNT_SID
        sync: false
      - key: TWILIO_AUTH_TOKEN
        sync: false
      - key: TWILIO_PHONE_NUMBER
        sync: false
"""
        
        with open('render.yaml', 'w') as f:
            f.write(render_config)
        
        print("✅ render.yaml generado")
        self.fixes.append("Generado render.yaml")
    
    def generate_procfile(self):
        """Genera Procfile alternativo"""
        print("\n📝 Generando Procfile...")
        print("-" * 50)
        
        procfile_content = """web: gunicorn voice_agent_v2_real:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120 --log-file -
"""
        
        with open('Procfile', 'w') as f:
            f.write(procfile_content)
        
        print("✅ Procfile generado")
        self.fixes.append("Generado Procfile")
    
    def generate_runtime_txt(self):
        """Genera runtime.txt para especificar versión de Python"""
        print("\n📝 Generando runtime.txt...")
        print("-" * 50)
        
        with open('runtime.txt', 'w') as f:
            f.write('python-3.9.18\n')
        
        print("✅ runtime.txt generado")
        self.fixes.append("Generado runtime.txt")
    
    def check_main_file(self):
        """Verifica que el archivo principal esté correcto"""
        print("\n🔍 Verificando archivo principal...")
        print("-" * 50)
        
        if os.path.exists('voice_agent_v2_real.py'):
            with open('voice_agent_v2_real.py', 'r') as f:
                content = f.read()
            
            # Verificar imports críticos
            critical_imports = [
                'from flask import Flask',
                'from twilio.twiml.voice_response import VoiceResponse',
                'app = Flask(__name__)'
            ]
            
            for imp in critical_imports:
                if imp in content:
                    print(f"✅ {imp}")
                else:
                    print(f"❌ Falta: {imp}")
                    self.issues.append(f"Falta import: {imp}")
            
            # Verificar que tenga if __name__ == '__main__'
            if "if __name__ == '__main__':" in content:
                print("✅ Tiene punto de entrada")
            else:
                print("⚠️ Falta punto de entrada __main__")
                self.issues.append("Falta punto de entrada")
        else:
            print("❌ voice_agent_v2_real.py no existe")
            self.issues.append("Archivo principal no existe")
    
    def generate_simple_test_app(self):
        """Genera app Flask simple para testing"""
        print("\n📝 Generando app de prueba simple...")
        print("-" * 50)
        
        test_app = """# test_app.py - App simple para verificar Render
from flask import Flask, jsonify
from datetime import datetime

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        'status': 'ok',
        'message': 'Picap Voice Agent - Test App',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
"""
        
        with open('test_app.py', 'w') as f:
            f.write(test_app)
        
        print("✅ test_app.py generado")
        print("\n💡 Para probar deployment básico en Render:")
        print("   1. Cambia el Start Command a: gunicorn test_app:app")
        print("   2. Haz deploy")
        print("   3. Si funciona, cambia de vuelta a voice_agent_v2_real:app")
        
        self.fixes.append("Generado test_app.py para debugging")
    
    def generate_env_example(self):
        """Genera .env.example con todas las variables necesarias"""
        print("\n📝 Generando .env.example actualizado...")
        print("-" * 50)
        
        env_content = """# ClickHouse Configuration
CLICKHOUSE_HOST=your_clickhouse_host
CLICKHOUSE_PORT=9000
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=your_password
CLICKHOUSE_DATABASE=picapmongoprod

# Twilio Configuration
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+57XXXXXXXXXX

# Flask Configuration
FLASK_ENV=production
SECRET_KEY=your_secret_key_here

# Render Configuration
PORT=10000
"""
        
        with open('.env.example', 'w') as f:
            f.write(env_content)
        
        print("✅ .env.example generado")
        self.fixes.append("Generado .env.example")
    
    def generate_summary_report(self):
        """Genera reporte final"""
        print("\n" + "=" * 50)
        print("📊 REPORTE FINAL")
        print("=" * 50)
        
        if self.issues:
            print(f"\n❌ Problemas encontrados ({len(self.issues)}):")
            for issue in self.issues:
                print(f"   • {issue}")
        else:
            print("\n✅ No se encontraron problemas")
        
        if self.fixes:
            print(f"\n🔧 Correcciones aplicadas ({len(self.fixes)}):")
            for fix in self.fixes:
                print(f"   • {fix}")
        
        print("\n" + "=" * 50)
        print("📋 PASOS PARA DEPLOYAR EN RENDER")
        print("=" * 50)
        
        print("""
1. CONFIGURACIÓN EN RENDER DASHBOARD:
   • Build Command: pip install -r requirements.txt
   • Start Command: gunicorn voice_agent_v2_real:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
   • Environment: Python 3

2. VARIABLES DE ENTORNO (en Render Dashboard):
   • CLICKHOUSE_HOST
   • CLICKHOUSE_PORT
   • CLICKHOUSE_USER
   • CLICKHOUSE_PASSWORD
   • TWILIO_ACCOUNT_SID
   • TWILIO_AUTH_TOKEN
   • TWILIO_PHONE_NUMBER

3. VERIFICAR:
   • Que el repositorio esté actualizado en GitHub
   • Que todos los archivos estén commiteados
   • Que Render esté conectado al repo correcto

4. HACER DEPLOY:
   • Push a GitHub
   • Render detectará cambios y hará auto-deploy
   • Revisar logs en Render Dashboard

5. PROBAR:
   • Visitar: https://tu-app.onrender.com/health
   • Debe retornar JSON con status: healthy
""")
        
        # Generar archivo de instrucciones
        with open('DEPLOYMENT_INSTRUCTIONS.md', 'w') as f:
            f.write(self.generate_deployment_instructions())
        
        print("✅ Instrucciones guardadas en: DEPLOYMENT_INSTRUCTIONS.md")
    
    def generate_deployment_instructions(self):
        """Genera instrucciones detalladas de deployment"""
        return """# Instrucciones de Deployment - Render.com

## 1. Preparación del Repositorio

### Archivos necesarios:
- [x] voice_agent_v2_real.py
- [x] document_configs_real.json
- [x] requirements.txt
- [x] Procfile
- [x] render.yaml (opcional)
- [x] runtime.txt

### Commit y Push:
```bash
git add .
git commit -m "Deploy: Agente de voz configurado"
git push origin main
```

## 2. Configuración en Render

### 2.1 Crear Web Service:
1. Ir a https://dashboard.render.com
2. Click "New" → "Web Service"
3. Conectar repositorio de GitHub
4. Seleccionar el repo correcto

### 2.2 Configurar Build & Deploy:
```
Name: picap-voice-agent
Environment: Python 3
Branch: main
Root Directory: (dejar vacío)
Build Command: pip install -r requirements.txt
Start Command: gunicorn voice_agent_v2_real:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
```

### 2.3 Agregar Variables de Entorno:
```
CLICKHOUSE_HOST = your_host
CLICKHOUSE_PORT = 9000
CLICKHOUSE_USER = default
CLICKHOUSE_PASSWORD = your_password
CLICKHOUSE_DATABASE = picapmongoprod

TWILIO_ACCOUNT_SID = ACxxxxx...
TWILIO_AUTH_TOKEN = your_token
TWILIO_PHONE_NUMBER = +57XXXXX

FLASK_ENV = production
```

### 2.4 Seleccionar Plan:
- Plan: Starter (gratis)
- Instance Type: Web Service

## 3. Deploy

Click "Create Web Service" y esperar deployment.

## 4. Verificación

### 4.1 Verificar que el servicio esté corriendo:
```bash
curl https://tu-app.onrender.com/health
```

Respuesta esperada:
```json
{
  "status": "healthy",
  "timestamp": "2025-04-15T..."
}
```

### 4.2 Ver logs en tiempo real:
- En Render Dashboard → Logs
- Buscar: "Running on http://0.0.0.0:10000"

## 5. Troubleshooting

### Error: "Application failed to respond"
**Solución:**
- Verificar que el Start Command esté correcto
- Verificar que voice_agent_v2_real.py exista
- Revisar logs para ver error específico

### Error: "Module not found"
**Solución:**
- Verificar requirements.txt
- Agregar módulo faltante
- Rebuild

### Error: "Port binding failed"
**Solución:**
- Asegurarse que la app use: `port = int(os.environ.get('PORT', 5000))`
- En Render el puerto se pasa via variable PORT

## 6. Próximos Pasos

Una vez el servicio esté corriendo:

1. Copiar la URL de Render (ej: https://picap-voice-agent.onrender.com)
2. Configurar webhooks en Twilio
3. Ejecutar prueba de llamada
4. Lanzar campaña piloto

---

**Última actualización:** 2025-04-15
"""
    
    def run_all_checks(self):
        """Ejecuta todos los checks y genera archivos"""
        print("=" * 50)
        print("🔧 VERIFICADOR DE CONFIGURACIÓN - RENDER.COM")
        print("=" * 50)
        
        self.check_file_structure()
        self.check_requirements()
        self.check_main_file()
        
        print("\n" + "=" * 50)
        print("🛠️ GENERANDO ARCHIVOS DE CONFIGURACIÓN")
        print("=" * 50)
        
        self.generate_render_yaml()
        self.generate_procfile()
        self.generate_runtime_txt()
        self.generate_env_example()
        self.generate_simple_test_app()
        
        self.generate_summary_report()
        
        print("\n✅ Verificación completada")
        print("\n💡 Próximo paso: Ejecutar diagnostic_tool.py con tu URL de Render")


if __name__ == '__main__':
    checker = RenderConfigChecker()
    checker.run_all_checks()
