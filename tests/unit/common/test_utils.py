import pytest
pytestmark = pytest.mark.unit

# tests/test_utils.py
"""Unit tests for utils.py — all pure functions, no mocking needed."""
from common.utils import parse_float, parse_int, normalize_text, format_report_line, generate_confirmation_image


# ── parse_float ──────────────────────────────────────────────

class TestParseFloat:
    """Tests for parse_float — Argentine-locale number parsing."""

    def test_simple_integer(self):
        assert parse_float("1000") == 1000.0

    def test_decimal_with_comma(self):
        """Argentine format uses comma as decimal separator."""
        assert parse_float("1500,50") == 1500.50

    def test_thousands_separator_dot(self):
        """Argentine format uses dot as thousands separator."""
        assert parse_float("1.500") == 1500.0

    def test_thousands_and_decimal(self):
        """Full Argentine format: 1.500,75 → 1500.75"""
        assert parse_float("1.500,75") == 1500.75

    def test_large_number(self):
        assert parse_float("1.000.000,99") == 1000000.99

    def test_whitespace(self):
        assert parse_float("  500  ") == 500.0

    def test_zero(self):
        assert parse_float("0") == 0.0

    def test_invalid_text(self):
        assert parse_float("abc") is None

    def test_empty_string(self):
        assert parse_float("") is None

    def test_non_string_input(self):
        assert parse_float(123) is None
        assert parse_float(None) is None

    def test_negative_number(self):
        assert parse_float("-500") == -500.0

    def test_standard_decimal_two_digits(self):
        """Standard format like '5000.00' should parse as 5000.0 not 500000."""
        assert parse_float("5000.00") == 5000.0

    def test_standard_decimal_one_digit(self):
        """'12.5' has 1 digit after dot → standard decimal."""
        assert parse_float("12.5") == 12.5

    def test_standard_decimal_api_price(self):
        """Simulates TiendaNube API returning '10000.00'."""
        assert parse_float("10000.00") == 10000.0


# ── parse_int ────────────────────────────────────────────────

class TestParseInt:
    """Tests for parse_int — integer parsing that strips decimal/comma parts."""

    def test_simple_integer(self):
        assert parse_int("42") == 42

    def test_strips_decimal(self):
        """Strips everything after comma/dot to get integer part."""
        assert parse_int("10,5") == 10

    def test_strips_dot_decimal(self):
        assert parse_int("10.5") == 10

    def test_zero(self):
        assert parse_int("0") == 0

    def test_whitespace(self):
        assert parse_int("  7  ") == 7

    def test_invalid_text(self):
        assert parse_int("abc") is None

    def test_empty_string(self):
        assert parse_int("") is None

    def test_non_string_input(self):
        assert parse_int(42) is None
        assert parse_int(None) is None


# ── normalize_text ───────────────────────────────────────────

class TestNormalizeText:
    """Tests for normalize_text — lowercase, strip, remove accents."""

    def test_lowercase(self):
        assert normalize_text("HELLO") == "hello"

    def test_strip_whitespace(self):
        assert normalize_text("  hello  ") == "hello"

    def test_remove_accents(self):
        assert normalize_text("Categoría") == "categoria"

    def test_remove_multiple_accents(self):
        assert normalize_text("Información") == "informacion"

    def test_ñ_preserved(self):
        """ñ is a distinct letter, not an accent — should be preserved."""
        assert normalize_text("Año") == "ano"

    def test_empty_string(self):
        assert normalize_text("") == ""

    def test_non_string_input(self):
        assert normalize_text(123) == ""
        assert normalize_text(None) == ""

    def test_combined(self):
        assert normalize_text("  CATEGORÍA  ") == "categoria"


# ── format_report_line ───────────────────────────────────────

class TestFormatReportLine:
    """Tests for format_report_line — right-aligned currency formatting."""

    def test_basic_alignment(self):
        result = format_report_line("Ventas", 10000.0)
        assert "Ventas" in result
        assert "$10,000.00" in result

    def test_total_width(self):
        result = format_report_line("A", 0.0, total_width=20)
        assert len(result) >= 5  # At minimum "A" + "$0.00"

    def test_zero_value(self):
        result = format_report_line("Nada", 0.0)
        assert "$0.00" in result

    def test_large_number(self):
        result = format_report_line("Total", 1000000.50)
        assert "$1,000,000.50" in result


# ── generate_confirmation_image ──────────────────────────────

class TestGenerateConfirmationImage:
    """Tests for generate_confirmation_image — currently a stub."""

    def test_returns_none(self):
        """Stub always returns None."""
        assert generate_confirmation_image({}, "Test") is None
