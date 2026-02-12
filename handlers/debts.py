import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from constants import *
from config import RESTART_PROMPT
from sheet import (
    add_new_debt, get_active_debts, register_debt_payment, increase_debt_amount, 
    get_value_from_dict_insensitive, check_and_set_event_processed
)
from common.utils import parse_float
from .core import display_main_menu, build_button_rows

logger = logging.getLogger(__name__)

async def start_debt_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, send_as_new: bool = False) -> int:
    """Muestra el submenú de opciones de Deudas, editando o enviando un nuevo mensaje."""
    buttons = [
        ("➕ Crear Nueva Deuda", "debt_create"),
        ("💵 Registrar Pago Deuda", "debt_pay"),
        ("Modificar Deuda", "debt_modify"),
        ("📋 Consultar Deudas", "debt_query"),
        ("🔙 Volver al Menú", "cancel_to_main")
    ]
    reply_markup = InlineKeyboardMarkup(build_button_rows(1, buttons))
    text = "💰 Gestión de Deudas\n\nElige una opción:"

    query = update.callback_query
    # Si se pide enviar como nuevo, o si no hay un query para editar, se envía.
    if send_as_new or not query:
        # Si la actualización original fue un mensaje de texto, usamos `update.message`
        if update.message:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        # Si fue un botón, usamos `update.effective_chat` para enviar un nuevo mensaje al chat
        elif update.effective_chat:
            await update.effective_chat.send_message(text, reply_markup=reply_markup, parse_mode='Markdown')
    else: # Si hay un query y no se pide enviar como nuevo, se edita.
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
    return DEBT_MENU

async def debt_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maneja la selección del submenú de Deudas."""
    query = update.callback_query
    await query.answer()

    action = query.data
    if action == "debt_create":
        await query.edit_message_text(f"👤 Ingresa el nombre de la persona o entidad deudora:{RESTART_PROMPT}")
        return CREATE_DEBT_GET_NAME
    elif action == "debt_pay":
        return await start_pay_debt(update, context)
    elif action == "debt_modify":
        return await start_modify_debt(update, context)
    elif action == "debt_query":
        return await query_debts(update, context)

    return await display_main_menu(update, context)

# Flujo: Crear Nueva Deuda
async def create_debt_get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text: return CREATE_DEBT_GET_NAME

    context.user_data['debt_name'] = update.message.text.strip()
    await update.message.reply_text(f"💵 Ingresa el monto total de la nueva deuda (sin puntos ni comas):{RESTART_PROMPT}")
    return CREATE_DEBT_GET_AMOUNT

async def create_debt_get_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text: return CREATE_DEBT_GET_AMOUNT
    
    event_id = f"{update.effective_user.id}-{update.message.message_id}"
    if not check_and_set_event_processed(event_id):
        logger.warning(f"Creación de deuda {event_id} ya procesada. Se omite el reintento.")
        return await start_debt_menu(update, context)
        
    amount = parse_float(update.message.text)
    if not amount or amount <= 0:
        await update.message.reply_text("Monto inválido. Ingresa un número positivo:")
        return CREATE_DEBT_GET_AMOUNT
    
    name = context.user_data.get('debt_name')
    new_debt = add_new_debt(name, amount)
    
    if new_debt:
        await update.message.reply_text(f"✅ Deuda creada exitosamente para {name} por un monto de ${amount:,.2f}.", parse_mode='Markdown')
    else:
        await update.message.reply_text("⚠️ Hubo un error al crear la deuda. Inténtalo de nuevo.")
        
    # Volver al menú de deudas
    return await start_debt_menu(update, context)

# Flujo: Registrar Pago
async def start_pay_debt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer() # Responde al callback para que el botón no quede "cargando"

    active_debts = get_active_debts()
    
    if not active_debts:
        await query.edit_message_text("👍 ¡No hay deudas activas para registrar pagos!")
        return await start_debt_menu(update, context)
    
    buttons = []
    for debt in active_debts:
        debt_id = debt.get('ID Deuda')
        name = debt.get('Nombre')
        pending = parse_float(str(debt.get('Saldo Pendiente', '0')))
        label = f"{name} - Debe: ${pending:,.2f}"
        buttons.append((label, f"pay_debt_id_{debt_id}"))
    
    button_rows = build_button_rows(1, buttons)
    button_rows.append([InlineKeyboardButton("🔙 Volver", callback_data="debt_back_to_menu")])
    reply_markup = InlineKeyboardMarkup(button_rows)
    
    await query.edit_message_text("💵 Registrar Pago\n\nSelecciona la deuda a la que quieres registrar un pago:", reply_markup=reply_markup)
    return PAY_DEBT_CHOOSE_DEBT

async def pay_debt_choose_debt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "debt_back_to_menu":
        return await start_debt_menu(update, context)
        
    debt_id = query.data.replace("pay_debt_id_", "")
    
    # Encontrar los detalles de la deuda seleccionada
    active_debts = get_active_debts()
    selected_debt = next((d for d in active_debts if d.get('ID Deuda') == debt_id), None)
    
    if not selected_debt:
         await query.edit_message_text("⚠️ Error: No se encontró la deuda seleccionada.")
         return await start_debt_menu(update, context)

    context.user_data['selected_debt'] = selected_debt
    pending_amount = parse_float(str(selected_debt.get('Saldo Pendiente', '0')))
    
    await query.edit_message_text(f"Deuda de {selected_debt.get('Nombre')}.\nSaldo pendiente: ${pending_amount:,.2f}\n\nIngresa el monto del pago (sin puntos ni comas):{RESTART_PROMPT}", parse_mode='Markdown')
    return PAY_DEBT_GET_AMOUNT

async def pay_debt_get_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text: return PAY_DEBT_GET_AMOUNT
    
    event_id = f"{update.effective_user.id}-{update.message.message_id}"
    if not check_and_set_event_processed(event_id):
        logger.warning(f"Pago de deuda {event_id} ya procesado. Se omite el reintento.")
        return await start_debt_menu(update, context)
        
    payment_amount = parse_float(update.message.text)
    selected_debt = context.user_data.get('selected_debt')
    pending_amount = parse_float(str(selected_debt.get('Saldo Pendiente', '0')))
    
    if not payment_amount or payment_amount <= 0:
        await update.message.reply_text("Monto inválido. Ingresa un número positivo:")
        return PAY_DEBT_GET_AMOUNT
        
    if payment_amount > pending_amount:
        await update.message.reply_text(f"El pago no puede ser mayor que el saldo pendiente (${pending_amount:,.2f}). Ingresa un monto válido:")
        return PAY_DEBT_GET_AMOUNT
        
    updated_debt = register_debt_payment(selected_debt.get('ID Deuda'), payment_amount)
    
    if updated_debt:
        new_pending = updated_debt.get('Saldo Pendiente')
        if new_pending <= 0:
            await update.message.reply_text(f"✅ ¡Pago registrado! La deuda de {updated_debt.get('Nombre')} ha sido saldada por completo.", parse_mode='Markdown')
        else:
            await update.message.reply_text(f"✅ ¡Pago registrado! El nuevo saldo pendiente para {updated_debt.get('Nombre')} es de ${new_pending:,.2f}.", parse_mode='Markdown')
    else:
        await update.message.reply_text("⚠️ Hubo un error al registrar el pago.")
        
    return await start_debt_menu(update, context)


# Flujo: Modificar Deuda
async def start_modify_debt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    active_debts = get_active_debts()

    if not active_debts:
        await query.edit_message_text("No hay deudas activas para modificar en este momento.")
        return await start_debt_menu(update, context)

    context.user_data['modify_debts'] = active_debts

    buttons = []
    for debt in active_debts:
        debt_id = debt.get('ID Deuda')
        name = debt.get('Nombre')
        pending = parse_float(str(debt.get('Saldo Pendiente', '0')))
        label = f"{name} - Saldo: ${pending:,.2f}"
        buttons.append((label, f"mod_debt_id_{debt_id}"))

    button_rows = build_button_rows(1, buttons)
    button_rows.append([InlineKeyboardButton("Volver", callback_data="debt_back_to_menu")])
    reply_markup = InlineKeyboardMarkup(button_rows)

    await query.edit_message_text(
        "Modificar Deuda\n\nSelecciona la deuda que deseas aumentar:",
        reply_markup=reply_markup
    )
    return MODIFY_DEBT_CHOOSE_DEBT

async def modify_debt_choose_debt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    debt_id = query.data.replace("mod_debt_id_", "")
    stored_debts = context.user_data.get('modify_debts', [])
    selected_debt = next((d for d in stored_debts if d.get('ID Deuda') == debt_id), None)

    if not selected_debt:
        active_debts = get_active_debts()
        selected_debt = next((d for d in active_debts if d.get('ID Deuda') == debt_id), None)

    if not selected_debt:
        await query.edit_message_text("No se encontro la deuda seleccionada.")
        return await start_debt_menu(update, context)

    context.user_data['selected_debt'] = selected_debt
    pending_amount = parse_float(str(selected_debt.get('Saldo Pendiente', '0')))

    await query.edit_message_text(
        f"Deuda de {selected_debt.get('Nombre')}.\nSaldo pendiente actual: ${pending_amount:,.2f}\n\nIngresa el monto adicional para aumentar la deuda (sin puntos ni comas):{RESTART_PROMPT}",
        parse_mode='Markdown'
    )
    return MODIFY_DEBT_GET_AMOUNT

async def modify_debt_get_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text:
        return MODIFY_DEBT_GET_AMOUNT

    event_id = f"{update.effective_user.id}-{update.message.message_id}"
    if not check_and_set_event_processed(event_id):
        logger.warning(f"Modificacion de deuda {event_id} ya procesada. Se omite el reintento.")
        return await display_main_menu(update, context, "Operacion finalizada.", send_as_new=True)

    additional_amount = parse_float(update.message.text)
    if not additional_amount or additional_amount <= 0:
        await update.message.reply_text("Monto invalido. Ingresa un numero positivo:")
        return MODIFY_DEBT_GET_AMOUNT

    selected_debt = context.user_data.get('selected_debt')
    if not selected_debt:
        await update.message.reply_text("No se encontro la deuda seleccionada. Vuelve a intentarlo desde el menu.")
        return await display_main_menu(update, context, "Operacion finalizada.", send_as_new=True)

    updated_debt = increase_debt_amount(selected_debt.get('ID Deuda'), additional_amount)

    if updated_debt:
        await update.message.reply_text(
            f"✅ Deuda actualizada.\nSe sumaron ${additional_amount:,.2f} a la deuda de {updated_debt.get('Nombre')}.\nNuevo saldo pendiente: ${updated_debt.get('Saldo Pendiente'):,.2f}.",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("�s��,? Hubo un error al actualizar la deuda. Intentalo nuevamente.")

    context.user_data.pop('selected_debt', None)
    context.user_data.pop('modify_debts', None)

    return await display_main_menu(update, context, "Operacion finalizada.", send_as_new=True)

# Flujo: Consultar Deudas
async def query_debts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    active_debts = get_active_debts()

    if not active_debts:
        await query.edit_message_text("👍 ¡Excelente! No hay deudas pendientes de pago.", reply_markup=None)
    else:
        response_parts = ["📋 Resumen de Deudas Activas\n"]
        total_debt = 0
        for debt in sorted(active_debts, key=lambda x: str(get_value_from_dict_insensitive(x, "Nombre") or '')):
            name = get_value_from_dict_insensitive(debt, "Nombre")
            pending = parse_float(str(get_value_from_dict_insensitive(debt, "Saldo Pendiente") or '0'))
            total_debt += pending
            response_parts.append(f"- {name}: Debe ${pending:,.2f}")

        response_parts.append("-" * 20)
        response_parts.append(f"💰 Total adeudado: ${total_debt:,.2f}")

        await query.edit_message_text("\n".join(response_parts), parse_mode='Markdown', reply_markup=None)
    
    return await start_debt_menu(update, context, send_as_new=True)
