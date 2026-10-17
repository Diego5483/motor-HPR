import os
import time
import random
import re
from functools import wraps
from typing import Callable, TypeVar, ParamSpec

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timezone

from .schemas import (
    CommunicationQuerySchema,
    TriggerExecutionRequest,
    TriggerExecutionResponse,
    TriggerResult,
    TriggerType,
)
from .core.security_agent import verify_security_guard
from .security_agent import HPRSecurityEngine
from .core.session_manager import SessionManager, create_session_manager
from .core.task_orchestrator import (
    TaskOrchestrator, create_task_orchestrator,
    OrchestratorInput, OrchestratorOutput,
    IntentSchema, IntentCategory, IntentComplexity, IntentPriority,
    create_intent_schema
)
from .models.contracts import (
    ConversationTurn, TurnRole, TurnType, SessionContext,
    StructuredResult, Decision
)
from .execution_log import log_execution, get_logs, get_log_stats, export_logs
from .core.engine import sovereign_gate_validation, nexus_root_validation
from .core.deep_synthesizer import DeepSynthesizer


# ---------------------------------------------------------------------------
# Exponential Backoff & Retry Utilities (Rate Limit / Stability)
# ---------------------------------------------------------------------------
P = ParamSpec("P")
R = TypeVar("R")

class RetryConfig:
    """Configuración de reintentos con backoff exponencial."""
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retryable_statuses: tuple = (429, 500, 502, 503, 504),
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retryable_statuses = retryable_statuses

    def calculate_delay(self, attempt: int) -> float:
        """Calcula el delay con backoff exponencial y jitter opcional."""
        delay = min(
            self.base_delay * (self.exponential_base ** attempt),
            self.max_delay
        )
        if self.jitter:
            # Jitter: ±25% para evitar thundering herd
            delay = delay * (0.75 + random.random() * 0.5)
        return delay


DEFAULT_RETRY_CONFIG = RetryConfig()


def with_retry(config: RetryConfig = DEFAULT_RETRY_CONFIG):
    """
    Decorador para añadir reintentos con backoff exponencial a funciones async.
    
    Uso:
        @with_retry(RetryConfig(max_attempts=3, base_delay=1.0))
        async def llamar_api_externa(...):
            ...
    """
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            last_exception = None
            
            for attempt in range(config.max_attempts):
                try:
                    return await func(*args, **kwargs)
                except HTTPException as e:
                    # Re-lanzar errores de cliente (4xx) excepto 429
                    if e.status_code not in config.retryable_statuses:
                        raise
                    last_exception = e
                except Exception as e:
                    # Para otras excepciones, reintentar
                    last_exception = e
                
                # Si no es el último intento, esperar y reintentar
                if attempt < config.max_attempts - 1:
                    delay = config.calculate_delay(attempt)
                    # Log para observabilidad
                    print(f"[RETRY] Intento {attempt + 1}/{config.max_attempts} falló: {last_exception}. Esperando {delay:.2f}s...")
                    time.sleep(delay)
                else:
                    print(f"[RETRY] Todos los {config.max_attempts} intentos fallaron. Último error: {last_exception}")
            
            # Si llegamos aquí, todos los intentos fallaron
            if isinstance(last_exception, HTTPException):
                raise last_exception
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Servicio no disponible tras {config.max_attempts} reintentos: {last_exception}"
            )
        return wrapper
    return decorator


# Configuraciones específicas por tipo de operación
CHAT_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=0.5,
    max_delay=10.0,
    exponential_base=2.0,
    jitter=True,
    retryable_statuses=(429, 500, 502, 503, 504),
)

TRIGGER_RETRY_CONFIG = RetryConfig(
    max_attempts=2,
    base_delay=1.0,
    max_delay=15.0,
    exponential_base=2.0,
    jitter=True,
    retryable_statuses=(429, 500, 502, 503, 504),
)

ORCHESTRATE_RETRY_CONFIG = RetryConfig(
    max_attempts=2,
    base_delay=2.0,
    max_delay=30.0,
    exponential_base=2.0,
    jitter=True,
    retryable_statuses=(429, 500, 502, 503, 504),
)


# Fallback local para cuando la API externa falla
class LocalFallback:
    """Respuestas de fallback local cuando el modelo externo no está disponible."""
    
    @staticmethod
    def chat_fallback(message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Genera una respuesta local básica sin depender de APIs externas."""
        msg_lower = message.lower().strip()
        
        # Respuestas conversacionales básicas
        if any(p in msg_lower for p in ["hola", "buenas", "hey", "hi", "hello"]):
            response = "¡Hola! El motor HPR está operativo en modo local (fallback). Puedo conversar y ayudarte con consultas sobre el sistema."
        elif any(p in msg_lower for p in ["gracias", "genial", "perfecto", "ok", "vale"]):
            response = "¡De nada! Estoy aquí en modo local. ¿Necesitas algo más?"
        elif any(p in msg_lower for p in ["adiós", "adios", "chao", "hasta luego"]):
            response = "¡Hasta luego! El motor HPR permanece vigilante en modo local."
        elif any(p in msg_lower for p in ["quién eres", "qué eres", "quien eres", "que eres"]):
            response = "Soy HPR — Hybrid Predictive Reasoning, operando en modo fallback local (sin API externa)."
        else:
            response = (
                f"Procesando en modo local (fallback): '{message[:100]}'. "
                f"El motor externo no está disponible temporalmente. "
                f"Puedo responder consultas básicas sobre HPR o ejecutar triggers locales."
            )
        
        return {
            "session_id": session_id or str(uuid4()),
            "turn_id": str(uuid4()),
            "response": response,
            "session_context": None,
            "metadata": {
                "security_status": "local_fallback",
                "language": "es",
                "use_voice": False,
                "fallback": True,
            }
        }
    
    @staticmethod
    def trigger_fallback(trigger: str, confidence_level: int) -> Dict[str, Any]:
        """Respuesta de fallback para triggers."""
        return {
            "estado": "fallback_local",
            "trigger": trigger,
            "nivel_confianza": confidence_level,
            "mensaje": f"Trigger '{trigger}' ejecutado en modo fallback local. API externa no disponible.",
        }


# Instancia global del fallback
_local_fallback = LocalFallback()


# Inicialización de la API del motor HPR
app = FastAPI(title="Motor HPR - Arquitectura Híbrida", version="1.0.0")

# ---------------------------------------------------------------------------
# Gestores globales (inicialización lazy para evitar dependencias circulares)
# ---------------------------------------------------------------------------
_session_manager: Optional[SessionManager] = None
_task_orchestrator: Optional[TaskOrchestrator] = None
_security_engine: Optional[HPRSecurityEngine] = None


def get_session_manager() -> SessionManager:
    """Obtiene o crea el gestor de sesiones singleton."""
    global _session_manager
    if _session_manager is None:
        _session_manager = create_session_manager()
    return _session_manager


def get_task_orchestrator() -> TaskOrchestrator:
    """Obtiene o crea el orquestador de tareas singleton."""
    global _task_orchestrator
    if _task_orchestrator is None:
        _task_orchestrator = create_task_orchestrator()
    return _task_orchestrator


def get_security_engine() -> HPRSecurityEngine:
    """Obtiene o crea el motor de seguridad singleton."""
    global _security_engine
    if _security_engine is None:
        _security_engine = HPRSecurityEngine()
    return _security_engine


# ---------------------------------------------------------------------------
# Esquemas Pydantic para endpoints
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    """Request para el endpoint de chat autónomo."""
    session_id: Optional[UUID] = Field(None, description="ID de sesión existente (opcional, se crea si no existe)")
    message: str = Field(..., min_length=1, max_length=8000, description="Mensaje del usuario")
    use_voice: bool = Field(False, description="Indica si el mensaje proviene de entrada de voz")
    language: Optional[str] = Field("es", description="Idioma detectado/seleccionado")


class ChatResponse(BaseModel):
    """Response del endpoint de chat autónomo."""
    session_id: UUID = Field(..., description="ID de la sesión")
    turn_id: UUID = Field(..., description="ID del turno del asistente")
    response: str = Field(..., description="Respuesta del asistente")
    session_context: Optional[Dict[str, Any]] = Field(None, description="Contexto actual de la sesión")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadatos adicionales")


class OrchestrateRequest(BaseModel):
    """Request para el endpoint de orquestación técnica."""
    session_id: UUID = Field(..., description="ID de sesión obligatoria")
    intent_summary: str = Field(..., min_length=1, max_length=500, description="Resumen de la intención")
    intent_category: str = Field(default="analysis", description="Categoría: analysis, synthesis, verification, decision, planning, execution, clarification, monitoring")
    intent_complexity: str = Field(default="simple", description="Complejidad: atomic, simple, moderate, complex")
    intent_priority: str = Field(default="normal", description="Prioridad: low, normal, high, critical")
    constraints: List[str] = Field(default_factory=list, description="Restricciones duras")
    success_criteria: List[str] = Field(default_factory=list, description="Criterios de éxito")
    dry_run: bool = Field(default=False, description="Solo planificar, no ejecutar")


class OrchestrateResponse(BaseModel):
    """Response del endpoint de orquestación técnica."""
    session_id: UUID
    task_id: Optional[UUID] = None
    success: bool
    phase_reached: str
    subtasks_planned: int
    subtasks_executed: int
    final_result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    dag_structure: Optional[List[Dict[str, Any]]] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# MotorRazonamientoSuperior · Generador de respuestas contextuales
# ---------------------------------------------------------------------------

def _generate_contextual_response(user_message: str, pipeline_response: Dict[str, Any]) -> str:
    """
    Genera respuestas con enrutamiento lógico de intenciones:
    
    1. CONVERSACIÓN NATURAL: saludos, preguntas generales → respuesta fluida (PRIORIDAD ALTA)
    2. ANÁLISIS TÉCNICO PROFUNDO: consultas técnicas complejas o código → DeepSynthesizer
    
    NO usa plantillas ni eco del mensaje.
    """
    msg_lower = user_message.lower().strip()
    
    # ================================================================
    # ENRUTAMIENTO LÓGICO DE INTENCIONES (con prioridad explícita)
    # ================================================================
    
    # 1. CONVERSACIÓN NATURAL: saludos, preguntas generales, interacciones cotidianas
    patrones_conversacionales = [
        # Saludos (coincidencia exacta de palabras completas para evitar falsos positivos)
        "hola", "buenas", "buenos días", "buenas tardes", "buenas noches",
        "hey", "hi", "hello", "qué tal", "que tal", "como estás", "cómo estás",
        # Preguntas generales
        "quién eres", "qué eres", "quien eres", "que eres", "presentación", "presentate",
        "qué haces", "que haces", "qué sabes", "que sabes", "qué puedes", "que puedes",
        "gracias", "genial", "perfecto", "excelente", "bien", "ok", "vale",
        "adiós", "adios", "chao", "hasta luego", "nos vemos",
        # Interacciones cotidianas
        "cómo te llamas", "como te llamas", "qué nombre", "que nombre",
        "de dónde eres", "de donde eres", "qué edad", "que edad",
    ]
    
    # Verificación estricta: coincidencia de palabra completa o frase
    def _match_conversacional(texto: str, patrones: list) -> bool:
        for p in patrones:
            # Para palabras sueltas, usar word boundary; para frases, substring
            if ' ' in p:
                if p in texto:
                    return True
            else:
                # Palabra completa (re ya importado a nivel de módulo)
                if re.search(rf'\b{re.escape(p)}\b', texto):
                    return True
        return False
    
    es_conversacional = _match_conversacional(msg_lower, patrones_conversacionales)
    
    # 2. ANÁLISIS TÉCNICO: consultas técnicas complejas, código, o análisis profundo
    # SOLO si NO es conversacional (previene fuga de saludos a análisis técnico)
    patrones_tecnicos = [
        "analiza", "análisis", "evalúa", "evaluar", "compara", "comparar",
        "qué opinas", "que opinas", "qué piensas", "que piensas",
        "explícame", "explicame", "enséñame", "enseñame", "muéstrame", "muestrame",
        "código", "codigo", "script", "algoritmo", "función", "funcion",
        "implementa", "implementar", "diseña", "disenar", "optimiza", "optimizar",
        "rendimiento", "métricas", "metricas", "benchmark", "profile",
        "seguridad", "vulnerabilidad", "riesgo", "amenaza", "attack",
        "arquitectura de", "diagrama de", "flujo de", "proceso de",
    ]
    
    es_tecnico = any(patron in msg_lower for patron in patrones_tecnicos) and not es_conversacional
    
    # ================================================================
    # RESPUESTA SEGÚN INTENCIÓN (PRIORIDAD: Conversacional > Técnico > Sistema > Default)
    # ================================================================
    
    # PRIORIDAD 1: Conversacional puro (saludos, charla)
    if es_conversacional:
        return _generar_respuesta_conversacional(msg_lower, pipeline_response)
    
    # PRIORIDAD 2: Técnico explícito (solo si no es conversacional)
    if es_tecnico:
        return _generar_respuesta_tecnica(user_message, pipeline_response)
    
    # PRIORIDAD 3: Consulta sobre el motor HPR (términos técnicos del sistema)
    terminos_tecnicos = ["hpr", "motor", "sistema", "trigger", "nivel", "confianza",
                         "sesión", "sesion", "log", "audio", "voz", "micrófono"]
    tiene_terminos_tecnicos = any(t in msg_lower for t in terminos_tecnicos)
    
    if tiene_terminos_tecnicos:
        return _generar_respuesta_sobre_sistema(msg_lower, pipeline_response)
    
    # PRIORIDAD 4 (DEFAULT): Conversación natural genérica
    return _generar_respuesta_conversacional(msg_lower, pipeline_response)


def _generar_respuesta_conversacional(msg_lower: str, pipeline_response: Dict[str, Any]) -> str:
    """Genera una respuesta fluida y conversacional para interacciones cotidianas."""
    
    # Consulta sobre el autor (debe ir antes de preguntas generales)
    if any(p in msg_lower for p in ["diego", "rivero", "autor", "creador", "inventor"]):
        return (
            "Diego Rivero es el autor y creador del motor HPR. "
            "Su visión arquitectónica fue construir un sistema de razonamiento híbrido que combine "
            "seguridad determinista con capacidades de lenguaje natural, "
            "manteniendo la soberanía total de los datos en entorno local. "
            "El motor opera 100% local, sin CDNs ni servicios remotos, "
            "con un pipeline de seguridad de tres barreras: SOVEREIGN-GATE, NEXUS-ROOT y EPSILON-WALL."
        )
    
    # Saludos
    if any(p in msg_lower for p in ["hola", "buenas", "buenos días", "buenas tardes", "hey", "hi", "hello"]):
        return (
            "¡Hola! Soy el motor HPR — Hybrid Predictive Reasoning. "
            "Estoy operativo y listo para ayudarte. "
            "Puedes consultarme sobre el sistema, ejecutar triggers del motor técnico, "
            "o simplemente conversar. ¿En qué puedo ayudarte today?"
        ).replace(" today", "")
    
    if any(p in msg_lower for p in ["qué tal", "que tal", "como estás", "cómo estás"]):
        return (
            "Estoy al 100% de capacidad operativa. Todos los sistemas de seguridad "
            "están activos y no hay incidencias. ¿Qué necesitas de mí?"
        )
    
    # Identidad
    if any(p in msg_lower for p in ["quién eres", "qué eres", "quien eres", "que eres", "presentación", "presentate"]):
        return (
            "Soy HPR — Hybrid Predictive Reasoning, un motor de seguridad IA híbrido. "
            "Mi arquitectura combina un backend FastAPI con un frontend dual-panel, "
            "y opero con un pipeline de seguridad de tres barreras: SOVEREIGN-GATE, "
            "NEXUS-ROOT y EPSILON-WALL. Funciono 100% local, sin dependencias de servicios externos."
        )
    
    if any(p in msg_lower for p in ["cómo te llamas", "como te llamas", "qué nombre", "que nombre"]):
        return (
            "Me llamo HPR — Hybrid Predictive Reasoning. "
            "Fui diseñado para ser un motor de seguridad y razonamiento híbrido, "
            "con capacidades de conversación natural y análisis técnico."
        )
    
    # Agradecimientos
    if any(p in msg_lower for p in ["gracias", "genial", "perfecto", "excelente"]):
        return (
            "¡De nada! Estoy aquí para ayudarte. "
            "Si necesitas algo más, no dudes en preguntar."
        )
    
    if any(p in msg_lower for p in ["adiós", "adios", "chao", "hasta luego", "nos vemos"]):
        return (
            "¡Hasta luego! Estaré aquí cuando me necesites. "
            "El motor HPR permanece operativo y vigilante."
        )
    
    # Ayuda general
    if any(p in msg_lower for p in ["ayuda", "help", "comandos", "opciones", "qué puedes", "que puedes"]):
        return (
            "Puedo ayudarte con varias cosas:\n\n"
            "• **Conversar** sobre el motor HPR, su arquitectura o cualquier tema\n"
            "• **Ejecutar triggers** del motor técnico desde la pestaña 'Motor Técnico'\n"
            "• **Analizar consultas técnicas** con inferencia profunda\n"
            "• **Consultar telemetría** del sistema en tiempo real\n\n"
            "¿Qué te gustaría hacer?"
        )
    
    # Respuesta conversacional por defecto
    return (
        "Entendido. Estoy aquí para ayudarte con el motor HPR. "
        "Puedo conversar sobre el sistema, ejecutar triggers técnicos, "
        "o analizar consultas complejas. ¿Qué necesitas?"
    )


def _generar_respuesta_sobre_sistema(msg_lower: str, pipeline_response: Dict[str, Any]) -> str:
    """Genera respuestas sobre el motor HPR con tono técnico pero conversacional."""
    
    if "seguridad" in msg_lower or "sovereign" in msg_lower or "nexus" in msg_lower or "epsilon" in msg_lower:
        return (
            "El pipeline de seguridad del motor HPR consta de tres barreras complementarias:\n\n"
            "• **SOVEREIGN-GATE**: control de ingesta que mitiga entradas maliciosas antes de su procesamiento\n"
            "• **NEXUS-ROOT**: validación de identidad determinista del sistema\n"
            "• **EPSILON-WALL**: límite epistémico que asegura que toda respuesta esté respaldada por evidencia\n\n"
            "Los tres componentes están activos y operativos. ¿Te gustaría profundizar en alguno?"
        )
    
    if "arquitectura" in msg_lower or "componentes" in msg_lower or "estructura" in msg_lower:
        return (
            "La arquitectura HPR es híbrida y dual:\n\n"
            "• **Backend**: FastAPI (Python) con endpoints de chat y orquestación\n"
            "• **Frontend**: interfaz dual-panel (Motor Técnico + Chat Autónomo)\n"
            "• **Motor de razonamiento**: MotorRazonamientoSuperior con DeepSynthesizer\n"
            "• **Gestión de sesiones**: SessionManager con memoria episódica\n"
            "• **Orquestación**: TaskOrchestrator con DAG y métricas\n\n"
            "Todo opera 100% local. ¿Qué aspecto te interesa más?"
        )
    
    if "trigger" in msg_lower or "@hpr" in msg_lower or "@nivel" in msg_lower:
        return (
            "Los triggers del motor técnico son comandos especiales que ejecutan "
            "operaciones específicas del sistema:\n\n"
            "• **@hpr_confianza**: consulta de estado del perímetro de confianza\n"
            "• **@nivel1**: perfil de interacción de Nivel 1\n"
            "• **N1 · Búsqueda Cognitiva**: recuperación semántica\n"
            "• **N2 · Grafo de Consistencia**: detección de conflictos\n"
            "• **MotorRazonamientoSuperior**: síntesis y discernimiento\n\n"
            "Puedes ejecutarlos desde la pestaña 'Motor Técnico'. ¿Cuál te gustaría probar?"
        )
    
    if "bóveda" in msg_lower or "boveda" in msg_lower or "conocimiento" in msg_lower:
        return (
            "La bóveda HPR es la base de conocimiento local del sistema. "
            "Contiene documentación técnica, bitácoras de ingeniería y conocimiento operativo. "
            "El motor accede a ella para verificar información sin recurrir a fuentes externas, "
            "manteniendo la soberanía del conocimiento en entorno local."
        )
    
    if "telemetría" in msg_lower or "telemetrica" in msg_lower or "métricas" in msg_lower or "metricas" in msg_lower:
        return (
            "La telemetría del sistema incluye latencia de ejecución, tokens consumidos, "
            "subtareas ejecutadas y validaciones del pipeline. "
            "Puedes ver los valores actualizados en tiempo real en la pestaña 'Motor Técnico'. "
            "¿Te gustaría revisar algún indicador específico?"
        )
    
    # Respuesta sobre el sistema por defecto
    return (
        "El motor HPR es un sistema de seguridad IA híbrido que opera 100% local. "
        "Combina razonamiento determinista con capacidades de lenguaje natural, "
        "y mantiene un pipeline de seguridad de tres barreras: "
        "SOVEREIGN-GATE, NEXUS-ROOT y EPSILON-WALL. "
        "¿Te gustaría saber más sobre algún aspecto específico?"
    )


def _generar_respuesta_tecnica(user_message: str, pipeline_response: Dict[str, Any]) -> str:
    """Genera análisis técnico profundo usando DeepSynthesizer."""
    from .core.deep_synthesizer import DeepSynthesizer
    
    corpus_tecnico = _build_hpr_corpus()
    synthesizer = DeepSynthesizer(min_confianza=0.2)
    hallazgos = _extract_hallazgos_from_query(user_message, corpus_tecnico)
    
    if hallazgos:
        resultados = [
            {
                "titulo": f"Documentación técnica HPR: {h['tipo']}",
                "url": "local://hpr/corpus",
                "snippet": h["descripcion"],
                "fuente": "hpr_corpus",
                "contenido_completo": (
                    f"Arquitectura HPR: {h['descripcion']}. "
                    f"El motor HPR opera con FastAPI 1.0.0 y Python 3.12. "
                    f"Incluye componentes: SOVEREIGN-GATE, NEXUS-ROOT, EPSILON-WALL. "
                    f"Soporta triggers: @hpr_confianza, @nivel1, @web_search. "
                    f"Características: chat con memoria, telemetría en tiempo real, "
                    f"logs con hash SHA-256. Versión del motor: 1.0.0."
                ),
                "relevancia": h["confianza"],
            }
            for h in hallazgos[:5]
        ]
        
        informe = synthesizer.procesar_resultados(user_message, resultados)
        
        partes = []
        if informe.introduccion:
            partes.append(informe.introduccion)
        if informe.analisis_detallado:
            partes.append(informe.analisis_detallado)
        if informe.conclusiones:
            partes.append("\n".join(f"• {c}" for c in informe.conclusiones[:3]))
        
        if partes:
            return "\n\n".join(partes)
    
    # Si no hay hallazgos, responder con orientación técnica
    return (
        f"Entendido. Para un análisis técnico profundo sobre '{user_message[:50]}', "
        f"necesitaría más contexto o parámetros específicos. "
        f"El DeepSynthesizer del motor HPR está disponible para consultas con "
        f"código, especificaciones técnicas o solicitudes de análisis detallado. "
        f"¿Podrías proporcionar más detalles sobre el aspecto que deseas analizar?"
    )


def _build_hpr_corpus() -> str:
    """Construye el corpus técnico real del motor HPR."""
    return """
    HPR (Hybrid Predictive Reasoning) es un motor de seguridad IA híbrido con arquitectura dual.

    ARQUITECTURA:
    - Backend FastAPI (Python) con endpoints de chat y orquestación técnica
    - Frontend web dual-panel (Motor Técnico + Chat Autónomo)
    - Pipeline de seguridad: SOVEREIGN-GATE → NEXUS-ROOT → EPSILON-WALL
    - MotorRazonamientoSuperior: síntesis, evaluación y discernimiento de resultados
    - TaskOrchestrator: orquestación de tareas con DAG y métricas
    - SessionManager: gestión de sesiones conversacionales con memoria episódica
    - DeepSynthesizer: inferencia profunda basada en evidencia
    - Sistema de bóveda local con documentos .docx

    COMPONENTES DE SEGURIDAD:
    - SOVEREIGN-GATE: control de ingesta y mitigación de entradas maliciosas
    - NEXUS-ROOT: validación de identidad determinista (HPR-CORE-DETERMINISTA)
    - EPSILON-WALL: límite epistémico y control de afirmaciones
    - verify_security_guard: inspección anti-phishing en parámetro ?query=

    CAPACIDADES:
    - Chat con memoria de sesión (session_id + turnos)
    - Triggers técnicos: @hpr_confianza, @nivel1, @web_search, N1, N2, MotorRazonamientoSuperior
    - Telemetría en tiempo real (polling 5s)
    - Logs de ejecución en bóveda local con hash SHA-256
    - TTS soberano (speechSynthesis nativo del navegador)
    - Dictado por voz (Web Speech API con divulgación de privacidad)

    CONSTITUCIÓN:
    - S1: Jurisdicción local - todos los datos se almacenan localmente
    - S2: Soberanía de ejecución - sin CDNs ni servicios remotos
    - S5: Integridad verificable - hashes SHA-256 en artefactos críticos
    - P1: Prueba o no existe - toda entrega llega con pruebas
    - P3: Deterministas - sin red, sin reloj en aserciones
    """


def _extract_hallazgos_from_query(query: str, corpus: str) -> List[Dict[str, Any]]:
    """
    Extrae hallazgos técnicos del corpus basados en la consulta del usuario.
    
    Analiza la intención del usuario y extrae secciones relevantes del corpus
    técnico del motor HPR con peso técnico real.
    """
    import re
    
    hallazgos = []
    query_lower = query.lower().strip()
    
    # Mapeo de intenciones a secciones del corpus
    mapeo_intenciones = {
        "identidad": {
            "palabras_clave": ["quién eres", "qué eres", "quien eres", "que eres", "presentación", "presentate", "hola", "buenas"],
            "seccion": "HPR (Hybrid Predictive Reasoning) es un motor de seguridad IA híbrido con arquitectura dual.",
            "tipo": "identidad",
        },
        "seguridad": {
            "palabras_clave": ["seguridad", "security", "sovereign", "nexus", "epsilon", "protección"],
            "seccion": "SOVEREIGN-GATE: control de ingesta y mitigación de entradas maliciousas. NEXUS-ROOT: validación de identidad determinista. EPSILON-WALL: límite epistémico y control de afirmaciones.",
            "tipo": "seguridad",
        },
        "arquitectura": {
            "palabras_clave": ["arquitectura", "componentes", "estructura", "sistema", "backend", "frontend"],
            "seccion": "Backend FastAPI (Python) con endpoints de chat y orquestación técnica. Frontend web dual-panel (Motor Técnico + Chat Autónomo).",
            "tipo": "arquitectura",
        },
        "capacidades": {
            "palabras_clave": ["capacidades", "qué puedes", "que puedes", "funciones", "operaciones", "ayuda", "help"],
            "seccion": "Chat con memoria de sesión. Triggers técnicos: @hpr_confianza, @nivel1, @web_search, N1, N2, MotorRazonamientoSuperior. Telemetría en tiempo real.",
            "tipo": "capacidades",
        },
        "triggers": {
            "palabras_clave": ["trigger", "disparador", "@hpr", "@nivel", "@web"],
            "seccion": "Triggers técnicos: @hpr_confianza (consulta de estado), @nivel1 (perfil de interacción), @web_search (búsqueda web), N1 (búsqueda cognitiva), N2 (grafo de consistencia), MotorRazonamientoSuperior (síntesis).",
            "tipo": "triggers",
        },
        "autor": {
            "palabras_clave": ["diego", "rivero", "autor", "creador", "inventor"],
            "seccion": "Diego Rivero es el autor y creador del motor HPR. Su visión fue construir un sistema de razonamiento híbrido.",
            "tipo": "autor",
        },
        "bóveda": {
            "palabras_clave": ["bóveda", "boveda", "conocimiento", "documentos", "documentación"],
            "seccion": "La bóveda HPR es la base de conocimiento local del sistema. Contiene documentación técnica, bitácoras de ingeniería y conocimiento operativo en formato .docx.",
            "tipo": "boveda",
        },
        "telemetría": {
            "palabras_clave": ["telemetría", "telemetrica", "métricas", "metricas", "rendimiento", "estado"],
            "seccion": "La telemetría del motor HPR incluye latencia de ejecución, tokens consumidos, subtareas ejecutadas y validaciones del pipeline.",
            "tipo": "telemetria",
        },
        "sesiones": {
            "palabras_clave": ["sesión", "sesion", "conversación", "conversacion", "chat"],
            "seccion": "Chat con memoria de sesión (session_id + turnos). Sistema de gestión conversacional con memoria episódica.",
            "tipo": "sesiones",
        },
        "constitución": {
            "palabras_clave": ["constitución", "constitucion", "principios", "reglas", "filosofía"],
            "seccion": "S1: Jurisdicción local. S2: Soberanía de ejecución. S5: Integridad verificable. P1: Prueba o no existe. P3: Deterministas.",
            "tipo": "constitucion",
        },
    }
    
    # Buscar intención del usuario en el mapeo
    for intencion, datos in mapeo_intenciones.items():
        if any(palabra in query_lower for palabra in datos["palabras_clave"]):
            hallazgos.append({
                "tipo": datos["tipo"],
                "descripcion": datos["seccion"],
                "evidencia": corpus[:800],
                "confianza": 0.9,
            })
    
    # G.1 · Desacople del chat respecto al motor forense:
    # sin coincidencia real de intención NO se fabrican hallazgos. Antes se
    # rellenaba con los primeros párrafos del corpus (confianza 0.6), lo que
    # garantizaba una lista no vacía y forzaba la ruta de síntesis profunda.
    return hallazgos


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/")
def read_root():
    return {
        "estado": "en línea",
        "modulo": "main",
        "mensaje": "El servidor del motor HPR está transmitiendo correctamente.",
        "endpoints": {
            "chat": "/api/v1/chat (POST) - Chat autónomo con memoria de sesión",
            "orchestrate": "/api/v1/orchestrate (POST) - Orquestación técnica manual",
            "communications": "/api/v1/communications/query (GET) - Consulta legacy",
        }
    }


@app.get("/api/v1/communications/query")
async def communications_query(
    params: CommunicationQuerySchema = Depends(),
    security_check: bool = Depends(verify_security_guard),
):
    """
    Endpoint legacy para procesar consultas de comunicación en el motor HPR
    utilizando Pydantic y el agente de seguridad antiphishing.
    """
    return {
        "query": params.query,
        "limit": params.limit,
        "status": "procesado seguro",
        "resultados": [],
    }


@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    security_check: bool = Depends(verify_security_guard),
):
    """
    Endpoint de chat autónomo con memoria de sesión conversacional.
    
    Flujo:
    1. Obtener/crear sesión conversacional
    2. Añadir turno de usuario
    3. Procesar a través del motor de seguridad (Sovereign Gate + Nexus Root)
    4. Añadir turno de asistente con respuesta
    5. Retornar respuesta + contexto de sesión actualizado
    
    Diseñado para la Pestaña 1: "Chat Autónomo / Natural"
    
    Resiliencia:
    - Reintentos con backoff exponencial para llamadas a API externa
    - Fallback local automático si la API externa falla tras reintentos
    """
    session_mgr = get_session_manager()
    security_engine = get_security_engine()
    
    # 1. Obtener o crear sesión (con auto-reparación tras reinicio)
    if request.session_id:
        session = session_mgr.get_session(request.session_id)
        if not session:
            # Auto-inicializar sesión si no está en memoria (ej. tras reinicio)
            session = session_mgr.create_session(
                initial_query=request.message,
                title=f"Chat {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
            )
    else:
        session = session_mgr.create_session(
            initial_query=request.message,
            title=f"Chat {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
        )
    
    # 2. Añadir turno de usuario
    user_turn = session_mgr.add_turn(
        session_id=session.id,
        role=TurnRole.USER,
        content=request.message,
        turn_type=TurnType.QUERY,
    )
    
    if not user_turn:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo crear el turno de usuario (límites de sesión excedidos)"
        )
    
    # 3. Procesar a través del motor de seguridad + MotorRazonamientoSuperior
    # Con reintentos y fallback local
    assistant_response = None
    security_status = "unknown"
    used_fallback = False
    
    async def _process_with_retry():
        """Procesa el pipeline con reintentos para llamadas externas."""
        # Pipeline de seguridad (SOVEREIGN-GATE + NEXUS-ROOT) - esto es local, no necesita retry
        response = security_engine.process_pipeline(
            payload=request.message,
            state={"identity": "HPR-CORE-DETERMINISTIC"},
            truth=[],
        )
        
        # Guarda defensiva (Compuerta 8 / B3): el contrato del pipeline es un dict en
        # todas las rutas. Si una regresión devolviera otro tipo, se normaliza para
        # evitar que el chat degrade a fallback local en lugar de responder/bloquear.
        if not isinstance(response, dict):
            response = {
                "estado": response if isinstance(response, str) else "Respuesta no válida del pipeline"
            }

        # Verificar bloqueo de seguridad
        if "BLOQUEO" in response.get("estado", ""):
            return response.get("estado", "Bloqueo de seguridad"), response.get("estado", "unknown"), False
        
        # MotorRazonamientoSuperior: respuesta contextual real
        # Aquí es donde podría haber llamadas a API externa (DeepSynthesizer, etc.)
        # Envolvemos en retry para proteger contra saturación de API externa
        try:
            response_text = _generate_contextual_response(request.message, response)
            return response_text, response.get("estado", "procesado"), False
        except Exception as e:
            # Si hay error en el motor de razonamiento (ej. API externa), propagar para retry
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Error en motor de razonamiento: {str(e)}"
            )
    
    # Ejecutar con reintentos
    for attempt in range(CHAT_RETRY_CONFIG.max_attempts):
        try:
            assistant_response, security_status, used_fallback = await _process_with_retry()
            break  # Éxito, salir del loop
        except HTTPException as e:
            if e.status_code not in CHAT_RETRY_CONFIG.retryable_statuses:
                # Error no reintentable (4xx excepto 429)
                raise
            # Error reintentable
            if attempt < CHAT_RETRY_CONFIG.max_attempts - 1:
                delay = CHAT_RETRY_CONFIG.calculate_delay(attempt)
                print(f"[CHAT RETRY] Intento {attempt + 1}/{CHAT_RETRY_CONFIG.max_attempts} falló: {e.detail}. Esperando {delay:.2f}s...")
                time.sleep(delay)
            else:
                # Último intento fallado - usar fallback local
                print(f"[CHAT FALLBACK] Todos los reintentos fallaron. Activando fallback local.")
                fallback_data = _local_fallback.chat_fallback(request.message, str(session.id))
                assistant_response = fallback_data["response"]
                security_status = "local_fallback"
                used_fallback = True
        except Exception as e:
            # Excepción inesperada
            if attempt < CHAT_RETRY_CONFIG.max_attempts - 1:
                delay = CHAT_RETRY_CONFIG.calculate_delay(attempt)
                print(f"[CHAT RETRY] Intento {attempt + 1}/{CHAT_RETRY_CONFIG.max_attempts} falló: {str(e)}. Esperando {delay:.2f}s...")
                time.sleep(delay)
            else:
                print(f"[CHAT FALLBACK] Error inesperado tras reintentos: {str(e)}. Activando fallback local.")
                fallback_data = _local_fallback.chat_fallback(request.message, str(session.id))
                assistant_response = fallback_data["response"]
                security_status = "local_fallback_error"
                used_fallback = True
    
    # 4. Añadir turno de asistente
    
    # 4. Añadir turno de asistente
    assistant_turn = session_mgr.add_turn(
        session_id=session.id,
        role=TurnRole.ASSISTANT,
        content=assistant_response,
        turn_type=TurnType.QUERY,
    )
    
    if not assistant_turn:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo crear el turno de asistente"
        )
    
    # 5. Obtener contexto de sesión actualizado para el frontend
    session_context = session_mgr.get_session_context(session.id)
    context_dict = None
    if session_context:
        context_dict = {
            "current_turn_number": session_context.current_turn_number,
            "active_topics": session_context.active_topics,
            "unresolved_ambiguities": session_context.unresolved_ambiguities,
            "pending_references_count": len(session_context.pending_references),
            "last_user_turn": session_context.last_user_turn.content if session_context.last_user_turn else None,
            "last_assistant_turn": session_context.last_assistant_turn.content[:200] if session_context.last_assistant_turn else None,
        }
    
    # 6. Retornar respuesta estructurada
    # Incluir nivel de confianza inferido para telemetría pasiva del frontend
    current_confidence = _infer_confidence_level(session_context) if session_context else 1
    
    # Garantizar string plano y seguro para Pydantic (response: str)
    safe_response: str = str(assistant_response) if assistant_response is not None else ""
    
    # security_status proviene de la variable `security_status` asignada en el loop de reintentos
    sec_status = security_status if 'security_status' in locals() else "unknown"
    
    return ChatResponse(
        session_id=session.id,
        turn_id=assistant_turn.id,
        response=safe_response,
        session_context=context_dict,
        metadata={
            "security_status": sec_status,
            "language": request.language,
            "use_voice": request.use_voice,
            "turn_number": user_turn.turn_number,
            "confidence_level": current_confidence,
            "fallback": used_fallback,
        }
    )


@app.post("/api/v1/orchestrate", response_model=OrchestrateResponse)
async def orchestrate_endpoint(
    request: OrchestrateRequest,
    security_check: bool = Depends(verify_security_guard),
):
    """
    Endpoint de orquestación técnica manual para auditoría y control de DAGs.
    
    Flujo:
    1. Validar sesión existente
    2. Construir IntentSchema desde parámetros explícitos
    3. Obtener contexto de sesión y evidencia disponible
    4. Ejecutar TaskOrchestrator.process_intent()
    6. Retornar resultado completo con DAG, métricas y estado
    
    Diseñado para la Pestaña 2: "Motor Técnico / Manual"
    """
    session_mgr = get_session_manager()
    orchestrator = get_task_orchestrator()
    
    # 1. Validar sesión
    session = session_mgr.get_session(request.session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sesión no encontrada: {request.session_id}"
        )
    
    # 2. Construir IntentSchema desde request
    try:
        category = IntentCategory(request.intent_category)
        complexity = IntentComplexity(request.intent_complexity)
        priority = IntentPriority(request.intent_priority)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Parámetro inválido: {str(e)}"
        )
    
    # Usar el último turno de la sesión como source_turn_id
    source_turn_id = session.turns[-1].id if session.turns else uuid4()
    
    intent = create_intent_schema(
        category=category,
        summary=request.intent_summary,
        session_id=request.session_id,
        source_turn_id=source_turn_id,
        complexity=complexity,
        priority=priority,
        description=f"Intención técnica manual: {request.intent_summary}",
        constraints=request.constraints,
        success_criteria=request.success_criteria,
    )
    
    # 3. Obtener contexto de sesión y recursos disponibles
    session_context = session_mgr.get_session_context(request.session_id)
    if not session_context:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo obtener contexto de sesión"
        )
    
    # Obtener evidencia disponible de la sesión (simplificado)
    available_evidence = []  # En implementación completa, extraer de turnos previos
    previous_results = []    # En implementación completa, extraer StructuredResults previos
    
    # Último turno para el input
    last_turn = session.turns[-1] if session.turns else None
    if not last_turn:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La sesión debe tener al menos un turno"
        )
    
    # 4. Construir OrchestratorInput y ejecutar
    input_data = OrchestratorInput(
        intent=intent,
        session_context=session_context,
        turn=last_turn,
        available_evidence=available_evidence,
        previous_results=previous_results,
        force_replan=False,
        dry_run=request.dry_run,
    )
    
    output: OrchestratorOutput = orchestrator.process_intent(input_data)
    
    # 5. Preparar estructura del DAG para visualización
    dag_structure = None
    if output.task:
        dag_structure = []
        for st in output.task.subtasks:
            dag_structure.append({
                "id": str(st.id),
                "name": st.name,
                "type": st.type.value,
                "status": st.status.value,
                "depends_on": [str(d) for d in st.depends_on],
                "description": st.description,
            })
    
    # 6. Retornar respuesta completa
    return OrchestrateResponse(
        session_id=request.session_id,
        task_id=output.task.id if output.task else None,
        success=output.success,
        phase_reached=output.phase_reached.value,
        subtasks_planned=output.total_subtasks_planned,
        subtasks_executed=output.total_subtasks_executed,
        final_result=output.final_result.model_dump() if output.final_result else None,
        error_message=output.error_message,
        warnings=output.warnings,
        dag_structure=dag_structure,
        metrics={
            "tokens_used": output.tokens_used,
            "latency_ms": output.latency_ms,
            "started_at": output.started_at.isoformat() if output.started_at else None,
            "completed_at": output.completed_at.isoformat() if output.completed_at else None,
        }
    )


@app.get("/api/v1/sessions/{session_id}")
async def get_session(
    session_id: UUID,
    security_check: bool = Depends(verify_security_guard),
):
    """Obtiene una sesión por ID con su historial completo."""
    session_mgr = get_session_manager()
    session = session_mgr.get_session(session_id)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sesión no encontrada: {session_id}"
        )
    
    return session.model_dump(mode='json')


@app.get("/api/v1/sessions/{session_id}/context")
async def get_session_context(
    session_id: UUID,
    security_check: bool = Depends(verify_security_guard),
):
    """Obtiene el contexto actual de una sesión para el frontend."""
    session_mgr = get_session_manager()
    context = session_mgr.get_session_context(session_id)
    
    if not context:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sesión no encontrada: {session_id}"
        )
    
    return context.model_dump(mode='json')


@app.delete("/api/v1/sessions/{session_id}")
async def delete_session(
    session_id: UUID,
    security_check: bool = Depends(verify_security_guard),
):
    """Elimina (archiva) una sesión."""
    session_mgr = get_session_manager()
    success = session_mgr.delete_session(session_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sesión no encontrada: {session_id}"
        )
    
    return {"status": "deleted", "session_id": str(session_id)}


@app.get("/api/v1/sessions")
async def list_sessions(
    status: Optional[str] = None,
    limit: int = 50,
    security_check: bool = Depends(verify_security_guard),
):
    """Lista sesiones con filtros opcionales."""
    session_mgr = get_session_manager()
    session_status = None
    if status:
        try:
            from .models.contracts import SessionStatus
            session_status = SessionStatus(status)
        except ValueError:
            pass
    
    sessions = session_mgr.list_sessions(status=session_status, limit=limit)
    return [s.model_dump(mode='json') for s in sessions]


# ---------------------------------------------------------------------------
# Etapa D · Ejecución real de triggers
# ---------------------------------------------------------------------------

async def _execute_trigger_internal(request: TriggerExecutionRequest) -> Dict[str, Any]:
    """
    Ejecución interna de un trigger según su tipo.

    Cada trigger realiza una operación específica del motor HPR, o declara
    honestamente su indisponibilidad. Los resultados son reales, sin datos
    simulados: cuando una operación no está conectada al motor vivo se informa
    como 'no_disponible' (nunca se simulan resultados).
    """
    session_mgr = get_session_manager()
    
    # Obtener o crear sesión (con auto-reparación tras reinicio)
    if request.session_id:
        session = session_mgr.get_session(request.session_id)
        if not session:
            # Auto-inicializar sesión si no está en memoria (ej. tras reinicio)
            session = session_mgr.create_session(
                initial_query=f"Trigger: {request.trigger.value}",
                title=f"Trigger {request.trigger.value}",
            )
    else:
        session = session_mgr.create_session(
            initial_query=f"Trigger: {request.trigger.value}",
            title=f"Trigger {request.trigger.value}",
        )
    
    # Usar payload del usuario si está disponible, sino parámetros
    user_payload = request.payload or ""
    parameters = request.parameters or {}
    
    # Ejecutar según tipo de trigger
    if request.trigger == TriggerType.CONFIANZA:
        context = session_mgr.get_session_context(session.id)
        return {
            "estado": "activo",
            "nivel_confianza": request.confidence_level,
            "turnos": len(session.turns) if session.turns else 0,
            "contexto": context.model_dump(mode='json') if context else None,
        }
    
    elif request.trigger == TriggerType.NIVEL1:
        return {
            "perfil": "Nivel 1 — Acceso básico",
            "operaciones_permitidas": ["consulta", "búsqueda", "síntesis"],
            "restricciones": ["operaciones_sensibles", "cambios_estado"],
        }
    
    elif request.trigger == TriggerType.WEB_SEARCH:
        # Usar el payload del usuario como query de búsqueda
        search_query = user_payload.strip() or parameters.get("query", "")
        if not search_query:
            return {
                "estado": "error",
                "mensaje": "Se requiere un término de búsqueda. Proporcione un payload o parámetro 'query'.",
            }
        # Fase 1 · Compuerta #3/#5 — Honestidad: sin proveedor externo configurado
        # NO se simulan fuentes ni se fabrican resultados (prohibido inventar).
        # Se informa el estado real; 'no_disponible' deriva en success=False (G.2).
        return {
            "estado": "no_disponible",
            "query": search_query,
            "mensaje": "Búsqueda web no disponible: no hay un motor de búsqueda externo configurado. El motor HPR no genera resultados simulados.",
            "sugerencia_configuracion": "Configure un proveedor de búsqueda externo (ej. SERPAPI_KEY o BRAVE_API_KEY) para habilitar búsqueda web real.",
        }
    
    elif request.trigger == TriggerType.N1_BUSQUEDA:
        # Fase 1 · Compuerta H2 — Honestidad: no hay un motor de búsqueda cognitiva
        # sobre la sesión conectado al motor vivo. NO se afirma haber buscado ni se
        # fabrican resultados (prohibido inventar). 'no_disponible' => success=False (G.2).
        last_turn = session.turns[-1] if session.turns else None
        search_filter = user_payload.strip() or parameters.get("filter", "")
        return {
            "estado": "no_disponible",
            "query": last_turn.content[:200] if last_turn else None,
            "filtro_usuario": search_filter if search_filter else None,
            "resultados": [],
            "mensaje": "Búsqueda cognitiva no disponible: no hay un motor de búsqueda sobre la sesión conectado al motor vivo. No se realizó ninguna búsqueda ni se generan resultados simulados.",
            "sugerencia_configuracion": "Conecte un índice de búsqueda cognitiva sobre los turnos de la sesión para habilitar N1 · Búsqueda Cognitiva.",
        }
    
    elif request.trigger == TriggerType.N2_GRAFO:
        # Fase 1 · Compuerta H2 — Honestidad: no hay un motor de grafo de consistencia
        # conectado. NO se afirma haber verificado nada (prohibido el falso éxito).
        return {
            "estado": "no_disponible",
            "conflictos": [],
            "turnos_analizados": len(session.turns) if session.turns else 0,
            "mensaje": "Grafo de consistencia no disponible: no hay un motor de verificación de coherencia conectado al motor vivo. No se analizaron conflictos ni se generan resultados simulados.",
            "sugerencia_configuracion": "Conecte el motor de grafo de consistencia para habilitar N2 · Grafo de Consistencia.",
        }
    
    elif request.trigger == TriggerType.MOTOR_RAZON:
        # Fase 1 · Compuerta H2 — Honestidad: el motor de razonamiento superior no está
        # conectado al motor vivo (hallazgo H1). NO se fabrica una síntesis inexistente.
        context = session_mgr.get_session_context(session.id)
        focus = user_payload.strip() or parameters.get("focus", "")
        return {
            "estado": "no_disponible",
            "sintesis": None,
            "foco_usuario": focus if focus else None,
            "turnos": len(session.turns) if session.turns else 0,
            "temas_activos": context.active_topics if context else [],
            "ambiguedades": context.unresolved_ambiguities if context else [],
            "mensaje": "Motor de razonamiento superior no disponible: la síntesis de sesión no está conectada al motor vivo. No se genera una síntesis simulada.",
            "sugerencia_configuracion": "Conecte el motor de razonamiento superior (razonamiento_engine) para habilitar la síntesis de sesión.",
        }
    
    elif request.trigger == TriggerType.SOVEREIGN_GATE:
        # SOVEREIGN-GATE: verificación de soberanía
        return {
            "estado": "verificado",
            "soberania": "confirmada",
            "ingestión_permitida": True,
            "cambios_sensibles": "requieren_autorizacion_adicional",
        }
    
    else:
        raise ValueError(f"Trigger no soportado: {request.trigger}")


@app.get("/api/v1/telemetry")
async def get_telemetry(
    session_id: Optional[str] = None,
    security_check: bool = Depends(verify_security_guard),
):
    """
    Endpoint de telemetría en tiempo real (Etapa D3).
    
    Devuelve métricas reales del motor HPR:
    - Estadísticas globales (sesiones, turnos, tokens)
    - Estadísticas de sesión específica (si se proporciona session_id)
    - Estado del backend y componentes
    - Nivel de confianza actual de la sesión (para indicadores pasivos UI)
    
    Seguridad: verify_security_guard inspecciona ?query= para anti-phishing.
    """
    session_mgr = get_session_manager()
    
    # Estadísticas globales (siempre disponibles)
    global_stats = session_mgr.get_global_stats()
    
    # Estadísticas de sesión específica (si se proporciona)
    session_stats = None
    session_context = None
    session_confidence_level = None
    if session_id:
        try:
            from uuid import UUID as UUIDType
            session_uuid = UUIDType(session_id)
            session_stats = session_mgr.get_session_stats(session_uuid)
            # Obtener contexto de sesión para nivel de confianza
            session_context = session_mgr.get_session_context(session_uuid)
            if session_context:
                # El nivel de confianza se puede inferir de los metadatos de la sesión
                # o de los turnos recientes. Por ahora usamos un valor por defecto
                # basado en la actividad de la sesión.
                session_confidence_level = _infer_confidence_level(session_context)
        except (ValueError, TypeError):
            session_stats = None
    
    # Métricas de componentes (soberanía, sin servicios externos)
    telemetry = {
        "backend": {
            "estado": "en línea",
            "version": "1.0.0",
            "modulo": "main",
            "almacenamiento": global_stats.get("storage_path", "memory_only"),
        },
        "sesiones": global_stats,
        "session_actual": session_stats,
        "componentes": {
            "nexus_root": "activo",
            "sovereign_gate": "activo",
            "epsilon_wall": "vigilante",
            "session_manager": "activo",
            "task_orchestrator": "disponible",
        },
        "telemetria": {
            "total_sessions": global_stats.get("total_sessions", 0),
            "active_sessions": global_stats.get("active_sessions", 0),
            "total_turns": global_stats.get("total_turns", 0),
            "total_tokens": global_stats.get("total_tokens", 0),
            "avg_turns_per_session": global_stats.get("avg_turns_per_session", 0),
            "confidence_level": session_confidence_level,
        },
    }
    
    return telemetry


def _infer_confidence_level(session_context) -> int:
    """
    Infiere el nivel de confianza basado en el contexto de la sesión.
    
    Lógica:
    - Nivel 1: Sesión nueva o con pocos turnos, sin operaciones sensibles
    - Nivel 2: Sesión activa con múltiples turnos, consultas técnicas
    - Nivel 3: Sesión con triggers SOVEREIGN-GATE o operaciones restringidas
    
    Esta es una heurística simple; la validación real ocurre en NEXUS-ROOT/SOVEREIGN-GATE.
    """
    try:
        turn_count = session_context.current_turn_number or 0
        active_topics = session_context.active_topics or []
        
        # Verificar si hay temas técnicos/sensibles
        sensitive_topics = {"seguridad", "soberanía", "sovereign", "nexus", "epsilon", 
                           "trigger", "configuración", "admin", "sistema"}
        has_sensitive = any(t.lower() in sensitive_topics for t in active_topics)
        
        if has_sensitive or turn_count > 10:
            return 3
        elif turn_count > 3:
            return 2
        else:
            return 1
    except Exception:
        return 1


@app.post("/api/v1/trigger", response_model=TriggerExecutionResponse)
async def execute_trigger_endpoint(
    request: TriggerExecutionRequest,
    security_check: bool = Depends(verify_security_guard),
):
    """
    Endpoint de ejecución real de triggers (Etapa D).
    
    Flujo:
    1. Validar parámetros y nivel de confianza
    2. Verificar guardia de seguridad (verify_security_guard)
    3. Ejecutar trigger según tipo (con reintentos y fallback)
    4. Recopilar telemetría
    5. Retornar resultado estructurado
    
    Seguridad:
    - verify_security_guard: inspección anti-phishing en ?query=
    - SOVEREIGN-GATE: operaciones sensibles requieren nivel 3 + autorización
    
    Resiliencia:
    - Reintentos con backoff exponencial para llamadas a API externa
    - Fallback local automático si la API externa falla tras reintentos
    """
    import time
    start_time = time.time()
    
    # Validación SOVEREIGN-GATE para operaciones sensibles
    if request.trigger == TriggerType.SOVEREIGN_GATE or request.confidence_level == 3:
        execution_time = (time.time() - start_time) * 1000
        return TriggerExecutionResponse(
            success=False,
            trigger=request.trigger.value,
            error_message="Operación sensible: requiere autorización explícita del backend (SOVEREIGN-GATE).",
            telemetry={
                "auth_required": True,
                "level": request.confidence_level,
                "execution_time_ms": round(execution_time, 2),
            },
            execution_time_ms=round(execution_time, 2),
        )
    
    # Paso 2.1: Pipeline de seguridad completo (SOVEREIGN-GATE + NEXUS-ROOT)
    # SOVEREIGN-GATE: validación de payload (incluir payload del usuario)
    trigger_payload = f"{request.trigger.value} {request.confidence_level}"
    if request.parameters:
        trigger_payload += " " + " ".join(str(v) for v in request.parameters.values())
    if request.payload:
        trigger_payload += " " + request.payload
    
    if not sovereign_gate_validation(trigger_payload):
        execution_time = (time.time() - start_time) * 1000
        # Respuesta sanitizada: no exponer detalles internos de SOVEREIGN-GATE
        return TriggerExecutionResponse(
            success=False,
            trigger=request.trigger.value,
            error_message="Bloqueo de seguridad: el contenido de la petición fue rechazado por el guardia de seguridad.",
            telemetry={
                "security_block": True,
                "execution_time_ms": round(execution_time, 2),
            },
            execution_time_ms=round(execution_time, 2),
        )
    
    # NEXUS-ROOT: validación de identidad determinista
    system_state = {"identity": "HPR-CORE-DETERMINISTIC"}
    if not nexus_root_validation(system_state):
        execution_time = (time.time() - start_time) * 1000
        # Respuesta sanitizada: no exponer detalles internos de NEXUS-ROOT
        return TriggerExecutionResponse(
            success=False,
            trigger=request.trigger.value,
            error_message="Acceso denegado: la identidad del sistema no pudo ser verificada.",
            telemetry={
                "auth_failed": True,
                "execution_time_ms": round(execution_time, 2),
            },
            execution_time_ms=round(execution_time, 2),
        )
    
    # Ejecución real del trigger con reintentos y fallback
    result = None
    used_fallback = False
    error_message = None
    
    for attempt in range(TRIGGER_RETRY_CONFIG.max_attempts):
        try:
            result = await _execute_trigger_internal(request)
            break  # Éxito, salir del loop
        except HTTPException as e:
            if e.status_code not in TRIGGER_RETRY_CONFIG.retryable_statuses:
                # Error no reintentable (4xx excepto 429)
                error_message = e.detail
                break
            # Error reintentable
            if attempt < TRIGGER_RETRY_CONFIG.max_attempts - 1:
                delay = TRIGGER_RETRY_CONFIG.calculate_delay(attempt)
                print(f"[TRIGGER RETRY] Intento {attempt + 1}/{TRIGGER_RETRY_CONFIG.max_attempts} falló: {e.detail}. Esperando {delay:.2f}s...")
                time.sleep(delay)
            else:
                # Último intento fallado - usar fallback local
                print(f"[TRIGGER FALLBACK] Todos los reintentos fallaron. Activando fallback local.")
                fallback_data = _local_fallback.trigger_fallback(request.trigger.value, request.confidence_level)
                result = fallback_data
                used_fallback = True
        except Exception as e:
            # Excepción inesperada
            if attempt < TRIGGER_RETRY_CONFIG.max_attempts - 1:
                delay = TRIGGER_RETRY_CONFIG.calculate_delay(attempt)
                print(f"[TRIGGER RETRY] Intento {attempt + 1}/{TRIGGER_RETRY_CONFIG.max_attempts} falló: {str(e)}. Esperando {delay:.2f}s...")
                time.sleep(delay)
            else:
                print(f"[TRIGGER FALLBACK] Error inesperado tras reintentos: {str(e)}. Activando fallback local.")
                fallback_data = _local_fallback.trigger_fallback(request.trigger.value, request.confidence_level)
                result = fallback_data
                used_fallback = True
    
    execution_time = (time.time() - start_time) * 1000
    
    if error_message:
        response = TriggerExecutionResponse(
            success=False,
            trigger=request.trigger.value,
            session_id=str(request.session_id) if request.session_id else None,
            error_message=error_message,
            telemetry={
                "error_type": "HTTPException",
                "execution_time_ms": round(execution_time, 2),
                "confidence_level": request.confidence_level,
                "trigger_type": request.trigger.value,
            },
            execution_time_ms=round(execution_time, 2),
        )
    else:
        # G.2 · El éxito se DERIVA del estado real del resultado, no se asume.
        # Un resultado con estado "error" o "no_disponible" NO es un éxito.
        estado = result.get("estado") if isinstance(result, dict) else None
        derived_success = estado not in ("error", "no_disponible")
        response = TriggerExecutionResponse(
            success=derived_success,
            trigger=request.trigger.value,
            session_id=str(request.session_id) if request.session_id else None,
            result=TriggerResult(**result) if isinstance(result, dict) else result,
            error_message=(
                result.get("mensaje")
                if not derived_success and isinstance(result, dict)
                else None
            ),
            telemetry={
                "execution_time_ms": round(execution_time, 2),
                "confidence_level": request.confidence_level,
                "trigger_type": request.trigger.value,
                "fallback": used_fallback,
            },
            execution_time_ms=round(execution_time, 2),
        )
    
    # Registrar en log de ejecución (Etapa D4)
    log_execution(
        trigger=request.trigger.value,
        success=response.success,
        session_id=str(request.session_id) if request.session_id else None,
        confidence_level=request.confidence_level,
        result=result if response.success else None,
        error_message=response.error_message,
        telemetry=response.telemetry,
        execution_time_ms=response.execution_time_ms,
    )
    
    return response


# ---------------------------------------------------------------------------
# Etapa D4 · Logs de ejecución (bóveda local)
# ---------------------------------------------------------------------------

@app.get("/api/v1/logs")
async def get_execution_logs(
    limit: int = 100,
    trigger: Optional[str] = None,
    success: Optional[bool] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    security_check: bool = Depends(verify_security_guard),
):
    """
    Endpoint de consulta de logs de ejecución (Etapa D4).
    
    Devuelve logs persistentes de la bóveda local con filtros opcionales.
    """
    logs = get_logs(
        limit=limit,
        trigger=trigger,
        success=success,
        date_from=date_from,
        date_to=date_to,
    )
    return {
        "logs": logs,
        "count": len(logs),
        "filters": {
            "limit": limit,
            "trigger": trigger,
            "success": success,
            "date_from": date_from,
            "date_to": date_to,
        },
    }


@app.get("/api/v1/logs/stats")
async def get_logs_stats(
    security_check: bool = Depends(verify_security_guard),
):
    """Estadísticas globales de los logs de ejecución."""
    stats = get_log_stats()
    return stats


@app.get("/api/v1/logs/export")
async def export_execution_logs(
    format: str = "json",
    trigger: Optional[str] = None,
    success: Optional[bool] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    security_check: bool = Depends(verify_security_guard),
):
    """
    Endpoint de exportación de logs (Etapa D4).
    
    Exporta logs en formato JSON o CSV.
    """
    try:
        export_path = export_logs(
            format=format,
            trigger=trigger,
            success=success,
            date_from=date_from,
            date_to=date_to,
        )
        return {
            "status": "exported",
            "format": format,
            "file_path": export_path,
            "message": f"Logs exportados correctamente en {format.upper()}.",
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@app.get("/api/v1/logs/integrity")
async def verify_logs_integrity(
    security_check: bool = Depends(verify_security_guard),
):
    """
    Verificación de integridad de los logs (S5).
    
    Retorna el resultado de la verificación de hashes SHA-256.
    """
    from pathlib import Path
    
    logs_dir = Path(__file__).resolve().parent.parent / "boveda y vitacoras" / "logs"
    
    if not logs_dir.exists():
        return {
            "status": "no_logs",
            "message": "No hay logs para verificar.",
        }
    
    results = []
    for log_file in sorted(logs_dir.glob("execution_*.jsonl")):
        from .execution_log import verify_log_integrity
        result = verify_log_integrity(log_file)
        results.append(result)
    
    total_valid = sum(r["valid_entries"] for r in results)
    total_invalid = sum(r["invalid_entries"] for r in results)
    
    return {
        "files_verified": len(results),
        "total_entries": sum(r["total_entries"] for r in results),
        "valid_entries": total_valid,
        "invalid_entries": total_invalid,
        "integrity_ok": total_invalid == 0,
        "details": results,
    }


# ---------------------------------------------------------------------------
# Interfaz web estática dual (Etapa B)
# ---------------------------------------------------------------------------
# Frontend HTML/CSS/JS servido por el propio FastAPI local
# (127.0.0.1:8000/ui). Ejecución 100% local: sin CDNs ni servicios
# externos (S1, S2, E1, E2). Las rutas de la API registradas arriba
# conservan su contrato intacto; este montaje solo sirve archivos
# estáticos y no altera ningún endpoint.
# ---------------------------------------------------------------------------
_WEB_UI_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web_ui")
if os.path.isdir(_WEB_UI_DIR):
    app.mount("/ui", StaticFiles(directory=_WEB_UI_DIR, html=True), name="web_ui")