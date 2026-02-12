# services/debts_service.py
"""
Debt management: create, query, pay, and modify debts.
"""
import gspread
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from config import DEBTS_SHEET_NAME, DEBTS_HEADERS
from common.utils import parse_float
from services.sheets_connection import (
    _get_or_create_worksheet, get_value_from_dict_insensitive,
    find_column_index, safe_row_value
)

logger = logging.getLogger(__name__)


def get_or_create_debts_sheet() -> Optional[gspread.Worksheet]:
    """Obtiene la hoja de Deudas o la crea con las cabeceras si no existe."""
    return _get_or_create_worksheet(DEBTS_SHEET_NAME, DEBTS_HEADERS)


def add_new_debt(name: str, amount: float) -> Optional[Dict[str, Any]]:
    """Añade una nueva deuda a la hoja de Deudas."""
    debts_sheet = get_or_create_debts_sheet()
    if not debts_sheet:
        return None
    timestamp = datetime.now()
    debt_id = f"DEUDA-{int(timestamp.timestamp())}"
    date_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
    row_data = [debt_id, name, amount, 0.0, amount, "Activa", date_str, date_str]
    try:
        debts_sheet.append_row(row_data, value_input_option='USER_ENTERED')
        logger.info(f"Nueva deuda creada: {row_data}")
        return {
            "ID Deuda": debt_id, "Nombre": name, "Monto Inicial": amount, "Saldo Pendiente": amount
        }
    except Exception as e:
        logger.error(f"Error al añadir nueva deuda a la hoja: {e}", exc_info=True)
        return None


def get_active_debts() -> List[Dict[str, Any]]:
    """Obtiene todas las deudas con saldo pendiente > 0."""
    debts_sheet = get_or_create_debts_sheet()
    if not debts_sheet:
        return []
    try:
        all_debts = debts_sheet.get_all_records()
        active_debts = []
        for i, debt in enumerate(all_debts):
            pending_balance = parse_float(str(get_value_from_dict_insensitive(debt, "Saldo Pendiente") or '0'))
            if pending_balance is not None and pending_balance > 0:
                debt['row_number'] = i + 2
                active_debts.append(debt)
        return active_debts
    except Exception as e:
        logger.error(f"Error al obtener deudas activas: {e}", exc_info=True)
        return []


def register_debt_payment(debt_id: str, payment_amount: float) -> Optional[Dict[str, Any]]:
    """Registra un pago para una deuda especifica y actualiza la hoja."""
    debts_sheet = get_or_create_debts_sheet()
    if not debts_sheet:
        return None
    try:
        cell = debts_sheet.find(debt_id)
        if not cell:
            logger.error(f"No se encontro la deuda con ID {debt_id} para registrar el pago.")
            return None
        row_number = cell.row
        row_values = debts_sheet.row_values(row_number)
        headers = debts_sheet.row_values(1)

        paid_col = find_column_index(headers, "Monto Pagado")
        pending_col = find_column_index(headers, "Saldo Pendiente")
        status_col = find_column_index(headers, "Estado")
        last_paid_col = find_column_index(headers, "Fecha Ultimo Pago", "Fecha Asltimo Pago", "Fecha Último Pago")

        if not all([paid_col, pending_col, status_col, last_paid_col]):
            logger.error(f"No se encontraron todas las columnas necesarias para registrar pagos de deudas. Headers: {headers}")
            return None

        current_paid = parse_float(safe_row_value(row_values, paid_col)) or 0.0
        current_pending = parse_float(safe_row_value(row_values, pending_col)) or 0.0
        new_paid = current_paid + payment_amount
        new_pending = current_pending - payment_amount
        new_status = "Activa" if new_pending > 0 else "Saldada"
        update_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        debts_sheet.update_cell(row_number, paid_col, new_paid)
        debts_sheet.update_cell(row_number, pending_col, new_pending)
        debts_sheet.update_cell(row_number, status_col, new_status)
        debts_sheet.update_cell(row_number, last_paid_col, update_timestamp)
        logger.info(f"Pago registrado para deuda {debt_id}. Nuevo saldo pendiente: {new_pending}")

        name_col = find_column_index(headers, "Nombre")
        debt_name = safe_row_value(row_values, name_col) if name_col else "N/A"
        return {
            "ID Deuda": debt_id,
            "Nombre": debt_name,
            "Saldo Pendiente": new_pending
        }
    except Exception as e:
        logger.error(f"Error al registrar pago de deuda: {e}", exc_info=True)
        return None


def increase_debt_amount(debt_id: str, increase_amount: float) -> Optional[Dict[str, Any]]:
    """Incrementa el monto inicial y el saldo pendiente de una deuda existente."""
    debts_sheet = get_or_create_debts_sheet()
    if not debts_sheet:
        return None
    try:
        cell = debts_sheet.find(debt_id)
        if not cell:
            logger.error(f"No se encontró la deuda con ID {debt_id} para incrementar.")
            return None
        row_number = cell.row
        headers = debts_sheet.row_values(1)
        row_values = debts_sheet.row_values(row_number)

        initial_col = find_column_index(headers, "Monto Inicial")
        pending_col = find_column_index(headers, "Saldo Pendiente")
        status_col = find_column_index(headers, "Estado")
        last_paid_col = find_column_index(headers, "Fecha Último Pago", "Fecha Ultimo Pago")
        name_col = find_column_index(headers, "Nombre")

        if None in (initial_col, pending_col, status_col, last_paid_col, name_col):
            logger.error(f"No se encontraron las columnas necesarias. Headers: {headers}")
            return None

        current_initial = parse_float(safe_row_value(row_values, initial_col)) or 0.0
        current_pending = parse_float(safe_row_value(row_values, pending_col)) or 0.0
        new_initial = current_initial + increase_amount
        new_pending = current_pending + increase_amount

        debts_sheet.update_cell(row_number, initial_col, new_initial)
        debts_sheet.update_cell(row_number, pending_col, new_pending)
        debts_sheet.update_cell(row_number, status_col, "Activa")
        debts_sheet.update_cell(row_number, last_paid_col, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        debt_name = safe_row_value(row_values, name_col)
        logger.info(f"Deuda {debt_id} incrementada en {increase_amount}. Nuevo saldo: {new_pending}.")
        return {
            "ID Deuda": debt_id,
            "Nombre": debt_name,
            "Saldo Pendiente": new_pending
        }
    except Exception as e:
        logger.error(f"Error al incrementar deuda {debt_id}: {e}", exc_info=True)
        return None
