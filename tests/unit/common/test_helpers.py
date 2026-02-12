import pytest
pytestmark = pytest.mark.unit

# tests/test_helpers.py
"""Unit tests for shared helpers in sheets_connection.py."""
from services.sheets_connection import find_column_index, safe_row_value


# ── find_column_index ────────────────────────────────────────

class TestFindColumnIndex:
    """Tests for find_column_index — header lookup with accent normalization."""

    SAMPLE_HEADERS = ["Fecha", "Nombre", "Monto Total", "Categoría", "Estado"]

    def test_exact_match(self):
        assert find_column_index(self.SAMPLE_HEADERS, "Nombre") == 2

    def test_returns_1_based_index(self):
        assert find_column_index(self.SAMPLE_HEADERS, "Fecha") == 1

    def test_last_column(self):
        assert find_column_index(self.SAMPLE_HEADERS, "Estado") == 5

    def test_accent_normalization(self):
        """Should match 'Categoría' even with accent variations."""
        assert find_column_index(self.SAMPLE_HEADERS, "Categoria") == 4

    def test_case_insensitive(self):
        assert find_column_index(self.SAMPLE_HEADERS, "NOMBRE") == 2

    def test_multiple_candidates_first_match(self):
        """Returns the first matching candidate."""
        result = find_column_index(self.SAMPLE_HEADERS, "Monto", "Monto Total")
        # "Monto" won't match exactly, "Monto Total" will
        assert result == 3

    def test_no_match_returns_none(self):
        assert find_column_index(self.SAMPLE_HEADERS, "NoExiste") is None

    def test_empty_headers(self):
        assert find_column_index([], "Fecha") is None


# ── safe_row_value ───────────────────────────────────────────

class TestSafeRowValue:
    """Tests for safe_row_value — safe 1-based row access."""

    SAMPLE_ROW = ["2026-01-01", "Juan", "5000", "REMERAS", "PAGO"]

    def test_first_column(self):
        assert safe_row_value(self.SAMPLE_ROW, 1) == "2026-01-01"

    def test_last_column(self):
        assert safe_row_value(self.SAMPLE_ROW, 5) == "PAGO"

    def test_middle_column(self):
        assert safe_row_value(self.SAMPLE_ROW, 3) == "5000"

    def test_out_of_range_returns_default(self):
        assert safe_row_value(self.SAMPLE_ROW, 10) == "0"

    def test_out_of_range_custom_default(self):
        assert safe_row_value(self.SAMPLE_ROW, 10, default="N/A") == "N/A"

    def test_empty_row(self):
        assert safe_row_value([], 1) == "0"

    def test_index_zero_wraps_to_last(self):
        """Index 0 is not valid 1-based, but Python -1 indexing wraps to last element.
        This is a known edge case — callers should never pass 0."""
        assert safe_row_value(self.SAMPLE_ROW, 0) == "PAGO"  # wraps to [-1]
