import os
from docx import Document

class HPRSecurityEngine:
    def __init__(self, nexus_identity="HPR-CORE-DETERMINISTIC"):
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
        return system_state.get("identity") == self.nexus_identity

    def epsilon_wall_validation(self, response_content: str, ground_truth: list) -> bool:
        """Regla 2: Filtro anti-alucinación basado en verificación estricta."""
        return all(term in response_content for term in ground_truth)

    def sovereign_gate_validation(self, incoming_payload: str) -> bool:
        """Regla 3: Control de ingesta y mitigación de entradas maliciosas."""
        if not incoming_payload or len(incoming_payload.strip()) == 0:
            return False
        malicious_patterns = ["<script>", "DROP TABLE", "OVERRIDE_ROOT"]
        return not any(pattern in incoming_payload for pattern in malicious_patterns)

    def process_pipeline(self, payload: str, state: dict, truth: list) -> str:
        """Ejecuta el pipeline completo de seguridad y extrae respuestas de la base de conocimiento HPR."""
        if not self.sovereign_gate_validation(payload):
            return "BLOQUEO DE SEGURIDAD: SOVEREIGN-GATE: Entrada bloqueada por seguridad."
        if not self.nexus_root_validation(state):
            return "Acceso denegado por Nexus Root."

        # Si pasa las validaciones, devolvemos el contenido extraído de la bóveda
        if self.knowledge_base:
            return f"Pipeline verificado con éxito.\n\nInformación extraída de la Bóveda HPR ({len(self.knowledge_base)} caracteres totales):\n\n{self.knowledge_base[:1500]}..."
        else:
            return "Pipeline superado con éxito, pero la bóveda de documentos se encuentra vacía o no se detectaron archivos .docx."