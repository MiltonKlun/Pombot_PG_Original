# services/products_service.py
"""
Product data management: caching, querying categories/variants, stock updates,
and TiendaNube synchronization.
"""
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

from config import PRODUCTOS_SHEET_NAME, PRODUCTOS_HEADERS
from common.utils import normalize_text, parse_float
from services.tiendanube_service import update_tiendanube_stock
from services.sheets_connection import (
    is_connected,
    _get_or_create_worksheet, apply_table_formatting,
    get_value_from_dict_insensitive
)

logger = logging.getLogger(__name__)

# --- Product cache ---
products_cache: Dict[str, Any] = {'data': None, 'timestamp': None}
CACHE_TTL_SECONDS = 60


def invalidate_products_cache() -> None:
    """Clears the in-memory product cache (in-place to preserve references)."""
    logger.info("Invalidando caché de productos.")
    products_cache.update({'data': None, 'timestamp': None})


def get_product_sheet():
    """Gets (or creates) the Productos worksheet."""
    return _get_or_create_worksheet(PRODUCTOS_SHEET_NAME, PRODUCTOS_HEADERS)


def get_all_products_data_cached() -> List[Dict[str, Any]]:
    """Returns all product records, using an in-memory cache with TTL."""
    now = datetime.now()
    if products_cache['data'] is not None and products_cache['timestamp']:
        if (now - products_cache['timestamp']).total_seconds() < CACHE_TTL_SECONDS:
            logger.info(f"Usando caché de productos ({len(products_cache['data'])} registros).")
            return products_cache['data']
    product_sheet = get_product_sheet()
    if not product_sheet:
        return []
    try:
        logger.info("Refrescando caché de productos desde Google Sheets...")
        all_records = product_sheet.get_all_records()
        logger.info(f"gspread.get_all_records() devolvió {len(all_records)} registros.")
        if all_records and isinstance(all_records, list):
            logger.info(f"Ejemplo del primer registro obtenido: {all_records[0]}")
            logger.info(f"Claves del primer registro: {list(all_records[0].keys())}")
        for i, record in enumerate(all_records):
            record['row_number'] = i + 2
        products_cache['data'] = all_records
        products_cache['timestamp'] = now
        return all_records
    except Exception as e:
        logger.error(f"Error obteniendo todos los datos de productos de la hoja", exc_info=True)
        return []


def get_product_categories() -> list[str]:
    """Returns a sorted list of unique product categories."""
    all_products = get_all_products_data_cached()
    if not all_products:
        return []
    seen_categories = set()
    for product in all_products:
        category_value = get_value_from_dict_insensitive(product, "Categoría")
        if category_value is not None:
            category_str = str(category_value).strip()
            if category_str:
                seen_categories.add(category_str)
    logger.info(f"Categorías únicas procesadas: {seen_categories}")
    return sorted(list(seen_categories))


def get_products_by_category(selected_category: str) -> list[str]:
    """Returns a sorted list of product names for a given category."""
    all_products = get_all_products_data_cached()
    if not all_products:
        return []
    normalized_selected_category = normalize_text(selected_category)
    products_in_category = set()
    for product in all_products:
        category_value = get_value_from_dict_insensitive(product, "Categoría")
        if category_value is not None and normalize_text(str(category_value)) == normalized_selected_category:
            product_name = get_value_from_dict_insensitive(product, "Producto")
            if product_name and str(product_name).strip():
                products_in_category.add(str(product_name).strip())
    return sorted(list(products_in_category))


def get_product_options(product_name: str, option_number: int, prior_selections: Dict[str, str] = None) -> Tuple[str, List[str]]:
    """Returns the option name and available values for a given product and option level."""
    all_products = get_all_products_data_cached()
    if not all_products:
        return "", []
    normalized_product_name = normalize_text(product_name)
    option_name_header = f"Opción {option_number}: Nombre"
    option_value_header = f"Opción {option_number}: Valor"
    option_name = ""
    available_values = set()
    for product in all_products:
        if normalize_text(str(get_value_from_dict_insensitive(product, "Producto") or '')) != normalized_product_name:
            continue
        match = True
        if prior_selections:
            for key, value in prior_selections.items():
                if normalize_text(str(get_value_from_dict_insensitive(product, key) or '')) != normalize_text(value):
                    match = False
                    break
        if match:
            current_option_name = str(get_value_from_dict_insensitive(product, option_name_header) or '').strip()
            current_option_value = str(get_value_from_dict_insensitive(product, option_value_header) or '').strip()
            if current_option_name and not option_name:
                option_name = current_option_name
            if current_option_value:
                available_values.add(current_option_value)
    return option_name, sorted(list(available_values))


def get_variant_details(product_name: str, selections: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """Finds and returns the full details of a specific product variant."""
    all_products = get_all_products_data_cached()
    if not all_products:
        return None
    normalized_product_name = normalize_text(product_name)
    normalized_selections = {key: normalize_text(value) for key, value in selections.items()}
    for record in all_products:
        if normalize_text(str(get_value_from_dict_insensitive(record, "Producto") or '')) != normalized_product_name:
            continue
        match = True
        for key, value in normalized_selections.items():
            if normalize_text(str(get_value_from_dict_insensitive(record, key) or '')) != value:
                match = False
                break
        if match:
            clean_record = {
                'Producto': get_value_from_dict_insensitive(record, 'Producto'),
                'ID Producto': get_value_from_dict_insensitive(record, 'ID Producto'),
                'ID Variante': get_value_from_dict_insensitive(record, 'ID Variante'),
                'Categoría': get_value_from_dict_insensitive(record, 'Categoría'),
                'Opción 1: Valor': get_value_from_dict_insensitive(record, 'Opción 1: Valor'),
                'Opción 2: Valor': get_value_from_dict_insensitive(record, 'Opción 2: Valor'),
                'Opción 3: Valor': get_value_from_dict_insensitive(record, 'Opción 3: Valor'),
                'Precio Final': parse_float(str(get_value_from_dict_insensitive(record, 'Precio Final') or '0')),
                'Precio Unitario': parse_float(str(get_value_from_dict_insensitive(record, 'Precio Unitario') or '0')),
                '%': parse_float(str(get_value_from_dict_insensitive(record, '%') or '0')),
                'Descuento': parse_float(str(get_value_from_dict_insensitive(record, 'Descuento') or '0')),
                'Stock': int(parse_float(str(get_value_from_dict_insensitive(record, 'Stock') or '0'))),
                'row_number': record['row_number']
            }
            return clean_record
    logger.warning(f"Variante no encontrada para '{product_name}' con selecciones {selections}")
    return None


def update_product_stock(row_number: int, new_stock: int) -> bool:
    """Updates the stock value for a specific product row in the sheet."""
    product_sheet = get_product_sheet()
    if not product_sheet:
        logger.error("No se pudo acceder a la hoja de productos para actualizar el stock.")
        return False
    try:
        stock_col_index = PRODUCTOS_HEADERS.index("Stock") + 1
        product_sheet.update_cell(row_number, stock_col_index, new_stock)
        logger.info(f"Stock actualizado en la fila {row_number} a {new_stock}.")
        return True
    except (ValueError, IndexError, Exception) as e:
        logger.error(f"Error al actualizar el stock en la fila {row_number}", exc_info=True)
        return False


def update_products_from_tiendanube(products_data: list) -> tuple[bool, str]:
    """Replaces all product data in the sheet with fresh data from TiendaNube."""
    if not is_connected():
        msg = "No hay conexión a Google Sheets para actualizar productos."
        return False, msg
    product_sheet = get_product_sheet()
    if not product_sheet:
        msg = f"No se pudo acceder o crear la hoja '{PRODUCTOS_SHEET_NAME}'."
        return False, msg
    try:
        logger.info(f"Actualizando la hoja '{PRODUCTOS_SHEET_NAME}'...")
        product_sheet.clear()
        product_sheet.append_row(PRODUCTOS_HEADERS, value_input_option='USER_ENTERED')
        if products_data:
            product_sheet.append_rows(products_data, value_input_option='USER_ENTERED')
            msg = f"Hoja '{PRODUCTOS_SHEET_NAME}' actualizada con {len(products_data)} variantes."
        else:
            msg = "No hay productos de TiendaNube para añadir a la hoja."
        apply_table_formatting(product_sheet, len(PRODUCTOS_HEADERS))
        invalidate_products_cache()
        return True, msg
    except Exception as e:
        msg = f"Error inesperado al actualizar la hoja de productos"
        logger.error(msg, exc_info=True)
        return False, f"{msg}: {e}"
