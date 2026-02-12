import pytest
pytestmark = pytest.mark.unit

# tests/test_balance.py
"""Unit tests for balance_service.py — requires mocking Google Sheets."""
from unittest.mock import patch, MagicMock


class TestGetMonthlySummary:
    """Tests for get_monthly_summary — aggregates data from a sheet tab."""

    @patch("services.balance_service.IS_SHEET_CONNECTED", True)
    @patch("services.balance_service.spreadsheet")
    def test_calculates_totals(self, mock_spreadsheet, sample_sales_records):
        mock_worksheet = MagicMock()
        mock_worksheet.get_all_records.return_value = sample_sales_records
        mock_spreadsheet.worksheet.return_value = mock_worksheet

        from services.balance_service import get_monthly_summary
        result = get_monthly_summary("Ventas", 2026, 1)

        assert result["total"] == 17200.0  # 10000 + 7200
        assert result["count"] == 2
        assert "REMERAS" in result["by_category"]
        assert "PANTALONES" in result["by_category"]

    @patch("services.balance_service.IS_SHEET_CONNECTED", True)
    @patch("services.balance_service.spreadsheet")
    def test_empty_sheet(self, mock_spreadsheet):
        import gspread
        mock_spreadsheet.worksheet.side_effect = gspread.exceptions.WorksheetNotFound

        from services.balance_service import get_monthly_summary
        result = get_monthly_summary("Ventas", 2026, 1)

        assert result["total"] == 0.0
        assert result["count"] == 0

    @patch("services.balance_service.IS_SHEET_CONNECTED", False)
    def test_not_connected_raises(self):
        from services.balance_service import get_monthly_summary
        with pytest.raises(ConnectionError):
            get_monthly_summary("Ventas", 2026, 1)


class TestGetNetBalanceForMonth:
    """Tests for get_net_balance_for_month — the main balance calculation."""

    @patch("services.balance_service.get_wholesale_summary")
    @patch("services.balance_service.get_monthly_summary")
    def test_basic_balance_calculation(self, mock_summary, mock_wholesale):
        """Tests the core formula: saldo_pg = (sales + wholesale) - gastos_pg."""
        # Sales: 50000
        mock_summary.side_effect = [
            {"total": 50000.0, "count": 5, "by_category": {"REMERAS": 50000.0}},  # Sales
            {"total": 20000.0, "count": 3, "by_category": {"INSUMOS": 15000.0, "MARKETING": 5000.0}},  # Expenses (all PG)
        ]
        # Wholesale: 30000
        mock_wholesale.return_value = {"total": 30000.0, "count": 2, "by_client": {}}

        from services.balance_service import get_net_balance_for_month
        result = get_net_balance_for_month(2026, 1)

        # saldo_pg = (50000 + 30000) - 20000 = 60000
        assert result["saldo_pg"] == 60000.0
        assert result["sales_summary"]["total"] == 50000.0
        assert result["wholesale_summary"]["total"] == 30000.0
        assert result["gastos_pg_summary"]["total"] == 20000.0
        assert result["month_name"] == "Enero"
        assert result["year"] == 2026

    @patch("services.balance_service.get_wholesale_summary")
    @patch("services.balance_service.get_monthly_summary")
    def test_separates_personal_expenses(self, mock_summary, mock_wholesale):
        """Personal expenses are tracked separately from PG expenses."""
        mock_summary.side_effect = [
            {"total": 50000.0, "count": 5, "by_category": {"REMERAS": 50000.0}},  # Sales
            {"total": 30000.0, "count": 3, "by_category": {"INSUMOS": 10000.0, "PERSONALES": 20000.0}},  # Expenses
        ]
        mock_wholesale.return_value = {"total": 0.0, "count": 0, "by_client": {}}

        from services.balance_service import get_net_balance_for_month

        # Need to also mock the spreadsheet for the PERSONALES subcategory lookup
        with patch("services.balance_service.spreadsheet") as mock_ss:
            mock_ws = MagicMock()
            mock_ws.get_all_records.return_value = [
                {"Categoría": "PERSONALES", "Subcategoría": "ALQUILER", "Monto": 15000},
                {"Categoría": "PERSONALES", "Subcategoría": "LUZ", "Monto": 5000},
                {"Categoría": "INSUMOS", "Subcategoría": "GENERAL", "Monto": 10000},
            ]
            mock_ss.worksheet.return_value = mock_ws

            result = get_net_balance_for_month(2026, 1)

        # PG expenses = INSUMOS (10000), not PERSONALES
        assert result["gastos_pg_summary"]["total"] == 10000.0
        # saldo_pg = (50000 + 0) - 10000 = 40000
        assert result["saldo_pg"] == 40000.0

    @patch("services.balance_service.get_wholesale_summary")
    @patch("services.balance_service.get_monthly_summary")
    def test_zero_everything(self, mock_summary, mock_wholesale):
        """All zeros should produce a clean zero balance."""
        mock_summary.side_effect = [
            {"total": 0.0, "count": 0, "by_category": {}},
            {"total": 0.0, "count": 0, "by_category": {}},
        ]
        mock_wholesale.return_value = {"total": 0.0, "count": 0, "by_client": {}}

        from services.balance_service import get_net_balance_for_month
        result = get_net_balance_for_month(2026, 6)

        assert result["saldo_pg"] == 0.0
        assert result["saldo_neto"] == 0.0
        assert result["month_name"] == "Junio"
