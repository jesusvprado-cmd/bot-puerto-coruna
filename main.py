import os
import requests
import urllib3
from bs4 import BeautifulSoup
from datetime import datetime

# Desactivamos los avisos de seguridad por el fallo del certificado de la web
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CONFIGURACIÓN DE SECRETOS ---
TOKEN = os.getenv('TELEGRAM_TOKEN')
USER_NEMO = os.getenv('NEMO_USER')
PASS_NEMO = os.getenv('NEMO_PASS')
MY_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

AVISADOS_FILE = "avisados.txt"

def bot_send(mensaje):
    if not MY_CHAT_ID:
        print("❌ Error: No se encuentra el TELEGRAM_CHAT_ID en los secretos.")
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": MY_CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}
    try:
        r = requests.post(url, json=payload)
        print(f"Respuesta Telegram: {r.status_code}")
    except Exception as e:
        print(f"Error enviando Telegram: {e}")

def get_nemo_data():
    print(f"--- INICIO DE EJECUCIÓN: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} ---")
    session = requests.Session()
    session.verify = False  # Saltamos la verificación de certificado SSL
    
    login_url = "https://nemopilots.com/login_check"
    plan_url = "https://nemopilots.com/planificacion/"
    
    try:
        # 1. Intentamos el login
        print("Intentando login en Nemo Pilots...")
        payload = {'_username': USER_NEMO, '_password': PASS_NEMO}
        r_login = session.post(login_url, data=payload, verify=False)
        
        # 2. Cargamos la página de planificación
        res = session.get(plan_url, verify=False)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # Diagnóstico: ¿Qué estamos viendo?
        titulo = soup.title.string.strip() if soup.title else "Sin título"
        print(f"Título de la página cargada: {titulo}")
        
        if "Login" in titulo or "Acceso" in titulo:
            print("❌ ERROR: El bot no ha podido entrar. Revisa usuario y contraseña en los Secretos.")
            return []

        barcos = []
        # Buscamos la tabla. Si falla, probamos una búsqueda más genérica
        tabla = soup.find('table')
        if not tabla:
            print("❌ ERROR: No se ha encontrado ninguna tabla en la página.")
            return []

        filas = tabla.find_all('tr')
        print(f"Analizando {len(filas)} filas encontradas...")
        
        for f in filas:
            cols = f.find_all('td')
            # Buscamos filas que tengan contenido real (la tabla de Nemo tiene muchas columnas)
            if len(cols) > 13:
                nombre = cols[3].get_text(strip=True)
                if nombre: # Evitamos filas vacías
                    barcos.append({
                        'eta_str': cols[0].get_text(strip=True),
                        'nombre': nombre,
                        'muelle': cols[11].get_text(strip=True),
                        'operacion': cols[13].get_text(strip=True),
                        'consignatario': cols[9].get_text(strip=True)
                    })
        
        print(f"Total de barcos detectados con éxito: {len(barcos)}")
        return barcos

    except Exception as e:
        print(f"❌ Error crítico durante la obtención de datos: {e}")
        return []

def monitor_automatico():
    data = get_nemo_data()
    if not data:
        return

    # Cargamos historial de avisados para no repetir mensajes
    avisados = set()
    if os.path.exists(AVISADOS_FILE):
        with open(AVISADOS_FILE, "r") as f:
            avisados = set(f.read().splitlines())

    nuevos_avisos = 0
    for b in data:
        id_unico = f"{b['nombre']}-{b['eta_str']}"
        
        if id_unico not in avisados:
            print(f"📢 Nuevo buque para avisar: {b['nombre']}")
            mensaje = (f"🔔 *NUEVA ENTRADA DETECTADA*\n\n"
                       f"🚢 *Buque:* {b['nombre']}\n"
                       f"📅 *ETA:* {b['eta_str']}\n"
                       f"⚓ *Muelle:* {b['muelle']}\n"
                       f"🏗️ *Operación:* {b['operacion']}\n"
                       f"🏢 *Consignatario:* {b['consignatario']}")
            
            bot_send(mensaje)
            avisados.add(id_unico)
            nuevos_avisos += 1

    # Guardamos el archivo actualizado para que el bot tenga memoria
    with open(AVISADOS_FILE, "w") as f:
        f.write("\n".join(avisados))
    
    print(f"Proceso terminado. Avisos enviados: {nuevos_avisos}")

if __name__ == "__main__":
    monitor_automatico()
    print("--- TAREA FINALIZADA ---")
