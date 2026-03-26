import os
import requests
import urllib3
import time
from bs4 import BeautifulSoup
from datetime import datetime

# Desactivar avisos de seguridad SSL
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
    # Añadimos cabeceras de navegador real para que no nos bloqueen
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest'
    })
    
    try:
        # 1. Obtener Token CSRF
        login_page = session.get("https://nemopilots.com/login", verify=False)
        soup_init = BeautifulSoup(login_page.text, 'html.parser')
        token = soup_init.find('input', {'name': '_csrf_token'})
        csrf_token = token.get('value') if token else ""

        # 2. Login
        payload = {'_username': USER_NEMO, '_password': PASS_NEMO, '_csrf_token': csrf_token}
        session.post("https://nemopilots.com/login_check", data=payload, verify=False)
        print("Login realizado. Esperando a que carguen los datos...")
        
        # 3. Acceder a la planificación (Esperamos 5 segundos para simular la carga)
        time.sleep(5)
        res = session.get("https://nemopilots.com/planificacion/", verify=False)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        barcos = []
        tablas = soup.find_all('table')
        
        # Si no hay tablas, probamos a buscar por una clase específica que se ve en el vídeo
        if not tablas:
            print("No se ven tablas normales, buscando capas de datos...")
            # En el vídeo se ven filas con clases tipo 'row' o 'buque'
            # Intentamos capturar cualquier cosa que parezca una fila de barco
            filas = soup.select('tr') or soup.select('.row')
        else:
            # Si hay tablas, cogemos todas las filas de todas las tablas
            filas = []
            for t in tablas:
                filas.extend(t.find_all('tr'))

        print(f"Filas encontradas para analizar: {len(filas)}")

        for f in filas:
            cols = f.find_all('td')
            if len(cols) > 13:
                # Limpiamos el texto de espacios y saltos de línea
                nombre = cols[3].get_text(strip=True)
                eta = cols[0].get_text(strip=True)
                if nombre and eta:
                    barcos.append({
                        'eta_str': eta,
                        'nombre': nombre,
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
    
    # Historial de barcos ya avisados
    avisados = set()
    if os.path.exists(AVISADOS_FILE):
        with open(AVISADOS_FILE, "r") as f:
            avisados = set(f.read().splitlines())

    if not data:
        print("⚠️ La web no ha devuelto barcos todavía. Puede que necesitemos Selenium.")
        return

    for b in data:
        # ID único: Nombre + Fecha (Corregido el error de sintaxis anterior)
        id_unico = f"{b['nombre']}-{b['eta_str']}"
        
        if id_unico not in avisados:
            print(f"¡Nuevo barco! {b['nombre']}")
            mensaje = (f"🚢 **NUEVO BUQUE DETECTADO**\n\n"
                       f"🔹 *Nombre:* {b['nombre']}\n"
                       f"🕒 *ETA:* {b['eta_str']}\n"
                       f"📍 *Muelle:* {b['muelle']}\n"
                       f"🏗️ *Operación:* {b['operacion']}\n"
                       f"🏢 *Consignatario:* {b['consignatario']}")
            
            bot_send(MY_CHAT_ID, mensaje)
            avisados.add(id_unico)

    # Guardar memoria
    with open(AVISADOS_FILE, "w") as f:
        f.write("\n".join(avisados))

if __name__ == "__main__":
    ahora = datetime.now().strftime('%d/%m/%Y %H:%M')
    print(f"--- BOT PUERTO CORUÑA: {ahora} ---")
    monitor_automatico()
    print("--- PROCESO FINALIZADO ---")
