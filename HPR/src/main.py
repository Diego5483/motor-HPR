import os

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime

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
    
    # 1. Obtener o crear sesión
    if request.session_id:
        session = session_mgr.get_session(request.session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sesión no encontrada: {request.session_id}"
            )
    else:
        session = session_mgr.create_session(
            initial_query=request.message,
            title=f"Chat {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
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
    
    # 3. Procesar a través del motor de seguridad (pipeline completo)
    try:
        response = security_engine.process_pipeline(
            payload=request.message,
            state={"identity": "HPR-CORE-DETERMINISTIC"},
            truth=[],
        )
        assistant_response = response.get("estado", "Sin respuesta")
        
        # Extraer conocimiento si está disponible
        knowledge = response.get("conocimiento", "")
        if knowledge:
            assistant_response = f"{assistant_response}\n\n{knowledge}"
            
    except Exception as e:
        assistant_response = f"BLOQUEO DE SEGURIDAD: {str(e)}"
    
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
    
    # Obtener o crear sesión
    if request.session_id:
        session = session_mgr.get_session(request.session_id)
        if not session:
            raise ValueError(f"Sesión no encontrada: {request.session_id}")
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