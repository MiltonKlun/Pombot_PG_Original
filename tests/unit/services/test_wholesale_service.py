import pytest
pytestmark = pytest.mark.unit

# tests/test_wholesale_service.py
"""Unit tests for services/wholesale_service.py — Risk R8: wholesale seña/payment correctness."""
from unittest.mock import patch, MagicMock
from collections import defaultdict


class TestAddWholesaleRecord:
    """Tests for add_wholesale_record — records a wholesale transaction."""

    @patch("services.wholesale_service.get_or_create_monthly_sheet", autospec=True)
    def test_calculates_remaining_amount(self, mock_get_sheet):
        mock_ws = MagicMock()
        mock_ws.title = "Mayoristas Enero 2026"
        mock_get_sheet.return_value = mock_ws

        from services.wholesale_service import add_wholesale_record
        result = add_wholesale_record(
            name="Mayorista A",
            product="Remeras",
            quantity=10,
            paid_amount=30000.0,
            total_amount=50000.0,
            category="Seña"
        )

        mock_ws.append_row.assert_called_once()
        row = mock_ws.append_row.call_args[0][0]
        assert row[1] == "Mayorista A"
        assert row[4] == 50000.0     # total
        assert row[5] == 30000.0     # paid
        assert row[6] == 20000.0     # remaining = 50000 - 30000
        assert row[7] == "Seña"
        assert result["name"] == "Mayorista A"
        assert result["paid_amount"] == 30000.0

    @patch("services.wholesale_service.get_or_create_monthly_sheet", autospec=True)
    def test_full_payment_has_zero_remaining(self, mock_get_sheet):
        mock_ws = MagicMock()
        mock_ws.title = "Mayoristas Enero 2026"
        mock_get_sheet.return_value = mock_ws

        from services.wholesale_service import add_wholesale_record
        add_wholesale_record("B", "Pants", 5, 25000.0, 25000.0, "PAGO")

        row = mock_ws.append_row.call_args[0][0]
        assert row[6] == 0.0  # remaining = 0

    @patch("services.wholesale_service.get_or_create_monthly_sheet", autospec=True)
    def test_returns_none_on_no_sheet(self, mock_get_sheet):
        mock_get_sheet.return_value = None

        from services.wholesale_service import add_wholesale_record
        assert add_wholesale_record("A", "X", 1, 1000, 2000, "Seña") is None

    @patch("services.wholesale_service.get_or_create_monthly_sheet", autospec=True)
    def test_returns_none_on_append_error(self, mock_get_sheet):
        mock_ws = MagicMock()
        mock_ws.append_row.side_effect = Exception("API error")
        mock_get_sheet.return_value = mock_ws

        from services.wholesale_service import add_wholesale_record
        assert add_wholesale_record("A", "X", 1, 1000, 2000, "Seña") is None


class TestGetPendingWholesalePayments:
    """Tests for get_pending_wholesale_payments — filters 'Seña' records."""

    @patch("services.wholesale_service.get_spreadsheet")
    def test_filters_only_sena_records(self, mock_get_spreadsheet):
        mock_spreadsheet = MagicMock()
        mock_get_spreadsheet.return_value = mock_spreadsheet
        mock_ws = MagicMock()
        mock_ws.get_all_records.return_value = [
            {"Nombre": "A", "Categoría": "Seña", "Monto Restante": 5000},
            {"Nombre": "B", "Categoría": "PAGO", "Monto Restante": 0},
            {"Nombre": "C", "Categoría": "Seña", "Monto Restante": 10000},
        ]
        mock_spreadsheet.worksheet.return_value = mock_ws

        from services.wholesale_service import get_pending_wholesale_payments
        result = get_pending_wholesale_payments(2026, 1)

        assert len(result) == 2
        assert result[0]["Nombre"] == "A"
        assert result[0]["row_number"] == 2  # header=1, first record=2
        assert result[1]["Nombre"] == "C"
        assert result[1]["row_number"] == 4

    @patch("services.wholesale_service.get_spreadsheet")
    def test_returns_empty_on_missing_sheet(self, mock_get_spreadsheet):
        mock_spreadsheet = MagicMock()
        mock_get_spreadsheet.return_value = mock_spreadsheet
        mock_spreadsheet.worksheet.side_effect = Exception("NotFound")

        from services.wholesale_service import get_pending_wholesale_payments
        assert get_pending_wholesale_payments(2026, 1) == []


class TestModifyWholesalePayment:
    """Tests for modify_wholesale_payment — applies payment to existing seña."""

    @patch("services.wholesale_service.get_or_create_monthly_sheet", autospec=True)
    def test_partial_payment_updates_amounts(self, mock_get_sheet):
        mock_ws = MagicMock()
        # WHOLESALE_HEADERS = ["Fecha", "Nombre", "Producto", "Cantidad", "Monto Total", "Monto Pagado", "Monto Restante", "Categoría"]
        mock_ws.cell.side_effect = lambda row, col: MagicMock(value={
            6: "10000",   # paid
            7: "40000",   # remaining
        }[col])
        mock_get_sheet.return_value = mock_ws

        from services.wholesale_service import modify_wholesale_payment
        result = modify_wholesale_payment(row_number=3, payment_amount=15000.0)

        # new_paid = 10000 + 15000 = 25000, new_remaining = 40000 - 15000 = 25000
        mock_ws.update_cell.assert_any_call(3, 6, 25000.0)  # paid
        mock_ws.update_cell.assert_any_call(3, 7, 25000.0)  # remaining
        assert result["remaining_balance"] == 25000.0

    @patch("services.wholesale_service.get_or_create_monthly_sheet", autospec=True)
    def test_full_payment_changes_to_pago(self, mock_get_sheet):
        mock_ws = MagicMock()
        mock_ws.cell.side_effect = lambda row, col: MagicMock(value={
            6: "30000",   # paid
            7: "20000",   # remaining
        }[col])
        mock_get_sheet.return_value = mock_ws

        from services.wholesale_service import modify_wholesale_payment
        result = modify_wholesale_payment(row_number=3, payment_amount=20000.0)

        # new_remaining = 0
        mock_ws.update_cell.assert_any_call(3, 8, "PAGO")  # category
        assert result["remaining_balance"] == 0.0

    @patch("services.wholesale_service.get_or_create_monthly_sheet", autospec=True)
    def test_rejects_overpayment(self, mock_get_sheet):
        mock_ws = MagicMock()
        mock_ws.cell.side_effect = lambda row, col: MagicMock(value={
            6: "0",       # paid
            7: "10000",   # remaining
        }[col])
        mock_get_sheet.return_value = mock_ws

        from services.wholesale_service import modify_wholesale_payment
        result = modify_wholesale_payment(row_number=3, payment_amount=15000.0)

        assert "error" in result
        mock_ws.update_cell.assert_not_called()

    @patch("services.wholesale_service.get_or_create_monthly_sheet", autospec=True)
    def test_returns_none_on_no_sheet(self, mock_get_sheet):
        mock_get_sheet.return_value = None

        from services.wholesale_service import modify_wholesale_payment
        assert modify_wholesale_payment(3, 1000.0) is None


class TestGetWholesaleSummary:
    """Tests for get_wholesale_summary — aggregates by client with details."""

    @patch("services.wholesale_service.is_connected", return_value=True)
    @patch("services.wholesale_service.get_spreadsheet")
    def test_aggregates_by_client(self, mock_get_spreadsheet, mock_is_connected):
        mock_spreadsheet = MagicMock()
        mock_get_spreadsheet.return_value = mock_spreadsheet
        mock_ws = MagicMock()
        mock_ws.get_all_records.return_value = [
            {"Nombre": "ClienteA", "Producto": "Remeras", "Cantidad": 10, "Monto Pagado": 50000, "Categoría": "PAGO"},
            {"Nombre": "ClienteA", "Producto": "Pantalones", "Cantidad": 5, "Monto Pagado": 30000, "Categoría": "PAGO"},
            {"Nombre": "ClienteB", "Producto": "Buzos", "Cantidad": 3, "Monto Pagado": 20000, "Categoría": "PAGO"},
        ]
        mock_spreadsheet.worksheet.return_value = mock_ws

        from services.wholesale_service import get_wholesale_summary
        result = get_wholesale_summary(2026, 1)

        assert result["total"] == 100000.0
        assert result["count"] == 3
        assert result["by_client"]["ClienteA"]["amount"] == 80000.0
        assert result["by_client"]["ClienteA"]["quantity"] == 15
        assert result["by_client"]["ClienteB"]["amount"] == 20000.0
        assert len(result["details"]) == 3

    @patch("services.wholesale_service.is_connected", return_value=True)
    @patch("services.wholesale_service.get_spreadsheet")
    def test_returns_zeros_on_missing_sheet(self, mock_get_spreadsheet, mock_is_connected):
        mock_spreadsheet = MagicMock()
        mock_get_spreadsheet.return_value = mock_spreadsheet
        mock_spreadsheet.worksheet.side_effect = Exception("NotFound")

        from services.wholesale_service import get_wholesale_summary
        result = get_wholesale_summary(2026, 1)

        assert result["total"] == 0.0
        assert result["count"] == 0
        assert result["by_client"] == {}
        assert result["details"] == []

    @patch("services.wholesale_service.is_connected", return_value=False)
    def test_raises_on_no_connection(self, mock_is_connected):
        from services.wholesale_service import get_wholesale_summary
        with pytest.raises(ConnectionError):
            get_wholesale_summary(2026, 1)
