# services/checks_service.py
"""
Checks and Future Payments management: CRUD operations plus
scheduling helpers for due-date alerts and auto-conciliation.
"""
import gspread
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from config import (
    CHECKS_SHEET_NAME, CHECKS_HEADERS,
    FUTURE_PAYMENTS_SHEET_NAME, FUTURE_PAYMENTS_HEADERS
)
from services.sheets_connection import (
    _get_or_create_worksheet, apply_table_formatting
)

logger = logging.getLogger(__name__)


# --- Checks ---

def add_check(entity: str, initial_amount: float, commission: float, due_date: str) -> None:
    """Emits a new check with auto-calculated 1.2% tax."""
    sheet = _get_or_create_worksheet(CHECKS_SHEET_NAME, CHECKS_HEADERS)
    if not sheet:
        raise ConnectionError("Hoja de Cheques no disponible.")
    check_id = f"CHK-{int(datetime.now().timestamp())}"
    tax = initial_amount * 0.012
    final_amount = initial_amount + commission + tax
    row_data = [check_id, due_date, entity, initial_amount, tax, commission, final_amount, "Pendiente"]
    sheet.append_row(row_data, value_input_option='USER_ENTERED')


def get_pending_checks() -> List[Dict[str, Any]]:
    """Returns all checks with status 'Pendiente'."""
    sheet = _get_or_create_worksheet(CHECKS_SHEET_NAME, CHECKS_HEADERS)
    if not sheet:
        return []
    all_records = sheet.get_all_records()
    return [r for r in all_records if r.get("Estado") == "Pendiente"]


# --- Future Payments ---

def add_future_payment(entity: str, product: str, quantity: int, initial_amount: float, commission: float, due_date: str) -> None:
    """Records a received future payment."""
    sheet = _get_or_create_worksheet(FUTURE_PAYMENTS_SHEET_NAME, FUTURE_PAYMENTS_HEADERS)
    if not sheet:
        raise ConnectionError("Hoja de Pagos Futuros no disponible.")
    try:
        existing_headers = sheet.row_values(1)
        if existing_headers != FUTURE_PAYMENTS_HEADERS:
            sheet.update('1:1', [FUTURE_PAYMENTS_HEADERS])
            apply_table_formatting(sheet, len(FUTURE_PAYMENTS_HEADERS))
    except Exception as e:
        logger.warning(f"No se pudo actualizar cabeceras de Pagos Futuros: {e}")
    payment_id = f"FP-{int(datetime.now().timestamp())}"
    final_amount = initial_amount - commission
    row_data = [payment_id, due_date, entity, product, quantity, initial_amount, commission, final_amount, "Pendiente"]
    sheet.append_row(row_data, value_input_option='USER_ENTERED')


def get_pending_future_payments() -> List[Dict[str, Any]]:
    """Returns all future payments with status 'Pendiente'."""
    sheet = _get_or_create_worksheet(FUTURE_PAYMENTS_SHEET_NAME, FUTURE_PAYMENTS_HEADERS)
    if not sheet:
        return []
    all_records = sheet.get_all_records()
    return [r for r in all_records if r.get("Estado") == "Pendiente"]


# --- Scheduling helpers ---

def get_items_due_in_x_days(days: int) -> Dict[str, List]:
    """Busca en Cheques y Pagos Futuros los items que vencen en los próximos X días."""
    today = datetime.now()
    target_dates = [(today + timedelta(days=i)).strftime("%d/%m/%Y") for i in range(days + 1)]
    results = {"cheques": [], "pagos_futuros": []}
    pending_checks = get_pending_checks()
    for check in pending_checks:
        due_date = check.get("Fecha Cobro")
        if due_date in target_dates:
            results["cheques"].append(check)
    pending_fps = get_pending_future_payments()
    for fp in pending_fps:
        due_date = fp.get("Fecha Cobro")
        if due_date in target_dates:
            results["pagos_futuros"].append(fp)
    return results


def update_past_due_statuses() -> None:
    """Revisa Cheques y Pagos Futuros y marca como 'PAGO' los que ya vencieron."""
    logger.info("Iniciando actualización de estados para Cheques y Pagos Futuros...")
    today = datetime.now()
    updated_count = 0

    def process_sheet(sheet_name, headers):
        nonlocal updated_count
        sheet = _get_or_create_worksheet(sheet_name, headers)
        if not sheet:
            return
        all_records = sheet.get_all_records()
        for i, record in enumerate(all_records):
            row_num = i + 2
            status = record.get("Estado")
            due_date_str = record.get("Fecha Cobro")
            if status == "Pendiente" and due_date_str:
                try:
                    due_date = datetime.strptime(due_date_str, "%d/%m/%Y")
                    if due_date < today:
                        status_col_index = headers.index("Estado") + 1
                        sheet.update_cell(row_num, status_col_index, "PAGO")
                        updated_count += 1
                        logger.info(f"Fila {row_num} en '{sheet_name}' actualizada a PAGO.")
                except ValueError:
                    logger.warning(f"Formato de fecha incorrecto en la fila {row_num} de '{sheet_name}': {due_date_str}")
                    continue

    process_sheet(CHECKS_SHEET_NAME, CHECKS_HEADERS)
    process_sheet(FUTURE_PAYMENTS_SHEET_NAME, FUTURE_PAYMENTS_HEADERS)
    logger.info(f"Actualización de estados finalizada. Se actualizaron {updated_count} registros.")


def get_items_due_today() -> Dict[str, List]:
    """Busca en Cheques y Pagos Futuros los items cuyo estado es 'PAGO' y vencen hoy."""
    today_str = datetime.now().strftime("%d/%m/%Y")
    results = {"cheques": [], "pagos_futuros": []}
    all_checks = _get_or_create_worksheet(CHECKS_SHEET_NAME, CHECKS_HEADERS).get_all_records()
    for check in all_checks:
        if check.get("Estado") == "PAGO" and check.get("Fecha Cobro") == today_str:
            results["cheques"].append(check)
    all_fps = _get_or_create_worksheet(FUTURE_PAYMENTS_SHEET_NAME, FUTURE_PAYMENTS_HEADERS).get_all_records()
    for fp in all_fps:
        if fp.get("Estado") == "PAGO" and fp.get("Fecha Cobro") == today_str:
            results["pagos_futuros"].append(fp)
    return results


def update_item_status(sheet_name: str, item_id: str, new_status: str) -> bool:
    """Busca un item por su ID y actualiza su estado."""
    headers = CHECKS_HEADERS if sheet_name == CHECKS_SHEET_NAME else FUTURE_PAYMENTS_HEADERS
    sheet = _get_or_create_worksheet(sheet_name, headers)
    if not sheet:
        return False
    try:
        existing_headers = sheet.row_values(1)
        if existing_headers != headers:
            sheet.update('1:1', [headers])
            apply_table_formatting(sheet, len(headers))
    except Exception as e:
        logger.warning(f"No se pudieron actualizar cabeceras para {sheet_name}: {e}")
    try:
        cell = sheet.find(item_id, in_column=1)
        if not cell:
            logger.warning(f"No se encontro el item con ID {item_id} en la hoja {sheet_name}.")
            return False
        status_col_index = headers.index("Estado") + 1
        sheet.update_cell(cell.row, status_col_index, new_status)
        logger.info(f"Item {item_id} en hoja {sheet_name} actualizado a estado '{new_status}'.")
        return True
    except Exception as e:
        logger.error(f"Error actualizando estado para item {item_id}: {e}", exc_info=True)
        return False
