import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
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
    try:
        requests.post(url, json=payload)
    except:
        pass

def get_nemo_data_selenium():
    print("Iniciando navegador invisible...")
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # --- ESTO ES LO QUE SOLUCIONA EL 'PRIVACY ERROR' ---
    chrome_options.add_argument('--ignore-certificate-errors')
    chrome_options.add_argument('--ignore-ssl-errors')
    chrome_options.add_argument('--allow-insecure-localhost')
    # ---------------------------------------------------

    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    barcos = []

    try:
        print("Accediendo a la web (saltando avisos de seguridad)...")
        driver.get("https://nemopilots.com/login")
        
        wait = WebDriverWait(driver, 25) # Un poco más de tiempo por si la web va lenta
        print("Buscando cuadros de login...")
        
        # Esperamos a que el campo de usuario aparezca
        user_field = wait.until(EC.presence_of_element_located((By.NAME, "_username")))
        pass_field = driver.find_element(By.NAME, "_password")
        
        print("Introduciendo credenciales...")
        user_field.send_keys(USER_NEMO)
        pass_field.send_keys(PASS_NEMO)
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        
        print("Login enviado. Cargando planificación...")
        time.sleep(5) 
        driver.get("https://nemopilots.com/planificacion/")
        
        # Esperamos a que el circulito de carga de tu vídeo desaparezca
        print("Esperando 15 segundos a que carguen los barcos...")
        time.sleep(15) 
        
        filas = driver.find_elements(By.TAG_NAME, "tr")
        print(f"Filas detectadas en total: {len(filas)}")

        for f in filas:
            cols = f.find_elements(By.TAG_NAME, "td")
            if len(cols) >= 13:
                datos = [c.text.strip() for c in cols]
                if datos[3]: 
                    barcos.append({
                        'eta': datos[0],
                        'nombre': datos[3],
                        'muelle': datos[11] if len(datos) > 11 else "S/D",
                        'operacion': datos[13] if len(datos) > 13 else "S/D"
                    })
    except Exception as e:
        print(f"⚠️ ERROR: {e}")
        print(f"Página en la que se detuvo: {driver.title}")
    finally:
        driver.quit()
    return barcos

if __name__ == "__main__":
    print(f"--- BOT PUERTO CORUÑA {datetime.now().strftime('%H:%M')} ---")
    barcos_hoy = get_nemo_data_selenium()
    
    # Cargar historial
    avisados = set()
    if os.path.exists(AVISADOS_FILE):
        with open(AVISADOS_FILE, "r") as f:
            avisados = set(f.read().splitlines())

    for b in barcos_hoy:
        id_b = f"{b['nombre']}-{b['eta']}"
        if id_b not in avisados:
            print(f"¡NUEVO BARCO! {b['nombre']}")
            msg = (f"🚢 **NUEVA ENTRADA DETECTADA**\n\n"
                   f"🔹 *Barco:* {b['nombre']}\n"
                   f"🕒 *ETA:* {b['eta']}\n"
                   f"📍 *Muelle:* {b['muelle']}\n"
                   f"🏗️ *Op:* {b['operacion']}")
            bot_send(msg)
            avisados.add(id_b)

    # Guardar memoria
    with open(AVISADOS_FILE, "w") as f:
        f.write("\n".join(avisados))
    
    print(f"Proceso terminado. Barcos encontrados: {len(barcos_hoy)}")
