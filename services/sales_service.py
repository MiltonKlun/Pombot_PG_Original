# services/sales_service.py
"""
Sales recording: generic transaction helper and the main add_sale function.
"""
import logging
from datetime import datetime
from typing import Dict, Any

from config import SALES_SHEET_BASE_NAME, SALES_HEADERS
from common.utils import parse_float
from services.tiendanube_service import update_tiendanube_stock
from services.sheets_connection import (
    get_or_create_monthly_sheet, get_value_from_dict_insensitive
)
from services.products_service import (
    update_product_stock, invalidate_products_cache
)

logger = logging.getLogger(__name__)


def add_transaction_generic(sheet_base_name: str, headers: list, row_data: list) -> dict:
    """Appends a row to the correct monthly sheet. Used by add_sale and others."""
    worksheet = get_or_create_monthly_sheet(sheet_base_name, headers)
    if not worksheet:
        raise ConnectionError(f"Hoja para '{sheet_base_name}' no disponible.")
    try:
        worksheet.append_row(row_data, value_input_option='USER_ENTERED')
        logger.info(f"Transacción registrada en '{worksheet.title}': {row_data}")
        return {"sheet_title": worksheet.title, "data": row_data}
    except Exception as e:
        logger.error(f"Error al añadir transacción en '{worksheet.title}'", exc_info=True)
        raise


def add_sale(variant_details: dict, quantity: int, client_name: str) -> dict:
    """Records a sale, updates stock in both Sheets and TiendaNube."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    variant_desc_parts = []
    for i in range(1, 4):
        val = variant_details.get(f"Opción {i}: Valor")
        if val and str(val).strip():
            variant_desc_parts.append(str(val))
    variant_description = ", ".join(variant_desc_parts)
    total_price_sale = float(variant_details.get("Precio Final", 0.0) or 0.0) * quantity
    row_data = [
        timestamp,
        variant_details["Producto"],
        variant_description,
        client_name,
        variant_details["Categoría"],
        quantity,
        variant_details.get("Precio Unitario", 0.0),
        variant_details.get("%", 0.0),
        variant_details.get("Descuento", 0.0),
        total_price_sale
    ]
    result = add_transaction_generic(SALES_SHEET_BASE_NAME, SALES_HEADERS, row_data)
    current_stock = int(variant_details.get("Stock", 0) or 0)
    new_stock_level = current_stock - quantity
    stock_updated_on_sheet = update_product_stock(variant_details["row_number"], new_stock_level)
    if stock_updated_on_sheet:
        invalidate_products_cache()
    product_id = get_value_from_dict_insensitive(variant_details, "ID Producto")
    variant_id = get_value_from_dict_insensitive(variant_details, "ID Variante")
    if product_id and variant_id:
        update_tiendanube_stock(int(product_id), int(variant_id), new_stock_level)
    else:
        logger.error(f"No se pudo actualizar TiendaNube: Faltan product_id o variant_id en variant_details.")
    return {
        "timestamp": timestamp,
        "product_name": variant_details["Producto"],
        "variant_description": variant_description,
        "client_name": client_name,
        "quantity": quantity,
        "total_sale_price": total_price_sale,
        "sheet_title": result["sheet_title"],
        "remaining_stock": new_stock_level if stock_updated_on_sheet else "Error al actualizar"
    }
