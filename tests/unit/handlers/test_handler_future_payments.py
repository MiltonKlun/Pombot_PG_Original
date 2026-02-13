import pytest
pytestmark = pytest.mark.unit

# tests/unit/handlers/test_handler_future_payments.py
"""Unit tests for handlers/future_payments.py — Risk R9: future payment tracking."""
from unittest.mock import patch, AsyncMock, MagicMock
from telegram.ext import ConversationHandler
from constants import (
    FUTURE_PAYMENTS_MENU, FUTURE_PAYMENTS_GET_ENTITY, 
    FUTURE_PAYMENTS_GET_PRODUCT, FUTURE_PAYMENTS_GET_QUANTITY,
    FUTURE_PAYMENTS_GET_INITIAL_AMOUNT, FUTURE_PAYMENTS_GET_COMMISSION,
    FUTURE_PAYMENTS_GET_DUE_DATE
)
from config import RESTART_PROMPT
from tests.helpers.telegram_factories import make_update, make_context

class TestFuturePaymentsMenu:
    """Tests for menu navigation."""

    @pytest.mark.asyncio
    async def test_start_menu_shows_options(self):
        from handlers.future_payments import start_fp_menu
        update = make_update(callback_data="wholesale_pagos_futuros")
        context = make_context()
        
        state = await start_fp_menu(update, context)
        
        assert state == FUTURE_PAYMENTS_MENU
        update.callback_query.edit_message_text.assert_called_once()
        args, _ = update.callback_query.edit_message_text.call_args
        assert "Módulo de Pagos Futuros" in args[0]

    @pytest.mark.asyncio
    @patch("handlers.future_payments.get_pending_future_payments", autospec=True)
    @patch("handlers.future_payments.display_main_menu", new_callable=AsyncMock, return_value=-1)
    async def test_consult_lists_payments(self, mock_menu, mock_get_pending):
        from handlers.future_payments import fp_menu_handler
        mock_get_pending.return_value = [
            {"Entidad": "Client A", "Producto": "Prod X", "Cantidad": 2, "Monto Final": 1000, "Fecha Cobro": "01/01/2024"}
        ]
        update = make_update(callback_data="fp_consult")
        context = make_context()
        
        await fp_menu_handler(update, context)
        
        # Should edit message with list
        calls = update.callback_query.edit_message_text.call_args_list
        last_call_text = calls[-1][0][0] # The list content
        assert "Client A" in last_call_text
        assert "$1,000.00" in last_call_text

    @pytest.mark.asyncio
    @patch("handlers.future_payments.get_pending_future_payments", autospec=True, return_value=[])
    @patch("handlers.future_payments.display_main_menu", new_callable=AsyncMock, return_value=-1)
    async def test_consult_handles_empty_list(self, mock_menu, mock_get_pending):
        from handlers.future_payments import fp_menu_handler
        update = make_update(callback_data="fp_consult")
        context = make_context()
        await fp_menu_handler(update, context)
        calls = update.callback_query.edit_message_text.call_args_list
        assert "No hay pagos futuros pendientes" in calls[-1][0][0]

    @pytest.mark.asyncio
    async def test_start_receive_flow(self):
        from handlers.future_payments import fp_menu_handler
        update = make_update(callback_data="fp_recibir")
        context = make_context()
        
        state = await fp_menu_handler(update, context)
        
        assert state == FUTURE_PAYMENTS_GET_ENTITY
        assert context.user_data['fp_flow'] == {}
        
class TestFuturePaymentsInputFlow:
    """Tests for the data entry wizard steps."""

    @pytest.mark.asyncio
    async def test_get_entity(self):
        from handlers.future_payments import fp_get_entity
        update = make_update(text="Cliente Test")
        context = make_context(user_data={"fp_flow": {}})
        
        state = await fp_get_entity(update, context)
        
        assert state == FUTURE_PAYMENTS_GET_PRODUCT
        assert context.user_data['fp_flow']['entity'] == "Cliente Test"

    @pytest.mark.asyncio
    async def test_get_product(self):
        from handlers.future_payments import fp_get_product
        update = make_update(text="Producto Test")
        context = make_context(user_data={"fp_flow": {}})
        
        state = await fp_get_product(update, context)
        
        assert state == FUTURE_PAYMENTS_GET_QUANTITY
        assert context.user_data['fp_flow']['product'] == "Producto Test"

    @pytest.mark.asyncio
    async def test_get_quantity_valid(self):
        from handlers.future_payments import fp_get_quantity
        update = make_update(text="10")
        context = make_context(user_data={"fp_flow": {}})
        
        state = await fp_get_quantity(update, context)
        
        assert state == FUTURE_PAYMENTS_GET_INITIAL_AMOUNT
        assert context.user_data['fp_flow']['quantity'] == 10

    @pytest.mark.asyncio
    async def test_get_quantity_invalid(self):
        from handlers.future_payments import fp_get_quantity
        update = make_update(text="abc")
        context = make_context(user_data={"fp_flow": {}})
        
        state = await fp_get_quantity(update, context)
        
        assert state == FUTURE_PAYMENTS_GET_QUANTITY
        update.message.reply_text.assert_called_with(f"Cantidad inválida. Ingresa un número entero positivo:{RESTART_PROMPT}")

    @pytest.mark.asyncio
    async def test_get_initial_amount_valid(self):
        from handlers.future_payments import fp_get_initial_amount
        update = make_update(text="5000")
        context = make_context(user_data={"fp_flow": {}})
        
        state = await fp_get_initial_amount(update, context)
        
        assert state == FUTURE_PAYMENTS_GET_COMMISSION
        assert context.user_data['fp_flow']['initial_amount'] == 5000.0

    @pytest.mark.asyncio
    async def test_get_commission_valid(self):
        from handlers.future_payments import fp_get_commission
        update = make_update(text="500")
        context = make_context(user_data={"fp_flow": {}})
        
        state = await fp_get_commission(update, context)
        
        assert state == FUTURE_PAYMENTS_GET_DUE_DATE
        assert context.user_data['fp_flow']['commission'] == 500.0

class TestFuturePaymentsFinalize:
    """Tests for the final step: saving the record."""

    @pytest.mark.asyncio
    @patch("handlers.future_payments.add_future_payment", autospec=True)
    @patch("handlers.future_payments.display_main_menu", new_callable=AsyncMock, return_value=-1)
    async def test_saves_successfully(self, mock_menu, mock_add):
        from handlers.future_payments import fp_get_due_date
        update = make_update(text="31/12/2024")
        context = make_context(user_data={
            "fp_flow": {
                "entity": "Client", "product": "Prod", "quantity": 1,
                "initial_amount": 1000.0, "commission": 100.0
            }
        })
        
        state = await fp_get_due_date(update, context)
        
        # Verify add_future_payment called with correct args
        mock_add.assert_called_once_with(
            entity="Client", product="Prod", quantity=1,
            initial_amount=1000.0, commission=100.0, due_date="31/12/2024"
        )
        
        # Verify confirmation message
        args, _ = update.message.reply_text.call_args
        assert "Pago Futuro Recibido registrado" in args[0]
        assert "Monto Final: $900.00" in args[0] # 1000 - 100
        
        assert state == -1

    @pytest.mark.asyncio
    @patch("handlers.future_payments.add_future_payment", autospec=True, side_effect=Exception("Sheet Error"))
    @patch("handlers.future_payments.display_main_menu", new_callable=AsyncMock, return_value=-1)
    async def test_handles_save_error(self, mock_menu, mock_add):
        from handlers.future_payments import fp_get_due_date
        update = make_update(text="31/12/2024")
        context = make_context(user_data={"fp_flow": {"entity": "X", "product": "Y", "quantity": 1, "initial_amount": 10, "commission": 0}})
        
        await fp_get_due_date(update, context)
        
        update.message.reply_text.assert_called_with("Hubo un error al registrar el Pago Futuro.")
