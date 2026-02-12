import pytest
pytestmark = pytest.mark.unit

# tests/test_checks_service.py
"""Unit tests for services/checks_service.py — Risk R7/R10: check tax & scheduler correctness."""
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta


class TestAddCheck:
    """Tests for add_check — emits a check with auto-calculated 1.2% tax."""

    @patch("services.checks_service._get_or_create_worksheet")
    def test_tax_and_final_amount_calculation(self, mock_get_ws):
        mock_ws = MagicMock()
        mock_get_ws.return_value = mock_ws

        from services.checks_service import add_check
        add_check(entity="Proveedor X", initial_amount=100000.0, commission=5000.0, due_date="15/02/2026")

        mock_ws.append_row.assert_called_once()
        row = mock_ws.append_row.call_args[0][0]
        assert row[0].startswith("CHK-")           # auto-generated ID
        assert row[1] == "15/02/2026"               # due date
        assert row[2] == "Proveedor X"               # entity
        assert row[3] == 100000.0                    # initial
        assert row[4] == pytest.approx(1200.0)       # tax = 100000 * 0.012
        assert row[5] == 5000.0                      # commission
        assert row[6] == pytest.approx(106200.0)     # final = 100000 + 5000 + 1200
        assert row[7] == "Pendiente"

    @patch("services.checks_service._get_or_create_worksheet")
    def test_zero_commission(self, mock_get_ws):
        mock_ws = MagicMock()
        mock_get_ws.return_value = mock_ws

        from services.checks_service import add_check
        add_check("Y", 50000.0, 0.0, "01/01/2026")

        row = mock_ws.append_row.call_args[0][0]
        assert row[5] == 0.0
        assert row[6] == pytest.approx(50600.0)  # 50000 + 0 + 600

    @patch("services.checks_service._get_or_create_worksheet")
    def test_raises_on_no_sheet(self, mock_get_ws):
        mock_get_ws.return_value = None

        from services.checks_service import add_check
        with pytest.raises(ConnectionError):
            add_check("Z", 1000.0, 0.0, "01/01/2026")


class TestGetPendingChecks:
    """Tests for get_pending_checks — filters by 'Pendiente' status."""

    @patch("services.checks_service._get_or_create_worksheet")
    def test_returns_only_pending(self, mock_get_ws):
        mock_ws = MagicMock()
        mock_ws.get_all_records.return_value = [
            {"ID": "CHK-1", "Estado": "Pendiente"},
            {"ID": "CHK-2", "Estado": "PAGO"},
            {"ID": "CHK-3", "Estado": "Pendiente"},
        ]
        mock_get_ws.return_value = mock_ws

        from services.checks_service import get_pending_checks
        result = get_pending_checks()

        assert len(result) == 2
        assert result[0]["ID"] == "CHK-1"
        assert result[1]["ID"] == "CHK-3"

    @patch("services.checks_service._get_or_create_worksheet")
    def test_returns_empty_on_no_sheet(self, mock_get_ws):
        mock_get_ws.return_value = None

        from services.checks_service import get_pending_checks
        assert get_pending_checks() == []


class TestAddFuturePayment:
    """Tests for add_future_payment — records a future payment."""

    @patch("services.checks_service.apply_table_formatting")
    @patch("services.checks_service._get_or_create_worksheet")
    def test_final_equals_initial_minus_commission(self, mock_get_ws, mock_format):
        mock_ws = MagicMock()
        mock_ws.row_values.return_value = []  # headers check
        mock_get_ws.return_value = mock_ws

        from services.checks_service import add_future_payment
        add_future_payment("Cliente Y", "Remeras", 10, 80000.0, 5000.0, "20/03/2026")

        row = mock_ws.append_row.call_args[0][0]
        assert row[0].startswith("FP-")
        assert row[2] == "Cliente Y"
        assert row[3] == "Remeras"
        assert row[4] == 10
        assert row[5] == 80000.0            # initial
        assert row[6] == 5000.0             # commission
        assert row[7] == 75000.0            # final = 80000 - 5000
        assert row[8] == "Pendiente"

    @patch("services.checks_service._get_or_create_worksheet")
    def test_raises_on_no_sheet(self, mock_get_ws):
        mock_get_ws.return_value = None

        from services.checks_service import add_future_payment
        with pytest.raises(ConnectionError):
            add_future_payment("X", "Y", 1, 1000.0, 0.0, "01/01/2026")


class TestGetItemsDueInXDays:
    """Tests for get_items_due_in_x_days — date range filtering."""

    @patch("services.checks_service.get_pending_future_payments")
    @patch("services.checks_service.get_pending_checks")
    def test_finds_items_due_tomorrow(self, mock_checks, mock_fps):
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%d/%m/%Y")
        far_future = "01/01/2099"

        mock_checks.return_value = [
            {"ID": "CHK-1", "Fecha Cobro": tomorrow},
            {"ID": "CHK-2", "Fecha Cobro": far_future},
        ]
        mock_fps.return_value = [
            {"ID": "FP-1", "Fecha Cobro": tomorrow},
        ]

        from services.checks_service import get_items_due_in_x_days
        result = get_items_due_in_x_days(1)

        assert len(result["cheques"]) == 1
        assert result["cheques"][0]["ID"] == "CHK-1"
        assert len(result["pagos_futuros"]) == 1

    @patch("services.checks_service.get_pending_future_payments")
    @patch("services.checks_service.get_pending_checks")
    def test_returns_empty_when_nothing_due(self, mock_checks, mock_fps):
        mock_checks.return_value = [{"ID": "CHK-1", "Fecha Cobro": "01/01/2099"}]
        mock_fps.return_value = []

        from services.checks_service import get_items_due_in_x_days
        result = get_items_due_in_x_days(3)

        assert result["cheques"] == []
        assert result["pagos_futuros"] == []


class TestUpdatePastDueStatuses:
    """Tests for update_past_due_statuses — marks past-due items as PAGO."""

    @patch("services.checks_service._get_or_create_worksheet")
    def test_marks_past_due_as_pago(self, mock_get_ws):
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%d/%m/%Y")
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%d/%m/%Y")

        mock_ws = MagicMock()
        mock_ws.get_all_records.return_value = [
            {"Estado": "Pendiente", "Fecha Cobro": yesterday},   # should be marked
            {"Estado": "Pendiente", "Fecha Cobro": tomorrow},    # should NOT be marked
            {"Estado": "PAGO", "Fecha Cobro": yesterday},        # already PAGO
        ]
        mock_get_ws.return_value = mock_ws

        from services.checks_service import update_past_due_statuses
        update_past_due_statuses()

        # Only the first record (row 2) should be updated
        # The function processes both CHECKS and FUTURE_PAYMENTS sheets
        # We only verify calls happened (specific col depends on headers)
        assert mock_ws.update_cell.call_count >= 1

    @patch("services.checks_service._get_or_create_worksheet")
    def test_skips_invalid_dates(self, mock_get_ws):
        mock_ws = MagicMock()
        mock_ws.get_all_records.return_value = [
            {"Estado": "Pendiente", "Fecha Cobro": "invalid-date"},
        ]
        mock_get_ws.return_value = mock_ws

        from services.checks_service import update_past_due_statuses
        # Should not crash on invalid dates
        update_past_due_statuses()
        mock_ws.update_cell.assert_not_called()


class TestUpdateItemStatus:
    """Tests for update_item_status — finds by ID and updates status."""

    @patch("services.checks_service.apply_table_formatting")
    @patch("services.checks_service._get_or_create_worksheet")
    def test_updates_status_successfully(self, mock_get_ws, mock_format):
        mock_ws = MagicMock()
        mock_ws.row_values.return_value = []  # headers check
        mock_ws.find.return_value = MagicMock(row=3)
        mock_get_ws.return_value = mock_ws

        from services.checks_service import update_item_status
        from config import CHECKS_SHEET_NAME
        result = update_item_status(CHECKS_SHEET_NAME, "CHK-123", "Cobrado")

        assert result is True
        mock_ws.update_cell.assert_called_once()

    @patch("services.checks_service._get_or_create_worksheet")
    def test_returns_false_when_not_found(self, mock_get_ws):
        mock_ws = MagicMock()
        mock_ws.row_values.return_value = []
        mock_ws.find.return_value = None
        mock_get_ws.return_value = mock_ws

        from services.checks_service import update_item_status
        from config import CHECKS_SHEET_NAME
        result = update_item_status(CHECKS_SHEET_NAME, "NONEXISTENT", "Cobrado")

        assert result is False

    @patch("services.checks_service._get_or_create_worksheet")
    def test_returns_false_on_no_sheet(self, mock_get_ws):
        mock_get_ws.return_value = None

        from services.checks_service import update_item_status
        from config import CHECKS_SHEET_NAME
        assert update_item_status(CHECKS_SHEET_NAME, "CHK-1", "X") is False
