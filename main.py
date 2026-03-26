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
    # Intentar en el contenido principal primero
    rows = driver.find_elements(By.TAG_NAME, "tr")
    if len(rows) > 10:
        return rows
    
    # Si no hay suficientes filas, buscar en iframes
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    logging.info(f"Se encontraron {len(iframes)} iframes. Probando contenido...")
    
    for index, iframe in enumerate(iframes):
        try:
            driver.switch_to.frame(iframe)
            rows = driver.find_elements(By.TAG_NAME, "tr")
            if len(rows) > 10:
                logging.info(f"Tabla encontrada en el iframe índice {index}.")
                return rows
            # Si no está aquí, volver al principal para probar el siguiente
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
    chrome_options.add_argument("--ignore-certificate-errors")
    
    # Inicializar WebDriver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    wait = WebDriverWait(driver, 30)
    
    try:
        logging.info("Accediendo a la página de login...")
        driver.get("https://nemopilots.com/login")
        
        # Esperar y realizar login
        username_field = wait.until(EC.element_to_be_clickable((By.NAME, "_username")))
        password_field = driver.find_element(By.NAME, "_password")
        
        username_field.send_keys(NEMO_USER)
        password_field.send_keys(NEMO_PASS)
        
        login_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        login_button.click()
        
        logging.info("Login enviado. Esperando navegación a planificación...")
        time.sleep(5) # Pequeña pausa tras login
        
        driver.get("https://nemopilots.com/planificacion/")
        
        # Espera generosa para carga AJAX/JS
        logging.info("Esperando renderizado de la tabla (15s)...")
        time.sleep(15)
        
        rows = find_table_rows(driver)
        logging.info(f"Filas totales detectadas: {len(rows)}")
        
        notified_ids = get_notified_ids()
        new_notifications = 0
        
        for row in rows:
            try:
                cols = row.find_elements(By.TAG_NAME, "td")
                # Estructura esperada: ETA(0), Buque(3), Consignatario(9), Muelle(11), Operación(13)
                if len(cols) >= 14:
                    eta = cols[0].text.strip()
                    nombre = cols[3].text.strip()
                    consignatario = cols[9].text.strip()
                    muelle = cols[11].text.strip()
                    operacion = cols[13].text.strip()
                    
                    if not nombre or not eta:
                        continue
                        
                    # Identificador único simplificado
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
                        logging.info(f"Enviando notificación: {nombre}")
                        send_telegram_message(message)
                        save_notified_id(ship_id)
                        notified_ids.add(ship_id)
                        new_notifications += 1
            except Exception:
                continue # Saltar filas con errores de lectura
        
        logging.info(f"Script finalizado correctamente. Nuevos avisos: {new_notifications}")
        
    except Exception as e:
        logging.error(f"Error crítico durante la ejecución: {e}")
        driver.save_screenshot("error_screenshot.png")
        logging.info("Se ha guardado una captura de pantalla del error.")
    finally:
        driver.quit()

if __name__ == "__main__":
    if not all([TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, NEMO_USER, NEMO_PASS]):
        logging.error("Configuración incompleta: Verifica las variables de entorno.")
    else:
        run_scraper()

