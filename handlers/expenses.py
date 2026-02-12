import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from constants import *
from config import EXPENSE_CATEGORIES, EXPENSE_SUBCATEGORIES, RESTART_PROMPT
from sheet import add_expense, check_and_set_event_processed 
from common.utils import parse_float, parse_int
from .core import display_main_menu, build_button_rows
from .checks import start_checks_menu

logger = logging.getLogger(__name__)

async def start_add_expense(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    buttons = [(cat, f"exp_cat_{cat}") for cat in EXPENSE_CATEGORIES]
    buttons.append(("🧾 Cheques", "exp_cat_CHEQUES")) # Botón para el nuevo módulo
    
    button_rows = build_button_rows(2, buttons)
    button_rows.append([InlineKeyboardButton("🔙 Volver al Menú", callback_data="cancel_to_main")])
    reply_markup = InlineKeyboardMarkup(button_rows)
    await query.edit_message_text("💸 Registrar Gasto\n\nSelecciona una categoría:", reply_markup=reply_markup)
    context.user_data['expense_flow'] = {}
    return ADD_EXPENSE_CHOOSE_CATEGORY

async def expense_choose_category_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    selected_category = query.data.replace("exp_cat_", "")
    context.user_data['expense_flow'] = {'category': selected_category}

    if selected_category == "CHEQUES":
        return await start_checks_menu(update, context)

    if selected_category == "CANJES":
        await query.edit_message_text(f"Registrando Canje\n\n👤 Ingresa el nombre de la persona o entidad del canje:{RESTART_PROMPT}", parse_mode='Markdown')
        return ADD_EXPENSE_CANJE_GET_ENTITY

    if selected_category == "PROVEEDORES":
        await query.edit_message_text(f"Gasto de Proveedor\n\n👤 Ingresa el nombre del proveedor:{RESTART_PROMPT}", parse_mode='Markdown')
        return ADD_EXPENSE_PROVEEDORES_GET_NAME

    if selected_category in EXPENSE_SUBCATEGORIES:
        subcategories = EXPENSE_SUBCATEGORIES[selected_category]
        buttons = [(sub, f"exp_subcat_{sub}") for sub in subcategories]
        button_rows = build_button_rows(2, buttons)
        button_rows.append([InlineKeyboardButton("🔙 Elegir otra Categoría", callback_data="back_to_exp_cat_sel")])
        reply_markup = InlineKeyboardMarkup(button_rows)

        await query.edit_message_text(f"Categoría: {selected_category}\n\nSelecciona la subcategoría:", reply_markup=reply_markup, parse_mode='Markdown')
        return ADD_EXPENSE_CHOOSE_SUBCATEGORY
    else:
        context.user_data['expense_flow']['subcategory'] = ''
        await query.edit_message_text(f"Categoría: {selected_category}\n\nIngresa una descripción para el gasto:{RESTART_PROMPT}", parse_mode='Markdown')
        return ADD_EXPENSE_INPUT_DESCRIPTION

# --- Flujo de Canjes ---
async def expense_canje_get_entity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text: return ADD_EXPENSE_CANJE_GET_ENTITY
    context.user_data['expense_flow']['entity'] = update.message.text.strip()
    await update.message.reply_text(f"🏷️ Ingresa el artículo que se canjea:{RESTART_PROMPT}")
    return ADD_EXPENSE_CANJE_GET_ITEM

async def expense_canje_get_item(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text: return ADD_EXPENSE_CANJE_GET_ITEM
    context.user_data['expense_flow']['item'] = update.message.text.strip()
    await update.message.reply_text(f"🔢 Ingresa la cantidad de unidades:{RESTART_PROMPT}")
    return ADD_EXPENSE_CANJE_GET_QUANTITY

async def expense_canje_get_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text: return ADD_EXPENSE_CANJE_GET_QUANTITY
    quantity = parse_int(update.message.text)
    if not quantity or quantity <= 0:
        await update.message.reply_text(f"Cantidad inválida. Ingresa un número entero positivo:{RESTART_PROMPT}")
        return ADD_EXPENSE_CANJE_GET_QUANTITY
    context.user_data['expense_flow']['quantity'] = quantity
    await update.message.reply_text(f"💵 Ingresa el monto total del canje (sin puntos ni comas):{RESTART_PROMPT}")
    return ADD_EXPENSE_INPUT_AMOUNT

# --- Flujo de Proveedores ---
async def expense_proveedores_get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text: return ADD_EXPENSE_PROVEEDORES_GET_NAME
    context.user_data['expense_flow']['provider_name'] = update.message.text.strip()
    await update.message.reply_text(f"🏷️ Ingresa el artículo o servicio adquirido:{RESTART_PROMPT}")
    return ADD_EXPENSE_PROVEEDORES_GET_ITEM

async def expense_proveedores_get_item(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text: return ADD_EXPENSE_PROVEEDORES_GET_ITEM
    context.user_data['expense_flow']['item'] = update.message.text.strip()
    await update.message.reply_text(f"🔢 Ingresa la cantidad de unidades:{RESTART_PROMPT}")
    return ADD_EXPENSE_PROVEEDORES_GET_QUANTITY

async def expense_proveedores_get_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text: return ADD_EXPENSE_PROVEEDORES_GET_QUANTITY
    quantity = parse_int(update.message.text)
    if not quantity or quantity <= 0:
        await update.message.reply_text(f"Cantidad inválida. Ingresa un número entero positivo:{RESTART_PROMPT}")
        return ADD_EXPENSE_PROVEEDORES_GET_QUANTITY
    context.user_data['expense_flow']['quantity'] = quantity
    await update.message.reply_text(f"💵 Ingresa el monto total del gasto (sin puntos ni comas):{RESTART_PROMPT}")
    return ADD_EXPENSE_INPUT_AMOUNT

async def expense_choose_subcategory_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer()

    if query.data == "back_to_exp_cat_sel":
        return await start_add_expense(update, context)

    selected_subcategory = query.data.replace("exp_subcat_", "")
    context.user_data['expense_flow']['subcategory'] = selected_subcategory
    category = context.user_data['expense_flow']['category']

    if category == "PERSONALES" and selected_subcategory != "GENERAL":
        context.user_data['expense_flow']['description'] = selected_subcategory
        await query.edit_message_text(
            f"Categoría: {category}\nSubcategoría: {selected_subcategory}\n\nIngresa el monto del gasto (sin puntos ni comas):{RESTART_PROMPT}",
            parse_mode='Markdown'
        )
        return ADD_EXPENSE_INPUT_AMOUNT

    await query.edit_message_text(
        f"Categoría: {category}\nSubcategoría: {selected_subcategory}\n\nIngresa una descripción para el gasto:{RESTART_PROMPT}",
        parse_mode='Markdown'
    )
    return ADD_EXPENSE_INPUT_DESCRIPTION

async def expense_input_description_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text: return ADD_EXPENSE_INPUT_DESCRIPTION
    context.user_data['expense_flow']['description'] = update.message.text
    await update.message.reply_text(f"Ingresa el monto del gasto (sin puntos ni comas):{RESTART_PROMPT}")
    return ADD_EXPENSE_INPUT_AMOUNT

async def expense_input_amount_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text: return ADD_EXPENSE_INPUT_AMOUNT
    
    event_id = f"{update.effective_user.id}-{update.message.message_id}"
    if not check_and_set_event_processed(event_id):
        logger.warning(f"Operación de gasto {event_id} ya procesada. Se omite el reintento.")
        return await display_main_menu(update, context, "Operación finalizada.", send_as_new=True)

    amount = parse_float(update.message.text)
    if not amount or amount <= 0:
        await update.message.reply_text(f"Monto inválido. Ingresa un número positivo:{RESTART_PROMPT}")
        return ADD_EXPENSE_INPUT_AMOUNT

    try:
        flow_data = context.user_data['expense_flow']
        category = flow_data['category']

        # Construir los datos para la hoja de cálculo
        if category == "CANJES":
            subcategory = flow_data.get('item', '')
            description = flow_data.get('entity', '')
            quantity = flow_data.get('quantity', 0)
            details = f"Cantidad: {quantity}"
        elif category == "PROVEEDORES":
            subcategory = ''
            description = flow_data.get('provider_name', '')
            item = flow_data.get('item', '')
            quantity = flow_data.get('quantity', 0)
            details = f"Artículo: {item} (Cantidad: {quantity})"
        else:
            subcategory = flow_data.get('subcategory', '')
            description = flow_data.get('description', '')
            details = ''

        expense_data = add_expense(
            category=category,
            subcategory=subcategory,
            description=description,
            details=details,
            amount=amount
        )

        # Construir el mensaje de confirmación
        confirmation_text = f"✅ Gasto Registrado ✅\n\nCategoría: {expense_data['category']}\n"
        if expense_data['subcategory']:
            confirmation_text += f"Subcategoría: {expense_data['subcategory']}\n"
        confirmation_text += (
            f"Descripción: {expense_data['description']}\n"
        )
        if expense_data['details']:
             confirmation_text += f"Detalles: {expense_data['details']}\n"
        confirmation_text += (
            f"Monto: ${expense_data['amount']:,.2f}\n"
            f"Hoja: '{expense_data['sheet_title']}'"
        )

        await update.message.reply_text(confirmation_text, parse_mode='Markdown')

    except Exception:
        logger.error("Error registrando gasto", exc_info=True)
        await update.message.reply_text("⚠️ Hubo un error al registrar el gasto.")

    return await display_main_menu(update, context, "Gasto registrado con éxito.", send_as_new=True)