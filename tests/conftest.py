# tests/conftest.py
"""
Shared pytest fixtures for the Pombot test suite.
"""
import pytest
import warnings
try:
    from telegram.warnings import PTBUserWarning
    warnings.filterwarnings("ignore", category=PTBUserWarning)
except ImportError:
    pass


@pytest.fixture
def sample_expense_records():
    """Sample expense records as returned by gspread get_all_records()."""
    return [
        {"Fecha": "01/01/2026", "Categoría": "INSUMOS", "Subcategoría": "ESTAMPAS", "Descripción Principal": "Tela", "Detalles Adicionales": "", "Monto": 5000},
        {"Fecha": "02/01/2026", "Categoría": "PERSONALES", "Subcategoría": "ALQUILER", "Descripción Principal": "Alquiler Enero", "Detalles Adicionales": "", "Monto": 80000},
        {"Fecha": "03/01/2026", "Categoría": "PERSONALES", "Subcategoría": "LUZ", "Descripción Principal": "Factura Luz", "Detalles Adicionales": "", "Monto": 15000},
        {"Fecha": "04/01/2026", "Categoría": "CANJES", "Subcategoría": "Promo", "Descripción Principal": "Canje con influencer", "Detalles Adicionales": "", "Monto": 3000},
    ]


@pytest.fixture
def sample_sales_records():
    """Sample sales records as returned by gspread get_all_records()."""
    return [
        {"Fecha": "01/01/2026", "Producto": "Remera", "Variante": "M", "Cliente": "Juan", "Categoría": "REMERAS", "Cantidad": 2, "Precio Unitario": 5000, "%": 0, "Descuento": 0, "Precio Total": 10000},
        {"Fecha": "02/01/2026", "Producto": "Pantalón", "Variante": "L", "Cliente": "María", "Categoría": "PANTALONES", "Cantidad": 1, "Precio Unitario": 8000, "%": 10, "Descuento": 800, "Precio Total": 7200},
    ]
