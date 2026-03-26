import os
import requests
import urllib3
from bs4 import BeautifulSoup
from datetime import datetime

# Desactivamos los avisos de seguridad por el certificado de la web
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CONFIGURACIÓN DE SECRETOS (GitHub) ---
TOKEN = os.getenv('TELEGRAM_TOKEN')
MY_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
USER_NEMO = os.getenv('NEMO_USER')
PASS_NEMO = os.getenv('NEMO_PASS')

AVISADOS_FILE = "avisados.txt"

def bot_send(mensaje):
    """Envía un mensaje a tu Telegram"""
    if not TOKEN or not MY_CHAT_ID:
        print("❌ Error: Faltan los secretos de Telegram en GitHub.")
        return
    
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": MY_CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}
    try:
        r = requests.post(url, json=payload)
        if r.status_code == 200:
            print("✅ Mensaje enviado a Telegram correctamente.")
        else:
            print(f"❌ Error Telegram: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"❌ Error de conexión con Telegram: {e}")

def get_nemo_data():
    """Entra en NemoPilots y saca la tabla de barcos"""
    print("--- INICIANDO FASE DE ACCESO ---")
    session = requests.Session()
    session.verify = False 
    
    login_url = "https://nemopilots.com/login"
    login_check_url = "https://nemopilots.com/login_check"
    
    try:
        # 1. Obtener el Token CSRF de la pantalla de entrada
        print("Paso 1: Capturando token de seguridad...")
        first_page = session.get(login_url, verify=False)
        soup_init = BeautifulSoup(first_page.text, 'html.parser')
        
        csrf_token = ""
        token_input = soup_init.find('input', {'name': '_csrf_token'})
        if token_input:
            csrf_token = token_input.get('value')
            print("Token capturado.")
        else:
            print("⚠️ No se encontró el token, intentando login directo...")

        # 2. Hacer el Login Real
        print(f"Paso 2: Intentando login como {USER_NEMO}...")
        payload = {
            '_username': USER_NEMO, 
            '_password': PASS_NEMO,
            '_csrf_token': csrf_token
        }
        session.post(login_check_url, data=payload, verify=False)
        
        # 3. Acceder a la planificación
        print("Paso 3: Cargando tabla de planificación...")
        res = session.get("https://nemopilots.com/planificacion/", verify=False)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        titulo = soup.title.string.strip() if soup.title else ""
        print(f"Página cargada: {titulo}")

        if "Planificación" not in titulo:
            print("❌ ERROR: No se ha podido entrar en la zona privada. Revisa usuario/pass.")
            return []

        # 4. Procesar las tablas
        barcos = []
        tablas = soup.find_all('table')
        print(f"Se han encontrado {len(tablas)} tablas.")

        for i, t in enumerate(tablas):
            filas = t.find_all('tr')
            if len(filas) > 1:
                print(f"Extrayendo datos de la tabla {i+1} ({len(filas)} filas)...")
                for f in filas[1:]: # Saltamos cabecera
                    cols = f.find_all('td')
                    if len(cols) > 13:
                        barcos.append({
                            'eta_str': cols[0].get_text(strip=True),
                            'nombre': cols[3].get_text(strip=True),
                            'muelle': cols[11].get_text(strip=True),
                            'operacion': cols[13].get_text(strip=True),
                            'consignatario': cols[9].get_text(strip=True)
                        })
        return barcos

    except Exception as e:
        print(f"❌ Error en el proceso: {e}")
        return []

def monitor_automatico():
    data = get_nemo_data()
    if not data:
        print("No hay barcos nuevos o no se pudo leer la tabla.")
        return

    # Gestionar memoria (quién ha sido avisado ya)
    avisados = set()
    if os.path.exists(AVISADOS_FILE):
        with open(AVISADOS_FILE, "r") as f:
            avisados = set(f.read().splitlines())

    for b in data:
        id_unico = f"{b['nombre']
