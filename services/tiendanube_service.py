import requests
import logging
from typing import List, Dict, Any, Optional
from config import (
    TIENDANUBE_API_BASE_URL,
    TIENDANUBE_STORE_ID,
    TIENDANUBE_ACCESS_TOKEN,
    TIENDANUBE_USER_AGENT
)
from common.utils import parse_float

logger = logging.getLogger(__name__)

def _get_localized_name(name_obj: Any, prefer_lang: str = 'es') -> str:
    if isinstance(name_obj, dict):
        if prefer_lang in name_obj and name_obj[prefer_lang]: return str(name_obj[prefer_lang])
        for lang_code in ['es_AR', 'es_US', 'es_ES']:
            if lang_code in name_obj and name_obj[lang_code]: return str(name_obj[lang_code])
        for lang_code in name_obj:
            if name_obj[lang_code]: return str(name_obj[lang_code])
    elif isinstance(name_obj, str):
        return name_obj
    return "No disponible"

def get_tiendanube_products() -> List[List[Any]]:
    if not TIENDANUBE_STORE_ID or not isinstance(TIENDANUBE_STORE_ID, int):
        logger.error("TiendaNube Store ID not configured or invalid in config.py.")
        raise ValueError("TiendaNube Store ID no configurado o inválido.")
    if not TIENDANUBE_ACCESS_TOKEN or "your_tiendanube_access_token" in TIENDANUBE_ACCESS_TOKEN:
        logger.error("TiendaNube Access Token not configured in config.py.")
        raise ValueError("TiendaNube Access Token no configurado.")

    all_variants_data_for_sheet: List[List[Any]] = []
    page = 1
    per_page = 50 

    headers = {
        "Authentication": f"bearer {str(TIENDANUBE_ACCESS_TOKEN).strip()}",
        "User-Agent": TIENDANUBE_USER_AGENT
    }
    
    url = f"{TIENDANUBE_API_BASE_URL}{TIENDANUBE_STORE_ID}/products"

    while True:
        params = {"page": page, "per_page": per_page, "fields": "id,name,variants,categories,attributes"}
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            products_page = response.json()
            
            if not products_page: break

            for product in products_page:
                product_name = _get_localized_name(product.get("name", {}))
                product_id = product.get("id") # --- OBTENER ID DEL PRODUCTO PADRE ---
                
                category_name = "General"
                categories = product.get("categories", [])
                if categories:
                    category_name = _get_localized_name(categories[0].get("name", {}))
                attribute_names = [_get_localized_name(attr) for attr in product.get("attributes", [])]

                variants = product.get("variants", [])
                if not variants: continue

                for variant in variants:
                    variant_id = variant.get("id")
                    sku = variant.get("sku") if variant.get("sku") else ""
                    
                    stock: Optional[int]
                    if variant.get("stock_management"):
                        raw_stock = variant.get("stock")
                        stock = int(raw_stock) if raw_stock is not None else 0
                    else:
                        stock = 999 

                    unit_price = parse_float(str(variant.get("price", "0"))) or 0.0
                    promo_price_val = parse_float(str(variant.get("promotional_price")))
                    final_price, fixed_discount, discount_percentage = unit_price, 0.0, 0.0
                    if promo_price_val is not None and 0 < promo_price_val < unit_price:
                        final_price = promo_price_val
                        fixed_discount = unit_price - final_price
                        if unit_price > 0: discount_percentage = (fixed_discount / unit_price) * 100
                    
                    option_values = [_get_localized_name(val) for val in variant.get("values", [])]

                    # --- MODIFICADO: Se añade product_id a la fila ---
                    product_row = [
                        product_name,
                        product_id, # ID del Producto
                        variant_id, # ID de la Variante
                        sku,
                        attribute_names[0] if len(attribute_names) > 0 else "",
                        option_values[0] if len(option_values) > 0 else "",
                        attribute_names[1] if len(attribute_names) > 1 else "",
                        option_values[1] if len(option_values) > 1 else "",
                        attribute_names[2] if len(attribute_names) > 2 else "",
                        option_values[2] if len(option_values) > 2 else "",
                        category_name,
                        stock,
                        round(unit_price, 2),
                        round(discount_percentage, 2),
                        round(fixed_discount, 2),
                        round(final_price, 2)
                    ]
                    all_variants_data_for_sheet.append(product_row)

            page += 1
            if len(products_page) < per_page: break

        except requests.exceptions.RequestException as e:
            logger.error(f"Error en la solicitud a TiendaNube API: {e}", exc_info=True)
            raise ConnectionError(f"Error de conexión con TiendaNube.") from e
        except Exception as e:
            logger.error(f"Error inesperado procesando productos de TiendaNube: {e}", exc_info=True)
            raise RuntimeError(f"Error inesperado con TiendaNube.") from e
            
    logger.info(f"Se obtuvieron un total de {len(all_variants_data_for_sheet)} variantes de productos de TiendaNube.")
    return all_variants_data_for_sheet

# --- NUEVO: Función para obtener stock en tiempo real de una variante ---
def get_realtime_stock(product_id: int, variant_id: int) -> Optional[int]:
    """Consulta la API de TiendaNube para obtener el stock actual de una variante específica."""
    logger.info(f"Consultando stock en tiempo real para producto {product_id}, variante {variant_id}")
    url = f"{TIENDANUBE_API_BASE_URL}{TIENDANUBE_STORE_ID}/products/{product_id}/variants/{variant_id}"
    headers = {
        "Authentication": f"bearer {str(TIENDANUBE_ACCESS_TOKEN).strip()}",
        "User-Agent": TIENDANUBE_USER_AGENT
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get("stock_management"):
            return data.get("stock")
        else:
            return 999 # Representación de stock ilimitado
    except Exception as e:
        logger.error(f"No se pudo obtener el stock en tiempo real para variante {variant_id}: {e}", exc_info=True)
        return None

# --- NUEVO: Función para actualizar el stock en TiendaNube (preparada para el futuro) ---
def update_tiendanube_stock(product_id: int, variant_id: int, new_stock_level: int) -> bool:
    """Actualiza el stock de una variante en TiendaNube."""
    logger.info(f"Intentando actualizar stock en TiendaNube para variante {variant_id} a {new_stock_level}")
    
    url = f"{TIENDANUBE_API_BASE_URL}{TIENDANUBE_STORE_ID}/products/{product_id}/variants/{variant_id}"
    headers = {
        "Authentication": f"bearer {str(TIENDANUBE_ACCESS_TOKEN).strip()}",
        "User-Agent": TIENDANUBE_USER_AGENT,
        "Content-Type": "application/json"
    }
    payload = {"stock": new_stock_level}
    
    try:
        response = requests.put(url, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        logger.info(f"Éxito: Stock de la variante {variant_id} actualizado a {new_stock_level} en TiendaNube.")
        return True
    except Exception as e:
        logger.error(f"FALLO al actualizar stock en TiendaNube para variante {variant_id}: {e}", exc_info=True)
        # Aquí se podría implementar una lógica de reintentos o notificación de error.
        return False