import pytest
pytestmark = pytest.mark.unit

# tests/unit/lambdas/test_scheduler_handler.py
"""Unit tests for lambdas/scheduler_handler.py — Risk R10: automation failures."""
from unittest.mock import patch, MagicMock, AsyncMock
from config import BOT_TOKEN, CHAT_ID, CHECKS_SHEET_NAME, FUTURE_PAYMENTS_SHEET_NAME

class TestSendAlerts:
    """Tests for send_alerts logic."""

    @pytest.mark.asyncio
    @patch("lambdas.scheduler_handler.CHAT_ID", 12345)
    @patch("lambdas.scheduler_handler.BOT_TOKEN", "test_token")
    @patch("lambdas.scheduler_handler.Bot")
    @patch("lambdas.scheduler_handler.connect_globally_to_sheets", return_value=True)
    @patch("lambdas.scheduler_handler.update_past_due_statuses")
    @patch("lambdas.scheduler_handler.get_items_due_in_x_days")
    async def test_sends_alert_if_items_due(self, mock_get_due, mock_update, mock_connect, mock_bot_cls):
        from lambdas.scheduler_handler import send_alerts
        # Mock due items
        mock_get_due.return_value = {
            "cheques": [{"ID": "CHK-001", "Tipo": "EMITIDO", "Entidad": "Banco X", "Monto": 1000, "Fecha Cobro": "15/05/2024"}],
            "pagos_futuros": []
        }
        
        # Setup mock bot
        mock_bot_instance = AsyncMock()
        mock_bot_cls.return_value = mock_bot_instance

        await send_alerts()

        mock_update.assert_called_once()
        mock_bot_instance.send_message.assert_called_once()
        args, kwargs = mock_bot_instance.send_message.call_args
        assert "Banco X" in kwargs['text']
        assert "$1,000.00" in kwargs['text']

    @pytest.mark.asyncio
    @patch("lambdas.scheduler_handler.CHAT_ID", 12345)
    @patch("lambdas.scheduler_handler.BOT_TOKEN", "test_token")
    @patch("lambdas.scheduler_handler.Bot")
    @patch("lambdas.scheduler_handler.connect_globally_to_sheets", return_value=True)
    @patch("lambdas.scheduler_handler.update_past_due_statuses")
    @patch("lambdas.scheduler_handler.get_items_due_in_x_days")
    async def test_no_alerts_sent_if_empty(self, mock_get_due, mock_update, mock_connect, mock_bot_cls):
        from lambdas.scheduler_handler import send_alerts
        mock_get_due.return_value = {"cheques": [], "pagos_futuros": []}
        mock_bot_instance = AsyncMock()
        mock_bot_cls.return_value = mock_bot_instance

        await send_alerts()

        mock_update.assert_called_once()
        mock_bot_instance.send_message.assert_not_called()

    @pytest.mark.asyncio
    @patch("lambdas.scheduler_handler.CHAT_ID", 12345)
    @patch("lambdas.scheduler_handler.BOT_TOKEN", "test_token")
    @patch("lambdas.scheduler_handler.connect_globally_to_sheets", return_value=False)
    @patch("lambdas.scheduler_handler.Bot")
    async def test_aborts_if_no_sheet_connection(self, mock_bot_cls, mock_connect):
        from lambdas.scheduler_handler import send_alerts
        
        await send_alerts()
        
        # Should initialize bot
        mock_bot_cls.assert_called()
        
        # But should NOT proceed to update statuses
        with patch("lambdas.scheduler_handler.update_past_due_statuses") as mock_update:
             await send_alerts()
             mock_update.assert_not_called()


class TestDailyTasks:
    """Tests for daily_tasks logic (recording actions)."""

    @pytest.mark.asyncio
    @patch("lambdas.scheduler_handler.CHAT_ID", 12345)
    @patch("lambdas.scheduler_handler.BOT_TOKEN", "test_token")
    @patch("lambdas.scheduler_handler.Bot")
    @patch("lambdas.scheduler_handler.connect_globally_to_sheets", return_value=True)
    @patch("lambdas.scheduler_handler.update_past_due_statuses")
    @patch("lambdas.scheduler_handler.get_items_due_today")
    @patch("lambdas.scheduler_handler.add_expense")
    @patch("lambdas.scheduler_handler.add_wholesale_record")
    @patch("lambdas.scheduler_handler.update_item_status")
    @patch("lambdas.scheduler_handler.get_items_due_in_x_days")
    async def test_records_cheque_and_payment(self, mock_get_alerts, mock_update_status, mock_add_w, mock_add_exp, mock_get_today, mock_update_past, mock_connect, mock_bot_cls):
        from lambdas.scheduler_handler import daily_tasks
        
        # Mock items due today
        mock_get_today.return_value = {
            "cheques": [{"ID": "C1", "Entidad": "Prov", "Monto Final": 500, "Fecha Cobro": "01/01/2024"}],
            "pagos_futuros": [{"ID": "F1", "Entidad": "Client", "Monto Final": 200, "Fecha Cobro": "01/01/2024", "Producto": "X", "Cantidad": 1}]
        }
        
        # Mock alerts (empty to simplify)
        mock_get_alerts.return_value = {"cheques": [], "pagos_futuros": []}
        
        mock_bot_instance = AsyncMock()
        mock_bot_cls.return_value = mock_bot_instance

        await daily_tasks()

        # Verify Cheque processing
        mock_add_exp.assert_called_once()
        mock_update_status.assert_any_call(CHECKS_SHEET_NAME, "C1", "Conciliado")

        # Verify Future Payment processing
        mock_add_w.assert_called_once()
        mock_update_status.assert_any_call(FUTURE_PAYMENTS_SHEET_NAME, "F1", "Conciliado")

        # Verify Report sent
        assert mock_bot_instance.send_message.call_count >= 1 
        args, kwargs = mock_bot_instance.send_message.call_args_list[-1]
        assert "Reporte de Conciliación Automática" in kwargs['text']


class TestLambdaHandler:
    """Tests the entry point lambda_handler."""
    
    @patch("lambdas.scheduler_handler.asyncio.run")
    @patch("lambdas.scheduler_handler.daily_tasks")
    def test_invokes_daily_tasks(self, mock_daily_tasks, mock_asyncio_run):
        from lambdas.scheduler_handler import lambda_handler
        result = lambda_handler({}, {})
        mock_asyncio_run.assert_called_once()
        mock_daily_tasks.assert_called_once()
        assert result['status'] == 200
