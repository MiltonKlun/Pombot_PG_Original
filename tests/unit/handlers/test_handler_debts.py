import pytest
pytestmark = pytest.mark.unit

# tests/test_handler_debts.py
"""
Unit tests for handlers/debts.py — Risk R3: debt payments.
Expanded to cover Creation, Payment Selection, Modification, and Query flows.
"""
from unittest.mock import patch, AsyncMock, MagicMock
from constants import (
    CREATE_DEBT_GET_NAME, CREATE_DEBT_GET_AMOUNT,
    PAY_DEBT_CHOOSE_DEBT, PAY_DEBT_GET_AMOUNT,
    MODIFY_DEBT_CHOOSE_DEBT, MODIFY_DEBT_GET_AMOUNT,
    DEBT_MENU
)
from config import RESTART_PROMPT
from tests.helpers.telegram_factories import make_update, make_context
import asyncio

# --- 1. Creation Flow ---

class TestCreateDebtGetName:
    """Tests for Step 1: create_debt_get_name"""
    
    @pytest.mark.asyncio
    async def test_stores_name_and_asks_amount(self):
        from handlers.debts import create_debt_get_name
        update = make_update(text=" Juan Perez ")
        context = make_context()
        
        state = await create_debt_get_name(update, context)
        
        assert state == CREATE_DEBT_GET_AMOUNT
        assert context.user_data['debt_name'] == "Juan Perez"
        args, _ = update.message.reply_text.call_args
        assert "monto total" in args[0].lower()

class TestCreateDebtGetAmount:
    """Tests for Step 2: create_debt_get_amount"""

    @pytest.mark.asyncio
    @patch("handlers.debts.start_debt_menu", new_callable=AsyncMock, return_value=DEBT_MENU)
    @patch("handlers.debts.check_and_set_event_processed", return_value=True)
    @patch("handlers.debts.add_new_debt")
    async def test_valid_amount_creates_debt(self, mock_add, mock_event, mock_menu):
        from handlers.debts import create_debt_get_amount
        mock_add.return_value = {"ID Deuda": "D001"}
        update = make_update(text="5000")
        context = make_context(user_data={"debt_name": "Juan"})
        
        await create_debt_get_amount(update, context)
        
        mock_add.assert_called_once_with("Juan", 5000.0)
        # Verify success message and return to menu
        args, _ = update.message.reply_text.call_args
        assert "creada exitosamente" in args[0].lower()
        mock_menu.assert_called_once()

    @pytest.mark.asyncio
    async def test_rejects_invalid_amount(self):
        from handlers.debts import create_debt_get_amount
        update = make_update(text="abc")
        context = make_context(user_data={"debt_name": "Juan"})
        
        result = await create_debt_get_amount(update, context)
        
        assert result == CREATE_DEBT_GET_AMOUNT
        update.message.reply_text.assert_called_with("Monto inválido. Ingresa un número positivo:")


# --- 2. Payment Flow ---

class TestStartPayDebt:
    """Tests for starting payment flow (listing debts)."""

    @pytest.mark.asyncio
    @patch("handlers.debts.get_active_debts")
    async def test_lists_multiple_debts(self, mock_get):
        from handlers.debts import start_pay_debt
        mock_get.return_value = [
            {"ID Deuda": "1", "Nombre": "Juan", "Saldo Pendiente": 1000},
            {"ID Deuda": "2", "Nombre": "Maria", "Saldo Pendiente": 2000}
        ]
        update = make_update(callback_data="debt_pay")
        context = make_context()
        
        state = await start_pay_debt(update, context)
        
        assert state == PAY_DEBT_CHOOSE_DEBT
        # Check that we built a keyboard with 2 debt options + back
        args, default_args = update.callback_query.edit_message_text.call_args
        markup = default_args['reply_markup']
        # 2 debts + 1 back button = 3 rows (assuming build_button_rows(1))
        assert len(markup.inline_keyboard) >= 2 

    @pytest.mark.asyncio
    @patch("handlers.debts.start_debt_menu", new_callable=AsyncMock)
    @patch("handlers.debts.get_active_debts", return_value=[])
    async def test_no_debts_shows_message(self, mock_get, mock_menu):
        from handlers.debts import start_pay_debt
        update = make_update(callback_data="debt_pay")
        context = make_context()
        
        await start_pay_debt(update, context)
        
        update.callback_query.edit_message_text.assert_called_with("👍 ¡No hay deudas activas para registrar pagos!")
        mock_menu.assert_called_once()

class TestPayDebtChooseDebt:
    """Tests for selecting a debt to pay."""

    @pytest.mark.asyncio
    @patch("handlers.debts.get_active_debts")
    async def test_selects_valid_debt(self, mock_get):
        from handlers.debts import pay_debt_choose_debt
        mock_get.return_value = [{"ID Deuda": "100", "Nombre": "Juan", "Saldo Pendiente": 5000}]
        
        update = make_update(callback_data="pay_debt_id_100")
        context = make_context()
        
        state = await pay_debt_choose_debt(update, context)
        
        assert state == PAY_DEBT_GET_AMOUNT
        assert context.user_data['selected_debt']['ID Deuda'] == "100"
        args, _ = update.callback_query.edit_message_text.call_args
        assert "Juan" in args[0]
        assert "5,000.00" in args[0]

class TestPayDebtGetAmount:
    """Tests for entering payment amount."""

    @pytest.mark.asyncio
    @patch("handlers.debts.display_main_menu", new_callable=AsyncMock, return_value=0)
    @patch("handlers.debts.start_debt_menu", new_callable=AsyncMock, return_value=0)
    @patch("handlers.debts.check_and_set_event_processed", return_value=True)
    @patch("handlers.debts.register_debt_payment")
    async def test_valid_payment_calls_register(self, mock_pay, mock_event, mock_menu_start, mock_menu_display):
        from handlers.debts import pay_debt_get_amount
        mock_pay.return_value = {"Nombre": "Juan", "Saldo Pendiente": 3000.0}
        
        update = make_update(text="2000")
        context = make_context(user_data={
            "selected_debt": {"ID Deuda": "D001", "Saldo Pendiente": "5000"}
        })
        
        await pay_debt_get_amount(update, context)
        
        mock_pay.assert_called_once_with("D001", 2000.0)
        args, _ = update.message.reply_text.call_args
        assert "nuevo saldo" in args[0].lower()

    @pytest.mark.asyncio
    @patch("handlers.debts.check_and_set_event_processed", return_value=True)
    async def test_rejects_overpayment(self, mock_event):
        from handlers.debts import pay_debt_get_amount
        update = make_update(text="6000")
        context = make_context(user_data={
            "selected_debt": {"ID Deuda": "D001", "Saldo Pendiente": "5000"}
        })
        
        result = await pay_debt_get_amount(update, context)
        
        assert result == PAY_DEBT_GET_AMOUNT
        args, _ = update.message.reply_text.call_args
        assert "no puede ser mayor" in args[0].lower()


class TestPayDebtError:
    """Tests for error scenarios in Pay Debt flow."""

    @pytest.mark.asyncio
    @patch("handlers.debts.display_main_menu", new_callable=AsyncMock, return_value=0)
    @patch("handlers.debts.check_and_set_event_processed", return_value=True)
    @patch("handlers.debts.register_debt_payment", return_value=None)
    async def test_handles_register_error(self, mock_register, mock_event, mock_menu):
        from handlers.debts import pay_debt_get_amount
        update = make_update(text="200")
        context = make_context(user_data={
            "selected_debt": {"ID Deuda": "D001", "Saldo Pendiente": "1000"}
        })
        await pay_debt_get_amount(update, context)
        
        called_text = str(update.message.reply_text.call_args_list)
        assert "error" in called_text.lower()


# --- 3. Modification Flow ---

class TestModifyDebtGetAmount:
    """Tests for increasing debt."""

    @pytest.mark.asyncio
    @patch("handlers.debts.display_main_menu", new_callable=AsyncMock, return_value=0)
    @patch("handlers.debts.check_and_set_event_processed", return_value=True)
    @patch("handlers.debts.increase_debt_amount")
    async def test_valid_increase_calls_service(self, mock_increase, mock_event, mock_menu):
        from handlers.debts import modify_debt_get_amount
        mock_increase.return_value = {"Nombre": "Juan", "Saldo Pendiente": 8000.0}
        
        update = make_update(text="3000")
        context = make_context(user_data={
            "selected_debt": {"ID Deuda": "D001", "Saldo Pendiente": "5000"}
        })
        
        await modify_debt_get_amount(update, context)
        
        mock_increase.assert_called_once_with("D001", 3000.0)


# --- 4. Query Flow ---

class TestQueryDebts:
    """Tests for listing all debts."""

    @pytest.mark.asyncio
    @patch("handlers.debts.start_debt_menu", new_callable=AsyncMock)
    @patch("handlers.debts.get_active_debts")
    async def test_formats_list_correctly(self, mock_get, mock_menu):
        from handlers.debts import query_debts
        mock_get.return_value = [
            {"Nombre": "Alice", "Saldo Pendiente": 100},
            {"Nombre": "Bob", "Saldo Pendiente": 200}
        ]
        
        update = make_update(callback_data="debt_query")
        context = make_context()
        
        await query_debts(update, context)
        
        args, kwargs = update.callback_query.edit_message_text.call_args
        message = args[0]
        
        assert "- Alice: Debe $100.00" in message
        assert "- Bob: Debe $200.00" in message
        assert "Total adeudado: $300.00" in message
        mock_menu.assert_called_once()


class TestDebtMenu:
    """Tests for menu navigation."""

    @pytest.mark.asyncio
    async def test_start_menu_shows_options(self):
        from handlers.debts import start_debt_menu, DEBT_MENU
        from telegram import Bot
        
        # Mock update.message for start_debt_menu
        update = MagicMock()
        update.callback_query = None
        update.message = MagicMock()
        context = make_context()
        
        update.message.reply_text = AsyncMock()
        
        state = await start_debt_menu(update, context)
        
        assert state == DEBT_MENU
        update.message.reply_text.assert_called_once()
        args, _ = update.message.reply_text.call_args
        assert "Gestión de Deudas" in args[0]

    @pytest.mark.asyncio
    @patch("handlers.debts.start_pay_debt", new_callable=AsyncMock)
    async def test_menu_handler_routes(self, mock_pay):
        from handlers.debts import debt_menu_handler, CREATE_DEBT_GET_NAME
        # Test Create
        update = make_update(callback_data="debt_create")
        context = make_context()
        state = await debt_menu_handler(update, context)
        assert state == CREATE_DEBT_GET_NAME
        
        # Test Pay
        update_pay = make_update(callback_data="debt_pay")
        await debt_menu_handler(update_pay, context)
        mock_pay.assert_called_once()


class TestModifyDebtNavigation:
    """Tests for modify debt flow navigation."""

    @pytest.mark.asyncio
    @patch("handlers.debts.get_active_debts")
    async def test_start_modify_shows_list(self, mock_get):
        from handlers.debts import start_modify_debt, MODIFY_DEBT_CHOOSE_DEBT
        mock_get.return_value = [{"ID Deuda": "1", "Nombre": "A", "Saldo Pendiente": 100}]
        update = make_update(callback_data="debt_modify")
        context = make_context()
        
        state = await start_modify_debt(update, context)
        
        assert state == MODIFY_DEBT_CHOOSE_DEBT
        args, _ = update.callback_query.edit_message_text.call_args
        assert "Modificar Deuda" in args[0]

    @pytest.mark.asyncio
    async def test_choose_debt_for_modification(self):
        from handlers.debts import modify_debt_choose_debt, MODIFY_DEBT_GET_AMOUNT
        update = make_update(callback_data="mod_debt_id_10")
        # Pre-load context with debts as if they were fetched
        context = make_context(user_data={"modify_debts": [{"ID Deuda": "10", "Nombre": "B", "Saldo Pendiente": 50}]})
        
        state = await modify_debt_choose_debt(update, context)
        
        assert state == MODIFY_DEBT_GET_AMOUNT
        assert context.user_data['selected_debt']['ID Deuda'] == "10"
        args, _ = update.callback_query.edit_message_text.call_args
        assert "Deuda de B" in args[0]

