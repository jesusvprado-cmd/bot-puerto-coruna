import os
import time
import requests
import logging
from datetime import datetime, timedelta
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

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': msg, 'parse_mode': 'Markdown'}
    try: requests.post(url, json=payload).raise_for_status()
    except Exception as e: logging.error(f"Error Telegram: {e}")

def get_history():
    if not os.path.exists(HISTORY_FILE): return set()
    with open(HISTORY_FILE, "r") as f: return set(l.strip() for l in f if l.strip())

def save_id(sid):
    with open(HISTORY_FILE, "a") as f: f.write(f"{sid}\n")

def run():
    chrome_opts = Options()
    chrome_opts.add_argument("--headless")
    chrome_opts.add_argument("--no-sandbox")
    chrome_opts.add_argument("--disable-dev-shm-usage")
    chrome_opts.add_argument("--window-size=1920,1080")
    chrome_opts.add_argument("--ignore-certificate-errors")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_opts)
    wait = WebDriverWait(driver, 30)
    
    try:
        logging.info("Entrando...")
        driver.get("https://nemopilots.com/login")
        wait.until(EC.element_to_be_clickable((By.NAME, "email"))).send_keys(NEMO_USER)
        driver.find_element(By.NAME, "password").send_keys(NEMO_PASS)
        driver.find_element(By.XPATH, "//input[@type='submit' or @type='button'][contains(@value, 'Acceder')]").click()
        
        time.sleep(10)
        try: wait.until(EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, "Planificaci"))).click()
        except: driver.get("https://nemopilots.com/planificacion")
        time.sleep(12)

        tables = driver.find_elements(By.TAG_NAME, "table")
        history = get_history()
        now = datetime.now()
        
        # 1. ANALIZAR BUQUES EN PUERTO (Atracados)
        atracados_msg = "📍 *BUQUES ACTUALMENTE EN PUERTO*\n"
        found_atracado = False
        
        if len(tables) > 0:
            rows = tables[0].find_elements(By.TAG_NAME, "tr")
            for r in rows:
                cols = r.find_elements(By.TAG_NAME, "td")
                # Basado en tu foto: ETD(0), ATA(3), Atraque(5), Buque(6), Consigna(7), Obs(9)
                if len(cols) >= 8:
                    buque = cols[6].text.strip()
                    ata = cols[3].text.strip()
                    muelle = cols[5].text.strip()
                    if "/" in ata and buque:
                        atracados_msg += f"• *{buque}* | Atracó: {ata}\n  Muelle: {muelle}\n"
                        found_atracado = True
                        # Notificar si es una entrada nueva al puerto
                        sid = f"IN_{buque}_{ata}".replace(" ","_")
                        if sid not in history:
                            send_telegram(f"🔔 *Entrada Detectada en Puerto*\n¡El buque *{buque}* acaba de atracar!\nMuelle: {muelle}\nATA: {ata}")
                            save_id(sid)
                            history.add(sid)

        # 2. ANALIZAR PREVISIÓN (Próximas 8 horas)
        plan_msg = "🕒 *PREVISIÓN PRÓXIMAS 8 HORAS*\n"
        found_plan = False
        limit_time = now + timedelta(hours=8)

        if len(tables) > 1:
            rows = tables[1].find_elements(By.TAG_NAME, "tr")
            for r in rows:
                cols = r.find_elements(By.TAG_NAME, "td")
                # Basado en tu foto: ETA(0), Buque(6), Consigna(10), Atraque(11)
                if len(cols) >= 11:
                    eta_str = cols[0].text.strip()
                    nombre = cols[6].text.strip()
                    muelle = cols[11].text.strip()
                    
                    if "/" in eta_str and nombre:
                        # Comprobar si está dentro de las próximas 8 horas
                        try:
                            # Formato esperado: "24/03/26 21:00"
                            eta_dt = datetime.strptime(eta_str, "%d/%m/%y %H:%M")
                            if now <= eta_dt <= limit_time:
                                plan_msg += f"• *{nombre}* | ETA: {eta_str}\n  Muelle: {muelle}\n"
                                found_plan = True
                        except: pass
                        
                        # Notificar nueva planificación (cualquier hora)
                        sid = f"PLAN_{nombre}_{eta_str}".replace(" ","_")
                        if sid not in history:
                            send_telegram(f"🚢 *Nueva Planificación Detectada*\nBuque: {nombre}\nETA: {eta_str}\nMuelle: {muelle}")
                            save_id(sid)
                            history.add(sid)

        # Enviar resúmenes solo si hay algo relevante y el usuario lo quiere (lo podrias activar con un flag)
        # Por ahora lo dejamos automático para tu control
        
    except Exception as e: logging.error(f"Error: {e}")
    finally: driver.quit()

if __name__ == "__main__":
    run()
