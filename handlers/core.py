import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import ALLOWED_USER_IDS
from sheet import IS_SHEET_CONNECTED, update_products_from_tiendanube
from services.tiendanube_service import get_tiendanube_products
from constants import MAIN_MENU

logger = logging.getLogger(__name__)

def build_button_rows(buttons_per_row: int, button_labels_and_data: list[tuple[str, str]]) -> list[list[InlineKeyboardButton]]:
    keyboard = []
    row = []
    for label, data in button_labels_and_data:
        row.append(InlineKeyboardButton(label, callback_data=data))
        if len(row) == buttons_per_row:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    return keyboard

async def display_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, message_text: str = None, send_as_new: bool = False):
    context.user_data.clear()
    buttons = [
        ("📊 Registrar Venta", 'main_add_sale'),
        ("📦 Registrar Mayorista", 'main_add_wholesale'),
        ("💸 Registrar Gasto", 'main_add_expense'),
        ("💳 Deudas", 'main_debts'),
        ("📈 Consultar Balance", 'main_query_balance_start')
    ]
    reply_markup = InlineKeyboardMarkup(build_button_rows(1, buttons))
    text_to_send = message_text if message_text is not None else "Hola! 👋 Soy tu asistente de finanzas. ¿Qué deseas hacer?"

    query = update.callback_query
    if send_as_new or not query:
        if update.effective_chat:
             await update.effective_chat.send_message(text_to_send, reply_markup=reply_markup)
    else: 
        try:
            await query.edit_message_text(text_to_send, reply_markup=reply_markup)
        except Exception:
             if update.effective_chat:
                await update.effective_chat.send_message(text_to_send, reply_markup=reply_markup)

    return MAIN_MENU

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await is_allowed_user(update): return ConversationHandler.END
    if not IS_SHEET_CONNECTED:
        if update.message: await update.message.reply_text("⚠️ Error Crítico: No se pudo conectar a Google Sheets.")
        return ConversationHandler.END
    if update.effective_chat:
        context.chat_data['chat_id'] = update.effective_chat.id
    return await display_main_menu(update, context)

async def back_to_main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    return await display_main_menu(update, context)

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Este comando es un 'escape de emergencia', por eso termina la conversación.
    # El botón 'Volver al Menú' usa back_to_main_menu_handler que es más suave.
    message_service = update.message or update.callback_query
    if message_service:
        await message_service.reply_text("Operación cancelada forzosamente. Usa /start para iniciar de nuevo.")
    context.user_data.clear()
    return ConversationHandler.END

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_allowed_user(update) and update.message: 
        await update.message.reply_text("Comando no reconocido. Usa /start para volver al menú.")

async def handle_main_menu_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # --- Imports locales ---
    from .sales import start_add_sale
    from .expenses import start_add_expense
    from .debts import start_debt_menu
    from .balance import query_balance_start_handler
    from .wholesale import start_add_wholesale
    
    query = update.callback_query; await query.answer()
    if not await is_allowed_user(update): return ConversationHandler.END
    
    action_map = {
        'main_add_sale': start_add_sale,
        'main_add_wholesale': start_add_wholesale,
        'main_add_expense': start_add_expense, 
        'main_debts': start_debt_menu,
        'main_query_balance_start': query_balance_start_handler
    }
    
    if query.data in action_map: 
        return await action_map[query.data](update, context)
    return MAIN_MENU

async def handle_timeout_state(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info("La conversación ha finalizado por timeout.")
    chat_id = context.chat_data.get('chat_id')
    if not chat_id and context._user_id:
        chat_id = context._user_id

    if chat_id:
        try:
            await context.bot.send_message(
                chat_id=chat_id, 
                text="⏰ Tu sesión ha finalizado por inactividad. Presiona /start para iniciar nuevamente."
            )
        except Exception as e:
            logger.error(f"No se pudo enviar el mensaje de timeout al chat {chat_id}: {e}")
    else:
        logger.warning("No se pudo determinar el chat_id para enviar el mensaje de timeout.")
        
    context.user_data.clear()
    context.chat_data.clear()
    return ConversationHandler.END

async def is_allowed_user(update: Update) -> bool:
    user_id = update.effective_user.id
    if user_id in ALLOWED_USER_IDS: return True
    logger.warning(f"Acceso denegado para usuario ID: {user_id}")
    message_service = update.message or update.callback_query
    if message_service:
        try:
            if update.callback_query: await message_service.answer("⛔ No tienes permiso.", show_alert=True)
            await (update.callback_query.edit_message_text if update.callback_query else message_service.reply_text)("⛔ No tienes permiso para usar este bot.")
        except Exception: pass
    return False

async def sync_products_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_allowed_user(update) or not update.message: return
    await update.message.reply_text("⚙️ Iniciando sincronización de variantes...")
    try:
        tiendanube_data = get_tiendanube_products()
        success, message = update_products_from_tiendanube(tiendanube_data)
        final_message = f"✅ ¡Sincronización completada! {message}" if success else f"⚠️ Error en la sincronización: {message}"
        await update.message.reply_text(final_message)
    except Exception as e:
        logger.error(f"Error inesperado durante /sync_products", exc_info=True)
        await update.message.reply_text(f"💥 Error inesperado al sincronizar: {e}")