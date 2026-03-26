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
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Configuracion de variables de entorno
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
NEMO_USER = os.getenv('NEMO_USER')
NEMO_PASS = os.getenv('NEMO_PASS')

HISTORY_FILE = "avisados.txt"

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown'
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
    except Exception as e:
        logging.error(f"Error enviando mensaje a Telegram: {e}")

def get_notified_ids():
    if not os.path.exists(HISTORY_FILE):
        return set()
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def save_notified_id(ship_id):
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(f"{ship_id}\n")

def find_table_rows(driver):
    """Busca filas de la tabla principal, entrando en iframes si es necesario."""
    rows = driver.find_elements(By.TAG_NAME, "tr")
    if len(rows) > 10:
        return rows
    
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    logging.info(f"Se encontraron {len(iframes)} iframes. Probando contenidos...")
    
    for index, iframe in enumerate(iframes):
        try:
            driver.switch_to.frame(iframe)
            rows = driver.find_elements(By.TAG_NAME, "tr")
            if len(rows) > 10:
                logging.info(f"Tabla encontrada en el iframe índice {index}.")
                return rows
            driver.switch_to.default_content()
        except Exception:
            driver.switch_to.default_content()
            continue
    return []

def run_scraper():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--ignore-certificate-errors") # Importante para este sitio
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    wait = WebDriverWait(driver, 30)
    
    try:
        logging.info("Accediendo a la página de login...")
        driver.get("https://nemopilots.com/login")
        
        # --- CAMPOS ACTUALIZADOS ---
        # Ahora el usuario es "email" y la contraseña "password"
        username_field = wait.until(EC.element_to_be_clickable((By.NAME, "email"))) 
        password_field = driver.find_element(By.NAME, "password")
        
        username_field.send_keys(NEMO_USER)
        password_field.send_keys(NEMO_PASS)
        
        # El botón de login a veces no tiene un ID claro, usamos el tipo submit del formulario
        login_button = driver.find_element(By.XPATH, "//input[@type='submit' or @type='button'][contains(@value, 'Acceder')]")
        if not login_button:
             login_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
             
        login_button.click()
        
        logging.info("Login enviado. Esperando navegación...")
        time.sleep(8)
        
        driver.get("https://nemopilots.com/planificacion/")
        logging.info("Esperando renderizado de la tabla (15s)...")
        time.sleep(15)
        
        rows = find_table_rows(driver)
        logging.info(f"Filas totales detectadas: {len(rows)}")
        
        notified_ids = get_notified_ids()
        new_notifications = 0
        
        for row in rows:
            try:
                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) >= 14:
                    eta = cols[0].text.strip()
                    nombre = cols[3].text.strip()
                    consignatario = cols[9].text.strip()
                    muelle = cols[11].text.strip()
                    operacion = cols[13].text.strip()
                    
                    if not nombre or not eta:
                        continue
                        
                    ship_id = f"{nombre}_{eta}".replace(" ", "_").replace("/", "-")
                    
                    if ship_id not in notified_ids:
                        message = (
                            f"🚢 *Nueva Entrada Planificada*\n\n"
                            f"*Buque:* {nombre}\n"
                            f"*ETA:* {eta}\n"
                            f"*Consignatario:* {consignatario}\n"
                            f"*Muelle:* {muelle}\n"
                            f"*Operación:* {operacion}"
                        )
                        logging.info(f"Notificando buque: {nombre}")
                        send_telegram_message(message)
                        save_notified_id(ship_id)
                        notified_ids.add(ship_id)
                        new_notifications += 1
            except Exception:
                continue
        
        logging.info(f"Proceso finalizado. Nuevos avisos: {new_notifications}")
        
    except Exception as e:
        logging.error(f"Fallo en login o scraping: {e}")
        driver.save_screenshot("error_screenshot.png")
    finally:
        driver.quit()

if __name__ == "__main__":
    if not all([TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, NEMO_USER, NEMO_PASS]):
        logging.error("Faltan credenciales en los Secrets.")
    else:
        run_scraper()
