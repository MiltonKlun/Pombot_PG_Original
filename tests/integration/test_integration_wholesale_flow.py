import pytest
pytestmark = pytest.mark.integration

# tests/test_integration_wholesale_flow.py
"""
Integration tests for the wholesale flow:
Record Seña → modify payment → verify remaining → complete → verify PAGO.
"""
from unittest.mock import patch, MagicMock

from config import WHOLESALE_HEADERS


class TestWholesaleRecordAndModify:
    """Record a wholesale transaction, then apply payments."""

    @patch("services.wholesale_service.get_or_create_monthly_sheet")
    def test_record_seña_calculates_remaining(self, mock_sheet):
        """Seña record: remaining = total - paid."""
        mock_ws = MagicMock()
        mock_ws.title = "Mayoristas Enero 2026"
        mock_sheet.return_value = mock_ws

        from services.wholesale_service import add_wholesale_record
        result = add_wholesale_record(
            name="MayoristaX", product="Remera Pack", quantity=20,
            paid_amount=30000.0, total_amount=50000.0, category="Seña"
        )

        row = mock_ws.append_row.call_args[0][0]
        assert row[1] == "MayoristaX"
        assert row[4] == 50000.0    # Monto Total
        assert row[5] == 30000.0    # Monto Pagado
        assert row[6] == 20000.0    # Monto Restante = 50000 - 30000
        assert row[7] == "Seña"
        assert result["name"] == "MayoristaX"
        assert result["paid_amount"] == 30000.0

    @patch("services.wholesale_service.get_or_create_monthly_sheet")
    def test_partial_payment_reduces_remaining(self, mock_sheet):
        """Partial payment on seña reduces remaining balance."""
        mock_ws = MagicMock()
        mock_ws.title = "Mayoristas Enero 2026"
        # Setup cell reads for current paid/remaining
        paid_col = WHOLESALE_HEADERS.index("Monto Pagado") + 1
        remaining_col = WHOLESALE_HEADERS.index("Monto Restante") + 1

        def cell_reader(row, col):
            values = {paid_col: MagicMock(value="30000"), remaining_col: MagicMock(value="20000")}
            return values.get(col, MagicMock(value="0"))
        mock_ws.cell = cell_reader
        mock_sheet.return_value = mock_ws

        from services.wholesale_service import modify_wholesale_payment
        result = modify_wholesale_payment(row_number=5, payment_amount=10000.0)

        # New paid = 30000 + 10000 = 40000
        mock_ws.update_cell.assert_any_call(5, paid_col, 40000.0)
        # New remaining = 20000 - 10000 = 10000
        mock_ws.update_cell.assert_any_call(5, remaining_col, 10000.0)
        assert result["remaining_balance"] == 10000.0

    @patch("services.wholesale_service.get_or_create_monthly_sheet")
    def test_full_payment_marks_pago(self, mock_sheet):
        """Completing payment sets category to PAGO."""
        mock_ws = MagicMock()
        mock_ws.title = "Mayoristas Enero 2026"
        paid_col = WHOLESALE_HEADERS.index("Monto Pagado") + 1
        remaining_col = WHOLESALE_HEADERS.index("Monto Restante") + 1
        category_col = WHOLESALE_HEADERS.index("Categoría") + 1

        def cell_reader(row, col):
            values = {paid_col: MagicMock(value="30000"), remaining_col: MagicMock(value="20000")}
            return values.get(col, MagicMock(value="0"))
        mock_ws.cell = cell_reader
        mock_sheet.return_value = mock_ws

        from services.wholesale_service import modify_wholesale_payment
        result = modify_wholesale_payment(row_number=5, payment_amount=20000.0)

        # Remaining = 0 → category updated to PAGO
        mock_ws.update_cell.assert_any_call(5, remaining_col, 0.0)
        mock_ws.update_cell.assert_any_call(5, category_col, "PAGO")
        assert result["remaining_balance"] == 0.0

    @patch("services.wholesale_service.get_or_create_monthly_sheet")
    def test_overpayment_returns_error(self, mock_sheet):
        """Payment exceeding remaining returns error dict."""
        mock_ws = MagicMock()
        paid_col = WHOLESALE_HEADERS.index("Monto Pagado") + 1
        remaining_col = WHOLESALE_HEADERS.index("Monto Restante") + 1

        def cell_reader(row, col):
            values = {paid_col: MagicMock(value="30000"), remaining_col: MagicMock(value="5000")}
            return values.get(col, MagicMock(value="0"))
        mock_ws.cell = cell_reader
        mock_sheet.return_value = mock_ws

        from services.wholesale_service import modify_wholesale_payment
        result = modify_wholesale_payment(row_number=5, payment_amount=10000.0)

        assert "error" in result


class TestWholesalePendingPayments:
    """get_pending_wholesale_payments filters by Seña category."""

    @patch("services.sheets_connection.spreadsheet")
    def test_returns_only_seña_records(self, mock_spreadsheet):
        mock_ws = MagicMock()
        mock_ws.get_all_records.return_value = [
            {"Nombre": "A", "Categoría": "Seña", "Monto Restante": "5000"},
            {"Nombre": "B", "Categoría": "PAGO", "Monto Restante": "0"},
            {"Nombre": "C", "Categoría": "Seña", "Monto Restante": "3000"},
        ]
        mock_spreadsheet.worksheet.return_value = mock_ws

        from services.wholesale_service import get_pending_wholesale_payments
        pending = get_pending_wholesale_payments(2026, 1)

        assert len(pending) == 2
        assert all(p.get("Categoría") == "Seña" for p in pending)
        assert pending[0]["row_number"] == 2
        assert pending[1]["row_number"] == 4


class TestWholesaleSummary:
    """get_wholesale_summary aggregates totals by client."""

    @patch("services.sheets_connection.IS_SHEET_CONNECTED", True)
    @patch("services.sheets_connection.spreadsheet")
    def test_summary_aggregates_by_client(self, mock_spreadsheet):
        mock_ws = MagicMock()
        mock_ws.get_all_records.return_value = [
            {"Nombre": "ClienteA", "Producto": "Remera", "Cantidad": 10, "Monto Pagado": 50000},
            {"Nombre": "ClienteA", "Producto": "Pantalón", "Cantidad": 5, "Monto Pagado": 30000},
            {"Nombre": "ClienteB", "Producto": "Remera", "Cantidad": 2, "Monto Pagado": 10000},
        ]
        mock_spreadsheet.worksheet.return_value = mock_ws

        from services.wholesale_service import get_wholesale_summary
        summary = get_wholesale_summary(2026, 1)

        assert summary["total"] == 90000.0
        assert summary["count"] == 3
        assert summary["by_client"]["ClienteA"]["amount"] == 80000.0
        assert summary["by_client"]["ClienteA"]["quantity"] == 15
        assert summary["by_client"]["ClienteB"]["amount"] == 10000.0
        assert len(summary["details"]) == 3
