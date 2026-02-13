import logging
import asyncio
import json
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    PicklePersistence
)
from config import BOT_TOKEN
from sheet import IS_SHEET_CONNECTED, connect_globally_to_sheets
from handlers.core import unknown_command, sync_products_command
from handlers.conversation import conv_handler

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

if not IS_SHEET_CONNECTED:
    connect_globally_to_sheets()

persistence = PicklePersistence(filepath="/tmp/pombot_persistence")
application = Application.builder().token(BOT_TOKEN).persistence(persistence).build()

application.add_handler(conv_handler)
application.add_handler(CommandHandler("sync_products", sync_products_command))
application.add_handler(MessageHandler(filters.COMMAND, unknown_command))

async def process_telegram_update(update_json):
    async with application:
        await application.initialize()
        update = Update.de_json(update_json, application.bot)
        await application.process_update(update)
        await application.shutdown()

def lambda_handler(event, context):
    logger.info(f"Evento crudo recibido de API Gateway: {event}")
    try:
        if not IS_SHEET_CONNECTED:
            logger.info("Conexión a Sheets no detectada. Intentando conectar...")
            if not connect_globally_to_sheets():
                 return {
                    'statusCode': 500,
                    'body': json.dumps('Error Critico: Fallo la conexion a Google Sheets (Ver logs)')
                }
    except Exception as e:
        logger.error(f"Error intentando conectar a Sheets en lambda_handler: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error de Conexión: {str(e)}')
        }
    try:
        if 'body' in event:
            try:
                if isinstance(event['body'], str):
                    update_json = json.loads(event['body'])
                else:
                    update_json = event['body']
            except json.JSONDecodeError:
                logger.error("El body del evento no es un JSON válido.")
                return {'statusCode': 400, 'body': 'Invalid JSON'}
        else:
            update_json = event
            
        if not update_json: 
             return {'statusCode': 200, 'body': 'Empty event ignored'}

        if 'update_id' not in update_json:
             logger.warning("El evento recibido no parece ser un Update de Telegram válido (falta update_id).")
             return {'statusCode': 400, 'body': 'Invalid Update Format: Missing update_id'}

        asyncio.run(process_telegram_update(update_json))
        return {
            'statusCode': 200,
            'body': json.dumps('Update procesado')
        }
    except Exception as e:
        logger.error(f"Error en el lambda_handler: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps('Error procesando el update')
        }
