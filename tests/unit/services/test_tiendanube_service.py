import pytest
pytestmark = pytest.mark.unit

# tests/test_tiendanube_service.py
"""Unit tests for services/tiendanube_service.py — Risk R4: TiendaNube API failures."""
from unittest.mock import patch, MagicMock
import requests


class TestGetLocalizedName:
    """Tests for _get_localized_name — locale fallback chain."""

    def test_prefers_es(self):
        from services.tiendanube_service import _get_localized_name
        result = _get_localized_name({"es": "Remera", "en": "T-Shirt"})
        assert result == "Remera"

    def test_falls_back_to_es_AR(self):
        from services.tiendanube_service import _get_localized_name
        result = _get_localized_name({"es_AR": "Remera AR", "en": "T-Shirt"})
        assert result == "Remera AR"

    def test_falls_back_to_any_non_empty(self):
        from services.tiendanube_service import _get_localized_name
        result = _get_localized_name({"pt": "Camiseta"})
        assert result == "Camiseta"

    def test_handles_string_input(self):
        from services.tiendanube_service import _get_localized_name
        assert _get_localized_name("Remera") == "Remera"

    def test_handles_empty_dict(self):
        from services.tiendanube_service import _get_localized_name
        assert _get_localized_name({}) == "No disponible"

    def test_handles_none(self):
        from services.tiendanube_service import _get_localized_name
        assert _get_localized_name(None) == "No disponible"

    def test_handles_int(self):
        from services.tiendanube_service import _get_localized_name
        assert _get_localized_name(42) == "No disponible"


class TestGetTiendanubeProducts:
    """Tests for get_tiendanube_products — pagination, validation, errors."""

    @patch("services.tiendanube_service.TIENDANUBE_ACCESS_TOKEN", "valid_token")
    @patch("services.tiendanube_service.TIENDANUBE_STORE_ID", 12345)
    @patch("services.tiendanube_service.requests.get")
    def test_happy_path_single_page(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "id": 1,
                "name": {"es": "Remera"},
                "categories": [{"name": {"es": "REMERAS"}}],
                "attributes": [{"es": "Color"}, {"es": "Talle"}],
                "variants": [
                    {
                        "id": 100,
                        "sku": "REM-001",
                        "stock_management": True,
                        "stock": 10,
                        "price": "5000.00",
                        "promotional_price": None,
                        "values": [{"es": "Rojo"}, {"es": "M"}],
                    }
                ],
            }
        ]
        # First call returns data, second returns empty (end of pages)
        mock_get.side_effect = [mock_response, MagicMock(json=MagicMock(return_value=[]), status_code=200, raise_for_status=MagicMock())]

        from services.tiendanube_service import get_tiendanube_products
        result = get_tiendanube_products()

        assert len(result) == 1
        row = result[0]
        assert row[0] == "Remera"       # product name
        assert row[1] == 1              # product id
        assert row[2] == 100            # variant id
        assert row[3] == "REM-001"      # sku
        assert row[11] == 10            # stock
        assert row[12] == 5000.0        # unit price
        assert row[15] == 5000.0        # final price (no promo)

    @patch("services.tiendanube_service.TIENDANUBE_ACCESS_TOKEN", "valid_token")
    @patch("services.tiendanube_service.TIENDANUBE_STORE_ID", 12345)
    @patch("services.tiendanube_service.requests.get")
    def test_promo_price_calculates_discount(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "id": 1, "name": "Test", "categories": [], "attributes": [],
                "variants": [{
                    "id": 100, "sku": "", "stock_management": True, "stock": 5,
                    "price": "10000.00", "promotional_price": "8000.00", "values": [],
                }]
            }
        ]
        mock_get.side_effect = [mock_response, MagicMock(json=MagicMock(return_value=[]), status_code=200, raise_for_status=MagicMock())]

        from services.tiendanube_service import get_tiendanube_products
        result = get_tiendanube_products()

        row = result[0]
        assert row[12] == 10000.0            # unit price
        assert row[15] == 8000.0             # final price = promo
        assert row[14] == 2000.0             # fixed discount
        assert row[13] == pytest.approx(20.0) # 20% discount

    @patch("services.tiendanube_service.TIENDANUBE_STORE_ID", None)
    def test_raises_on_no_store_id(self):
        from services.tiendanube_service import get_tiendanube_products
        with pytest.raises(ValueError, match="Store ID"):
            get_tiendanube_products()

    @patch("services.tiendanube_service.TIENDANUBE_STORE_ID", 12345)
    @patch("services.tiendanube_service.TIENDANUBE_ACCESS_TOKEN", "your_tiendanube_access_token")
    def test_raises_on_placeholder_token(self):
        from services.tiendanube_service import get_tiendanube_products
        with pytest.raises(ValueError, match="Token"):
            get_tiendanube_products()

    @patch("services.tiendanube_service.TIENDANUBE_ACCESS_TOKEN", "valid_token")
    @patch("services.tiendanube_service.TIENDANUBE_STORE_ID", 12345)
    @patch("services.tiendanube_service.requests.get")
    def test_raises_connection_error_on_http_failure(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError("timeout")

        from services.tiendanube_service import get_tiendanube_products
        with pytest.raises(ConnectionError):
            get_tiendanube_products()

    @patch("services.tiendanube_service.TIENDANUBE_ACCESS_TOKEN", "valid_token")
    @patch("services.tiendanube_service.TIENDANUBE_STORE_ID", 12345)
    @patch("services.tiendanube_service.requests.get")
    def test_unmanaged_stock_returns_999(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "id": 1, "name": "Test", "categories": [], "attributes": [],
                "variants": [{
                    "id": 100, "sku": "", "stock_management": False,
                    "stock": None, "price": "1000.00", "promotional_price": None, "values": [],
                }]
            }
        ]
        mock_get.side_effect = [mock_response, MagicMock(json=MagicMock(return_value=[]), status_code=200, raise_for_status=MagicMock())]

        from services.tiendanube_service import get_tiendanube_products
        result = get_tiendanube_products()

        assert result[0][11] == 999  # stock = 999 for unmanaged


class TestGetRealtimeStock:
    """Tests for get_realtime_stock — queries API for variant stock."""

    @patch("services.tiendanube_service.requests.get")
    def test_returns_stock_for_managed_variant(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"stock_management": True, "stock": 15}
        mock_get.return_value = mock_response

        from services.tiendanube_service import get_realtime_stock
        assert get_realtime_stock(1, 100) == 15

    @patch("services.tiendanube_service.requests.get")
    def test_returns_999_for_unmanaged(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"stock_management": False, "stock": None}
        mock_get.return_value = mock_response

        from services.tiendanube_service import get_realtime_stock
        assert get_realtime_stock(1, 100) == 999

    @patch("services.tiendanube_service.requests.get")
    def test_returns_none_on_error(self, mock_get):
        mock_get.side_effect = Exception("Network error")

        from services.tiendanube_service import get_realtime_stock
        assert get_realtime_stock(1, 100) is None


class TestUpdateTiendanubeStock:
    """Tests for update_tiendanube_stock — sends PUT request."""

    @patch("services.tiendanube_service.requests.put")
    def test_sends_correct_payload(self, mock_put):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_put.return_value = mock_response

        from services.tiendanube_service import update_tiendanube_stock
        result = update_tiendanube_stock(product_id=1, variant_id=100, new_stock_level=8)

        assert result is True
        call_kwargs = mock_put.call_args
        assert call_kwargs[1]["json"] == {"stock": 8}

    @patch("services.tiendanube_service.requests.put")
    def test_returns_false_on_error(self, mock_put):
        mock_put.side_effect = Exception("API error")

        from services.tiendanube_service import update_tiendanube_stock
        assert update_tiendanube_stock(1, 100, 8) is False
