# Módulo multilingüe HPR
# Proporciona autodetección de idioma, selector de interfaz y enrutamiento
# a los paquetes de traducción (ES, EN, PT).

from .detector import detectar_idioma
from .selector import render_selector_idioma, actualizar_idioma_por_detector
from .router import set_engine, procesar_con_idioma

__all__ = [
    "detectar_idioma",
    "render_selector_idioma",
    "actualizar_idioma_por_detector",
    "set_engine",
    "procesar_con_idioma",
]