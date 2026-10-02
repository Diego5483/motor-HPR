"""Triaje determinista de consultas del motor HPR (Reglas D1 y D2).

Clasifica consultas entrantes por categoría y nivel de riesgo mediante
reglas puras y ordenadas: sin reloj, sin red, sin azar. El orden de
evaluación es fijo (seguridad primero) y forma parte del contrato.
"""

from ..models.contracts import CategoriaConsulta, NivelRiesgo, TriageResult
from .engine import PATRONES_SOVEREIGN_GATE
from .security_agent import inspect_for_phishing

#: Señales deterministas de consulta operativa (estado del sistema).
SENALES_OPERATIVAS = ("estado", "estatus", "en línea", "latencia", "rendimiento", "salud")

#: Señales deterministas de consulta de conocimiento (preguntas).
SENALES_CONOCIMIENTO = ("qué", "cuál", "cómo", "por qué", "cuándo", "dónde", "quién")


def triage_query(query: str | None) -> TriageResult:
    """Clasifica una consulta de forma determinista (D1: misma entrada, misma salida).

    Orden de reglas (primero lo más crítico):
    1. Ingesta maliciosa (patrones Sovereign Gate) -> SEGURIDAD/CRÍTICO.
    2. Phishing (guardia de seguridad) -> SEGURIDAD/ALTO.
    3. Señales operativas -> OPERATIVA/BAJO.
    4. Señales de conocimiento -> CONOCIMIENTO/BAJO.
    5. Sin señales reconocidas -> DESCONOCIDA/MEDIO (precaución).
    """
    texto = (query or "").strip()

    if not texto:
        return TriageResult(
            categoria=CategoriaConsulta.DESCONOCIDA,
            nivel_riesgo=NivelRiesgo.MEDIO,
            razones=["consulta vacía"],
        )

    patron = next((p for p in PATRONES_SOVEREIGN_GATE if p in texto), None)
    if patron is not None:
        return TriageResult(
            categoria=CategoriaConsulta.SEGURIDAD,
            nivel_riesgo=NivelRiesgo.CRITICO,
            razones=[f"patrón de ingesta bloqueado detectado: {patron}"],
        )

    if inspect_for_phishing(texto):
        return TriageResult(
            categoria=CategoriaConsulta.SEGURIDAD,
            nivel_riesgo=NivelRiesgo.ALTO,
            razones=["coincidencia con patrón de phishing"],
        )

    minusculas = texto.lower()
    senales = [s for s in SENALES_OPERATIVAS if s in minusculas]
    if senales:
        return TriageResult(
            categoria=CategoriaConsulta.OPERATIVA,
            nivel_riesgo=NivelRiesgo.BAJO,
            razones=[f"señal operativa: {s}" for s in senales],
        )

    senales = [s for s in SENALES_CONOCIMIENTO if s in minusculas]
    if senales:
        return TriageResult(
            categoria=CategoriaConsulta.CONOCIMIENTO,
            nivel_riesgo=NivelRiesgo.BAJO,
            razones=[f"señal de conocimiento: {s}" for s in senales],
        )

    return TriageResult(
        categoria=CategoriaConsulta.DESCONOCIDA,
        nivel_riesgo=NivelRiesgo.MEDIO,
        razones=["sin señales reconocidas"],
    )
