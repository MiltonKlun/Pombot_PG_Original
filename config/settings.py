import os
import json
import boto3
from google.oauth2.service_account import Credentials

print("INFO: Cargando configuración (settings)...")

CONFIG = {}

def _load_secrets():
    """Loads secrets from AWS Secrets Manager into CONFIG dict."""
    global CONFIG
    secret_name = os.environ.get("SECRET_NAME")
    if not secret_name:
        print("ADVERTENCIA: La variable de entorno SECRET_NAME no está configurada.")
        return
    try:
        session = boto3.session.Session()
        client = session.client(service_name='secretsmanager')
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        secrets = json.loads(get_secret_value_response['SecretString'])
        CONFIG.update(secrets)
        if 'GOOGLE_CREDENTIALS_JSON' in CONFIG:
            credentials_path = "/tmp/bot-credentials.json"
            with open(credentials_path, "w") as f:
                f.write(CONFIG['GOOGLE_CREDENTIALS_JSON'])
            CONFIG['SERVICE_ACCOUNT_FILE'] = credentials_path
    except Exception as e:
        print(f"ERROR CRÍTICO: No se pudieron cargar los secretos desde AWS Secrets Manager: {e}")

_load_secrets()

# --- Telegram, Google Sheets, TiendaNube ---
BOT_TOKEN = CONFIG.get("BOT_TOKEN", "INVALID_TOKEN")
CHAT_ID = CONFIG.get("CHAT_ID")
ALLOWED_USER_IDS_STR = CONFIG.get("ALLOWED_USER_IDS", "")
INACTIVITY_TIMEOUT_SECONDS = int(CONFIG.get("INACTIVITY_TIMEOUT_SECONDS", 180))
SHEET_ID = CONFIG.get("SHEET_ID")
SERVICE_ACCOUNT_FILE = CONFIG.get("SERVICE_ACCOUNT_FILE", "bot-credentials.json")
TIENDANUBE_STORE_ID_STR = CONFIG.get("TIENDANUBE_STORE_ID", "0")
TIENDANUBE_ACCESS_TOKEN = CONFIG.get("TIENDANUBE_ACCESS_TOKEN")
TIENDANUBE_USER_AGENT = CONFIG.get("TIENDANUBE_USER_AGENT", "Pombot/1.0")
TIENDANUBE_API_BASE_URL = "https://api.tiendanube.com/v1/"

# --- Processed values ---
try:
    TIENDANUBE_STORE_ID = int(TIENDANUBE_STORE_ID_STR)
    cleaned_ids_str = ALLOWED_USER_IDS_STR.strip().strip('[]').strip()
    if cleaned_ids_str:
        ALLOWED_USER_IDS = [int(uid.strip()) for uid in cleaned_ids_str.split(',')]
    else:
        ALLOWED_USER_IDS = []
except (ValueError, TypeError) as e:
    print(f"ADVERTENCIA: No se pudo procesar IDs o Store ID: {e}")
    ALLOWED_USER_IDS = []
    TIENDANUBE_STORE_ID = 0

google_credentials = None
try:
    if SERVICE_ACCOUNT_FILE:
        google_credentials = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=["https://www.googleapis.com/auth/spreadsheets"])
        print("INFO: Credenciales de Google cargadas exitosamente.")
except Exception as e:
    print(f"ERROR: No se pudieron cargar las credenciales de Google desde el archivo '{SERVICE_ACCOUNT_FILE}': {e}")
