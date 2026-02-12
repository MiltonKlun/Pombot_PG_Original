import pytest
pytestmark = pytest.mark.unit

# tests/test_sales_service.py
"""Unit tests for services/sales_service.py — Risk R2: sale price/stock correctness."""
from unittest.mock import patch, MagicMock, call


@pytest.mark.unit
class TestAddTransactionGeneric:
    """Tests for the generic row-append helper."""

    @patch("services.sales_service.get_or_create_monthly_sheet")
    def test_happy_path_appends_row(self, mock_get_sheet):
        mock_ws = MagicMock()
        mock_ws.title = "Ventas Enero 2026"
        mock_get_sheet.return_value = mock_ws

        from services.sales_service import add_transaction_generic
        result = add_transaction_generic("Ventas", ["H1", "H2"], ["val1", "val2"])

        mock_ws.append_row.assert_called_once_with(["val1", "val2"], value_input_option='USER_ENTERED')
        assert result["sheet_title"] == "Ventas Enero 2026"
        assert result["data"] == ["val1", "val2"]

    @patch("services.sales_service.get_or_create_monthly_sheet")
    def test_raises_on_no_connection(self, mock_get_sheet):
        mock_get_sheet.return_value = None

        from services.sales_service import add_transaction_generic
        with pytest.raises(ConnectionError, match="no disponible"):
            add_transaction_generic("Ventas", ["H1"], ["val1"])

    @patch("services.sales_service.get_or_create_monthly_sheet")
    def test_propagates_gspread_error(self, mock_get_sheet):
        mock_ws = MagicMock()
        mock_ws.append_row.side_effect = Exception("API quota exceeded")
        mock_get_sheet.return_value = mock_ws

        from services.sales_service import add_transaction_generic
        with pytest.raises(Exception, match="API quota exceeded"):
            add_transaction_generic("Ventas", ["H1"], ["val1"])


@pytest.mark.unit
class TestAddSale:
    """Tests for add_sale — the full sale recording chain."""

    def _make_variant(self, price=5000.0, stock=10, row_number=5,
                      product_id=100, variant_id=200):
        return {
            "Producto": "Remera Test",
            "Categoría": "REMERAS",
            "Opción 1: Valor": "Rojo",
            "Opción 2: Valor": "M",
            "Opción 3: Valor": "",
            "Precio Unitario": price,
            "Precio Final": price,
            "%": 0,
            "Descuento": 0,
            "Stock": stock,
            "row_number": row_number,
            "ID Producto": product_id,
            "ID Variante": variant_id,
        }

    @patch("services.sales_service.update_tiendanube_stock")
    @patch("services.sales_service.invalidate_products_cache")
    @patch("services.sales_service.update_product_stock", return_value=True)
    @patch("services.sales_service.add_transaction_generic")
    def test_records_sale_and_updates_stock(self, mock_add_tx, mock_update_stock,
                                            mock_invalidate, mock_tn_stock):
        mock_add_tx.return_value = {"sheet_title": "Ventas Enero 2026", "data": []}

        from services.sales_service import add_sale
        result = add_sale(self._make_variant(), quantity=2, client_name="Carlos")

        # Verify sale was recorded
        mock_add_tx.assert_called_once()
        row_data = mock_add_tx.call_args[0][2]  # third positional arg
        assert row_data[1] == "Remera Test"  # product name
        assert row_data[5] == 2  # quantity
        assert row_data[9] == 10000.0  # total = 5000 * 2

        # Verify stock was updated on Sheets
        mock_update_stock.assert_called_once_with(5, 8)  # 10 - 2 = 8

        # Verify cache was invalidated
        mock_invalidate.assert_called_once()

        # Verify TiendaNube was synced
        mock_tn_stock.assert_called_once_with(100, 200, 8)

        # Verify return value
        assert result["quantity"] == 2
        assert result["total_sale_price"] == 10000.0
        assert result["remaining_stock"] == 8

    @patch("services.sales_service.update_tiendanube_stock")
    @patch("services.sales_service.invalidate_products_cache")
    @patch("services.sales_service.update_product_stock", return_value=False)
    @patch("services.sales_service.add_transaction_generic")
    def test_stock_update_failure_does_not_invalidate_cache(
            self, mock_add_tx, mock_update_stock, mock_invalidate, mock_tn_stock):
        mock_add_tx.return_value = {"sheet_title": "Ventas", "data": []}

        from services.sales_service import add_sale
        result = add_sale(self._make_variant(), quantity=1, client_name="Ana")

        # Stock update failed → cache should NOT be invalidated
        mock_invalidate.assert_not_called()
        assert result["remaining_stock"] == "Error al actualizar"

    @patch("services.sales_service.update_tiendanube_stock")
    @patch("services.sales_service.invalidate_products_cache")
    @patch("services.sales_service.update_product_stock", return_value=True)
    @patch("services.sales_service.add_transaction_generic")
    def test_missing_tiendanube_ids_logs_error_but_succeeds(
            self, mock_add_tx, mock_update_stock, mock_invalidate, mock_tn_stock):
        mock_add_tx.return_value = {"sheet_title": "Ventas", "data": []}
        variant = self._make_variant()
        variant["ID Producto"] = None
        variant["ID Variante"] = None

        from services.sales_service import add_sale
        result = add_sale(variant, quantity=1, client_name="Luis")

        # TiendaNube should NOT be called
        mock_tn_stock.assert_not_called()
        # Sale itself should still succeed
        assert result["product_name"] == "Remera Test"

    @patch("services.sales_service.update_tiendanube_stock")
    @patch("services.sales_service.invalidate_products_cache")
    @patch("services.sales_service.update_product_stock", return_value=True)
    @patch("services.sales_service.add_transaction_generic")
    def test_variant_description_joins_non_empty_options(
            self, mock_add_tx, mock_update_stock, mock_invalidate, mock_tn_stock):
        mock_add_tx.return_value = {"sheet_title": "Ventas", "data": []}
        variant = self._make_variant()
        variant["Opción 1: Valor"] = "Rojo"
        variant["Opción 2: Valor"] = "M"
        variant["Opción 3: Valor"] = ""

        from services.sales_service import add_sale
        result = add_sale(variant, quantity=1, client_name="Test")

        assert result["variant_description"] == "Rojo, M"
