# handlers/wholesale.py
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from constants import *
from config import RESTART_PROMPT, WHOLESALE_SHEET_BASE_NAME, WHOLESALE_HEADERS
from sheet import (
    add_wholesale_record, get_pending_wholesale_payments, modify_wholesale_payment, 
    get_value_from_dict_insensitive, get_or_create_monthly_sheet,
    check_and_set_event_processed
)
from common.utils import parse_float, parse_int
from .core import display_main_menu, build_button_rows
from .future_payments import start_fp_menu

logger = logging.getLogger(__name__)

# --- Menú Principal de Mayoristas ---
async def start_add_wholesale(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    buttons = [
        ("📝 Registrar Seña", "wholesale_seña"),
        ("💵 Registrar Pago Completo", "wholesale_pago_completo"),
        ("🔄 Modificar Pago / Completar", "wholesale_modificar_pago"),
        ("🗓️ Pagos Futuros", "wholesale_pagos_futuros"),
        ("🔙 Volver al Menú Principal", "cancel_to_main")
    ]
    reply_markup = InlineKeyboardMarkup(build_button_rows(1, buttons))
    
    await query.edit_message_text("📦 Ventas Mayoristas\n\nElige el tipo de registro:", reply_markup=reply_markup)
    return ADD_WHOLESALE_MENU

async def wholesale_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer()
    
    if query.data == "cancel_to_main":
        return await display_main_menu(update, context)

    if query.data == "wholesale_pagos_futuros":
        return await start_fp_menu(update, context)

    context.user_data['wholesale_flow'] = {}
    
    if query.data == "wholesale_seña":
        context.user_data['wholesale_flow']['category'] = "Seña"
        await query.edit_message_text(f"📝 Registrando Seña\n\n👤 Por favor, ingresa el nombre del cliente:{RESTART_PROMPT}")
        return ADD_WHOLESALE_GET_NAME
        
    elif query.data == "wholesale_pago_completo":
        context.user_data['wholesale_flow']['category'] = "PAGO"
        await query.edit_message_text(f"💵 Registrando Pago Completo\n\n👤 Por favor, ingresa el nombre del cliente:{RESTART_PROMPT}")
        return ADD_WHOLESALE_GET_NAME
        
    elif query.data == "wholesale_modificar_pago":
        return await start_modify_payment(update, context)

    return await display_main_menu(update, context)


# --- Flujo Común para Seña y Pago Completo ---
async def wholesale_get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text: return ADD_WHOLESALE_GET_NAME
    context.user_data['wholesale_flow']['name'] = update.message.text.strip()
    await update.message.reply_text(f"🏷️ Ingresa el nombre o descripción del producto vendido:{RESTART_PROMPT}")
    return ADD_WHOLESALE_GET_PRODUCT

async def wholesale_get_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text: return ADD_WHOLESALE_GET_PRODUCT
    context.user_data['wholesale_flow']['product'] = update.message.text.strip()
    await update.message.reply_text(f"🔢 Ingresa la cantidad de unidades vendidas:{RESTART_PROMPT}")
    return ADD_WHOLESALE_GET_QUANTITY

async def wholesale_get_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text: return ADD_WHOLESALE_GET_QUANTITY
    quantity = parse_int(update.message.text)
    if not quantity or quantity <= 0:
        await update.message.reply_text(f"Cantidad inválida. Ingresa un número entero positivo:{RESTART_PROMPT}")
        return ADD_WHOLESALE_GET_QUANTITY
    context.user_data['wholesale_flow']['quantity'] = quantity
    
    category = context.user_data['wholesale_flow']['category']
    if category == "Seña":
        await update.message.reply_text(f"💰 Ingresa el monto de la SEÑA (sin puntos ni comas):{RESTART_PROMPT}")
    else: # Pago Completo
        await update.message.reply_text(f"💵 Ingresa el monto TOTAL de la venta (sin puntos ni comas):{RESTART_PROMPT}")
        
    return ADD_WHOLESALE_GET_PAID_AMOUNT

async def wholesale_get_paid_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text: return ADD_WHOLESALE_GET_PAID_AMOUNT
    amount = parse_float(update.message.text)
    if not amount or amount <= 0:
        await update.message.reply_text("Monto inválido. Ingresa un número positivo:")
        return ADD_WHOLESALE_GET_PAID_AMOUNT
        
    context.user_data['wholesale_flow']['paid_amount'] = amount
    category = context.user_data['wholesale_flow']['category']

    if category == "Seña":
        await update.message.reply_text(f"📈 Ahora, ingresa el monto TOTAL de la venta (sin puntos ni comas):{RESTART_PROMPT}")
        return ADD_WHOLESALE_GET_TOTAL_AMOUNT
    else: # Pago Completo
        context.user_data['wholesale_flow']['total_amount'] = amount
        return await save_wholesale_record(update, context)

async def wholesale_get_total_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text: return ADD_WHOLESALE_GET_TOTAL_AMOUNT
    total_amount = parse_float(update.message.text)
    paid_amount = context.user_data['wholesale_flow']['paid_amount']

    if not total_amount or total_amount <= 0:
        await update.message.reply_text("Monto total inválido. Ingresa un número positivo:")
        return ADD_WHOLESALE_GET_TOTAL_AMOUNT
    
    if total_amount < paid_amount:
        await update.message.reply_text("El monto total no puede ser menor que la seña. Ingresa un monto total válido:")
        return ADD_WHOLESALE_GET_TOTAL_AMOUNT

    context.user_data['wholesale_flow']['total_amount'] = total_amount
    return await save_wholesale_record(update, context)

async def save_wholesale_record(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message: return await display_main_menu(update, context)
    
    event_id = f"{update.effective_user.id}-{update.message.message_id}"
    if not check_and_set_event_processed(event_id):
        logger.warning(f"Operación mayorista {event_id} ya procesada. Se omite el reintento.")
        return await display_main_menu(update, context, "Operación finalizada.", send_as_new=True)
    
    try:
        flow_data = context.user_data['wholesale_flow']
        name = flow_data['name']
        product = flow_data['product']
        quantity = flow_data['quantity']
        category = flow_data['category']
        paid_amount = flow_data['paid_amount']
        total_amount = flow_data['total_amount']
        
        record_data = add_wholesale_record(name, product, quantity, paid_amount, total_amount, category)
        
        if record_data:
            await update.message.reply_text(
                f"✅ Registro Mayorista Exitoso ✅\n\n"
                f"Tipo: {category}\n"
                f"Cliente: {record_data['name']}\n"
                f"Producto: {record_data['product']}\n"
                f"Cantidad: {record_data['quantity']}\n"
                f"Monto Pagado: ${record_data['paid_amount']:,.2f}\n\n"
                f"Registrado en la hoja: '{record_data['sheet_title']}'",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("⚠️ Hubo un error al registrar.")
            
    except Exception:
        logger.error("Error registrando venta mayorista", exc_info=True)
        await update.message.reply_text("⚠️ Hubo un error al procesar tu solicitud.")
        
    return await display_main_menu(update, context, "Operación finalizada.", send_as_new=True)

# --- Flujo de Modificar Pago (REDISEÑADO) ---
async def start_modify_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🔄 Buscando señas pendientes en la hoja del mes actual...")

    get_or_create_monthly_sheet(WHOLESALE_SHEET_BASE_NAME, WHOLESALE_HEADERS)
    
    now = datetime.now()
    pending_señs = get_pending_wholesale_payments(now.year, now.month)
    
    if not pending_señs:
        await query.edit_message_text("No se encontraron señas pendientes para el mes actual.")
        return await start_add_wholesale(update, context)
        
    context.user_data['wholesale_flow']['pending_señs'] = pending_señs
    
    buttons = []
    for i, seña in enumerate(pending_señs):
        name = get_value_from_dict_insensitive(seña, "Nombre")
        product = get_value_from_dict_insensitive(seña, "Producto")
        remaining = parse_float(str(get_value_from_dict_insensitive(seña, "Monto Restante") or "0.0"))
        label = f"{name} - {product} - Restan: ${remaining:,.2f}"
        buttons.append((label, f"mod_sena_{i}"))
        
    button_rows = build_button_rows(1, buttons)
    button_rows.append([InlineKeyboardButton("🔙 Volver", callback_data="back_to_wholesale_menu")])
    
    await query.edit_message_text("Selecciona la seña a la que quieres agregar un pago:", reply_markup=InlineKeyboardMarkup(button_rows))
    return MODIFY_PAYMENT_CHOOSE_SENA

async def ask_for_modification_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer()

    if query.data == "back_to_wholesale_menu":
        return await start_add_wholesale(update, context)

    try:
        seña_index = int(query.data.replace("mod_sena_", ""))
        pending_señs = context.user_data['wholesale_flow'].get('pending_señs', [])
        selected_seña = pending_señs[seña_index]
        context.user_data['wholesale_flow']['selected_seña'] = selected_seña
    except (ValueError, IndexError):
        await query.edit_message_text("Error al seleccionar la seña. Inténtalo de nuevo.")
        return await start_add_wholesale(update, context)

    pending_amount = parse_float(str(get_value_from_dict_insensitive(selected_seña, "Monto Restante") or "0.0"))
    await query.edit_message_text(f"El saldo pendiente es ${pending_amount:,.2f}.\n\nIngresa el monto del pago (sin puntos ni comas):{RESTART_PROMPT}", parse_mode='Markdown')
    return MODIFY_PAYMENT_GET_AMOUNT

async def apply_modification_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text: return MODIFY_PAYMENT_GET_AMOUNT
    
    payment_amount = parse_float(update.message.text)
    selected_seña = context.user_data['wholesale_flow']['selected_seña']
    pending_amount = parse_float(str(get_value_from_dict_insensitive(selected_seña, "Monto Restante") or "0.0"))
    
    if not payment_amount or payment_amount <= 0:
        await update.message.reply_text(f"Monto inválido.{RESTART_PROMPT}")
        return MODIFY_PAYMENT_GET_AMOUNT
    
    if payment_amount > pending_amount:
        await update.message.reply_text(f"El pago no puede exceder el saldo de ${pending_amount:,.2f}. Ingresa un monto válido.{RESTART_PROMPT}")
        return MODIFY_PAYMENT_GET_AMOUNT
        
    result = modify_wholesale_payment(selected_seña['row_number'], payment_amount)
    
    if result and "error" not in result:
        remaining = result['remaining_balance']
        if remaining <= 0:
            await update.message.reply_text("✅ ¡Pago completado! La seña ha sido saldada y marcada como 'PAGO'.")
        else:
            await update.message.reply_text(f"✅ Pago registrado. El nuevo saldo pendiente es de ${remaining:,.2f}.", parse_mode='Markdown')
    else:
        await update.message.reply_text("⚠️ Hubo un error al modificar el pago en la hoja de cálculo.")
        
    return await display_main_menu(update, context, "Operación finalizada.", send_as_new=True)