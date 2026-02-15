import logging
import math
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from constants import *
from config import PRODUCTOS_SHEET_NAME, RESTART_PROMPT, SALES_SHEET_BASE_NAME, SALES_HEADERS
from sheet import (
    get_or_create_monthly_sheet, get_product_categories, get_products_by_category, 
    get_variant_details, get_product_options, add_sale, check_and_set_event_processed
)
from services.tiendanube_service import get_realtime_stock
from common.utils import parse_int
from .core import display_main_menu, build_button_rows

logger = logging.getLogger(__name__)

def create_paginated_keyboard(product_list: list, page: int = 0, items_per_page: int = 10) -> InlineKeyboardMarkup:
    """Crea un teclado con botones de producto paginados."""
    total_items = len(product_list)
    total_pages = math.ceil(total_items / items_per_page)
    
    start_index = page * items_per_page
    end_index = start_index + items_per_page
    
    # Botones de productos para la página actual
    buttons = [(prod, f"sale_prod_{i + start_index}") for i, prod in enumerate(product_list[start_index:end_index])]
    keyboard = build_button_rows(1, buttons)
    
    # Botones de navegación
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Anterior", callback_data=f"prod_page_{page - 1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("Siguiente ➡️", callback_data=f"prod_page_{page + 1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
        
    # Botón para volver al menú de categorías
    keyboard.append([InlineKeyboardButton("🔙 Elegir otra Categoría", callback_data="back_to_sale_cat_sel")])
    
    return InlineKeyboardMarkup(keyboard)

async def start_add_sale(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query: await query.answer()
    logger.info("Iniciando flujo 'Registrar Venta'.")
    
    logger.info("Verificando/Creando hoja de ventas mensual...")
    sales_sheet = get_or_create_monthly_sheet(SALES_SHEET_BASE_NAME, SALES_HEADERS)
    if not sales_sheet:
        error_message = "⚠️ Error crítico: No se pudo crear o acceder a la hoja de Ventas. Por favor, contacta al administrador."
        if query:
            await query.edit_message_text(error_message)
        elif update.message:
            await update.message.reply_text(error_message)
        return await display_main_menu(update, context, "Operación cancelada.", send_as_new=True)

    logger.info("Obteniendo categorías de productos...")
    categories = get_product_categories()
    
    if not categories:
        error_message = f"⚠️ No se encontraron categorías en la hoja '{PRODUCTOS_SHEET_NAME}'.\n\nAsegúrate de haber ejecutado /sync_products al menos una vez."
        return await display_main_menu(update, context, error_message)
    
    context.user_data['sale_flow'] = {}
    buttons = [(cat, f"sale_cat_{cat}") for cat in categories]
    button_rows = build_button_rows(2, buttons)
    button_rows.append([InlineKeyboardButton("🔙 Volver al Menú", callback_data="cancel_to_main")])
    reply_markup = InlineKeyboardMarkup(button_rows)
    
    text = "🛒 Registrar Venta\nSelecciona la categoría:"
    if query:
        await query.edit_message_text(text, reply_markup=reply_markup)
    elif update.message:
        await update.message.reply_text(text, reply_markup=reply_markup)
        
    return ADD_SALE_CHOOSE_CATEGORY

async def sale_choose_category_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer()
    
    selected_category = query.data.replace("sale_cat_", "")
    context.user_data['sale_flow']['category'] = selected_category
    
    products = get_products_by_category(selected_category)
    if not products:
        return await display_main_menu(update, context, f"No se encontraron productos para '{selected_category}'.")

    # Guardar la lista completa de productos para la paginación
    context.user_data['sale_flow']['product_list'] = products
    
    # Crear el teclado para la primera página (página 0)
    reply_markup = create_paginated_keyboard(products, page=0)
    
    await query.edit_message_text(
        f"Categoría: {selected_category}\nSelecciona el producto (Página 1/{math.ceil(len(products)/10)}):", 
        reply_markup=reply_markup, 
        parse_mode='Markdown'
    )
    return ADD_SALE_CHOOSE_PRODUCT

async def sale_product_pagination_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maneja los clics en los botones 'Anterior' y 'Siguiente'."""
    query = update.callback_query; await query.answer()
    
    page = int(query.data.split("_")[-1])
    
    # Recuperar la lista de productos y la categoría del contexto
    product_list = context.user_data['sale_flow'].get('product_list', [])
    category = context.user_data['sale_flow'].get('category', 'Desconocida')
    
    if not product_list:
        return await display_main_menu(update, context, "Error: Se perdió la lista de productos. Por favor, empieza de nuevo.")

    # Crear y mostrar el teclado para la nueva página
    reply_markup = create_paginated_keyboard(product_list, page=page)
    
    await query.edit_message_text(
        f"Categoría: {category}\nSelecciona el producto (Página {page + 1}/{math.ceil(len(product_list)/10)}):",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return ADD_SALE_CHOOSE_PRODUCT

async def sale_choose_product_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer()
    if query.data == "back_to_sale_cat_sel": return await start_add_sale(update, context)
    
    try:
        product_index = int(query.data.replace("sale_prod_", ""))
        product_list = context.user_data['sale_flow'].get('product_list', [])
        selected_product_name = product_list[product_index]
    except (IndexError, ValueError) as e:
        logger.error(f"Error al obtener el producto por índice: {e}", exc_info=True)
        return await display_main_menu(update, context, "Error al seleccionar el producto. Inténtalo de nuevo.")

    context.user_data['sale_flow']['product_name'] = selected_product_name
    context.user_data['sale_flow']['selections'] = {}

    return await sale_process_next_option(update, context, option_number=1)

async def sale_process_next_option(update: Update, context: ContextTypes.DEFAULT_TYPE, option_number: int) -> int:
    product_name = context.user_data['sale_flow']['product_name']
    prior_selections = context.user_data['sale_flow']['selections']

    option_name, option_values = get_product_options(product_name, option_number, prior_selections)

    if not option_name or not option_values:
        return await sale_ask_for_quantity(update, context)

    context.user_data['sale_flow']['current_option_name_header'] = f"Opción {option_number}: Valor"
    
    selections_text = f"Producto: {product_name}\n"
    for key, value in prior_selections.items():
        clean_key = key.replace("Opción ", "").replace(": Valor", "")
        selections_text += f" ✓ {clean_key}: {value}\n"
    
    buttons = [(val, f"sale_opt{option_number}_{val}") for val in option_values]
    button_rows = build_button_rows(2, buttons)
    
    back_callback = "back_to_prod_sel" if option_number == 1 else f"back_to_opt_{option_number - 1}"
    button_rows.append([InlineKeyboardButton("🔙 Volver", callback_data=back_callback)])

    await update.callback_query.edit_message_text(
        f"{selections_text}\nSelecciona {option_name}:",
        reply_markup=InlineKeyboardMarkup(button_rows),
        parse_mode='Markdown'
    )
    
    return ADD_SALE_CHOOSE_OPTION_1 if option_number == 1 else ADD_SALE_CHOOSE_OPTION_2

async def sale_choose_option1_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer()
    if query.data == "back_to_prod_sel":
        return await start_add_sale(update, context)

    selected_value = query.data.replace("sale_opt1_", "")
    option_name_header = context.user_data['sale_flow']['current_option_name_header']
    context.user_data['sale_flow']['selections'][option_name_header] = selected_value
    
    return await sale_process_next_option(update, context, option_number=2)

async def sale_choose_option2_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer()
    if query.data.startswith("back_to_opt_"):
        context.user_data['sale_flow']['selections'].popitem()
        return await sale_process_next_option(update, context, option_number=1)

    selected_value = query.data.replace("sale_opt2_", "")
    option_name_header = context.user_data['sale_flow']['current_option_name_header']
    context.user_data['sale_flow']['selections'][option_name_header] = selected_value

    return await sale_ask_for_quantity(update, context)

async def sale_ask_for_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    product_name = context.user_data['sale_flow']['product_name']
    selections = context.user_data['sale_flow']['selections']

    variant_details = get_variant_details(product_name, selections)

    if not variant_details:
        return await display_main_menu(update, context, "Error: No se encontró la variante del producto con esas opciones.")

    context.user_data['sale_flow']['variant_details'] = variant_details

    variant_desc_parts = [str(variant_details.get(f"Opción {i}: Valor", "")) for i in range(1, 4)]
    variant_name = " / ".join(filter(None, variant_desc_parts))

    await query.edit_message_text(
        f"Producto: {product_name} ({variant_name})\n"
        f"Precio: ${variant_details.get('Precio Final', 0):,.2f}\n"
        f"Stock: {variant_details.get('Stock', 0)}\n\n"
        f"Ingresa la cantidad vendida:{RESTART_PROMPT}",
        parse_mode='Markdown'
    )
    return ADD_SALE_INPUT_QUANTITY

async def sale_input_quantity_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text: return ADD_SALE_INPUT_QUANTITY

    quantity_sold = parse_int(update.message.text)
    if not quantity_sold or quantity_sold <= 0:
        await update.message.reply_text(f"Cantidad inválida. Ingresa un número entero positivo:{RESTART_PROMPT}")
        return ADD_SALE_INPUT_QUANTITY

    variant_details = context.user_data['sale_flow']['variant_details']
    product_id = variant_details.get("ID Producto")
    variant_id = variant_details.get("ID Variante")

    if not product_id or not variant_id:
        return await display_main_menu(update, context, "Error: No se pudo identificar el producto para verificar el stock.")

    await update.message.reply_text("Verificando stock en tiempo real...")
    realtime_stock = get_realtime_stock(int(product_id), int(variant_id))

    if realtime_stock is None:
        return await display_main_menu(update, context, "⚠️ No se pudo verificar el stock con TiendaNube en este momento. La operación ha sido cancelada.")

    if quantity_sold > realtime_stock:
        await update.message.reply_text(
            f"⚠️ Stock insuficiente.\n\n"
            f"El stock se actualizó mientras procesabas el pedido.\n"
            f"Stock real disponible: {realtime_stock}\n\n"
            "La operación ha sido cancelada."
        )
        return await display_main_menu(update, context, send_as_new=True)

    context.user_data['sale_flow']['variant_details']['Stock'] = realtime_stock
    context.user_data['sale_flow']['quantity_sold'] = quantity_sold
    await update.message.reply_text(f"✅ Stock confirmado.\n👤 Por favor, ingresa el nombre del cliente/comprador:{RESTART_PROMPT}")
    return ADD_SALE_INPUT_CLIENT

async def sale_input_client_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text: return ADD_SALE_INPUT_CLIENT
    client_name = update.message.text.strip()
    if not client_name:
        await update.message.reply_text("El nombre del cliente no puede estar vacío. Por favor, ingrésalo de nuevo:")
        return ADD_SALE_INPUT_CLIENT
        
    event_id = f"{update.effective_user.id}-{update.message.message_id}"
    if not check_and_set_event_processed(event_id):
        logger.warning(f"Operación de venta {event_id} ya procesada. Se omite el reintento.")
        # Simplemente salimos sin hacer nada para no confundir al usuario.
        return await display_main_menu(update, context, "Operación finalizada.", send_as_new=True)

    try:
        variant_details = context.user_data['sale_flow']['variant_details']
        quantity = context.user_data['sale_flow']['quantity_sold']
        sale_data = add_sale(variant_details, quantity, client_name)
        
        await update.message.reply_text(
            f"✅ Venta Registrada ✅\n\n"
            f"Fecha: {sale_data['timestamp'].split(' ')[0]}\n"
            f"Producto: {sale_data['product_name']} ({sale_data['variant_description']})\n"
            f"Cliente: {sale_data['client_name']}\n"
            f"Cantidad: {sale_data['quantity']}\n"
            f"Total: ${sale_data['total_sale_price']:,.2f}\n"
            f"Stock restante: {sale_data['remaining_stock']}\n\n"
            f"Registrado en la hoja: '{sale_data['sheet_title']}'",
            parse_mode='Markdown'
        )
    except Exception:
        logger.error(f"Error registrando venta final", exc_info=True)
        await update.message.reply_text("⚠️ Hubo un error al registrar la venta en la hoja de cálculo.")
    
    return await display_main_menu(update, context, "Operación finalizada.", send_as_new=True)