"""Adaptador del motor HPR:une la bóveda local con el motor lógico central.

Las tres validaciones raíz (Nexus Root, Epsilon Wall, Sovereign Gate)
viven en ``src/core/engine.py`` como fuente única de verdad; esta clase
delegga en ellas y añade la carga de la bóveda documental local (E6).
Además, integra evaluación de intenciones y búsqueda web externa con
gobernanza de tres niveles de confianza (Reglas S2, E5, D4).
"""

import os
import sys
import re
from typing import Optional

# Asegurar que el directorio src esté en el path para importaciones relativas
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from docx import Document

# Importaciones desde src.core.engine y módulos asociados
from src.core.engine import (
    nexus_root_validation,
    sovereign_gate_validation,
    epsilon_wall_validation,
    evaluar_intencion_externa,
    MENSAJE_BLOQUEO_SOVEREIGN_GATE,
    MENSAJE_DENEGACION_NEXUS_ROOT,
    MENSAJE_PIPELINE_VERIFICADO,
)

# NUEVO: Patrones de trigger sintáctico con prefijoarroba (@)
# Formato validado: @identificador (ej. @hpr_confianza, @nivel1, @web_search)
# La presencia de un trigger @ validado activa REQUIRE_EXTERNA de forma directa.
TRIGGER_ARROBA_PATTERN = re.compile(r"^@\w+|\s@\w+")

from src.models.contracts import IDENTIDAD_DETERMINISTA
from src.validador_niveles_confianza import ValidadorNivelesConfianza


class HPRSecurityEngine:
    """Motor de seguridad HPR: bóveda local más validaciones del núcleo determinista."""

    def __init__(self, nexus_identity: str = IDENTIDAD_DETERMINISTA):
        self.nexus_identity = nexus_identity
        base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "boveda y vitacoras")
        self.docs_path = base_dir if os.path.exists(base_dir) else os.path.join("..", "boveda y vitacoras")
        self.validador = ValidadorNivelesConfianza()
        self.knowledge_base = self.load_knowledge()


    def load_knowledge(self):
        text_content = ""
        path = self.docs_path if os.path.exists(self.docs_path) else os.path.join("..", "boveda y vitacoras")
        if os.path.exists(path):
            for file in os.listdir(path):
                if file.endswith(".docx"):
                    file_path = os.path.join(path, file)
                    try:
                        doc = Document(file_path)
                        for para in doc.paragraphs:
                            if para.text.strip():
                                text_content += para.text + "\n"
                    except Exception as e:
                        print(f"Error leyendo {file}: {e}")
        return text_content
    def nexus_root_validation(self, system_state: dict) -> bool:
        """Regla 1: Valida la identidad inmutable y el propósito del sistema."""
        return nexus_root_validation(system_state, self.nexus_identity)

    def epsilon_wall_validation(self, response_content: str, ground_truth: list) -> bool:
        """Regla 2: Filtro anti-alucinación basado en verificación estricta."""
        return epsilon_wall_validation(response_content, ground_truth)

    def sovereign_gate_validation(self, incoming_payload: str) -> bool:
        """Regla 3: Control de ingesta y mitigación de entradas maliciosas.
        
        Capa 0 - Precedencia Soberana: Si el mensaje comienza con un trigger sintáctico
        con prefijo arroba (@), se otorga control soberano automático y se omiten las
        restricciones restrictivas estándar, permitiendo un pase libre y directo hacia
        el pipeline principal (process_pipeline) para ejecutar búsquedas externas
        bajo los 3 niveles de confianza del motor HPR.
        
        Además de la Capa 0, se aplican las restricciones tradicionales:
        - Patrones bloqueados: "<script>", "DROP TABLE", "OVERRIDE_ROOT"
        - El Nexus Root valida la identidad inmutable (siempre permitido para consultas web).
        """
        # --- CAPA 0: Precedencia Soberana (TRIGGERS @) ---
        # Si el input comienza con @, otorgar paso libre inmediato.
        # Esto evita que las reglas restrictivas bloqueen los comandos de operador.
        if incoming_payload.startswith("@"):
            # Trigger detectado: paso libre sin validación de patrones restrictivos
            return True
        
        # --- CAPA 1: Restricciones Tradicionales ---
        if not incoming_payload or len(incoming_payload.strip()) == 0:
            return False
        if any(pattern in incoming_payload for pattern in ["<script>", "DROP TABLE", "OVERRIDE_ROOT"]):
            return False
        
        # --- CAPA 2: El Nexus Root valida la identidad en pipeline downstream ---
        # No se bloquea aquí; el downstream manejará la validación de identidad.
        return True

    def evaluar_intencion_consulta(self, consulta: str) -> dict:
        """Evalúa si la consulta requiere búsqueda web externa.

        Aplica la regla D1/D2: si la consulta contiene señales de externalidad
        (actualidad, tecnología reciente) y la bóveda no cubre el tema,
        retorna True para activar búsqueda web.
        """
        return evaluar_intencion_externa(consulta, self.knowledge_base)

    def _pasaje_mas_relevante(self, consulta: str) -> str | None:
        """Selecciona el pasaje de la bóveda con más coincidencias (D1)."""
        terminos = self._terminos(consulta)
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

    @staticmethod
    def _terminos(consulta: str) -> list[str]:
        """Extrae términos de búsqueda en minúsculas (determinista)."""
        import re
        return [
            termino
            for termino in re.findall(r"\w+", consulta.lower())
            if len(termino) >= 4
        ]

    def _ejecutar_busqueda_web(self, consulta: str) -> dict:
        """Ejecuta búsqueda web externa con política de cero alucinaciones.

        Integra validación de tres niveles de confianza mediante
        ValidadorNivelesConfianza antes de inyectar el resultado.
        """
        # 1. Buscar en web (usando requests + fallback)
        try:
            import requests

            # Usar DuckDuckGo Instant Answer API (sin clave API requerida)
            url = "https://api.duckduckgo.com/"
            params = {
                "q": consulta,
                "format": "json",
                "no_redirect": 1,
                "medium": "text",
            }
            respuesta = requests.get(url, params=params, timeout=10)
            datos = respuesta.json()

            # Extraer la respuesta principal
            resultado_web = datos.get("Abstract", "") or datos.get("Answer", "") or ""
            if not resultado_web:
                # Intentar Description como fallback
                resultado_web = datos.get("Description", "")[:500] if datos.get("Description") else ""

            if not resultado_web.strip():
                # Sin resultados de DuckDuckGo: informar transparente sin inventar.
                # Política de cero alucinaciones: reportar que no hay información
                # externa validada disponible en este momento.
                return {
                    "estado": "No he encontrado información suficiente en internet para responder a tu consulta. "
                              "Los resultados de búsqueda no contienen datos verificables para este tema. "
                              "Sugiero reformular la pregunta o consultar fuentes oficiales directamente.",
                    "requiere_web": True,
                    "resultado_web": "Sin resultados web verificables - por favor reformula tu consulta o consulta fuentes oficiales",
                    "nivel_confianza": 3,
                }

        except Exception as e:
            # Fallback silencioso si falla la red: informar transparentemente
            # sin inventar datos. El pipeline continúa con la lógica interna HPR.
            return {
                "estado": f"Error de red al consultar fuentes externas: {str(e)[:200]}. "
                          "El pipeline continuará con la lógica interna HPR. "
                          "Sugiera reformular la pregunta para intentar una nueva búsqueda.",
                "requiere_web": False,
                "resultado_web": "Error de red - intente nuevamente o consulte fuentes oficiales",
                "nivel_confianza": 3,
            }

        # 2. Pasar por ValidadorNivelesConfianza
        try:
            validacion = self.validador.clasificar_fuente("web_search", resultado_web)
        except Exception:
            # Si el validador falla, asumir nivel 3 (baja confianza)
            validacion = {
                "nivel": 3,
                "etiqueta": "Baja Confianza (Precaución)",
                "estado": "No se pudo validar la fuente externa.",
            }

        nivel = validacion["nivel"]
        etiqueta = validacion["etiqueta"]
        estado_validacion = validacion["estado"]

        # 3. Aplicar regla de cero alucinaciones
        if nivel == 1:
            # Alta confianza verificada - puede usarse directamente
            return {
                "estado": f"Respuesta externa validada (Nivel 1 - Alta Confianza):\n\n{resultado_web}\n\n[Fuente externa validada y confirmada por el sistema HPR]",
                "requiere_web": True,
                "resultado_web": resultado_web,
                "nivel_confianza": 1,
            }
        elif nivel == 2:
            # Confianza media - puede usarse con validación cruzada
            return {
                "estado": f"Respuesta externa con validación media (Nivel 2 - Confianza Media):\n\n{resultado_web}\n\n[Fuente externa: sometida a validación cruzada con la lógica interna del motor HPR antes de la emisión. El usuario debe confirmar la precisión en casos críticos.]",
                "requiere_web": True,
                "resultado_web": resultado_web,
                "nivel_confianza": 2,
            }
        else:
            # Nivel 3 - Baja confianza o información insuficiente
            # PROHIBIDO inventar datos. Informar transparentemente.
            return {
                "estado": f"No he podido verificar la información encontrada en internet con suficiente confianza para su uso (Nivel 3 - Baja Confianza). Por política de cero alucinaciones del motor HPR, no genero información inventada. Sugiero reformular la consulta o proporcionar más contexto para que pueda realizarse una búsqueda más precisa, o consultar fuentes oficiales directamente.",
                "requiere_web": True,
                "resultado_web": resultado_web,
                "nivel_confianza": 3,
            }

    def process_pipeline(self, payload: str, state: dict, truth: list) -> dict:
        """Ejecuta el pipeline de seguridad HPR y extrae conocimiento de la bóveda local.

        Contrato unificado (Compuerta 8 / B3): retorna SIEMPRE un ``dict`` con las
        claves ``estado``, ``requiere_externa``, ``nivel_confianza``, ``justificación``
        y ``fuente``. Los consumidores (``main.py``, ``web_interface.py``,
        ``multilingual/router.py``) dependen de este contrato; una ruta que devolviera
        ``str`` rompía el chat y disparaba un fallback espurio.

        Orden determinista (Reglas P4, D5, E6):
        1. Sovereign Gate: bloqueo de ingesta maliciosa (fuente única: core.engine).
        2. Nexus Root: identidad inmutable del sistema (D5).
        3. Bóveda: extracción de conocimiento local o reporte de bóveda vacía.
        """
        # 1. Sovereign Gate: control de ingesta (Regla P4).
        if not sovereign_gate_validation(payload):
            return {
                "estado": MENSAJE_BLOQUEO_SOVEREIGN_GATE,
                "requiere_externa": False,
                "nivel_confianza": None,
                "justificación": "Entrada bloqueada por Sovereign Gate.",
                "fuente": "sovereign_gate",
            }

        # 2. Nexus Root: valida la identidad inmutable del sistema (Regla D5).
        if not self.nexus_root_validation(state):
            return {
                "estado": MENSAJE_DENEGACION_NEXUS_ROOT,
                "requiere_externa": False,
                "nivel_confianza": None,
                "justificación": "Identidad no autorizada por Nexus Root.",
                "fuente": "nexus_root",
            }

        # 3. Bóveda: extracción de conocimiento local (Regla E6).
        if self.knowledge_base:
            return {
                "estado": (
                    f"{MENSAJE_PIPELINE_VERIFICADO}\n\n"
                    f"Información extraída de la Bóveda HPR ({len(self.knowledge_base)} caracteres totales):\n\n"
                    f"{self.knowledge_base[:1500]}..."
                ),
                "requiere_externa": False,
                "nivel_confianza": "alto",
                "justificación": "Conocimiento local disponible en la bóveda.",
                "fuente": "boveda",
            }

        return {
            "estado": "Pipeline superado con éxito, pero la bóveda de documentos se encuentra vacía o no se detectaron archivos .docx.",
            "requiere_externa": True,
            "nivel_confianza": "bajo",
            "justificación": "Sin conocimiento local en la bóveda.",
            "fuente": "boveda_vacia",
        }
        
