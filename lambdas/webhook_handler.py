# lambdas/webhook_handler.py
import logging
import json
from datetime import datetime
import requests

from config import (
    TIENDANUBE_API_BASE_URL, TIENDANUBE_STORE_ID, TIENDANUBE_ACCESS_TOKEN, 
    TIENDANUBE_USER_AGENT, SALES_SHEET_BASE_NAME, SALES_HEADERS,
    EXPENSES_SHEET_BASE_NAME, EXPENSES_HEADERS
)
from sheet import (
    connect_globally_to_sheets, get_or_create_monthly_sheet,
    add_sale, add_expense, log_webhook_event, invalidate_products_cache
)
from common.utils import parse_float

logger = logging.getLogger("webhook_handler")
logger.setLevel(logging.INFO)

def get_full_order_details(order_id: int) -> dict:
    """Obtiene los detalles completos de una orden, incluyendo productos y transacciones."""
    if not order_id: return {}
    
    url = f"{TIENDANUBE_API_BASE_URL}{TIENDANUBE_STORE_ID}/orders/{order_id}"
    headers = {
        "Authentication": f"bearer {TIENDANUBE_ACCESS_TOKEN}",
        "User-Agent": TIENDANUBE_USER_AGENT
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error al obtener los detalles de la orden {order_id}: {e}")
        return {}

def process_order_paid(order_data: dict):
    """Procesa una orden pagada, registra la venta y las comisiones."""
    order_id = order_data.get('id')
    customer_name = order_data.get('customer', {}).get('name', 'Cliente TiendaNube')
    
    # Suponemos que la información relevante está en la primera transacción
    transactions = order_data.get('transactions', [])
    if not transactions:
        logger.warning(f"Orden {order_id} pagada pero sin transacciones. Se omite.")
        return

    main_transaction = transactions[0]
    total_paid = parse_float(str(main_transaction.get('captured_amount', '0.0')))
    
    # Concatenar los nombres de los productos para la descripción
    product_names = ", ".join([p.get('name', 'N/A') for p in order_data.get('products', [])])
    
    # En TiendaNube, la comisión no viene explícitamente en la API de la orden.
    # El `total_paid` ya es el monto bruto. La conciliación del neto se haría
    # al procesar el extracto de Mercado Pago.
    # Por ahora, registramos la venta por el total cobrado.
    
    # add_sale necesita un diccionario `variant_details`. Lo simulamos.
    simulated_details = {
        'Producto': product_names[:255], # Limitar longitud
        'Categoria': 'TiendaNube Venta Online',
        'Precio Final': total_paid,
        'Precio Unitario': total_paid,
        '%': 0,
        'Descuento': 0,
        # Necesitamos un 'row_number' falso para que la función no falle al intentar actualizar stock
        # que no existe. La mejor solución es refactorizar `add_sale` en el futuro.
        # Por ahora, esta es una solución temporal que no actualiza el stock.
        'row_number': -1 
    }
    
    add_sale(
        variant_details=simulated_details,
        quantity=sum(p.get('quantity', 0) for p in order_data.get('products', [])),
        client_name=customer_name
    )
    
    # Inmediatamente después de una venta online, invalidamos el caché de productos
    # para que el bot tenga el stock más actualizado posible.
    invalidate_products_cache()
    
    logger.info(f"Venta online de la orden #{order_id} registrada por un total de ${total_paid}.")

def process_webhook_event(event_data: dict):
    """Procesa el webhook, aplicando lógica de duplicados y orden."""
    store_id = event_data.get('store_id')
    event_type = event_data.get('event')
    entity_id = event_data.get('id')
    
    # Construir un ID único para el evento para evitar duplicados
    unique_event_id = f"{store_id}-{event_type}-{entity_id}"
    
    # 1. VERIFICAR DUPLICADOS
    is_new_event = log_webhook_event(unique_event_id, event_type, entity_id)
    if not is_new_event:
        return # Si no es nuevo, detenemos el procesamiento aquí.

    # 2. PROCESAR EVENTOS DE PAGO
    if event_type == 'order/paid':
        # Obtenemos los detalles completos de la orden AHORA, sin depender de 'order/created'
        order_details = get_full_order_details(entity_id)
        if order_details:
            process_order_paid(order_details)
        else:
            logger.error(f"No se pudieron obtener los detalles de la orden pagada #{entity_id}.")
            
    # Aquí puedes añadir lógica para otros eventos en el futuro
    # elif event_type == 'order/cancelled':
    #     ...

def lambda_handler(event, context):
    """Punto de entrada para la Lambda que recibe los webhooks."""
    logger.info(f"Webhook Lambda invocado con el evento: {event}")
    
    if not connect_globally_to_sheets():
        logger.critical("No se pudo conectar a Google Sheets. Abortando.")
        return {'statusCode': 500, 'body': json.dumps('Error de conexión a Sheets')}
        
    try:
        webhook_body = json.loads(event.get('body', '{}'))
        process_webhook_event(webhook_body)
        
        return {'statusCode': 200, 'body': json.dumps('Webhook procesado')}
    except Exception as e:
        logger.error(f"Error fatal en el webhook_handler: {e}", exc_info=True)
        return {'statusCode': 500, 'body': json.dumps('Error interno al procesar')}