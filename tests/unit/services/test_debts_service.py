import pytest
pytestmark = pytest.mark.unit

# tests/test_debts_service.py
"""Unit tests for services/debts_service.py — Risk R3: debt payment correctness."""
from unittest.mock import patch, MagicMock


# The actual DEBTS_HEADERS from config.py
DEBTS_HEADERS = ["ID Deuda", "Nombre", "Monto Inicial", "Monto Pagado", "Saldo Pendiente",
                 "Estado", "Fecha Creación", "Fecha Ultimo Pago"]


class TestAddNewDebt:
    """Tests for add_new_debt — creates a debt row in the sheet."""

    @patch("services.debts_service.get_or_create_debts_sheet")
    def test_creates_debt_with_correct_fields(self, mock_get_sheet):
        mock_ws = MagicMock()
        mock_get_sheet.return_value = mock_ws

        from services.debts_service import add_new_debt
        result = add_new_debt("Proveedor X", 50000.0)

        mock_ws.append_row.assert_called_once()
        row = mock_ws.append_row.call_args[0][0]
        assert row[0].startswith("DEUDA-")  # auto-generated ID
        assert row[1] == "Proveedor X"       # name
        assert row[2] == 50000.0             # monto inicial
        assert row[3] == 0.0                 # monto pagado
        assert row[4] == 50000.0             # saldo pendiente = initial
        assert row[5] == "Activa"            # status
        assert result["Nombre"] == "Proveedor X"
        assert result["Saldo Pendiente"] == 50000.0

    @patch("services.debts_service.get_or_create_debts_sheet")
    def test_returns_none_on_no_sheet(self, mock_get_sheet):
        mock_get_sheet.return_value = None

        from services.debts_service import add_new_debt
        assert add_new_debt("Test", 1000.0) is None

    @patch("services.debts_service.get_or_create_debts_sheet")
    def test_returns_none_on_append_error(self, mock_get_sheet):
        mock_ws = MagicMock()
        mock_ws.append_row.side_effect = Exception("API error")
        mock_get_sheet.return_value = mock_ws

        from services.debts_service import add_new_debt
        assert add_new_debt("Test", 1000.0) is None


class TestGetActiveDebts:
    """Tests for get_active_debts — filters debts with pending balance > 0."""

    @patch("services.debts_service.get_or_create_debts_sheet")
    def test_filters_only_positive_balance(self, mock_get_sheet):
        mock_ws = MagicMock()
        mock_ws.get_all_records.return_value = [
            {"ID Deuda": "D1", "Nombre": "A", "Saldo Pendiente": 5000, "Estado": "Activa"},
            {"ID Deuda": "D2", "Nombre": "B", "Saldo Pendiente": 0, "Estado": "Saldada"},
            {"ID Deuda": "D3", "Nombre": "C", "Saldo Pendiente": 1000, "Estado": "Activa"},
        ]
        mock_get_sheet.return_value = mock_ws

        from services.debts_service import get_active_debts
        result = get_active_debts()

        assert len(result) == 2
        assert result[0]["ID Deuda"] == "D1"
        assert result[1]["ID Deuda"] == "D3"
        assert result[0]["row_number"] == 2
        assert result[1]["row_number"] == 4

    @patch("services.debts_service.get_or_create_debts_sheet")
    def test_returns_empty_on_no_sheet(self, mock_get_sheet):
        mock_get_sheet.return_value = None

        from services.debts_service import get_active_debts
        assert get_active_debts() == []

    @patch("services.debts_service.get_or_create_debts_sheet")
    def test_returns_empty_on_error(self, mock_get_sheet):
        mock_ws = MagicMock()
        mock_ws.get_all_records.side_effect = Exception("Network error")
        mock_get_sheet.return_value = mock_ws

        from services.debts_service import get_active_debts
        assert get_active_debts() == []


class TestRegisterDebtPayment:
    """Tests for register_debt_payment — updates payment columns using find_column_index."""

    def _setup_mock_sheet(self, mock_get_sheet, current_paid="10000", current_pending="40000"):
        """Sets up a mock sheet with proper headers for find_column_index."""
        mock_ws = MagicMock()
        mock_ws.find.return_value = MagicMock(row=3)
        mock_ws.row_values.side_effect = lambda row: {
            1: DEBTS_HEADERS,
            3: ["DEUDA-1", "Proveedor X", "50000", current_paid, current_pending,
                "Activa", "2026-01-01", "2026-01-01"],
        }[row]
        mock_get_sheet.return_value = mock_ws
        return mock_ws

    @patch("services.debts_service.get_or_create_debts_sheet")
    def test_partial_payment_keeps_activa(self, mock_get_sheet):
        mock_ws = self._setup_mock_sheet(mock_get_sheet, current_paid="10000", current_pending="40000")

        from services.debts_service import register_debt_payment
        result = register_debt_payment("DEUDA-1", 15000.0)

        # find_column_index finds: Monto Pagado=4, Saldo Pendiente=5, Estado=6, Fecha Ultimo Pago=8
        mock_ws.update_cell.assert_any_call(3, 4, 25000.0)   # paid
        mock_ws.update_cell.assert_any_call(3, 5, 25000.0)   # pending
        mock_ws.update_cell.assert_any_call(3, 6, "Activa")  # status
        assert result["Saldo Pendiente"] == 25000.0

    @patch("services.debts_service.get_or_create_debts_sheet")
    def test_full_payment_marks_saldada(self, mock_get_sheet):
        mock_ws = self._setup_mock_sheet(mock_get_sheet, current_paid="0", current_pending="50000")

        from services.debts_service import register_debt_payment
        result = register_debt_payment("DEUDA-1", 50000.0)

        mock_ws.update_cell.assert_any_call(3, 5, 0.0)         # pending = 0
        mock_ws.update_cell.assert_any_call(3, 6, "Saldada")   # status
        assert result["Saldo Pendiente"] == 0.0

    @patch("services.debts_service.get_or_create_debts_sheet")
    def test_returns_none_when_debt_not_found(self, mock_get_sheet):
        mock_ws = MagicMock()
        mock_ws.find.return_value = None
        mock_get_sheet.return_value = mock_ws

        from services.debts_service import register_debt_payment
        assert register_debt_payment("NONEXISTENT", 1000.0) is None

    @patch("services.debts_service.get_or_create_debts_sheet")
    def test_returns_none_on_no_sheet(self, mock_get_sheet):
        mock_get_sheet.return_value = None

        from services.debts_service import register_debt_payment
        assert register_debt_payment("DEUDA-1", 1000.0) is None


class TestIncreaseDebtAmount:
    """Tests for increase_debt_amount — adds to initial and pending."""

    @patch("services.debts_service.get_or_create_debts_sheet")
    def test_increases_both_initial_and_pending(self, mock_get_sheet):
        mock_ws = MagicMock()
        mock_ws.find.return_value = MagicMock(row=2)
        mock_ws.row_values.side_effect = lambda row: {
            1: DEBTS_HEADERS,
            2: ["DEUDA-1", "Vendor A", "50000", "10000", "40000", "Activa", "2026-01-01", "2026-01-01"],
        }[row]
        mock_get_sheet.return_value = mock_ws

        from services.debts_service import increase_debt_amount
        result = increase_debt_amount("DEUDA-1", 20000.0)

        # find_column_index: Monto Inicial=3, Saldo Pendiente=5, Estado=6
        mock_ws.update_cell.assert_any_call(2, 3, 70000.0)   # initial
        mock_ws.update_cell.assert_any_call(2, 5, 60000.0)   # pending
        mock_ws.update_cell.assert_any_call(2, 6, "Activa")  # status stays Activa
        assert result["Saldo Pendiente"] == 60000.0

    @patch("services.debts_service.get_or_create_debts_sheet")
    def test_returns_none_when_not_found(self, mock_get_sheet):
        mock_ws = MagicMock()
        mock_ws.find.return_value = None
        mock_get_sheet.return_value = mock_ws

        from services.debts_service import increase_debt_amount
        assert increase_debt_amount("NONEXISTENT", 5000.0) is None
