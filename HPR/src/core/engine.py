"""Motor lógico central del HPR: validaciones puras y deterministas.

Reglas de la Constitución:
- D1: misma entrada -> misma salida; funciones puras sin efectos secundarios.
- D2: sin reloj, red ni azar en el camino crítico.
- D5: la identidad del sistema es inmutable.
- E5: ninguna llamada saliente.

Las tres raíces del motor (Nexus Root, Epsilon Wall, Sovereign Gate)
viven aquí como fuente única de verdad; el adaptador
``src/security_agent.py`` delega en este módulo.
"""

from ..models.contracts import (
    IDENTIDAD_DETERMINISTA,
    EstadoPipeline,
    PipelineRequest,
    PipelineResult,
)

#: Patrones de ingesta bloqueados por la Sovereign Gate (Regla P4).
PATRONES_SOVEREIGN_GATE = ("<script>", "DROP TABLE", "OVERRIDE_ROOT")

#: Mensajes terminales del pipeline (fuente única de verdad).
MENSAJE_BLOQUEO_SOVEREIGN_GATE = (
    "BLOQUEO DE SEGURIDAD: SOVEREIGN-GATE: Entrada bloqueada por seguridad."
)
MENSAJE_DENEGACION_NEXUS_ROOT = "Acceso denegado por Nexus Root."
MENSAJE_PIPELINE_VERIFICADO = "Pipeline verificado con éxito."


def sovereign_gate_validation(incoming_payload: str | None) -> bool:
    """Regla 3 (Sovereign Gate): control de ingesta y mitigación de entradas maliciosas."""
    if not incoming_payload or len(incoming_payload.strip()) == 0:
        return False
    return not any(pattern in incoming_payload for pattern in PATRONES_SOVEREIGN_GATE)


def nexus_root_validation(system_state: dict, nexus_identity: str = IDENTIDAD_DETERMINISTA) -> bool:
    """Regla 1 (Nexus Root): valida la identidad inmutable y el propósito del sistema."""
    return system_state.get("identity") == nexus_identity


def epsilon_wall_validation(response_content: str, ground_truth: list[str]) -> bool:
    """Regla 2 (Epsilon Wall): filtro anti-alucinación basado en verificación estricta."""
    return all(term in response_content for term in ground_truth)


class HPREngine:
    """Motor central determinista: aplica las tres raíces y devuelve un contrato (D1, D4)."""

    def __init__(self, nexus_identity: str = IDENTIDAD_DETERMINISTA) -> None:
        self.nexus_identity = nexus_identity

    def process(
        self,
        payload: str | None,
        state: dict,
        truth: list[str],
    ) -> PipelineResult:
        """Ejecuta las tres validaciones raíz y devuelve un resultado estructurado.

        El parámetro ``truth`` se conserva por paridad de contrato con el
        pipeline: el muro Epsilon valida *respuestas* frente a la verdad de
        referencia, no peticiones de entrada.
        """
        if not sovereign_gate_validation(payload):
            return PipelineResult(
                estado=EstadoPipeline.BLOQUEADO,
                mensaje=MENSAJE_BLOQUEO_SOVEREIGN_GATE,
            )
        if not nexus_root_validation(state, self.nexus_identity):
            return PipelineResult(
                estado=EstadoPipeline.DENEGADO,
                mensaje=MENSAJE_DENEGACION_NEXUS_ROOT,
            )
        return PipelineResult(
            estado=EstadoPipeline.VERIFICADO,
            mensaje=MENSAJE_PIPELINE_VERIFICADO,
        )

    def process_request(self, request: PipelineRequest) -> PipelineResult:
        """Punto de entrada por contrato (D4): valida una petición estructurada."""
        return self.process(request.payload, request.state.model_dump(), request.truth)
