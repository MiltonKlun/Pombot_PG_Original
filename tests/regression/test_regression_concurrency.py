import pytest
pytestmark = pytest.mark.regression

# tests/regression/test_regression_concurrency.py
"""
Regression tests for concurrency-related logic (cache consistency).
"""
from unittest.mock import patch, MagicMock
from services.products_service import get_all_products_data_cached, invalidate_products_cache, products_cache

class TestCacheInvalidation:
    """Verify cache state consistency."""

    @pytest.fixture(autouse=True)
    def reset_global_cache(self):
        """Reset the global products_cache before each test."""
        invalidate_products_cache()
        products_cache['data'] = None
        products_cache['timestamp'] = None
        yield
        # Cleanup
        invalidate_products_cache()

    @patch("services.products_service.get_product_sheet")
    def test_invalidation_forces_refresh(self, mock_get_sheet):
        # Setup mock worksheet
        mock_ws = MagicMock()
        mock_ws.get_all_records.return_value = [{"Producto": "A", "Stock": 10}]
        mock_get_sheet.return_value = mock_ws

        # 1. Fill cache
        data1 = get_all_products_data_cached()
        assert data1[0]["Stock"] == 10
        assert mock_ws.get_all_records.call_count == 1

        # 2. Invalidate
        invalidate_products_cache()

        # 3. Fetch again -> should call get_all_records again
        data2 = get_all_products_data_cached()
        assert data2[0]["Stock"] == 10
        assert mock_ws.get_all_records.call_count == 2
    
    @patch("services.products_service.get_product_sheet")
    def test_no_invalidation_uses_cache(self, mock_get_sheet):
        mock_ws = MagicMock()
        mock_ws.get_all_records.return_value = [{"Producto": "A", "Stock": 10}]
        mock_get_sheet.return_value = mock_ws

        # 1. Fill cache
        get_all_products_data_cached()
        
        # 2. Fetch again immediately
        get_all_products_data_cached()

        # Should strictly be 1 actual call to sheet
        assert mock_ws.get_all_records.call_count == 1
