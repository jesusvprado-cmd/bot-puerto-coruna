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
    requests.post(url, json=payload)

def get_nemo_data_selenium():
    print("Iniciando navegador invisible...")
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # Fingimos ser un navegador normal para que no nos bloqueen
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    barcos = []

    try:
        # 1. Login
        print("Accediendo a la web...")
        driver.get("https://nemopilots.com/login")
        
        # Esperamos hasta 20 segundos a que aparezca el cuadro de usuario
        wait = WebDriverWait(driver, 20)
        print("Buscando cuadros de login...")
        
        user_field = wait.until(EC.presence_of_element_located((By.NAME, "_username")))
        pass_field = driver.find_element(By.NAME, "_password")
        
        user_field.send_keys(USER_NEMO)
        pass_field.send_keys(PASS_NEMO)
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        
        # 2. Ir a planificación
        print("Login enviado. Esperando a la tabla...")
        time.sleep(5) # Pausa técnica post-login
        driver.get("https://nemopilots.com/planificacion/")
        
        # Esperamos a que el circulito de carga desaparezca y aparezcan los datos
        time.sleep(12) 
        
        # 3. Extraer datos
        filas = driver.find_elements(By.TAG_NAME, "tr")
        print(f"Filas detectadas: {len(filas)}")

        for f in filas:
            cols = f.find_elements(By.TAG_NAME, "td")
            if len(cols) >= 13:
                datos = [c.text.strip() for c in cols]
                if datos[3]: # Si hay nombre de barco
                    barcos.append({
                        'eta': datos[0],
                        'nombre': datos[3],
                        'muelle': datos[11] if len(datos) > 11 else "S/D",
                        'operacion': datos[13] if len(datos) > 13 else "S/D"
                    })
    except Exception as e:
        print(f"⚠️ ERROR: {e}")
        print(f"Página actual: {driver.title}")
    finally:
        driver.quit()
    return barcos

if __name__ == "__main__":
    print(f"--- BOT PUERTO CORUÑA {datetime.now().strftime('%H:%M')} ---")
    barcos_hoy = get_nemo_data_selenium()
    
    avisados = set()
    if os.path.exists(AVISADOS_FILE):
        with open(AVISADOS_FILE, "r") as f:
            avisados = set(f.read().splitlines())

    for b in barcos_hoy:
        id_b = f"{b['nombre']}-{b['eta']}"
        if id_b not in avisados:
            print(f"¡NUEVO! {b['nombre']}")
            msg = (f"🚢 **NUEVA ENTRADA**\n\n"
                   f"🔹 *Barco:* {b['nombre']}\n"
                   f"🕒 *ETA:* {b['eta']}\n"
                   f"📍 *Muelle:* {b['muelle']}\n"
                   f"🏗️ *Op:* {b['operacion']}")
            bot_send(msg)
            avisados.add(id_b)

    with open(AVISADOS_FILE, "w") as f:
        f.write("\n".join(avisados))
    print(f"Proceso terminado. Barcos encontrados: {len(barcos_hoy)}")
