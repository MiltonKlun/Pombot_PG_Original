import pytest
pytestmark = pytest.mark.integration

# tests/test_integration_balance_report.py
"""
Integration tests for balance reporting:
get_monthly_summary + get_net_balance_for_month — verifies the balance formula
across sales, expenses, and wholesale data.
"""
from unittest.mock import patch, MagicMock
import gspread

from config import SALES_SHEET_BASE_NAME, EXPENSES_SHEET_BASE_NAME


class TestGetMonthlySummary:
    """get_monthly_summary — totals and category breakdown from a sheet."""

    @patch("services.balance_service.IS_SHEET_CONNECTED", True)
    @patch("services.balance_service.spreadsheet")
    def test_sales_summary_totals(self, mock_ss):
        """Sales summary calculates total from Precio Total column."""
        mock_ws = MagicMock()
        mock_ws.get_all_records.return_value = [
            {"Categoría": "REMERAS", "Precio Total": 10000},
            {"Categoría": "PANTALONES", "Precio Total": 7200},
            {"Categoría": "REMERAS", "Precio Total": 5000},
        ]
        mock_ss.worksheet.return_value = mock_ws

        from services.balance_service import get_monthly_summary
        result = get_monthly_summary(SALES_SHEET_BASE_NAME, 2026, 1)

        assert result["total"] == 22200.0
        assert result["count"] == 3
        assert result["by_category"]["REMERAS"] == 15000.0
        assert result["by_category"]["PANTALONES"] == 7200.0

    @patch("services.balance_service.IS_SHEET_CONNECTED", True)
    @patch("services.balance_service.spreadsheet")
    def test_expenses_summary_uses_monto_column(self, mock_ss):
        """Expense summary reads from Monto column."""
        mock_ws = MagicMock()
        mock_ws.get_all_records.return_value = [
            {"Categoría": "INSUMOS", "Monto": 5000},
            {"Categoría": "PERSONALES", "Monto": 80000},
            {"Categoría": "CANJES", "Monto": 3000},
        ]
        mock_ss.worksheet.return_value = mock_ws

        from services.balance_service import get_monthly_summary
        result = get_monthly_summary(EXPENSES_SHEET_BASE_NAME, 2026, 1)

        assert result["total"] == 88000.0
        assert result["by_category"]["PERSONALES"] == 80000.0
        assert result["by_category"]["CANJES"] == 3000.0

    @patch("services.balance_service.IS_SHEET_CONNECTED", True)
    @patch("services.balance_service.spreadsheet")
    def test_missing_sheet_returns_zero_totals(self, mock_ss):
        """Non-existent sheet returns zero totals."""
        mock_ss.worksheet.side_effect = gspread.exceptions.WorksheetNotFound("test")

        from services.balance_service import get_monthly_summary
        result = get_monthly_summary(SALES_SHEET_BASE_NAME, 2026, 1)

        assert result["total"] == 0.0
        assert result["count"] == 0

    @patch("services.balance_service.IS_SHEET_CONNECTED", False)
    def test_raises_on_no_connection(self):
        from services.balance_service import get_monthly_summary
        with pytest.raises(ConnectionError):
            get_monthly_summary(SALES_SHEET_BASE_NAME, 2026, 1)


class TestGetNetBalanceForMonth:
    """get_net_balance_for_month — the master balance formula:
    saldo_pg = (sales + wholesale) - gastos_pg
    saldo_neto = saldo_pg - gastos_personales
    """

    @patch("services.balance_service.IS_SHEET_CONNECTED", True)
    @patch("services.balance_service.spreadsheet")
    @patch("services.balance_service.get_wholesale_summary")
    def test_balance_formula(self, mock_wholesale, mock_ss, ):
        """Verify the net balance calculation with known data."""
        # Sales sheet
        mock_sales_ws = MagicMock()
        mock_sales_ws.get_all_records.return_value = [
            {"Categoría": "REMERAS", "Precio Total": 100000},
        ]

        # Expenses sheet
        mock_expenses_ws = MagicMock()
        mock_expenses_ws.get_all_records.return_value = [
            {"Categoría": "INSUMOS", "Subcategoría": "", "Monto": 20000},
            {"Categoría": "PERSONALES", "Subcategoría": "ALQUILER", "Monto": 50000},
            {"Categoría": "CANJES", "Subcategoría": "Promo", "Monto": 3000},
        ]

        def worksheet_side_effect(title):
            if "Ventas" in title:
                return mock_sales_ws
            elif "Gastos" in title:
                return mock_expenses_ws
            raise gspread.exceptions.WorksheetNotFound(title)

        mock_ss.worksheet.side_effect = worksheet_side_effect

        mock_wholesale.return_value = {
            "total": 30000.0, "count": 2, "by_client": {}, "details": []
        }

        from services.balance_service import get_net_balance_for_month
        result = get_net_balance_for_month(2026, 1)

        # Sales = 100000, Wholesale = 30000
        # Non-personal, non-canje expenses = INSUMOS 20000
        # saldo_pg = (100000 + 30000) - 20000 = 110000
        assert result["saldo_pg"] == 110000.0

        # Personal expenses = 50000
        # saldo_neto = 110000 - 50000 = 60000
        assert result["saldo_neto"] == 60000.0

        # CANJES are separated
        assert result["canjes_summary"]["total"] == 3000.0

        # Month name
        assert result["month_name"] == "Enero"
        assert result["year"] == 2026

    @patch("services.balance_service.IS_SHEET_CONNECTED", True)
    @patch("services.balance_service.spreadsheet")
    @patch("services.balance_service.get_wholesale_summary")
    def test_balance_with_no_sales(self, mock_wholesale, mock_ss):
        """Zero sales → negative balance if expenses exist."""
        mock_ws = MagicMock()
        mock_ws.get_all_records.return_value = []

        def worksheet_side_effect(title):
            if "Gastos" in title:
                mock_exp_ws = MagicMock()
                mock_exp_ws.get_all_records.return_value = [
                    {"Categoría": "INSUMOS", "Subcategoría": "", "Monto": 10000},
                ]
                return mock_exp_ws
            raise gspread.exceptions.WorksheetNotFound(title)

        mock_ss.worksheet.side_effect = worksheet_side_effect
        mock_wholesale.return_value = {"total": 0.0, "count": 0, "by_client": {}, "details": []}

        from services.balance_service import get_net_balance_for_month
        result = get_net_balance_for_month(2026, 1)

        assert result["saldo_pg"] == -10000.0
        assert result["saldo_neto"] == -10000.0


class TestGetAvailableSheetMonthsYears:
    """get_available_sheet_months_years — discovers data months from sheet titles."""

    @patch("services.balance_service.IS_SHEET_CONNECTED", True)
    @patch("services.balance_service.spreadsheet")
    def test_discovers_months_from_sheet_titles(self, mock_ss):
        mock_ss.worksheets.return_value = [
            MagicMock(title="Ventas Enero 2026"),
            MagicMock(title="Gastos Enero 2026"),
            MagicMock(title="Ventas Febrero 2026"),
            MagicMock(title="Deudas"),  # Non-monthly sheet
            MagicMock(title="Mayoristas Enero 2026"),
        ]

        from services.balance_service import get_available_sheet_months_years
        result = get_available_sheet_months_years()

        assert (2026, 2) in result
        assert (2026, 1) in result
        # Sorted descending
        assert result[0] == (2026, 2)

    @patch("services.balance_service.IS_SHEET_CONNECTED", False)
    def test_returns_empty_when_not_connected(self):
        from services.balance_service import get_available_sheet_months_years
        assert get_available_sheet_months_years() == []
