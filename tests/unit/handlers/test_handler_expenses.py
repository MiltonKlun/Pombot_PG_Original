import pytest
pytestmark = pytest.mark.unit

# tests/test_handler_expenses.py
"""Unit tests for handlers/expenses.py."""
from unittest.mock import patch, AsyncMock, MagicMock
from constants import (
    ADD_EXPENSE_CANJE_GET_ENTITY, ADD_EXPENSE_PROVEEDORES_GET_NAME,
    ADD_EXPENSE_CHOOSE_SUBCATEGORY, ADD_EXPENSE_INPUT_DESCRIPTION,
    ADD_EXPENSE_INPUT_AMOUNT
)
from tests.helpers.telegram_factories import make_update, make_context


class TestExpenseChooseCategoryHandler:
    """Tests for expense_choose_category_handler — routes by category."""

    @pytest.mark.asyncio
    @patch("handlers.expenses.start_checks_menu", new_callable=AsyncMock, return_value=99)
    async def test_cheques_routes_to_checks_menu(self, mock_checks):
        from handlers.expenses import expense_choose_category_handler
        update = make_update(callback_data="exp_cat_CHEQUES")
        context = make_context()
        result = await expense_choose_category_handler(update, context)
        mock_checks.assert_called_once()

    @pytest.mark.asyncio
    async def test_canjes_routes_to_canje_flow(self):
        from handlers.expenses import expense_choose_category_handler
        update = make_update(callback_data="exp_cat_CANJES")
        context = make_context()
        result = await expense_choose_category_handler(update, context)
        assert result == ADD_EXPENSE_CANJE_GET_ENTITY
        assert context.user_data['expense_flow']['category'] == "CANJES"

    @pytest.mark.asyncio
    async def test_proveedores_routes_to_provider_flow(self):
        from handlers.expenses import expense_choose_category_handler
        update = make_update(callback_data="exp_cat_PROVEEDORES")
        context = make_context()
        result = await expense_choose_category_handler(update, context)
        assert result == ADD_EXPENSE_PROVEEDORES_GET_NAME
        assert context.user_data['expense_flow']['category'] == "PROVEEDORES"

    @pytest.mark.asyncio
    @patch("handlers.expenses.EXPENSE_SUBCATEGORIES", {"SERVICIOS": ["Luz", "Gas"]})
    async def test_category_with_subcategories_shows_selection(self):
        from handlers.expenses import expense_choose_category_handler
        update = make_update(callback_data="exp_cat_SERVICIOS")
        context = make_context()
        result = await expense_choose_category_handler(update, context)
        assert result == ADD_EXPENSE_CHOOSE_SUBCATEGORY

    @pytest.mark.asyncio
    @patch("handlers.expenses.EXPENSE_SUBCATEGORIES", {})
    async def test_category_without_subcategories_goes_to_description(self):
        from handlers.expenses import expense_choose_category_handler
        update = make_update(callback_data="exp_cat_OTROS")
        context = make_context()
        result = await expense_choose_category_handler(update, context)
        assert result == ADD_EXPENSE_INPUT_DESCRIPTION


class TestExpenseInputAmountHandler:
    """Tests for expense_input_amount_handler — validates and records expense."""

    @pytest.mark.asyncio
    @patch("handlers.expenses.display_main_menu", new_callable=AsyncMock, return_value=0)
    @patch("handlers.expenses.check_and_set_event_processed", return_value=True)
    @patch("handlers.expenses.add_expense")
    async def test_valid_amount_calls_add_expense(self, mock_add, mock_event, mock_menu):
        from handlers.expenses import expense_input_amount_handler
        mock_add.return_value = {
            "category": "SERVICIOS", "subcategory": "Luz",
            "description": "Factura marzo", "details": "",
            "amount": 5000.0, "sheet_title": "Gastos Enero"
        }
        update = make_update(text="5000")
        context = make_context(user_data={
            "expense_flow": {"category": "SERVICIOS", "subcategory": "Luz", "description": "Factura marzo"}
        })
        await expense_input_amount_handler(update, context)
        mock_add.assert_called_once_with(
            category="SERVICIOS", subcategory="Luz",
            description="Factura marzo", details="", amount=5000.0
        )

    @pytest.mark.asyncio
    async def test_rejects_invalid_amount(self):
        from handlers.expenses import expense_input_amount_handler
        update = make_update(text="abc")
        context = make_context(user_data={"expense_flow": {"category": "X"}})
        result = await expense_input_amount_handler(update, context)
        assert result == ADD_EXPENSE_INPUT_AMOUNT

    @pytest.mark.asyncio
    async def test_rejects_zero_amount(self):
        from handlers.expenses import expense_input_amount_handler
        update = make_update(text="0")
        context = make_context(user_data={"expense_flow": {"category": "X"}})
        result = await expense_input_amount_handler(update, context)
        assert result == ADD_EXPENSE_INPUT_AMOUNT

    @pytest.mark.asyncio
    @patch("handlers.expenses.display_main_menu", new_callable=AsyncMock, return_value=0)
    @patch("handlers.expenses.check_and_set_event_processed", return_value=True)
    @patch("handlers.expenses.add_expense")
    async def test_canjes_passes_correct_data(self, mock_add, mock_event, mock_menu):
        from handlers.expenses import expense_input_amount_handler
        mock_add.return_value = {
            "category": "CANJES", "subcategory": "Gorra",
            "description": "Entidad A", "details": "Cantidad: 2",
            "amount": 3000.0, "sheet_title": "Gastos Enero"
        }
        update = make_update(text="3000")
        context = make_context(user_data={
            "expense_flow": {"category": "CANJES", "entity": "Entidad A", "item": "Gorra", "quantity": 2}
        })
        await expense_input_amount_handler(update, context)
        mock_add.assert_called_once_with(
            category="CANJES", subcategory="Gorra",
            description="Entidad A", details="Cantidad: 2", amount=3000.0
        )

    @pytest.mark.asyncio
    @patch("handlers.expenses.display_main_menu", new_callable=AsyncMock, return_value=0)
    @patch("handlers.expenses.check_and_set_event_processed", return_value=True)
    @patch("handlers.expenses.add_expense", side_effect=Exception("Sheet error"))
    async def test_handles_service_error(self, mock_add, mock_event, mock_menu):
        from handlers.expenses import expense_input_amount_handler
        update = make_update(text="5000")
        context = make_context(user_data={
            "expense_flow": {"category": "X", "subcategory": "", "description": "Test"}
        })
        await expense_input_amount_handler(update, context)
        error_calls = [c for c in update.message.reply_text.call_args_list if "error" in str(c).lower()]
        assert len(error_calls) > 0


class TestExpenseCanjes:
    """Tests for Canjes flow."""

    @pytest.mark.asyncio
    async def test_canje_flow_collection(self):
        from handlers.expenses import expense_canje_get_entity, ADD_EXPENSE_CANJE_GET_ITEM
        update = make_update(text="Entidad X")
        context = make_context(user_data={"expense_flow": {}})
        
        state = await expense_canje_get_entity(update, context)
        
        assert state == ADD_EXPENSE_CANJE_GET_ITEM
        assert context.user_data['expense_flow']['entity'] == "Entidad X"

    @pytest.mark.asyncio
    async def test_canje_get_item(self):
        from handlers.expenses import expense_canje_get_item, ADD_EXPENSE_CANJE_GET_QUANTITY
        update = make_update(text="Item Y")
        context = make_context(user_data={"expense_flow": {}})
        
        state = await expense_canje_get_item(update, context)
        
        assert state == ADD_EXPENSE_CANJE_GET_QUANTITY
        assert context.user_data['expense_flow']['item'] == "Item Y"

    @pytest.mark.asyncio
    async def test_canje_get_quantity(self):
        from handlers.expenses import expense_canje_get_quantity, ADD_EXPENSE_INPUT_AMOUNT
        update = make_update(text="10")
        context = make_context(user_data={"expense_flow": {}})
        
        state = await expense_canje_get_quantity(update, context)
        
        assert state == ADD_EXPENSE_INPUT_AMOUNT
        assert context.user_data['expense_flow']['quantity'] == 10


class TestExpenseProveedores:
    """Tests for Proveedores flow."""

    @pytest.mark.asyncio
    async def test_proveedor_flow_collection(self):
        from handlers.expenses import expense_proveedores_get_name, ADD_EXPENSE_PROVEEDORES_GET_ITEM
        update = make_update(text="Prov Z")
        context = make_context(user_data={"expense_flow": {}})
        
        state = await expense_proveedores_get_name(update, context)
        
        assert state == ADD_EXPENSE_PROVEEDORES_GET_ITEM
        assert context.user_data['expense_flow']['provider_name'] == "Prov Z"

    @pytest.mark.asyncio
    async def test_proveedor_get_item(self):
        from handlers.expenses import expense_proveedores_get_item, ADD_EXPENSE_PROVEEDORES_GET_QUANTITY
        update = make_update(text="Servicio X")
        context = make_context(user_data={"expense_flow": {}})
        
        state = await expense_proveedores_get_item(update, context)
        
        assert state == ADD_EXPENSE_PROVEEDORES_GET_QUANTITY
        assert context.user_data['expense_flow']['item'] == "Servicio X"

    @pytest.mark.asyncio
    async def test_proveedor_get_quantity(self):
        from handlers.expenses import expense_proveedores_get_quantity, ADD_EXPENSE_INPUT_AMOUNT
        update = make_update(text="5")
        context = make_context(user_data={"expense_flow": {}})
        
        state = await expense_proveedores_get_quantity(update, context)
        
        assert state == ADD_EXPENSE_INPUT_AMOUNT
        assert context.user_data['expense_flow']['quantity'] == 5

class TestExpenseDescription:
    """Tests for Description and Subcategory handler."""

    @pytest.mark.asyncio
    async def test_expense_input_description_handler(self):
        from handlers.expenses import expense_input_description_handler, ADD_EXPENSE_INPUT_AMOUNT
        update = make_update(text="Gasto vario")
        context = make_context(user_data={"expense_flow": {}})
        
        state = await expense_input_description_handler(update, context)
        
        assert state == ADD_EXPENSE_INPUT_AMOUNT
        assert context.user_data['expense_flow']['description'] == "Gasto vario"

    @pytest.mark.asyncio
    @patch("handlers.expenses.start_add_expense", new_callable=AsyncMock)
    async def test_expense_choose_subcategory_handler_back(self, mock_start):
        from handlers.expenses import expense_choose_subcategory_handler
        update = make_update(callback_data="back_to_exp_cat_sel")
        context = make_context()
        
        await expense_choose_subcategory_handler(update, context)
        
        mock_start.assert_called_once()

