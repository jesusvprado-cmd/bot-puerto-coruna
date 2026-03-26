import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime

# --- CONFIGURACIÓN ---
TOKEN = os.getenv('TELEGRAM_TOKEN')
MY_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
USER_NEMO = os.getenv('NEMO_USER')
PASS_NEMO = os.getenv('NEMO_PASS')
AVISADOS_FILE = "avisados.txt"

def bot_send(mensaje):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": MY_CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}
    try: requests.post(url, json=payload)
    except: pass

def get_nemo_data_selenium():
    print("Iniciando navegador con esteroides...")
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument('--ignore-certificate-errors')
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    barcos = []

    try:
        print("Cargando web de Nemo Pilots...")
        driver.get("https://nemopilots.com/login")
        time.sleep(5)

        # 1. Intentar hacer Login (más robusto)
        print("Buscando campos de acceso...")
        
        # Probamos a encontrar el usuario por varios métodos
        try:
            # Buscamos por nombre, id o incluso por el tipo 'text'
            user_field = driver.find_element(By.NAME, "_username") or driver.find_element(By.ID, "username")
            pass_field = driver.find_element(By.NAME, "_password") or driver.find_element(By.ID, "password")
            btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            
            print("Introduciendo datos...")
            user_field.send_keys(USER_NEMO)
            pass_field.send_keys(PASS_NEMO)
            btn.click()
            print("Botón de entrar pulsado.")
            
        except Exception as e_login:
            print(f"No encontré los cuadros normales: {e_login}")
            # Si falla, sacamos una lista de qué hay en la pantalla para investigar
            inputs = driver.find_elements(By.TAG_NAME, "input")
            print(f"He encontrado {len(inputs)} cuadros de texto. Nombres: {[i.get_attribute('name') for i in inputs]}")
            return []

        # 2. Ir a la Planificación
        time.sleep(5)
        print("Accediendo a la tabla de Coruña...")
        driver.get("https://nemopilots.com/planificacion/")
        
        # Espera extra por el circulito de carga
        print("Esperando a que el puerto cargue los datos...")
        time.sleep(15) 
        
        # 3. Leer la tabla
        filas = driver.find_elements(By.TAG_NAME, "tr")
        print(f"¡ÉXITO! Filas detectadas: {len(filas)}")

        for f in filas:
            cols = f.find_elements(By.TAG_NAME, "td")
            if len(cols) >= 13:
                datos = [c.text.strip() for c in cols]
                if datos[3] and len(datos[3]) > 2: # Nombre del barco
                    barcos.append({
                        'eta': datos[0],
                        'nombre': datos[3],
                        'muelle': datos[11] if len(datos) > 11 else "S/D",
                        'op': datos[13] if len(datos) > 13 else "S/D"
                    })
    except Exception as e:
        print(f"⚠️ FALLO GENERAL: {e}")
    finally:
        driver.quit()
    return barcos

if __name__ == "__main__":
    print(f"--- EJECUCIÓN: {datetime.now().strftime('%H:%M')} ---")
    barcos_hoy = get_nemo_data_selenium()
    
    avisados = set()
    if os.path.exists(AVISADOS_FILE):
        with open(AVISADOS_FILE, "r") as f:
            avisados = set(f.read().splitlines())

    for b in barcos_hoy:
        id_b = f"{b['nombre']}-{b['eta']}"
        if id_b not in avisados:
            print(f"Notificando barco: {b['nombre']}")
            msg = (f"🚢 **NUEVO BARCO EN PUERTO**\n\n"
                   f"⚓ *Nombre:* {b['nombre']}\n"
                   f"🕒 *Llegada:* {b['eta']}\n"
                   f"📍 *Muelle:* {b['muelle']}\n"
                   f"🏗️ *Op:* {b['op']}")
            bot_send(msg)
            avisados.add(id_b)

    with open(AVISADOS_FILE, "w") as f:
        f.write("\n".join(avisados))
    
    print(f"Finalizado. Barcos encontrados: {len(barcos_hoy)}")
