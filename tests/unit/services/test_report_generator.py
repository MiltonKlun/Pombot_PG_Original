import pytest
pytestmark = pytest.mark.unit

# tests/test_report_generator.py
"""Unit tests for services/report_generator.py — Risk R9: PDF generation edge cases."""
from unittest.mock import patch, MagicMock
import io
import os


class TestHexToRgb:
    """Tests for hex_to_rgb — color conversion utility."""

    def test_converts_black(self):
        from services.report_generator import hex_to_rgb
        assert hex_to_rgb("#000000") == (0, 0, 0)

    def test_converts_white(self):
        from services.report_generator import hex_to_rgb
        assert hex_to_rgb("#FFFFFF") == (255, 255, 255)

    def test_converts_brand_primary(self):
        from services.report_generator import hex_to_rgb
        assert hex_to_rgb("#c0392b") == (192, 57, 43)

    def test_handles_no_hash(self):
        from services.report_generator import hex_to_rgb
        assert hex_to_rgb("FF5733") == (255, 87, 51)


class TestGenerateBalancePdf:
    """Tests for generate_balance_pdf — produces valid PDF output."""

    @pytest.fixture
    def full_balance_data(self):
        return {
            "month_name": "Enero",
            "year": 2026,
            "sales_summary": {"total": 100000.0, "count": 10, "by_category": {"REMERAS": 70000.0, "PANTALONES": 30000.0}},
            "wholesale_summary": {
                "total": 50000.0, "count": 3,
                "by_client": {"ClienteA": {"amount": 30000.0, "quantity": 5}, "ClienteB": {"amount": 20000.0, "quantity": 3}},
                "details": [
                    {"client": "ClienteA", "product": "Remera", "quantity": 5, "amount": 30000.0},
                    {"client": "ClienteB", "product": "Pantalón", "quantity": 3, "amount": 20000.0},
                ]
            },
            "gastos_pg_summary": {"total": 30000.0, "count": 5, "by_category": {"INSUMOS": 20000.0, "MARKETING": 10000.0}},
            "gastos_personales_summary": {"total": 15000.0, "count": 2, "by_category": {"ALQUILER": 15000.0}},
            "saldo_pg": 120000.0,
            "saldo_neto": 105000.0,
        }

    @pytest.fixture
    def empty_balance_data(self):
        return {
            "month_name": "Febrero",
            "year": 2026,
            "sales_summary": {"total": 0.0, "count": 0, "by_category": {}},
            "wholesale_summary": {"total": 0.0, "count": 0, "by_client": {}, "details": []},
            "gastos_pg_summary": {"total": 0.0, "count": 0, "by_category": {}},
            "gastos_personales_summary": {"total": 0.0, "count": 0, "by_category": {}},
            "saldo_pg": 0.0,
            "saldo_neto": 0.0,
        }

    @patch("services.report_generator._create_bar_chart")
    def test_produces_valid_file_path(self, mock_chart, full_balance_data):
        from services.report_generator import generate_balance_pdf
        result = generate_balance_pdf(full_balance_data)

        assert result is not None
        assert result.endswith(".pdf")
        assert "Enero" in result
        assert "2026" in result
        if result and os.path.exists(result):
            os.remove(result)

    @patch("services.report_generator._create_bar_chart")
    def test_pdf_file_is_non_empty(self, mock_chart, full_balance_data):
        from services.report_generator import generate_balance_pdf
        result = generate_balance_pdf(full_balance_data)

        assert result is not None
        assert os.path.getsize(result) > 0
        if result and os.path.exists(result):
            os.remove(result)

    @patch("services.report_generator._create_bar_chart")
    def test_handles_empty_balance_data(self, mock_chart, empty_balance_data):
        from services.report_generator import generate_balance_pdf
        result = generate_balance_pdf(empty_balance_data)

        assert result is not None
        assert os.path.getsize(result) > 0
        if result and os.path.exists(result):
            os.remove(result)

    def test_returns_none_on_error(self):
        from services.report_generator import generate_balance_pdf
        result = generate_balance_pdf(None)
        assert result is None


class TestCreateBarChart:
    """Tests for _create_bar_chart — produces chart image via QuickChart."""

    @patch("services.report_generator.requests.post")
    def test_writes_to_buffer(self, mock_post):
        mock_response = MagicMock()
        mock_response.content = b"\x89PNG\r\n\x1a\n"  # PNG header bytes
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        from services.report_generator import _create_bar_chart
        buffer = io.BytesIO()
        _create_bar_chart({"INSUMOS": 20000, "MARKETING": 10000}, "Test Chart", buffer)

        assert buffer.getbuffer().nbytes > 0

    @patch("services.report_generator.requests.post")
    def test_handles_empty_data(self, mock_post):
        from services.report_generator import _create_bar_chart
        buffer = io.BytesIO()
        _create_bar_chart({}, "Empty Chart", buffer)

        mock_post.assert_not_called()
        assert buffer.getbuffer().nbytes == 0

    @patch("services.report_generator.requests.post")
    def test_handles_api_error(self, mock_post):
        import requests as req_lib
        mock_post.side_effect = req_lib.exceptions.ConnectionError("timeout")

        from services.report_generator import _create_bar_chart
        buffer = io.BytesIO()
        _create_bar_chart({"A": 100}, "Fail Chart", buffer)
        assert buffer.getbuffer().nbytes == 0
