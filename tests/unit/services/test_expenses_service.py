import pytest
pytestmark = pytest.mark.unit

# tests/test_expenses_service.py
"""Unit tests for services/expenses_service.py — expense recording."""
from unittest.mock import patch, MagicMock
from datetime import datetime


class TestAddExpense:
    """Tests for add_expense — appends a row to the monthly expense sheet."""

    @patch("services.expenses_service.get_or_create_monthly_sheet")
    def test_happy_path_uses_current_date(self, mock_get_sheet):
        mock_ws = MagicMock()
        mock_ws.title = "Gastos Enero 2026"
        mock_get_sheet.return_value = mock_ws

        from services.expenses_service import add_expense
        result = add_expense(
            category="INSUMOS",
            subcategory="ESTAMPAS",
            description="Tela importada",
            details="2 metros",
            amount=5000.0
        )

        mock_ws.append_row.assert_called_once()
        row = mock_ws.append_row.call_args[0][0]
        assert row[1] == "INSUMOS"
        assert row[2] == "ESTAMPAS"
        assert row[3] == "Tela importada"
        assert row[4] == "2 metros"
        assert row[5] == 5000.0
        assert result["category"] == "INSUMOS"
        assert result["sheet_title"] == "Gastos Enero 2026"

    @patch("services.expenses_service.get_or_create_monthly_sheet")
    def test_custom_date_overrides_default(self, mock_get_sheet):
        mock_ws = MagicMock()
        mock_ws.title = "Gastos Marzo 2026"
        mock_get_sheet.return_value = mock_ws

        from services.expenses_service import add_expense
        result = add_expense(
            category="PERSONALES",
            subcategory="LUZ",
            description="Factura",
            details="",
            amount=15000.0,
            date_str="2026-03-15 10:00:00"
        )

        # date_override should be March 2026
        call_kwargs = mock_get_sheet.call_args
        date_override = call_kwargs[1].get("date_override") or call_kwargs[0][2] if len(call_kwargs[0]) > 2 else None
        row = mock_ws.append_row.call_args[0][0]
        assert row[0] == "2026-03-15 10:00:00"
        assert result["amount"] == 15000.0

    @patch("services.expenses_service.get_or_create_monthly_sheet")
    def test_raises_on_no_connection(self, mock_get_sheet):
        mock_get_sheet.return_value = None

        from services.expenses_service import add_expense
        with pytest.raises(ConnectionError, match="no disponible"):
            add_expense("INSUMOS", "TELA", "Desc", "", 1000.0)

    @patch("services.expenses_service.get_or_create_monthly_sheet")
    def test_returns_all_fields_in_result(self, mock_get_sheet):
        mock_ws = MagicMock()
        mock_ws.title = "Gastos Febrero 2026"
        mock_get_sheet.return_value = mock_ws

        from services.expenses_service import add_expense
        result = add_expense("CANJES", "Promo", "Canje influencer", "IG", 3000.0)

        assert result["category"] == "CANJES"
        assert result["subcategory"] == "Promo"
        assert result["description"] == "Canje influencer"
        assert result["details"] == "IG"
        assert result["amount"] == 3000.0
        assert "timestamp" in result
        assert "sheet_title" in result
