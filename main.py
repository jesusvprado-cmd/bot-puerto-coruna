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

# --- CONFIGURACIÓN DE SECRETOS ---
TOKEN = os.getenv('TELEGRAM_TOKEN')
MY_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
USER_NEMO = os.getenv('NEMO_USER')
PASS_NEMO = os.getenv('NEMO_PASS')
AVISADOS_FILE = "avisados.txt"

def bot_send(mensaje):
    """Envía un mensaje a Telegram"""
    if not TOKEN or not MY_CHAT_ID:
        print("Faltan los secretos de Telegram.")
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": MY_CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}
    try:
        r = requests.post(url, json=payload)
        print(f"Resultado envío Telegram: {r.status_code}")
    except Exception as e:
        print(f"Error enviando Telegram: {e}")

def get_nemo_data_selenium():
    """Navega por la web y extrae los barcos"""
    print("Iniciando navegador invisible...")
    options = Options()
    options.add_argument("--headless") # Sin ventana
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument('--ignore-certificate-errors') # Salta el error de privacidad
    options.add_argument('--ignore-ssl-errors')
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    barcos = []

    try:
        # 1. LOGIN
        print("Paso 1: Realizando login...")
        driver.get("https://nemopilots.com/login")
        
        wait = WebDriverWait(driver, 20)
        user_field = wait.until(EC.presence_of_element_located((By.NAME, "_username")))
        pass_field = driver.find_element(By.NAME, "_password")
        
        user_field.send_keys(USER_NEMO)
        pass_field.send_keys(PASS_NEMO)
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        
        # 2. ACCESO A DATOS
        print("Paso 2: Entrando en Planificación...")
        time.sleep(5)
        driver.get("https://nemopilots.com/planificacion/")
        
        # Espera estratégica por el circulito de carga del vídeo (20 seg)
        print("Esperando 20 segundos a que el puerto cargue los datos...")
        time.sleep(20) 

        # 3. DETECTOR DE MARCOS (IFRAMES)
        # Si la tabla está vacía, buscamos dentro de iframes
        filas = driver.find_elements(By.TAG_NAME, "tr")
        
        if len(filas) < 5:
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            if iframes:
                print(f"Detectados {len(iframes)} marcos. Buscando datos dentro...")
                for i in range(len(iframes)):
                    driver.switch_to.frame(i)
                    filas_internas = driver.find_elements(By.TAG_NAME, "tr")
                    if len(filas_internas) > 5:
                        print(f"¡Datos localizados en el marco {i}!")
                        filas = filas_internas
                        break
                    driver.switch_to.default_content()

        # 4. PROCESAR FILAS
        print(f"Analizando {len(filas)} filas detectadas...")
        for f in filas:
            cols = f.find_elements(By.TAG_NAME, "td")
            if len(cols) >= 13: # Columnas mínimas según la web de Nemo
                datos = [c.text.strip() for c in cols]
                # ETA=0, Nombre=3, Muelle=11, Operación=13
                if len(datos[3]) > 2: 
                    barcos.append({
                        'eta': datos[0],
                        'nombre': datos[3],
                                            'consignatario': datos[9] if len(datos) > 9 else "S/D",
                        'muelle': datos[11] if len(datos) > 11 else "S/D",
                        'op': datos[13] if len(datos) > 13 else "S/D"
                    })
    except Exception as e:
        print(f"⚠️ ERROR DURANTE EL PROCESO: {e}")
    finally:
        driver.quit()
    return barcos

if __name__ == "__main__":
    ahora = datetime.now().strftime('%d/%m/%Y %H:%M')
    print(f"--- INICIO EJECUCIÓN: {ahora} ---")
    
    lista_barcos = get_nemo_data_selenium()
    
    # Cargar historial para no repetir avisos
    avisados = set()
    if os.path.exists(AVISADOS_FILE):
        with open(AVISADOS_FILE, "r") as f:
            avisados = set(f.read().splitlines())

    nuevos_avisos = 0
    for b in lista_barcos:
        id_unico = f"{b['nombre']}-{b['eta']}"
        
        if id_unico not in avisados:
            print(f"Nuevo barco encontrado: {b['nombre']}")
            mensaje = (f"🚢 **NUEVA ENTRADA DETECTADA**\n\n"
                       f"🔹 *Buque:* {b['nombre']}\n"
                       f"🕒 *ETA:* {b['eta']}\n"
                       f"⚓ *Muelle:* {b['muelle']}\n"
                                               f" *Consignatario:* {b['consignatario']}\n"
                       f"🏗️ *Op:* {b['op']}")
            
            bot_send(mensaje)
            avisados.add(id_unico)
            nuevos_avisos += 1

    # Guardar la memoria para la siguiente hora
    with open(AVISADOS_FILE, "w") as f:
        f.write("\n".join(avisados))
    
    print(f"--- FIN: {nuevos_avisos} barcos nuevos notificados ---")
