# handlers/balance.py
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import ContextTypes

from constants import *
from config import SPANISH_MONTHS
from sheet import get_available_sheet_months_years, get_net_balance_for_month
from .core import display_main_menu, build_button_rows
from services.report_generator import generate_balance_pdf

logger = logging.getLogger(__name__)

async def query_balance_start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    # Respondemos al clic del botón inmediatamente
    if query: await query.answer()

    available_months_years = get_available_sheet_months_years()
    if not available_months_years:
        await query.edit_message_text("No hay datos de meses anteriores para consultar.")
        return await display_main_menu(update, context, send_as_new=True)
        
    unique_years = sorted(list(set(ym[0] for ym in available_months_years)), reverse=True)
    year_buttons = [(str(year), f"balance_year_{year}") for year in unique_years[:5]]
    button_rows = build_button_rows(3, year_buttons)
    button_rows.append([InlineKeyboardButton("🗓️ Balance Mes Actual", callback_data="balance_current_month")])
    button_rows.append([InlineKeyboardButton("🔙 Volver al Menú", callback_data="cancel_to_main")])
    reply_markup = InlineKeyboardMarkup(button_rows)
    await query.edit_message_text("📈 Consultar Balance\nSelecciona el año:", reply_markup=reply_markup)
    return QUERY_BALANCE_CHOOSE_YEAR

async def query_balance_year_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    # Respondemos al clic del botón inmediatamente
    if query: await query.answer()
    
    if query.data == "balance_current_month":
        now = datetime.now()
        return await process_and_display_balance(update, context, now.year, now.month)
        
    selected_year = int(query.data.split('_')[-1])
    context.user_data['selected_balance_year'] = selected_year
    available_months_years = get_available_sheet_months_years()
    months_for_year = sorted([ym[1] for ym in available_months_years if ym[0] == selected_year], reverse=True)
    
    month_buttons = [(SPANISH_MONTHS.get(mn, "Error"), f"balance_month_{selected_year}_{mn}") for mn in months_for_year]
    
    if not month_buttons:
        await query.edit_message_text(f"No hay datos de meses para el año {selected_year}.")
        return await query_balance_start_handler(update, context)
        
    button_rows = build_button_rows(3, month_buttons)
    button_rows.append([InlineKeyboardButton("🔙 Elegir otro Año", callback_data="main_query_balance_start")])
    button_rows.append([InlineKeyboardButton("🔙 Volver al Menú", callback_data="cancel_to_main")])
    reply_markup = InlineKeyboardMarkup(button_rows)
    await query.edit_message_text(f"Año seleccionado: {selected_year}\nSelecciona el mes:", reply_markup=reply_markup)
    return QUERY_BALANCE_CHOOSE_MONTH

async def query_balance_month_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    # Respondemos al clic del botón inmediatamente
    if query: await query.answer()
    
    if query.data == "main_query_balance_start": 
        return await query_balance_start_handler(update, context)
        
    parts = query.data.split('_')
    selected_year, selected_month = int(parts[-2]), int(parts[-1])
    return await process_and_display_balance(update, context, selected_year, selected_month)

async def process_and_display_balance(update: Update, context: ContextTypes.DEFAULT_TYPE, year: int, month: int) -> int:
    query = update.callback_query
    month_name = SPANISH_MONTHS.get(month, "MesInvalido")
    
    # Notificamos al usuario que estamos trabajando
    if query:
        await query.edit_message_text(f"⏳ Generando reporte en PDF para {month_name} {year}...")
        
    try:
        # Hacemos el trabajo pesado de forma secuencial (esperamos a que termine)
        balance_data = get_net_balance_for_month(year, month)
        pdf_path = generate_balance_pdf(balance_data)

        if pdf_path and update.effective_chat:
            with open(pdf_path, 'rb') as pdf_file:
                await context.bot.send_document(
                    chat_id=update.effective_chat.id,
                    document=InputFile(pdf_file),
                    filename=pdf_path.split('/')[-1],
                    caption=f"Aquí tienes tu reporte de balance para {month_name} {year}."
                )
            if query:
                await query.delete_message()
        else:
            if query:
                await query.edit_message_text("⚠️ Hubo un error al generar el reporte PDF.")

    except Exception:
        logger.error(f"Error inesperado obteniendo balance", exc_info=True)
        if query: await query.edit_message_text("⚠️ Hubo un error al calcular el balance.")

    # Al final, volvemos al menú principal
    return await display_main_menu(update, context, "Consulta finalizada.", send_as_new=True)