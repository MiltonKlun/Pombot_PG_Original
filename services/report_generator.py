# services/report_generator.py
import logging
import os
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from datetime import datetime
import io
import requests
from config import BRAND_COLORS

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ASSETS_DIR = os.path.join(_PROJECT_ROOT, "assets")

logger = logging.getLogger(__name__)

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

class PDFReport(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 12)
        self.cell(0, 10, 'Reporte de Balance Mensual - Pombot',
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        logo_width = 20
        page_width = self.w
        margin = 10
        logo_x_position = page_width - logo_width - margin

        try:
            self.image(os.path.join(_ASSETS_DIR, 'logo.png'), x=logo_x_position, y=8, w=logo_width)
        except (FileNotFoundError, EnvironmentError):
            logger.warning("No se encontró 'logo.png' o Pillow no disponible. El reporte se generará sin logo.")

        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}',
                  new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')

def _create_bar_chart(
    data: dict, title: str, buffer: io.BytesIO, color_hex: str = '#c0392b',
    width: int = 800, height: int = 500, title_font_size: int = 28,
    label_font_size: int = 18, bar_thickness: int = 32
):
    if not data:
        return
    sorted_data = dict(sorted(data.items(), key=lambda item: item[1], reverse=True))
    chart_config = {
        'type': 'horizontalBar',
        'data': {
            'labels': list(sorted_data.keys()),
            'datasets': [{
                'data': list(sorted_data.values()),
                'backgroundColor': color_hex,
                'barThickness': bar_thickness
            }]
        },
        'options': {
            'layout': {'padding': {'right': 90}},
            'legend': {'display': False},
            'title': {'display': True, 'text': title, 'font': {'size': title_font_size}},
            'plugins': {
                'datalabels': {
                    'anchor': 'end', 'align': 'right', 'offset': 8,
                    'color': 'black',
                    'font': {'size': label_font_size, 'weight': 'bold'},
                    'formatter': "(value) => { return value.toLocaleString('es-AR'); }"
                }
            },
            'scales': {
                'xAxes': [{'ticks': {'beginAtZero': True, 'font': {'size': label_font_size - 4}}}],
                'yAxes': [{'ticks': {'font': {'size': label_font_size}}}]
            }
        }
    }
    try:
        response = requests.post(
            'https://quickchart.io/chart',
            json={'chart': chart_config, 'backgroundColor': 'white', 'width': width, 'height': height},
            timeout=10
        )
        response.raise_for_status()
        buffer.write(response.content)
        buffer.seek(0)
    except requests.exceptions.RequestException as e:
        logger.error(f"Error al contactar QuickChart.io para el gráfico de barras '{title}': {e}")


def generate_balance_pdf(balance_data: dict) -> str:
    try:
        pdf = PDFReport()
        pdf.add_page()

        month_name = balance_data.get('month_name', 'N/A')
        year = balance_data.get('year', 'N/A')

        # --- Título ---
        pdf.set_font('Helvetica', 'B', 22)
        pdf.set_text_color(*hex_to_rgb(BRAND_COLORS['primary_dark']))
        pdf.cell(0, 10, f"Balance para {month_name} {year}",
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
        pdf.set_font('Helvetica', '', 11)
        pdf.set_text_color(*hex_to_rgb(BRAND_COLORS['text_gray']))
        pdf.cell(0, 5, f"Generado el: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
        pdf.ln(10)

        pdf.set_font('Helvetica', 'B', 14)
        pdf.set_text_color(*hex_to_rgb(BRAND_COLORS['primary_dark']))
        pdf.cell(0, 10, "Resumen General",
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')

        summary_items = {
            "Total Ventas": balance_data.get("sales_summary", {}).get("total", 0),
            "Total Mayoristas": balance_data.get("wholesale_summary", {}).get("total", 0),
            "Total Gastos (PG)": balance_data.get("gastos_pg_summary", {}).get("total", 0),
            "Total Gastos (Personales)": balance_data.get("gastos_personales_summary", {}).get("total", 0),
            "SALDO PG": balance_data.get("saldo_pg", 0),
            "SALDO NETO": balance_data.get("saldo_neto", 0)
        }

        pdf.set_fill_color(*hex_to_rgb(BRAND_COLORS['light_gray']))
        for label, value in summary_items.items():
            pdf.set_font('Helvetica', '', 10)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(95, 8, label, border=1,
                     new_x=XPos.RIGHT, new_y=YPos.TOP, align='L', fill=True)
            pdf.set_font('Helvetica', 'B', 10)
            pdf.cell(95, 8, f"${value:,.2f}", border=1,
                     new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='R')
        pdf.ln(10)

        # --- Gráfico de Gastos ---
        expenses_data = {k: v for k, v in balance_data.get("gastos_pg_summary", {}).get("by_category", {}).items() if v > 0}
        if expenses_data:
            expense_buffer = io.BytesIO()
            expense_chart_height = 120 + (len(expenses_data) * 40)
            _create_bar_chart(
                data=expenses_data, title="Distribución de Gastos (PG)", buffer=expense_buffer,
                width=800, height=expense_chart_height, color_hex=BRAND_COLORS['expense']
            )
            if expense_buffer.getbuffer().nbytes > 0:
                if pdf.get_y() + (expense_chart_height / 4) > pdf.page_break_trigger:
                     pdf.add_page()
                pdf.image(expense_buffer, x=10, w=pdf.w - 20)

        # --- Tablas de Detalle ---
        def create_detail_table(title, data):
            if not data: return
            pdf.add_page()
            pdf.set_font('Helvetica', 'B', 16)
            pdf.set_text_color(*hex_to_rgb(BRAND_COLORS['primary_dark']))
            pdf.cell(0, 10, title,
                     new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')

            pdf.set_font('Helvetica', 'B', 10)
            pdf.set_fill_color(*hex_to_rgb(BRAND_COLORS['primary_dark']))
            pdf.set_text_color(255, 255, 255)
            pdf.cell(130, 8, "Categoría", border=1,
                     new_x=XPos.RIGHT, new_y=YPos.TOP, align='C', fill=True)
            pdf.cell(60, 8, "Monto", border=1,
                     new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C', fill=True)

            pdf.set_font('Helvetica', '', 10)
            pdf.set_text_color(0, 0, 0)
            fill = False
            for category, total in sorted(data.items()):
                pdf.set_fill_color(*hex_to_rgb(BRAND_COLORS['light_gray']))
                pdf.cell(130, 8, f"      {category}", border=1,
                         new_x=XPos.RIGHT, new_y=YPos.TOP, align='L', fill=fill)
                pdf.cell(60, 8, f"${total:,.2f}", border=1,
                         new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='R', fill=fill)
                fill = not fill

        create_detail_table("Detalle de Ventas", balance_data.get("sales_summary", {}).get("by_category", {}))
        wholesale_summary_data = balance_data.get("wholesale_summary", {})
        wholesale_details_list = wholesale_summary_data.get("details", [])
        wholesale_by_client = wholesale_summary_data.get("by_client", {})

        if wholesale_details_list:
            pdf.add_page()
            pdf.set_font('Helvetica', 'B', 16)
            pdf.set_text_color(*hex_to_rgb(BRAND_COLORS['primary_dark']))
            pdf.cell(0, 10, "Detalle de Mayoristas (Operaciones)",
                     new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')

            pdf.set_font('Helvetica', 'B', 10)
            pdf.set_fill_color(*hex_to_rgb(BRAND_COLORS['primary_dark']))
            pdf.set_text_color(255, 255, 255)

            # Anchos de columna: Mayorista (40), Producto (60), Cantidad (30), Monto (60) = 190 total
            pdf.cell(40, 8, "Mayorista", border=1,
                     new_x=XPos.RIGHT, new_y=YPos.TOP, align='C', fill=True)
            pdf.cell(60, 8, "Producto", border=1,
                     new_x=XPos.RIGHT, new_y=YPos.TOP, align='C', fill=True)
            pdf.cell(30, 8, "Cant.", border=1,
                     new_x=XPos.RIGHT, new_y=YPos.TOP, align='C', fill=True)
            pdf.cell(60, 8, "Monto", border=1,
                     new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C', fill=True)

            pdf.set_font('Helvetica', '', 9)  # Fuente un poco más chica para que entre todo
            pdf.set_text_color(0, 0, 0)
            fill = False

            # Ordenar por nombre de cliente para agrupar visualmente
            sorted_details = sorted(wholesale_details_list, key=lambda x: x['client'])

            for item in sorted_details:
                pdf.set_fill_color(*hex_to_rgb(BRAND_COLORS['light_gray']))

                # Truncar textos largos
                client_text = (item['client'][:18] + '..') if len(item['client']) > 20 else item['client']
                product_text = (item['product'][:28] + '..') if len(item['product']) > 30 else item['product']

                pdf.cell(40, 8, f" {client_text}", border=1,
                         new_x=XPos.RIGHT, new_y=YPos.TOP, align='L', fill=fill)
                pdf.cell(60, 8, f" {product_text}", border=1,
                         new_x=XPos.RIGHT, new_y=YPos.TOP, align='L', fill=fill)
                pdf.cell(30, 8, str(item['quantity']), border=1,
                         new_x=XPos.RIGHT, new_y=YPos.TOP, align='C', fill=fill)
                pdf.cell(60, 8, f"${item['amount']:,.2f}", border=1,
                         new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='R', fill=fill)
                fill = not fill

        elif wholesale_by_client:
            # Fallback para compatibilidad si no hay detalles
            pdf.add_page()
            pdf.set_font('Helvetica', 'B', 16)
            pdf.set_text_color(*hex_to_rgb(BRAND_COLORS['primary_dark']))
            pdf.cell(0, 10, "Detalle de Mayoristas (Resumen)",
                     new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')

            pdf.set_font('Helvetica', 'B', 10)
            pdf.set_fill_color(*hex_to_rgb(BRAND_COLORS['primary_dark']))
            pdf.set_text_color(255, 255, 255)
            pdf.cell(100, 8, "Mayorista", border=1,
                     new_x=XPos.RIGHT, new_y=YPos.TOP, align='C', fill=True)
            pdf.cell(30, 8, "Cantidad", border=1,
                     new_x=XPos.RIGHT, new_y=YPos.TOP, align='C', fill=True)
            pdf.cell(60, 8, "Monto", border=1,
                     new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C', fill=True)

            pdf.set_font('Helvetica', '', 10)
            pdf.set_text_color(0, 0, 0)
            fill = False
            for client, data in sorted(wholesale_by_client.items()):
                pdf.set_fill_color(*hex_to_rgb(BRAND_COLORS['light_gray']))
                pdf.cell(100, 8, f"      {client}", border=1,
                         new_x=XPos.RIGHT, new_y=YPos.TOP, align='L', fill=fill)
                pdf.cell(30, 8, str(data.get("quantity", 0)), border=1,
                         new_x=XPos.RIGHT, new_y=YPos.TOP, align='R', fill=fill)
                pdf.cell(60, 8, f"${data.get('amount', 0):,.2f}", border=1,
                         new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='R', fill=fill)
                fill = not fill
        create_detail_table("Detalle de Gastos PG", balance_data.get("gastos_pg_summary", {}).get("by_category", {}))
        create_detail_table("Detalle de Gastos Personales", balance_data.get("gastos_personales_summary", {}).get("by_category", {}))

        pdf_file_path = f"/tmp/Balance_{month_name}_{year}.pdf"
        pdf.output(pdf_file_path)
        return pdf_file_path

    except Exception as e:
        logger.error(f"Error generando el reporte PDF: {e}", exc_info=True)
        return None
