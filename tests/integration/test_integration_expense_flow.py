import pytest
pytestmark = pytest.mark.integration

# tests/test_integration_expense_flow.py
"""
Integration tests for expense flows:
Standard / CANJES / PROVEEDORES — handler → expenses_service → sheets_connection.
"""
from unittest.mock import patch, MagicMock, AsyncMock

from tests.helpers.telegram_factories import make_update, make_context
from constants import (
    ADD_EXPENSE_INPUT_AMOUNT, ADD_EXPENSE_CANJE_GET_ENTITY,
    ADD_EXPENSE_PROVEEDORES_GET_NAME
)


class TestStandardExpenseFlow:
    """Standard category → subcategory → description → amount → sheet write."""

    @patch("handlers.expenses.display_main_menu", new_callable=AsyncMock, return_value=0)
    @patch("handlers.expenses.check_and_set_event_processed", return_value=True)
    @patch("services.expenses_service.get_or_create_monthly_sheet")
    def test_standard_expense_writes_correct_row(self, mock_sheet, mock_event, mock_menu):
        """Verify add_expense writes the expected 6-column row."""
        mock_ws = MagicMock()
        mock_ws.title = "Gastos Enero 2026"
        mock_sheet.return_value = mock_ws

        from services.expenses_service import add_expense
        result = add_expense(
            category="INSUMOS", subcategory="ESTAMPAS",
            description="Tela importada", details="", amount=5000.0
        )

        mock_ws.append_row.assert_called_once()
        row = mock_ws.append_row.call_args[0][0]
        assert row[1] == "INSUMOS"
        assert row[2] == "ESTAMPAS"
        assert row[3] == "Tela importada"
        assert row[5] == 5000.0
        assert result["sheet_title"] == "Gastos Enero 2026"

    @patch("services.expenses_service.get_or_create_monthly_sheet")
    def test_raises_on_no_sheet(self, mock_sheet):
        """ConnectionError when sheet is unavailable."""
        mock_sheet.return_value = None

        from services.expenses_service import add_expense
        with pytest.raises(ConnectionError):
            add_expense("X", "", "", "", 100.0)


class TestCanjesExpenseFlow:
    """CANJES flow: handler routes → collects entity/item/quantity → add_expense."""

    @pytest.mark.asyncio
    async def test_canjes_routing_sets_category(self):
        from handlers.expenses import expense_choose_category_handler
        update = make_update(callback_data="exp_cat_CANJES")
        context = make_context()
        result = await expense_choose_category_handler(update, context)

        assert result == ADD_EXPENSE_CANJE_GET_ENTITY
        assert context.user_data["expense_flow"]["category"] == "CANJES"

    @patch("services.expenses_service.get_or_create_monthly_sheet")
    def test_canjes_data_mapping(self, mock_sheet):
        """CANJES: subcategory=item, description=entity, details=Cantidad: N."""
        mock_ws = MagicMock()
        mock_ws.title = "Gastos Enero 2026"
        mock_sheet.return_value = mock_ws

        from services.expenses_service import add_expense
        result = add_expense(
            category="CANJES", subcategory="Gorra",
            description="Influencer X", details="Cantidad: 5",
            amount=3000.0
        )

        row = mock_ws.append_row.call_args[0][0]
        assert row[1] == "CANJES"
        assert row[2] == "Gorra"          # subcategory = item
        assert row[3] == "Influencer X"   # description = entity
        assert row[4] == "Cantidad: 5"    # details
        assert row[5] == 3000.0


class TestProveedoresExpenseFlow:
    """PROVEEDORES flow: handler routes → collects provider/item/quantity → add_expense."""

    @pytest.mark.asyncio
    async def test_proveedores_routing(self):
        from handlers.expenses import expense_choose_category_handler
        update = make_update(callback_data="exp_cat_PROVEEDORES")
        context = make_context()
        result = await expense_choose_category_handler(update, context)

        assert result == ADD_EXPENSE_PROVEEDORES_GET_NAME
        assert context.user_data["expense_flow"]["category"] == "PROVEEDORES"

    @patch("services.expenses_service.get_or_create_monthly_sheet")
    def test_proveedores_data_mapping(self, mock_sheet):
        """PROVEEDORES: description=provider_name, details=Artículo: X (Cantidad: N)."""
        mock_ws = MagicMock()
        mock_ws.title = "Gastos Febrero 2026"
        mock_sheet.return_value = mock_ws

        from services.expenses_service import add_expense
        result = add_expense(
            category="PROVEEDORES", subcategory="",
            description="Proveedor ABC",
            details="Artículo: Tela (Cantidad: 10)",
            amount=50000.0
        )

        row = mock_ws.append_row.call_args[0][0]
        assert row[1] == "PROVEEDORES"
        assert row[3] == "Proveedor ABC"
        assert "Tela" in row[4]
        assert row[5] == 50000.0


class TestExpenseAmountValidation:
    """Handler-level amount validation before service call."""

    @pytest.mark.asyncio
    async def test_handler_rejects_non_numeric_amount(self):
        from handlers.expenses import expense_input_amount_handler
        update = make_update(text="abc")
        context = make_context(user_data={"expense_flow": {"category": "INSUMOS"}})
        result = await expense_input_amount_handler(update, context)
        assert result == ADD_EXPENSE_INPUT_AMOUNT

    @pytest.mark.asyncio
    async def test_handler_rejects_negative_amount(self):
        from handlers.expenses import expense_input_amount_handler
        update = make_update(text="-500")
        context = make_context(user_data={"expense_flow": {"category": "INSUMOS"}})
        result = await expense_input_amount_handler(update, context)
        assert result == ADD_EXPENSE_INPUT_AMOUNT

    @pytest.mark.asyncio
    @patch("handlers.expenses.display_main_menu", new_callable=AsyncMock, return_value=0)
    @patch("handlers.expenses.check_and_set_event_processed", return_value=True)
    @patch("handlers.expenses.add_expense")
    async def test_handler_passes_valid_amount_to_service(self, mock_add, mock_event, mock_menu):
        from handlers.expenses import expense_input_amount_handler
        mock_add.return_value = {
            "category": "INSUMOS", "subcategory": "ESTAMPAS",
            "description": "Prueba", "details": "",
            "amount": 7500.0, "sheet_title": "Gastos Enero 2026"
        }
        update = make_update(text="7500")
        context = make_context(user_data={
            "expense_flow": {"category": "INSUMOS", "subcategory": "ESTAMPAS", "description": "Prueba"}
        })
        await expense_input_amount_handler(update, context)
        mock_add.assert_called_once()
        assert mock_add.call_args[1]["amount"] == 7500.0
