import os
import time
import requests
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
NEMO_USER = os.getenv('NEMO_USER')
NEMO_PASS = os.getenv('NEMO_PASS')
HISTORY_FILE = "avisados_puerto.txt" # Historial separado para puerto

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'Markdown'}
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
    except Exception as e:
        logging.error(f"Error Telegram: {e}")

def get_history():
    if not os.path.exists(HISTORY_FILE): return set()
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def save_history(ship_id):
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(f"{ship_id}\n")

def run_scraper():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--ignore-certificate-errors")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    wait = WebDriverWait(driver, 30)
    
    try:
        logging.info("Iniciando sesión...")
        driver.get("https://nemopilots.com/login")
        
        wait.until(EC.element_to_be_clickable((By.NAME, "email"))).send_keys(NEMO_USER)
        driver.find_element(By.NAME, "password").send_keys(NEMO_PASS)
        driver.find_element(By.XPATH, "//input[@type='submit' or @type='button'][contains(@value, 'Acceder')]").click()
        
        time.sleep(8)
        # Ir a planificación donde están ambas tablas
        driver.get("https://nemopilots.com/planificacion")
        logging.info("Esperando carga de la tabla de Buques en Puerto...")
        time.sleep(15)

        # Buscamos todas las tablas
        tables = driver.find_elements(By.TAG_NAME, "table")
        if not tables:
            logging.error("No se encontraron tablas.")
            return

        # La primera tabla suele ser siempre "Buques en puerto"
        puerto_table = tables[0]
        rows = puerto_table.find_elements(By.TAG_NAME, "tr")
        history = get_history()
        count = 0
        
        for row in rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            # La tabla de puerto tiene unas 10 columnas
            if 8 <= len(cols) <= 12:
                try:
                    # MAPPING CORRECTO PARA "BUQUES EN PUERTO"
                    ata = cols[3].text.strip()      # Columna 3: ATA (Fecha atraque)
                    muelle = cols[5].text.strip()   # Columna 5: Atraque (Muelle)
                    buque = cols[6].text.strip()    # Columna 6: Buque (Nombre)
                    agente = cols[7].text.strip()   # Columna 7: Consignataria
                    
                    if not (buque and ata and "/" in ata):
                        continue
                    
                    # Identificador único para este atraque
                    ship_id = f"ATR_{buque}_{ata}".replace(" ", "_").replace("/", "-")
                    
                    if ship_id not in history:
                        message = (
                            f"🔔 *Entrada en Puerto Detectada*\n\n"
                            f"🚢 *Buque:* {buque}\n"
                            f"📍 *Muelle:* {muelle}\n"
                            f"🕒 *Llegada (ATA):* {ata}\n"
                            f"🏢 *Agente:* {agente}"
                        )
                        logging.info(f"Nuevo buque atracado: {buque}")
                        send_telegram(message)
                        save_history(ship_id)
                        history.add(ship_id)
                        count += 1
                except Exception as e:
                    continue
        
        logging.info(f"Finalizado. Nuevos barcos en puerto: {count}")
        
    except Exception as e:
        logging.error(f"Error: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    run_scraper()
