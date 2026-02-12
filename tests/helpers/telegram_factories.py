# tests/telegram_helpers.py
"""
Reusable test doubles for Telegram handler tests.
Provides factory functions to create mock Update and Context objects.
"""
from unittest.mock import MagicMock, AsyncMock


def make_update(text=None, callback_data=None, user_id=12345):
    """Create a mock telegram.Update with the given text message or callback query."""
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = user_id
    update.effective_chat = MagicMock()
    update.effective_chat.id = 67890

    if text is not None:
        update.message = MagicMock()
        update.message.text = text
        update.message.message_id = 100
        update.message.reply_text = AsyncMock()
        update.callback_query = None
    elif callback_data is not None:
        update.message = None
        update.callback_query = MagicMock()
        update.callback_query.data = callback_data
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()
        update.callback_query.delete_message = AsyncMock()
    else:
        update.message = None
        update.callback_query = None

    return update


def make_context(user_data=None, chat_data=None):
    """Create a mock ContextTypes.DEFAULT_TYPE with the given user/chat data dicts."""
    context = MagicMock()
    context.user_data = user_data if user_data is not None else {}
    context.chat_data = chat_data if chat_data is not None else {}
    context.bot = MagicMock()
    context.bot.send_message = AsyncMock()
    context.bot.send_document = AsyncMock()
    context._user_id = 12345
    return context
