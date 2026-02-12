# Reemplaza el contenido completo de create_webhooks.py con esta versión
import requests
import logging
from config import (
    TIENDANUBE_API_BASE_URL,
    TIENDANUBE_STORE_ID,
    TIENDANUBE_ACCESS_TOKEN,
    TIENDANUBE_USER_AGENT
)

# --- Configuración ---
# Pega aquí la URL completa de tu API Gateway que apunta a Pombot-Webhook-Processor
WEBHOOK_URL = "https://j4k112ym6i.execute-api.us-east-1.amazonaws.com/tiendanube-webhook" 

# Eventos recomendados por el soporte para una gestión completa
EVENTS_TO_SUBSCRIBE = [
    "order/paid",
    "order/created",
    "order/cancelled",
    "order/updated"
]

# --- Fin de la Configuración ---

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def create_webhook(event: str, url: str):
    """Hace la llamada a la API para crear un webhook para un evento específico."""
    
    api_url = f"{TIENDANUBE_API_BASE_URL}{TIENDANUBE_STORE_ID}/webhooks"
    
    headers = {
        "Authentication": f"bearer {TIENDANUBE_ACCESS_TOKEN}",
        "User-Agent": TIENDANUBE_USER_AGENT,
        "Content-Type": "application/json"
    }
    
    payload = { "event": event, "url": url }
    
    try:
        logging.info(f"Intentando crear webhook para el evento: '{event}'...")
        response = requests.post(api_url, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        
        logging.info(f"✅ ¡Éxito! Webhook para '{event}' creado. ID: {response.json().get('id')}")
        return True
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 422 and "already been taken" in e.response.text:
            logging.warning(f"⚠️  Aviso: El webhook para '{event}' en esta URL ya existe. No se necesita acción.")
            return True
        else:
            logging.error(f"❌ Error al crear webhook para '{event}': {e.response.status_code} - {e.response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Error de conexión al crear webhook para '{event}': {e}")
        return False

if __name__ == "__main__":
    if "xxxx" in WEBHOOK_URL:
        logging.error("¡ACCIÓN REQUERIDA! Edita el archivo 'create_webhooks.py' y reemplaza la URL de ejemplo por la tuya.")
    else:
        logging.info("--- Iniciando Creación/Verificación de Webhooks en TiendaNube ---")
        success_count = 0
        for event in EVENTS_TO_SUBSCRIBE:
            if create_webhook(event, WEBHOOK_URL):
                success_count += 1
        
        logging.info("--- Proceso Finalizado ---")
        if success_count == len(EVENTS_TO_SUBSCRIBE):
            logging.info("🎉 ¡Todos los webhooks necesarios fueron creados o ya existían! La integración está lista.")
        else:
            logging.error("Algunos webhooks no se pudieron crear. Revisa los mensajes de error de arriba.")