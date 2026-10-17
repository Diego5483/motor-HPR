"""Regresión G.1 — Desacople del chat respecto al motor forense.

Fase G (corrección controlada). Causa raíz (Fase E): el chat podía terminar
en `DeepSynthesizer` ("Análisis técnico profundo de: …") porque
`_extract_hallazgos_from_query` NUNCA devolvía una lista vacía (relleno forzado
con los primeros párrafos del corpus), lo que garantizaba la ruta de síntesis.

Estas pruebas FALLAN antes de la corrección y PASAN después:
- Antes: `_extract_hallazgos_from_query` devolvía 3 hallazgos "general" (0.6);
  `_generar_introduccion([], …)` devolvía "Análisis de: …".

Reglas (Constitución HPR): P1 (prueba o no existe), P3 (deterministas, sin red),
P7 (no mutan).
"""

import sys
from pathlib import Path

# Convención del proyecto (ver run.py y test_etapa_d.py): HPR/ y HPR/src/ en path.
_HPR_DIR = Path(__file__).resolve().parent.parent
_SRC_DIR = _HPR_DIR / "src"
for _path in (str(_HPR_DIR), str(_SRC_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from src.main import (  # noqa: E402
    _build_hpr_corpus,
    _generate_contextual_response,
    _extract_hallazgos_from_query,
)
from src.core.deep_synthesizer import DeepSynthesizer  # noqa: E402


# Entrada sin ninguna coincidencia de intención ni término técnico.
_SIN_COINCIDENCIA = "zzz qwerty asdf sin coincidencia"


def test_no_fabrica_hallazgos_sin_coincidencia():
    """Sin intención real, el extractor NO debe inventar hallazgos."""
    hallazgos = _extract_hallazgos_from_query(_SIN_COINCIDENCIA, _build_hpr_corpus())
    assert hallazgos == []


def test_corpus_no_vacio_para_control():
    """Control: el corpus existe, así que la lista vacía no es por falta de corpus."""
    assert len(_build_hpr_corpus()) > 100


def test_entrada_sin_coincidencia_no_emite_informe_forense():
    """El chat no debe responder con el encabezado forense."""
    respuesta = _generate_contextual_response(_SIN_COINCIDENCIA, {})
    assert "Análisis técnico profundo" not in respuesta
    assert "Análisis de:" not in respuesta


def test_saludo_no_emite_informe_forense():
    """Un saludo simple nunca debe ser 'secuestrado' por el motor forense."""
    respuesta = _generate_contextual_response("hola", {})
    assert "Análisis técnico profundo" not in respuesta
    assert "Análisis de:" not in respuesta


def test_sintetizador_sin_hallazgos_no_emite_encabezado():
    """`_generar_introduccion` no debe producir encabezado sin evidencia."""
    sintetizador = DeepSynthesizer(min_confianza=0.2)
    assert sintetizador._generar_introduccion("q", [], 0) == ""
