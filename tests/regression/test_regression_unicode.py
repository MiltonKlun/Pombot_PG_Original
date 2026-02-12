import pytest
pytestmark = pytest.mark.regression

# tests/regression/test_regression_unicode.py
"""
Regression tests for unicode and text normalization handling.
"""
from common.utils import normalize_text
from services.sheets_connection import find_column_index

class TestUnicodeNormalization:
    def test_accent_removal(self):
        assert normalize_text("Categoría") == "categoria"
        assert normalize_text("Árbol") == "arbol"
        assert normalize_text("Ñandú") == "nandu"

    def test_case_sensitivity(self):
        assert normalize_text("TeSt") == "test"

    def test_mixed_chars(self):
        assert normalize_text("  Música & Más  ") == "musica & mas"

class TestHeaderMatching:
    """Verify fuzzy matching for sheet headers."""

    HEADERS = ["Fecha", "Categoría", "Descripción", "Opción 1: Valor"]

    def test_accent_insensitive_match(self):
        # Debug prints
        print(f"\nHeader normalized: '{normalize_text(self.HEADERS[1])}'")
        print(f"Target normalized: '{normalize_text('Categoria')}'")
        
        idx = find_column_index(self.HEADERS, "Categoria")
        assert idx == 2
        
        idx2 = find_column_index(self.HEADERS, "Descripcion")
        assert idx2 == 3

    def test_case_insensitive_match(self):
        assert find_column_index(self.HEADERS, "FECHA") == 1
        assert find_column_index(self.HEADERS, "CATEGORÍA") == 2
