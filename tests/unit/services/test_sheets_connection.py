import pytest
pytestmark = pytest.mark.unit

# tests/test_sheets_connection.py
"""Unit tests for services/sheets_connection.py — connection, worksheets, dedup."""
from unittest.mock import patch, MagicMock
import gspread


class TestConnectGloballyToSheets:
    """Tests for connect_globally_to_sheets — singleton connection."""

    @patch("services.sheets_connection.SHEET_ID", "test-sheet-id")
    @patch("services.sheets_connection.google_credentials")
    @patch("services.sheets_connection.gspread.authorize")
    def test_successful_connection(self, mock_authorize, mock_creds):
        mock_gc = MagicMock()
        mock_spreadsheet = MagicMock()
        mock_authorize.return_value = mock_gc
        mock_gc.open_by_key.return_value = mock_spreadsheet

        import services.sheets_connection as sc
        sc.gc = None
        sc.spreadsheet = None
        sc.IS_SHEET_CONNECTED = False

        result = sc.connect_globally_to_sheets()

        assert result is True
        assert sc.IS_SHEET_CONNECTED is True
        mock_authorize.assert_called_once_with(mock_creds)

    @patch("services.sheets_connection.google_credentials", None)
    def test_returns_false_without_credentials(self):
        import services.sheets_connection as sc
        sc.gc = None
        sc.spreadsheet = None
        sc.IS_SHEET_CONNECTED = False

        result = sc.connect_globally_to_sheets()

        assert result is False
        assert sc.IS_SHEET_CONNECTED is False

    @patch("services.sheets_connection.SHEET_ID", "bad-id")
    @patch("services.sheets_connection.google_credentials", MagicMock())
    @patch("services.sheets_connection.gspread.authorize")
    def test_returns_false_on_spreadsheet_not_found(self, mock_authorize):
        mock_gc = MagicMock()
        mock_gc.open_by_key.side_effect = gspread.exceptions.SpreadsheetNotFound
        mock_authorize.return_value = mock_gc

        import services.sheets_connection as sc
        sc.gc = None
        sc.spreadsheet = None
        sc.IS_SHEET_CONNECTED = False

        result = sc.connect_globally_to_sheets()

        assert result is False

    def test_returns_true_if_already_connected(self):
        import services.sheets_connection as sc
        sc.gc = MagicMock()
        sc.spreadsheet = MagicMock()

        result = sc.connect_globally_to_sheets()

        assert result is True


class TestGetValueFromDictInsensitive:
    """Tests for get_value_from_dict_insensitive — accent/case insensitive lookup."""

    def test_exact_match(self):
        from services.sheets_connection import get_value_from_dict_insensitive
        assert get_value_from_dict_insensitive({"Nombre": "Juan"}, "Nombre") == "Juan"

    def test_case_insensitive(self):
        from services.sheets_connection import get_value_from_dict_insensitive
        assert get_value_from_dict_insensitive({"nombre": "Juan"}, "Nombre") == "Juan"

    def test_accent_insensitive(self):
        from services.sheets_connection import get_value_from_dict_insensitive
        assert get_value_from_dict_insensitive({"Categoría": "INSUMOS"}, "Categoria") == "INSUMOS"

    def test_returns_none_on_no_match(self):
        from services.sheets_connection import get_value_from_dict_insensitive
        assert get_value_from_dict_insensitive({"Nombre": "Juan"}, "Apellido") is None

    def test_non_dict_returns_none(self):
        from services.sheets_connection import get_value_from_dict_insensitive
        assert get_value_from_dict_insensitive("not a dict", "key") is None

    def test_non_string_key_returns_none(self):
        from services.sheets_connection import get_value_from_dict_insensitive
        assert get_value_from_dict_insensitive({"key": "val"}, 123) is None


class TestGetOrCreateWorksheet:
    """Tests for _get_or_create_worksheet — finds or creates sheets."""

    @patch("services.sheets_connection.IS_SHEET_CONNECTED", True)
    @patch("services.sheets_connection.spreadsheet")
    def test_returns_existing_worksheet(self, mock_spreadsheet):
        mock_ws = MagicMock()
        mock_spreadsheet.worksheet.return_value = mock_ws

        from services.sheets_connection import _get_or_create_worksheet
        result = _get_or_create_worksheet("TestSheet", ["H1", "H2"])

        assert result == mock_ws

    @patch("services.sheets_connection.apply_table_formatting")
    @patch("services.sheets_connection.IS_SHEET_CONNECTED", True)
    @patch("services.sheets_connection.spreadsheet")
    def test_creates_new_sheet_when_not_found(self, mock_spreadsheet, mock_format):
        mock_spreadsheet.worksheet.side_effect = gspread.exceptions.WorksheetNotFound
        mock_new_ws = MagicMock()
        mock_spreadsheet.add_worksheet.return_value = mock_new_ws

        from services.sheets_connection import _get_or_create_worksheet
        result = _get_or_create_worksheet("NewSheet", ["Col1", "Col2"])

        assert result == mock_new_ws
        mock_spreadsheet.add_worksheet.assert_called_once()
        mock_new_ws.append_row.assert_called_once_with(["Col1", "Col2"], value_input_option='USER_ENTERED')

    @patch("services.sheets_connection.IS_SHEET_CONNECTED", False)
    def test_returns_none_without_connection(self):
        from services.sheets_connection import _get_or_create_worksheet
        assert _get_or_create_worksheet("Test", ["H1"]) is None


class TestGetOrCreateMonthlySheet:
    """Tests for get_or_create_monthly_sheet — month-based sheet creation."""

    @patch("services.sheets_connection.IS_SHEET_CONNECTED", True)
    @patch("services.sheets_connection.spreadsheet")
    def test_returns_existing_monthly_sheet(self, mock_spreadsheet):
        mock_ws = MagicMock()
        mock_spreadsheet.worksheet.return_value = mock_ws

        from services.sheets_connection import get_or_create_monthly_sheet
        from datetime import datetime
        result = get_or_create_monthly_sheet("Ventas", ["H1"], date_override=datetime(2026, 1, 15))

        assert result == mock_ws
        mock_spreadsheet.worksheet.assert_called_once_with("Ventas Enero 2026")

    @patch("services.sheets_connection.apply_table_formatting")
    @patch("services.sheets_connection.IS_SHEET_CONNECTED", True)
    @patch("services.sheets_connection.spreadsheet")
    def test_creates_new_monthly_sheet(self, mock_spreadsheet, mock_format):
        mock_spreadsheet.worksheet.side_effect = gspread.exceptions.WorksheetNotFound
        mock_new_ws = MagicMock()
        mock_spreadsheet.add_worksheet.return_value = mock_new_ws

        from services.sheets_connection import get_or_create_monthly_sheet
        from datetime import datetime
        result = get_or_create_monthly_sheet("Gastos", ["H1", "H2"], date_override=datetime(2026, 3, 10))

        assert result == mock_new_ws
        mock_spreadsheet.add_worksheet.assert_called_once()
        # Verify the sheet name includes the correct month
        call_kwargs = mock_spreadsheet.add_worksheet.call_args
        assert "Marzo" in call_kwargs[1].get("title", call_kwargs[0][0] if call_kwargs[0] else "")

    @patch("services.sheets_connection.IS_SHEET_CONNECTED", False)
    def test_returns_none_without_connection(self):
        from services.sheets_connection import get_or_create_monthly_sheet
        assert get_or_create_monthly_sheet("Ventas", ["H1"]) is None


class TestCheckAndSetEventProcessed:
    """Tests for check_and_set_event_processed — deduplication logic."""

    @patch("services.sheets_connection._get_or_create_worksheet")
    def test_new_event_returns_true(self, mock_get_ws):
        mock_ws = MagicMock()
        mock_ws.find.return_value = None  # not found = new event
        mock_get_ws.return_value = mock_ws

        from services.sheets_connection import check_and_set_event_processed
        result = check_and_set_event_processed("event-123")

        assert result is True
        mock_ws.append_row.assert_called_once()

    @patch("services.sheets_connection._get_or_create_worksheet")
    def test_duplicate_event_returns_false(self, mock_get_ws):
        mock_ws = MagicMock()
        mock_ws.find.return_value = MagicMock()  # found = duplicate
        mock_get_ws.return_value = mock_ws

        from services.sheets_connection import check_and_set_event_processed
        result = check_and_set_event_processed("event-123")

        assert result is False
        mock_ws.append_row.assert_not_called()

    def test_empty_event_id_returns_false(self):
        from services.sheets_connection import check_and_set_event_processed
        assert check_and_set_event_processed("") is False

    @patch("services.sheets_connection._get_or_create_worksheet")
    def test_returns_true_on_no_sheet(self, mock_get_ws):
        """When sheet can't be accessed, returns True to allow processing (fail-open)."""
        mock_get_ws.return_value = None

        from services.sheets_connection import check_and_set_event_processed
        result = check_and_set_event_processed("event-456")

        assert result is True


class TestLogWebhookEvent:
    """Tests for log_webhook_event — webhook dedup log."""

    @patch("services.sheets_connection.spreadsheet")
    def test_new_webhook_returns_true(self, mock_spreadsheet):
        mock_ws = MagicMock()
        mock_ws.find.return_value = None  # new
        mock_spreadsheet.worksheet.return_value = mock_ws

        from services.sheets_connection import log_webhook_event
        result = log_webhook_event("webhook-1", "order/created", 12345)

        assert result is True
        mock_ws.append_row.assert_called_once()
        row = mock_ws.append_row.call_args[0][0]
        assert row[0] == "webhook-1"
        assert row[1] == "order/created"
        assert row[2] == 12345

    @patch("services.sheets_connection.spreadsheet")
    def test_duplicate_webhook_returns_false(self, mock_spreadsheet):
        mock_ws = MagicMock()
        mock_ws.find.return_value = MagicMock()  # found
        mock_spreadsheet.worksheet.return_value = mock_ws

        from services.sheets_connection import log_webhook_event
        result = log_webhook_event("webhook-1", "order/created", 12345)

        assert result is False

    @patch("services.sheets_connection.spreadsheet")
    def test_returns_false_on_missing_sheet(self, mock_spreadsheet):
        mock_spreadsheet.worksheet.side_effect = gspread.exceptions.WorksheetNotFound

        from services.sheets_connection import log_webhook_event
        result = log_webhook_event("webhook-1", "order/created", 12345)

        assert result is False
