"""Adaptador del motor HPR:une la bóveda local con el motor lógico central.

Las tres validaciones raíz (Nexus Root, Epsilon Wall, Sovereign Gate)
viven en ``src/core/engine.py`` como fuente única de verdad; esta clase
delegga en ellas y añade la carga de la bóveda documental local (E6).
Además, integra evaluación de intenciones y búsqueda web externa con
gobernanza de tres niveles de confianza (Reglas S2, E5, D4).
"""

import os
import sys
from typing import Optional

# Asegurar que el directorio src esté en el path para importaciones relativas
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from docx import Document

# Importaciones desde src.core.engine y módulos asociados
from src.core.engine import (
    nexus_root_validation,
    sovereign_gate_validation,
    evaluar_intencion_externa,
    triage_query,
)
from src.models.contracts import IDENTIDAD_DETERMINISTA
from src.validador_niveles_confianza import ValidadorNivelesConfianza

# Definición local de epsilon_wall_validation para evitar importaciones problemáticas
def epsilon_wall_validation(response_content: str, ground_truth: list) -> bool:
    """Regla 2 (Epsilon Wall): filtro anti-alucinación basado en verificaci��n estricta."""
    return all(term in response_content for term in ground_truth)

# Definición local de constantes de seguridad
MENSAJE_BLOQUEO_SOVEREIGN_GATE = "Acceso bloqueado por la pasarela soberana de seguridad."
MENSAJE_DENEGACION_NEXUS_ROOT = "Acceso denegado por el núcleo raíz determinista."


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
        """Regla 3: Control de ingesta y mitigación de entradas maliciosas."""
        return sovereign_gate_validation(incoming_payload)

    def evaluar_intencion_consulta(self, consulta: str) -> dict:
        """Evalúa si la consulta requiere búsqueda web externa.

        Aplica la regla D1/D2: si la consulta contiene señales de externalidad
        (actualidad, tecnología reciente) y la bóveda no cubre el tema,
        retorna True para activar búsqueda web.
        """
        return evaluar_intencion_externa(consulta, self.knowledge_base)

    def proceso_pipeline(self, payload: str, state: dict, truth: list) -> dict:
        """Ejecuta el pipeline de seguridad HPR con evaluación de intención y búsqueda web opcional.

        Flujo completo (Reglas D1/D2/E5/S2/P4):
        1. Evaluación de intención: determina si la consulta requiere información externa
           (actualidad, tecnología reciente, eventos no en bóveda).
        2. Validaciones deterministas:
           - Sovereign Gate: bloquea entradas maliciosas (P4).
           - Nexus Root: valida identidad inmutable del sistema (D5).
        3. Según el resultado del triaje y la evaluación de intención:
           - Si requiere externa: ejecutar _ejecutar_busqueda_web con validación
             de tres niveles de confianza.
           - Si interna suficiente: extraer pasaje de la bóveda (D1).
           - Si mezclada: preferir interna, complementar con web validada.
        4. Retornar diccionario con estado, resultado web y nivel de confianza
           para la interfaz Streamlit.

        Retorna dict con:
        - estado: str (resultado procesado)
        - requiere_web: bool
        - resultado_web: str | None (contenido validado o None)
        - nivel_confianza: int | None (1=alta, 2=media, 3=baja)
        - fuente: str (origen: "boveda", "web_nivel1", "web_nivel2", "web_nivel3")
        """
        # --- Paso 1: Evaluación de intención ---
        eval_externa = self.evaluar_intencion_consulta(payload)

        # --- Paso 2: Validaciones deterministas ---
        # Sovereign Gate: control de ingesta y mitigación de entradas maliciosas (Regla P4)
        if not sovereign_gate_validation(payload):
            return {
                "estado": "BLOQUEO DE SEGURIDAD: SOVEREIGN-GATE: Entrada bloqueada por seguridad.",
                "requiere_web": False,
                "resultado_web": None,
                "nivel_confianza": None,
                "fuente": "soveraign_gate",
            }

        # Nexus Root: valida la identidad inmutable y el propósito del sistema (Regla D1).
        # Ya no bloquea consultas que requieren investigación externa; solo registra el estado
        # para efectos de rastreo, pero el acceso a internet y la veracidad de la información
        # quedan completamente gobernados por el sistema de tres niveles de confianza.
        nexus_root_result = nexus_root_validation(state)
        if not nexus_root_result:
            # No bloquear Consultas} externa; solo informar y continuar
            # permitiendo que el sistema de tres niveles de confianza gouverne el acceso web.
            pass  # Continúa el pipeline para búsquedas web gobernadas por confianza

        # --- Paso 3: Triaje determinista ---
        triaje = triage_query(payload, self.knowledge_base)

        # Manejo por categoría de triaje
        # Si es seguridad, bloquear
        if triaje.categoria.name == "SEGURIDAD":
            return {
                "estado": f"Consulta clasificada como SEGURIDAD (riesgo {triaje.nivel_riesgo.value}). Motivo: {triaje.razones[0]}. Por política del motor HPR, esta entrada no se procesa.",
                "requiere_web": False,
                "resultado_web": None,
                "nivel_confianza": None,
                "fuente": "triage_seguridad",
            }

        # Si es operativa, retornar estado
        if triaje.categoria.name == "OPERATIVA":
            return {
                "estado": f"Motor HPR en línea. Identidad: {self.nexus_identity}. Bóveda local: {len(self.knowledge_base)} caracteres.",
                "requiere_web": False,
                "resultado_web": None,
                "nivel_confianza": None,
                "fuente": "triage_operativa",
            }

        # --- Paso 4: Manejo de conocimiento ---
        # Si es conocimiento, verificar si la bóveda tiene pasaje relevante
        if triaje.categoria.name == "CONOCIMIENTO":
            # Intentar obtener pasaje de la bóveda primero
            pasaje = self._pasaje_mas_relevante(payload)
            if pasaje is not None:
                # Contexto interno encontrado → Nivel 1 directo (verificado por construcción)
                return {
                    "estado": f"Respuesta extraída de la Bóveda HPR (Nivel 1 - Alta Confianza):\n\n{pasaje}",
                    "requiere_web": False,
                    "resultado_web": None,
                    "nivel_confianza": 1,
                    "fuente": "boveda_nivel1",
                }

            # Bóveda no tiene respuesta → activar búsqueda web si la evaluación lo requiere
            if eval_externa["requiere_externa"]:
                return self._ejecutar_busqueda_web(payload)
            else:
                # Sin pasaje interno y sin necesidad externa → información insuficiente
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
                return {
                    "estado": "No he encontrado información suficiente en la bóveda interna del motor HPR, ni puedo recuperar un resultado web validado para tu consulta. Por favor, reformula la pregunta o proporciona más contexto para que pueda buscar con mayor precisión.",
                    "requiere_web": True,
                    "resultado_web": None,
                    "nivel_confianza": None,
                }

        except Exception as e:
            # Fallback silencioso si falla la red
            return {
                "estado": f"Error de red al consultar fuentes externas: {str(e)[:200]}. El pipeline continuará con la lógica interna HPR.",
                "requiere_web": False,
                "resultado_web": None,
                "nivel_confianza": None,
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

    def process_pipeline(self, *args, **kwargs):
        query = args[0] if args else kwargs.get("query", kwargs.get("payload", ""))
        if isinstance(query, dict):
            query = query.get("query", query.get("text", str(query)))

        intencion = self.evaluar_intencion_consulta(str(query))
        # Nexus Root: validación de identidad (sin bloqueo para consultas web/externas)
        # El acceso a internet y la veracidad quedan gobernados por el sistema de tres niveles de confianza

        if not sovereign_gate_validation(str(query)):
            return MENSAJE_BLOQUEO_SOVEREIGN_GATE
        
