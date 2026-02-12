# sheet.py
"""
Backward-compatible facade — re-exports all public functions from the
services/ package so that existing `from sheet import X` statements
continue to work without changes.

All business logic now lives in the services/ submodules:
  - services.sheets_connection   (connection, helpers, idempotency)
  - services.products_service    (product cache, queries, stock)
  - services.sales_service       (add_sale, add_transaction_generic)
  - services.expenses_service    (add_expense)
  - services.debts_service       (debt CRUD)
  - services.wholesale_service   (wholesale CRUD + summaries)
  - services.checks_service      (checks, future payments, scheduling)
  - services.balance_service     (monthly summaries, net balance)
"""

# Connection & infrastructure
from services.sheets_connection import (
    connect_globally_to_sheets,
    IS_SHEET_CONNECTED,
    get_value_from_dict_insensitive,
    apply_table_formatting,
    _get_or_create_worksheet,
    get_or_create_monthly_sheet,
    find_column_index,
    safe_row_value,
    check_and_set_event_processed,
    log_webhook_event,
)

# Products
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

# Sales
from services.sales_service import (
    add_transaction_generic,
    add_sale,
)

# Expenses
from services.expenses_service import (
    add_expense,
)

# Debts
from services.debts_service import (
    get_or_create_debts_sheet,
    add_new_debt,
    get_active_debts,
    register_debt_payment,
    increase_debt_amount,
)

# Wholesale
from services.wholesale_service import (
    add_wholesale_record,
    get_pending_wholesale_payments,
    modify_wholesale_payment,
    get_wholesale_summary,
)

# Checks & Future Payments
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

# Balance & Reporting
from services.balance_service import (
    get_monthly_summary,
    get_net_balance_for_month,
    get_available_sheet_months_years,
)
