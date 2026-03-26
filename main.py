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

# Configuración de Logging
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

def find_table_rows(driver):
    """Busca filas en el contenido principal o en iframes."""
    # Intentar primero en el documento principal
    rows = driver.find_elements(By.TAG_NAME, "tr")
    if len(rows) > 10: return rows
    
    # Si no, buscar en iframes
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    for index, iframe in enumerate(iframes):
        try:
            driver.switch_to.frame(iframe)
            rows = driver.find_elements(By.TAG_NAME, "tr")
            if len(rows) > 10: return rows
            driver.switch_to.default_content()
        except:
            driver.switch_to.default_content()
    return []

def run_scraper():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--ignore-certificate-errors")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    wait = WebDriverWait(driver, 30)
    
    try:
        logging.info("Iniciando Login...")
        driver.get("https://nemopilots.com/login")
        
        # Login
        wait.until(EC.element_to_be_clickable((By.NAME, "email"))).send_keys(NEMO_USER)
        driver.find_element(By.NAME, "password").send_keys(NEMO_PASS)
        driver.find_element(By.XPATH, "//input[@type='submit' or @type='button'][contains(@value, 'Acceder')]").click()
        
        logging.info("Login realizado. Buscando menú de Planificación...")
        time.sleep(10)
        
        # --- REPARACIÓN: En lugar de ir a la URL, clicamos en el menú ---
        try:
            # Buscamos el enlace que contiene el texto 'Planificación'
            plan_menu = wait.until(EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, "Planificaci")))
            plan_menu.click()
            logging.info("Clic en menú Planificación realizado.")
        except Exception as e:
            logging.warning(f"No se pudo clicar en el menú, intentando URL alternativa: {e}")
            driver.get("https://nemopilots.com/planificacion") # Intentar sin la barra final
            
        time.sleep(15)
        driver.save_screenshot("debug_final.png") # Para ver si ahora sí sale la tabla
        
        rows = find_table_rows(driver)
        logging.info(f"Filas detectadas: {len(rows)}")
        
        notified_ids = get_notified_ids()
        new_notifications = 0
        
        for row in rows:
            try:
                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) >= 14:
                    eta, nombre = cols[0].text.strip(), cols[3].text.strip()
                    consignatario, muelle, operacion = cols[9].text.strip(), cols[11].text.strip(), cols[13].text.strip()
                    
                    if not (nombre and eta): continue
                    
                    ship_id = f"{nombre}_{eta}".replace(" ", "_").replace("/", "-")
                    if ship_id not in notified_ids:
                        msg = f"🚢 *Nuevo Barco*\n*Buque:* {nombre}\n*ETA:* {eta}\n*Muelle:* {muelle}"
                        send_telegram_message(msg)
                        save_notified_id(ship_id)
                        notified_ids.add(ship_id)
                        new_notifications += 1
            except: continue
            
        logging.info(f"Fin. Nuevos: {new_notifications}")
        
    except Exception as e:
        logging.error(f"Error: {e}")
        driver.save_screenshot("debug_final.png")
    finally:
        driver.quit()

if __name__ == "__main__":
    run_scraper()
