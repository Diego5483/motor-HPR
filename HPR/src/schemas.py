from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class CommunicationQuerySchema(BaseModel):
    """
    Modelo de validación para las consultas de comunicación en el motor HPR.
    """

    query: str | None = Field(
        default=None,
        description="Texto o término de búsqueda para la consulta de comunicación.",
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Límite de resultados a retornar, entre 1 y 100.",
    )


# ---------------------------------------------------------------------------
# Etapa D · Contrato de ejecución de triggers
# ---------------------------------------------------------------------------

class TriggerType(str, Enum):
    """Triggers disponibles para ejecución real en el motor HPR."""

    CONFIANZA = "@hpr_confianza"
    NIVEL1 = "@nivel1"
    WEB_SEARCH = "@web_search"
    N1_BUSQUEDA = "N1 · Búsqueda Cognitiva"
    N2_GRAFO = "N2 · Grafo de Consistencia"
    MOTOR_RAZON = "MotorRazonamientoSuperior"
    SOVEREIGN_GATE = "SOVEREIGN-GATE"


class TriggerExecutionRequest(BaseModel):
    """Solicitud de ejecución de trigger (Etapa D)."""

    trigger: TriggerType = Field(..., description="Trigger a ejecutar.")
    session_id: Optional[str] = Field(
        default=None,
        description="ID de sesión existente (opcional, se crea si no existe).",
    )
    confidence_level: int = Field(
        default=1,
        ge=1,
        le=3,
        description="Nivel de confianza solicitado (1–3).",
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parámetros adicionales para el trigger.",
    )


class TriggerExecutionResponse(BaseModel):
    """Respuesta de ejecución de trigger con telemetría (Etapa D)."""

    success: bool = Field(..., description="Indica si la ejecución fue exitosa.")
    trigger: str = Field(..., description="Trigger ejecutado.")
    session_id: Optional[str] = Field(
        default=None,
        description="ID de sesión asociada a la ejecución.",
    )
    result: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Resultado de la ejecución del trigger.",
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Mensaje de error si la ejecución falló.",
    )
    telemetry: Dict[str, Any] = Field(
        default_factory=dict,
        description="Telemetría de la ejecución (latencia, estado, etc.).",
    )
    execution_time_ms: Optional[float] = Field(
        default=None,
        description="Tiempo de ejecución en milisegundos.",
    )