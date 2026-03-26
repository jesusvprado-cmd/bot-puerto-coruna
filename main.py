import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# --- CONFIGURACIÓN DE SECRETOS (Desde GitHub Settings) ---
TOKEN = os.getenv('TELEGRAM_TOKEN')
USER_NEMO = os.getenv('NEMO_USER')
PASS_NEMO = os.getenv('NEMO_PASS')

# Archivos para guardar datos entre ejecuciones
USUARIOS_FILE = "usuarios_activos.txt"
AVISADOS_FILE = "avisados.txt"

def bot_send(chat_id, mensaje):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": mensaje, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Error enviando Telegram: {e}")

def get_nemo_data():
    session = requests.Session()
    # 1. Login en la plataforma
    login_url = "https://nemopilots.com/login_check" 
    session.post(login_url, data={'_username': USER_NEMO, '_password': PASS_NEMO})
    
    # 2. Obtener la página de planificación
    res = session.get("https://nemopilots.com/planificacion/")
    soup = BeautifulSoup(res.text, 'html.parser')
    
    barcos = []
    filas = soup.find_all('tr')
    
    for f in filas:
        cols = f.find_all('td')
        if len(cols) > 13:
            # Extraemos los datos según la estructura de tu foto
            barcos.append({
                'eta_str': cols[0].get_text(strip=True),
                'nombre': cols[3].get_text(strip=True),
                'bandera': cols[4].get_text(strip=True),
                'consignatario': cols[9].get_text(strip=True),
                'muelle': cols[11].get_text(strip=True),
                'estado': cols[12].get_text(strip=True),
                'operacion': cols[13].get_text(strip=True)
            })
    return barcos

def gestionar_comandos():
    url_updates = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    try:
        updates = requests.get(url_updates).json()
        if not updates.get("result"): return
    except: return

    for update in updates["result"]:
        if "message" not in update: continue
        chat_id = str(update["message"]["chat"]["id"])
        text = update["message"].get("text", "")

        if text == "/start":
            # Añadir usuario a la lista de servicio
            usuarios = set()
            if os.path.exists(USUARIOS_FILE):
                with open(USUARIOS_FILE, "r") as f:
                    usuarios = set(f.read().splitlines())
            usuarios.add(chat_id)
            with open(USUARIOS_FILE, "w") as f:
                f.write("\n".join(usuarios))
            bot_send(chat_id, "✅ **SERVICIO INICIADO.** Recibirás alertas automáticas de nuevas entradas en A Coruña y Langosteira.")

        elif text == "/stop":
            # Quitar usuario de la lista
            if os.path.exists(USUARIOS_FILE):
                with open(USUARIOS_FILE, "r") as f:
                    users = f.read().splitlines()
                with open(USUARIOS_FILE, "w") as f:
                    for u in users:
                        if u != chat_id: f.write(u + "\n")
            bot_send(chat_id, "😴 **SERVICIO FINALIZADO.** Ya no recibirás más notificaciones hasta que vuelvas a pulsar /start.")

        elif text == "/list":
            data = get_nemo_data()
            msg = "⚓ **ESTADO ACTUAL DEL PUERTO:**\n\n"
            for b in data:
                # Mostramos solo los que ya están en muelle (omitimos fondeados si quieres)
                if "FONDEO" not in b['muelle'].upper():
                    msg += f"🚢 *{b['nombre']}*\n📍 {b['muelle']}\n\n"
            bot_send(chat_id, msg if len(msg) > 30 else "No hay buques atracados ahora mismo.")

        elif text == "/next":
            data = get_nemo_data()
            ahora = datetime.now()
            limite = ahora + timedelta(hours=8)
            msg = "🕒 **ENTRADAS PRÓXIMAS 8 HORAS:**\n_(Excluyendo fondeos)_\n\n"
            
            for b in data:
                try:
                    # Intentamos convertir la fecha de Nemo (formato DD/MM/YY HH:mm)
                    fecha_buque = datetime.strptime(b['eta_str'], "%d/%m/%y %H:%M")
                    if ahora <= fecha_buque <= limite and "FONDEO" not in b['muelle'].upper():
                        msg += f"➡️ *{b['nombre']}* ({b['eta_str']})\n📍 {b['muelle']}\n🏗️ {b['operacion']}\n\n"
                except: continue
            bot_send(chat_id, msg if len(msg) > 50 else "No hay entradas previstas en las próximas 8h.")

def monitor_automatico():
    # Solo avisar a los usuarios en 'usuarios_activos.txt'
    if not os.path.exists(USUARIOS_FILE): return
    with open(USUARIOS_FILE, "r") as f:
        activos = f.read().splitlines()
    if not activos: return

    data = get_nemo_data()
    
    # Cargar historial de avisados para no repetir
    if os.path.exists(AVISADOS_FILE):
        with open(AVISADOS_FILE, "r") as f:
            avisados = set(f.read().splitlines())
    else:
        avisados = set()

    for b in data:
        # ID único basado en nombre y fecha para detectar si es nuevo
        id_unico = f"{b['nombre']}-{b['eta_str']}"
        
        if id_unico not in avisados:
            mensaje = (f"🔔 **NUEVA ENTRADA DETECTADA**\n\n"
                       f"🚢 *Buque:* {b['nombre']}\n"
                       f"📅 *ETA:* {b['eta_str']}\n"
                       f"⚓ *Muelle:* {b['muelle']}\n"
                       f"🏗️ *Operación:* {b['operacion']}\n"
                       f"🏢 *Consignatario:* {b['consignatario']}")
            
            # Enviar a todos los que están de servicio
            for user_id in activos:
                bot_send(user_id, mensaje)
            
            avisados.add(id_unico)

    # Guardar historial actualizado
    with open(AVISADOS_FILE, "w") as f:
        f.write("\n".join(avisados))

if __name__ == "__main__":
    gestionar_comandos()
    monitor_automatico()
