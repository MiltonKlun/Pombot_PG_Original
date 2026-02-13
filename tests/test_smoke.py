import pytest
pytestmark = pytest.mark.smoke

# tests/test_smoke.py
"""
Smoke tests for Pombot-Handler.
Verifies basic integrity, imports, and config defaults.
"""
import importlib
import sys
import os

# Ensure project root is in path
# Ensure project root is in path
sys.path.append(os.getcwd())

@pytest.mark.smoke
def test_config_defaults():
    """Verify critical config defaults."""
    import config
    from services.sheets_connection import IS_SHEET_CONNECTED
    
    # Check config has essential keys
    assert hasattr(config, "SHEET_ID")
    
    # Should start disconnected to avoid accidental writes during import
    assert IS_SHEET_CONNECTED is False

def test_imports_services():
    """Verify all service modules import cleanly."""
    services = [
        "services.sales_service",
        "services.expenses_service", 
        "services.debts_service",
        "services.wholesale_service",
        "services.checks_service",
        "services.products_service",
        "services.tiendanube_service",
        "services.sheets_connection",
        "services.balance_service",
        "services.report_generator"
    ]
    for s in services:
        importlib.import_module(s)

def test_imports_handlers():
    """Verify handler modules import cleanly."""
    handlers = [
        "handlers.core",
        "handlers.sales",
        "handlers.expenses",
        "handlers.debts", 
        "handlers.wholesale",
        "handlers.checks",
        "handlers.balance",
        "handlers.future_payments",
        "handlers.conversation" 
    ]
    for h in handlers:
        importlib.import_module(h)

def test_imports_lambdas():
    """Verify lambda entry points import."""
    lambdas = [
        "lambdas.webhook_handler",
        "lambdas.scheduler_handler",
        "lambdas.lambda_sync"
    ]
    for l in lambdas:
        importlib.import_module(l)

def test_lambda_callables():
    """Verify lambda handlers expose the expected function."""
    from lambdas.webhook_handler import lambda_handler as webhook
    assert callable(webhook)
    
    from lambdas.scheduler_handler import lambda_handler as scheduler
    assert callable(scheduler)
    
    from lambdas.lambda_sync import lambda_handler as sync
    assert callable(sync)
