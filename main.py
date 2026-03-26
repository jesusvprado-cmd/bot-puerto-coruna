import os
import requests
import urllib3
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# --- CONFIGURACIÓN DE SEGURIDAD ---
# Esto silencia el aviso de "Sitio no seguro" en la consola de GitHub
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CONFIGURACIÓN DE SECRETOS ---
TOKEN = os.getenv('TELEGRAM_TOKEN')
USER_NEMO = os.getenv('NEMO_USER')
PASS_NEMO = os.getenv('NEMO_PASS')
MY_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

AVISADOS_FILE = "avisados.txt"

def bot_send(chat_id, mensaje):
    if not chat_id:
        print("Error: No se ha configurado el TELEGRAM_CHAT_ID en los Secretos.")
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": mensaje, "parse_mode": "Markdown"}
    try:
        r = requests.post(url, json=payload)
        if r.status_code == 200:
            print(f"Mensaje enviado correctamente a Telegram.")
        else:
            print(f"Telegram respondió con error {r.status_code}: {r.text}")
    except Exception as e:
        print(f"Error enviando Telegram: {e}")

def get_nemo_data():
    print("Conectando con Nemo Pilots (saltando verificación SSL)...")
    session = requests.Session()
    # Desactivamos la verificación de certificado para evitar el error 'Hostname mismatch'
    session.verify = False 
    
    login_url = "https://nemopilots.com/login_check" 
    try:
        # Hacemos el login
        session.post(login_url, data={'_username': USER_NEMO, '_password': PASS_NEMO}, verify=False)
        
        # Vamos a la página de planificación
        res = session.get("https://nemopilots.com/planificacion/", verify=False)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        barcos = []
        filas = soup.find_all('tr')
        print(f"Analizando {len(filas)} filas de la tabla...")
        
        for f in filas:
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
        print(f"Error técnico al obtener datos: {e}")
        return []

def monitor_automatico():
    data = get_nemo_data()
    if not data:
        print("No se encontraron barcos o la tabla estaba vacía.")
        return

    # Cargamos historial de barcos ya avisados
    avisados = set()
    if os.path.exists(AVISADOS_FILE):
        with open(AVISADOS_FILE, "r") as f:
            avisados = set(f.read().splitlines())

    nuevos_detectados = 0
    for b in data:
        # Creamos un ID único con nombre y fecha
        id_unico = f"{b['nombre']}-{b['eta_str']}"
        
        if id_unico not in avisados:
            print(f"¡Nuevo barco! -> {b['nombre']}")
            mensaje = (f"🚢 **NUEVO BARCO DETECTADO**\n\n"
                       f"🔹 *Nombre:* {b['nombre']}\n"
                       f"📅 *ETA:* {b['eta_str']}\n"
                       f"⚓ *Muelle:* {b['muelle']}\n"
                       f"🏗️ *Operación:* {b['operacion']}\n"
                       f"🏢 *Consignatario:* {b['consignatario']}")
            
            bot_send(MY_CHAT_ID, mensaje)
            avisados.add(id_unico)
            nuevos_detectados += 1

    if nuevos_detectados == 0:
        print("No hay barcos nuevos desde la última revisión.")

    # Guardamos la memoria para la próxima vez
    with open(AVISADOS_FILE, "w") as f:
        f.write("\n".join(avisados))

if __name__ == "__main__":
    print(f"--- INICIO DE EJECUCIÓN: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} ---")
    monitor_automatico()
    print("--- TAREA FINALIZADA ---")
