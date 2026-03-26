import os
import requests
import urllib3
import time
from bs4 import BeautifulSoup
from datetime import datetime

# Desactivar avisos de seguridad SSL por el fallo de la web
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CONFIGURACIÓN DE SECRETOS ---
TOKEN = os.getenv('TELEGRAM_TOKEN')
USER_NEMO = os.getenv('NEMO_USER')
PASS_NEMO = os.getenv('NEMO_PASS')
MY_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

AVISADOS_FILE = "avisados.txt"

def bot_send(chat_id, mensaje):
    if not chat_id: return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": mensaje, "parse_mode": "Markdown"}
    try:
        r = requests.post(url, json=payload)
        print(f"Estado envío Telegram: {r.status_code}")
    except Exception as e:
        print(f"Error enviando Telegram: {e}")

def get_nemo_data():
    print("--- INICIANDO FASE DE ACCESO ---")
    session = requests.Session()
    session.verify = False 
    
    login_url = "https://nemopilots.com/login"
    login_check_url = "https://nemopilots.com/login_check"
    
    try:
        # 1. Obtener el Token CSRF
        print("Paso 1: Capturando token de seguridad...")
        first_page = session.get(login_url, verify=False)
        soup_init = BeautifulSoup(first_page.text, 'html.parser')
        
        csrf_token = ""
        token_input = soup_init.find('input', {'name': '_csrf_token'})
        if token_input:
            csrf_token = token_input.get('value')
            print("Token capturado.")
        
        # 2. Hacer el Login
        print(f"Paso 2: Login con usuario {USER_NEMO}...")
        payload = {'_username': USER_NEMO, '_password': PASS_NEMO, '_csrf_token': csrf_token}
        session.post(login_check_url, data=payload, verify=False)
        
        # 3. Leer la Planificación
        print("Paso 3: Leyendo tablas de barcos...")
        res = session.get("https://nemopilots.com/planificacion/", verify=False)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        barcos = []
        tablas = soup.find_all('table')
        print(f"Se han encontrado {len(tablas)} tablas en total.")

        for i, t in enumerate(tablas):
            filas = t.find_all('tr')
            if len(filas) > 1:
                print(f"Analizando Tabla {i+1}...")
                for f in filas[1:]:
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
        print(f"Error: {e}")
        return []

def monitor_automatico():
    data = get_nemo_data()
    if not data:
        print("No se encontraron datos. Revisando si es por el login...")
        return

    avisados = set()
    if os.path.exists(AVISADOS_FILE):
        with open(AVISADOS_FILE, "r") as f:
            avisados = set(f.read().splitlines())

    for b in data:
        # AQUÍ HEMOS CORREGIDO EL ERROR DE SINTAXIS (Cerrando bien el f-string)
        id_unico = f"{b['nombre']}-{b['eta_str']}"
        
        if id_unico not in avisados:
            print(f"¡Nuevo barco! Avisando de: {b['nombre']}")
            mensaje = (f"🔔 **NUEVA ENTRADA DETECTADA**\n\n"
                       f"🚢 *Buque:* {b['nombre']}\n"
                       f"📅 *ETA:* {b['eta_str']}\n"
                       f"⚓ *Muelle:* {b['muelle']}\n"
                       f"🏗️ *Operación:* {b['operacion']}\n"
                       f"🏢 *Consignatario:* {b['consignatario']}")
            
            bot_send(MY_CHAT_ID, mensaje)
            avisados.add(id_unico)

    with open(AVISADOS_FILE, "w") as f:
        f.write("\n".join(avisados))

if __name__ == "__main__":
    print(f"--- BOT PUERTO CORUÑA: {datetime.now().strftime('%d/%m/%y %H:%M')} ---")
    monitor_automatico()
    print("--- PROCESO COMPLETADO ---")
