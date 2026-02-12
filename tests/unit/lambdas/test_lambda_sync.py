import pytest
pytestmark = pytest.mark.unit

# tests/unit/lambdas/test_lambda_sync.py
"""Unit tests for lambdas/lambda_sync.py — Risk R11: product sync failures."""
from unittest.mock import patch, MagicMock, AsyncMock

class TestLambdaHandlerSync:
    """Tests for sync products lambda."""

    @patch("lambdas.lambda_sync.connect_globally_to_sheets", return_value=True)
    @patch("lambdas.lambda_sync.get_tiendanube_products")
    @patch("lambdas.lambda_sync.update_products_from_tiendanube")
    @patch("lambdas.lambda_sync.send_telegram_notification")
    def test_sync_success(self, mock_notify, mock_update, mock_get, mock_connect):
        from lambdas.lambda_sync import lambda_handler
        
        mock_get.return_value = [{"id": 1, "name": "Prod"}]
        mock_update.return_value = (True, "Updated 1 product")
        
        result = lambda_handler({}, {})
        
        assert result['statusCode'] == 200
        assert "Sincronización completada" in result['body']
        mock_notify.assert_called_once()

    @patch("lambdas.lambda_sync.connect_globally_to_sheets", return_value=True)
    @patch("lambdas.lambda_sync.get_tiendanube_products")
    @patch("lambdas.lambda_sync.update_products_from_tiendanube")
    @patch("lambdas.lambda_sync.send_telegram_notification")
    def test_sync_partial_failure(self, mock_notify, mock_update, mock_get, mock_connect):
        from lambdas.lambda_sync import lambda_handler
        
        mock_get.return_value = []
        mock_update.return_value = (False, "Sheet error")
        
        result = lambda_handler({}, {})
        
        assert result['statusCode'] == 500
        assert "Error" in result['body']
        mock_notify.assert_called_once()

    @patch("lambdas.lambda_sync.connect_globally_to_sheets", return_value=False)
    def test_connection_failure(self, mock_connect):
        from lambdas.lambda_sync import lambda_handler
        result = lambda_handler({}, {})
        assert result['statusCode'] == 500
        assert "Failed to connect" in result['body']

    @patch("lambdas.lambda_sync.connect_globally_to_sheets", return_value=True)
    @patch("lambdas.lambda_sync.get_tiendanube_products", side_effect=ValueError("Bad Config"))
    @patch("lambdas.lambda_sync.send_telegram_notification")
    def test_handles_value_error(self, mock_notify, mock_get, mock_connect):
        from lambdas.lambda_sync import lambda_handler
        
        result = lambda_handler({}, {})
        
        assert result['statusCode'] == 500
        assert "Error de configuración" in result['body']
        mock_notify.assert_called_once()

    @patch("lambdas.lambda_sync.connect_globally_to_sheets", return_value=True)
    @patch("lambdas.lambda_sync.get_tiendanube_products", side_effect=ConnectionError("Timeout"))
    @patch("lambdas.lambda_sync.send_telegram_notification")
    def test_handles_connection_error(self, mock_notify, mock_get, mock_connect):
        from lambdas.lambda_sync import lambda_handler
        
        result = lambda_handler({}, {})
        
        assert result['statusCode'] == 500
        assert "Error de conexión" in result['body']
        mock_notify.assert_called_once()

    @patch("lambdas.lambda_sync.connect_globally_to_sheets", return_value=True)
    @patch("lambdas.lambda_sync.get_tiendanube_products", side_effect=Exception("Unknown"))
    @patch("lambdas.lambda_sync.send_telegram_notification")
    def test_handles_unexpected_error(self, mock_notify, mock_get, mock_connect):
        from lambdas.lambda_sync import lambda_handler
        
        result = lambda_handler({}, {})
        
        assert result['statusCode'] == 500
        assert "Error inesperado" in result['body']
        mock_notify.assert_called_once()


class TestSyncNotifications:
    """Tests for send_telegram_notification logic."""

    @pytest.mark.asyncio
    @patch("lambdas.lambda_sync.Bot")
    async def test_sends_message_if_token_and_chat_id_valid(self, mock_bot_cls):
        from lambdas.lambda_sync import send_telegram_notification
        mock_bot = MagicMock()
        mock_bot_cls.return_value = mock_bot
        # Mock async send_message
        mock_bot.send_message = AsyncMock()
        
        with patch("lambdas.lambda_sync.BOT_TOKEN", "VALID_TOKEN"):
            await send_telegram_notification("Hello", 123456)
        
        mock_bot.send_message.assert_called_once_with(chat_id=123456, text="Hello")

    @pytest.mark.asyncio
    @patch("lambdas.lambda_sync.Bot")
    async def test_skips_if_token_invalid(self, mock_bot_cls):
        from lambdas.lambda_sync import send_telegram_notification
        
        with patch("lambdas.lambda_sync.BOT_TOKEN", None):
            await send_telegram_notification("Hello", 123456)
            
        mock_bot_cls.assert_not_called()

    @pytest.mark.asyncio
    @patch("lambdas.lambda_sync.Bot")
    async def test_skips_if_chat_id_missing(self, mock_bot_cls):
        from lambdas.lambda_sync import send_telegram_notification
        
        with patch("lambdas.lambda_sync.BOT_TOKEN", "VALID_TOKEN"):
            await send_telegram_notification("Hello", None)
            
        mock_bot_cls.assert_not_called()

    @pytest.mark.asyncio
    @patch("lambdas.lambda_sync.Bot")
    @patch("lambdas.lambda_sync.logger")
    async def test_handles_send_error(self, mock_logger, mock_bot_cls):
        from lambdas.lambda_sync import send_telegram_notification
        mock_bot = MagicMock()
        mock_bot_cls.return_value = mock_bot
        # Mock async send_message to raise exception
        mock_bot.send_message = AsyncMock(side_effect=Exception("API Down"))
        
        with patch("lambdas.lambda_sync.BOT_TOKEN", "VALID_TOKEN"):
            await send_telegram_notification("Hello", 123456)
            
        # Should catch exception and log error
        args, _ = mock_logger.error.call_args
        assert "Failed to send Telegram notification" in args[0]

