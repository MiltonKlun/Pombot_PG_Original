# handlers/conversation.py
from telegram.ext import (
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters
)
from constants import *
from handlers.core import (
    start_command, cancel_command, handle_main_menu_choice, back_to_main_menu_handler,
    sync_products_command
)
from handlers.sales import (
    start_add_sale, sale_choose_category_handler, sale_product_pagination_handler, 
    sale_choose_product_handler, sale_process_next_option, sale_choose_option1_handler, 
    sale_choose_option2_handler, sale_ask_for_quantity, sale_input_quantity_handler, 
    sale_input_client_handler
)
from handlers.expenses import (
    start_add_expense, expense_choose_category_handler, expense_choose_subcategory_handler,
    expense_input_description_handler, expense_input_amount_handler,
    expense_canje_get_entity, expense_canje_get_item, expense_canje_get_quantity,
    expense_proveedores_get_name, expense_proveedores_get_item, expense_proveedores_get_quantity
)
from handlers.debts import (
    start_debt_menu, debt_menu_handler, create_debt_get_name, create_debt_get_amount,
    pay_debt_choose_debt, pay_debt_get_amount,
    modify_debt_choose_debt, modify_debt_get_amount
)
from handlers.wholesale import (
    start_add_wholesale, wholesale_menu_handler, wholesale_get_name, wholesale_get_product,
    wholesale_get_quantity, wholesale_get_paid_amount, wholesale_get_total_amount,
    ask_for_modification_amount, apply_modification_payment
)
from handlers.balance import (
    query_balance_year_handler, query_balance_month_handler
)
from handlers.checks import (
    checks_menu_handler, checks_get_entity, 
    checks_get_initial_amount, checks_get_commission, checks_get_due_date
)
from handlers.future_payments import (
    fp_menu_handler, fp_get_entity, fp_get_product, fp_get_quantity,
    fp_get_initial_amount, fp_get_commission, fp_get_due_date
)

conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start_command)],
    states={
        MAIN_MENU: [CallbackQueryHandler(handle_main_menu_choice, pattern='^main_')],
        
        # --- Flujos de Pombot ---
        ADD_SALE_CHOOSE_CATEGORY: [CallbackQueryHandler(sale_choose_category_handler, pattern='^sale_cat_'), CallbackQueryHandler(back_to_main_menu_handler, pattern='^cancel_to_main$')],
        ADD_SALE_CHOOSE_PRODUCT: [CallbackQueryHandler(sale_product_pagination_handler, pattern='^prod_page_'), CallbackQueryHandler(sale_choose_product_handler, pattern='^sale_prod_'), CallbackQueryHandler(start_add_sale, pattern='^back_to_sale_cat_sel$')],
        ADD_SALE_CHOOSE_OPTION_1: [CallbackQueryHandler(sale_choose_option1_handler, pattern='^(sale_opt1_|back_to_prod_sel$)')],
        ADD_SALE_CHOOSE_OPTION_2: [CallbackQueryHandler(sale_choose_option2_handler, pattern='^(sale_opt2_|back_to_opt_1$)')],
        ADD_SALE_INPUT_QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, sale_input_quantity_handler)],
        ADD_SALE_INPUT_CLIENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, sale_input_client_handler)],
        
        ADD_EXPENSE_CHOOSE_CATEGORY: [
            CallbackQueryHandler(expense_choose_category_handler, pattern='^exp_cat_'),
            CallbackQueryHandler(back_to_main_menu_handler, pattern='^cancel_to_main$')
        ],
        ADD_EXPENSE_CHOOSE_SUBCATEGORY: [CallbackQueryHandler(expense_choose_subcategory_handler, pattern='^exp_subcat_'), CallbackQueryHandler(start_add_expense, pattern='^back_to_exp_cat_sel$')],
        ADD_EXPENSE_INPUT_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, expense_input_description_handler)],
        ADD_EXPENSE_CANJE_GET_ENTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, expense_canje_get_entity)],
        ADD_EXPENSE_CANJE_GET_ITEM: [MessageHandler(filters.TEXT & ~filters.COMMAND, expense_canje_get_item)],
        ADD_EXPENSE_CANJE_GET_QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, expense_canje_get_quantity)],
        
        ADD_EXPENSE_PROVEEDORES_GET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, expense_proveedores_get_name)],
        ADD_EXPENSE_PROVEEDORES_GET_ITEM: [MessageHandler(filters.TEXT & ~filters.COMMAND, expense_proveedores_get_item)],
        ADD_EXPENSE_PROVEEDORES_GET_QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, expense_proveedores_get_quantity)],

        ADD_EXPENSE_INPUT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, expense_input_amount_handler)],
        
        QUERY_BALANCE_CHOOSE_YEAR: [CallbackQueryHandler(query_balance_year_handler, pattern='^(balance_year_|balance_current_month)'), CallbackQueryHandler(back_to_main_menu_handler, pattern='^cancel_to_main$')],
        QUERY_BALANCE_CHOOSE_MONTH: [CallbackQueryHandler(query_balance_month_handler, pattern='^(balance_month_|main_query_balance_start)'), CallbackQueryHandler(back_to_main_menu_handler, pattern='^cancel_to_main$')],
        
        DEBT_MENU: [CallbackQueryHandler(debt_menu_handler, pattern='^debt_'), CallbackQueryHandler(back_to_main_menu_handler, pattern='^cancel_to_main$')],
        CREATE_DEBT_GET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_debt_get_name)],
        CREATE_DEBT_GET_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_debt_get_amount)],
        PAY_DEBT_CHOOSE_DEBT: [CallbackQueryHandler(pay_debt_choose_debt, pattern='^pay_debt_id_'), CallbackQueryHandler(start_debt_menu, pattern='^debt_back_to_menu$')],
        PAY_DEBT_GET_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, pay_debt_get_amount)],
        MODIFY_DEBT_CHOOSE_DEBT: [CallbackQueryHandler(modify_debt_choose_debt, pattern='^mod_debt_id_'), CallbackQueryHandler(start_debt_menu, pattern='^debt_back_to_menu$')],
        MODIFY_DEBT_GET_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, modify_debt_get_amount)],

        ADD_WHOLESALE_MENU: [
            CallbackQueryHandler(wholesale_menu_handler, pattern='^wholesale_'),
            CallbackQueryHandler(back_to_main_menu_handler, pattern='^cancel_to_main$')
        ],
        ADD_WHOLESALE_GET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, wholesale_get_name)],
        ADD_WHOLESALE_GET_PRODUCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, wholesale_get_product)],
        ADD_WHOLESALE_GET_QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, wholesale_get_quantity)],
        ADD_WHOLESALE_GET_PAID_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, wholesale_get_paid_amount)],
        ADD_WHOLESALE_GET_TOTAL_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, wholesale_get_total_amount)],
        MODIFY_PAYMENT_CHOOSE_SENA: [
            CallbackQueryHandler(ask_for_modification_amount, pattern='^mod_sena_'),
            CallbackQueryHandler(start_add_wholesale, pattern='^back_to_wholesale_menu$')
        ],
        MODIFY_PAYMENT_GET_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, apply_modification_payment)],
        
        CHECKS_MENU: [
            CallbackQueryHandler(checks_menu_handler, pattern='^check_'),
            CallbackQueryHandler(back_to_main_menu_handler, pattern='^cancel_to_main$')
        ],
        CHECKS_GET_ENTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, checks_get_entity)],
        CHECKS_GET_INITIAL_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, checks_get_initial_amount)],
        CHECKS_GET_COMMISSION: [MessageHandler(filters.TEXT & ~filters.COMMAND, checks_get_commission)],
        CHECKS_GET_DUE_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, checks_get_due_date)],

        FUTURE_PAYMENTS_MENU: [
            CallbackQueryHandler(fp_menu_handler, pattern='^fp_'),
            CallbackQueryHandler(back_to_main_menu_handler, pattern='^cancel_to_main$')
        ],
        FUTURE_PAYMENTS_GET_ENTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, fp_get_entity)],
        FUTURE_PAYMENTS_GET_PRODUCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, fp_get_product)],
        FUTURE_PAYMENTS_GET_QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, fp_get_quantity)],
        FUTURE_PAYMENTS_GET_INITIAL_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, fp_get_initial_amount)],
        FUTURE_PAYMENTS_GET_COMMISSION: [MessageHandler(filters.TEXT & ~filters.COMMAND, fp_get_commission)],
        FUTURE_PAYMENTS_GET_DUE_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, fp_get_due_date)],
    },
    fallbacks=[CommandHandler("cancelar", cancel_command)],
    allow_reentry=True,
    name="pombot_conversation",
    persistent=True
)
