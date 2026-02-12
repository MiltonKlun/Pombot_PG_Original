import pytest
pytestmark = pytest.mark.unit

# tests/test_products_service.py
"""Unit tests for services/products_service.py — Risk R11: cache & product data correctness."""
from unittest.mock import patch, MagicMock 
from datetime import datetime, timedelta
from config import PRODUCTOS_HEADERS

# ... (Existing tests: TestInvalidateProductsCache, TestGetAllProductsDataCached, etc.) ...
# I will retain existing tests and append new ones.

class TestInvalidateProductsCache:
    """Tests for invalidate_products_cache."""

    def test_clears_cache(self):
        import services.products_service as ps
        ps.products_cache['data'] = [{"Producto": "Test"}]
        ps.products_cache['timestamp'] = datetime.now()

        ps.invalidate_products_cache()

        # After invalidation, the module's products_cache should be reset
        assert ps.products_cache['data'] is None
        assert ps.products_cache['timestamp'] is None


class TestGetAllProductsDataCached:
    """Tests for get_all_products_data_cached — TTL-based cache (uses datetime, not time.time())."""

    @patch("services.products_service.get_product_sheet")
    def test_fetches_from_sheet_on_cold_cache(self, mock_get_sheet):
        import services.products_service as ps
        ps.products_cache = {'data': None, 'timestamp': None}

        mock_ws = MagicMock()
        mock_ws.get_all_records.return_value = [
            {"Producto": "Remera", "Categoría": "REMERAS"},
        ]
        mock_get_sheet.return_value = mock_ws

        result = ps.get_all_products_data_cached()

        assert len(result) == 1
        assert result[0]["Producto"] == "Remera"
        mock_ws.get_all_records.assert_called_once()

    @patch("services.products_service.get_product_sheet")
    def test_returns_cached_data_within_ttl(self, mock_get_sheet):
        import services.products_service as ps
        cached_data = [{"Producto": "Cached"}]
        ps.products_cache = {'data': cached_data, 'timestamp': datetime.now()}

        result = ps.get_all_products_data_cached()

        assert result == cached_data
        mock_get_sheet.assert_not_called()

    @patch("services.products_service.get_product_sheet")
    def test_refreshes_after_ttl_expires(self, mock_get_sheet):
        import services.products_service as ps
        expired_ts = datetime.now() - timedelta(seconds=ps.CACHE_TTL_SECONDS + 1)
        ps.products_cache = {'data': [{"Producto": "Old"}], 'timestamp': expired_ts}

        mock_ws = MagicMock()
        mock_ws.get_all_records.return_value = [{"Producto": "Fresh"}]
        mock_get_sheet.return_value = mock_ws

        result = ps.get_all_products_data_cached()

        assert result[0]["Producto"] == "Fresh"
        mock_ws.get_all_records.assert_called_once()

    @patch("services.products_service.get_product_sheet")
    def test_returns_empty_on_no_sheet(self, mock_get_sheet):
        import services.products_service as ps
        ps.products_cache = {'data': None, 'timestamp': None}
        mock_get_sheet.return_value = None

        assert ps.get_all_products_data_cached() == []


class TestGetProductCategories:
    """Tests for get_product_categories — unique sorted categories."""

    @patch("services.products_service.get_all_products_data_cached")
    def test_returns_sorted_unique(self, mock_cached):
        mock_cached.return_value = [
            {"Categoría": "REMERAS"},
            {"Categoría": "BUZOS"},
            {"Categoría": "REMERAS"},
            {"Categoría": "PANTALONES"},
        ]

        from services.products_service import get_product_categories
        result = get_product_categories()

        assert result == ["BUZOS", "PANTALONES", "REMERAS"]

    @patch("services.products_service.get_all_products_data_cached")
    def test_returns_empty_on_no_data(self, mock_cached):
        mock_cached.return_value = []

        from services.products_service import get_product_categories
        assert get_product_categories() == []


class TestGetProductsByCategory:
    """Tests for get_products_by_category — filters by category."""

    @patch("services.products_service.get_all_products_data_cached")
    def test_filters_by_category(self, mock_cached):
        mock_cached.return_value = [
            {"Producto": "Remera Básica", "Categoría": "REMERAS"},
            {"Producto": "Pantalón Cargo", "Categoría": "PANTALONES"},
            {"Producto": "Remera Premium", "Categoría": "REMERAS"},
        ]

        from services.products_service import get_products_by_category
        result = get_products_by_category("REMERAS")

        assert "Remera Básica" in result
        assert "Remera Premium" in result
        assert "Pantalón Cargo" not in result

    @patch("services.products_service.get_all_products_data_cached")
    def test_returns_empty_for_unknown_category(self, mock_cached):
        mock_cached.return_value = [
            {"Producto": "Remera", "Categoría": "REMERAS"},
        ]

        from services.products_service import get_products_by_category
        assert get_products_by_category("ZAPATOS") == []


class TestGetVariantDetails:
    """Tests for get_variant_details — finds exact match using insensitive lookup on keys."""

    @patch("services.products_service.get_all_products_data_cached")
    def test_finds_exact_match(self, mock_cached):
        """Selections dict keys should match the option value keys after insensitive lookup."""
        mock_cached.return_value = [
            {
                "Producto": "Remera", "Categoría": "REMERAS",
                "Opción 1: Nombre": "Color", "Opción 1: Valor": "Rojo",
                "Opción 2: Nombre": "Talle", "Opción 2: Valor": "M",
                "Opción 3: Nombre": "", "Opción 3: Valor": "",
                "Precio Final": 5000, "Precio Unitario": 5000,
                "%": 0, "Descuento": 0, "Stock": 10,
                "ID Producto": 100, "ID Variante": 200,
                "row_number": 3,
            },
        ]

        from services.products_service import get_variant_details
        # The function matches on arbitrary keys
        result = get_variant_details("Remera", {"Opción 1: Valor": "Rojo", "Opción 2: Valor": "M"})

        assert result is not None
        assert result["Opción 1: Valor"] == "Rojo"
        assert result["Opción 2: Valor"] == "M"

    @patch("services.products_service.get_all_products_data_cached")
    def test_returns_none_for_no_match(self, mock_cached):
        mock_cached.return_value = [
            {
                "Producto": "Remera", "Categoría": "REMERAS",
                "Opción 1: Nombre": "Color", "Opción 1: Valor": "Rojo",
                "Opción 2: Nombre": "Talle", "Opción 2: Valor": "M",
                "Opción 3: Nombre": "", "Opción 3: Valor": "",
                "Precio Final": 5000, "Precio Unitario": 5000,
                "%": 0, "Descuento": 0, "Stock": 10,
                "ID Producto": 100, "ID Variante": 200,
                "row_number": 4,
            },
        ]

        from services.products_service import get_variant_details
        result = get_variant_details("Remera", {"Opción 1: Valor": "Verde", "Opción 2: Valor": "XL"})

        assert result is None


class TestUpdateProductStock:
    """Tests for update_product_stock — updates the stock cell using PRODUCTOS_HEADERS index."""

    @patch("services.products_service.get_product_sheet")
    def test_updates_correct_cell(self, mock_get_sheet):
        mock_ws = MagicMock()
        mock_get_sheet.return_value = mock_ws

        from services.products_service import update_product_stock
        result = update_product_stock(row_number=5, new_stock=8)

        assert result is True
        mock_ws.update_cell.assert_called_once()

    @patch("services.products_service.get_product_sheet")
    def test_returns_false_on_no_sheet(self, mock_get_sheet):
        mock_get_sheet.return_value = None

        from services.products_service import update_product_stock
        result = update_product_stock(5, 8)

        assert result is False


class TestUpdateProductsFromTiendanube:
    """Tests for full sheet replacement from TiendaNube data (Sync)."""

    @patch("services.products_service.get_product_sheet")
    @patch("services.products_service.IS_SHEET_CONNECTED", True)
    @patch("services.products_service.apply_table_formatting")
    @patch("services.products_service.invalidate_products_cache")
    def test_successful_update(self, mock_invalidate, mock_format, mock_get_sheet):
        from services.products_service import update_products_from_tiendanube
        
        mock_ws = MagicMock()
        mock_get_sheet.return_value = mock_ws
        
        new_data = [{"ID Producto": 1, "Nombre": "Nuevo"}]
        success, msg = update_products_from_tiendanube(new_data)
        
        assert success is True
        assert "actualizada" in msg
        mock_ws.clear.assert_called_once()
        mock_ws.append_row.assert_called_once_with(PRODUCTOS_HEADERS, value_input_option='USER_ENTERED')
        mock_ws.append_rows.assert_called_once_with(new_data, value_input_option='USER_ENTERED')
        mock_invalidate.assert_called_once()

    @patch("services.products_service.get_product_sheet")
    @patch("services.products_service.IS_SHEET_CONNECTED", True)
    def test_handles_sheet_error(self, mock_get_sheet):
        from services.products_service import update_products_from_tiendanube
        
        mock_ws = MagicMock()
        # Simulate error during clear
        mock_ws.clear.side_effect = Exception("API Error")
        mock_get_sheet.return_value = mock_ws
        
        success, msg = update_products_from_tiendanube([{}])
        
        assert success is False
        assert "Error inesperado" in msg
        assert "API Error" in msg


class TestGetVariantDetailsNormalization:
    """Tests for Fuzzy/Normalization matching in get_variant_details."""

    @patch("services.products_service.get_all_products_data_cached")
    def test_matches_accented_characters(self, mock_cached):
        # Data in cache has accents
        mock_cached.return_value = [{
            "Producto": "Algodón",
            "Opción 1: Valor": "Único",
            "ID Producto": 1,
            "ID Variante": 1,
            "row_number": 2,
            "Stock": 5
        }]
        
        from services.products_service import get_variant_details
        
        # Search using unaccented text (user input)
        selections = {"Opción 1: Valor": "Unico"} 
        result = get_variant_details("Algodon", selections)
        
        assert result is not None
        assert result["ID Producto"] == 1
        assert result["Opción 1: Valor"] == "Único" # Should return original data

    @patch("services.products_service.get_all_products_data_cached")
    def test_matches_case_insensitive(self, mock_cached):
        mock_cached.return_value = [{
            "Producto": "Remera",
            "Opción 1: Valor": "Rojo",
            "ID Producto": 1,
            "ID Variante": 1,
            "row_number": 2,
            "Stock": 5
        }]
        
        from services.products_service import get_variant_details
        
        # Search using UPPERCASE
        selections = {"Opción 1: Valor": "ROJO"} 
        result = get_variant_details("REMERA", selections)
        
        assert result is not None
        assert result["ID Producto"] == 1


class TestGetProductOptions:
    """Tests for get_product_options — filters by product and prior selections."""

    @patch("services.products_service.get_all_products_data_cached")
    def test_returns_empty_if_no_products(self, mock_cached):
        mock_cached.return_value = []
        from services.products_service import get_product_options
        name, options = get_product_options("Remera", 1)
        assert name == ""
        assert options == []

    @patch("services.products_service.get_all_products_data_cached")
    def test_returns_level_1_options(self, mock_cached):
        mock_cached.return_value = [
            {"Producto": "Remera", "Opción 1: Nombre": "Color", "Opción 1: Valor": "Rojo"},
            {"Producto": "Remera", "Opción 1: Nombre": "Color", "Opción 1: Valor": "Azul"},
            {"Producto": "Pantalón", "Opción 1: Nombre": "Talle", "Opción 1: Valor": "L"},
        ]
        from services.products_service import get_product_options
        name, options = get_product_options("Remera", 1)
        
        assert name == "Color"
        assert "Rojo" in options
        assert "Azul" in options
        assert "L" not in options

    @patch("services.products_service.get_all_products_data_cached")
    def test_returns_level_2_options_filtered_by_prior(self, mock_cached):
        mock_cached.return_value = [
            {"Producto": "Remera", "Opción 1: Valor": "Rojo", "Opción 2: Nombre": "Talle", "Opción 2: Valor": "S"},
            {"Producto": "Remera", "Opción 1: Valor": "Rojo", "Opción 2: Nombre": "Talle", "Opción 2: Valor": "M"},
            {"Producto": "Remera", "Opción 1: Valor": "Azul", "Opción 2: Nombre": "Talle", "Opción 2: Valor": "L"},
        ]
        from services.products_service import get_product_options
        
        # User selected Rojo, should see S and M, but NOT L
        prior = {"Opción 1: Valor": "Rojo"}
        name, options = get_product_options("Remera", 2, prior)
        
        assert name == "Talle"
        assert "S" in options
        assert "M" in options
        assert "L" not in options

    @patch("services.products_service.get_all_products_data_cached")
    def test_handles_insensitive_matching(self, mock_cached):
        mock_cached.return_value = [
            {"Producto": "Remera", "Opción 1: Valor": "Rojo", "Opción 2: Nombre": "Talle", "Opción 2: Valor": "S"},
        ]
        from services.products_service import get_product_options
        
        # User selected "rojo" (lowercase), data has "Rojo"
        prior = {"Opción 1: Valor": "rojo"}
        name, options = get_product_options("REMERA", 2, prior)
        
        assert name == "Talle"
        assert "S" in options

