# services/__init__.py
"""
Services package — re-exports all public functions for backward compatibility.
Consumers can import directly from `services` or from individual submodules.
"""

# --- sheets_connection ---
from services.sheets_connection import (
    connect_globally_to_sheets,
    IS_SHEET_CONNECTED,
    get_value_from_dict_insensitive,
    apply_table_formatting,
    _get_or_create_worksheet,
    get_or_create_monthly_sheet,
    find_column_index, safe_row_value,
    check_and_set_event_processed,
    log_webhook_event,
)

# --- products_service ---
from services.products_service import (
    invalidate_products_cache,
    get_product_sheet,
    get_all_products_data_cached,
    get_product_categories,
    get_products_by_category,
    get_product_options,
    get_variant_details,
    update_product_stock,
    update_products_from_tiendanube,
)

# --- sales_service ---
from services.sales_service import (
    add_transaction_generic,
    add_sale,
)

# --- expenses_service ---
from services.expenses_service import (
    add_expense,
)

# --- debts_service ---
from services.debts_service import (
    get_or_create_debts_sheet,
    add_new_debt,
    get_active_debts,
    register_debt_payment,
    increase_debt_amount,
)

# --- wholesale_service ---
from services.wholesale_service import (
    add_wholesale_record,
    get_pending_wholesale_payments,
    modify_wholesale_payment,
    get_wholesale_summary,
)

# --- checks_service ---
from services.checks_service import (
    add_check,
    get_pending_checks,
    add_future_payment,
    get_pending_future_payments,
    get_items_due_in_x_days,
    update_past_due_statuses,
    get_items_due_today,
    update_item_status,
)

# --- balance_service ---
from services.balance_service import (
    get_monthly_summary,
    get_net_balance_for_month,
    get_available_sheet_months_years,
)
