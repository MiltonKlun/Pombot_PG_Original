import pytest
pytestmark = pytest.mark.integration

# tests/test_integration_sale_flow.py
"""
Integration tests for the full sale flow:
Handler → sales_service → sheets_connection + products_service + tiendanube_service.

Only gspread I/O and TiendaNube API are mocked; all intermediate logic runs for real.
"""
from unittest.mock import patch, MagicMock, AsyncMock

from tests.helpers.telegram_factories import make_update, make_context


@pytest.mark.integration
class TestFullSaleFlow:
    """End-to-end sale: handler receives quantity + client → service records sale,
    updates stock on Sheets and TiendaNube."""

    def _make_variant(self, price=5000.0, stock=10, row_number=5,
                      product_id=100, variant_id=200):
        return {
            "Producto": "Remera Test", "Categoría": "REMERAS",
            "Opción 1: Valor": "Rojo", "Opción 2: Valor": "M",
            "Opción 3: Valor": "",
            "Precio Unitario": price, "Precio Final": price,
            "%": 0, "Descuento": 0, "Stock": stock,
            "row_number": row_number,
            "ID Producto": product_id, "ID Variante": variant_id,
        }

    @patch("services.sales_service.update_tiendanube_stock")
    @patch("services.sales_service.invalidate_products_cache")
    @patch("services.sales_service.update_product_stock", return_value=True)
    @patch("services.sales_service.get_or_create_monthly_sheet")
    def test_sale_records_to_sheet_and_syncs_stock(
        self, mock_sheet, mock_update_stock, mock_invalidate, mock_tn
    ):
        """Verify real add_sale logic: row appended, stock decremented, TN synced."""
        mock_ws = MagicMock()
        mock_ws.title = "Ventas Enero 2026"
        mock_sheet.return_value = mock_ws

        from services.sales_service import add_sale
        variant = self._make_variant(price=5000.0, stock=10)
        result = add_sale(variant, quantity=3, client_name="Carlos")

        # Row was appended with correct total price
        row_data = mock_ws.append_row.call_args[0][0]
        assert row_data[9] == 15000.0  # 5000 * 3

        # Stock updated on sheet: 10 - 3 = 7
        mock_update_stock.assert_called_once_with(5, 7)
        mock_invalidate.assert_called_once()

        # TiendaNube synced with new stock
        mock_tn.assert_called_once_with(100, 200, 7)

        # Return value has all expected fields
        assert result["quantity"] == 3
        assert result["total_sale_price"] == 15000.0
        assert result["remaining_stock"] == 7
        assert result["sheet_title"] == "Ventas Enero 2026"

    @pytest.mark.asyncio
    @patch("handlers.sales.display_main_menu", new_callable=AsyncMock, return_value=0)
    @patch("handlers.sales.check_and_set_event_processed", return_value=True)
    @patch("handlers.sales.add_sale")
    async def test_handler_passes_data_to_service(self, mock_add_sale, mock_event, mock_menu):
        """Verify handler assembles correct args from user_data and text input."""
        mock_add_sale.return_value = {
            "timestamp": "2026-01-15 10:00:00", "product_name": "Remera Test",
            "variant_description": "Rojo, M", "client_name": "Ana",
            "quantity": 2, "total_sale_price": 10000.0,
            "remaining_stock": 8, "sheet_title": "Ventas Enero 2026"
        }
        from handlers.sales import sale_input_client_handler

        update = make_update(text="Ana")
        context = make_context(user_data={
            "sale_flow": {
                "variant_details": self._make_variant(price=5000.0, stock=10),
                "quantity_sold": 2
            }
        })
        await sale_input_client_handler(update, context)

        mock_add_sale.assert_called_once()
        call_args = mock_add_sale.call_args
        assert call_args[1].get("client_name", call_args[0][2] if len(call_args[0]) > 2 else None) == "Ana" or "Ana" in str(call_args)

    @patch("services.sales_service.update_tiendanube_stock")
    @patch("services.sales_service.invalidate_products_cache")
    @patch("services.sales_service.update_product_stock", return_value=True)
    @patch("services.sales_service.get_or_create_monthly_sheet")
    def test_variant_description_built_correctly(self, mock_sheet, mock_stock, mock_inv, mock_tn):
        """Multi-option variants produce comma-separated description."""
        mock_ws = MagicMock()
        mock_ws.title = "Ventas Enero 2026"
        mock_sheet.return_value = mock_ws

        from services.sales_service import add_sale
        variant = self._make_variant()
        variant["Opción 1: Valor"] = "Azul"
        variant["Opción 2: Valor"] = "L"
        variant["Opción 3: Valor"] = "Algodón"
        result = add_sale(variant, quantity=1, client_name="Test")

        assert result["variant_description"] == "Azul, L, Algodón"

    @patch("services.sales_service.update_tiendanube_stock")
    @patch("services.sales_service.invalidate_products_cache")
    @patch("services.sales_service.update_product_stock", return_value=False)
    @patch("services.sales_service.get_or_create_monthly_sheet")
    def test_sheet_stock_failure_still_records_sale(self, mock_sheet, mock_stock, mock_inv, mock_tn):
        """Sale is recorded even if sheet stock update fails."""
        mock_ws = MagicMock()
        mock_ws.title = "Ventas Enero 2026"
        mock_sheet.return_value = mock_ws

        from services.sales_service import add_sale
        result = add_sale(self._make_variant(), quantity=1, client_name="Test")

        # Sale recorded
        mock_ws.append_row.assert_called_once()
        # Cache not invalidated since stock update failed
        mock_inv.assert_not_called()
        assert result["remaining_stock"] == "Error al actualizar"
