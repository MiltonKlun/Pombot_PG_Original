# lambda_sync.py
import logging
import os
from config import ( # Assuming config.py can be packaged or its values set as env vars
    BOT_TOKEN, ALLOWED_USER_IDS # These might be needed if you want Lambda to send a Telegram notification
)
import asyncio
from services.tiendanube_service import get_tiendanube_products
from sheet import update_products_from_tiendanube, IS_SHEET_CONNECTED, connect_globally_to_sheets
from telegram import Bot # For optional notifications

# --- Lambda Specific Logging ---
# AWS Lambda automatically captures print() statements and logging.
# Configuring a logger specifically for Lambda context.
logger = logging.getLogger("lambda_sync")
logger.setLevel(logging.INFO) # Adjust level as needed (INFO, DEBUG, ERROR)

# --- Environment Variables (Recommended for Lambda) ---
# You should set these as environment variables in your Lambda configuration
# instead of relying on a packaged config.py for sensitive data like tokens.
# For this example, we assume config.py might be packaged, or these are fetched similarly.
# If using environment variables:
# TIENDANUBE_STORE_ID_ENV = os.environ.get('TIENDANUBE_STORE_ID')
# TIENDANUBE_ACCESS_TOKEN_ENV = os.environ.get('TIENDANUBE_ACCESS_TOKEN')
# TIENDANUBE_USER_AGENT_ENV = os.environ.get('TIENDANUBE_USER_AGENT')
# SHEET_ID_ENV = os.environ.get('SHEET_ID')
# SERVICE_ACCOUNT_FILE_PATH_ENV = os.environ.get('LAMBDA_TASK_ROOT', '.') + "/bot-credentials.json"
# BOT_TOKEN_ENV = os.environ.get('BOT_TOKEN')
# NOTIFY_USER_ID_ENV = os.environ.get('NOTIFY_USER_ID') # Telegram User ID to notify on success/failure

# Reemplaza la función send_telegram_notification existente por esta
async def send_telegram_notification(message: str, chat_id_to_notify: str | int | None):
    """Optional: Sends a notification message via Telegram asynchronously."""
    if not BOT_TOKEN or BOT_TOKEN == "INVALID_TOKEN":
        logger.warning("Bot token for notifications is not configured. Skipping notification.")
        return
    if not chat_id_to_notify:
        logger.warning("No chat_id_to_notify provided for notification. Skipping.")
        return
        
    try:
        bot = Bot(token=BOT_TOKEN)
        # Usamos await para ejecutar la función asíncrona
        await bot.send_message(chat_id=int(chat_id_to_notify), text=message)
        logger.info(f"Notification sent to {chat_id_to_notify}.")
    except Exception as e:
        logger.error(f"Failed to send Telegram notification: {e}", exc_info=True)

def lambda_handler(event, context):
    """
    AWS Lambda handler function.
    This function will be executed when the Lambda is triggered (e.g., by EventBridge schedule).
    """
    logger.info("Lambda sync_products_handler invoked.")
    
    # --- Crucial: Ensure Google Sheets Connection ---
    # The global IS_SHEET_CONNECTED might not be set in Lambda's stateless environment correctly
    # without an explicit call or if modules are re-imported.
    # Forcing a connection check/attempt here if not already connected.
    if not IS_SHEET_CONNECTED:
        logger.info("Lambda: Google Sheets not connected, attempting to connect.")
        if not connect_globally_to_sheets(): # Explicitly call to connect
            error_msg = "Lambda: CRITICAL - Failed to connect to Google Sheets. Sync aborted."
            logger.critical(error_msg)
            # Optionally notify admin via Telegram if configured
            # send_telegram_notification(error_msg, os.environ.get('ADMIN_TELEGRAM_ID'))
            return {'statusCode': 500, 'body': error_msg}

    # Determine which user ID to notify (e.g., the first allowed user)
    # This is just an example; you might have a dedicated admin ID.
    user_to_notify = str(ALLOWED_USER_IDS[0]) if ALLOWED_USER_IDS else None

    try:
        logger.info("Lambda: Iniciando obtención de productos desde TiendaNube...")
        tiendanube_products_data = get_tiendanube_products()
        logger.info(f"Lambda: Se obtuvieron {len(tiendanube_products_data)} productos de TiendaNube.")

        # update_products_from_tiendanube handles empty product list message internally
        logger.info("Lambda: Actualizando hoja 'Productos' en Google Sheets...")
        success, message = update_products_from_tiendanube(tiendanube_products_data)
        
        final_message = ""
        if success:
            final_message = f"✅ Lambda Sync: ¡Sincronización completada! {message}"
            logger.info(final_message)
            asyncio.run(send_telegram_notification(final_message, user_to_notify))
            return {'statusCode': 200, 'body': final_message}
        else:
            final_message = f"⚠️ Lambda Sync: Error durante la sincronización con Google Sheets: {message}"
            logger.error(final_message)
            asyncio.run(send_telegram_notification(final_message, user_to_notify))
            return {'statusCode': 500, 'body': final_message}

    except ValueError as e:
        error_msg = f"⚠️ Lambda Sync: Error de configuración/datos: {e}"
        logger.error(error_msg, exc_info=True)
        asyncio.run(send_telegram_notification(error_msg, user_to_notify))
        return {'statusCode': 500, 'body': error_msg}
    except ConnectionError as e:
        error_msg = f"🔌 Lambda Sync: Error de conexión: {e}"
        logger.error(error_msg, exc_info=True)
        asyncio.run(send_telegram_notification(error_msg, user_to_notify))
        return {'statusCode': 500, 'body': error_msg}
    except Exception as e:
        error_msg = f"💥 Lambda Sync: Error inesperado al sincronizar productos: {e}"
        logger.error(error_msg, exc_info=True)
        asyncio.run(send_telegram_notification(error_msg, user_to_notify))
        return {'statusCode': 500, 'body': error_msg}

# Example of how you might test this locally if you set up environment variables
# or have config.py accessible in the same way Lambda would.
if __name__ == "__main__":
    logger.info("Executing lambda_handler locally for testing...")
    # To test locally, you might need to mock the event and context,
    # and ensure all configurations (like SERVICE_ACCOUNT_FILE path) are correct for local execution.
    # Make sure 'bot-credentials.json' is in the root or path is correctly set for local test.
    
    # Example: If you want to use env vars for local testing:
    # os.environ['TIENDANUBE_STORE_ID'] = "your_store_id" 
    # ... (set other necessary env vars from your config.py for testing)

    # A simple direct call for testing (assuming config.py is used and SERVICE_ACCOUNT_FILE is found)
    if not IS_SHEET_CONNECTED: # Ensure connection before local test
        if not connect_globally_to_sheets():
            print("Local test: Failed to connect to Google Sheets. Aborting.")
            exit()

    result = lambda_handler({}, {}) # Empty event and context
    print(f"Local test execution result: {result}")