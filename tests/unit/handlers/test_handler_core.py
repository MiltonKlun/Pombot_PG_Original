import pytest
pytestmark = pytest.mark.unit

# tests/test_handler_core.py
"""Unit tests for handlers/core.py — Risk R6: unauthorized access."""
from unittest.mock import patch, AsyncMock, MagicMock
from telegram.ext import ConversationHandler
from constants import MAIN_MENU
from tests.helpers.telegram_factories import make_update, make_context


class TestIsAllowedUser:
    """Tests for is_allowed_user — authorization gate."""

    @pytest.mark.asyncio
    @patch("handlers.core.ALLOWED_USER_IDS", [12345])
    async def test_allowed_user_returns_true(self):
        from handlers.core import is_allowed_user
        update = make_update(text="hi")
        result = await is_allowed_user(update)
        assert result is True

    @pytest.mark.asyncio
    @patch("handlers.core.ALLOWED_USER_IDS", [99999])
    async def test_unauthorized_user_returns_false(self):
        from handlers.core import is_allowed_user
        update = make_update(text="hi", user_id=12345)
        result = await is_allowed_user(update)
        assert result is False

    @pytest.mark.asyncio
    @patch("handlers.core.ALLOWED_USER_IDS", [99999])
    async def test_unauthorized_user_sends_denial_message(self):
        from handlers.core import is_allowed_user
        update = make_update(text="hi", user_id=12345)
        await is_allowed_user(update)
        update.message.reply_text.assert_called()


class TestStartCommand:
    """Tests for start_command — entry point."""

    @pytest.mark.asyncio
    @patch("handlers.core.is_connected", return_value=True)
    @patch("handlers.core.ALLOWED_USER_IDS", [12345])
    @patch("handlers.core.display_main_menu", new_callable=AsyncMock, return_value=MAIN_MENU)
    async def test_allowed_and_connected_returns_main_menu(self, mock_menu, mock_is_connected):
        from handlers.core import start_command
        update = make_update(text="/start")
        context = make_context()
        result = await start_command(update, context)
        assert result == MAIN_MENU

    @pytest.mark.asyncio
    @patch("handlers.core.is_connected", return_value=False)
    @patch("handlers.core.ALLOWED_USER_IDS", [12345])
    async def test_not_connected_returns_end(self, mock_is_connected):
        from handlers.core import start_command
        update = make_update(text="/start")
        context = make_context()
        result = await start_command(update, context)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    @patch("handlers.core.ALLOWED_USER_IDS", [99999])
    async def test_unauthorized_returns_end(self):
        from handlers.core import start_command
        update = make_update(text="/start", user_id=12345)
        context = make_context()
        result = await start_command(update, context)
        assert result == ConversationHandler.END


class TestCancelCommand:
    """Tests for cancel_command — emergency exit."""

    @pytest.mark.asyncio
    async def test_clears_user_data_and_returns_end(self):
        from handlers.core import cancel_command
        update = make_update(text="/cancel")
        context = make_context(user_data={"sale_flow": {"product": "X"}})
        result = await cancel_command(update, context)
        assert result == ConversationHandler.END
        assert context.user_data == {}

    @pytest.mark.asyncio
    async def test_sends_cancellation_message(self):
        from handlers.core import cancel_command
        update = make_update(text="/cancel")
        context = make_context()
        await cancel_command(update, context)
        update.message.reply_text.assert_called_once()


class TestHandleTimeoutState:
    """Tests for handle_timeout_state — session timeout."""

    @pytest.mark.asyncio
    async def test_sends_timeout_message_and_returns_end(self):
        from handlers.core import handle_timeout_state
        update = make_update(text="anything")
        context = make_context(chat_data={"chat_id": 67890})
        result = await handle_timeout_state(update, context)
        assert result == ConversationHandler.END
        context.bot.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_clears_user_data_on_timeout(self):
        from handlers.core import handle_timeout_state
        update = make_update(text="anything")
        context = make_context(user_data={"a": 1}, chat_data={"chat_id": 67890})
        await handle_timeout_state(update, context)
        assert context.user_data == {}


class TestBuildButtonRows:
    """Tests for build_button_rows — keyboard layout utility."""

    def test_creates_rows_of_correct_size(self):
        from handlers.core import build_button_rows
        buttons = [("A", "a"), ("B", "b"), ("C", "c"), ("D", "d"), ("E", "e")]
        rows = build_button_rows(2, buttons)
        assert len(rows) == 3  # 2 + 2 + 1
        assert len(rows[0]) == 2
        assert len(rows[2]) == 1

    def test_single_row(self):
        from handlers.core import build_button_rows
        buttons = [("A", "a"), ("B", "b")]
        rows = build_button_rows(2, buttons)
        assert len(rows) == 1

    def test_empty_list(self):
        from handlers.core import build_button_rows
        rows = build_button_rows(2, [])
        assert rows == []


class TestUnknownCommand:
    """Tests for unknown_command."""

    @pytest.mark.asyncio
    @patch("handlers.core.ALLOWED_USER_IDS", [12345])
    async def test_replies_to_unknown_text(self):
        from handlers.core import unknown_command
        update = make_update(text="foo")
        context = make_context()
        await unknown_command(update, context)
        update.message.reply_text.assert_called_with("Comando no reconocido. Usa /start para volver al menú.")

    @pytest.mark.asyncio
    @patch("handlers.core.ALLOWED_USER_IDS", [99999])
    async def test_ignores_unauthorized_user(self):
        from handlers.core import unknown_command
        update = make_update(text="foo", user_id=12345)
        context = make_context()
        await unknown_command(update, context)
        # Should NOT reply with "Comando no reconocido", but is_allowed_user sends "No tienes permiso"
        assert update.message.reply_text.call_count == 1
        assert "No tienes permiso" in update.message.reply_text.call_args[0][0]


class TestHandleMainMenuChoice:
    """Tests main menu routing logic."""

    @pytest.mark.asyncio
    @patch("handlers.core.ALLOWED_USER_IDS", [12345])
    @patch("handlers.sales.start_add_sale", new_callable=AsyncMock, return_value=10)
    async def test_routes_to_sales(self, mock_sales):
        from handlers.core import handle_main_menu_choice
        update = make_update(callback_data="main_add_sale")
        context = make_context()
        
        result = await handle_main_menu_choice(update, context)
        
        assert result == 10
        mock_sales.assert_called_once()

    @pytest.mark.asyncio
    @patch("handlers.core.ALLOWED_USER_IDS", [12345])
    @patch("handlers.expenses.start_add_expense", new_callable=AsyncMock, return_value=30)
    async def test_routes_to_expenses(self, mock_expenses):
        from handlers.core import handle_main_menu_choice
        update = make_update(callback_data="main_add_expense")
        context = make_context()
        
        result = await handle_main_menu_choice(update, context)
        
        assert result == 30
        mock_expenses.assert_called_once()

    @pytest.mark.asyncio
    @patch("handlers.core.ALLOWED_USER_IDS", [12345])
    async def test_ignores_invalid_choice(self):
        from handlers.core import handle_main_menu_choice
        update = make_update(callback_data="invalid_action")
        context = make_context()
        
        result = await handle_main_menu_choice(update, context)
        
        assert result == MAIN_MENU


class TestSyncProductsCommand:
    """Tests for /sync_products."""

    @pytest.mark.asyncio
    @patch("handlers.core.ALLOWED_USER_IDS", [12345])
    @patch("handlers.core.get_tiendanube_products")
    @patch("handlers.core.update_products_from_tiendanube")
    async def test_sync_success(self, mock_update, mock_get_tn):
        from handlers.core import sync_products_command
        mock_get_tn.return_value = [{"id": 1}]
        mock_update.return_value = (True, "Datos actualizados")
        
        update = make_update(text="/sync_products")
        context = make_context()
        
        await sync_products_command(update, context)
        
        # 1. "Iniciando..."
        # 2. "Exito..."
        assert update.message.reply_text.call_count == 2
        args, _ = update.message.reply_text.call_args
        assert "Sincronización completada" in args[0]

    @pytest.mark.asyncio
    @patch("handlers.core.ALLOWED_USER_IDS", [12345])
    @patch("handlers.core.get_tiendanube_products", side_effect=Exception("API Down"))
    async def test_sync_exception(self, mock_get_tn):
        from handlers.core import sync_products_command
        update = make_update(text="/sync_products")
        context = make_context()
        
        await sync_products_command(update, context)
        
        args, _ = update.message.reply_text.call_args
        assert "Error inesperado" in args[0]
