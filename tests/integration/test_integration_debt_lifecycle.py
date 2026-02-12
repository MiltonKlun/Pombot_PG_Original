import pytest
pytestmark = pytest.mark.integration

# tests/test_integration_debt_lifecycle.py
"""
Integration tests for the full debt lifecycle:
Create → partial pay → verify Activa → pay remainder → verify Saldada.
Create → increase → pay all.
"""
from unittest.mock import patch, MagicMock

DEBTS_HEADERS = [
    "ID Deuda", "Nombre", "Monto Inicial", "Monto Pagado",
    "Saldo Pendiente", "Estado", "Fecha Creación", "Fecha Último Pago"
]


class TestDebtCreateAndPayLifecycle:
    """Create a debt, make partial payment, then full payment."""

    @patch("services.debts_service.get_or_create_debts_sheet")
    def test_create_sets_initial_balance(self, mock_get_sheet):
        """New debt: Saldo Pendiente == Monto Inicial, Estado == Activa."""
        mock_ws = MagicMock()
        mock_get_sheet.return_value = mock_ws

        from services.debts_service import add_new_debt
        result = add_new_debt("Proveedor Z", 100000.0)

        row = mock_ws.append_row.call_args[0][0]
        assert row[2] == 100000.0    # Monto Inicial
        assert row[3] == 0.0         # Monto Pagado
        assert row[4] == 100000.0    # Saldo Pendiente
        assert row[5] == "Activa"
        assert result["Saldo Pendiente"] == 100000.0

    @patch("services.debts_service.get_or_create_debts_sheet")
    def test_partial_payment_keeps_active(self, mock_get_sheet):
        """After partial payment, status stays Activa with updated balance."""
        mock_ws = MagicMock()
        mock_ws.find.return_value = MagicMock(row=3)
        mock_ws.row_values.side_effect = lambda r: {
            1: DEBTS_HEADERS,
            3: ["DEUDA-1", "Proveedor Z", "100000", "0", "100000",
                "Activa", "2026-01-01", "2026-01-01"],
        }[r]
        mock_get_sheet.return_value = mock_ws

        from services.debts_service import register_debt_payment
        result = register_debt_payment("DEUDA-1", 30000.0)

        # Verify updated cells
        mock_ws.update_cell.assert_any_call(3, 4, 30000.0)    # paid
        mock_ws.update_cell.assert_any_call(3, 5, 70000.0)    # pending
        mock_ws.update_cell.assert_any_call(3, 6, "Activa")   # still active
        assert result["Saldo Pendiente"] == 70000.0

    @patch("services.debts_service.get_or_create_debts_sheet")
    def test_final_payment_marks_saldada(self, mock_get_sheet):
        """Paying remaining balance sets status to Saldada."""
        mock_ws = MagicMock()
        mock_ws.find.return_value = MagicMock(row=3)
        mock_ws.row_values.side_effect = lambda r: {
            1: DEBTS_HEADERS,
            3: ["DEUDA-1", "Proveedor Z", "100000", "30000", "70000",
                "Activa", "2026-01-01", "2026-01-15"],
        }[r]
        mock_get_sheet.return_value = mock_ws

        from services.debts_service import register_debt_payment
        result = register_debt_payment("DEUDA-1", 70000.0)

        mock_ws.update_cell.assert_any_call(3, 4, 100000.0)   # fully paid
        mock_ws.update_cell.assert_any_call(3, 5, 0.0)        # no pending
        mock_ws.update_cell.assert_any_call(3, 6, "Saldada")
        assert result["Saldo Pendiente"] == 0.0


class TestDebtIncreaseAndPayLifecycle:
    """Create → increase amount → pay all."""

    @patch("services.debts_service.get_or_create_debts_sheet")
    def test_increase_adds_to_both_initial_and_pending(self, mock_get_sheet):
        """increase_debt_amount adds to Monto Inicial and Saldo Pendiente."""
        mock_ws = MagicMock()
        mock_ws.find.return_value = MagicMock(row=2)
        mock_ws.row_values.side_effect = lambda r: {
            1: DEBTS_HEADERS,
            2: ["DEUDA-1", "Vendor A", "50000", "10000", "40000",
                "Activa", "2026-01-01", "2026-01-01"],
        }[r]
        mock_get_sheet.return_value = mock_ws

        from services.debts_service import increase_debt_amount
        result = increase_debt_amount("DEUDA-1", 20000.0)

        mock_ws.update_cell.assert_any_call(2, 3, 70000.0)    # initial increased
        mock_ws.update_cell.assert_any_call(2, 5, 60000.0)    # pending increased
        assert result["Saldo Pendiente"] == 60000.0

    @patch("services.debts_service.get_or_create_debts_sheet")
    def test_pay_full_after_increase(self, mock_get_sheet):
        """After increase, paying full new balance sets Saldada."""
        mock_ws = MagicMock()
        mock_ws.find.return_value = MagicMock(row=2)
        mock_ws.row_values.side_effect = lambda r: {
            1: DEBTS_HEADERS,
            2: ["DEUDA-1", "Vendor A", "70000", "10000", "60000",
                "Activa", "2026-01-01", "2026-01-15"],
        }[r]
        mock_get_sheet.return_value = mock_ws

        from services.debts_service import register_debt_payment
        result = register_debt_payment("DEUDA-1", 60000.0)

        mock_ws.update_cell.assert_any_call(2, 5, 0.0)
        mock_ws.update_cell.assert_any_call(2, 6, "Saldada")
        assert result["Saldo Pendiente"] == 0.0


class TestGetActiveDebtsFiltering:
    """get_active_debts correctly filters by pending balance."""

    @patch("services.debts_service.get_or_create_debts_sheet")
    def test_returns_only_active(self, mock_get_sheet):
        mock_ws = MagicMock()
        mock_ws.get_all_records.return_value = [
            {"ID Deuda": "D1", "Nombre": "A", "Saldo Pendiente": 5000, "Estado": "Activa"},
            {"ID Deuda": "D2", "Nombre": "B", "Saldo Pendiente": 0, "Estado": "Saldada"},
            {"ID Deuda": "D3", "Nombre": "C", "Saldo Pendiente": 1000, "Estado": "Activa"},
        ]
        mock_get_sheet.return_value = mock_ws

        from services.debts_service import get_active_debts
        active = get_active_debts()

        assert len(active) == 2
        assert all(d["Saldo Pendiente"] > 0 for d in active)
        # Row numbers are 2-indexed (header is row 1)
        assert active[0]["row_number"] == 2
        assert active[1]["row_number"] == 4
