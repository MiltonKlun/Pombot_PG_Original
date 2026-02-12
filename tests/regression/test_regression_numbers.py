import pytest
pytestmark = pytest.mark.regression

# tests/regression/test_regression_numbers.py
"""
Regression tests for number parsing and boundary values.
Covers Argentine formats, large numbers, and edge cases.
"""
from common.utils import parse_float, parse_int

class TestNumberParsing:
    """Tests for utils.parse_float and parse_int with various formats."""

    def test_argentine_format_with_thousands_sep(self):
        """Standard Argentine format: dot thousands, comma decimal."""
        assert parse_float("1.500,50") == 1500.50
        assert parse_float("10.000,00") == 10000.0
        assert parse_float("1.000.000,01") == 1000000.01

    def test_argentine_format_simple_decimal(self):
        """Comma decimal without thousands separators."""
        assert parse_float("100,50") == 100.50
        assert parse_float("0,01") == 0.01
        assert parse_float(",5") == 0.5

    def test_standard_format_with_decimal(self):
        """Standard US/Code format: dot decimal."""
        assert parse_float("1500.50") == 1500.50
        assert parse_float("10.50") == 10.50
        assert parse_float("0.99") == 0.99

    def test_ambiguous_thousands_seps(self):
        """Dots interpreted as thousands separators based on heuristic."""
        # 3 digits after dot -> likely thousands (1.000 = 1000)
        assert parse_float("1.000") == 1000.0
        # Multiple dots -> definitely thousands
        assert parse_float("1.000.000") == 1000000.0
        # 10.000 -> 10000
        assert parse_float("10.000") == 10000.0

    def test_ambiguous_decimal_seps(self):
        """Dots interpreted as decimal separators based on heuristic."""
        # 1-2 digits after single dot -> decimal (1.50)
        assert parse_float("1.50") == 1.50
        assert parse_float("1.5") == 1.5
        assert parse_float("99.99") == 99.99

    def test_plain_integers(self):
        assert parse_float("500") == 500.0
        assert parse_float("1000000") == 1000000.0

    def test_negative_numbers(self):
        assert parse_float("-500,00") == -500.0
        assert parse_float("-1.000") == -1000.0

    def test_invalid_input(self):
        assert parse_float("abc") is None
        # "12.34.56" -> 123456 due to multiple dots = thousands logic
        assert parse_float("12.34.56") == 123456.0 
        assert parse_float("") is None
        assert parse_float(None) is None


class TestIntParsing:
    def test_strips_decimals(self):
        assert parse_int("10,50") == 10
        assert parse_int("10.50") == 10
        assert parse_int("1.500,99") == 1500

    def test_large_integers(self):
        assert parse_int("1.000.000") == 1000000
