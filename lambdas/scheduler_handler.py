import logging
import asyncio
from telegram import Bot
from sheet import (
    connect_globally_to_sheets, get_items_due_in_x_days, 
    update_past_due_statuses, get_items_due_today,
    add_expense, add_wholesale_record, update_item_status
)
from common.utils import parse_float
from datetime import datetime
from config import BOT_TOKEN, CHAT_ID, CHECKS_SHEET_NAME, FUTURE_PAYMENTS_SHEET_NAME

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def send_alerts():
    if not BOT_TOKEN or not CHAT_ID:
        logger.error("BOT_TOKEN o CHAT_ID no encontrados.")
        return

    bot = Bot(token=BOT_TOKEN)
    if not connect_globally_to_sheets():
        logger.error("No se pudo conectar a Google Sheets para el scheduler.")
        return

    # --- NUEVO: Ejecutamos la actualización de estados ANTES de buscar alertas ---
    update_past_due_statuses()
    
    items_due = get_items_due_in_x_days(days=3)
    
    if not items_due["cheques"] and not items_due["pagos_futuros"]:
        logger.info("No hay vencimientos en los próximos 3 días. No se enviaron alertas.")
        return

    alerts_by_date = {}
    all_items = items_due["cheques"] + items_due["pagos_futuros"]

    for item in all_items:
        due_date_str = item.get("Fecha Cobro", "Sin Fecha")
        try:
            due_date_obj = datetime.strptime(due_date_str, "%d/%m/%Y")
        except ValueError:
            due_date_obj = datetime.now()

        if due_date_obj not in alerts_by_date:
            alerts_by_date[due_date_obj] = []
        
        prefix = "🧾 Cheque" if "CHK" in str(item.get("ID")) else "🗓️ Pago Futuro"
        tipo = item.get("Tipo", "N/A")
        entidad = item.get("Entidad", "N/A")
        monto = parse_float(str(item.get("Monto", 0)))
        arrow = "➡️" if tipo == "EMITIDO" else "⬅️"
        
        alert_line = f"• {prefix} **{tipo}** a/de **{entidad}** por **${monto:,.2f}**"
        alerts_by_date[due_date_obj].append(alert_line)

    # Usamos tu nuevo encabezado
    header = "🚨 Tienes los siguientes vencimientos:\n"
    message_parts = [header]
    
    for date in sorted(alerts_by_date.keys()):
        date_header = date.strftime("%d/%m/%Y")
        message_parts.append(f"\n**{date_header}:**")
        message_parts.extend(alerts_by_date[date])

    final_message = "\n".join(message_parts)
    await bot.send_message(chat_id=CHAT_ID, text=final_message, parse_mode='Markdown')
    logger.info(f"Se envió una alerta con {len(all_items)} vencimientos.")
    
async def daily_tasks():
    if not BOT_TOKEN or not CHAT_ID:
        logger.error("BOT_TOKEN o CHAT_ID no encontrados.")
        return

    bot = Bot(token=BOT_TOKEN)
    if not connect_globally_to_sheets():
        logger.error("No se pudo conectar a Google Sheets para el scheduler.")
        return

    # --- Tarea 1: Actualizar estados de vencidos a "PAGO" ---
    update_past_due_statuses()

    # --- Tarea 2: Procesar los items que vencen hoy y registrarlos ---
    items_to_record = get_items_due_today()
    recorded_items = []

    # Procesar Cheques Emitidos
    for check in items_to_record.get("cheques", []):
        try:
            entity = check.get("Entidad")
            final_amount = parse_float(str(check.get("Monto Final", 0)))
            due_date = datetime.strptime(check.get("Fecha Cobro"), "%d/%m/%Y").strftime("%Y-%m-%d %H:%M:%S")
            
            add_expense(
                category="CHEQUES",
                subcategory=entity,
                description=f"Cobro de cheque a {entity}",
                details="",
                amount=final_amount,
                date_str=due_date
            )
            update_item_status(CHECKS_SHEET_NAME, check.get("ID"), "Conciliado")
            recorded_items.append(f"• ✅ Cheque a {entity} por ${final_amount:,.2f} registrado en Gastos.")
        except Exception as e:
            logger.error(f"Error al registrar cheque {check.get('ID')} como gasto: {e}")

    # Procesar Pagos Futuros Recibidos
    for payment in items_to_record.get("pagos_futuros", []):
        try:
            entity = payment.get("Entidad")
            product = payment.get("Producto") or "Pago Futuro Acreditado"
            quantity = parse_float(str(payment.get("Cantidad", 1))) or 1
            final_amount = parse_float(str(payment.get("Monto Final", 0)))
            due_date = datetime.strptime(payment.get("Fecha Cobro"), "%d/%m/%Y").strftime("%Y-%m-%d %H:%M:%S")

            add_wholesale_record(
                name=entity,
                product=product,
                quantity=int(quantity),
                paid_amount=final_amount,
                total_amount=final_amount,
                category="PAGO",
                date_str=due_date
            )
            update_item_status(FUTURE_PAYMENTS_SHEET_NAME, payment.get("ID"), "Conciliado")
            recorded_items.append(f"Pago de {entity} ({product} x{int(quantity)}) por ${final_amount:,.2f} registrado en Mayoristas.")
        except Exception as e:
            logger.error(f"Error al registrar pago futuro {payment.get('ID')} como mayorista: {e}")

# --- Tarea 3: Enviar Alertas de Próximos Vencimientos ---
    items_due_for_alert = get_items_due_in_x_days(days=3)
    # ... (el código de envío de alertas no cambia)

    # --- Tarea 4: Enviar un reporte de las acciones automáticas (opcional pero recomendado) ---
    if recorded_items:
        report_header = "📄 **Reporte de Conciliación Automática:**\n\n"
        report_message = report_header + "\n".join(recorded_items)
        await bot.send_message(chat_id=CHAT_ID, text=report_message, parse_mode='Markdown')

def lambda_handler(event, context):
    logger.info("Iniciando ejecución de tareas diarias de Pombot...")
    asyncio.run(daily_tasks())
    logger.info("Finalizada ejecución de tareas diarias de Pombot.")
    return {'status': 200, 'body': 'Scheduler executed'}