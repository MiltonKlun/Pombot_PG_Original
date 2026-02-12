import pytest
pytestmark = pytest.mark.unit

# tests/test_handler_checks.py
"""Unit tests for handlers/checks.py — Risk R7: tax calculation."""
from unittest.mock import patch, AsyncMock, MagicMock
from constants import CHECKS_MENU, CHECKS_GET_ENTITY, CHECKS_GET_INITIAL_AMOUNT, CHECKS_GET_COMMISSION, CHECKS_GET_DUE_DATE
from tests.helpers.telegram_factories import make_update, make_context


class TestChecksMenuHandler:
    """Tests for checks_menu_handler — consult or emit."""

    @pytest.mark.asyncio
    @patch("handlers.checks.display_main_menu", new_callable=AsyncMock, return_value=0)
    @patch("handlers.checks.get_pending_checks")
    async def test_consult_with_pending_checks(self, mock_get, mock_menu):
        from handlers.checks import checks_menu_handler
        mock_get.return_value = [
            {"Entidad": "BancoA", "Monto Final": "10000", "Fecha Cobro": "15/03/2026"}
        ]
        update = make_update(callback_data="check_consult")
        context = make_context()
        await checks_menu_handler(update, context)
        called_text = str(update.callback_query.edit_message_text.call_args_list)
        assert "BancoA" in called_text

    @pytest.mark.asyncio
    @patch("handlers.checks.display_main_menu", new_callable=AsyncMock, return_value=0)
    @patch("handlers.checks.get_pending_checks", return_value=[])
    async def test_consult_no_pending(self, mock_get, mock_menu):
        from handlers.checks import checks_menu_handler
        update = make_update(callback_data="check_consult")
        context = make_context()
        await checks_menu_handler(update, context)
        called_text = str(update.callback_query.edit_message_text.call_args_list)
        assert "no hay" in called_text.lower() or "No hay" in called_text

    @pytest.mark.asyncio
    async def test_emit_starts_check_flow(self):
        from handlers.checks import checks_menu_handler
        update = make_update(callback_data="check_emitir")
        context = make_context()
        result = await checks_menu_handler(update, context)
        assert result == CHECKS_GET_ENTITY
        assert "check_flow" in context.user_data


class TestChecksGetDueDate:
    """Tests for checks_get_due_date — final step, saves check with tax."""

    @pytest.mark.asyncio
    @patch("handlers.checks.display_main_menu", new_callable=AsyncMock, return_value=0)
    @patch("handlers.checks.add_check")
    async def test_saves_check_and_calculates_tax(self, mock_add, mock_menu):
        from handlers.checks import checks_get_due_date
        update = make_update(text="15/03/2026")
        context = make_context(user_data={
            "check_flow": {
                "entity": "BancoA",
                "initial_amount": 10000.0,
                "commission": 500.0
            }
        })
        await checks_get_due_date(update, context)
        mock_add.assert_called_once_with(
            entity="BancoA", initial_amount=10000.0,
            commission=500.0, due_date="15/03/2026"
        )
        # Verify tax calculation in confirmation message
        # expected tax = 10000 * 0.012 = 120
        # expected final = 10000 + 500 + 120 = 10620
        called_text = str(update.message.reply_text.call_args_list)
        assert "120" in called_text  # tax
        assert "10,620" in called_text or "10620" in called_text  # final amount

    @pytest.mark.asyncio
    @patch("handlers.checks.display_main_menu", new_callable=AsyncMock, return_value=0)
    @patch("handlers.checks.add_check", side_effect=Exception("Sheet error"))
    async def test_handles_service_error(self, mock_add, mock_menu):
        from handlers.checks import checks_get_due_date
        update = make_update(text="15/03/2026")
        context = make_context(user_data={
            "check_flow": {"entity": "X", "initial_amount": 100.0, "commission": 0.0}
        })
        await checks_get_due_date(update, context)
        error_calls = [c for c in update.message.reply_text.call_args_list if "error" in str(c).lower()]
        assert len(error_calls) > 0


class TestChecksGetEntity:
    """Tests for checks_get_entity — stores entity name."""

    @pytest.mark.asyncio
    async def test_stores_entity_and_advances(self):
        from handlers.checks import checks_get_entity
        update = make_update(text="BancoA")
        context = make_context(user_data={"check_flow": {}})
        result = await checks_get_entity(update, context)
        assert result == CHECKS_GET_INITIAL_AMOUNT
        assert context.user_data["check_flow"]["entity"] == "BancoA"

    @pytest.mark.asyncio
    async def test_ignores_missing_message(self):
        from handlers.checks import checks_get_entity
        update = make_update()  # no text, no callback
        update.message = None
        context = make_context(user_data={"check_flow": {}})
        result = await checks_get_entity(update, context)
        assert result == CHECKS_GET_ENTITY


class TestChecksGetInitialAmount:
    """Tests for checks_get_initial_amount — validates amount."""

    @pytest.mark.asyncio
    async def test_valid_amount_advances(self):
        from handlers.checks import checks_get_initial_amount
        update = make_update(text="10000")
        context = make_context(user_data={"check_flow": {}})
        result = await checks_get_initial_amount(update, context)
        assert result == CHECKS_GET_COMMISSION
        assert context.user_data["check_flow"]["initial_amount"] == 10000.0

    @pytest.mark.asyncio
    async def test_rejects_invalid(self):
        from handlers.checks import checks_get_initial_amount
        update = make_update(text="abc")
        context = make_context(user_data={"check_flow": {}})
        result = await checks_get_initial_amount(update, context)
        assert result == CHECKS_GET_INITIAL_AMOUNT
