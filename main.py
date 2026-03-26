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
    requests.post(url, json=payload)

def get_nemo_data_selenium():
    print("Iniciando navegador invisible...")
    chrome_options = Options()
    chrome_options.add_argument("--headless") # Sin ventana
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    barcos = []

    try:
        # 1. Login
        print("Accediendo al login...")
        driver.get("https://nemopilots.com/login")
        time.sleep(2)
        driver.find_element(By.NAME, "_username").send_keys(USER_NEMO)
        driver.find_element(By.NAME, "_password").send_keys(PASS_NEMO)
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        
        # 2. Ir a planificación y ESPERAR al circulito
        print("Login ok. Cargando planificación...")
        driver.get("https://nemopilots.com/planificacion/")
        time.sleep(10) # Esperamos 10 segundos a que el circulito de tu vídeo se quite
        
        # 3. Buscar las filas de la tabla
        filas = driver.find_elements(By.TAG_NAME, "tr")
        print(f"Filas detectadas con el navegador: {len(filas)}")

        for f in filas:
            cols = f.find_elements(By.TAG_NAME, "td")
            if len(cols) >= 10: # Si tiene bastantes columnas, es un barco
                datos = [c.text.strip() for c in cols]
                # Según tu vídeo: 0=ETA, 3=Nombre, 11=Muelle
                if datos[3]: # Si el nombre no está vacío
                    barcos.append({
                        'eta': datos[0],
                        'nombre': datos[3],
                        'muelle': datos[11] if len(datos) > 11 else "S/D"
                    })
    except Exception as e:
        print(f"Fallo en el navegador: {e}")
    finally:
        driver.quit()
    return barcos

if __name__ == "__main__":
    print(f"--- BOT PUERTO CORUÑA {datetime.now().strftime('%H:%M')} ---")
    barcos_hoy = get_nemo_data_selenium()
    
    # Cargar memoria
    avisados = set()
    if os.path.exists(AVISADOS_FILE):
        with open(AVISADOS_FILE, "r") as f:
            avisados = set(f.read().splitlines())

    for b in barcos_hoy:
        id_b = f"{b['nombre']}-{b['eta']}"
        if id_b not in avisados:
            print(f"¡NUEVO! {b['nombre']}")
            msg = f"🚢 **NUEVO BARCO DETECTADO**\n\n*Nombre:* {b['nombre']}\n*ETA:* {b['eta']}\n*Muelle:* {b['muelle']}"
            bot_send(msg)
            avisados.add(id_b)

    with open(AVISADOS_FILE, "w") as f:
        f.write("\n".join(avisados))
    print("--- FIN ---")
