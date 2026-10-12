"""
Gestor de Memoria y Grafo de Sesión Conversacional - Fase 6: Paso 1

Implementa:
1. Persistencia y recuperación de sesiones conversacionales
2. Gestión de turnos y grafo de referencias entre turnos
3. Desambiguación y enlace determinista de referencias
4. Contexto de sesión para toma de decisiones
"""

from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from uuid import UUID, uuid4
from datetime import datetime
from enum import Enum
import logging
import json
from pathlib import Path

from models.contracts import (
    ConversationTurn, TurnReference, ConversationSession, SessionContext,
    TurnRole, TurnType, TurnStatus, ReferenceType, SessionStatus,
    TurnRole, TurnType, TurnStatus, ReferenceType, SessionStatus,
    ConversationTurn, TurnReference, ConversationSession, SessionContext,
)

logger = logging.getLogger(__name__)


class SessionManager:
    """
    Gestor de Memoria y Grafo de Sesión Conversacional.
    
    Responsabilidades:
    - Persistencia y recuperación de sesiones conversacionales
    - Gestión de turnos y grafo de referencias entre turnos
    - Desambiguación y enlace determinista de referencias
    - Proporcionar contexto de sesión para toma de decisiones
    """
    
    def __init__(
        self,
        storage_path: Optional[str] = None,
        max_turns_per_session: int = 100,
        max_tokens_per_session: int = 8000,
        reference_confidence_threshold: float = 0.7,
    ):
        """
        Inicializa el gestor de sesiones.
        
        Args:
            storage_path: Ruta para persistencia de sesiones (opcional)
            max_turns_per_session: Límite máximo de turnos por sesión
            max_tokens_per_session: Límite de tokens por sesión
            reference_confidence_threshold: Umbral de confianza para resolver referencias
        """
        self.storage_path = Path(storage_path) if storage_path else None
        self.max_turns_per_session = max_turns_per_session
        self.max_tokens_per_session = max_tokens_per_session
        self.reference_confidence_threshold = reference_confidence_threshold
        
        # Cache en memoria de sesiones activas
        self._sessions: Dict[UUID, ConversationSession] = {}
        
        # Asegurar directorio de almacenamiento
        if self.storage_path:
            self.storage_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"SessionManager inicializado | storage={self.storage_path} | max_turns={max_turns_per_session}")
    
    # =============================================================================
    # GESTIÓN DE SESIONES
    # =============================================================================
    
    def create_session(
        self,
        initial_query: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[list[str]] = None,
        max_turns: Optional[int] = None,
        max_tokens: Optional[int] = None,
    ) -> ConversationSession:
        """
        Crea una nueva sesión conversacional.
        
        Args:
            initial_query: Consulta inicial que inició la sesión
            title: Título descriptivo
            description: Descripción detallada
            tags: Etiquetas para clasificación
            max_turns: Límite de turnos (sobrescribe default)
            max_tokens: Límite de tokens (sobrescribe default)
            
        Returns:
            ConversationSession creada
        """
        session = ConversationSession(
            initial_query=initial_query,
            title=title,
            description=description,
            tags=tags or [],
            max_turns=max_turns or self.max_turns_per_session,
            max_tokens=max_tokens or self.max_tokens_per_session,
        )
        
        self._sessions[session.id] = session
        self._persist_session(session)
        
        logger.info(f"Sesión creada: {session.id} | turns_max={session.max_turns} | tokens_max={session.max_tokens}")
        return session
    
    def get_session(self, session_id: UUID) -> Optional[ConversationSession]:
        """
        Obtiene una sesión por ID.
        
        Args:
            session_id: ID de la sesión
            
        Returns:
            ConversationSession si existe, None en caso contrario
        """
        # Primero buscar en caché
        if session_id in self._sessions:
            return self._sessions[session_id]
        
        # Intentar cargar desde almacenamiento
        session = self._load_session(session_id)
        if session:
            self._sessions[session_id] = session
            return session
        
        return None
    
    def update_session(self, session: ConversationSession) -> None:
        """
        Actualiza una sesión existente.
        
        Args:
            session: Sesión a actualizar
        """
        session.updated_at = datetime.utcnow()
        session.total_turns = len(session.turns)
        session.total_tokens = sum(t.tokens_used or 0 for t in session.turns)
        session.total_latency_ms = sum(t.latency_ms or 0 for t in session.turns)
        
        self._sessions[session.id] = session
        self._persist_session(session)
        
        logger.debug(f"Sesión actualizada: {session.id} | turns={session.total_turns}")
    
    def close_session(self, session_id: UUID, reason: str = "completed") -> bool:
        """
        Cierra una sesión.
        
        Args:
            session_id: ID de la sesión
            reason: Razón del cierre
            
        Returns:
            True si se cerró correctamente
        """
        session = self.get_session(session_id)
        if not session:
            return False
        
        session.status = SessionStatus.COMPLETED if reason == "completed" else SessionStatus.ARCHIVED
        session.completed_at = datetime.utcnow()
        session.updated_at = datetime.utcnow()
        
        self.update_session(session)
        logger.info(f"Sesión cerrada: {session_id} | reason={reason}")
        return True
    
    # =============================================================================
    # GESTIÓN DE TURNOS
    # =============================================================================
    
    def add_turn(
        self,
        session_id: UUID,
        role: "TurnRole",
        content: str,
        turn_type: "TurnType" = TurnType.QUERY,
        referenced_evidence_ids: Optional[list[UUID]] = None,
        claim_evaluation_ids: Optional[list[UUID]] = None,
        structured_result_id: Optional[UUID] = None,
        tokens_used: Optional[int] = None,
        latency_ms: Optional[int] = None,
    ) -> Optional[ConversationTurn]:
        """
        Añade un turno a la sesión.
        
        Args:
            session_id: ID de la sesión
            role: Rol del emisor
            content: Contenido textual
            turn_type: Tipo de turno
            referenced_evidence_ids: IDs de evidencia referenciada
            claim_evaluation_ids: IDs de evaluaciones de afirmaciones
            structured_result_id: ID del resultado estructurado
            tokens_used: Tokens consumidos
            latency_ms: Latencia en ms
            
        Returns:
            ConversationTurn creado o None si error
        """
        session = self.get_session(session_id)
        if not session:
            logger.error(f"Sesión no encontrada: {session_id}")
            return None
        
        # Verificar límites
        if len(session.turns) >= session.max_turns:
            logger.warning(f"Límite de turnos alcanzado para sesión {session_id}")
            return None
        
        if session.total_tokens + (tokens_used or 0) > session.max_tokens:
            logger.warning(f"Límite de tokens alcanzado para sesión {session_id}")
            return None
        
        # Crear turno
        turn_number = len(session.turns) + 1
        turn = ConversationTurn(
            session_id=session_id,
            turn_number=turn_number,
            role=role,
            turn_type=turn_type,
            content=content,
            referenced_evidence_ids=referenced_evidence_ids or [],
            claim_evaluation_ids=claim_evaluation_ids or [],
            structured_result_id=structured_result_id,
            tokens_used=tokens_used,
            latency_ms=latency_ms,
        )
        
        session.turns.append(turn)
        self.update_session(session)
        
        logger.info(f"Turno añadido: session={session_id} | turn={turn_number} | role={role.value}")
        return turn
    
    def get_turn(self, session_id: UUID, turn_id: UUID) -> Optional[ConversationTurn]:
        """
        Obtiene un turno específico de una sesión.
        """
        session = self.get_session(session_id)
        if not session:
            return None
        
        for turn in session.turns:
            if turn.id == turn_id:
                return turn
        return None
    
    def update_turn_status(self, session_id: UUID, turn_id: UUID, status: "TurnStatus") -> bool:
        """
        Actualiza el estado de un turno.
        """
        turn = self.get_turn(session_id, turn_id)
        if not turn:
            return False
        
        turn.status = status
        if status == TurnStatus.COMPLETED:
            turn.completed_at = datetime.utcnow()
        
        session = self.get_session(session_id)
        if session:
            self.update_session(session)
        return True
    
    # =============================================================================
    # GESTIÓN DE REFERENCIAS (DESAMBIGUACIÓN)
    # =============================================================================
    
    def add_reference(
        self,
        session_id: UUID,
        source_turn_id: UUID,
        target_turn_id: UUID,
        reference_type: "ReferenceType",
        reference_text: str,
        resolved_content: Optional[str] = None,
        confidence: float = 1.0,
    ) -> Optional[TurnReference]:
        """
        Añade una referencia entre turnos para desambiguación.
        
        Args:
            session_id: ID de la sesión
            source_turn_id: ID del turno que hace la referencia
            target_turn_id: ID del turno referenciado
            reference_type: Tipo de referencia
            reference_text: Texto de la referencia
            resolved_content: Contenido resuelto (opcional)
            confidence: Confianza en la resolución
            
        Returns:
            TurnReference creada o None si error
        """
        session = self.get_session(session_id)
        if not session:
            return None
        
        # Verificar que ambos turnos existen en la sesión
        source_turn = self.get_turn(session_id, source_turn_id)
        target_turn = self.get_turn(session_id, target_turn_id)
        
        if not source_turn or not target_turn:
            logger.warning(f"Turno origen o destino no encontrado en sesión {session_id}")
            return None
        
        # Verificar que la referencia es hacia atrás en el tiempo (no forward sin cataphora)
        if source_turn.turn_number <= target_turn.turn_number and reference_type != ReferenceType.CATAPHORIC:
            logger.warning("Referencia hacia adelante detectada sin marcar como cataphora")
        
        reference = TurnReference(
            source_turn_id=source_turn_id,
            target_turn_id=target_turn_id,
            reference_type=reference_type,
            reference_text=reference_text,
            resolved_content=resolved_content,
            confidence=confidence,
        )
        
        session.references.append(reference)
        self.update_session(session)
        
        logger.debug(f"Referencia añadida: {source_turn_id} -> {target_turn_id} ({reference_type.value})")
        return reference
    
    def resolve_references(
        self,
        session_id: UUID,
        source_turn_id: UUID,
    ) -> list[TurnReference]:
        """
        Resuelve todas las referencias pendientes de un turno.
        
        Args:
            session_id: ID de la sesión
            source_turn_id: ID del turno que contiene referencias
            
        Returns:
            Lista de referencias resueltas
        """
        session = self.get_session(session_id)
        if not session:
            return []
        
        resolved = []
        for ref in session.references:
            if ref.source_turn_id == source_turn_id:
                # Resolver contenido si no está resuelto
                if not ref.resolved_content:
                    target_turn = self.get_turn(session_id, ref.target_turn_id)
                    if target_turn:
                        ref.resolved_content = target_turn.content
                        ref.confidence = max(ref.confidence, 0.8)  # Boost confidence al resolver
                
                # Verificar umbral DESPUÉS de boostear la confianza
                if ref.confidence >= self.reference_confidence_threshold:
                    resolved.append(ref)
        
        logger.debug(f"Referencias resueltas para turno {source_turn_id}: {len(resolved)}")
        return resolved
    
    def get_pending_references(self, session_id: UUID) -> list[TurnReference]:
        """
        Obtiene referencias pendientes de resolver (confianza baja).
        """
        session = self.get_session(session_id)
        if not session:
            return []
        
        pending = [
            ref for ref in session.references
            if ref.confidence < self.reference_confidence_threshold
        ]
        return pending
    
    # =============================================================================
    # CONTEXTO DE SESIÓN
    # =============================================================================
    
    def get_session_context(self, session_id: UUID) -> Optional[SessionContext]:
        """
        Obtiene el contexto actual de la sesión para toma de decisiones.
        
        Args:
            session_id: ID de la sesión
            
        Returns:
            SessionContext con estado actual o None si error
        """
        session = self.get_session(session_id)
        if not session:
            return None
        
        # Últimos turnos
        user_turns = [t for t in session.turns if t.role == TurnRole.USER]
        assistant_turns = [t for t in session.turns if t.role == TurnRole.ASSISTANT]
        
        last_user = user_turns[-1] if user_turns else None
        last_assistant = assistant_turns[-1] if assistant_turns else None
        
        # Referencias pendientes
        pending_refs = self.get_pending_references(session.id)
        
        # Temas activos (extraer de conclusiones/claims recientes)
        active_topics = self._extract_active_topics(session)
        
        # Ambiguedades no resueltas
        unresolved = self._detect_unresolved_ambiguities(session)
        
        return SessionContext(
            session_id=session.id,
            current_turn_number=len(session.turns) + 1,
            last_user_turn=last_user,
            last_assistant_turn=last_assistant,
            pending_references=pending_refs,
            active_topics=active_topics,
            unresolved_ambiguities=unresolved,
        )
    
    def _extract_active_topics(self, session: ConversationSession) -> list[str]:
        """Extrae temas activos de la conversación reciente."""
        topics = []
        
        # De los últimos 5 turnos del asistente
        recent_assistant = [t for t in session.turns if t.role == TurnRole.ASSISTANT][-5:]
        for turn in recent_assistant:
            if turn.structured_result_id:
                # En implementación real, buscar el StructuredResult y extraer temas
                pass
        
        # De claims/evaluaciones recientes
        for turn in session.turns[-5:]:
            for eval_id in turn.claim_evaluation_ids:
                # En implementación real, buscar la ClaimEvaluation y extraer tema
                pass
        
        # Por ahora, extraer de consultas iniciales y títulos
        if session.initial_query:
            topics = session.initial_query.split()[:5]
        
        return list(set(topics))[:10]
    
    def _detect_unresolved_ambiguities(self, session: ConversationSession) -> list[str]:
        """Detecta ambigüedades no resueltas en la sesión."""
        ambiguities = []
        
        # Referencias sin resolver
        pending = self.get_pending_references(session.id)
        for ref in pending:
            ambiguities.append(f"Referencia pendiente: '{ref.reference_text}' (confianza: {ref.confidence:.0%})")
        
        # Turnos fallidos
        failed_turns = [t for t in session.turns if t.status == TurnStatus.FAILED]
        for turn in failed_turns:
            ambiguities.append(f"Turno fallido #{turn.turn_number}: {turn.error_message or 'Error desconocido'}")
        
        return ambiguities
    
    # =============================================================================
    # PERSISTENCIA
    # =============================================================================
    
    def _persist_session(self, session: ConversationSession) -> None:
        """Persiste una sesión al almacenamiento."""
        if not self.storage_path:
            return
        
        try:
            file_path = self.storage_path / f"{session.id}.json"
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(session.model_dump(mode='json'), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error persistiendo sesión {session.id}: {e}")
    
    def _load_session(self, session_id: UUID) -> Optional[ConversationSession]:
        """Carga una sesión desde almacenamiento."""
        if not self.storage_path:
            return None
        
        try:
            file_path = self.storage_path / f"{session_id}.json"
            if not file_path.exists():
                return None
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            return ConversationSession.model_validate(data)
        except Exception as e:
            logger.error(f"Error cargando sesión {session_id}: {e}")
            return None
    
    def list_sessions(
        self,
        status: Optional["SessionStatus"] = None,
        limit: int = 50,
    ) -> list[ConversationSession]:
        """
        Lista sesiones con filtros opcionales.
        """
        sessions = list(self._sessions.values())
        
        # Cargar desde disco si no están en caché
        if self.storage_path:
            for file_path in self.storage_path.glob("*.json"):
                session_id = UUID(file_path.stem)
                if session_id not in self._sessions:
                    session = self._load_session(session_id)
                    if session:
                        self._sessions[session_id] = session
        
        sessions = list(self._sessions.values())
        
        if status:
            sessions = [s for s in sessions if s.status == status]
        
        # Ordenar por fecha de actualización descendente
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        
        return sessions[:limit]
    
    def delete_session(self, session_id: UUID) -> bool:
        """Elimina una sesión (marca como archivada y elimina archivo)."""
        session = self.get_session(session_id)
        if not session:
            return False
        
        session.status = SessionStatus.ARCHIVED
        self.update_session(session)
        
        # Eliminar archivo
        if self.storage_path:
            file_path = self.storage_path / f"{session_id}.json"
            try:
                file_path.unlink(missing_ok=True)
            except Exception:
                pass
        
        self._sessions.pop(session_id, None)
        return True
    
    # =============================================================================
    # ESTADÍSTICAS Y MÉTRICAS
    # =============================================================================
    
    def get_session_stats(self, session_id: UUID) -> Optional[dict]:
        """Obtiene estadísticas de una sesión."""
        session = self.get_session(session_id)
        if not session:
            return None
        
        user_turns = [t for t in session.turns if t.role == TurnRole.USER]
        assistant_turns = [t for t in session.turns if t.role == TurnRole.ASSISTANT]
        failed_turns = [t for t in session.turns if t.status == TurnStatus.FAILED]
        
        avg_tokens = (
            sum(t.tokens_used or 0 for t in session.turns) / len(session.turns)
            if session.turns else 0
        )
        avg_latency = (
            sum(t.latency_ms or 0 for t in session.turns) / len(session.turns)
            if session.turns else 0
        )
        
        return {
            "session_id": str(session.id),
            "status": session.status.value,
            "total_turns": session.total_turns,
            "user_turns": len(user_turns),
            "assistant_turns": len(assistant_turns),
            "failed_turns": len(failed_turns),
            "total_tokens": session.total_tokens,
            "total_latency_ms": session.total_latency_ms,
            "avg_tokens_per_turn": round(avg_tokens, 1),
            "avg_latency_ms": round(avg_latency, 1),
            "total_references": len(session.references),
            "pending_references": len(self.get_pending_references(session.id)),
            "duration_seconds": (
                (session.completed_at or datetime.utcnow()) - session.created_at
            ).total_seconds() if session.completed_at else (
                datetime.utcnow() - session.created_at
            ).total_seconds(),
        }
    
    def get_global_stats(self) -> dict:
        """Obtiene estadísticas globales del gestor."""
        sessions = self.list_sessions()
        
        active = sum(1 for s in sessions if s.status == SessionStatus.ACTIVE)
        completed = sum(1 for s in sessions if s.status == SessionStatus.COMPLETED)
        archived = sum(1 for s in sessions if s.status == SessionStatus.ARCHIVED)
        
        total_turns = sum(s.total_turns for s in sessions)
        total_tokens = sum(s.total_tokens for s in sessions)
        
        return {
            "total_sessions": len(sessions),
            "active_sessions": active,
            "completed_sessions": completed,
            "archived_sessions": archived,
            "total_turns": total_turns,
            "total_tokens": total_tokens,
            "avg_turns_per_session": round(total_turns / len(sessions), 1) if sessions else 0,
            "storage_path": str(self.storage_path) if self.storage_path else "memory_only",
        }


def create_session_manager(
    storage_path: Optional[str] = None,
    max_turns_per_session: int = 100,
    max_tokens_per_session: int = 8000,
    reference_confidence_threshold: float = 0.7,
) -> SessionManager:
    """Factoría para SessionManager."""
    return SessionManager(
        storage_path=storage_path,
        max_turns_per_session=max_turns_per_session,
        max_tokens_per_session=max_tokens_per_session,
        reference_confidence_threshold=reference_confidence_threshold,
    )