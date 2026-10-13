"""
Orquestador de Tareas - Fase 6: Paso 2.2
Estructura base, esquemas de intenciones, contratos Pydantic y lógica de descomposición.

Integra VerifiedReasoningEngine para generar dinámicamente SubTasks a partir de IntentSchema,
con validación de DAG de dependencias y emisión de OrchestrationEvents.
"""

from enum import Enum
from typing import Optional, List, Dict, Any, Literal, Set, Tuple
from datetime import datetime
from uuid import UUID, uuid4
import logging
from collections import deque

from pydantic import BaseModel, Field, field_validator

from models.contracts import (
    ConversationTurn, ConversationSession, SessionContext,
    TurnRole, TurnType, StructuredResult, Decision,
    Evidence, ClaimEvaluation
)
from core.verified_reasoning import VerifiedReasoningEngine, create_verified_reasoning_engine, DecisionPolicy, DecisionPolicyEngine

logger = logging.getLogger(__name__)


# =============================================================================
# ESQUEMAS DE INTENCIONES (INTENT SCHEMAS)
# =============================================================================

class IntentCategory(str, Enum):
    """Categorías de intención de alto nivel para descomposición de tareas."""
    ANALYSIS = "analysis"           # Análisis de información, investigación
    SYNTHESIS = "synthesis"         # Síntesis, generación de informes, resúmenes
    EXECUTION = "execution"         # Ejecución de acciones, comandos, código
    PLANNING = "planning"           # Planificación, descomposición en subtareas
    CLARIFICATION = "clarification" # Solicitud de aclaración al usuario
    VERIFICATION = "verification"   # Verificación de hechos, validación
    DECISION = "decision"           # Toma de decisiones, evaluación de opciones
    MONITORING = "monitoring"       # Seguimiento, vigilancia de estado


class IntentComplexity(str, Enum):
    """Nivel de complejidad estimado de la intención."""
    ATOMIC = "atomic"       # Tarea única, no descomponible
    SIMPLE = "simple"       # 2-3 subtareas secuenciales
    MODERATE = "moderate"   # Subtareas con ramificación/paralelismo
    COMPLEX = "complex"     # Grafo de tareas con dependencias y bucles


class IntentPriority(str, Enum):
    """Prioridad de ejecución de la intención."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class IntentSchema(BaseModel):
    """
    Esquema de intención: representación estructurada de lo que el usuario quiere lograr.
    
    Es el contrato de entrada para el orquestador. Se genera a partir del análisis
    de la consulta del usuario (TurnType.TASK, TurnType.QUERY, etc.).
    """
    id: UUID = Field(default_factory=uuid4, description="Identificador único de la intención")
    category: IntentCategory = Field(..., description="Categoría principal de la intención")
    complexity: IntentComplexity = Field(default=IntentComplexity.SIMPLE, description="Complejidad estimada")
    priority: IntentPriority = Field(default=IntentPriority.NORMAL, description="Prioridad de ejecución")
    
    # Descripción semántica
    summary: str = Field(..., min_length=1, max_length=500, description="Resumen legible de la intención")
    description: str = Field(default="", description="Descripción detallada y contexto")
    
    # Parámetros y restricciones
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Parámetros específicos de la intención")
    constraints: List[str] = Field(default_factory=list, description="Restricciones duras (budget, tiempo, riesgo)")
    success_criteria: List[str] = Field(default_factory=list, description="Criterios de éxito medibles")
    
    # Contexto de sesión
    session_id: UUID = Field(..., description="ID de la sesión conversacional origen")
    source_turn_id: UUID = Field(..., description="ID del turno que originó esta intención")
    
    # Dependencias y relaciones
    depends_on: List[UUID] = Field(default_factory=list, description="IDs de intenciones predecesoras")
    blocks: List[UUID] = Field(default_factory=list, description="IDs de intenciones que esta bloquea")
    
    # Metadatos de orquestación
    estimated_subtasks: int = Field(default=1, ge=1, le=50, description="Estimación de subtareas")
    estimated_tokens: int = Field(default=0, ge=0, description="Presupuesto estimado de tokens")
    max_iterations: int = Field(default=3, ge=1, le=10, description="Máximo iteraciones de refinamiento")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    @field_validator('updated_at', mode='before')
    @classmethod
    def set_updated_at(cls, v):
        return datetime.utcnow()


# =============================================================================
# CONTRATOS DE TAREAS Y SUBTAREAS
# =============================================================================

class TaskStatus(str, Enum):
    """Estados del ciclo de vida de una tarea."""
    PENDING = "pending"           # En cola, esperando recursos
    SCHEDULED = "scheduled"       # Programada para ejecución
    RUNNING = "running"           # En ejecución activa
    WAITING = "waiting"           # Esperando dependencia externa (usuario, tool, otra tarea)
    COMPLETED = "completed"       # Completada exitosamente
    FAILED = "failed"             # Falló con error
    PARTIAL = "partial"           # Completada parcialmente (resultados útiles pero incompletos)
    CANCELLED = "cancelled"       # Cancelada por usuario o sistema
    DEFERRED = "deferred"         # Diferida para ejecución posterior


class TaskType(str, Enum):
    """Tipos de tarea atómicas ejecutables por el orquestador."""
    # Tareas de razonamiento (usan VerifiedReasoningEngine)
    REASONING = "reasoning"              # Razonamiento verificado sobre evidencia
    CLAIM_EXTRACTION = "claim_extraction" # Extracción de afirmaciones de texto
    EVIDENCE_GATHERING = "evidence_gathering" # Búsqueda y recopilación de evidencia
    CLAIM_EVALUATION = "claim_evaluation"   # Evaluación de claims contra evidencia
    SYNTHESIS = "synthesis"              # Síntesis de hallazgos en conclusión
    
    # Tareas de planificación
    DECOMPOSITION = "decomposition"      # Descomposición de intención en subtareas
    PLANNING = "planning"                # Generación de plan de ejecución
    SCHEDULING = "scheduling"            # Ordenación y asignación de recursos
    
    # Tareas de interacción
    USER_CLARIFICATION = "user_clarification" # Solicitar aclaración al usuario
    USER_CONFIRMATION = "user_confirmation"   # Solicitar confirmación al usuario
    
    # Tareas de ejecución (acciones externas)
    CODE_EXECUTION = "code_execution"    # Ejecución de código en sandbox
    API_CALL = "api_call"                # Llamada a API externa
    FILE_OPERATION = "file_operation"    # Operaciones de archivo
    
    # Tareas de control
    VALIDATION = "validation"            # Validación de resultados intermedios
    AGGREGATION = "aggregation"          # Agregación de resultados de subtareas
    CHECKPOINT = "checkpoint"            # Punto de control/guardado de estado


class SubTask(BaseModel):
    """
    Subtarea atómica dentro de una tarea compuesta.
    
    Cada subtarea es una unidad de trabajo que puede ejecutarse independientemente
    (salvo dependencias declaradas) y produce un resultado trazable.
    """
    id: UUID = Field(default_factory=uuid4, description="Identificador único de la subtarea")
    task_id: UUID = Field(..., description="ID de la tarea padre")
    intent_id: UUID = Field(..., description="ID de la intención origen")
    
    # Definición de la subtarea
    type: TaskType = Field(..., description="Tipo de subtarea")
    name: str = Field(..., min_length=1, max_length=200, description="Nombre legible")
    description: str = Field(default="", description="Descripción detallada")
    
    # Entrada y configuración
    input_data: Dict[str, Any] = Field(default_factory=dict, description="Datos de entrada serializados")
    config: Dict[str, Any] = Field(default_factory=dict, description="Configuración específica del tipo")
    
    # Dependencias (DAG)
    depends_on: List[UUID] = Field(default_factory=list, description="IDs de subtareas predecesoras")
    
    # Estado y ejecución
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="Estado actual")
    assigned_worker: Optional[str] = Field(None, description="Identificador del worker asignado")
    
    # Resultado
    output_data: Optional[Dict[str, Any]] = Field(None, description="Datos de salida serializados")
    result_id: Optional[UUID] = Field(None, description="ID de resultado estructurado (StructuredResult)")
    error_message: Optional[str] = Field(None, description="Mensaje de error si falló")
    
    # Métricas
    tokens_used: int = Field(default=0, ge=0, description="Tokens consumidos")
    latency_ms: int = Field(default=0, ge=0, description="Latencia de ejecución en ms")
    retry_count: int = Field(default=0, ge=0, description="Número de reintentos")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = Field(None)
    completed_at: Optional[datetime] = Field(None)
    
    @field_validator('started_at', mode='before')
    @classmethod
    def set_started_at(cls, v):
        return v or datetime.utcnow() if v is not None else None


class Task(BaseModel):
    """
    Tarea compuesta: agregación de subtareas que cumple una intención.
    
    Una tarea representa el plan de ejecución completo para una IntentSchema.
    Mantiene el estado agregado, el grafo de dependencias (DAG) de subtareas,
    y el resultado final consolidado.
    """
    id: UUID = Field(default_factory=uuid4, description="Identificador único de la tarea")
    intent_id: UUID = Field(..., description="ID de la intención que origina esta tarea")
    session_id: UUID = Field(..., description="ID de la sesión conversacional")
    
    # Definición
    name: str = Field(..., min_length=1, max_length=200, description="Nombre de la tarea")
    description: str = Field(default="", description="Descripción del objetivo")
    
    # Grafo de subtareas (DAG)
    subtasks: List[SubTask] = Field(default_factory=list, description="Subtareas ordenadas topológicamente")
    
    # Estado agregado
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="Estado agregado de la tarea")
    progress: float = Field(default=0.0, ge=0.0, le=1.0, description="Progreso global [0,1]")
    
    # Resultado consolidado
    final_result: Optional[StructuredResult] = Field(None, description="Resultado final consolidado")
    aggregated_evidence: List[UUID] = Field(default_factory=list, description="Evidencia agregada de todas las subtareas")
    aggregated_claims: List[UUID] = Field(default_factory=list, description="Claims evaluados agregados")
    
    # Métricas agregadas
    total_subtasks: int = Field(default=0, ge=0)
    completed_subtasks: int = Field(default=0, ge=0)
    failed_subtasks: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    total_latency_ms: int = Field(default=0, ge=0)
    
    # Control de ejecución
    max_parallelism: int = Field(default=3, ge=1, le=10, description="Máximo subtareas paralelas")
    timeout_seconds: int = Field(default=300, ge=1, description="Timeout global de la tarea")
    checkpoint_interval: int = Field(default=5, ge=1, description="Intervalo de checkpoints (subtareas)")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = Field(None)
    completed_at: Optional[datetime] = Field(None)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    @field_validator('updated_at', mode='before')
    @classmethod
    def set_updated_at(cls, v):
        return datetime.utcnow()


# =============================================================================
# ESTADO DE ORQUESTACIÓN
# =============================================================================

class OrchestrationPhase(str, Enum):
    """Fases del ciclo de orquestación."""
    IDLE = "idle"                     # Sin tarea activa
    INTAKE = "intake"                 # Análisis de intención entrante
    DECOMPOSITION = "decomposition"   # Descomposición en subtareas
    PLANNING = "planning"             # Planificación y ordenación
    EXECUTION = "execution"           # Ejecución activa de subtareas
    AGGREGATION = "aggregation"       # Agregación de resultados
    VALIDATION = "validation"         # Validación de resultado final
    COMPLETED = "completed"           # Ciclo completado
    ERROR = "error"                   # Error en orquestación


class OrchestrationState(BaseModel):
    """
    Estado global del orquestador para una sesión.
    
    Mantiene el estado de todas las tareas activas, la cola de intenciones pendientes,
    y el contexto de ejecución para toma de decisiones de scheduling.
    """
    session_id: UUID = Field(..., description="ID de la sesión")
    
    # Estado de fase actual
    phase: OrchestrationPhase = Field(default=OrchestrationPhase.IDLE)
    active_task_id: Optional[UUID] = Field(None, description="Tarea actualmente en ejecución")
    
    # Colas de trabajo
    pending_intents: List[IntentSchema] = Field(default_factory=list, description="Intenciones pendientes de descomponer")
    active_tasks: Dict[UUID, Task] = Field(default_factory=dict, description="Tareas en ejecución (por ID)")
    completed_tasks: Dict[UUID, Task] = Field(default_factory=dict, description="Tareas completadas (por ID)")
    failed_tasks: Dict[UUID, Task] = Field(default_factory=dict, description="Tareas fallidas (por ID)")
    
    # Recursos y límites
    max_concurrent_tasks: int = Field(default=2, ge=1, le=5, description="Máximo tareas concurrentes")
    max_concurrent_subtasks: int = Field(default=3, ge=1, le=10, description="Máximo subtareas concurrentes globales")
    token_budget: int = Field(default=8000, ge=100, description="Presupuesto de tokens por ciclo")
    tokens_consumed: int = Field(default=0, ge=0, description="Tokens consumidos en ciclo actual")
    
    # Contexto de decisión
    last_decision: Optional[str] = Field(None, description="Última decisión de política aplicada")
    decision_context: Dict[str, Any] = Field(default_factory=dict, description="Contexto para decisiones de scheduling")
    
    # Métricas de sesión
    total_tasks_created: int = Field(default=0, ge=0)
    total_tasks_completed: int = Field(default=0, ge=0)
    total_tasks_failed: int = Field(default=0, ge=0)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_activity_at: datetime = Field(default_factory=datetime.utcnow)
    
    @field_validator('updated_at', 'last_activity_at', mode='before')
    @classmethod
    def set_timestamp(cls, v):
        return datetime.utcnow() if v is None else v


# =============================================================================
# CONTRATOS DE ENTRADA/SALIDA DEL ORQUESTADOR
# =============================================================================

class OrchestratorInput(BaseModel):
    """
    Entrada al orquestador: intención detectada + contexto de sesión.
    
    Se genera desde el SessionManager al detectar un turno de tipo TASK/QUERY
    que requiere orquestación.
    """
    intent: IntentSchema = Field(..., description="Intención parseada y validada")
    session_context: SessionContext = Field(..., description="Contexto actual de la sesión")
    turn: ConversationTurn = Field(..., description="Turno que disparó la orquestación")
    
    # Recursos disponibles
    available_evidence: List[Evidence] = Field(default_factory=list, description="Evidencia disponible en sesión")
    previous_results: List[StructuredResult] = Field(default_factory=list, description="Resultados previos en sesión")
    
    # Configuración de ejecución
    force_replan: bool = Field(default=False, description="Forzar replanificación ignorando cache")
    dry_run: bool = Field(default=False, description="Solo planificar, no ejecutar")


class OrchestratorOutput(BaseModel):
    """
    Salida del orquestador tras procesar una intención.
    
    Contiene la tarea creada, su plan de ejecución, y el resultado final
    (si dry_run=False y la tarea completó).
    """
    success: bool = Field(..., description="Si la orquestación fue exitosa")
    task: Optional[Task] = Field(None, description="Tarea creada/ejecutada")
    final_result: Optional[StructuredResult] = Field(None, description="Resultado final si completó")
    
    # Información de diagnóstico
    phase_reached: OrchestrationPhase = Field(..., description="Fase alcanzada")
    error_message: Optional[str] = Field(None, description="Error si falló")
    warnings: List[str] = Field(default_factory=list, description="Advertencias no bloqueantes")
    
    # Métricas
    total_subtasks_planned: int = Field(default=0, ge=0)
    total_subtasks_executed: int = Field(default=0, ge=0)
    tokens_used: int = Field(default=0, ge=0)
    latency_ms: int = Field(default=0, ge=0)
    
    # Timestamps
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = Field(None)


# =============================================================================
# CONTRATOS DE EVENTOS (PARA OBSERVABILIDAD Y AUDITORÍA)
# =============================================================================

class OrchestrationEventType(str, Enum):
    """Tipos de eventos emitidos por el orquestador."""
    INTENT_RECEIVED = "intent_received"
    DECOMPOSITION_STARTED = "decomposition_started"
    DECOMPOSITION_COMPLETED = "decomposition_completed"
    PLANNING_STARTED = "planning_started"
    PLANNING_COMPLETED = "planning_completed"
    TASK_STARTED = "task_started"
    SUBTASK_STARTED = "subtask_started"
    SUBTASK_COMPLETED = "subtask_completed"
    SUBTASK_FAILED = "subtask_failed"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    AGGREGATION_STARTED = "aggregation_started"
    AGGREGATION_COMPLETED = "aggregation_completed"
    VALIDATION_STARTED = "validation_started"
    VALIDATION_COMPLETED = "validation_completed"
    CHECKPOINT_SAVED = "checkpoint_saved"
    USER_INTERACTION_REQUIRED = "user_interaction_required"
    BUDGET_EXCEEDED = "budget_exceeded"
    TIMEOUT = "timeout"


class OrchestrationEvent(BaseModel):
    """
    Evento de auditoría del orquestador.
    
    Inmutable, trazable, para logging estructurado y debugging determinista.
    """
    id: UUID = Field(default_factory=uuid4)
    event_type: OrchestrationEventType
    session_id: UUID
    task_id: Optional[UUID] = None
    subtask_id: Optional[UUID] = None
    intent_id: Optional[UUID] = None
    
    # Payload del evento
    message: str = Field(..., min_length=1)
    payload: Dict[str, Any] = Field(default_factory=dict)
    
    # Métricas asociadas
    tokens_delta: int = Field(default=0, description="Cambio en tokens consumidos")
    latency_ms: int = Field(default=0, ge=0)
    
    # Timestamp
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Correlación
    correlation_id: Optional[UUID] = Field(None, description="ID de correlación para trazas distribuidas")


# =============================================================================
# FACTORÍAS Y UTILIDADES DE CONTRATOS
# =============================================================================

def create_intent_schema(
    category: IntentCategory,
    summary: str,
    session_id: UUID,
    source_turn_id: UUID,
    complexity: IntentComplexity = IntentComplexity.SIMPLE,
    priority: IntentPriority = IntentPriority.NORMAL,
    description: str = "",
    parameters: Optional[Dict[str, Any]] = None,
    constraints: Optional[List[str]] = None,
    success_criteria: Optional[List[str]] = None,
    depends_on: Optional[List[UUID]] = None,
    estimated_subtasks: int = 1,
    estimated_tokens: int = 0,
    max_iterations: int = 3,
) -> IntentSchema:
    """Factoría para crear IntentSchema con valores por defecto seguros."""
    return IntentSchema(
        category=category,
        complexity=complexity,
        priority=priority,
        summary=summary,
        description=description,
        parameters=parameters or {},
        constraints=constraints or [],
        success_criteria=success_criteria or [],
        session_id=session_id,
        source_turn_id=source_turn_id,
        depends_on=depends_on or [],
        estimated_subtasks=estimated_subtasks,
        estimated_tokens=estimated_tokens,
        max_iterations=max_iterations,
    )


def create_subtask(
    task_id: UUID,
    intent_id: UUID,
    type: TaskType,
    name: str,
    description: str = "",
    input_data: Optional[Dict[str, Any]] = None,
    config: Optional[Dict[str, Any]] = None,
    depends_on: Optional[List[UUID]] = None,
) -> SubTask:
    """Factoría para crear SubTask."""
    return SubTask(
        task_id=task_id,
        intent_id=intent_id,
        type=type,
        name=name,
        description=description,
        input_data=input_data or {},
        config=config or {},
        depends_on=depends_on or [],
    )


def create_task(
    intent_id: UUID,
    session_id: UUID,
    name: str,
    description: str = "",
    subtasks: Optional[List[SubTask]] = None,
    max_parallelism: int = 3,
    timeout_seconds: int = 300,
) -> Task:
    """Factoría para crear Task con subtareas."""
    subtasks = subtasks or []
    return Task(
        intent_id=intent_id,
        session_id=session_id,
        name=name,
        description=description,
        subtasks=subtasks,
        total_subtasks=len(subtasks),
        max_parallelism=max_parallelism,
        timeout_seconds=timeout_seconds,
    )


def create_orchestration_state(session_id: UUID) -> OrchestrationState:
    """Factoría para estado inicial de orquestación."""
    return OrchestrationState(session_id=session_id)


def create_orchestrator_input(
    intent: IntentSchema,
    session_context: SessionContext,
    turn: ConversationTurn,
    available_evidence: Optional[List[Evidence]] = None,
    previous_results: Optional[List[StructuredResult]] = None,
    force_replan: bool = False,
    dry_run: bool = False,
) -> OrchestratorInput:
    """Factoría para entrada del orquestador."""
    return OrchestratorInput(
        intent=intent,
        session_context=session_context,
        turn=turn,
        available_evidence=available_evidence or [],
        previous_results=previous_results or [],
        force_replan=force_replan,
        dry_run=dry_run,
    )


def create_orchestration_event(
    event_type: OrchestrationEventType,
    session_id: UUID,
    message: str,
    task_id: Optional[UUID] = None,
    subtask_id: Optional[UUID] = None,
    intent_id: Optional[UUID] = None,
    payload: Optional[Dict[str, Any]] = None,
    tokens_delta: int = 0,
    latency_ms: int = 0,
    correlation_id: Optional[UUID] = None,
) -> OrchestrationEvent:
    """Factoría para eventos de auditoría."""
    return OrchestrationEvent(
        event_type=event_type,
        session_id=session_id,
        task_id=task_id,
        subtask_id=subtask_id,
        intent_id=intent_id,
        message=message,
        payload=payload or {},
        tokens_delta=tokens_delta,
        latency_ms=latency_ms,
        correlation_id=correlation_id,
    )


# =============================================================================
# MOTOR DE DESCOMPOSICIÓN DE INTENCIONES (PASO 2.2)
# =============================================================================

class DecompositionError(Exception):
    """Error durante la descomposición de intenciones."""
    def __init__(self, message: str, intent_id: UUID, stage: str):
        super().__init__(message)
        self.intent_id = intent_id
        self.stage = stage


class DAGValidationError(Exception):
    """Error de validación del DAG de dependencias."""
    def __init__(self, message: str, cycle: Optional[List[UUID]] = None):
        super().__init__(message)
        self.cycle = cycle


class TaskDecomposer:
    """
    Motor de descomposición de intenciones en subtareas ejecutables.
    
    Utiliza VerifiedReasoningEngine para analizar la intención y generar
    un plan de ejecución estructurado como DAG de SubTasks.
    """
    
    # Mapeo de categoría de intención a pipeline de subtareas base
    CATEGORY_PIPELINES: Dict[IntentCategory, List[Tuple[TaskType, str, str]]] = {
        IntentCategory.ANALYSIS: [
            (TaskType.EVIDENCE_GATHERING, "Recopilar evidencia", "Búsqueda y recopilación de evidencia relevante"),
            (TaskType.CLAIM_EXTRACTION, "Extraer afirmaciones", "Extracción de claims verificables del contenido"),
            (TaskType.CLAIM_EVALUATION, "Evaluar afirmaciones", "Evaluación de cada claim contra la evidencia"),
            (TaskType.REASONING, "Razonar sobre hallazgos", "Razonamiento verificado para sintetizar conclusiones"),
            (TaskType.SYNTHESIS, "Sintetizar resultado", "Generación de conclusión estructurada"),
        ],
        IntentCategory.SYNTHESIS: [
            (TaskType.EVIDENCE_GATHERING, "Recopilar fuentes", "Búsqueda de fuentes y evidencia base"),
            (TaskType.CLAIM_EXTRACTION, "Extraer puntos clave", "Identificación de afirmaciones y hallazgos"),
            (TaskType.REASONING, "Analizar y conectar", "Razonamiento para conectar hallazgos"),
            (TaskType.SYNTHESIS, "Generar síntesis", "Producción de informe/resumen estructurado"),
        ],
        IntentCategory.VERIFICATION: [
            (TaskType.CLAIM_EXTRACTION, "Extraer claims a verificar", "Identificación de afirmaciones verificables"),
            (TaskType.EVIDENCE_GATHERING, "Buscar evidencia", "Recopilación de evidencia pro/contra"),
            (TaskType.CLAIM_EVALUATION, "Evaluar cada claim", "Evaluación determinista contra evidencia"),
            (TaskType.VALIDATION, "Validar resultado", "Validación cruzada de evaluaciones"),
            (TaskType.SYNTHESIS, "Emitir veredicto", "Conclusión final con grado de confianza"),
        ],
        IntentCategory.DECISION: [
            (TaskType.EVIDENCE_GATHERING, "Recopilar opciones", "Búsqueda de alternativas y criterios"),
            (TaskType.CLAIM_EXTRACTION, "Extraer criterios", "Identificación de factores de decisión"),
            (TaskType.REASONING, "Analizar trade-offs", "Razonamiento sobre pros/contras"),
            (TaskType.VALIDATION, "Validar coherencia", "Verificación de consistencia lógica"),
            (TaskType.SYNTHESIS, "Emitir recomendación", "Decisión estructurada con justificación"),
        ],
        IntentCategory.PLANNING: [
            (TaskType.DECOMPOSITION, "Descomponer objetivo", "Análisis y descomposición en hitos"),
            (TaskType.PLANNING, "Generar plan", "Creación de plan con dependencias y recursos"),
            (TaskType.SCHEDULING, "Ordenar y priorizar", "Ordenación topológica y asignación"),
            (TaskType.VALIDATION, "Validar factibilidad", "Verificación de viabilidad del plan"),
        ],
        IntentCategory.EXECUTION: [
            (TaskType.PLANNING, "Planificar ejecución", "Descomposición en pasos accionables"),
            (TaskType.CODE_EXECUTION, "Ejecutar código", "Ejecución en sandbox controlado"),
            (TaskType.API_CALL, "Llamar APIs", "Invocación de servicios externos"),
            (TaskType.FILE_OPERATION, "Operaciones de archivo", "Lectura/escritura de archivos"),
            (TaskType.VALIDATION, "Validar resultados", "Verificación de outputs"),
            (TaskType.AGGREGATION, "Consolidar outputs", "Agregación de resultados de ejecución"),
        ],
        IntentCategory.CLARIFICATION: [
            (TaskType.USER_CLARIFICATION, "Solicitar aclaración", "Interacción con usuario para resolver ambigüedad"),
        ],
        IntentCategory.MONITORING: [
            (TaskType.EVIDENCE_GATHERING, "Recopilar métricas", "Obtención de datos de estado actual"),
            (TaskType.REASONING, "Analizar tendencias", "Detección de anomalías y patrones"),
            (TaskType.SYNTHESIS, "Generar reporte", "Informe de estado con alertas"),
        ],
    }
    
    # Complejidad -> factor de expansión de subtareas
    COMPLEXITY_MULTIPLIER: Dict[IntentComplexity, float] = {
        IntentComplexity.ATOMIC: 1.0,
        IntentComplexity.SIMPLE: 1.0,
        IntentComplexity.MODERATE: 1.5,
        IntentComplexity.COMPLEX: 2.5,
    }
    
    def __init__(
        self,
        reasoning_engine: Optional[VerifiedReasoningEngine] = None,
        decision_policy: Optional[DecisionPolicyEngine] = None,
        max_subtasks: int = 50,
        emit_events: bool = True,
    ):
        self.reasoning_engine = reasoning_engine or create_verified_reasoning_engine()
        self.decision_policy = decision_policy or DecisionPolicyEngine()
        self.max_subtasks = max_subtasks
        self.emit_events = emit_events
        self._event_callback: Optional[callable] = None
    
    def set_event_callback(self, callback: callable) -> None:
        """Registra callback para emisión de eventos (logging, streaming, etc.)."""
        self._event_callback = callback
    
    def _emit_event(self, event: OrchestrationEvent) -> None:
        """Emite evento si hay callback registrado."""
        if self.emit_events and self._event_callback:
            try:
                self._event_callback(event)
            except Exception as e:
                logger.warning(f"Error emitiendo evento {event.event_type}: {e}")
        logger.debug(f"Event: {event.event_type} | {event.message}")
    
    def decompose(
        self,
        intent: IntentSchema,
        session_context: SessionContext,
        available_evidence: List[Evidence],
        previous_results: List[StructuredResult],
        correlation_id: Optional[UUID] = None,
    ) -> Task:
        """
        Descompone una intención en una Task con SubTasks ordenadas topológicamente.
        
        Args:
            intent: Intención a descomponer
            session_context: Contexto de la sesión actual
            available_evidence: Evidencia disponible en la sesión
            previous_results: Resultados previos para reutilizar
            correlation_id: ID de correlación para trazabilidad
            
        Returns:
            Task con subtareas planificadas y validadas
            
        Raises:
            DecompositionError: Si falla la descomposición
            DAGValidationError: Si el grafo de dependencias tiene ciclos
        """
        start_time = datetime.utcnow()
        
        # Evento: inicio de descomposición
        self._emit_event(create_orchestration_event(
            event_type=OrchestrationEventType.DECOMPOSITION_STARTED,
            session_id=intent.session_id,
            intent_id=intent.id,
            message=f"Iniciando descomposición de intención: {intent.summary}",
            payload={
                "category": intent.category.value,
                "complexity": intent.complexity.value,
                "priority": intent.priority.value,
            },
            correlation_id=correlation_id,
        ))
        
        try:
            # 1. Obtener pipeline base para la categoría
            base_pipeline = self.CATEGORY_PIPELINES.get(intent.category, [])
            if not base_pipeline:
                raise DecompositionError(
                    f"No hay pipeline definido para categoría: {intent.category.value}",
                    intent.id,
                    "pipeline_selection"
                )
            
            # 2. Refinar pipeline usando VerifiedReasoningEngine
            refined_plan = self._refine_plan_with_reasoning(
                intent=intent,
                base_pipeline=base_pipeline,
                session_context=session_context,
                available_evidence=available_evidence,
                previous_results=previous_results,
                correlation_id=correlation_id,
            )
            
            # 3. Crear SubTasks desde el plan refinado
            subtasks = self._create_subtasks_from_plan(
                intent=intent,
                plan=refined_plan,
                session_context=session_context,
                correlation_id=correlation_id,
            )
            
            # 4. Validar DAG de dependencias
            self._validate_dag(subtasks)
            
            # 5. Ordenar topológicamente
            ordered_subtasks = self._topological_sort(subtasks)
            
            # 6. Crear Task consolidada
            task = create_task(
                intent_id=intent.id,
                session_id=intent.session_id,
                name=f"Task: {intent.summary}",
                description=intent.description,
                subtasks=ordered_subtasks,
                max_parallelism=self._calculate_parallelism(intent, ordered_subtasks),
                timeout_seconds=self._calculate_timeout(intent, ordered_subtasks),
            )
            
            # Actualizar métricas de la intención
            intent.estimated_subtasks = len(ordered_subtasks)
            intent.updated_at = datetime.utcnow()
            
            # Evento: descomposición completada
            latency_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            self._emit_event(create_orchestration_event(
                event_type=OrchestrationEventType.DECOMPOSITION_COMPLETED,
                session_id=intent.session_id,
                intent_id=intent.id,
                task_id=task.id,
                message=f"Descomposición completada: {len(ordered_subtasks)} subtareas generadas",
                payload={
                    "subtask_count": len(ordered_subtasks),
                    "subtask_types": [st.type.value for st in ordered_subtasks],
                    "max_parallelism": task.max_parallelism,
                    "timeout_seconds": task.timeout_seconds,
                },
                tokens_delta=0,
                latency_ms=latency_ms,
                correlation_id=correlation_id,
            ))
            
            logger.info(f"TaskDecomposer: Intent {intent.id} -> Task {task.id} ({len(ordered_subtasks)} subtasks)")
            return task
            
        except (DecompositionError, DAGValidationError):
            raise
        except Exception as e:
            latency_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            self._emit_event(create_orchestration_event(
                event_type=OrchestrationEventType.TASK_FAILED,
                session_id=intent.session_id,
                intent_id=intent.id,
                message=f"Error en descomposición: {str(e)}",
                payload={"error": str(e), "stage": "decomposition"},
                latency_ms=latency_ms,
                correlation_id=correlation_id,
            ))
            raise DecompositionError(f"Error inesperado en descomposición: {e}", intent.id, "decomposition")
    
    def _refine_plan_with_reasoning(
        self,
        intent: IntentSchema,
        base_pipeline: List[Tuple[TaskType, str, str]],
        session_context: SessionContext,
        available_evidence: List[Evidence],
        previous_results: List[StructuredResult],
        correlation_id: Optional[UUID],
    ) -> List[Dict[str, Any]]:
        """
        Usa VerifiedReasoningEngine para refinar el pipeline base según el contexto.
        
        El motor de razonamiento analiza la intención, la evidencia disponible y
        resultados previos para decidir qué subtareas son necesarias, cuáles pueden
        omitirse y qué parámetros específicos requieren.
        """
        # Construir query para el motor de razonamiento
        reasoning_query = self._build_refinement_query(
            intent=intent,
            base_pipeline=base_pipeline,
            session_context=session_context,
        )
        
        # Preparar evidencia para el razonamiento
        search_results = self._evidence_to_search_results(available_evidence, previous_results)
        
        # Ejecutar razonamiento (iteración 0 = planificación)
        try:
            reasoning_result = self.reasoning_engine.reason(
                query=reasoning_query,
                search_results=search_results,
                iteration=0,
            )
        except Exception as e:
            logger.warning(f"VerifiedReasoningEngine falló en refinamiento, usando pipeline base: {e}")
            return self._base_pipeline_to_plan(base_pipeline)
        
        # Parsear resultado para extraer plan refinado
        return self._parse_reasoning_plan(reasoning_result, base_pipeline, intent)
    
    def _build_refinement_query(
        self,
        intent: IntentSchema,
        base_pipeline: List[Tuple[TaskType, str, str]],
        session_context: SessionContext,
    ) -> str:
        """Construye la query para el motor de razonamiento de refinamiento de plan."""
        pipeline_desc = "\n".join([
            f"  {i+1}. {name}: {desc}" for i, (_, name, desc) in enumerate(base_pipeline)
        ])
        
        evidence_summary = f"{len(session_context.pending_references)} referencias pendientes, "
        evidence_summary += f"temas activos: {', '.join(session_context.active_topics[:5])}"
        
        return f"""
INTENCIÓN A DESCOMPONER:
- Categoría: {intent.category.value}
- Complejidad: {intent.complexity.value}
- Prioridad: {intent.priority.value}
- Resumen: {intent.summary}
- Descripción: {intent.description or 'N/A'}
- Restricciones: {', '.join(intent.constraints) if intent.constraints else 'Ninguna'}
- Criterios de éxito: {', '.join(intent.success_criteria) if intent.success_criteria else 'Ninguno'}

CONTEXTO DE SESIÓN:
- Turno actual: {session_context.current_turn_number}
- Última consulta usuario: {session_context.last_user_turn.content[:200] if session_context.last_user_turn else 'N/A'}
- Última respuesta asistente: {session_context.last_assistant_turn.content[:200] if session_context.last_assistant_turn else 'N/A'}
- {evidence_summary}

PIPELINE BASE PROPUESTO:
{pipeline_desc}

TAREA: Decide qué pasos del pipeline base son necesarios, cuáles pueden omitirse,
qué parámetros específicos requiere cada paso, y si se necesitan pasos adicionales.
Responde con un plan JSON estructurado.
"""
    
    def _evidence_to_search_results(
        self,
        evidence: List[Evidence],
        previous_results: List[StructuredResult],
    ) -> List[Dict[str, Any]]:
        """Convierte evidencia y resultados previos al formato esperado por VerifiedReasoningEngine."""
        results = []
        for e in evidence:
            results.append({
                "content": e.content,
                "source": e.source.value,
                "evidence_type": e.evidence_type.value,
                "source_url": str(e.source_url) if e.source_url else None,
                "source_title": e.source_title,
                "author": e.author,
                "relevance_score": e.relevance_score,
                "metadata": e.metadata,
            })
        for r in previous_results:
            results.append({
                "content": r.conclusion,
                "source": "internal",
                "evidence_type": "synthesis",
                "structured_result": r.model_dump(),
                "relevance_score": r.overall_confidence,
            })
        return results
    
    def _base_pipeline_to_plan(self, base_pipeline: List[Tuple[TaskType, str, str]]) -> List[Dict[str, Any]]:
        """Convierte pipeline base a formato de plan."""
        return [
            {
                "type": t.value,
                "name": name,
                "description": desc,
                "required": True,
                "config": {},
                "depends_on": [base_pipeline[i-1][0].value] if i > 0 else [],
            }
            for i, (t, name, desc) in enumerate(base_pipeline)
        ]
    
    def _parse_reasoning_plan(
        self,
        reasoning_result: Dict[str, Any],
        base_pipeline: List[Tuple[TaskType, str, str]],
        intent: IntentSchema,
    ) -> List[Dict[str, Any]]:
        """
        Parsea el resultado del razonamiento para extraer el plan refinado.
        
        En implementación completa, el VerifiedReasoningEngine retornaría un plan estructurado.
        Por ahora, usamos heurísticas basadas en la decisión y confianza.
        """
        decision_policy = reasoning_result.get("metadata", {}).get("decision_policy", "investigate")
        overall_confidence = reasoning_result.get("overall_confidence", 0.5)
        metrics = reasoning_result.get("metrics", {})
        
        # Si alta confianza y decisión ANSWER, simplificar pipeline
        if decision_policy == "answer" and overall_confidence > 0.8:
            # Pipeline mínimo: solo síntesis final
            return [
                {
                    "type": TaskType.SYNTHESIS.value,
                    "name": "Sintetizar respuesta directa",
                    "description": "Generar respuesta basada en evidencia ya disponible",
                    "required": True,
                    "config": {"use_cached_evidence": True},
                    "depends_on": [],
                }
            ]
        
        # Si decisión INVESTIGATE, expandir pipeline según complejidad
        plan = self._base_pipeline_to_plan(base_pipeline)
        
        # Ajustar según métricas
        if metrics.get("unverified", 0) > 2:
            # Añadir paso extra de evidencia gathering
            plan.insert(1, {
                "type": TaskType.EVIDENCE_GATHERING.value,
                "name": "Evidencia adicional",
                "description": "Búsqueda suplementaria para claims no verificados",
                "required": True,
                "config": {"supplementary": True},
                "depends_on": [plan[0]["type"]],
            })
        
        if metrics.get("contradicted", 0) > 0:
            # Añadir validación explícita
            plan.append({
                "type": TaskType.VALIDATION.value,
                "name": "Validar contradicciones",
                "description": "Revisión de claims contradictorios detectados",
                "required": True,
                "config": {"focus": "contradictions"},
                "depends_on": [plan[-1]["type"]],
            })
        
        # Aplicar multiplicador de complejidad
        multiplier = self.COMPLEXITY_MULTIPLIER.get(intent.complexity, 1.0)
        if multiplier > 1.0 and len(plan) < self.max_subtasks:
            # Expandir pasos clave (simplificado: duplicar evidence gathering)
            evidence_steps = [i for i, p in enumerate(plan) if p["type"] == TaskType.EVIDENCE_GATHERING.value]
            for idx in evidence_steps:
                if len(plan) >= self.max_subtasks:
                    break
                original = plan[idx]
                plan.insert(idx + 1, {
                    "type": TaskType.EVIDENCE_GATHERING.value,
                    "name": f"{original['name']} (ampliado)",
                    "description": f"Expansión de {original['description'].lower()}",
                    "required": False,
                    "config": {"expanded": True, "parent_step": original["type"]},
                    "depends_on": original["depends_on"],
                })
        
        return plan[:self.max_subtasks]
    
    def _create_subtasks_from_plan(
        self,
        intent: IntentSchema,
        plan: List[Dict[str, Any]],
        session_context: SessionContext,
        correlation_id: Optional[UUID],
    ) -> List[SubTask]:
        """Crea objetos SubTask desde el plan refinado."""
        subtasks = []
        type_to_id: Dict[str, UUID] = {}
        
        for i, step in enumerate(plan):
            task_type = TaskType(step["type"])
            subtask_id = uuid4()
            type_to_id[step["type"]] = subtask_id
            
            # Resolver dependencias por tipo
            depends_on = []
            for dep_type in step.get("depends_on", []):
                if dep_type in type_to_id:
                    depends_on.append(type_to_id[dep_type])
            
            # Configuración base según tipo
            config = step.get("config", {})
            config.update({
                "intent_category": intent.category.value,
                "intent_priority": intent.priority.value,
                "session_turn": session_context.current_turn_number,
                "step_index": i,
                "step_required": step.get("required", True),
            })
            
            # Input data base
            input_data = {
                "intent_summary": intent.summary,
                "intent_description": intent.description,
                "intent_parameters": intent.parameters,
                "session_context": {
                    "active_topics": session_context.active_topics,
                    "unresolved_ambiguities": session_context.unresolved_ambiguities,
                },
            }
            
            subtask = create_subtask(
                task_id=uuid4(),  # placeholder, se actualiza al crear Task
                intent_id=intent.id,
                type=task_type,
                name=step["name"],
                description=step["description"],
                input_data=input_data,
                config=config,
                depends_on=depends_on,
            )
            # Actualizar task_id real después
            subtasks.append(subtask)
        
        return subtasks
    
    def _validate_dag(self, subtasks: List[SubTask]) -> None:
        """
        Valida que el grafo de dependencias sea un DAG (sin ciclos).
        
        Usa algoritmo de Kahn para detección de ciclos.
        """
        # Construir grafo de adyacencia
        adj: Dict[UUID, List[UUID]] = {st.id: [] for st in subtasks}
        in_degree: Dict[UUID, int] = {st.id: 0 for st in subtasks}
        
        for st in subtasks:
            for dep_id in st.depends_on:
                if dep_id in adj:
                    adj[dep_id].append(st.id)
                    in_degree[st.id] += 1
                else:
                    logger.warning(f"Dependencia referenciada no existe: {dep_id} -> {st.id}")
        
        # Kahn's algorithm
        queue = deque([nid for nid, deg in in_degree.items() if deg == 0])
        visited = 0
        
        while queue:
            node = queue.popleft()
            visited += 1
            for neighbor in adj[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        if visited != len(subtasks):
            # Hay ciclo - encontrar el ciclo para reporte
            cycle = self._find_cycle(subtasks, adj)
            raise DAGValidationError(
                f"Ciclo detectado en dependencias de subtareas ({len(subtasks)} nodos, {visited} visitados)",
                cycle=cycle
            )
    
    def _find_cycle(self, subtasks: List[SubTask], adj: Dict[UUID, List[UUID]]) -> Optional[List[UUID]]:
        """Encuentra un ciclo en el grafo (DFS con colores)."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color: Dict[UUID, int] = {st.id: WHITE for st in subtasks}
        parent: Dict[UUID, Optional[UUID]] = {st.id: None for st in subtasks}
        cycle: List[UUID] = []
        
        def dfs(u: UUID) -> bool:
            color[u] = GRAY
            for v in adj.get(u, []):
                if color[v] == WHITE:
                    parent[v] = u
                    if dfs(v):
                        return True
                elif color[v] == GRAY:
                    # Ciclo encontrado - reconstruir
                    cycle.append(v)
                    curr = u
                    while curr != v:
                        cycle.append(curr)
                        curr = parent[curr]
                    cycle.append(v)
                    cycle.reverse()
                    return True
            color[u] = BLACK
            return False
        
        for node in adj:
            if color[node] == WHITE:
                if dfs(node):
                    return cycle
        return None
    
    def _topological_sort(self, subtasks: List[SubTask]) -> List[SubTask]:
        """Ordena topológicamente las subtareas (Kahn's algorithm)."""
        adj: Dict[UUID, List[UUID]] = {st.id: [] for st in subtasks}
        in_degree: Dict[UUID, int] = {st.id: 0 for st in subtasks}
        id_to_subtask = {st.id: st for st in subtasks}
        
        for st in subtasks:
            for dep_id in st.depends_on:
                if dep_id in adj:
                    adj[dep_id].append(st.id)
                    in_degree[st.id] += 1
        
        queue = deque([nid for nid, deg in in_degree.items() if deg == 0])
        result = []
        
        while queue:
            node = queue.popleft()
            result.append(id_to_subtask[node])
            for neighbor in adj[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        return result
    
    def _calculate_parallelism(self, intent: IntentSchema, subtasks: List[SubTask]) -> int:
        """Calcula paralelismo máximo basado en intención y estructura de subtareas."""
        # Contar subtareas sin dependencias (ejecutables en paralelo)
        independent = sum(1 for st in subtasks if not st.depends_on)
        
        base_parallelism = min(3, max(1, independent))
        
        # Ajustar por prioridad y complejidad
        if intent.priority == IntentPriority.CRITICAL:
            return min(base_parallelism + 1, 5)
        elif intent.priority == IntentPriority.HIGH:
            return min(base_parallelism, 4)
        elif intent.complexity == IntentComplexity.COMPLEX:
            return min(base_parallelism, 3)
        
        return base_parallelism
    
    def _calculate_timeout(self, intent: IntentSchema, subtasks: List[SubTask]) -> int:
        """Calcula timeout global estimado."""
        # Base: 60s por subtarea requerida
        required_count = sum(1 for st in subtasks if st.config.get("step_required", True))
        base_timeout = required_count * 60
        
        # Ajustar por complejidad
        multiplier = self.COMPLEXITY_MULTIPLIER.get(intent.complexity, 1.0)
        timeout = int(base_timeout * multiplier)
        
        # Límites
        return max(60, min(timeout, 1800))  # 1 min - 30 min


# =============================================================================
# ORQUESTADOR PRINCIPAL (INTERFAZ DE ALTO NIVEL)
# =============================================================================

class TaskOrchestrator:
    """
    Orquestador principal: coordina descomposición, planificación y ejecución.
    
    Expone una interfaz simple: process_intent() -> OrchestratorOutput
    """
    
    def __init__(
        self,
        decomposer: Optional[TaskDecomposer] = None,
        reasoning_engine: Optional[VerifiedReasoningEngine] = None,
        session_manager = None,  # Type hint evitado para evitar import circular
        event_callback: Optional[callable] = None,
    ):
        self.decomposer = decomposer or TaskDecomposer(reasoning_engine=reasoning_engine)
        self.session_manager = session_manager
        if event_callback:
            self.decomposer.set_event_callback(event_callback)
        
        # Estado por sesión
        self._states: Dict[UUID, OrchestrationState] = {}
    
    def get_or_create_state(self, session_id: UUID) -> OrchestrationState:
        """Obtiene o crea estado de orquestación para una sesión."""
        if session_id not in self._states:
            self._states[session_id] = create_orchestration_state(session_id)
        return self._states[session_id]
    
    def process_intent(
        self,
        input_data: OrchestratorInput,
        correlation_id: Optional[UUID] = None,
    ) -> OrchestratorOutput:
        """
        Procesa una intención completa: descomposición -> planificación -> ejecución.
        
        En Paso 2.2 solo implementamos descomposición + planificación.
        La ejecución completa se hará en Paso 2.3.
        """
        start_time = datetime.utcnow()
        intent = input_data.intent
        session_id = intent.session_id
        
        # Obtener/crear estado
        state = self.get_or_create_state(session_id)
        state.phase = OrchestrationPhase.INTAKE
        state.last_activity_at = datetime.utcnow()
        
        # Evento: intención recibida
        self.decomposer._emit_event(create_orchestration_event(
            event_type=OrchestrationEventType.INTENT_RECEIVED,
            session_id=session_id,
            intent_id=intent.id,
            message=f"Intención recibida: {intent.summary}",
            payload={"category": intent.category.value, "turn_id": str(input_data.turn.id)},
            correlation_id=correlation_id,
        ))
        
        try:
            # FASE 1: DESCOMPOSICIÓN
            state.phase = OrchestrationPhase.DECOMPOSITION
            task = self.decomposer.decompose(
                intent=intent,
                session_context=input_data.session_context,
                available_evidence=input_data.available_evidence,
                previous_results=input_data.previous_results,
                correlation_id=correlation_id,
            )
            
            # FASE 2: PLANIFICACIÓN (ordenación topológica ya hecha en descomposición)
            state.phase = OrchestrationPhase.PLANNING
            self.decomposer._emit_event(create_orchestration_event(
                event_type=OrchestrationEventType.PLANNING_COMPLETED,
                session_id=session_id,
                intent_id=intent.id,
                task_id=task.id,
                message=f"Planificación completada: {len(task.subtasks)} subtareas ordenadas",
                payload={
                    "subtask_order": [st.type.value for st in task.subtasks],
                    "parallelism": task.max_parallelism,
                },
                correlation_id=correlation_id,
            ))
            
            # Registrar tarea en estado
            state.active_tasks[task.id] = task
            state.active_task_id = task.id
            state.total_tasks_created += 1
            state.phase = OrchestrationPhase.EXECUTION
            
            # Por ahora (Paso 2.2), retornamos la tarea planificada sin ejecutar
            # La ejecución real será en Paso 2.3
            latency_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            return OrchestratorOutput(
                success=True,
                task=task,
                final_result=None,  # Se ejecutará en Paso 2.3
                phase_reached=OrchestrationPhase.PLANNING,
                error_message=None,
                warnings=["Ejecución de subtareas pendiente (Paso 2.3)"],
                total_subtasks_planned=len(task.subtasks),
                total_subtasks_executed=0,
                tokens_used=0,
                latency_ms=latency_ms,
                started_at=start_time,
                completed_at=datetime.utcnow(),
            )
            
        except DecompositionError as e:
            latency_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            state.phase = OrchestrationPhase.ERROR
            state.total_tasks_failed += 1
            
            self.decomposer._emit_event(create_orchestration_event(
                event_type=OrchestrationEventType.TASK_FAILED,
                session_id=session_id,
                intent_id=intent.id,
                message=f"Fallo en descomposición: {e}",
                payload={"error": str(e), "stage": e.stage},
                latency_ms=latency_ms,
                correlation_id=correlation_id,
            ))
            
            return OrchestratorOutput(
                success=False,
                task=None,
                final_result=None,
                phase_reached=state.phase,
                error_message=str(e),
                warnings=[],
                latency_ms=latency_ms,
                started_at=start_time,
                completed_at=datetime.utcnow(),
            )
        
        except DAGValidationError as e:
            latency_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            state.phase = OrchestrationPhase.ERROR
            state.total_tasks_failed += 1
            
            cycle_info = [str(u) for u in e.cycle] if e.cycle else []
            
            self.decomposer._emit_event(create_orchestration_event(
                event_type=OrchestrationEventType.TASK_FAILED,
                session_id=session_id,
                intent_id=intent.id,
                message=f"DAG inválido: {e}",
                payload={"cycle": cycle_info},
                latency_ms=latency_ms,
                correlation_id=correlation_id,
            ))
            
            return OrchestratorOutput(
                success=False,
                task=None,
                final_result=None,
                phase_reached=OrchestrationPhase.ERROR,
                error_message=f"Ciclo en dependencias: {e}",
                warnings=[],
                latency_ms=latency_ms,
                started_at=start_time,
                completed_at=datetime.utcnow(),
            )
        
        except Exception as e:
            latency_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            state.phase = OrchestrationPhase.ERROR
            state.total_tasks_failed += 1
            
            logger.exception(f"Error inesperado en TaskOrchestrator: {e}")
            
            return OrchestratorOutput(
                success=False,
                task=None,
                final_result=None,
                phase_reached=OrchestrationPhase.ERROR,
                error_message=f"Error interno: {e}",
                warnings=[],
                latency_ms=latency_ms,
                started_at=start_time,
                completed_at=datetime.utcnow(),
            )


# =============================================================================
# FACTORÍA PRINCIPAL
# =============================================================================

def create_task_orchestrator(
    reasoning_engine: Optional[VerifiedReasoningEngine] = None,
    session_manager = None,
    event_callback: Optional[callable] = None,
    max_subtasks: int = 50,
) -> TaskOrchestrator:
    """Factoría para crear TaskOrchestrator configurado."""
    decomposer = TaskDecomposer(
        reasoning_engine=reasoning_engine,
        max_subtasks=max_subtasks,
    )
    return TaskOrchestrator(
        decomposer=decomposer,
        reasoning_engine=reasoning_engine,
        session_manager=session_manager,
        event_callback=event_callback,
    )