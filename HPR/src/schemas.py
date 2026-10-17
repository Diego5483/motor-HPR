from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


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
        description="Parámetros adicionales para el trigger (ej. query para @web_search).",
    )
    payload: Optional[str] = Field(
        default=None,
        description="Payload/orden libre del usuario para el trigger (ej. términos de búsqueda web).",
    )


class WebSearchResultItem(BaseModel):
    """Resultado individual de búsqueda web (fuente + fragmento)."""

    titulo: str = Field(..., description="Título del resultado.")
    snippet: str = Field(..., description="Fragmento de texto del resultado.")
    fuente: str = Field(..., description="Fuente del resultado.")
    relevancia: float = Field(..., ge=0.0, le=1.0, description="Relevancia (0.0–1.0).")


class TriggerResult(BaseModel):
    """Resultado tipado de la ejecución de un trigger (G.2).

    Sustituye al dict libre ciego: cada clave conocida es un campo explícito.
    `estado` es la señal consumida por el contrato para derivar el éxito:
    un estado "error" o "no_disponible" NO es un éxito.
    """

    model_config = ConfigDict(extra="forbid")

    # Señal de estado (activo | verificado | error | no_disponible | fallback_local)
    estado: Optional[str] = None
    mensaje: Optional[str] = None

    # @hpr_confianza
    nivel_confianza: Optional[int] = None
    turnos: Optional[int] = None
    contexto: Optional[Dict[str, Any]] = None

    # @nivel1
    perfil: Optional[str] = None
    operaciones_permitidas: Optional[List[str]] = None
    restricciones: Optional[List[str]] = None

    # @web_search
    query: Optional[str] = None
    resultados_simulados: Optional[List[WebSearchResultItem]] = None
    sugerencia_configuracion: Optional[str] = None

    # N1 · Búsqueda Cognitiva
    resultados: Optional[List[Any]] = None
    filtro_usuario: Optional[str] = None

    # N2 · Grafo de Consistencia
    conflictos: Optional[List[Any]] = None
    turnos_analizados: Optional[int] = None

    # MotorRazonamientoSuperior
    sintesis: Optional[str] = None
    foco_usuario: Optional[str] = None
    temas_activos: Optional[List[str]] = None
    ambiguedades: Optional[List[str]] = None

    # SOVEREIGN-GATE
    soberania: Optional[str] = None
    ingestión_permitida: Optional[bool] = None
    cambios_sensibles: Optional[str] = None

    # Fallback local
    trigger: Optional[str] = None
    fallback: Optional[bool] = None


class TriggerExecutionResponse(BaseModel):
    """Respuesta de ejecución de trigger con telemetría (Etapa D)."""

    success: bool = Field(..., description="Indica si la ejecución fue exitosa.")
    trigger: str = Field(..., description="Trigger ejecutado.")
    session_id: Optional[str] = Field(
        default=None,
        description="ID de sesión asociada a la ejecución.",
    )
    result: Optional[TriggerResult] = Field(
        default=None,
        description="Resultado tipado de la ejecución del trigger (G.2).",
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