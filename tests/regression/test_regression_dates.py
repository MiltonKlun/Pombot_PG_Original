import pytest
pytestmark = pytest.mark.regression

# tests/regression/test_regression_dates.py
"""
Regression tests for date handling and boundary conditions.
"""
from unittest.mock import patch, MagicMock
from services.balance_service import get_sheet_name_for_month
from services.checks_service import update_past_due_statuses
from datetime import datetime

class TestDateBoundaries:
    """Tests for month rollover and invalid dates."""

    def test_month_boundaries_naming(self):
        """Verify sheet naming for end/start of year."""
        assert get_sheet_name_for_month("Ventas", 2026, 1) == "Ventas Enero 2026"
        assert get_sheet_name_for_month("Ventas", 2026, 12) == "Ventas Diciembre 2026"
        assert get_sheet_name_for_month("Ventas", 2027, 1) == "Ventas Enero 2027"

    def test_invalid_month_number(self):
        """Invalid month returns fallback."""
        assert "MesInvalido" in get_sheet_name_for_month("Ventas", 2026, 13)


class TestInvalidDateHandling:
    """Tests robustness against bad date formats in scheduler."""

    @patch("services.checks_service._get_or_create_worksheet")
    def test_update_past_due_ignores_garbage_dates(self, mock_get_ws):
        mock_ws = MagicMock()
        # Row with garbage date
        mock_ws.get_all_records.return_value = [
            {"ID": "1", "Fecha Cobro": "not-a-date", "Estado": "Pendiente"},
            {"ID": "2", "Fecha Cobro": "32/01/2026", "Estado": "Pendiente"}, # Invalid day
            {"ID": "3", "Fecha Cobro": "01/13/2026", "Estado": "Pendiente"}, # Invalid month
        ]
        
        # Mock for checks and future payments sheets
        mock_get_ws.return_value = mock_ws

        # Should NOT raise exception
        update_past_due_statuses()

        # Should NOT verify calls, but ensuring it didn't crash is the test.
        # Calling update_cell suggests it tried to process it.
        # Logic says: try datetime.strptime... except ValueError: continue
        # So update_cell should NOT be called.
        mock_ws.update_cell.assert_not_called()
