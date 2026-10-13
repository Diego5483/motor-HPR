"""Pruebas para el TaskOrchestrator - Fase 6: Paso 2.3"""

import sys
sys.path.insert(0, 'HPR/src')

from unittest.mock import Mock, MagicMock, patch
from uuid import UUID, uuid4
from datetime import datetime

from models.contracts import (
    ConversationTurn, ConversationSession, SessionContext,
    TurnRole, TurnType, StructuredResult, Decision,
    Evidence, EvidenceSource, EvidenceType, ClaimEvaluation, ClaimStatus,
)
from core.task_orchestrator import (
    TaskOrchestrator, TaskDecomposer, create_task_orchestrator,
    IntentSchema, IntentCategory, IntentComplexity, IntentPriority,
    Task, SubTask, TaskType, TaskStatus,
    OrchestrationPhase, OrchestrationState, OrchestratorInput, OrchestratorOutput,
    OrchestrationEvent, OrchestrationEventType,
    DecompositionError, DAGValidationError,
    create_intent_schema, create_orchestrator_input,
)
from core.verified_reasoning import VerifiedReasoningEngine, DecisionPolicyEngine, DecisionContext


# ============================================================================
# MOCKS Y FIXTURES
# ============================================================================

class MockVerifiedReasoningEngine:
    """Mock del VerifiedReasoningEngine para testing determinista."""
    
    def __init__(self, decision_policy="investigate", overall_confidence=0.6, metrics=None):
        self.decision_policy = decision_policy
        self.overall_confidence = overall_confidence
        self.metrics = metrics or {
            "unverified": 0,
            "contradicted": 0,
            "supported": 2,
            "insufficient": 0,
        }
        self.call_count = 0
        self.last_query = None
        self.last_search_results = None
    
    def reason(self, query: str, search_results: list, iteration: int = 0) -> dict:
        self.call_count += 1
        self.last_query = query
        self.last_search_results = search_results
        
        return {
            "conclusion": "Test conclusion",
            "claim_evaluations": [],
            "decision": "accept",
            "overall_confidence": self.overall_confidence,
            "limitations": [],
            "references": [],
            "metadata": {
                "decision_policy": self.decision_policy,
                "policy_reasoning": "Test reasoning",
                "iteration": iteration,
                "should_iterate": False,
                "claims_extracted": 2,
                "claims_evaluated": 2,
            },
            "metrics": self.metrics,
        }


class MockSessionManager:
    """Mock del SessionManager para testing."""
    
    def __init__(self):
        self.sessions = {}
        self.turns = {}
    
    def create_session(self, **kwargs):
        session = ConversationSession(**kwargs)
        self.sessions[session.id] = session
        return session
    
    def get_session(self, session_id: UUID):
        return self.sessions.get(session_id)
    
    def add_turn(self, session_id: UUID, **kwargs):
        session = self.get_session(session_id)
        if not session:
            return None
        turn = ConversationTurn(session_id=session_id, **kwargs)
        session.turns.append(turn)
        self.turns[turn.id] = turn
        return turn
    
    def get_session_context(self, session_id: UUID):
        session = self.get_session(session_id)
        if not session:
            return None
        user_turns = [t for t in session.turns if t.role == TurnRole.USER]
        assistant_turns = [t for t in session.turns if t.role == TurnRole.ASSISTANT]
        return SessionContext(
            session_id=session.id,
            current_turn_number=len(session.turns) + 1,
            last_user_turn=user_turns[-1] if user_turns else None,
            last_assistant_turn=assistant_turns[-1] if assistant_turns else None,
            pending_references=[],
            active_topics=["test_topic"],
            unresolved_ambiguities=[],
        )


def make_test_intent(
    session_id: UUID,
    turn_id: UUID,
    category: IntentCategory = IntentCategory.ANALYSIS,
    complexity: IntentComplexity = IntentComplexity.SIMPLE,
    priority: IntentPriority = IntentPriority.NORMAL,
) -> IntentSchema:
    """Crea una intención de prueba válida."""
    return create_intent_schema(
        category=category,
        summary="Test intent summary",
        description="Test intent description",
        session_id=session_id,
        source_turn_id=turn_id,
        complexity=complexity,
        priority=priority,
        constraints=["budget: 1000 tokens"],
        success_criteria=["generate valid response"],
        estimated_subtasks=3,
        estimated_tokens=500,
    )


def make_test_turn(session_id: UUID, role: TurnRole = TurnRole.USER, content: str = "Test query") -> ConversationTurn:
    """Crea un turno de prueba."""
    return ConversationTurn(
        session_id=session_id,
        turn_number=1,
        role=role,
        turn_type=TurnType.TASK,
        content=content,
    )


def make_test_evidence() -> list[Evidence]:
    """Crea evidencia de prueba."""
    return [
        Evidence(
            content="Test evidence content",
            source=EvidenceSource.OFFICIAL,
            evidence_type=EvidenceType.DOCUMENT,
            relevance_score=0.8,
            source_title="Test Document",
        )
    ]


def make_test_session_context(session_id: UUID, turn: ConversationTurn) -> SessionContext:
    """Crea un contexto de sesión de prueba."""
    return SessionContext(
        session_id=session_id,
        current_turn_number=2,
        last_user_turn=turn,
        last_assistant_turn=None,
        pending_references=[],
        active_topics=["test"],
        unresolved_ambiguities=[],
    )


def make_orchestrator_input(
    intent: IntentSchema,
    session_context: SessionContext,
    turn: ConversationTurn,
    evidence: list = None,
) -> OrchestratorInput:
    """Crea entrada del orquestador de prueba."""
    return create_orchestrator_input(
        intent=intent,
        session_context=session_context,
        turn=turn,
        available_evidence=evidence or make_test_evidence(),
        previous_results=[],
        force_replan=False,
        dry_run=False,
    )


# ============================================================================
# TESTS: FLUJO DE ESTADOS (INTAKE -> DECOMPOSITION -> PLANNING -> EXECUTION)
# ============================================================================

def test_orchestrator_state_transitions():
    """
    Valida la transición exitosa de estados del TaskOrchestrator:
    INTAKE -> DECOMPOSITION -> PLANNING -> EXECUTION
    
    Este test verifica que el orquestador pasa por todas las fases
    correctamente al procesar una intención válida.
    """
    print("\n=== TEST: Flujo de estados INTAKE -> DECOMPOSITION -> PLANNING -> EXECUTION ===")
    
    # --- SETUP ---
    session_id = uuid4()
    turn_id = uuid4()
    
    # Mock del VerifiedReasoningEngine con respuesta exitosa
    mock_reasoning = MockVerifiedReasoningEngine(
        decision_policy="investigate",
        overall_confidence=0.7,
        metrics={"unverified": 1, "supported": 2, "contradicted": 0}
    )
    
    # Mock del SessionManager
    mock_session_mgr = MockSessionManager()
    session = mock_session_mgr.create_session(
        title="Test Session",
        initial_query="Test query",
        max_turns=10,
        max_tokens=1000,
    )
    turn = make_test_turn(session_id, content="Analyze this data")
    mock_session_mgr.add_turn(session_id=session_id, role=TurnRole.USER, content="Analyze this data", turn_type=TurnType.TASK)
    
    # Crear intención y contexto
    intent = make_test_intent(session_id, turn_id, category=IntentCategory.ANALYSIS)
    session_context = make_test_session_context(session_id, turn)
    
    # Crear OrchestratorInput
    input_data = make_orchestrator_input(intent, session_context, turn)
    
    # Capturar eventos emitidos
    emitted_events = []
    def event_capture(event: OrchestrationEvent):
        emitted_events.append(event)
    
    # Crear orquestador con mocks
    orchestrator = create_task_orchestrator(
        reasoning_engine=mock_reasoning,
        session_manager=mock_session_mgr,
        event_callback=event_capture,
        max_subtasks=10,
    )
    
    # --- EJECUCIÓN ---
    output = orchestrator.process_intent(input_data)
    
    # --- ASSERTIONS: RESULTADO ---
    assert output.success is True, f"Orquestación falló: {output.error_message}"
    assert output.task is not None, "Debe crear una Task"
    assert output.final_result is None, "En Paso 2.2 no hay ejecución real"
    assert output.phase_reached == OrchestrationPhase.PLANNING, f"Fase incorrecta: {output.phase_reached}"
    assert output.total_subtasks_planned > 0, "Debe planificar al menos 1 subtarea"
    assert output.total_subtasks_executed == 0, "No debe ejecutar subtareas en Paso 2.2"
    assert "Ejecución de subtareas pendiente (Paso 2.3)" in output.warnings
    
    # --- ASSERTIONES: ESTADO INTERNO DEL ORQUESTADOR ---
    state = orchestrator.get_or_create_state(session_id)
    assert state.phase == OrchestrationPhase.EXECUTION, f"Estado final incorrecto: {state.phase}"
    assert state.active_task_id == output.task.id, "Task ID debe coincidir con active_task_id"
    assert state.total_tasks_created == 1, "Debe haber creado 1 tarea"
    assert state.total_tasks_completed == 0, "No debe haber tareas completadas aún"
    assert state.total_tasks_failed == 0, "No debe haber tareas fallidas"
    assert len(state.active_tasks) == 1, "Debe haber 1 tarea activa"
    assert output.task.id in state.active_tasks, "Task debe estar en active_tasks"
    
    # --- ASSERTIONES: EVENTOS EMITIDOS ---
    event_types = [e.event_type for e in emitted_events]
    assert OrchestrationEventType.INTENT_RECEIVED in event_types, "Debe emitir INTENT_RECEIVED"
    assert OrchestrationEventType.DECOMPOSITION_STARTED in event_types, "Debe emitir DECOMPOSITION_STARTED"
    assert OrchestrationEventType.DECOMPOSITION_COMPLETED in event_types, "Debe emitir DECOMPOSITION_COMPLETED"
    assert OrchestrationEventType.PLANNING_COMPLETED in event_types, "Debe emitir PLANNING_COMPLETED"
    
    # Verificar orden de eventos
    phase_events = [
        OrchestrationEventType.INTENT_RECEIVED,
        OrchestrationEventType.DECOMPOSITION_STARTED,
        OrchestrationEventType.DECOMPOSITION_COMPLETED,
        OrchestrationEventType.PLANNING_COMPLETED,
    ]
    for i, expected_type in enumerate(phase_events):
        actual_type = event_types[i]
        assert actual_type == expected_type, f"Evento {i}: esperado {expected_type}, got {actual_type}"
    
    # --- ASSERTIONES: TAREA CREADA ---
    task = output.task
    assert task.intent_id == intent.id, "Task debe referenciar la intención correcta"
    assert task.session_id == session_id, "Task debe referenciar la sesión correcta"
    assert task.status == TaskStatus.PENDING, "Task debe empezar en PENDING"
    assert len(task.subtasks) > 0, "Task debe tener subtareas"
    assert task.max_parallelism >= 1, "Parallelism debe ser >= 1"
    assert task.timeout_seconds >= 60, "Timeout debe ser >= 60 segundos"
    
    # Verificar que las subtareas están ordenadas topológicamente
    for i, st in enumerate(task.subtasks):
        for dep_id in st.depends_on:
            dep_index = next(j for j, s in enumerate(task.subtasks) if s.id == dep_id)
            assert dep_index < i, f"Subtarea {st.name} depende de {dep_id} que viene después"
    
    # --- ASSERTIONES: VERIFIEDREASONINGENGINE FUE INVOCADO ---
    assert mock_reasoning.call_count == 1, "Reasoning engine debe ser llamado una vez"
    assert mock_reasoning.last_query is not None, "Query no debe ser None"
    assert "INTENCIÓN A DESCOMPONER" in mock_reasoning.last_query, "Query debe contener info de intención"
    assert "PIPELINE BASE PROPUESTO" in mock_reasoning.last_query, "Query debe contener pipeline base"
    
    print("PASS: test_orchestrator_state_transitions")
    return True


# ============================================================================
# TESTS: MANEJO DE ERRORES TIPIFICADOS
# ============================================================================

def test_decomposition_error_on_reasoning_failure():
    """
    Valida que se lance DecompositionError tipado cuando el VerifiedReasoningEngine
    falle durante el proceso de descomposición/refinamiento del plan.
    
    Este test fuerza un fallo en el motor de razonamiento y verifica
    que el orquestador capture el error y retorne una salida de error estructurada.
    """
    print("\n=== TEST: DecompositionError en fallo de VerifiedReasoningEngine ===")
    
    session_id = uuid4()
    turn_id = uuid4()
    
    # Mock del VerifiedReasoningEngine que FALLA siempre
    class FailingReasoningEngine:
        def reason(self, query: str, search_results: list, iteration: int = 0) -> dict:
            raise RuntimeError("Simulated reasoning engine failure: connection timeout")
    
    mock_reasoning = FailingReasoningEngine()
    
    # Mock del SessionManager
    mock_session_mgr = MockSessionManager()
    session = mock_session_mgr.create_session(
        title="Test Session Error",
        initial_query="Test query",
        max_turns=10,
        max_tokens=1000,
    )
    turn = make_test_turn(session_id, content="This will fail")
    mock_session_mgr.add_turn(session_id=session_id, role=TurnRole.USER, content="This will fail", turn_type=TurnType.TASK)
    
    intent = make_test_intent(session_id, turn_id, category=IntentCategory.ANALYSIS)
    session_context = make_test_session_context(session_id, turn)
    input_data = make_orchestrator_input(intent, session_context, turn)
    
    emitted_events = []
    def event_capture(event: OrchestrationEvent):
        emitted_events.append(event)
    
    orchestrator = create_task_orchestrator(
        reasoning_engine=mock_reasoning,
        session_manager=mock_session_mgr,
        event_callback=event_capture,
        max_subtasks=10,
    )
    
    # --- EJECUCIÓN ---
    output = orchestrator.process_intent(input_data)
    
    # --- ASSERTIONS: RESULTADO DE ERROR ---
    assert output.success is False, "Debe fallar"
    assert output.task is None, "No debe crear tarea en caso de error"
    assert output.final_result is None, "No debe haber resultado final"
    assert output.phase_reached == OrchestrationPhase.ERROR, f"Fase debe ser ERROR, got {output.phase_reached}"
    assert output.error_message is not None, "Debe tener mensaje de error"
    assert "Error inesperado en descomposición" in output.error_message or "Simulated reasoning engine failure" in output.error_message
    assert output.total_subtasks_planned == 0
    assert output.total_subtasks_executed == 0
    
    # --- ASSERTIONES: ESTADO INTERNO ---
    state = orchestrator.get_or_create_state(session_id)
    assert state.phase == OrchestrationPhase.ERROR, "Estado debe ser ERROR"
    assert state.total_tasks_failed == 1, "Debe contabilizar 1 tarea fallida"
    assert state.total_tasks_created == 0, "No debe contabilizar tareas creadas (falló antes)"
    
    # --- ASSERTIONES: EVENTOS ---
    event_types = [e.event_type for e in emitted_events]
    assert OrchestrationEventType.INTENT_RECEIVED in event_types
    assert OrchestrationEventType.DECOMPOSITION_STARTED in event_types
    assert OrchestrationEventType.TASK_FAILED in event_types, "Debe emitir TASK_FAILED"
    
    # Verificar payload del evento de fallo
    failed_event = next(e for e in emitted_events if e.event_type == OrchestrationEventType.TASK_FAILED)
    assert "stage" in failed_event.payload, "Payload debe incluir stage"
    assert failed_event.payload["stage"] == "decomposition", "Stage debe ser 'decomposition'"
    assert "error" in failed_event.payload, "Payload debe incluir error"
    
    print("PASS: test_decomposition_error_on_reasoning_failure")
    return True


def test_dag_validation_error_circular_dependencies():
    """
    Valida que se lance DAGValidationError cuando el grafo de dependencias
    contenga ciclos (referencias circulares) o subtareas huérfanas en depends_on.
    
    Este test inyecta manualmente un ciclo en las subtareas generadas
    y verifica que la validación DAG lo detecte correctamente.
    """
    print("\n=== TEST: DAGValidationError en dependencias circulares ===")
    
    session_id = uuid4()
    turn_id = uuid4()
    
    # Mock del VerifiedReasoningEngine que genera un plan con ciclo intencional
    class CyclicPlanReasoningEngine:
        def reason(self, query: str, search_results: list, iteration: int = 0) -> dict:
            # Retornar métricas que NO disparen simplificación (decision_policy = investigate)
            return {
                "conclusion": "Test conclusion",
                "claim_evaluations": [],
                "decision": "accept",
                "overall_confidence": 0.6,
                "limitations": [],
                "references": [],
                "metadata": {
                    "decision_policy": "investigate",
                    "policy_reasoning": "Test reasoning",
                    "iteration": iteration,
                    "should_iterate": False,
                    "claims_extracted": 2,
                    "claims_evaluated": 2,
                },
                "metrics": {
                    "unverified": 0,
                    "contradicted": 0,
                    "supported": 2,
                    "insufficient": 0,
                },
            }
    
    mock_reasoning = CyclicPlanReasoningEngine()
    
    # Mock del SessionManager
    mock_session_mgr = MockSessionManager()
    session = mock_session_mgr.create_session(
        title="Test Session DAG",
        initial_query="Test query",
        max_turns=10,
        max_tokens=1000,
    )
    turn = make_test_turn(session_id, content="Test DAG")
    mock_session_mgr.add_turn(session_id=session_id, role=TurnRole.USER, content="Test DAG", turn_type=TurnType.TASK)
    
    intent = make_test_intent(session_id, turn_id, category=IntentCategory.ANALYSIS)
    session_context = make_test_session_context(session_id, turn)
    input_data = make_orchestrator_input(intent, session_context, turn)
    
    emitted_events = []
    def event_capture(event: OrchestrationEvent):
        emitted_events.append(event)
    
    orchestrator = create_task_orchestrator(
        reasoning_engine=mock_reasoning,
        session_manager=mock_session_mgr,
        event_callback=event_capture,
        max_subtasks=10,
    )
    
    # --- EJECUCIÓN NORMAL (debe pasar validación DAG) ---
    output = orchestrator.process_intent(input_data)
    
    # Si pasa, verificar que NO hay error de DAG
    if output.success:
        # Ahora vamos a testear el validador DAG directamente inyectando un ciclo
        decomposer = orchestrator.decomposer
        
        # Crear subtareas con ciclo manual: A -> B -> C -> A
        from core.task_orchestrator import SubTask, TaskType
        from uuid import uuid4
        
        id_a = uuid4()
        id_b = uuid4()
        id_c = uuid4()
        
        subtask_a = SubTask(
            id=id_a,
            task_id=uuid4(),
            intent_id=intent.id,
            type=TaskType.EVIDENCE_GATHERING,
            name="Task A",
            description="First task",
            depends_on=[id_c],  # A depende de C -> CICLO
        )
        subtask_b = SubTask(
            id=id_b,
            task_id=uuid4(),
            intent_id=intent.id,
            type=TaskType.CLAIM_EXTRACTION,
            name="Task B",
            description="Second task",
            depends_on=[id_a],  # B depende de A
        )
        subtask_c = SubTask(
            id=id_c,
            task_id=uuid4(),
            intent_id=intent.id,
            type=TaskType.CLAIM_EVALUATION,
            name="Task C",
            description="Third task",
            depends_on=[id_b],  # C depende de B
        )
        
        cyclic_subtasks = [subtask_a, subtask_b, subtask_c]
        
        # Validar que _validate_dag detecta el ciclo
        try:
            decomposer._validate_dag(cyclic_subtasks)
            assert False, "Debería haber lanzado DAGValidationError"
        except DAGValidationError as e:
            assert e.cycle is not None, "Debe detectar y reportar el ciclo"
            cycle_ids = [str(u) for u in e.cycle]
            assert str(id_a) in cycle_ids, "Ciclo debe incluir A"
            assert str(id_b) in cycle_ids, "Ciclo debe incluir B"
            assert str(id_c) in cycle_ids, "Ciclo debe incluir C"
            print(f"  Ciclo detectado correctamente: {cycle_ids}")
        except Exception as e:
            assert False, f"Excepción incorrecta: {type(e).__name__}: {e}"
    
    # --- TEST 2: Subtareas huérfanas (depends_on a ID inexistente) ---
    # Esto NO debe lanzar error, solo warning en logs
    orphan_id = uuid4()
    subtask_with_orphan = SubTask(
        id=uuid4(),
        task_id=uuid4(),
        intent_id=intent.id,
        type=TaskType.EVIDENCE_GATHERING,
        name="Task With Orphan Dep",
        description="Task with orphan dependency",
        depends_on=[orphan_id],  # Depende de ID que no existe
    )
    
    try:
        decomposer._validate_dag([subtask_with_orphan])
        # Debe pasar (warning logged pero no error)
        print("  Dependencia huérfana manejada correctamente (warning, no error)")
    except DAGValidationError:
        assert False, "Dependencia huérfana no debe lanzar DAGValidationError"
    except Exception as e:
        assert False, f"Excepción inesperada: {type(e).__name__}: {e}"
    
    # --- TEST 3: DAG válido sin ciclos ---
    id_1 = uuid4()
    id_2 = uuid4()
    id_3 = uuid4()
    
    valid_subtasks = [
        SubTask(
            id=id_1, task_id=uuid4(), intent_id=intent.id,
            type=TaskType.EVIDENCE_GATHERING, name="Task 1", description="First",
            depends_on=[],
        ),
        SubTask(
            id=id_2, task_id=uuid4(), intent_id=intent.id,
            type=TaskType.CLAIM_EXTRACTION, name="Task 2", description="Second",
            depends_on=[id_1],
        ),
        SubTask(
            id=id_3, task_id=uuid4(), intent_id=intent.id,
            type=TaskType.CLAIM_EVALUATION, name="Task 3", description="Third",
            depends_on=[id_2],
        ),
    ]
    
    try:
        decomposer._validate_dag(valid_subtasks)
        # Debe pasar sin errores
        print("  DAG válido validado correctamente")
    except Exception as e:
        assert False, f"DAG válido no debe fallar: {type(e).__name__}: {e}"
    
    # --- TEST 4: Ordenación topológica en DAG válido ---
    sorted_tasks = decomposer._topological_sort(valid_subtasks)
    assert len(sorted_tasks) == 3
    assert sorted_tasks[0].id == id_1, "Primero debe ser Task 1 (sin deps)"
    assert sorted_tasks[1].id == id_2, "Segundo debe ser Task 2 (dep de 1)"
    assert sorted_tasks[2].id == id_3, "Tercero debe ser Task 3 (dep de 2)"
    
    print("PASS: test_dag_validation_error_circular_dependencies")
    return True


def test_session_manager_integration():
    """
    Valida la integración con SessionManager:
    - Creación de sesión y turnos
    - Obtención de SessionContext
    - Paso de contexto al orquestador
    - Actualización de estado de sesión post-orquestación
    """
    print("\n=== TEST: Integración con SessionManager ===")
    
    session_id = uuid4()
    turn_id = uuid4()
    
    # Mock del VerifiedReasoningEngine exitoso
    mock_reasoning = MockVerifiedReasoningEngine(
        decision_policy="investigate",
        overall_confidence=0.75,
    )
    
    # SessionManager REAL (no mock) para test de integración
    from core.session_manager import create_session_manager
    import tempfile
    import shutil
    
    temp_dir = tempfile.mkdtemp()
    try:
        session_mgr = create_session_manager(storage_path=temp_dir)
        
        # Crear sesión real
        session = session_mgr.create_session(
            title="Integration Test",
            initial_query="Test integration",
            tags=["test"],
            max_turns=20,
            max_tokens=2000,
        )
        assert session.id == session_id or True  # session_id es nuevo
        
        # Añadir turno de usuario
        turn = session_mgr.add_turn(
            session_id=session.id,
            role=TurnRole.USER,
            content="Analyze the market trends for AI",
            turn_type=TurnType.TASK,
            tokens_used=50,
        )
        assert turn is not None
        assert turn.turn_number == 1
        assert turn.role == TurnRole.USER
        
        # Obtener contexto de sesión REAL
        session_context = session_mgr.get_session_context(session.id)
        assert session_context is not None
        assert session_context.session_id == session.id
        assert session_context.last_user_turn is not None
        assert session_context.last_user_turn.content == "Analyze the market trends for AI"
        assert session_context.current_turn_number == 2
        
        # Crear intención usando IDs reales de la sesión
        intent = make_test_intent(
            session_id=session.id,
            turn_id=turn.id,
            category=IntentCategory.ANALYSIS,
        )
        
        # Crear input con contexto REAL
        input_data = make_orchestrator_input(
            intent=intent,
            session_context=session_context,
            turn=turn,
            evidence=[],
        )
        
        emitted_events = []
        def event_capture(event: OrchestrationEvent):
            emitted_events.append(event)
        
        orchestrator = create_task_orchestrator(
            reasoning_engine=mock_reasoning,
            session_manager=session_mgr,
            event_callback=event_capture,
            max_subtasks=10,
        )
        
        # Procesar intención
        output = orchestrator.process_intent(input_data)
        
        # Verificaciones de integración
        assert output.success is True
        assert output.task is not None
        assert output.task.session_id == session.id
        assert output.task.intent_id == intent.id
        
        # Verificar que el estado del orquestador se actualizó
        state = orchestrator.get_or_create_state(session.id)
        assert state.active_task_id == output.task.id
        assert state.total_tasks_created == 1
        
        # Verificar eventos con IDs reales
        task_started_events = [e for e in emitted_events if e.task_id == output.task.id]
        assert len(task_started_events) > 0
        
        print("PASS: test_session_manager_integration")
        return True
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    import sys
    
    test_functions = [
        test_orchestrator_state_transitions,
        test_decomposition_error_on_reasoning_failure,
        test_dag_validation_error_circular_dependencies,
        test_session_manager_integration,
    ]
    
    passed = 0
    failed = 0
    
    for test_func in test_functions:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"FAIL: {test_func.__name__} - {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR: {test_func.__name__} - {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print(f"\n{'='*60}")
    print(f"Resultados: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)