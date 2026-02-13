# services/sheets_connection.py
"""
Core Google Sheets connection, global state, and worksheet helper functions.
This module manages the singleton connection to Google Sheets and provides
utilities for creating/accessing worksheets.
"""
import gspread
from gspread.utils import rowcol_to_a1
from datetime import datetime, timedelta
import logging
from typing import Optional, List, Dict, Any

from config import (
    google_credentials, SHEET_ID,
    WHOLESALE_SHEET_BASE_NAME, WHOLESALE_HEADERS,
    PROCESSED_EVENTS_SHEET_NAME, PROCESSED_EVENTS_HEADERS,
    WEBHOOK_LOGS_SHEET_NAME,
    get_sheet_name_for_month
)
from common.utils import normalize_text, parse_float

logger = logging.getLogger(__name__)

# --- Global connection state ---
gc: Optional[gspread.Client] = None
spreadsheet: Optional[gspread.Spreadsheet] = None


def connect_globally_to_sheets() -> bool:
    """Establishes a global connection to Google Sheets."""
    global gc, spreadsheet, IS_SHEET_CONNECTED
    if gc and spreadsheet:
        return True
    if not google_credentials:
        logger.critical("Credenciales de Google no disponibles en config.py.")
        return False
    try:
        gc = gspread.authorize(google_credentials)
        spreadsheet = gc.open_by_key(SHEET_ID)
        IS_SHEET_CONNECTED = True
        logger.info("Conexión global con Google Sheets establecida.")
        return True
    except gspread.exceptions.SpreadsheetNotFound:
        logger.critical(f"Spreadsheet con ID '{SHEET_ID}' no encontrado.")
        return False
    except Exception as e:
        logger.critical(f"Error CRÍTICO inicializando conexión global Sheets: {e}", exc_info=True)
        return False


IS_SHEET_CONNECTED = False


def get_value_from_dict_insensitive(data: dict, target_key: str) -> Any:
    """
    Busca una clave en el diccionario ignorando mayúsculas/minúsculas y acentos
    para evitar fallos por diferencias de escritura en las cabeceras.
    """
    if not isinstance(data, dict) or not isinstance(target_key, str):
        return None
    target_key_normalized = normalize_text(target_key)
    for key, value in data.items():
        if normalize_text(str(key)) == target_key_normalized:
            return value
    for key, value in data.items():
        if str(key).lower().strip() == target_key.lower().strip():
            return value
    return None


def apply_table_formatting(worksheet: gspread.Worksheet, num_headers: int) -> None:
    """Applies standard formatting (bold header, filter) to a worksheet."""
    if not worksheet:
        return
    try:
        header_format = {
            "backgroundColor": {"red": 0.85, "green": 0.85, "blue": 0.85},
            "textFormat": {"bold": True, "fontSize": 10},
            "horizontalAlignment": "CENTER"
        }
        worksheet.format(f"A1:{rowcol_to_a1(1, num_headers)}", header_format)
        worksheet.set_basic_filter()
        logger.info(f"Formato y filtro aplicados a la hoja '{worksheet.title}'.")
    except Exception as e:
        logger.error(f"Error aplicando formato a '{worksheet.title}'", exc_info=True)


def _get_or_create_worksheet(sheet_name: str, headers: List[str]) -> Optional[gspread.Worksheet]:
    """Obtiene una hoja por su nombre o la crea con cabeceras si no existe."""
    if not IS_SHEET_CONNECTED:
        logger.error(f"No se puede obtener/crear hoja '{sheet_name}' sin conexión a Sheets.")
        return None
    try:
        worksheet = spreadsheet.worksheet(sheet_name)
        return worksheet
    except gspread.exceptions.WorksheetNotFound:
        logger.info(f"Hoja '{sheet_name}' no encontrada. Creando...")
        try:
            worksheet = spreadsheet.add_worksheet(title=sheet_name, rows="1", cols=str(len(headers)))
            worksheet.append_row(headers, value_input_option='USER_ENTERED')
            apply_table_formatting(worksheet, len(headers))
            return worksheet
        except Exception as e_create:
            logger.error(f"Error al crear la hoja '{sheet_name}': {e_create}", exc_info=True)
            return None
    except Exception as e:
        logger.error(f"Error accediendo a la hoja '{sheet_name}': {e}", exc_info=True)
        return None


def get_or_create_monthly_sheet(base_name: str, headers: list, date_override: Optional[datetime] = None) -> Optional[gspread.Worksheet]:
    """
    Obtiene o crea una hoja mensual. Si se provee date_override,
    usa esa fecha en lugar de la actual para determinar el mes y año.
    """
    if not IS_SHEET_CONNECTED:
        logger.error(f"No se puede obtener/crear hoja '{base_name}' sin conexión a Sheets.")
        return None
    target_date = date_override or datetime.now()
    sheet_name = get_sheet_name_for_month(base_name, target_date.year, target_date.month)
    try:
        worksheet = spreadsheet.worksheet(sheet_name)
        logger.info(f"Hoja '{sheet_name}' encontrada.")
        return worksheet
    except gspread.exceptions.WorksheetNotFound:
        logger.info(f"Hoja '{sheet_name}' no encontrada. Creando...")
        try:
            worksheet = spreadsheet.add_worksheet(title=sheet_name, rows="1", cols=str(len(headers)))
            worksheet.append_row(headers, value_input_option='USER_ENTERED')
            apply_table_formatting(worksheet, len(headers))
            if base_name == WHOLESALE_SHEET_BASE_NAME:
                logger.info("Hoja de Mayoristas nueva. Buscando señas pendientes del mes anterior...")
                prev_month_date = target_date.replace(day=1) - timedelta(days=1)
                previous_sheet_name = get_sheet_name_for_month(base_name, prev_month_date.year, prev_month_date.month)
                try:
                    previous_sheet = spreadsheet.worksheet(previous_sheet_name)
                    all_records = previous_sheet.get_all_records()
                    pending_rows_to_carry_over = []
                    for record in all_records:
                        if get_value_from_dict_insensitive(record, "Categoría") == "Seña":
                            old_paid = parse_float(str(get_value_from_dict_insensitive(record, "Monto Pagado") or "0.0"))
                            old_remaining = parse_float(str(get_value_from_dict_insensitive(record, "Monto Restante") or "0.0"))
                            new_row_data = {
                                "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "Nombre": get_value_from_dict_insensitive(record, "Nombre"),
                                "Producto": get_value_from_dict_insensitive(record, "Producto"),
                                "Cantidad": get_value_from_dict_insensitive(record, "Cantidad"),
                                "Monto Total": old_paid + old_remaining,
                                "Monto Pagado": 0,
                                "Monto Restante": old_remaining,
                                "Categoría": "Seña"
                            }
                            row = [new_row_data.get(h) for h in headers]
                            pending_rows_to_carry_over.append(row)
                    if pending_rows_to_carry_over:
                        logger.info(f"Se encontraron {len(pending_rows_to_carry_over)} señas pendientes. Traspasando...")
                        worksheet.append_rows(pending_rows_to_carry_over, value_input_option='USER_ENTERED')
                    else:
                        logger.info("No se encontraron señas pendientes en el mes anterior.")
                except gspread.exceptions.WorksheetNotFound:
                    logger.info(f"No se encontró la hoja del mes anterior ('{previous_sheet_name}'). No se traspasarán señas.")
                except Exception as e:
                    logger.error(f"Error al intentar traspasar señas pendientes: {e}", exc_info=True)
            return worksheet
        except Exception as e:
            logger.error(f"Error al crear la hoja '{sheet_name}': {e}", exc_info=True)
            return None
    except Exception as e:
        logger.error(f"Error al acceder a la hoja '{sheet_name}': {e}", exc_info=True)
        return None


# --- Shared column helpers ---

def find_column_index(headers: List[str], *candidates: str) -> Optional[int]:
    """
    Busca una columna por nombre en la lista de cabeceras, probando múltiples
    candidatos para manejar variaciones de acentos/unicode. Devuelve el índice
    1-based, o None si no se encuentra.
    """
    for candidate in candidates:
        target = normalize_text(candidate)
        for idx, header in enumerate(headers):
            if normalize_text(str(header)) == target:
                return idx + 1
    return None


def safe_row_value(row_values: list, col_index: int, default: str = "0") -> str:
    """Devuelve el valor de una celda por índice 1-based, con fallback seguro."""
    return row_values[col_index - 1] if len(row_values) >= col_index else default


def check_and_set_event_processed(event_id: str) -> bool:
    """
    Verifica si un ID de evento ya fue procesado. Si no, lo registra y devuelve True.
    Si ya existe, devuelve False.
    """
    if not event_id:
        logger.warning("Se intentó verificar un event_id vacío.")
        return False
    log_sheet = _get_or_create_worksheet(PROCESSED_EVENTS_SHEET_NAME, PROCESSED_EVENTS_HEADERS)
    if not log_sheet:
        logger.error(f"No se pudo acceder a la hoja '{PROCESSED_EVENTS_SHEET_NAME}'. No se puede garantizar la idempotencia.")
        return True
    try:
        cell = log_sheet.find(event_id, in_column=1)
        if cell:
            logger.warning(f"Evento duplicado detectado y omitido: {event_id}")
            return False
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_sheet.append_row([event_id, timestamp], value_input_option='USER_ENTERED')
        logger.info(f"Evento nuevo '{event_id}' registrado como procesado.")
        return True
    except Exception as e:
        logger.error(f"Error al verificar/escribir en la hoja '{PROCESSED_EVENTS_SHEET_NAME}': {e}", exc_info=True)
        return False


def log_webhook_event(event_id: str, event_type: str, order_id: int) -> bool:
    """
    Registra un evento de webhook en la hoja de logs para prevenir duplicados.
    Devuelve True si el evento es nuevo y se registró, False si ya existía.
    """
    try:
        log_sheet = spreadsheet.worksheet(WEBHOOK_LOGS_SHEET_NAME)
    except gspread.exceptions.WorksheetNotFound:
        logger.error(f"La hoja '{WEBHOOK_LOGS_SHEET_NAME}' no existe. Por favor, créala manualmente.")
        return False
    try:
        cell = log_sheet.find(event_id)
        if cell:
            logger.warning(f"Evento duplicado detectado y omitido: {event_id}")
            return False
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_sheet.append_row([event_id, event_type, order_id, timestamp])
        logger.info(f"Evento nuevo registrado en el log: {event_id}")
        return True
    except Exception as e:
        logger.error(f"Error al buscar o escribir en la hoja de Webhook_Logs: {e}", exc_info=True)
        return False
