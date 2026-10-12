"""Contratos de dominio del motor HPR (Regla D4 de la Constitución).

Todo dato que cruza la frontera del motor se valida con esquemas
Pydantic estrictos. Los contratos son puros: no dependen del reloj,
de la red ni del azar (Reglas D2 y E5).
"""

from enum import Enum
from typing import Optional, Literal
from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, HttpUrl

#: Identidad inmutable del sistema (Regla D5).
IDENTIDAD_DETERMINISTA = "HPR-CORE-DETERMINISTIC"


# =============================================================================
# FASE 5: MOTOR DE PENSAMIENTO VERIFICABLE - CONTRATOS DE DATOS
# =============================================================================

class EvidenceType(str, Enum):
    """Tipos de evidencia soportados por el motor de verificación."""
    DOCUMENT = "document"           # Documento completo (paper, artículo, manual)
    SNIPPET = "snippet"             # Fragmento de texto extraído
    TABLE = "table"                 # Tabla de datos estructurados
    CODE = "code"                   # Fragmento de código fuente
    LOG = "log"                     # Log de ejecución o sistema
    METRIC = "metric"               # Métrica cuantitativa
    CITATION = "citation"           # Cita bibliográfica
    SPECIFICATION = "specification" # Especificación técnica oficial


class EvidenceSource(str, Enum):
    """Procedencia de la evidencia según taxonomía de confianza."""
    OFFICIAL = "official"           # Fuentes oficiales (gov, edu, corporativo verificado)
    TECHNICAL = "technical"         # Fuentes técnicas (repos, foros oficiales, docs)
    COMMUNITY = "community"         # Comunidad (StackOverflow, blogs técnicos)
    GENERAL = "general"             # Web general, blogs, redes sociales
    INTERNAL = "internal"           # Conocimiento interno / bóveda HPR


class Evidence(BaseModel):
    """
    Evidencia atómica para el motor de verificación.
    
    Cada pieza de evidencia es inmutable y trazable.
    La puntuación de relevancia NO se interpreta como probabilidad de verdad.
    """
    id: UUID = Field(default_factory=uuid4, description="Identificador único estable")
    content: str = Field(..., min_length=1, description="Contenido relevante de la evidencia")
    source: EvidenceSource = Field(..., description="Procedencia según taxonomía de confianza")
    evidence_type: EvidenceType = Field(..., description="Tipo de evidencia")
    source_url: Optional[HttpUrl] = Field(None, description="URL original de la evidencia")
    source_title: Optional[str] = Field(None, description="Título del documento origen")
    author: Optional[str] = Field(None, description="Autor o entidad emisora")
    published_at: Optional[datetime] = Field(None, description="Fecha de publicación")
    retrieved_at: datetime = Field(default_factory=datetime.utcnow, description="Fecha de recuperación")
    relevance_score: float = Field(
        ..., ge=0.0, le=1.0,
        description="Puntuación de relevancia (NO es probabilidad de verdad)"
    )
    metadata: dict = Field(default_factory=dict, description="Metadatos adicionales extensibles")


class ClaimStatus(str, Enum):
    """Estados obligatorios de evaluación de afirmaciones.
    
    No se permiten estados intermedios ni probabilísticos.
    """
    SUPPORTED = "supported"                 # La evidencia apoya la afirmación
    CONTRADICTED = "contradicted"           # La evidencia contradice la afirmación
    UNVERIFIED = "unverified"               # No hay evidencia suficiente para decidir
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"  # Evidencia existe pero no es concluyente


class ClaimEvaluation(BaseModel):
    """
    Evaluación de una afirmación contra la evidencia disponible.
    
    Cada afirmación se evalúa independientemente con estado binario/ternario estricto.
    """
    claim: str = Field(..., min_length=1, description="Afirmación a evaluar")
    status: ClaimStatus = Field(..., description="Estado de evaluación obligatorio")
    supporting_evidence: list[UUID] = Field(
        default_factory=list, description="IDs de evidencia que apoyan la afirmación"
    )
    contradicting_evidence: list[UUID] = Field(
        default_factory=list, description="IDs de evidencia que contradicen la afirmación"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0,
        description="Confianza en la evaluación (basada en calidad/cobertura de evidencia)"
    )
    reasoning: str = Field(..., min_length=1, description="Razonamiento textual de la evaluación")
    limitations: list[str] = Field(
        default_factory=list, description="Limitaciones conocidas de la evaluación"
    )


class Decision(str, Enum):
    """Decisiones finales del motor de pensamiento verificable."""
    ACCEPT = "accept"           # Aceptar la hipótesis/consulta
    REJECT = "reject"           # Rechazar la hipótesis/consulta
    DEFER = "defer"             # Diferir (requiere más evidencia)
    ABSTAIN = "abstain"         # Abstenerse (no responder por baja confianza/riesgo)


class StructuredResult(BaseModel):
    """
    Resultado estructurado final del motor de pensamiento verificable.
    
    Contiene la conclusión, evaluaciones detalladas, decisión final,
    limitaciones y referencias trazables.
    """
    conclusion: str = Field(..., min_length=1, description="Conclusión textual principal")
    claim_evaluations: list[ClaimEvaluation] = Field(
        default_factory=list, description="Evaluaciones de cada afirmación clave"
    )
    decision: Decision = Field(..., description="Decisión final del motor")
    overall_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confianza global en el resultado"
    )
    limitations: list[str] = Field(
        default_factory=list, description="Limitaciones globales del análisis"
    )
    references: list[UUID] = Field(
        default_factory=list, description="IDs de evidencia referenciada en el resultado"
    )
    metadata: dict = Field(default_factory=dict, description="Metadatos adicionales")


# =============================================================================
# FASE 6: GESTOR DE MEMORIA Y GRAFO DE SESIÓN CONVERSACIONAL
# =============================================================================

class TurnRole(str, Enum):
    """Roles en un turno conversacional."""
    USER = "user"           # Entrada del operador/usuario
    ASSISTANT = "assistant" # Respuesta del asistente/agente
    SYSTEM = "system"       # Mensajes de sistema/control


class TurnType(str, Enum):
    """Tipos de turno conversacional."""
    QUERY = "query"                 # Consulta de información
    TASK = "task"                   # Solicitud de ejecución de tarea
    CLARIFICATION = "clarification" # Solicitud de aclaración
    FEEDBACK = "feedback"           # Retroalimentación/corrección
    COMMAND = "command"             # Comando de control del sistema


class TurnStatus(str, Enum):
    """Estados de un turno conversacional."""
    PENDING = "pending"       # En procesamiento
    COMPLETED = "completed"   # Completado exitosamente
    FAILED = "failed"         # Falló con error
    PARTIAL = "partial"       # Completado parcialmente


class ConversationTurn(BaseModel):
    """
    Un turno individual en la conversación.
    
    Representa una interacción atómica entre usuario y asistente,
    con trazabilidad completa a evidencia y evaluaciones.
    """
    id: UUID = Field(default_factory=uuid4, description="Identificador único del turno")
    session_id: UUID = Field(..., description="ID de la sesión a la que pertenece")
    turn_number: int = Field(..., ge=1, description="Número ordinal del turno en la sesión")
    role: TurnRole = Field(..., description="Rol del emisor")
    turn_type: TurnType = Field(..., description="Tipo de turno")
    status: TurnStatus = Field(default=TurnStatus.PENDING, description="Estado del turno")
    
    # Contenido del turno
    content: str = Field(..., min_length=1, description="Contenido textual del turno")
    
    # Trazabilidad a evidencia y evaluaciones (FASE 5)
    referenced_evidence_ids: list[UUID] = Field(
        default_factory=list, description="IDs de evidencia referenciada en este turno"
    )
    claim_evaluation_ids: list[UUID] = Field(
        default_factory=list, description="IDs de evaluaciones de afirmaciones generadas en este turno"
    )
    structured_result_id: Optional[UUID] = Field(
        None, description="ID del resultado estructurado generado en este turno"
    )
    
    # Metadatos de ejecución
    tokens_used: Optional[int] = Field(None, ge=0, description="Tokens consumidos en este turno")
    latency_ms: Optional[int] = Field(None, ge=0, description="Latencia de procesamiento en ms")
    error_message: Optional[str] = Field(None, description="Mensaje de error si falló")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp de creación")
    completed_at: Optional[datetime] = Field(None, description="Timestamp de finalización")


class ReferenceType(str, Enum):
    """Tipos de referencias entre turnos para desambiguación."""
    EXPLICIT = "explicit"         # Referencia explícita ("lo anterior", "eso")
    IMPLICIT = "implicit"         # Referencia implícita (contexto)
    ANAPHORIC = "anaphoric"       # Referencia anafórica (pronombres)
    CATAcPHORIC = "cataphoric"    # Referencia catafórica (referencia forward)


class TurnReference(BaseModel):
    """
    Referencia entre turnos para desambiguación y enlace determinista.
    
    Permite rastrear cómo un turno referencia contenido de turnos previos,
    esencial para la coherencia conversacional y la trazabilidad.
    """
    id: UUID = Field(default_factory=uuid4, description="Identificador único de la referencia")
    source_turn_id: UUID = Field(..., description="ID del turno que hace la referencia")
    target_turn_id: UUID = Field(..., description="ID del turno referenciado")
    reference_type: ReferenceType = Field(..., description="Tipo de referencia")
    reference_text: str = Field(..., min_length=1, description="Texto de la referencia en el turno origen")
    resolved_content: Optional[str] = Field(None, description="Contenido resuelto de la referencia")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confianza en la resolución de la referencia")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp de creación")


class SessionStatus(str, Enum):
    """Estados de una sesión conversacional."""
    ACTIVE = "active"           # Sesión activa
    PAUSED = "paused"           # Sesión pausada
    COMPLETED = "completed"     # Sesión completada
    ARCHIVED = "archived"       # Sesión archivada
    ERROR = "error"             # Sesión con error crítico


class ConversationSession(BaseModel):
    """
    Sesión conversacional completa con grafo de turnos y referencias.
    
    Mantiene el estado completo de una conversación, incluyendo el historial
    de turnos, el grafo de referencias entre turnos, y el estado de tareas
    delegadas al motor de razonamiento.
    """
    id: UUID = Field(default_factory=uuid4, description="Identificador único de la sesión")
    status: SessionStatus = Field(default=SessionStatus.ACTIVE, description="Estado de la sesión")
    
    # Metadatos de la sesión
    title: Optional[str] = Field(None, description="Título descriptivo de la sesión")
    description: Optional[str] = Field(None, description="Descripción detallada")
    tags: list[str] = Field(default_factory=list, description="Etiquetas para clasificación")
    
    # Contexto de la sesión
    initial_query: Optional[str] = Field(None, description="Consulta inicial que inició la sesión")
    context_summary: Optional[str] = Field(None, description="Resumen del contexto acumulado")
    
    # Grafo de turnos y referencias
    turns: list[ConversationTurn] = Field(default_factory=list, description="Historial de turnos")
    references: list[TurnReference] = Field(default_factory=list, description="Grafo de referencias entre turnos")
    
    # Estado de tareas delegadas
    active_task_ids: list[UUID] = Field(default_factory=list, description="IDs de tareas activas")
    completed_task_ids: list[UUID] = Field(default_factory=list, description="IDs de tareas completadas")
    
    # Métricas de la sesión
    total_turns: int = Field(default=0, ge=0, description="Total de turnos en la sesión")
    total_tokens: int = Field(default=0, ge=0, description="Total de tokens consumidos")
    total_latency_ms: int = Field(default=0, ge=0, description="Latencia total acumulada en ms")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp de creación")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp de última actualización")
    completed_at: Optional[datetime] = Field(None, description="Timestamp de finalización")
    
    # Configuración
    max_turns: int = Field(default=100, ge=1, description="Límite máximo de turnos por sesión")
    max_tokens: int = Field(default=8000, ge=1, description="Límite de tokens por sesión")


class SessionContext(BaseModel):
    """
    Contexto actual de la sesión para toma de decisiones.
    
    Proporciona una vista consolidada del estado actual para el motor de decisión.
    """
    session_id: UUID = Field(..., description="ID de la sesión")
    current_turn_number: int = Field(..., ge=1, description="Número del turno actual")
    last_user_turn: Optional[ConversationTurn] = Field(None, description="Último turno del usuario")
    last_assistant_turn: Optional[ConversationTurn] = Field(None, description="Último turno del asistente")
    pending_references: list[TurnReference] = Field(default_factory=list, description="Referencias pendientes de resolver")
    active_topics: list[str] = Field(default_factory=list, description="Temas activos en la conversación")
    unresolved_ambiguities: list[str] = Field(default_factory=list, description="Ambiguedades pendientes de resolver")


# =============================================================================
# CONTRATOS EXISTENTES (MANTENIDOS PARA COMPATIBILIDAD)
# =============================================================================


class EstadoPipeline(str, Enum):
    """Estados terminales del pipeline de seguridad."""

    VERIFICADO = "verificado"
    BLOQUEADO = "bloqueado"
    DENEGADO = "denegado"


class NivelRiesgo(str, Enum):
    """Niveles de riesgo del triaje determinista."""

    BAJO = "bajo"
    MEDIO = "medio"
    ALTO = "alto"
    CRITICO = "critico"


class CategoriaConsulta(str, Enum):
    """Categorías de consulta del motor HPR."""

    SEGURIDAD = "seguridad"
    OPERATIVA = "operativa"
    CONOCIMIENTO = "conocimiento"
    DESCONOCIDA = "desconocida"


class PipelineState(BaseModel):
    """Estado del pipeline: identidad inmutable y propósito del sistema (D5)."""

    identity: str = Field(
        default=IDENTIDAD_DETERMINISTA,
        description="Identidad determinista que valida la raíz Nexus.",
    )


class PipelineRequest(BaseModel):
    """Contrato de entrada del pipeline: payload, estado y verdad de referencia."""

    payload: str = Field(
        description="Texto de entrada del usuario; la Sovereign Gate lo valida.",
    )
    state: PipelineState = Field(default_factory=PipelineState)
    truth: list[str] = Field(
        default_factory=list,
        description="Verdad de referencia (ground truth) para el muro Epsilon.",
    )


class PipelineResult(BaseModel):
    """Resultado estructurado y determinista del pipeline (D1)."""

    estado: EstadoPipeline
    mensaje: str
    conocimiento: str | None = Field(
        default=None,
        description="Extracto de la bóveda, cuando el pipeline lo extrae.",
    )
    caracteres_totales: int | None = Field(
        default=None,
        description="Tamaño total de la base de conocimiento, cuando aplica.",
    )


class TriageResult(BaseModel):
    """Resultado del triaje determinista de una consulta."""

    categoria: CategoriaConsulta
    nivel_riesgo: NivelRiesgo
    razones: list[str] = Field(
        default_factory=list,
        description="Reglas que dispararon la clasificación.",
    )
