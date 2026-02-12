import unicodedata
from io import BytesIO

def parse_float(text: str) -> float | None:
    """Parses a numeric string supporting both standard ('5000.00') and
    Argentine ('5.000,75') formats.

    Detection logic:
    - If the string contains a comma → Argentine format (dots are thousands separators).
    - If the string has a dot followed by exactly 1-2 digits at the end and
      no other dots → standard decimal (e.g. '5000.00', '12.5').
    - Otherwise → dots are thousands separators (e.g. '5.000', '1.000.000').
    """
    if not isinstance(text, str):
        return None
    cleaned = text.strip()
    if not cleaned:
        return None
    try:
        if ',' in cleaned:
            # Argentine format: dots = thousands, comma = decimal
            return float(cleaned.replace(".", "").replace(",", "."))

        dot_count = cleaned.count('.')
        if dot_count == 1:
            # Single dot: check if it looks like a decimal (1-2 digits after dot)
            _, after_dot = cleaned.rsplit('.', 1)
            digits_after = after_dot.lstrip('-')
            if len(digits_after) <= 2:
                # Standard decimal format (e.g. "5000.00", "12.5")
                return float(cleaned)
            else:
                # Likely a thousands separator (e.g. "5.000" = 5000)
                return float(cleaned.replace(".", ""))
        elif dot_count > 1:
            # Multiple dots = thousands separators (e.g. "1.000.000")
            return float(cleaned.replace(".", ""))
        else:
            # No dots, no commas — plain integer string
            return float(cleaned)
    except ValueError:
        return None

def parse_int(text: str) -> int | None:
    if not isinstance(text, str):
        return None
    try:
        val = parse_float(text)
        return int(val) if val is not None else None
    except (ValueError, TypeError):
        return None

def normalize_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = text.lower().strip()
    nfkd_form = unicodedata.normalize('NFKD', text)
    normalized_text = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    return normalized_text

def generate_confirmation_image(details: dict, title: str) -> BytesIO | None:
    """
    Genera una imagen de confirmación simple.
    TODO: Implementar con Pillow cuando se necesite (pip install Pillow).
    """
    return None

def format_report_line(label: str, value: float, total_width: int = 35) -> str:
    """Formatea una línea para el reporte, alineando el valor a la derecha."""
    formatted_value = f"${value:,.2f}"
    padding = total_width - len(label) - len(formatted_value)
    padding = max(0, padding)
    return f"{label}{' ' * padding}{formatted_value}"
