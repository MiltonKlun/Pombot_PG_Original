from datetime import datetime
import locale

print("INFO: Cargando definiciones de negocio...")

BRAND_COLORS = {
    'primary_dark': '#2c3e50',
    'income': '#27ae60',
    'expense': '#c0392b',
    'net_balance': '#2980b9',
    'light_gray': '#ecf0f1',
    'text_gray': '#7f8c8d'
}

# --- Constantes de Hojas de Cálculo ---
RESTART_PROMPT = "\n\nPuedes presionar /start en cualquier momento para reiniciar."
SALES_SHEET_BASE_NAME = "Ventas"
EXPENSES_SHEET_BASE_NAME = "Gastos"
PRODUCTOS_SHEET_NAME = "Productos"
DEBTS_SHEET_NAME = "Deudas"
WHOLESALE_SHEET_BASE_NAME = "Mayoristas"
WEBHOOK_LOGS_SHEET_NAME = "Webhook_Logs"
PROCESSED_EVENTS_SHEET_NAME = "Processed_Events"
CHECKS_SHEET_NAME = "Cheques"
FUTURE_PAYMENTS_SHEET_NAME = "Pagos Futuros"

# --- Cabeceras de Hojas de Cálculo ---
SALES_HEADERS = ["Fecha", "Producto", "Variante", "Cliente", "Categoría", "Cantidad", "Precio Unitario", "%", "Descuento", "Precio Total"]
EXPENSES_HEADERS = ["Fecha", "Categoría", "Subcategoría", "Descripción Principal", "Detalles Adicionales", "Monto"]
PRODUCTOS_HEADERS = ["Producto", "ID Producto", "ID Variante", "SKU", "Opción 1: Nombre", "Opción 1: Valor", "Opción 2: Nombre", "Opción 2: Valor", "Opción 3: Nombre", "Opción 3: Valor", "Categoría", "Stock", "Precio Unitario", "%", "Descuento", "Precio Final"]
DEBTS_HEADERS = ["ID Deuda", "Nombre", "Monto Inicial", "Monto Pagado", "Saldo Pendiente", "Estado", "Fecha Creación", "Fecha Último Pago"]
WHOLESALE_HEADERS = ["Fecha", "Nombre", "Producto", "Cantidad", "Monto Total", "Monto Pagado", "Monto Restante", "Categoría"]
PROCESSED_EVENTS_HEADERS = ["EventID", "Timestamp"]

CHECKS_HEADERS = ["ID", "Fecha Cobro", "Entidad", "Monto Inicial", "Impuesto", "Comision", "Monto Final", "Estado"]
FUTURE_PAYMENTS_HEADERS = ["ID", "Fecha Cobro", "Entidad", "Producto", "Cantidad", "Monto Inicial", "Comision", "Monto Final", "Estado"]

# --- Categorias y Subcategorias ---
EXPENSE_CATEGORIES = ["INSUMOS", "PROVEEDORES", "TALLERES", "DISEÑADOR", "FOTOGRAFO", "TIENDANUBE", "CADETERIA", "ARCA", "MARKETING", "VIATICOS", "SERVICIOS", "PERSONALES", "CANJES", "VARIOS"]
EXPENSE_SUBCATEGORIES = { "INSUMOS": ["ESTAMPAS", "GENERAL"], "TALLERES": ["BORDADOS", "GENERAL"], "DISEÑADOR": ["PG", "LOGO", "GENERAL"], "FOTOGRAFO": ["CARRERAS", "PRODUCCION", "GENERAL"], "TIENDANUBE": ["MENSUAL", "GENERAL"], "CADETERIA": ["UBER", "CORREO", "GENERAL"], "MARKETING": ["INFLUENCERS", "PROMOCIONES", "IG ANUNCIOS", "GENERAL"], "VIATICOS": ["CARRERAS", "EVENTOS", "GENERAL"], "PERSONALES": ["LUZ", "AGUA", "INTERNET", "ALQUILER", "EXPENSAS", "SEGURO", "COMBUSTIBLE", "COMIDA", "SALIDAS", "TARJETAS", "GENERAL"]}

SPANISH_MONTHS = { 1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"}

def get_sheet_name_for_month(base_name: str, year: int, month: int) -> str:
    month_name = SPANISH_MONTHS.get(month, "MesInvalido")
    return f"{base_name} {month_name} {year}"
