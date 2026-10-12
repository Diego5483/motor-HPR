"""Pruebas para el SessionManager - Fase 6: Paso 1"""

import sys
sys.path.insert(0, 'HPR/src')

from models.contracts import (
    ConversationTurn, TurnReference, ConversationSession, SessionContext,
    TurnRole, TurnType, TurnStatus, ReferenceType, SessionStatus,
    TurnRole, TurnType, TurnStatus, ReferenceType, SessionStatus,
    ConversationTurn, TurnReference, ConversationSession, SessionContext,
)
from core.session_manager import SessionManager, create_session_manager
from uuid import uuid4
from datetime import datetime

print("=== TESTS SESSION MANAGER - FASE 6: PASO 1 ===\n")

# ============================================================================
# FIXTURES
# ============================================================================

def make_session(title="Test Session"):
    """Crea una sesión de prueba."""
    return ConversationSession(
        title=title,
        initial_query="Test query",
        max_turns=10,
        max_tokens=1000,
    )

# ============================================================================
# TESTS: Gestión de sesiones
# ============================================================================

def test_create_session():
    """Creación básica de sesión."""
    manager = create_session_manager()
    session = manager.create_session(
        initial_query="Test query",
        title="Test Session",
        tags=["test", "unit"],
    )
    
    assert session.id is not None
    assert session.title == "Test Session"
    assert session.initial_query == "Test query"
    assert session.tags == ["test", "unit"]
    assert session.status == SessionStatus.ACTIVE
    assert session.max_turns == 100
    assert session.max_tokens == 8000
    print("PASS: test_create_session")


def test_get_session():
    """Obtener sesión por ID."""
    manager = create_session_manager()
    session = manager.create_session(title="Test")
    session_id = session.id
    
    retrieved = manager.get_session(session_id)
    assert retrieved is not None
    assert retrieved.id == session_id
    assert retrieved.title == "Test"
    print("PASS: test_get_session")


def test_update_session():
    """Actualizar sesión."""
    manager = create_session_manager()
    session = manager.create_session(title="Original")
    
    session.title = "Updated"
    session.description = "Updated description"
    manager.update_session(session)
    
    retrieved = manager.get_session(session.id)
    assert retrieved.title == "Updated"
    assert retrieved.description == "Updated description"
    print("PASS: test_update_session")


def test_close_session():
    """Cerrar sesión."""
    manager = create_session_manager()
    session = manager.create_session(title="To Close")
    
    result = manager.close_session(session.id, reason="completed")
    assert result is True
    
    retrieved = manager.get_session(session.id)
    assert retrieved.status == SessionStatus.COMPLETED
    assert retrieved.completed_at is not None
    print("PASS: test_close_session")


def test_list_sessions():
    """Listar sesiones."""
    manager = create_session_manager()
    s1 = manager.create_session(title="Session 1")
    s2 = manager.create_session(title="Session 2")
    manager.close_session(s1.id)
    
    all_sessions = manager.list_sessions()
    assert len(all_sessions) >= 2
    
    active = manager.list_sessions(status=SessionStatus.ACTIVE)
    assert len(active) >= 1
    assert all(s.status == SessionStatus.ACTIVE for s in active)
    
    completed = manager.list_sessions(status=SessionStatus.COMPLETED)
    assert len(completed) >= 1
    assert all(s.status == SessionStatus.COMPLETED for s in completed)
    print("PASS: test_list_sessions")


# ============================================================================
# TESTS: Gestión de turnos
# ============================================================================

def test_add_turn():
    """Añadir turno a sesión."""
    manager = create_session_manager()
    session = manager.create_session(title="Test Turns")
    
    turn = manager.add_turn(
        session_id=session.id,
        role=TurnRole.USER,
        content="Hola, ¿cómo estás?",
        turn_type=TurnType.QUERY,
        tokens_used=10,
        latency_ms=150,
    )
    
    assert turn is not None
    assert turn.session_id == session.id
    assert turn.turn_number == 1
    assert turn.role == TurnRole.USER
    assert turn.content == "Hola, ¿cómo estás?"
    assert turn.turn_type == TurnType.QUERY
    assert turn.tokens_used == 10
    assert turn.latency_ms == 150
    assert turn.status == TurnStatus.PENDING
    
    # Verificar que el turno está en la sesión
    retrieved = manager.get_session(session.id)
    assert len(retrieved.turns) == 1
    assert retrieved.turns[0].id == turn.id
    print("PASS: test_add_turn")


def test_add_multiple_turns():
    """Añadir múltiples turnos alternados."""
    manager = create_session_manager()
    session = manager.create_session(title="Multi Turn")
    
    # User turn
    t1 = manager.add_turn(session.id, TurnRole.USER, "Hola", TurnType.QUERY)
    # Assistant turn
    t2 = manager.add_turn(session.id, TurnRole.ASSISTANT, "Hola! ¿En qué te ayudo?", TurnType.QUERY)
    # User turn
    t3 = manager.add_turn(session.id, TurnRole.USER, "Quiero saber sobre Python", TurnType.QUERY)
    
    retrieved = manager.get_session(session.id)
    assert len(retrieved.turns) == 3
    assert retrieved.turns[0].turn_number == 1
    assert retrieved.turns[1].turn_number == 2
    assert retrieved.turns[2].turn_number == 3
    assert retrieved.turns[0].role == TurnRole.USER
    assert retrieved.turns[1].role == TurnRole.ASSISTANT
    assert retrieved.turns[2].role == TurnRole.USER
    print("PASS: test_add_multiple_turns")


def test_turn_limits():
    """Límites de turnos y tokens."""
    manager = create_session_manager(max_turns_per_session=3, max_tokens_per_session=100)
    session = manager.create_session(max_turns=3, max_tokens=50)
    
    # Añadir 3 turnos (límite)
    for i in range(3):
        turn = manager.add_turn(session.id, TurnRole.USER, f"Turno {i}", TurnType.QUERY, tokens_used=10)
        assert turn is not None
    
    # El 4to debe fallar
    turn4 = manager.add_turn(session.id, TurnRole.USER, "Turno 4", TurnType.QUERY)
    assert turn4 is None  # Debe fallar por límite de turnos
    print("PASS: test_turn_limits")


def test_token_limit():
    """Límite de tokens."""
    manager = create_session_manager(max_turns_per_session=10, max_tokens_per_session=50)
    session = manager.create_session(max_turns=10, max_tokens=50)
    
    manager.add_turn(session.id, TurnRole.USER, "Turno 1", TurnType.QUERY, tokens_used=20)
    manager.add_turn(session.id, TurnRole.USER, "Turno 2", TurnType.QUERY, tokens_used=20)
    
    # El 3er turno con 20 tokens excedería el límite de 50
    turn3 = manager.add_turn(session.id, TurnRole.USER, "Turno 3", TurnType.QUERY, tokens_used=20)
    assert turn3 is None  # Debe fallar por límite de tokens
    print("PASS: test_token_limit")


# ============================================================================
# TESTS: Referencias y desambiguación
# ============================================================================

def test_add_reference():
    """Añadir referencia entre turnos."""
    manager = create_session_manager()
    session = manager.create_session()
    
    t1 = manager.add_turn(session.id, TurnRole.USER, "¿Qué es Python?", TurnType.QUERY)
    t2 = manager.add_turn(session.id, TurnRole.ASSISTANT, "Python es un lenguaje de programación...", TurnType.QUERY)
    t3 = manager.add_turn(session.id, TurnRole.USER, "¿Y eso?", TurnType.QUERY)  # Referencia a t2
    
    # Añadir referencia explícita de t3 a t2
    ref = manager.add_reference(
        session_id=session.id,
        source_turn_id=t3.id,
        target_turn_id=t2.id,
        reference_type=ReferenceType.EXPLICIT,
        reference_text="eso",
        confidence=0.9,
    )
    
    assert ref is not None
    assert ref.source_turn_id == t3.id
    assert ref.target_turn_id == t2.id
    assert ref.reference_type == ReferenceType.EXPLICIT
    assert ref.reference_text == "eso"
    assert ref.confidence == 0.9
    
    retrieved = manager.get_session(session.id)
    assert len(retrieved.references) == 1
    print("PASS: test_add_reference")


def test_resolve_references():
    """Resolver referencias."""
    manager = create_session_manager()
    session = manager.create_session()
    
    t1 = manager.add_turn(session.id, TurnRole.ASSISTANT, "Python es un lenguaje interpretado.", TurnType.QUERY)
    t2 = manager.add_turn(session.id, TurnRole.USER, "¿Qué es Python?", TurnType.QUERY)
    t3 = manager.add_turn(session.id, TurnRole.USER, "Explícamelo mejor.", TurnType.QUERY)
    
    # Referencia de t3 a t2 (implícita)
    ref = manager.add_reference(
        session_id=session.id,
        source_turn_id=t3.id,
        target_turn_id=t2.id,
        reference_type=ReferenceType.IMPLICIT,
        reference_text="mejor",
        confidence=0.6,
    )
    
    # Resolver referencias de t3
    resolved = manager.resolve_references(session.id, t3.id)
    
    assert len(resolved) >= 1
    assert resolved[0].source_turn_id == t3.id
    assert resolved[0].target_turn_id == t2.id
    assert resolved[0].confidence >= 0.7  # Boost al resolver
    print("PASS: test_resolve_references")


def test_pending_references():
    """Referencias pendientes (confianza baja)."""
    manager = create_session_manager()
    session = manager.create_session()
    
    t1 = manager.add_turn(session.id, TurnRole.ASSISTANT, "Python es un lenguaje interpretado.", TurnType.QUERY)
    t2 = manager.add_turn(session.id, TurnRole.USER, "¿Qué es Python?", TurnType.QUERY)
    t3 = manager.add_turn(session.id, TurnRole.USER, "Explícamelo mejor.", TurnType.QUERY)
    
    # Referencia de t3 a t2 (implícita)
    ref = manager.add_reference(
        session_id=session.id,
        source_turn_id=t3.id,
        target_turn_id=t2.id,
        reference_type=ReferenceType.IMPLICIT,
        reference_text="mejor",
        confidence=0.6,
    )
    
    # Resolver referencias de t3
    resolved = manager.resolve_references(session.id, t3.id)
    
    assert len(resolved) >= 1
    assert resolved[0].source_turn_id == t3.id
    assert resolved[0].target_turn_id == t2.id
    assert resolved[0].confidence >= 0.7  # Boost al resolver
    print("PASS: test_resolve_references")


def test_pending_references():
    """Referencias pendientes (confianza baja)."""
    manager = create_session_manager()
    session = manager.create_session()
    
    t1 = manager.add_turn(session.id, TurnRole.ASSISTANT, "Python es un lenguaje interpretado.", TurnType.QUERY)
    t2 = manager.add_turn(session.id, TurnRole.USER, "¿Qué es Python?", TurnType.QUERY)
    t3 = manager.add_turn(session.id, TurnRole.USER, "Explícamelo mejor.", TurnType.QUERY)
    
    # Referencia de t3 a t2 (implícita)
    ref = manager.add_reference(
        session_id=session.id,
        source_turn_id=t3.id,
        target_turn_id=t2.id,
        reference_type=ReferenceType.IMPLICIT,
        reference_text="mejor",
        confidence=0.6,
    )
    
    # Resolver referencias de t3
    resolved = manager.resolve_references(session.id, t3.id)
    
    assert len(resolved) >= 1
    assert resolved[0].source_turn_id == t3.id
    assert resolved[0].target_turn_id == t2.id
    assert resolved[0].confidence >= 0.7  # Boost al resolver
    print("PASS: test_resolve_references")


# ============================================================================
# TESTS: Contexto de sesión
# ============================================================================

def test_get_session_context():
    """Obtener contexto de sesión."""
    manager = create_session_manager()
    session = manager.create_session(initial_query="¿Qué es Python?")
    
    t1 = manager.add_turn(session.id, TurnRole.USER, "¿Qué es Python?", TurnType.QUERY)
    t2 = manager.add_turn(session.id, TurnRole.ASSISTANT, "Python es un lenguaje...", TurnType.QUERY)
    t3 = manager.add_turn(session.id, TurnRole.USER, "¿Y para qué sirve?", TurnType.QUERY)
    t4 = manager.add_turn(session.id, TurnRole.ASSISTANT, "Sirve para...", TurnType.QUERY)
    
    context = manager.get_session_context(session.id)
    
    assert context is not None
    assert context.session_id == session.id
    assert context.current_turn_number == 5  # 4 turnos + 1
    assert context.last_user_turn is not None
    assert context.last_user_turn.content == "¿Y para qué sirve?"
    assert context.last_assistant_turn is not None
    assert context.last_assistant_turn.content is not None
    assert isinstance(context.active_topics, list)
    assert isinstance(context.unresolved_ambiguities, list)
    print("PASS: test_get_session_context")


def test_detect_unresolved_ambiguities():
    """Detectar ambigüedades no resueltas."""
    manager = create_session_manager()
    session = manager.create_session()
    
    t1 = manager.add_turn(session.id, TurnRole.ASSISTANT, "Python es un lenguaje interpretado.", TurnType.QUERY)
    t2 = manager.add_turn(session.id, TurnRole.USER, "¿Qué es Python?", TurnType.QUERY)
    t3 = manager.add_turn(session.id, TurnRole.USER, "Explícamelo mejor.", TurnType.QUERY)
    
    # Referencia de t3 a t2 (implícita)
    ref = manager.add_reference(
        session_id=session.id,
        source_turn_id=t3.id,
        target_turn_id=t2.id,
        reference_type=ReferenceType.IMPLICIT,
        reference_text="mejor",
        confidence=0.6,
    )
    
    # Turno fallido
    from models.contracts import TurnStatus
    failed_turn = ConversationTurn(
        session_id=session.id,
        turn_number=4,
        role=TurnRole.ASSISTANT,
        turn_type=TurnType.QUERY,
        content="Error",
        status=TurnStatus.FAILED,
        error_message="Timeout",
    )
    session.turns.append(failed_turn)
    manager.update_session(session)
    
    context = manager.get_session_context(session.id)
    
    ambiguities = context.unresolved_ambiguities
    assert len(ambiguities) >= 2  # Referencia pendiente + turno fallido
    assert any("Referencia pendiente" in a for a in ambiguities)
    assert any("Turno fallido" in a for a in ambiguities)
    print("PASS: test_detect_unresolved_ambiguities")


# ============================================================================
# TESTS: Estadísticas
# ============================================================================

def test_session_stats():
    """Estadísticas de sesión."""
    manager = create_session_manager()
    session = manager.create_session()
    
    manager.add_turn(session.id, TurnRole.USER, "Hola", tokens_used=10, latency_ms=100)
    manager.add_turn(session.id, TurnRole.ASSISTANT, "Hola!", tokens_used=5, latency_ms=50)
    manager.add_turn(session.id, TurnRole.USER, "¿Cómo estás?", tokens_used=8, latency_ms=80)
    
    stats = manager.get_session_stats(session.id)
    
    assert stats is not None
    assert stats["total_turns"] == 3
    assert stats["user_turns"] == 2
    assert stats["assistant_turns"] == 1
    assert stats["total_tokens"] == 23  # 10+5+8 = 23
    print("PASS: test_session_stats")


def test_global_stats():
    """Estadísticas globales."""
    manager = create_session_manager()
    
    s1 = manager.create_session(title="S1")
    s2 = manager.create_session(title="S2")
    manager.close_session(s1.id)
    
    manager.add_turn(s1.id, TurnRole.USER, "Hola", tokens_used=10)
    manager.add_turn(s2.id, TurnRole.USER, "Hola", tokens_used=5)
    
    stats = manager.get_global_stats()
    
    assert stats["total_sessions"] >= 2
    assert stats["active_sessions"] >= 1
    assert stats["completed_sessions"] >= 1
    assert stats["total_turns"] >= 2
    assert stats["total_tokens"] >= 15
    print("PASS: test_global_stats")


# ============================================================================
# TESTS: Persistencia (simulada)
# ============================================================================

def test_persistence():
    """Persistencia de sesión."""
    import tempfile
    import shutil
    
    temp_dir = tempfile.mkdtemp()
    try:
        manager = create_session_manager(storage_path=temp_dir)
        session = manager.create_session(title="Persistent", initial_query="Test")
        
        manager.add_turn(session.id, TurnRole.USER, "Test")
        
        # Crear nuevo manager con mismo storage
        manager2 = create_session_manager(storage_path=temp_dir)
        loaded = manager2.get_session(session.id)
        
        assert loaded is not None
        assert loaded.id == session.id
        assert loaded.title == "Persistent"
        assert len(loaded.turns) == 1
        print("PASS: test_persistence")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# ============================================================================
# RUN ALL TESTS
# ============================================================================

if __name__ == "__main__":
    import sys
    
    test_functions = [
        test_create_session,
        test_get_session,
        test_update_session,
        test_close_session,
        test_list_sessions,
        test_add_turn,
        test_add_multiple_turns,
        test_turn_limits,
        test_token_limit,
        test_add_reference,
        test_resolve_references,
        test_pending_references,
        test_get_session_context,
        test_detect_unresolved_ambiguities,
        test_session_stats,
        test_global_stats,
        test_persistence,
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
            failed += 1
    
    print(f"\n{'='*50}")
    print(f"Resultados: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)