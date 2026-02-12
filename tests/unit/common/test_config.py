import pytest
pytestmark = pytest.mark.unit

# tests/test_config.py
"""Unit tests for config.py — pure function tests only."""
from config import get_sheet_name_for_month, SPANISH_MONTHS


class TestGetSheetNameForMonth:
    """Tests for get_sheet_name_for_month — builds sheet tab names."""

    def test_january(self):
        assert get_sheet_name_for_month("Ventas", 2026, 1) == "Ventas Enero 2026"

    def test_december(self):
        assert get_sheet_name_for_month("Gastos", 2025, 12) == "Gastos Diciembre 2025"

    def test_wholesale(self):
        assert get_sheet_name_for_month("Mayoristas", 2026, 6) == "Mayoristas Junio 2026"

    def test_all_months_are_valid(self):
        """Every month 1-12 should produce a valid name, not 'MesInvalido'."""
        for month in range(1, 13):
            result = get_sheet_name_for_month("Ventas", 2026, month)
            assert "MesInvalido" not in result, f"Month {month} returned MesInvalido"

    def test_invalid_month_zero(self):
        result = get_sheet_name_for_month("Ventas", 2026, 0)
        assert "MesInvalido" in result

    def test_invalid_month_13(self):
        result = get_sheet_name_for_month("Ventas", 2026, 13)
        assert "MesInvalido" in result


class TestSpanishMonths:
    """Tests for the SPANISH_MONTHS dictionary."""

    def test_has_12_months(self):
        assert len(SPANISH_MONTHS) == 12

    def test_keys_are_1_to_12(self):
        assert set(SPANISH_MONTHS.keys()) == set(range(1, 13))

    def test_all_values_are_strings(self):
        for month_name in SPANISH_MONTHS.values():
            assert isinstance(month_name, str)
            assert len(month_name) > 0
