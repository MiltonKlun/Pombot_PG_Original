# services/expenses_service.py
"""
Expense recording service.
"""
import logging
from datetime import datetime

from config import EXPENSES_SHEET_BASE_NAME, EXPENSES_HEADERS
from services.sheets_connection import get_or_create_monthly_sheet

logger = logging.getLogger(__name__)


def add_expense(category: str, subcategory: str, description: str, details: str, amount: float, date_str: str = None) -> dict:
    """Añade un registro de gasto, permitiendo una fecha personalizada."""
    timestamp = date_str or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sheet_date = datetime.strptime(timestamp.split(' ')[0], "%Y-%m-%d")
    worksheet = get_or_create_monthly_sheet(EXPENSES_SHEET_BASE_NAME, EXPENSES_HEADERS, date_override=sheet_date)
    if not worksheet:
        raise ConnectionError(f"Hoja para '{EXPENSES_SHEET_BASE_NAME}' no disponible.")
    row_data = [timestamp, category, subcategory, description, details, amount]
    worksheet.append_row(row_data, value_input_option='USER_ENTERED')
    return {
        "timestamp": timestamp, "category": category, "subcategory": subcategory,
        "description": description, "details": details, "amount": amount,
        "sheet_title": worksheet.title
    }
