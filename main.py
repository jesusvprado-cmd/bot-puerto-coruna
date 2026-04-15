import os
import re
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

TELEGRAM_TOKEN   = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
NEMO_USER        = os.getenv('NEMO_USER')
NEMO_PASS        = os.getenv('NEMO_PASS')
HISTORY_FILE     = "avisados_puerto.txt"

def limpiar(texto):
    return " ".join(texto.split())

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'Markdown'}
    try:
        r = requests.post(url, json=payload, timeout=15)
        r.raise_for_status()
        logging.info("Mensaje Telegram enviado OK.")
    except Exception as e:
        logging.error(f"Error Telegram: {e}")

def get_history():
    if not os.path.exists(HISTORY_FILE):
        return set()
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def save_to_history(ship_id):
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(f"{ship_id}\n")

def get_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

def login(driver, wait):
    logging.info("Accediendo al login...")
    driver.get("https://nemopilots.com/login")
    time.sleep(3)
    for selector in [(By.NAME,"_username"),(By.NAME,"username"),(By.NAME,"email"),(By.CSS_SELECTOR,"input[type='email']"),(By.CSS_SELECTOR,"input[type='text']")]:
        try:
            field = wait.until(EC.presence_of_element_located(selector))
            field.clear()
            field.send_keys(NEMO_USER)
            logging.info(f"Campo usuario: {selector}")
            break
        except:
            continue
    for selector in [(By.NAME,"_password"),(By.NAME,"password"),(By.CSS_SELECTOR,"input[type='password']")]:
        try:
            field = driver.find_element(*selector)
            field.clear()
            field.send_keys(NEMO_PASS)
            logging.info(f"Campo password: {selector}")
            break
        except:
            continue
    for selector in [(By.CSS_SELECTOR,"button[type='submit']"),(By.CSS_SELECTOR,"input[type='submit']"),(By.XPATH,"//button[contains(text(),'Acced') or contains(text(),'Entr') or contains(text(),'Login')]")]:
        try:
            driver.find_element(*selector).click()
            logging.info("Botón login pulsado.")
            break
        except:
            continue
    time.sleep(8)
    logging.info(f"URL tras login: {driver.current_url}")
    return "login" not in driver.current_url.lower()

def ir_a_planificacion(driver, wait):
    logging.info("Navegando a Planificación...")
    for selector in [(By.PARTIAL_LINK_TEXT,"Planificaci"),(By.XPATH,"//*[contains(text(),'Planificaci')]")]:
        try:
            link = wait.until(EC.element_to_be_clickable(selector))
            link.click()
            logging.info("Menú Planificación clicado.")
            time.sleep(12)
            return True
        except:
            continue
    driver.get("https://nemopilots.com/planificacion/")
    time.sleep(12)
    return True

def extraer_buques(driver):
    barcos = []
    tables = driver.find_elements(By.TAG_NAME, "table")
    logging.info(f"Tablas encontradas: {len(tables)}")
    if not tables:
        driver.save_screenshot("debug_final.png")
        logging.error("No se encontraron tablas.")
        return barcos
    best_table = max(tables, key=lambda t: len(t.find_elements(By.TAG_NAME, "tr")))
    rows = best_table.find_elements(By.TAG_NAME, "tr")
    logging.info(f"Filas en tabla principal: {len(rows)}")
    for row in rows:
        cols = row.find_elements(By.TAG_NAME, "td")
        if len(cols) < 9:
            continue
        try:
            ata_raw  = cols[3].text.strip()
            muelle   = cols[6].text.strip()
            buque    = cols[7].text.strip()
            consigna = cols[8].text.strip()
            obs      = cols[10].text.strip() if len(cols) > 10 else ""
            ata = limpiar(ata_raw)
            if not buque or not ata or "/" not in ata:
                continue
            nombre_muelle = muelle.split("\n")[0].strip()
            lineas_buque = buque.split("\n")
            nombre_buque = lineas_buque[0].strip()
            imo = ""
            for linea in lineas_buque:
                if "IMO" in linea.upper():
                    match = re.search(r'IMO\s*(\d+)', linea, re.IGNORECASE)
                    if match:
                        imo = f"(IMO {match.group(1)})"
                    break
            nombre_buque_completo = f"{nombre_buque} {imo}".strip()
            barcos.append({
                'id_key'  : f"ATR_{nombre_buque}_{ata}",
                'buque'   : nombre_buque_completo,
                'muelle'  : nombre_muelle,
                'ata'     : ata,
                'consigna': limpiar(consigna).split('\n')[0],
                'obs'     : limpiar(obs) if obs else "-"
            })
        except Exception as ex:
            logging.debug(f"Fila ignorada: {ex}")
            continue
    logging.info(f"Barcos extraídos: {len(barcos)}")
    return barcos

def run():
    if not all([TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, NEMO_USER, NEMO_PASS]):
        logging.error("Faltan variables de entorno.")
        return
    driver = get_driver()
    wait   = WebDriverWait(driver, 30)
    try:
        if not login(driver, wait):
            logging.error("Login fallido.")
            driver.save_screenshot("debug_final.png")
            return
        ir_a_planificacion(driver, wait)
        barcos = extraer_buques(driver)
        if not barcos:
            logging.warning("No se encontraron barcos.")
            driver.save_screenshot("debug_final.png")
            return
        history = get_history()
        nuevos  = 0
        for b in barcos:
            ship_id = b['id_key'].replace(" ","_").replace("/","-").replace("\n","")
            if ship_id not in history:
                message = (
                    f"🔔 *Nuevo Barco en el Puerto*\n\n"
                    f"🚢 *Buque:* {b['buque']}\n"
                    f"📍 *Muelle:* {b['muelle']}\n"
                    f"🕒 *Llegada (ATA):* {b['ata']}\n"
                    f"🏢 *Consignataria:* {b['consigna']}\n"
                    f"📋 *Obs:* {b['obs']}"
                )
                logging.info(f"Nuevo barco: {b['buque']}")
                send_telegram(message)
                save_to_history(ship_id)
                history.add(ship_id)
                nuevos += 1
        logging.info(f"Completado. Nuevos: {nuevos}")
    except Exception as e:
        logging.error(f"Error crítico: {e}")
        driver.save_screenshot("debug_final.png")
    finally:
        driver.quit()

if __name__ == "__main__":
    run()
