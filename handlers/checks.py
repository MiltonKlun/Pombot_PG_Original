# handlers/checks.py (Versión Simplificada)
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from constants import *
from config import RESTART_PROMPT
from sheet import add_check, get_pending_checks
from common.utils import parse_float
from .core import display_main_menu, build_button_rows

logger = logging.getLogger(__name__)

async def start_checks_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    buttons = [
        ("🧾 Emitir Cheque", "check_emitir"),
        ("📋 Consultar Cheques", "check_consult"),
        ("🔙 Volver al Menú Principal", "cancel_to_main")
    ]
    reply_markup = InlineKeyboardMarkup(build_button_rows(1, buttons))
    await query.edit_message_text("🧾 Módulo de Cheques\n\nElige una opción:", reply_markup=reply_markup)
    return CHECKS_MENU

async def checks_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    if query.data == "check_consult":
        await query.edit_message_text("Buscando cheques pendientes...")
        pending_checks = get_pending_checks()
        if not pending_checks:
            await query.edit_message_text("👍 No hay cheques pendientes de cobro.")
        else:
            response_parts = ["📋 **Cheques Pendientes (Emitidos)**\n"]
            for check in pending_checks:
                tipo = "EMITIDO"
                entidad = check.get("Entidad", "N/A")
                # Leemos de "Monto Final" en lugar de "Monto"
                monto = parse_float(str(check.get("Monto Final", 0)))
                fecha = check.get("Fecha Cobro", "N/A")
                arrow = "➡️"
                response_parts.append(f"{arrow} **{tipo}** a **{entidad}** por **${monto:,.2f}** (Cobro: {fecha})")
            await query.edit_message_text("\n".join(response_parts), parse_mode='Markdown')
        return await display_main_menu(update, context, send_as_new=True)

    # Inicia el flujo para un nuevo cheque
    context.user_data['check_flow'] = {}
    await query.edit_message_text(f"Emitiendo Cheque.\n\n👤 Ingresa la entidad o proveedor:{RESTART_PROMPT}")
    return CHECKS_GET_ENTITY

# --- Flujo Simplificado de Registro de Cheque ---
async def checks_get_entity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text: return CHECKS_GET_ENTITY
    context.user_data['check_flow']['entity'] = update.message.text.strip()
    await update.message.reply_text(f"💰 Ingresa el monto INICIAL del cheque:{RESTART_PROMPT}")
    return CHECKS_GET_INITIAL_AMOUNT

async def checks_get_initial_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text: return CHECKS_GET_INITIAL_AMOUNT
    amount = parse_float(update.message.text)
    if not amount or amount <= 0:
        await update.message.reply_text("Monto inválido.")
        return CHECKS_GET_INITIAL_AMOUNT
    context.user_data['check_flow']['initial_amount'] = amount
    await update.message.reply_text(f"💸 Ingresa el monto de la COMISIÓN (si no hay, ingresa 0):{RESTART_PROMPT}")
    return CHECKS_GET_COMMISSION

async def checks_get_commission(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text: return CHECKS_GET_COMMISSION
    commission = parse_float(update.message.text)
    if commission is None or commission < 0:
        await update.message.reply_text("Comisión inválida.")
        return CHECKS_GET_COMMISSION
    context.user_data['check_flow']['commission'] = commission
    await update.message.reply_text(f"📅 Ingresa la fecha de COBRO (dd/mm/aaaa):{RESTART_PROMPT}")
    return CHECKS_GET_DUE_DATE

async def checks_get_due_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text: return CHECKS_GET_DUE_DATE
    context.user_data['check_flow']['due_date'] = update.message.text.strip()
    
    flow = context.user_data['check_flow']
    try:
        add_check(
            entity=flow['entity'],
            initial_amount=flow['initial_amount'],
            commission=flow['commission'],
            due_date=flow['due_date']
        )
        tax = flow['initial_amount'] * 0.012
        final_amount = flow['initial_amount'] + flow['commission'] + tax
        await update.message.reply_text(
            f"✅ Cheque Emitido registrado:\n"
            f"Monto Inicial: ${flow['initial_amount']:,.2f}\n"
            f"Impuesto (1.2%): ${tax:,.2f}\n"
            f"Comisión: ${flow['commission']:,.2f}\n"
            f"Gasto Total: **${final_amount:,.2f}**",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error registrando cheque: {e}", exc_info=True)
        await update.message.reply_text("⚠️ Hubo un error al registrar el cheque.")

    return await display_main_menu(update, context, "Operación finalizada.", send_as_new=True)