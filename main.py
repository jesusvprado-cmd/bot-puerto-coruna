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
HISTORY_FILE = "avisados.txt"

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'Markdown'}
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
    except Exception as e:
        logging.error(f"Error Telegram: {e}")

def get_notified_ids():
    if not os.path.exists(HISTORY_FILE): return set()
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def save_notified_id(ship_id):
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
        logging.info("Accediendo a login...")
        driver.get("https://nemopilots.com/login")
        
        # Login
        wait.until(EC.element_to_be_clickable((By.NAME, "email"))).send_keys(NEMO_USER)
        driver.find_element(By.NAME, "password").send_keys(NEMO_PASS)
        driver.find_element(By.XPATH, "//input[@type='submit' or @type='button'][contains(@value, 'Acceder')]").click()
        
        logging.info("Login OK. Navegando a Planificación...")
        time.sleep(10)
        
        # Clic en Planificación del menú lateral
        try:
            plan_menu = wait.until(EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, "Planificaci")))
            plan_menu.click()
            time.sleep(10)
        except:
            driver.get("https://nemopilots.com/planificacion")
            time.sleep(10)

        # Buscar tablas (el portal de Coruña tiene varias)
        tables = driver.find_elements(By.TAG_NAME, "table")
        logging.info(f"Tablas encontradas: {len(tables)}")
        
        notified_ids = get_notified_ids()
        new_notifications = 0
        
        for table in tables:
            rows = table.find_elements(By.TAG_NAME, "tr")
            for row in rows:
                cols = row.find_elements(By.TAG_NAME, "td")
                # Según tu foto, la tabla de Planificación tiene unas 13 columnas
                if len(cols) >= 11:
                    try:
                        # AJUSTE DE COLUMNAS SEGÚN TU FOTO:
                        eta = cols[0].text.strip()    # Columna 0: ETA
                        nombre = cols[6].text.strip() # Columna 6: Buque
                        consigna = cols[10].text.strip() # Columna 10: Consignataria
                        muelle = cols[11].text.strip() # Columna 11: Atraque
                        
                        if not (nombre and eta and "202" in eta): 
                            continue # Evitar filas vacías o cabeceras
                            
                        ship_id = f"{nombre}_{eta}".replace(" ", "_").replace("/", "-")
                        
                        if ship_id not in notified_ids:
                            message = (
                                f"🚢 *Nueva Entrada Planificada Coruña*\n\n"
                                f"*Buque:* {nombre}\n"
                                f"*ETA:* {eta}\n"
                                f"*Consignataria:* {consigna}\n"
                                f"*Muelle/Atraque:* {muelle}"
                            )
                            logging.info(f"¡Barco detectado! -> {nombre}")
                            send_telegram_message(message)
                            save_notified_id(ship_id)
                            notified_ids.add(ship_id)
                            new_notifications += 1
                    except:
                        continue
        
        logging.info(f"Proceso finalizado. Total nuevos barcos: {new_notifications}")
        
    except Exception as e:
        logging.error(f"Error: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    run_scraper()
