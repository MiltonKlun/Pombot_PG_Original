# services/balance_service.py
"""
Balance reporting: monthly summaries, net balance calculation,
and available sheet months discovery.
"""
import gspread
import logging
from typing import Optional, List, Dict, Any

from config import (
    SALES_SHEET_BASE_NAME, EXPENSES_SHEET_BASE_NAME,
    WHOLESALE_SHEET_BASE_NAME, SPANISH_MONTHS,
    get_sheet_name_for_month
)
from common.utils import parse_float
from services.sheets_connection import (
    IS_SHEET_CONNECTED, spreadsheet,
    get_value_from_dict_insensitive
)
from services.wholesale_service import get_wholesale_summary

logger = logging.getLogger(__name__)


def get_monthly_summary(sheet_base_name: str, year: int, month: int) -> dict:
    """Calculates totals and category breakdown for a given monthly sheet."""
    if not IS_SHEET_CONNECTED:
        raise ConnectionError("No hay conexion a Google Sheets.")
    target_sheet_name = get_sheet_name_for_month(sheet_base_name, year, month)
    try:
        worksheet = spreadsheet.worksheet(target_sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        return {"total": 0.0, "count": 0, "by_category": {}, "message": f"La hoja '{target_sheet_name}' no existe."}
    all_records = worksheet.get_all_records()
    total_amount, count, by_category = 0.0, 0, {}
    category_candidates = ["Categoría", "Categoria", "CategorA-a"]
    if sheet_base_name == EXPENSES_SHEET_BASE_NAME:
        amount_candidates = ["Monto", "Monto Final"]
    else:
        amount_candidates = ["Precio Total", "Monto Total", "Precio Final"]
    for record in all_records:
        category_val = None
        for cand in category_candidates:
            category_val = get_value_from_dict_insensitive(record, cand)
            if category_val is not None and str(category_val).strip():
                break
        category = str(category_val or "Sin Categoria").strip()
        amount_val = None
        for cand in amount_candidates:
            amount_val = get_value_from_dict_insensitive(record, cand)
            if amount_val is not None:
                break
        amount = parse_float(str(amount_val or "0")) or 0.0
        total_amount += amount
        count += 1
        by_category[category] = by_category.get(category, 0.0) + amount
    return {"total": round(total_amount, 2), "count": count, "by_category": {c: round(v, 2) for c, v in by_category.items()}}


def get_net_balance_for_month(year: int, month: int) -> dict:
    """Calcula y devuelve una estructura de balance detallada, separando CANJES."""
    sales_summary = get_monthly_summary(SALES_SHEET_BASE_NAME, year, month)
    wholesale_summary = get_wholesale_summary(year, month)
    all_expenses_summary = get_monthly_summary(EXPENSES_SHEET_BASE_NAME, year, month)
    gastos_pg_total = 0
    gastos_personales_by_cat = {}
    gastos_pg_by_cat = {}
    canjes_summary = {"total": 0.0, "by_category": {}}
    if all_expenses_summary.get("by_category"):
        for category, total in all_expenses_summary["by_category"].items():
            if category == "PERSONALES":
                target_sheet_name = get_sheet_name_for_month(EXPENSES_SHEET_BASE_NAME, year, month)
                try:
                    worksheet = spreadsheet.worksheet(target_sheet_name)
                    all_expense_records = worksheet.get_all_records()
                    for record in all_expense_records:
                        if get_value_from_dict_insensitive(record, "Categoría") == "PERSONALES":
                            subcategory = get_value_from_dict_insensitive(record, "Subcategoría") or "General"
                            amount = parse_float(str(get_value_from_dict_insensitive(record, "Monto") or '0')) or 0.0
                            gastos_personales_by_cat[subcategory] = gastos_personales_by_cat.get(subcategory, 0.0) + amount
                except gspread.exceptions.WorksheetNotFound:
                    pass
            elif category == "CANJES":
                canjes_summary["total"] += total
                target_sheet_name = get_sheet_name_for_month(EXPENSES_SHEET_BASE_NAME, year, month)
                try:
                    worksheet = spreadsheet.worksheet(target_sheet_name)
                    all_expense_records = worksheet.get_all_records()
                    for record in all_expense_records:
                        if get_value_from_dict_insensitive(record, "Categoría") == "CANJES":
                            subcategory = get_value_from_dict_insensitive(record, "Subcategoría") or "N/A"
                            amount = parse_float(str(get_value_from_dict_insensitive(record, "Monto") or '0')) or 0.0
                            canjes_summary["by_category"][subcategory] = canjes_summary["by_category"].get(subcategory, 0.0) + amount
                except gspread.exceptions.WorksheetNotFound:
                    pass
            else:
                gastos_pg_total += total
                gastos_pg_by_cat[category] = total
    gastos_personales_total = sum(gastos_personales_by_cat.values())
    saldo_pg = (sales_summary.get('total', 0.0) + wholesale_summary.get('total', 0.0)) - gastos_pg_total
    saldo_neto = saldo_pg - gastos_personales_total
    return {
        "sales_summary": sales_summary,
        "wholesale_summary": wholesale_summary,
        "canjes_summary": {"total": round(canjes_summary["total"], 2), "by_category": {c: round(v, 2) for c, v in canjes_summary["by_category"].items()}},
        "gastos_pg_summary": {"total": round(gastos_pg_total, 2), "by_category": {c: round(v, 2) for c, v in gastos_pg_by_cat.items()}},
        "gastos_personales_summary": {"total": round(gastos_personales_total, 2), "by_category": {c: round(v, 2) for c, v in gastos_personales_by_cat.items()}},
        "saldo_pg": round(saldo_pg, 2),
        "saldo_neto": round(saldo_neto, 2),
        "month_name": SPANISH_MONTHS.get(month, "MesInvalido"),
        "year": year
    }


def get_available_sheet_months_years() -> list[tuple[int, int]]:
    """Discovers which (year, month) combinations have data in the spreadsheet."""
    if not IS_SHEET_CONNECTED:
        return []
    sheet_titles = [sh.title for sh in spreadsheet.worksheets()]
    logger.info(f"Hojas encontradas: {sheet_titles}")
    available = set()
    months_map_spanish = {v: k for k, v in SPANISH_MONTHS.items()}
    for title in sheet_titles:
        parts = title.split()
        if len(parts) >= 3:
            base_name = " ".join(parts[:-2])
            month_name_str, year_str = parts[-2], parts[-1]
            if base_name in [SALES_SHEET_BASE_NAME, EXPENSES_SHEET_BASE_NAME, WHOLESALE_SHEET_BASE_NAME]:
                try:
                    month_num = months_map_spanish.get(month_name_str.capitalize())
                    if month_num:
                        available.add((int(year_str), month_num))
                except (ValueError, KeyError):
                    continue
    return sorted(list(available), key=lambda x: (x[0], x[1]), reverse=True)
