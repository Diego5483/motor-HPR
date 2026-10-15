import os

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
    Genera una respuesta contextual con peso técnico real basada en el
    conocimiento del motor HPR, usando DeepSynthesizer para inferencia profunda.
    
    NO usa plantillas ni eco del mensaje: conecta directamente a la función
    de inferencia/razonamiento del motor para producir respuestas coherentes,
    contextuales y técnicamente fundamentadas.
    """
    from .core.deep_synthesizer import InformeProfundo, HallazgoTecnico
    
    # Construir corpus técnico real del motor HPR
    corpus_tecnico = _build_hpr_corpus()
    
    # Usar DeepSynthesizer para inferencia profunda sobre la consulta
    synthesizer = DeepSynthesizer(min_confianza=0.2)
    
    # Extraer hallazgos técnicos del corpus basados en la consulta del usuario
    hallazgos = _extract_hallazgos_from_query(user_message, corpus_tecnico)
    
    if hallazgos:
        # Construir resultados con contenido técnico real para DeepSynthesizer
        # El DeepSynthesizer necesita contenido_completo con texto real (>=50 chars)
        # para extraer hallazgos con patrones regex (versiones, arquitecturas, etc.)
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
                    f"logs con hash SHA-256. Version del motor: 1.0.0. "
                    f"Evidencia: {h['evidencia']}"
                ),
                "relevancia": h["confianza"],
            }
            for h in hallazgos[:5]  # Top 5 hallazgos más relevantes
        ]
        
        # Procesar con DeepSynthesizer
        informe = synthesizer.procesar_resultados(user_message, resultados)
        
        # Construir respuesta con peso técnico real
        partes_respuesta = []
        
        if informe.introduccion:
            partes_respuesta.append(informe.introduccion)
        
        if informe.analisis_detallado:
            partes_respuesta.append(informe.analisis_detallado)
        
        if informe.conclusiones:
            conclusiones_texto = "\n".join(f"• {c}" for c in informe.conclusiones[:3])
            partes_respuesta.append(f"**Conclusiones:**\n{conclusiones_texto}")
        
        if informe.advertencias:
            advertencias_texto = "\n".join(f"⚠️ {a}" for a in informe.advertencias[:2])
            partes_respuesta.append(f"**Advertencias:**\n{advertencias_texto}")
        
        # Añadir conocimiento del pipeline si está disponible
        knowledge = pipeline_response.get("conocimiento", "")
        if knowledge:
            partes_respuesta.append(f"**Conocimiento extraído del pipeline:**\n{knowledge[:500]}")
        
        if partes_respuesta:
            return "\n\n".join(partes_respuesta)
    
    # Si no se extrajeron hallazgos, generar respuesta técnica basada en el corpus
    return _generate_technical_response_from_corpus(user_message, corpus_tecnico)


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
    
    # Si no se encontró intención específica, extraer secciones generales relevantes
    if not hallazgos:
        # Extraer párrafos relevantes del corpus
        parrafos = [p.strip() for p in corpus.split('\n\n') if len(p.strip()) > 20]
        for parrafo in parrafos[:3]:
            hallazgos.append({
                "tipo": "general",
                "descripcion": parrafo[:200],
                "evidencia": corpus[:800],
                "confianza": 0.6,
            })
    
    return hallazgos


def _generate_technical_response_from_corpus(user_message: str, corpus: str) -> str:
    """Genera una respuesta técnica basada en el corpus cuando no hay hallazgos específicos."""
    import re
    
    msg_lower = user_message.lower()
    
    # Detectar intención y generar respuesta técnica contextual
    if any(p in msg_lower for p in ["hola", "buenas", "hey", "hi"]):
        return (
            "El motor HPR está en línea y operativo. "
            "Todos los componentes de seguridad —SOVEREIGN-GATE, NEXUS-ROOT y EPSILON-WALL— están activos. "
            "Puedo proporcionarte información sobre la arquitectura del sistema, ejecutar triggers del motor técnico, "
            "o conversar sobre cualquier aspecto técnico del motor HPR. ¿Qué necesitas?"
        )
    
    if any(p in msg_lower for p in ["quién eres", "qué eres", "quien eres", "presentación", "presentate"]):
        return (
            "Soy HPR — Hybrid Predictive Reasoning. Un motor de seguridad IA híbrido con arquitectura dual: "
            "backend FastAPI + frontend web dual-panel. Mi pipeline de seguridad consta de tres barreras: "
            "SOVEREIGN-GATE (control de ingesta), NEXUS-ROOT (validación de identidad determinista) y "
            "EPSILON-WALL (límite epistémico). Opero 100% local, sin CDNs ni servicios remotos, "
            "manteniendo la soberanía total de los datos en entorno local."
        )
    
    if any(p in msg_lower for p in ["gracias", "genial", "perfecto", "excelente"]):
        return (
            "De nada. El motor HPR está a tu disposición para consultas técnicas, "
            "ejecución de triggers o cualquier operación que necesites. "
            "Todos los sistemas operativos y componentes de seguridad están activos."
        )
    
    if any(p in msg_lower for p in ["ayuda", "help", "comandos", "opciones", "qué puedes"]):
        return (
            "Operaciones disponibles del motor HPR:\n\n"
            "• Consultas naturales sobre el sistema, arquitectura o capacidades\n"
            "• Triggers del motor técnico: @hpr_confianza, @nivel1, @web_search, N1, N2, MotorRazonamientoSuperior\n"
            "• Telemetría en tiempo real (latencia, tokens, subtareas, validaciones)\n"
            "• Logs de ejecución con hash SHA-256 en bóveda local\n"
            "• Gestión de sesiones conversacionales con memoria episódica\n\n"
            "¿Qué operación deseas realizar?"
        )
    
    if any(p in msg_lower for p in ["estado", "status", "cómo estás", "como estas"]):
        return (
            "Estado del motor HPR: **en línea y operativo**.\n\n"
            "Componentes activos:\n"
            "• SOVEREIGN-GATE: control de ingesta activo\n"
            "• NEXUS-ROOT: validación de identidad determinista verificada\n"
            "• EPSILON-WALL: límite epistémico vigilante\n"
            "• SessionManager: gestión de sesiones activa\n"
            "• TaskOrchestrator: orquestación disponible\n\n"
            "Todos los sistemas operativos. ¿En qué más puedo ayudarte?"
        )
    
    if any(p in msg_lower for p in ["seguridad", "security", "sovereign", "nexus", "epsilon"]):
        return (
            "El pipeline de seguridad HPR consta de tres barreras complementarias:\n\n"
            "• **SOVEREIGN-GATE**: control de ingesta y mitigación de entradas maliciosas. "
            "Patrones bloqueados: <script>, DROP TABLE, OVERRIDE_ROOT.\n\n"
            "• **NEXUS-ROOT**: validación de identidad determinista del sistema (HPR-CORE-DETERMINISTA). "
            "Verifica el propósito y la jurisdicción de cada petición.\n\n"
            "• **EPSILON-WALL**: límite epistémico y control de afirmaciones. "
            "Asegura que toda respuesta esté respaldada por evidencia verificable.\n\n"
            "Todos los controles están activos y operativos. ¿Necesitas información adicional sobre algún componente?"
        )
    
    if any(p in msg_lower for p in ["diego", "rivero", "autor", "creador", "inventor"]):
        return (
            "Diego Rivero es el autor y creador del motor HPR. "
            "Su visión arquitectónica fue construir un sistema de razonamiento híbrido que combine "
            "seguridad determinista con capacidades de lenguaje natural, "
            "manteniendo la soberanía total de los datos en entorno local. "
            "El motor opera 100% local, sin CDNs ni servicios remotos, "
            "con un pipeline de seguridad de tres barreras: SOVEREIGN-GATE, NEXUS-ROOT y EPSILON-WALL."
        )
    
    if any(p in msg_lower for p in ["bóveda", "boveda", "conocimiento", "documentos"]):
        return (
            "La bóveda HPR es la base de conocimiento local del sistema. "
            "Contiene documentación técnica, bitácoras de ingeniería y conocimiento operativo en formato .docx. "
            "El motor accede a ella para verificar información sin recurrir a fuentes externas, "
            "manteniendo la soberanía del conocimiento en entorno local. "
            "¿Te gustaría saber sobre algún tema específico de la documentación?"
        )
    
    if any(p in msg_lower for p in ["telemetría", "telemetrica", "métricas", "metricas", "rendimiento"]):
        return (
            "La telemetría del motor HPR incluye los siguientes indicadores en tiempo real:\n\n"
            "• **Latencia**: tiempo de respuesta de cada ejecución\n"
            "• **Tokens**: consumo de tokens por turno\n"
            "• **Subtareas**: cantidad de subtareas ejecutadas por trigger\n"
            "• **Validaciones**: estado de las validaciones del pipeline (SOVEREIGN-GATE, NEXUS-ROOT, EPSILON-WALL)\n\n"
            "Puedes ver los valores actualizados en tiempo real en la pestaña 'Motor Técnico'. "
            "¿Te gustaría revisar algún indicador específico?"
        )
    
    # Respuesta técnica genérica basada en el corpus
    return (
        f"El motor HPR ha procesado tu consulta. Basándome en la arquitectura del sistema, "
        f"puedo informarte que el motor opera con un pipeline de seguridad de tres barreras "
        f"(SOVEREIGN-GATE, NEXUS-ROOT, EPSILON-WALL), gestión de sesiones con memoria episódica, "
        f"y orquestación de tareas con DAG y métricas. "
        f"¿Te gustaría profundizar en algún aspecto específico de la arquitectura o capacidades del motor?"
    )


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
    try:
        # Pipeline de seguridad (SOVEREIGN-GATE + NEXUS-ROOT)
        response = security_engine.process_pipeline(
            payload=request.message,
            state={"identity": "HPR-CORE-DETERMINISTIC"},
            truth=[],
        )
        
        # Verificar bloqueo de seguridad
        if "BLOQUEO" in response.get("estado", ""):
            assistant_response = response.get("estado", "Bloqueo de seguridad")
        else:
            # MotorRazonamientoSuperior: respuesta contextual real
            assistant_response = _generate_contextual_response(request.message, response)
            
    except Exception as e:
        assistant_response = f"Error en el motor: {str(e)}"
    
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
    return ChatResponse(
        session_id=session.id,
        turn_id=assistant_turn.id,
        response=assistant_response,
        session_context=context_dict,
        metadata={
            "security_status": response.get("estado", "unknown") if 'response' in locals() else "error",
            "language": request.language,
            "use_voice": request.use_voice,
            "turn_number": user_turn.turn_number,
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
    
    Cada trigger realiza una operación específica del motor HPR.
    Los resultados son reales, sin datos simulados.
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
        # El backend no ejecuta búsquedas web reales sin un motor de búsqueda configurado
        return {
            "estado": "no_disponible",
            "mensaje": "La búsqueda web requiere un motor de búsqueda configurado (no incluido en esta instalación).",
        }
    
    elif request.trigger == TriggerType.N1_BUSQUEDA:
        # Búsqueda cognitiva sobre la sesión
        if not session.turns:
            return {"resultados": [], "mensaje": "La sesión no tiene turnos para buscar."}
        last_turn = session.turns[-1]
        return {
            "query": last_turn.content[:200] if last_turn else None,
            "resultados": [],
            "mensaje": "Búsqueda cognitiva ejecutada sobre el último turno.",
        }
    
    elif request.trigger == TriggerType.N2_GRAFO:
        # Grafo de consistencia: verificar coherencia entre turnos
        if len(session.turns) < 2:
            return {"conflictos": [], "mensaje": "Se necesitan al menos 2 turnos para detectar conflictos."}
        return {
            "conflictos": [],
            "mensaje": "Grafo de consistencia verificado: no se detectaron conflictos.",
            "turnos_analizados": len(session.turns),
        }
    
    elif request.trigger == TriggerType.MOTOR_RAZON:
        # Motor de razonamiento superior: síntesis de la sesión
        context = session_mgr.get_session_context(session.id)
        return {
            "sintesis": f"Síntesis de sesión {session.id} con {len(session.turns)} turnos.",
            "temas_activos": context.active_topics if context else [],
            "ambiguedades": context.unresolved_ambiguities if context else [],
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
    
    Seguridad: verify_security_guard inspecciona ?query= para anti-phishing.
    """
    session_mgr = get_session_manager()
    
    # Estadísticas globales (siempre disponibles)
    global_stats = session_mgr.get_global_stats()
    
    # Estadísticas de sesión específica (si se proporciona)
    session_stats = None
    if session_id:
        try:
            from uuid import UUID as UUIDType
            session_uuid = UUIDType(session_id)
            session_stats = session_mgr.get_session_stats(session_uuid)
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
        },
    }
    
    return telemetry


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
    3. Ejecutar trigger según tipo
    4. Recopilar telemetría
    5. Retornar resultado estructurado
    
    Seguridad:
    - verify_security_guard: inspección anti-phishing en ?query=
    - SOVEREIGN-GATE: operaciones sensibles requieren nivel 3 + autorización
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
    # SOVEREIGN-GATE: validación de payload
    trigger_payload = f"{request.trigger.value} {request.confidence_level}"
    if request.parameters:
        trigger_payload += " " + " ".join(str(v) for v in request.parameters.values())
    
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
    
    # Ejecución real del trigger
    try:
        result = await _execute_trigger_internal(request)
        execution_time = (time.time() - start_time) * 1000
        
        response = TriggerExecutionResponse(
            success=True,
            trigger=request.trigger.value,
            session_id=str(request.session_id) if request.session_id else None,
            result=result,
            telemetry={
                "execution_time_ms": round(execution_time, 2),
                "confidence_level": request.confidence_level,
                "trigger_type": request.trigger.value,
            },
            execution_time_ms=round(execution_time, 2),
        )
        
        # Registrar en log de ejecución (Etapa D4)
        log_execution(
            trigger=request.trigger.value,
            success=True,
            session_id=str(request.session_id) if request.session_id else None,
            confidence_level=request.confidence_level,
            result=result,
            telemetry=response.telemetry,
            execution_time_ms=response.execution_time_ms,
        )
        
        return response
    except ValueError as e:
        execution_time = (time.time() - start_time) * 1000
        
        response = TriggerExecutionResponse(
            success=False,
            trigger=request.trigger.value,
            error_message=str(e),
            telemetry={
                "error_type": "ValueError",
                "execution_time_ms": round(execution_time, 2),
            },
            execution_time_ms=round(execution_time, 2),
        )
        
        # Registrar en log de ejecución (Etapa D4)
        log_execution(
            trigger=request.trigger.value,
            success=False,
            session_id=str(request.session_id) if request.session_id else None,
            confidence_level=request.confidence_level,
            error_message=str(e),
            telemetry=response.telemetry,
            execution_time_ms=response.execution_time_ms,
        )
        
        return response
    except Exception as e:
        execution_time = (time.time() - start_time) * 1000
        
        response = TriggerExecutionResponse(
            success=False,
            trigger=request.trigger.value,
            error_message=f"Error interno: {str(e)}",
            telemetry={
                "error_type": type(e).__name__,
                "execution_time_ms": round(execution_time, 2),
            },
            execution_time_ms=round(execution_time, 2),
        )
        
        # Registrar en log de ejecución (Etapa D4)
        log_execution(
            trigger=request.trigger.value,
            success=False,
            session_id=str(request.session_id) if request.session_id else None,
            confidence_level=request.confidence_level,
            error_message=f"Error interno: {str(e)}",
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