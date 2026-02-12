import pytest
pytestmark = pytest.mark.integration

# tests/test_integration_scheduler.py
"""
Integration tests for the scheduling helpers in checks_service:
- update_past_due_statuses: marks overdue items as PAGO
- get_items_due_in_x_days: finds items due within N days
- get_items_due_today: finds items due today with PAGO status
"""
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from config import CHECKS_HEADERS, FUTURE_PAYMENTS_HEADERS


class TestUpdatePastDueStatuses:
    """update_past_due_statuses — auto-marks overdue Pendiente items as PAGO."""

    @patch("services.checks_service._get_or_create_worksheet")
    def test_marks_past_due_checks_as_pago(self, mock_get_ws):
        """Checks with due date in the past get status updated to PAGO."""
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%d/%m/%Y")
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%d/%m/%Y")

        mock_checks_ws = MagicMock()
        mock_checks_ws.get_all_records.return_value = [
            {"ID": "CHK-1", "Fecha Cobro": yesterday, "Estado": "Pendiente"},
            {"ID": "CHK-2", "Fecha Cobro": tomorrow, "Estado": "Pendiente"},
        ]
        mock_fp_ws = MagicMock()
        mock_fp_ws.get_all_records.return_value = []

        mock_get_ws.side_effect = lambda name, headers: (
            mock_checks_ws if name == "Cheques" else mock_fp_ws
        )

        from services.checks_service import update_past_due_statuses
        update_past_due_statuses()

        # Only CHK-1 (yesterday) should be updated
        status_col = CHECKS_HEADERS.index("Estado") + 1
        mock_checks_ws.update_cell.assert_called_once_with(2, status_col, "PAGO")

    @patch("services.checks_service._get_or_create_worksheet")
    def test_marks_past_due_future_payments(self, mock_get_ws):
        """Future payments with due date in the past get status updated to PAGO."""
        last_week = (datetime.now() - timedelta(days=7)).strftime("%d/%m/%Y")

        mock_checks_ws = MagicMock()
        mock_checks_ws.get_all_records.return_value = []

        mock_fp_ws = MagicMock()
        mock_fp_ws.get_all_records.return_value = [
            {"ID": "FP-1", "Fecha Cobro": last_week, "Estado": "Pendiente"},
        ]

        mock_get_ws.side_effect = lambda name, headers: (
            mock_checks_ws if name == "Cheques" else mock_fp_ws
        )

        from services.checks_service import update_past_due_statuses
        update_past_due_statuses()

        fp_status_col = FUTURE_PAYMENTS_HEADERS.index("Estado") + 1
        mock_fp_ws.update_cell.assert_called_once_with(2, fp_status_col, "PAGO")

    @patch("services.checks_service._get_or_create_worksheet")
    def test_skips_already_pago_items(self, mock_get_ws):
        """Items already marked PAGO should not be updated again."""
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%d/%m/%Y")

        mock_checks_ws = MagicMock()
        mock_checks_ws.get_all_records.return_value = [
            {"ID": "CHK-1", "Fecha Cobro": yesterday, "Estado": "PAGO"},
        ]
        mock_fp_ws = MagicMock()
        mock_fp_ws.get_all_records.return_value = []

        mock_get_ws.side_effect = lambda name, headers: (
            mock_checks_ws if name == "Cheques" else mock_fp_ws
        )

        from services.checks_service import update_past_due_statuses
        update_past_due_statuses()

        mock_checks_ws.update_cell.assert_not_called()

    @patch("services.checks_service._get_or_create_worksheet")
    def test_handles_bad_date_format(self, mock_get_ws):
        """Bad date format should be skipped without crashing."""
        mock_checks_ws = MagicMock()
        mock_checks_ws.get_all_records.return_value = [
            {"ID": "CHK-1", "Fecha Cobro": "invalid-date", "Estado": "Pendiente"},
        ]
        mock_fp_ws = MagicMock()
        mock_fp_ws.get_all_records.return_value = []

        mock_get_ws.side_effect = lambda name, headers: (
            mock_checks_ws if name == "Cheques" else mock_fp_ws
        )

        from services.checks_service import update_past_due_statuses
        # Should not raise
        update_past_due_statuses()
        mock_checks_ws.update_cell.assert_not_called()


class TestGetItemsDueInXDays:
    """get_items_due_in_x_days — finds items due within a date range."""

    @patch("services.checks_service._get_or_create_worksheet")
    def test_finds_check_due_tomorrow(self, mock_get_ws):
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%d/%m/%Y")
        next_week = (datetime.now() + timedelta(days=7)).strftime("%d/%m/%Y")

        mock_checks_ws = MagicMock()
        mock_checks_ws.get_all_records.return_value = [
            {"ID": "CHK-1", "Fecha Cobro": tomorrow, "Estado": "Pendiente"},
            {"ID": "CHK-2", "Fecha Cobro": next_week, "Estado": "Pendiente"},
        ]
        mock_fp_ws = MagicMock()
        mock_fp_ws.get_all_records.return_value = []

        mock_get_ws.side_effect = lambda name, headers: (
            mock_checks_ws if name == "Cheques" else mock_fp_ws
        )

        from services.checks_service import get_items_due_in_x_days
        result = get_items_due_in_x_days(1)

        assert len(result["cheques"]) == 1
        assert result["cheques"][0]["ID"] == "CHK-1"
        assert len(result["pagos_futuros"]) == 0

    @patch("services.checks_service._get_or_create_worksheet")
    def test_finds_future_payment_due_today(self, mock_get_ws):
        today = datetime.now().strftime("%d/%m/%Y")

        mock_checks_ws = MagicMock()
        mock_checks_ws.get_all_records.return_value = []
        mock_fp_ws = MagicMock()
        mock_fp_ws.get_all_records.return_value = [
            {"ID": "FP-1", "Fecha Cobro": today, "Estado": "Pendiente"},
        ]

        mock_get_ws.side_effect = lambda name, headers: (
            mock_checks_ws if name == "Cheques" else mock_fp_ws
        )

        from services.checks_service import get_items_due_in_x_days
        result = get_items_due_in_x_days(0)

        assert len(result["pagos_futuros"]) == 1
        assert result["pagos_futuros"][0]["ID"] == "FP-1"

    @patch("services.checks_service._get_or_create_worksheet")
    def test_empty_when_nothing_due(self, mock_get_ws):
        far_future = (datetime.now() + timedelta(days=365)).strftime("%d/%m/%Y")

        mock_checks_ws = MagicMock()
        mock_checks_ws.get_all_records.return_value = [
            {"ID": "CHK-1", "Fecha Cobro": far_future, "Estado": "Pendiente"},
        ]
        mock_fp_ws = MagicMock()
        mock_fp_ws.get_all_records.return_value = []

        mock_get_ws.side_effect = lambda name, headers: (
            mock_checks_ws if name == "Cheques" else mock_fp_ws
        )

        from services.checks_service import get_items_due_in_x_days
        result = get_items_due_in_x_days(1)

        assert len(result["cheques"]) == 0
        assert len(result["pagos_futuros"]) == 0
