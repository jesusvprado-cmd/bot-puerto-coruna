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
HISTORY_FILE = "avisados_puerto.txt"

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'Markdown'}
    try:
        requests.post(url, json=payload).raise_for_status()
    except Exception as e:
        logging.error(f"Error Telegram: {e}")

def get_history():
    if not os.path.exists(HISTORY_FILE): return set()
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def save_history(ship_id):
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(f"{ship_id}\n")

def limpiar(texto):
    """Elimina saltos de línea y espacios extra de cualquier texto."""
    return " ".join(texto.split())

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
        
        logging.info("Login OK. Esperando carga del portal...")
        time.sleep(10)
        
        try:
            plan_link = wait.until(EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, "Planificaci")))
            plan_link.click()
            logging.info("Menú Planificación OK.")
        except Exception as e:
            logging.warning(f"No se encontró el menú: {e}")
        
        logging.info("Esperando carga de tablas (15s)...")
        time.sleep(15)
        
        tables = driver.find_elements(By.TAG_NAME, "table")
        logging.info(f"Tablas encontradas: {len(tables)}")
        
        if not tables:
            logging.error("No se encontraron tablas.")
            driver.save_screenshot("debug_final.png")
            return

        # Columnas de "Buques en puerto":
        # 0=ETD, 1=Marea, 2=Días, 3=ATA, 4=SC, 5=N°Escala, 6=Atraque, 7=Buque, 8=Consignataria, 9=Secuencia, 10=Obs
        rows = tables[0].find_elements(By.TAG_NAME, "tr")
        history = get_history()
        count = 0
        
        for row in rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) >= 10:
                try:
                    # Leer texto de cada columna y limpiar saltos de línea
                    ata_raw   = cols[3].text.strip()
                    muelle    = cols[6].text.strip()
                    buque     = cols[7].text.strip()
                    consigna  = cols[8].text.strip()
                    obs       = cols[10].text.strip() if len(cols) > 10 else ""
                    
                    # ATA limpia en una sola línea (ej: "06/04/26 05:00")
                    ata = limpiar(ata_raw)
                    
                    # Validar que la fila tiene datos reales
                    if not (buque and ata and "/" in ata):
                        continue
                    
                    # MUELLE: solo la primera línea, sin los norays "(16 - 22)"
                    nombre_muelle = muelle.split("\n")[0].strip()
                    
                    # BUQUE: primera línea como nombre + extraer IMO
                    lineas_buque = buque.split("\n")
                    nombre_buque = lineas_buque[0].strip()
                    imo = ""
                    for linea in lineas_buque:
                        if "IMO" in linea:
                            partes = linea.strip().split()
                            try:
                                idx = partes.index("IMO")
                                if idx + 1 < len(partes):
                                    imo = f"(IMO {partes[idx + 1]})"
                            except ValueError:
                                pass
                            break
                    nombre_buque_completo = f"{nombre_buque} {imo}".strip()
                    
                    # ID único limpio (sin saltos de línea, sin barras)
                    ship_id = f"ATR_{nombre_buque}_{ata}".replace(" ", "_").replace("/", "-").replace("\n", "")
                    
                    if ship_id not in history:
                        message = (
                            f"🔔 *Nuevo Barco en el Puerto*\n\n"
                            f"🚢 *Buque:* {nombre_buque_completo}\n"
                            f"📍 *Muelle:* {nombre_muelle}\n"
                            f"🕒 *Llegada (ATA):* {ata}\n"
                            f"🏢 *Consignataria:* {limpiar(consigna).split(' ')[0]}\n"
                            f"📋 *Obs:* {limpiar(obs) if obs else '-'}"
                        )
                        logging.info(f"Notificando buque: {nombre_buque_completo}")
                        send_telegram(message)
                        save_history(ship_id)
                        history.add(ship_id)
                        count += 1
                except:
                    continue
        
        logging.info(f"Finalizado. Nuevos barcos notificados: {count}")
        
    except Exception as e:
        logging.error(f"Error crítico: {e}")
        driver.save_screenshot("debug_final.png")
    finally:
        driver.quit()

if __name__ == "__main__":
    run_scraper()
