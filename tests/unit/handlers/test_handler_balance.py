import pytest
pytestmark = pytest.mark.unit

# tests/test_handler_balance.py
"""Unit tests for handlers/balance.py — balance report generation."""
from unittest.mock import patch, AsyncMock, MagicMock
from constants import QUERY_BALANCE_CHOOSE_YEAR, QUERY_BALANCE_CHOOSE_MONTH
from tests.helpers.telegram_factories import make_update, make_context


class TestQueryBalanceStartHandler:
    """Tests for query_balance_start_handler — year selection."""

    @pytest.mark.asyncio
    @patch("handlers.balance.get_available_sheet_months_years")
    async def test_shows_year_buttons(self, mock_get):
        from handlers.balance import query_balance_start_handler
        mock_get.return_value = [(2026, 1), (2026, 2), (2025, 12)]
        update = make_update(callback_data="main_query_balance_start")
        context = make_context()
        result = await query_balance_start_handler(update, context)
        assert result == QUERY_BALANCE_CHOOSE_YEAR
        update.callback_query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio
    @patch("handlers.balance.display_main_menu", new_callable=AsyncMock, return_value=0)
    @patch("handlers.balance.get_available_sheet_months_years", return_value=[])
    async def test_no_data_returns_to_menu(self, mock_get, mock_menu):
        from handlers.balance import query_balance_start_handler
        update = make_update(callback_data="main_query_balance_start")
        context = make_context()
        await query_balance_start_handler(update, context)
        # Should notify no data and return to menu
        called_text = str(update.callback_query.edit_message_text.call_args_list)
        assert "no hay" in called_text.lower() or "No hay" in called_text


class TestQueryBalanceYearHandler:
    """Tests for query_balance_year_handler — month selection or current month shortcut."""

    @pytest.mark.asyncio
    @patch("handlers.balance.process_and_display_balance", new_callable=AsyncMock, return_value=0)
    async def test_current_month_shortcut(self, mock_process):
        from handlers.balance import query_balance_year_handler
        update = make_update(callback_data="balance_current_month")
        context = make_context()
        await query_balance_year_handler(update, context)
        mock_process.assert_called_once()

    @pytest.mark.asyncio
    @patch("handlers.balance.get_available_sheet_months_years")
    async def test_year_selection_shows_months(self, mock_get):
        from handlers.balance import query_balance_year_handler
        mock_get.return_value = [(2026, 1), (2026, 2)]
        update = make_update(callback_data="balance_year_2026")
        context = make_context()
        result = await query_balance_year_handler(update, context)
        assert result == QUERY_BALANCE_CHOOSE_MONTH
        assert context.user_data["selected_balance_year"] == 2026


class TestProcessAndDisplayBalance:
    """Tests for process_and_display_balance — PDF generation + send."""

    @pytest.mark.asyncio
    @patch("handlers.balance.display_main_menu", new_callable=AsyncMock, return_value=0)
    @patch("builtins.open", MagicMock())
    @patch("handlers.balance.generate_balance_pdf", return_value="/tmp/Balance_Enero_2026.pdf")
    @patch("handlers.balance.get_net_balance_for_month")
    async def test_generates_and_sends_pdf(self, mock_balance, mock_pdf, mock_menu):
        from handlers.balance import process_and_display_balance
        mock_balance.return_value = {"month_name": "Enero", "year": 2026, "saldo_neto": 50000.0}
        update = make_update(callback_data="balance_month_2026_1")
        context = make_context()
        await process_and_display_balance(update, context, 2026, 1)
        mock_balance.assert_called_once_with(2026, 1)
        mock_pdf.assert_called_once()

    @pytest.mark.asyncio
    @patch("handlers.balance.display_main_menu", new_callable=AsyncMock, return_value=0)
    @patch("handlers.balance.generate_balance_pdf", return_value=None)
    @patch("handlers.balance.get_net_balance_for_month", return_value={})
    async def test_shows_error_when_pdf_fails(self, mock_balance, mock_pdf, mock_menu):
        from handlers.balance import process_and_display_balance
        update = make_update(callback_data="balance_month_2026_1")
        context = make_context()
        await process_and_display_balance(update, context, 2026, 1)
        # Should show error message
        called_text = str(update.callback_query.edit_message_text.call_args_list)
        assert "error" in called_text.lower()

    @pytest.mark.asyncio
    @patch("handlers.balance.display_main_menu", new_callable=AsyncMock, return_value=0)
    @patch("handlers.balance.get_net_balance_for_month", side_effect=Exception("DB error"))
    async def test_handles_exception_gracefully(self, mock_balance, mock_menu):
        from handlers.balance import process_and_display_balance
        update = make_update(callback_data="balance_month_2026_1")
        context = make_context()
        await process_and_display_balance(update, context, 2026, 1)
        called_text = str(update.callback_query.edit_message_text.call_args_list)
        assert "error" in called_text.lower()
