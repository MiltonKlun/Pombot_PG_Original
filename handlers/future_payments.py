import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from constants import *
from config import RESTART_PROMPT
from sheet import add_future_payment, get_pending_future_payments
from common.utils import parse_float, parse_int
from .core import display_main_menu, build_button_rows

logger = logging.getLogger(__name__)


async def start_fp_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    buttons = [
        ("Recibir Pago Futuro", "fp_recibir"),
        ("Consultar Pagos Futuros", "fp_consult"),
        ("Volver al Menú Principal", "cancel_to_main")
    ]
    reply_markup = InlineKeyboardMarkup(build_button_rows(1, buttons))
    await query.edit_message_text("Módulo de Pagos Futuros\n\nElige una opción:", reply_markup=reply_markup)
    return FUTURE_PAYMENTS_MENU


async def fp_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    if query.data == "fp_consult":
        await query.edit_message_text("Buscando pagos pendientes...")
        pending_payments = get_pending_future_payments()
        if not pending_payments:
            await query.edit_message_text("No hay pagos futuros pendientes.")
        else:
            lines = ["Pagos Futuros Pendientes (Recibidos)\n"]
            for payment in pending_payments:
                tipo = "RECIBIDO"
                entidad = payment.get("Entidad", "N/A")
                producto = payment.get("Producto", "Pago Futuro")
                cantidad = payment.get("Cantidad", "N/A")
                monto = parse_float(str(payment.get("Monto Final", 0))) or 0.0
                fecha = payment.get("Fecha Cobro", "N/A")
                lines.append(f"- {tipo} de {entidad} | {producto} x{cantidad} | ${monto:,.2f} (Cobro: {fecha})")
            await query.edit_message_text("\n".join(lines), parse_mode='Markdown')
        return await display_main_menu(update, context, send_as_new=True)

    context.user_data['fp_flow'] = {}
    await query.edit_message_text(f"Recibiendo Pago Futuro.\n\nIngresa la entidad o cliente:{RESTART_PROMPT}")
    return FUTURE_PAYMENTS_GET_ENTITY


# Flujo de Registro de Pago Futuro
async def fp_get_entity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text:
        return FUTURE_PAYMENTS_GET_ENTITY
    context.user_data['fp_flow']['entity'] = update.message.text.strip()
    await update.message.reply_text(f"Ingresa el producto asociado al pago:{RESTART_PROMPT}")
    return FUTURE_PAYMENTS_GET_PRODUCT


async def fp_get_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text:
        return FUTURE_PAYMENTS_GET_PRODUCT
    context.user_data['fp_flow']['product'] = update.message.text.strip()
    await update.message.reply_text(f"Ingresa la cantidad (unidades):{RESTART_PROMPT}")
    return FUTURE_PAYMENTS_GET_QUANTITY


async def fp_get_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text:
        return FUTURE_PAYMENTS_GET_QUANTITY
    qty = parse_int(update.message.text)
    if not qty or qty <= 0:
        await update.message.reply_text(f"Cantidad inválida. Ingresa un número entero positivo:{RESTART_PROMPT}")
        return FUTURE_PAYMENTS_GET_QUANTITY
    context.user_data['fp_flow']['quantity'] = qty
    await update.message.reply_text(f"Ingresa el monto INICIAL del pago:{RESTART_PROMPT}")
    return FUTURE_PAYMENTS_GET_INITIAL_AMOUNT


async def fp_get_initial_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text:
        return FUTURE_PAYMENTS_GET_INITIAL_AMOUNT
    amount = parse_float(update.message.text)
    if not amount or amount <= 0:
        await update.message.reply_text("Monto inválido.")
        return FUTURE_PAYMENTS_GET_INITIAL_AMOUNT
    context.user_data['fp_flow']['initial_amount'] = amount
    await update.message.reply_text(f"Ingresa el monto de la COMISION (si no hay, ingresa 0):{RESTART_PROMPT}")
    return FUTURE_PAYMENTS_GET_COMMISSION


async def fp_get_commission(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text:
        return FUTURE_PAYMENTS_GET_COMMISSION
    commission = parse_float(update.message.text)
    if commission is None or commission < 0:
        await update.message.reply_text("Comisión inválida.")
        return FUTURE_PAYMENTS_GET_COMMISSION
    context.user_data['fp_flow']['commission'] = commission
    await update.message.reply_text(f"Ingresa la fecha de COBRO (dd/mm/aaaa):{RESTART_PROMPT}")
    return FUTURE_PAYMENTS_GET_DUE_DATE


async def fp_get_due_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text:
        return FUTURE_PAYMENTS_GET_DUE_DATE
    context.user_data['fp_flow']['due_date'] = update.message.text.strip()
    
    flow = context.user_data['fp_flow']
    try:
        add_future_payment(
            entity=flow['entity'],
            product=flow['product'],
            quantity=flow['quantity'],
            initial_amount=flow['initial_amount'],
            commission=flow['commission'],
            due_date=flow['due_date']
        )
        final_amount = flow['initial_amount'] - flow['commission']
        await update.message.reply_text(
            "Pago Futuro Recibido registrado:\n"
            f"Entidad: {flow['entity']}\n"
            f"Producto: {flow['product']}\n"
            f"Cantidad: {flow['quantity']}\n"
            f"Monto Inicial: ${flow['initial_amount']:,.2f}\n"
            f"Comisión: -${flow['commission']:,.2f}\n"
            f"Monto Final: ${final_amount:,.2f}",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error registrando Pago Futuro: {e}", exc_info=True)
        await update.message.reply_text("Hubo un error al registrar el Pago Futuro.")

    return await display_main_menu(update, context, "Operación finalizada.", send_as_new=True)
