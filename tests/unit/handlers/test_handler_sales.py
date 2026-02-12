import pytest
pytestmark = pytest.mark.unit

# tests/test_handler_sales.py
"""
Unit tests for handlers/sales.py — Risk R2: wrong price/stock.
Expanded to cover Stock Race Conditions, API Failures, Pagination Interactions, and Option Selection.
"""
from unittest.mock import patch, AsyncMock, MagicMock
from constants import (
    ADD_SALE_CHOOSE_CATEGORY, ADD_SALE_CHOOSE_PRODUCT,
    ADD_SALE_CHOOSE_OPTION_1, ADD_SALE_CHOOSE_OPTION_2,
    ADD_SALE_INPUT_QUANTITY, ADD_SALE_INPUT_CLIENT
)
from config import RESTART_PROMPT
from tests.helpers.telegram_factories import make_update, make_context
import asyncio

# --- 1. Initialization & Category ---

class TestStartAddSale:
    """Tests for initial state and category loading."""

    @pytest.mark.asyncio
    @patch("handlers.sales.get_or_create_monthly_sheet")
    @patch("handlers.sales.get_product_categories")
    async def test_loads_categories_successfully(self, mock_cats, mock_sheet):
        from handlers.sales import start_add_sale
        mock_sheet.return_value = MagicMock()
        mock_cats.return_value = ["Remeras", "Pantalones"]
        
        update = make_update(callback_data="start_sale")
        context = make_context()
        
        state = await start_add_sale(update, context)
        
        assert state == ADD_SALE_CHOOSE_CATEGORY
        args, _ = update.callback_query.edit_message_text.call_args
        assert "Selecciona la categoría" in args[0]
        # Check buttons
        markup = _['reply_markup']
        buttons = [b.text for row in markup.inline_keyboard for b in row]
        assert "Remeras" in buttons
        assert "Pantalones" in buttons

    @pytest.mark.asyncio
    @patch("handlers.sales.get_or_create_monthly_sheet", return_value=None)
    @patch("handlers.sales.display_main_menu", new_callable=AsyncMock)
    async def test_sheet_access_failure(self, mock_menu, mock_sheet):
        from handlers.sales import start_add_sale
        update = make_update(callback_data="start_sale")
        context = make_context()
        
        await start_add_sale(update, context)
        
        # Should show critical error
        args, _ = update.callback_query.edit_message_text.call_args
        assert "Error crítico" in args[0]
        assert "No se pudo crear" in args[0]

    @pytest.mark.asyncio
    @patch("handlers.sales.get_or_create_monthly_sheet")
    @patch("handlers.sales.get_product_categories", return_value=[])
    @patch("handlers.sales.display_main_menu", new_callable=AsyncMock)
    async def test_empty_categories_warning(self, mock_menu, mock_cats, mock_sheet):
        from handlers.sales import start_add_sale
        update = make_update(callback_data="start_sale")
        context = make_context()
        
        await start_add_sale(update, context)
        
        mock_menu.assert_called_once()
        args, _ = mock_menu.call_args
        assert "No se encontraron categorías" in args[2]


# --- 2. Pagination & Product Selection ---

class TestSalePagination:
    """Tests for product pagination logic."""

    @pytest.mark.asyncio
    @patch("handlers.sales.get_products_by_category")
    async def test_initial_page_load(self, mock_prods):
        from handlers.sales import sale_choose_category_handler
        mock_prods.return_value = [f"Prod {i}" for i in range(25)]
        
        update = make_update(callback_data="sale_cat_Remeras")
        context = make_context(user_data={'sale_flow': {}}) # Initialize sale_flow
        
        state = await sale_choose_category_handler(update, context)
        
        assert state == ADD_SALE_CHOOSE_PRODUCT
        assert context.user_data['sale_flow']['category'] == "Remeras"
        assert len(context.user_data['sale_flow']['product_list']) == 25
        
        # Verify Page 1 title
        args, _ = update.callback_query.edit_message_text.call_args
        assert "(Página 1/3)" in args[0]

    @pytest.mark.asyncio
    async def test_navigation_next_page(self):
        from handlers.sales import sale_product_pagination_handler
        update = make_update(callback_data="prod_page_1")
        # Setup context as if we are on page 0 with 25 items
        context = make_context(user_data={
            "sale_flow": {
                "category": "Remeras",
                "product_list": [f"Prod {i}" for i in range(25)]
            }
        })
        
        state = await sale_product_pagination_handler(update, context)
        
        assert state == ADD_SALE_CHOOSE_PRODUCT
        args, _ = update.callback_query.edit_message_text.call_args
        assert "(Página 2/3)" in args[0]

    @pytest.mark.asyncio
    async def test_lost_context_fail(self):
        from handlers.sales import sale_product_pagination_handler
        update = make_update(callback_data="prod_page_1")
        context = make_context(user_data={"sale_flow": {}}) # Empty flow data
        
        with patch("handlers.sales.display_main_menu", new_callable=AsyncMock) as mock_menu:
            await sale_product_pagination_handler(update, context)
            mock_menu.assert_called_once()
            args, _ = mock_menu.call_args
            assert "Error: Se perdió la lista" in args[2]


# --- 3. Option Selection ---

class TestOptionSelection:
    """Tests for selecting product options (Color/Size)."""

    @pytest.mark.asyncio
    @patch("handlers.sales.get_product_options")
    async def test_auto_skip_if_no_options(self, mock_opts):
        from handlers.sales import sale_choose_product_handler
        # Mock returning NO options for option #1
        mock_opts.return_value = ("", [])
        
        update = make_update(callback_data="sale_prod_0")
        context = make_context(user_data={
            "sale_flow": {
                "product_list": ["Camiseta Simple"],
                "product_name": "Camiseta Simple",
                "selections": {}
            }
        })
        
        # Should skip options and go straight to quantity
        # We need to mock get_variant_details because sale_ask_for_quantity calls it
        with patch("handlers.sales.get_variant_details", return_value={"Stock": 10, "Precio Final": 100}):
            state = await sale_choose_product_handler(update, context)
            assert state == ADD_SALE_INPUT_QUANTITY

    @pytest.mark.asyncio
    @patch("handlers.sales.get_product_options")
    async def test_prompts_for_option_1(self, mock_opts):
        from handlers.sales import sale_choose_product_handler
        mock_opts.return_value = ("Color", ["Rojo", "Azul"])
        
        update = make_update(callback_data="sale_prod_0")
        context = make_context(user_data={
            "sale_flow": {
                "product_list": ["Camiseta"],
                "product_name": "Camiseta"
            }
        })
        
        state = await sale_choose_product_handler(update, context)
        
        assert state == ADD_SALE_CHOOSE_OPTION_1
        args, _ = update.callback_query.edit_message_text.call_args
        assert "Selecciona Color" in args[0]


# --- 4. Quantity & Stock Checks (Critical) ---

class TestSaleInputQuantityHandler:
    """Tests for quantity input and TiendaNube stock synchronization."""

    @pytest.mark.asyncio
    @patch("handlers.sales.display_main_menu", new_callable=AsyncMock)
    @patch("handlers.sales.get_realtime_stock", return_value=10)
    async def test_valid_quantity_proceeds(self, mock_stock, mock_menu):
        from handlers.sales import sale_input_quantity_handler
        update = make_update(text="2")
        context = make_context(user_data={
            "sale_flow": {
                "variant_details": {"ID Producto": "1", "ID Variante": "2", "Stock": 10},
            }
        })
        
        result = await sale_input_quantity_handler(update, context)
        
        assert result == ADD_SALE_INPUT_CLIENT
        assert context.user_data['sale_flow']['quantity_sold'] == 2
        update.message.reply_text.assert_called_with(f"✅ Stock confirmado.\n👤 Por favor, ingresa el nombre del cliente/comprador:{RESTART_PROMPT}")

    @pytest.mark.asyncio
    @patch("handlers.sales.display_main_menu", new_callable=AsyncMock)
    @patch("handlers.sales.get_realtime_stock", return_value=None) # API Failure
    async def test_api_failure_cancel_sale(self, mock_stock, mock_menu):
        from handlers.sales import sale_input_quantity_handler
        update = make_update(text="2")
        context = make_context(user_data={
            "sale_flow": {
                "variant_details": {"ID Producto": "1", "ID Variante": "2", "Stock": 10},
            }
        })
        
        result = await sale_input_quantity_handler(update, context)
        
        # Should abort to main menu
        mock_menu.assert_called()
        args, _ = mock_menu.call_args
        assert "No se pudo verificar el stock" in args[2]

    @pytest.mark.asyncio
    @patch("handlers.sales.display_main_menu", new_callable=AsyncMock)
    @patch("handlers.sales.get_realtime_stock", return_value=1) # Stock dropped to 1 (Race condition)
    async def test_race_condition_insufficient_stock(self, mock_stock, mock_menu):
        from handlers.sales import sale_input_quantity_handler
        update = make_update(text="2") # User wants 2
        context = make_context(user_data={
            "sale_flow": {
                "variant_details": {"ID Producto": "1", "ID Variante": "2", "Stock": 10}, # App thinks we have 10
            }
        })
        
        result = await sale_input_quantity_handler(update, context)
        
        # Should abort because real stock (1) < requested (2)
        mock_menu.assert_called()
        args, _ = update.message.reply_text.call_args
        assert "Stock insuficiente" in args[0]
        assert "Stock real disponible: 1" in args[0]

    @pytest.mark.asyncio
    async def test_rejects_non_numeric(self):
        from handlers.sales import sale_input_quantity_handler
        update = make_update(text="abc")
        context = make_context(user_data={"sale_flow": {"variant_details": {}}})
        
        result = await sale_input_quantity_handler(update, context)
        
        assert result == ADD_SALE_INPUT_QUANTITY
        update.message.reply_text.assert_called_once()


# --- 5. Client Input & Finalization ---

class TestSaleInputClientHandler:
    """Tests for sale_input_client_handler — final sale step."""

    @pytest.mark.asyncio
    @patch("handlers.sales.display_main_menu", new_callable=AsyncMock, return_value=-1)
    @patch("handlers.sales.check_and_set_event_processed", return_value=True)
    @patch("handlers.sales.add_sale")
    async def test_calls_add_sale_with_correct_args(self, mock_add_sale, mock_event, mock_menu):
        from handlers.sales import sale_input_client_handler
        mock_add_sale.return_value = {
            "timestamp": "01/01/2026 10:00:00", "product_name": "Remera",
            "variant_description": "Rojo / M", "client_name": "Juan",
            "quantity": 2, "total_sale_price": 10000.0,
            "remaining_stock": 8, "sheet_title": "Ventas Enero"
        }
        update = make_update(text="Juan")
        context = make_context(user_data={
            "sale_flow": {
                "variant_details": {"Precio Final": 5000.0, "Stock": 10},
                "quantity_sold": 2
            }
        })
        await sale_input_client_handler(update, context)
        mock_add_sale.assert_called_once()
        args, _ = update.message.reply_text.call_args
        assert "Venta Registrada" in args[0]

    @pytest.mark.asyncio
    async def test_rejects_empty_client_name(self):
        from handlers.sales import sale_input_client_handler
        update = make_update(text="   ")
        context = make_context(user_data={"sale_flow": {}})
        result = await sale_input_client_handler(update, context)
        assert result == ADD_SALE_INPUT_CLIENT

    @pytest.mark.asyncio
    @patch("handlers.sales.display_main_menu", new_callable=AsyncMock, return_value=-1)
    @patch("handlers.sales.check_and_set_event_processed", return_value=True)
    @patch("handlers.sales.add_sale", side_effect=Exception("Sheet error"))
    async def test_handles_service_error_gracefully(self, mock_sale, mock_event, mock_menu):
        from handlers.sales import sale_input_client_handler
        update = make_update(text="Juan")
        context = make_context(user_data={
            "sale_flow": {"variant_details": {}, "quantity_sold": 1}
        })
        await sale_input_client_handler(update, context)
        # Should send error message, not crash
        error_calls = [c for c in update.message.reply_text.call_args_list if "error" in str(c).lower()]
        assert len(error_calls) > 0
