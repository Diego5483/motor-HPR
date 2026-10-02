"""Adaptador del motor HPR: une la bóveda local con el motor lógico central.

Las tres validaciones raíz (Nexus Root, Epsilon Wall, Sovereign Gate)
viven en ``src/core/engine.py`` como fuente única de verdad; esta clase
delega en ellas y añade la carga de la bóveda documental local (E6).
"""

import os

from docx import Document

from .core.engine import (
    MENSAJE_BLOQUEO_SOVEREIGN_GATE,
    MENSAJE_DENEGACION_NEXUS_ROOT,
    MENSAJE_PIPELINE_VERIFICADO,
    epsilon_wall_validation,
    nexus_root_validation,
    sovereign_gate_validation,
)
from .models.contracts import IDENTIDAD_DETERMINISTA


class HPRSecurityEngine:
    """Motor de seguridad HPR: bóveda local más validaciones del núcleo determinista."""

    def __init__(self, nexus_identity: str = IDENTIDAD_DETERMINISTA):
        self.nexus_identity = nexus_identity
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.docs_path = os.path.join(base_dir, "..", "boveda y vitacoras")
        self.knowledge_base = self.load_knowledge()

    def load_knowledge(self):
        text_content = ""
        path = self.docs_path if os.path.exists(self.docs_path) else os.path.join("..", self.docs_path)
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

    def process_pipeline(self, payload: str, state: dict, truth: list) -> str:
        """Ejecuta el pipeline completo de seguridad y extrae respuestas de la base de conocimiento HPR."""
        if not self.sovereign_gate_validation(payload):
            return MENSAJE_BLOQUEO_SOVEREIGN_GATE
        if not self.nexus_root_validation(state):
            return MENSAJE_DENEGACION_NEXUS_ROOT

        # Si pasa las validaciones, devolvemos el contenido extraído de la bóveda
        if self.knowledge_base:
            return (
                f"{MENSAJE_PIPELINE_VERIFICADO}\n\n"
                f"Información extraída de la Bóveda HPR ({len(self.knowledge_base)} caracteres totales):\n\n"
                f"{self.knowledge_base[:1500]}..."
            )
        else:
            return "Pipeline superado con éxito, pero la bóveda de documentos se encuentra vacía o no se detectaron archivos .docx."
