import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# --- CONFIGURACIÓN DE SECRETOS ---
TOKEN = os.getenv('TELEGRAM_TOKEN')
USER_NEMO = os.getenv('NEMO_USER')
PASS_NEMO = os.getenv('NEMO_PASS')
MY_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID') # <--- Usaremos esto para que te llegue a ti siempre

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
    print("Conectando con Nemo Pilots...")
    session = requests.Session()
    login_url = "https://nemopilots.com/login_check" 
    try:
        session.post(login_url, data={'_username': USER_NEMO, '_password': PASS_NEMO})
        res = session.get("https://nemopilots.com/planificacion/")
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
        print(f"Error al obtener datos: {e}")
        return []

def monitor_automatico():
    data = get_nemo_data()
    if not data:
        print("No se pudieron obtener datos de los barcos.")
        return

    # Cargamos historial (aunque en Actions se borrará si no lo guardamos en el repo)
    avisados = set()
    if os.path.exists(AVISADOS_FILE):
        with open(AVISADOS_FILE, "r") as f:
            avisados = set(f.read().splitlines())

    for b in data:
        id_unico = f"{b['nombre']}-{b['eta_str']}"
        
        if id_unico not in avisados:
            print(f"Nuevo buque detectado: {b['nombre']}")
            mensaje = (f"🔔 **NUEVA ENTRADA DETECTADA**\n\n"
                       f"🚢 *Buque:* {b['nombre']}\n"
                       f"📅 *ETA:* {b['eta_str']}\n"
                       f"⚓ *Muelle:* {b['muelle']}\n"
                       f"🏗️ *Operación:* {b['operacion']}\n")
            
            # TE LO ENVÍA A TI DIRECTAMENTE
            bot_send(MY_CHAT_ID, mensaje)
            avisados.add(id_unico)

    # Guardamos (esto servirá solo si el bot corre seguido o lo guardamos)
    with open(AVISADOS_FILE, "w") as f:
        f.write("\n".join(avisados))

if __name__ == "__main__":
    print("--- INICIANDO BOT PUERTO CORUÑA ---")
    monitor_automatico()
    print("--- TAREA FINALIZADA ---")
