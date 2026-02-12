import pytest
pytestmark = pytest.mark.unit

# tests/test_handler_wholesale.py
"""Unit tests for handlers/wholesale.py — Risk R8: seña overpayment."""
from unittest.mock import patch, AsyncMock, MagicMock
from constants import MODIFY_PAYMENT_GET_AMOUNT, ADD_WHOLESALE_GET_QUANTITY, ADD_WHOLESALE_GET_TOTAL_AMOUNT
from config import RESTART_PROMPT
from tests.helpers.telegram_factories import make_update, make_context
import asyncio


class TestSaveWholesaleRecord:
    """Tests for save_wholesale_record — builds record from user_data."""

    @pytest.mark.asyncio
    @patch("handlers.wholesale.display_main_menu", new_callable=AsyncMock, return_value=0)
    @patch("handlers.wholesale.check_and_set_event_processed", return_value=True)
    @patch("handlers.wholesale.add_wholesale_record")
    async def test_calls_service_with_correct_args(self, mock_add, mock_event, mock_menu):
        from handlers.wholesale import save_wholesale_record
        mock_add.return_value = {
            "name": "ClienteA", "product": "Remera", "quantity": 10,
            "paid_amount": 50000.0, "sheet_title": "Mayoristas Enero"
        }
        update = make_update(text="50000")
        context = make_context(user_data={
            "wholesale_flow": {
                "name": "ClienteA", "product": "Remera", "quantity": 10,
                "category": "PAGO", "paid_amount": 50000.0, "total_amount": 50000.0
            }
        })
        await save_wholesale_record(update, context)
        mock_add.assert_called_once_with("ClienteA", "Remera", 10, 50000.0, 50000.0, "PAGO")

    @pytest.mark.asyncio
    @patch("handlers.wholesale.display_main_menu", new_callable=AsyncMock, return_value=0)
    @patch("handlers.wholesale.check_and_set_event_processed", return_value=True)
    @patch("handlers.wholesale.add_wholesale_record", return_value=None)
    async def test_shows_error_on_service_failure(self, mock_add, mock_event, mock_menu):
        from handlers.wholesale import save_wholesale_record
        update = make_update(text="50000")
        context = make_context(user_data={
            "wholesale_flow": {
                "name": "A", "product": "B", "quantity": 1,
                "category": "PAGO", "paid_amount": 100.0, "total_amount": 100.0
            }
        })
        await save_wholesale_record(update, context)
        # Check if any call args contain "error" (case-insensitive)
        error_calls = [c for c in update.message.reply_text.call_args_list if "error" in str(c).lower()]
        assert len(error_calls) > 0

    @pytest.mark.asyncio
    @patch("handlers.wholesale.display_main_menu", new_callable=AsyncMock, return_value=0)
    @patch("handlers.wholesale.check_and_set_event_processed", return_value=True)
    @patch("handlers.wholesale.add_wholesale_record", side_effect=Exception("DB error"))
    async def test_handles_exception_gracefully(self, mock_add, mock_event, mock_menu):
        from handlers.wholesale import save_wholesale_record
        update = make_update(text="50000")
        context = make_context(user_data={
            "wholesale_flow": {
                "name": "A", "product": "B", "quantity": 1,
                "category": "PAGO", "paid_amount": 100.0, "total_amount": 100.0
            }
        })
        # Should not crash
        await save_wholesale_record(update, context)


class TestApplyModificationPayment:
    """Tests for apply_modification_payment — payment against pending seña."""

    @pytest.mark.asyncio
    @patch("handlers.wholesale.display_main_menu", new_callable=AsyncMock, return_value=0)
    @patch("handlers.wholesale.modify_wholesale_payment")
    @patch("handlers.wholesale.get_value_from_dict_insensitive", return_value="5000")
    async def test_valid_payment_calls_modify(self, mock_get_val, mock_modify, mock_menu):
        from handlers.wholesale import apply_modification_payment
        mock_modify.return_value = {"remaining_balance": 3000.0}
        update = make_update(text="2000")
        context = make_context(user_data={
            "wholesale_flow": {
                "selected_seña": {"row_number": 5, "Monto Restante": "5000"}
            }
        })
        await apply_modification_payment(update, context)
        mock_modify.assert_called_once_with(5, 2000.0)

    @pytest.mark.asyncio
    @patch("handlers.wholesale.get_value_from_dict_insensitive", return_value="5000")
    async def test_rejects_overpayment(self, mock_get_val):
        from handlers.wholesale import apply_modification_payment
        update = make_update(text="6000")
        context = make_context(user_data={
            "wholesale_flow": {
                "selected_seña": {"row_number": 5, "Monto Restante": "5000"}
            }
        })
        result = await apply_modification_payment(update, context)
        assert result == MODIFY_PAYMENT_GET_AMOUNT

    @pytest.mark.asyncio
    @patch("handlers.wholesale.get_value_from_dict_insensitive", return_value="5000")
    async def test_rejects_invalid_amount(self, mock_get_val):
        from handlers.wholesale import apply_modification_payment
        update = make_update(text="abc")
        context = make_context(user_data={
            "wholesale_flow": {
                "selected_seña": {"row_number": 5, "Monto Restante": "5000"}
            }
        })
        result = await apply_modification_payment(update, context)
        assert result == MODIFY_PAYMENT_GET_AMOUNT

    @pytest.mark.asyncio
    @patch("handlers.wholesale.display_main_menu", new_callable=AsyncMock, return_value=0)
    @patch("handlers.wholesale.modify_wholesale_payment")
    @patch("handlers.wholesale.get_value_from_dict_insensitive", return_value="5000")
    async def test_full_payment_shows_completed(self, mock_get_val, mock_modify, mock_menu):
        from handlers.wholesale import apply_modification_payment
        mock_modify.return_value = {"remaining_balance": 0}
        update = make_update(text="5000")
        context = make_context(user_data={
            "wholesale_flow": {
                "selected_seña": {"row_number": 5, "Monto Restante": "5000"}
            }
        })
        await apply_modification_payment(update, context)
        # Verify text sent contains 'pago completado' or similar
        called_text = str(update.message.reply_text.call_args_list)
        assert "pago completado" in called_text.lower() or "saldada" in called_text.lower()


class TestWholesaleValidation:
    """Tests for input validation in wholesale flows."""

    @pytest.mark.asyncio
    async def test_negative_quantity_rejected(self):
        """Should reject negative quantity input."""
        from handlers.wholesale import wholesale_get_quantity
        update = make_update(text="-5")
        context = make_context()
        
        # Act
        next_state = await wholesale_get_quantity(update, context)
        
        # Assert
        assert next_state == ADD_WHOLESALE_GET_QUANTITY
        update.message.reply_text.assert_called_with(
            f"Cantidad inválida. Ingresa un número entero positivo:{RESTART_PROMPT}"
        )

    @pytest.mark.asyncio
    async def test_non_numeric_quantity_rejected(self):
        """Should reject non-numeric quantity input."""
        from handlers.wholesale import wholesale_get_quantity
        update = make_update(text="abc")
        context = make_context()
        
        # Act
        next_state = await wholesale_get_quantity(update, context)
        
        # Assert
        assert next_state == ADD_WHOLESALE_GET_QUANTITY
        update.message.reply_text.assert_called_with(
            f"Cantidad inválida. Ingresa un número entero positivo:{RESTART_PROMPT}"
        )

    @pytest.mark.asyncio
    async def test_total_less_than_paid_rejected_for_seña(self):
        """Should reject if Total Amount < Paid Amount (Seña)."""
        from handlers.wholesale import wholesale_get_total_amount
        update = make_update(text="500") # Total amount attempt
        context = make_context()
        context.user_data['wholesale_flow'] = {'paid_amount': 1000.0} # Previously paid more
        
        # Act
        next_state = await wholesale_get_total_amount(update, context)
        
        # Assert
        assert next_state == ADD_WHOLESALE_GET_TOTAL_AMOUNT
        update.message.reply_text.assert_called_with(
            "El monto total no puede ser menor que la seña. Ingresa un monto total válido:"
        )


class TestWholesaleFullFlow:
    """Tests for complete successful flows."""

    @pytest.mark.asyncio
    @patch("handlers.wholesale.add_wholesale_record")
    @patch("handlers.wholesale.check_and_set_event_processed")
    @patch("handlers.wholesale.display_main_menu", new_callable=AsyncMock, return_value=-1)
    async def test_full_seña_flow_success(self, mock_menu, mock_check_processed, mock_add_record):
        """Should complete a Seña recording successfully."""
        from handlers.wholesale import wholesale_get_total_amount
        mock_check_processed.return_value = True
        mock_add_record.return_value = {
            'name': 'Client X', 'product': 'Prod Y', 'quantity': 10,
            'paid_amount': 500.0, 'sheet_title': 'Oct 2023', 'category': 'Seña'
        }
        
        update = make_update(text="2000") # Total amount
        context = make_context()
        context.user_data['wholesale_flow'] = {
            'name': 'Client X', 'product': 'Prod Y', 'quantity': 10,
            'category': 'Seña', 'paid_amount': 500.0
        }
        
        # Act
        next_state = await wholesale_get_total_amount(update, context)
        
        # Assert
        assert next_state == -1 # Ends flow
        mock_add_record.assert_called_with('Client X', 'Prod Y', 10, 500.0, 2000.0, 'Seña')
        
        # Verify success message
        args, _ = update.message.reply_text.call_args
        assert "✅ Registro Mayorista Exitoso ✅" in args[0]
        assert "Tipo: Seña" in args[0]


class TestWholesaleMenu:
    """Tests for menu navigation and option selection."""

    @pytest.mark.asyncio
    async def test_start_add_wholesale_shows_options(self):
        from handlers.wholesale import start_add_wholesale, ADD_WHOLESALE_MENU
        update = make_update(callback_data="main_add_wholesale")
        context = make_context()
        
        state = await start_add_wholesale(update, context)
        
        assert state == ADD_WHOLESALE_MENU
        update.callback_query.edit_message_text.assert_called_once()
        args, _ = update.callback_query.edit_message_text.call_args
        assert "Ventas Mayoristas" in args[0]

    @pytest.mark.asyncio
    async def test_menu_handler_starts_seña(self):
        from handlers.wholesale import wholesale_menu_handler, ADD_WHOLESALE_GET_NAME
        update = make_update(callback_data="wholesale_seña")
        context = make_context()
        
        state = await wholesale_menu_handler(update, context)
        
        assert state == ADD_WHOLESALE_GET_NAME
        assert context.user_data['wholesale_flow']['category'] == "Seña"

    @pytest.mark.asyncio
    async def test_menu_handler_starts_full_payment(self):
        from handlers.wholesale import wholesale_menu_handler, ADD_WHOLESALE_GET_NAME
        update = make_update(callback_data="wholesale_pago_completo")
        context = make_context()
        
        state = await wholesale_menu_handler(update, context)
        
        assert state == ADD_WHOLESALE_GET_NAME
        assert context.user_data['wholesale_flow']['category'] == "PAGO"


class TestWholesaleInputCollection:
    """Tests for collecting Name, Product, Quantity, and Amounts."""

    @pytest.mark.asyncio
    async def test_get_name(self):
        from handlers.wholesale import wholesale_get_name, ADD_WHOLESALE_GET_PRODUCT
        update = make_update(text="Cliente Test")
        context = make_context(user_data={"wholesale_flow": {}})
        
        state = await wholesale_get_name(update, context)
        
        assert state == ADD_WHOLESALE_GET_PRODUCT
        assert context.user_data['wholesale_flow']['name'] == "Cliente Test"

    @pytest.mark.asyncio
    async def test_get_product(self):
        from handlers.wholesale import wholesale_get_product, ADD_WHOLESALE_GET_QUANTITY
        update = make_update(text="Producto Test")
        context = make_context(user_data={"wholesale_flow": {}})
        
        state = await wholesale_get_product(update, context)
        
        assert state == ADD_WHOLESALE_GET_QUANTITY
        assert context.user_data['wholesale_flow']['product'] == "Producto Test"

    @pytest.mark.asyncio
    async def test_get_quantity_valid(self):
        from handlers.wholesale import wholesale_get_quantity, ADD_WHOLESALE_GET_PAID_AMOUNT
        from config import RESTART_PROMPT
        update = make_update(text="10")
        context = make_context(user_data={"wholesale_flow": {"category": "Seña"}})
        
        state = await wholesale_get_quantity(update, context)
        
        assert state == ADD_WHOLESALE_GET_PAID_AMOUNT
        assert context.user_data['wholesale_flow']['quantity'] == 10
        # Should ask for "monto de la SEÑA"
        update.message.reply_text.assert_called_with(f"💰 Ingresa el monto de la SEÑA (sin puntos ni comas):{RESTART_PROMPT}")

    @pytest.mark.asyncio
    @patch("handlers.wholesale.save_wholesale_record", new_callable=AsyncMock, return_value=-1)
    async def test_get_paid_amount_full_payment(self, mock_save):
        from handlers.wholesale import wholesale_get_paid_amount
        update = make_update(text="5000")
        context = make_context(user_data={"wholesale_flow": {"category": "PAGO"}})
        
        state = await wholesale_get_paid_amount(update, context)
        
        # For full payment, it sets total_amount = paid_amount and calls save
        assert context.user_data['wholesale_flow']['paid_amount'] == 5000.0
        assert context.user_data['wholesale_flow']['total_amount'] == 5000.0
        mock_save.assert_called_once()
        assert state == -1

    @pytest.mark.asyncio
    async def test_get_paid_amount_seña(self):
        from handlers.wholesale import wholesale_get_paid_amount, ADD_WHOLESALE_GET_TOTAL_AMOUNT
        update = make_update(text="1000")
        context = make_context(user_data={"wholesale_flow": {"category": "Seña"}})
        
        state = await wholesale_get_paid_amount(update, context)
        
        assert state == ADD_WHOLESALE_GET_TOTAL_AMOUNT
        assert context.user_data['wholesale_flow']['paid_amount'] == 1000.0
        # Should ask for TOTAL amount
        args, _ = update.message.reply_text.call_args
        assert "monto TOTAL" in args[0]


class TestWholesaleModifyNavigation:
    """Tests for Modify Payment flow navigation."""

    @pytest.mark.asyncio
    @patch("handlers.wholesale.get_or_create_monthly_sheet")
    @patch("handlers.wholesale.get_pending_wholesale_payments")
    async def test_start_modify_payment_lists_debts(self, mock_get_pending, mock_get_sheet):
        from handlers.wholesale import start_modify_payment, MODIFY_PAYMENT_CHOOSE_SENA
        # Mock pending señas
        mock_get_pending.return_value = [
            {"Nombre": "Client A", "Producto": "Item 1", "Monto Restante": "1000"},
            {"Nombre": "Client B", "Producto": "Item 2", "Monto Restante": "2000"}
        ]
        
        
        update = make_update(callback_data="wholesale_mod_pago")
        context = make_context(user_data={"wholesale_flow": {}})
        
        state = await start_modify_payment(update, context)
        
        assert state == MODIFY_PAYMENT_CHOOSE_SENA
        # Verify pending señas are stored in context
        assert len(context.user_data['wholesale_flow']['pending_señs']) == 2
        # Verify output message contains options (implicitly via edit_message_text call args)
        update.callback_query.edit_message_text.assert_called()
        args, kwargs = update.callback_query.edit_message_text.call_args
        reply_markup = kwargs.get('reply_markup')
        # 2 options + 1 back button
        assert len(reply_markup.inline_keyboard) >= 2

    @pytest.mark.asyncio
    @patch("handlers.wholesale.get_or_create_monthly_sheet")
    @patch("handlers.wholesale.get_pending_wholesale_payments", return_value=[])
    @patch("handlers.wholesale.start_add_wholesale", new_callable=AsyncMock)
    async def test_start_modify_payment_no_debts(self, mock_start, mock_get_pending, mock_get_sheet):
        from handlers.wholesale import start_modify_payment
        update = make_update(callback_data="wholesale_mod_pago")
        context = make_context()
        
        await start_modify_payment(update, context)
        
        mock_start.assert_called_once()
        update.callback_query.edit_message_text.assert_called_with("No se encontraron señas pendientes para el mes actual.")

    @pytest.mark.asyncio
    async def test_ask_for_modification_amount_valid_selection(self):
        from handlers.wholesale import ask_for_modification_amount, MODIFY_PAYMENT_GET_AMOUNT
        update = make_update(callback_data="mod_sena_1")
        # Setup context with pending señas
        context = make_context(user_data={
            "wholesale_flow": {
                "pending_señs": [
                    {"Nombre": "A", "Monto Restante": "100"},
                    {"Nombre": "B", "Monto Restante": "200"}
                ]
            }
        })
        
        state = await ask_for_modification_amount(update, context)
        
        assert state == MODIFY_PAYMENT_GET_AMOUNT
        assert context.user_data['wholesale_flow']['selected_seña']['Nombre'] == "B"
        args, _ = update.callback_query.edit_message_text.call_args
        assert "$200.00" in args[0]

    @pytest.mark.asyncio
    @patch("handlers.wholesale.start_add_wholesale", new_callable=AsyncMock)
    async def test_ask_for_modification_amount_invalid_selection(self, mock_start):
        from handlers.wholesale import ask_for_modification_amount
        update = make_update(callback_data="mod_sena_99")
        context = make_context(user_data={"wholesale_flow": {"pending_señs": []}})
        
        await ask_for_modification_amount(update, context)
        
        mock_start.assert_called_once()
        update.callback_query.edit_message_text.assert_called_with("Error al seleccionar la seña. Inténtalo de nuevo.")


