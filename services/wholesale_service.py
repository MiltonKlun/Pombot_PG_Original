# services/wholesale_service.py
"""
Wholesale transaction management: recording, querying pending payments,
modifying payments, and generating summaries.
"""
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from collections import defaultdict

from config import WHOLESALE_SHEET_BASE_NAME, WHOLESALE_HEADERS, get_sheet_name_for_month
from common.utils import parse_float
from services.sheets_connection import (
    IS_SHEET_CONNECTED, spreadsheet,
    get_or_create_monthly_sheet, get_value_from_dict_insensitive
)

logger = logging.getLogger(__name__)


def add_wholesale_record(name: str, product: str, quantity: int, paid_amount: float, total_amount: float, category: str, date_str: str = None) -> Optional[Dict[str, Any]]:
    """Records a wholesale transaction in the monthly sheet."""
    timestamp = date_str or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sheet_date = datetime.strptime(timestamp.split(' ')[0], "%Y-%m-%d")
    worksheet = get_or_create_monthly_sheet(WHOLESALE_SHEET_BASE_NAME, WHOLESALE_HEADERS, date_override=sheet_date)
    if not worksheet:
        logger.error(f"Hoja para '{WHOLESALE_SHEET_BASE_NAME}' no disponible.")
        return None
    remaining_amount = total_amount - paid_amount
    row_data = [timestamp, name, product, quantity, total_amount, paid_amount, remaining_amount, category]
    try:
        worksheet.append_row(row_data, value_input_option='USER_ENTERED')
        logger.info(f"Venta mayorista registrada: {row_data}")
        return {
            "timestamp": timestamp, "name": name, "product": product,
            "quantity": quantity, "paid_amount": paid_amount, "sheet_title": worksheet.title
        }
    except Exception as e:
        logger.error(f"Error al añadir registro mayorista: {e}", exc_info=True)
        return None


def get_pending_wholesale_payments(year: int, month: int) -> List[Dict[str, Any]]:
    """Obtiene todos los registros mayoristas marcados como 'Seña'."""
    target_sheet_name = get_sheet_name_for_month(WHOLESALE_SHEET_BASE_NAME, year, month)
    try:
        worksheet = spreadsheet.worksheet(target_sheet_name)
    except Exception:
        return []
    all_records = worksheet.get_all_records()
    pending_payments = []
    for i, record in enumerate(all_records):
        category = get_value_from_dict_insensitive(record, "Categoría")
        if category == "Seña":
            record['row_number'] = i + 2
            pending_payments.append(record)
    return pending_payments


def modify_wholesale_payment(row_number: int, payment_amount: float) -> Optional[Dict[str, Any]]:
    """Aplica un pago a una seña existente y actualiza las columnas de montos."""
    worksheet = get_or_create_monthly_sheet(WHOLESALE_SHEET_BASE_NAME, WHOLESALE_HEADERS)
    if not worksheet:
        return None
    try:
        paid_col = WHOLESALE_HEADERS.index("Monto Pagado") + 1
        remaining_col = WHOLESALE_HEADERS.index("Monto Restante") + 1
        category_col = WHOLESALE_HEADERS.index("Categoría") + 1

        current_paid_str = str(worksheet.cell(row_number, paid_col).value)
        current_remaining_str = str(worksheet.cell(row_number, remaining_col).value)
        current_paid = parse_float(current_paid_str) or 0.0
        current_remaining = parse_float(current_remaining_str) or 0.0
        if payment_amount > current_remaining:
            return {"error": "El pago excede el saldo pendiente."}
        new_paid_amount = current_paid + payment_amount
        new_remaining_amount = current_remaining - payment_amount
        worksheet.update_cell(row_number, paid_col, new_paid_amount)
        worksheet.update_cell(row_number, remaining_col, new_remaining_amount)
        if new_remaining_amount <= 0:
            worksheet.update_cell(row_number, category_col, "PAGO")
        return {"remaining_balance": new_remaining_amount}
    except Exception as e:
        logger.error(f"Error al modificar pago mayorista en fila {row_number}: {e}", exc_info=True)
        return None


def get_wholesale_summary(year: int, month: int) -> dict:
    """Obtiene el resumen de ventas mayoristas para un mes especifico, incluyendo detalles por operación."""
    if not IS_SHEET_CONNECTED:
        raise ConnectionError("No hay conexion a Google Sheets.")
    target_sheet_name = get_sheet_name_for_month(WHOLESALE_SHEET_BASE_NAME, year, month)
    try:
        worksheet = spreadsheet.worksheet(target_sheet_name)
    except Exception:
        return {"total": 0.0, "count": 0, "by_client": {}, "details": []}
    all_records = worksheet.get_all_records()
    total_amount = 0.0
    detailed_transactions = []
    by_client_data = defaultdict(lambda: {"amount": 0.0, "quantity": 0})
    for record in all_records:
        client_name_value = get_value_from_dict_insensitive(record, "Nombre")
        client_name_str = str(client_name_value).strip() if client_name_value is not None else "Sin Nombre"
        product_value = get_value_from_dict_insensitive(record, "Producto")
        product_str = str(product_value).strip() if product_value is not None else "N/A"
        amount = parse_float(str(get_value_from_dict_insensitive(record, "Monto Pagado") or '0')) or 0.0
        quantity_value = parse_float(str(get_value_from_dict_insensitive(record, "Cantidad") or '0')) or 0.0
        quantity = int(quantity_value)
        total_amount += amount
        detailed_transactions.append({
            "client": client_name_str,
            "product": product_str,
            "quantity": quantity,
            "amount": amount
        })
        client_entry = by_client_data[client_name_str]
        client_entry["amount"] += amount
        client_entry["quantity"] += quantity
    return {
        "total": round(total_amount, 2),
        "count": len(all_records),
        "by_client": {
            c: {"amount": round(data["amount"], 2), "quantity": data["quantity"]}
            for c, data in by_client_data.items()
        },
        "details": detailed_transactions
    }
