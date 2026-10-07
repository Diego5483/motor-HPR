"""Agente de chat del escritorio local: puente entre la interfaz y el núcleo.

Reglas de la Constitución:

- D1: la respuesta es función pura de (consulta, estado, bóveda); misma entrada
  produce la misma respuesta, siempre.
- E5/S2: la generación ocurre 100% en local, sobre la bóveda; el agente puede
  recurrir a búsqueda web externa solo cuando la bóveda no tiene la respuesta,
  pero toda información internet debe pasar por el ValidadorNivelesConfianza.
- P4: las entradas maliciosas se bloquean antes de generar.
- Epsilon Wall: las respuestas de conocimiento se extraen literalmente de la
  bóveda (anti-alucinación por construcción). TODO salida web está sujeta a
  validación de niveles de confianza antes de la emisión.
- D4/Nuevo: el motor evalúa intenciones externas antes de consultar la bóveda
  estática y gestiona resultados web con validación de tres niveles.
"""

import os
import sys
from typing import Optional

# Asegurar que el directorio src esté en el path para importaciones relativas
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import re
from typing import Optional

from ..core.engine import (
    MENSAJE_BLOQUEO_SOVEREIGN_GATE,
    MENSAJE_DENEGACION_NEXUS_ROOT,
    nexus_root_validation,
    sovereign_gate_validation,
    triage_query,
)
from ..models.contracts import CategoriaConsulta, IDENTIDAD_DETERMINISTA
from src.validador_niveles_confianza import ValidadorNivelesConfianza
from src.security_agent import HPRSecurityEngine

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
    """Genera respuestas deterministas del motor HPR para el escritorio local.

    Política de cero alucinaciones:
    - Contexto interno (bóveda CEO / conocimiento HPR) → uso directo (Nivel 1).
    - Si la bóveda no tiene la respuesta → búsqueda web obligatoria.
    - TODO información web pasa por ValidadorNivelesConfianza:
        * Nivel 1 o Nivel 2 (con validación cruzada) → puede utilizarse,
          etiquetada como "Fuente externa validada".
        * Nivel 3 (Baja Confianza) o información insuficiente → el agente
          ESTÁ PROHIBIDO de inventar datos. Debe informar transparentemente al
          usuario solicitando aclaración o re-consulta.
    - D4/Nuevo: el motor evalúa intenciones externas antes de consultar la bóveda
      estática y gestiona resultados web con validación de tres niveles.
    """

    def __init__(
        self,
        knowledge_base: str = "",
        nexus_identity: str = IDENTIDAD_DETERMINISTA,
    ) -> None:
        self.knowledge_base = knowledge_base
        self.nexus_identity = nexus_identity
        self.seguridad = HPRSecurityEngine(nexus_identity=nexus_identity)
        self.validador = ValidadorNivelesConfianza()

    def responder(self, consulta: str, state: dict | None = None) -> dict:
        """Responde una consulta de forma determinista (D1) bajo política de
        cero alucinaciones.

        Flujo actualizado (V2 con gobernanza web):
        1. Validación soberano y Nexus Root.
        2. Triage de la consulta (incluye evaluación de intencion externa).
        3. Búsqueda en bóveda interna HPR.
        4. Si no hay pasaje interno → evaluar necesidad de búsqueda web.
        5. Si requiere web: ejecutar búsqueda, validar por niveles, retornar resultado.
        6. Aplicar regla de cero alucinaciones para todos los casos.
        """
        estado = state if state is not None else {"identity": self.nexus_identity}

        # 1. Validación soberano y Nexus Root
        if not sovereign_gate_validation(consulta):
            return {
                "estado": MENSAJE_BLOQUEO_SOVEREIGN_GATE,
                "requiere_web": False,
                "resultado_web": None,
                "nivel_confianza": None,
                "fuente": "soveraign_gate",
            }

        if not nexus_root_validation(estado, self.nexus_identity):
            return {
                "estado": MENSAJE_DENEGACION_NEXUS_ROOT,
                "requiere_web": False,
                "resultado_web": None,
                "nivel_confianza": None,
                "fuente": "nexus_root",
            }

        # 2. Triage de la consulta (incluye evaluación de intencion externa)
        triaje = triage_query(consulta, self.knowledge_base)

        # 3. Manejo por categoría
        # Si es seguridad, bloquear
        if triaje.categoria is CategoriaConsulta.SEGURIDAD:
            return {
                "estado": f"Consulta clasificada como SEGURIDAD (riesgo {triaje.nivel_riesgo.value}). Motivo: {triaje.razones[0]}. Por política del motor HPR, esta entrada no se procesa.",
                "requiere_web": False,
                "resultado_web": None,
                "nivel_confianza": None,
                "fuente": "triage_seguridad",
            }

        # Si es operativa, retornar estado
        if triaje.categoria is CategoriaConsulta.OPERATIVA:
            return {
                "estado": f"Motor HPR en línea. Identidad: {self.nexus_identity}. Bóveda local: {len(self.knowledge_base)} caracteres.",
                "requiere_web": False,
                "resultado_web": None,
                "nivel_confianza": None,
                "fuente": "triage_operativa",
            }

        # Si es conocimiento
        if triaje.categoria is CategoriaConsulta.CONOCIMIENTO:
            # Verificar si la bóveda tiene pasaje relevante
            pasaje = self._pasaje_mas_relevante(consulta)
            if pasaje is not None:
                # Contexto interno encontrado → Nivel 1 directo (verificado por construcción)
                return {
                    "estado": f"Respuesta extraída de la Bóveda HPR (Nivel 1 - Alta Confianza):\n\n{pasaje}",
                    "requiere_web": False,
                    "resultado_web": None,
                    "nivel_confianza": 1,
                    "fuente": "boveda_nivel1",
                }

            # Bóveda interna no tiene la respuesta → evaluar búsqueda web
            # Aplicar regla: si la consulta tiene señales de externalidad,
            # activar búsqueda web obligatoria
            eval_externa = self.seguridad.evaluar_intencion_consulta(consulta)
            if eval_externa["requiere_externa"]:
                return self.seguridad._ejecutar_busqueda_web(consulta)
            else:
                # Sin señales externas y sin pasaje → información insuficiente
                return {
                    "estado": "No he encontrado información suficiente en la bóveda interna del "
                              "motor HPR, ni puedo recuperar un resultado web validado para tu "
                              "consulta. Por favor, reformula la pregunta o proporciona más "
                              "contexto para que pueda buscar con mayor precisión.",
                    "requiere_web": False,
                    "resultado_web": None,
                    "nivel_confianza": None,
                    "fuente": "insuficiente_datos",
                }

        # Consulta no clasificada
        return {
            "estado": "No reconozco el tipo de consulta. Puedes preguntar por la bóveda HPR, "
                      "el estado del motor o temas de seguridad.",
            "requiere_web": False,
            "resultado_web": None,
            "nivel_confianza": None,
            "fuente": "no_clasificada",
        }

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

    def __repr__(self) -> str:
        return f"AgenteChat(knowledge_base={len(self.knowledge_base)} chars, identity={self.nexus_identity})"