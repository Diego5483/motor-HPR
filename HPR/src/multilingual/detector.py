"""Autodetección de idioma para consultas HPR.

Detecta el idioma basándose en señales lexicas características
del español, inglés y portugués. Retorna 'es', 'en', 'pt' o 'unknown'
si no se pueden detectar señales claras.
"""

import re
from typing import Literal

# Patrones para detección rápida de idioma por señales características
ES_PATTERNS = [
    r"\b(hola|que|cómo|cuánto|dónde|cuándo|por qué|la|el|los|las)\b",
    r"\b(hasta|con|sin|por|para|de|en|un|una)\b",
]

EN_PATTERNS = [
    r"\b(hello|what|how|where|when|why)\b",
    r"\b(the|a|an|to|of|for|and|is|are|was|were)\b",
    r"\b(I|you|we|they|it)\b",
]

PT_PATTERNS = [
    r"\b(olá|como|onde|por que|quanto|você|se|para|com|com)\b",
    r"\b(olá|como|você)\b",
]


def detectar_idioma(consulta: str) -> Literal["es", "en", "pt", "unknown"]:
    """
    Detecta el idioma de una consulta basándose en señales lexicas.

    Retorna:
        - 'es' si se detectan señales en español
        - 'en' si se detectan señales en inglés
        - 'pt' si se detectan señales en portugués
        - 'unknown' si no se pueden detectar señales claras
    """
    if not consulta:
        return "unknown"

    consulta_lower = consulta.lower()

    # Contar coincidencias por idioma
    es_score = sum(1 for p in ES_PATTERNS if re.search(p, consulta_lower))
    en_score = sum(1 for p in EN_PATTERNS if re.search(p, consulta_lower))
    pt_score = sum(1 for p in PT_PATTERNS if re.search(p, consulta_lower))

    # Umbral: mínimo 1 señal fuerte para declarar idioma
    if es_score >= 1:
        return "es"
    elif en_score >= 1:
        return "en"
    elif pt_score >= 1:
        return "pt"
    else:
        return "unknown"


# Diccionario de puntajes por si se quiere lógica más compleja más adelante
PATTERNS_BY_LANGUAGE = {
    "es": ES_PATTERNS,
    "en": EN_PATTERNS,
    "pt": PT_PATTERNS,
}

JUSTIFICATIONS = {
    "es": "Señales lexicas españolas detectadas",
    "en": "English lexical signals detected",
    "pt": "Sinais lexicos em português detectados",
    "unknown": "No se detectaron señales idiomáticas claras",
}