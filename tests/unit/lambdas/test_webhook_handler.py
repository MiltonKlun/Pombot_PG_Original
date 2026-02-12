import pytest
pytestmark = pytest.mark.unit

# tests/unit/lambdas/test_webhook_handler.py
"""Unit tests for lambdas/webhook_handler.py — Risk R12: data loss from TiendaNube."""
from unittest.mock import patch, MagicMock
import json

class TestProcessWebhookEvent:
    """Tests webhook event routing and deduplication."""

    @patch("lambdas.webhook_handler.log_webhook_event", return_value=True)
    @patch("lambdas.webhook_handler.get_full_order_details")
    @patch("lambdas.webhook_handler.process_order_paid")
    def test_processes_order_paid(self, mock_process, mock_get_details, mock_log):
        from lambdas.webhook_handler import process_webhook_event
        event_data = {
            "store_id": 123, "event": "order/paid", "id": 999
        }
        mock_get_details.return_value = {"id": 999, "status": "paid"}
        
        process_webhook_event(event_data)
        
        mock_log.assert_called_once()
        mock_get_details.assert_called_with(999)
        mock_process.assert_called_once()

    @patch("lambdas.webhook_handler.log_webhook_event", return_value=False)
    @patch("lambdas.webhook_handler.get_full_order_details")
    def test_ignores_duplicate_event(self, mock_get_details, mock_log):
        from lambdas.webhook_handler import process_webhook_event
        event_data = {"store_id": 123, "event": "order/paid", "id": 999}
        
        process_webhook_event(event_data)
        
        mock_log.assert_called_once()
        mock_get_details.assert_not_called()

class TestProcessOrderPaid:
    """Tests logic for recording a paid order."""

    @patch("lambdas.webhook_handler.add_sale")
    @patch("lambdas.webhook_handler.invalidate_products_cache")
    def test_records_sale_correctly(self, mock_invalidate, mock_add_sale):
        from lambdas.webhook_handler import process_order_paid
        order_data = {
            "id": 1001,
            "customer": {"name": "Test Customer"},
            "transactions": [{"captured_amount": "5000.00"}],
            "products": [
                {"name": "Prod A", "quantity": 1},
                {"name": "Prod B", "quantity": 2}
            ]
        }
        
        process_order_paid(order_data)
        
        mock_add_sale.assert_called_once()
        kwargs = mock_add_sale.call_args[1]
        assert kwargs['client_name'] == "Test Customer"
        assert kwargs['quantity'] == 3 # 1 + 2
        assert kwargs['variant_details']['Precio Final'] == 5000.0
        assert "Prod A, Prod B" in kwargs['variant_details']['Producto']
        
        # Verify cache invalidation
        mock_invalidate.assert_called_once()


class TestLambdaHandler:
    """Tests entry point."""

    @patch("lambdas.webhook_handler.connect_globally_to_sheets", return_value=True)
    @patch("lambdas.webhook_handler.process_webhook_event")
    def test_success_response(self, mock_process, mock_connect):
        from lambdas.webhook_handler import lambda_handler
        event = {'body': json.dumps({"event": "test"})}
        
        response = lambda_handler(event, {})
        
        assert response['statusCode'] == 200
        mock_process.assert_called_once()

    @patch("lambdas.webhook_handler.connect_globally_to_sheets", return_value=False)
    def test_connection_failure(self, mock_connect):
        from lambdas.webhook_handler import lambda_handler
        response = lambda_handler({}, {})
        assert response['statusCode'] == 500
