"""Agente de chat del escritorio local: puente entre la interfaz y el núcleo.

Reglas de la Constitución:

- D1: la respuesta es función pura de (consulta, estado, bóveda);
  misma entrada produce la misma respuesta, siempre.
- E5/S2: la generación ocurre 100% en local, sobre la bóveda.
- P4: las entradas maliciosas se bloquean antes de generar.
- Epsilon Wall: las respuestas de conocimiento se extraen
  literalmente de la bóveda (anti-alucinación por construcción).
"""

import re

from ..core.engine import (
    MENSAJE_BLOQUEO_SOVEREIGN_GATE,
    MENSAJE_DENEGACION_NEXUS_ROOT,
    nexus_root_validation,
    sovereign_gate_validation,
)
from ..core.triage import triage_query
from ..models.contracts import CategoriaConsulta, IDENTIDAD_DETERMINISTA

#: Longitud mínima de un término de búsqueda en la bóveda.
_LONGITUD_MINIMA_TERMINO = 4


def _terminos(consulta: str) -> list[str]:
    """Extrae términos de búsqueda en minúsculas (determinista)."""
    return [
        termino
        for termino in re.findall(r"\w+", consulta.lower())
        if len(termino) >= _LONGITUD_MINIMA_TERMINO
    ]


class AgenteChat:
    """Genera respuestas deterministas del motor HPR para el escritorio local."""

    def __init__(
        self,
        knowledge_base: str = "",
        nexus_identity: str = IDENTIDAD_DETERMINISTA,
    ) -> None:
        self.knowledge_base = knowledge_base
        self.nexus_identity = nexus_identity

    def responder(self, consulta: str, state: dict | None = None) -> str:
        """Responde una consulta de forma determinista (D1)."""
        estado = state if state is not None else {"identity": self.nexus_identity}

        if not sovereign_gate_validation(consulta):
            return MENSAJE_BLOQUEO_SOVEREIGN_GATE
        if not nexus_root_validation(estado, self.nexus_identity):
            return MENSAJE_DENEGACION_NEXUS_ROOT

        triaje = triage_query(consulta)

        if triaje.categoria is CategoriaConsulta.SEGURIDAD:
            return (
                f"Consulta clasificada como SEGURIDAD (riesgo {triaje.nivel_riesgo.value}). "
                f"Motivo: {triaje.razones[0]}. "
                "Por política del motor HPR, esta entrada no se procesa."
            )
        if triaje.categoria is CategoriaConsulta.OPERATIVA:
            return (
                f"Motor HPR en línea. Identidad: {self.nexus_identity}. "
                f"Bóveda local: {len(self.knowledge_base)} caracteres."
            )
        if triaje.categoria is CategoriaConsulta.CONOCIMIENTO:
            pasaje = self._pasaje_mas_relevante(consulta)
            if pasaje is None:
                return (
                    "No encontré un pasaje en la bóveda que coincida con tu consulta. "
                    "Reformula con términos de la documentación HPR."
                )
            return f"Respuesta extraída de la Bóveda HPR:\n\n{pasaje}"

        return (
            "No reconozco el tipo de consulta. Puedes preguntar por la bóveda HPR, "
            "el estado del motor o temas de seguridad."
        )

    def _pasaje_mas_relevante(self, consulta: str) -> str | None:
        """Selecciona el pasaje de la bóveda con más coincidencias (D1).

        El desempate es determinista: a igual puntaje, gana el
        primer pasaje del corpus.
        """
        terminos = _terminos(consulta)
        if not terminos or not self.knowledge_base:
            return None

        mejor_puntaje = 0
        mejor_pasaje: str | None = None
        for pasaje in self.knowledge_base.split("\n"):
            pasaje = pasaje.strip()
            if not pasaje:
                continue
            minusculas = pasaje.lower()
            puntaje = sum(1 for termino in terminos if termino in minusculas)
            if puntaje > mejor_puntaje:
                mejor_puntaje = puntaje
                mejor_pasaje = pasaje
        return mejor_pasaje if mejor_puntaje > 0 else None
