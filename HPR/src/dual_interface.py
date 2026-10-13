"""
Motor HPR - Interfaz Dual de Doble Pestaña (Sección 2)

Arquitectura de interfaz unificada:
  - Pestaña 1: "Chat Autónomo / Natural" → entrada fija inferior, flujo ascendente, voz
  - Pestaña 2: "Motor Técnico / Manual"  → barra de comandos superior, DAGs, auditoría

Endpoints backend:
  - POST /api/v1/chat        (chat autónomo con memoria de sesión)
  - POST /api/v1/orchestrate (orquestación técnica manual)

Fase 4 (Pipeline de Comunicación Backend):
  - HPRClient unificado: sesión reutilizable con connection pooling,
    timeouts robustos por canal (connect, read) y reintentos idempotentes.
  - Canal Autónomo (/api/v1/chat): baja latencia, sin validaciones
    manuales de triggers.
  - Canal Técnico (/api/v1/orchestrate): contratos Pydantic estrictos
    del TaskOrchestrator, validación local fail-fast, inspección de
    subtareas, presupuesto de tokens y traza de eventos reconstruida.
  - Errores tipados por canal (HPRTimeoutError, HPRConnectionError,
    HPRHTTPError, HPRContractError) y observabilidad (ChannelStats).

Diseño ligero: sin dependencias remotas innecesarias, requests con timeout,
Web Speech API nativa del navegador para reconocimiento de voz (Pestaña 1).
"""

import html
import json
import time
import uuid
from typing import Optional, Dict, Any, List

import requests
import streamlit as st
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ---------------------------------------------------------------------------
# Configuración de página (debe ser la primera llamada de Streamlit)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Motor HPR - Interfaz Dual",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Configuración global
# ---------------------------------------------------------------------------
DEFAULT_API_URL = "http://localhost:8000"

if "api_url" not in st.session_state:
    st.session_state.api_url = DEFAULT_API_URL

if "active_session_id" not in st.session_state:
    st.session_state.active_session_id = None

if "tech_session_id" not in st.session_state:
    st.session_state.tech_session_id = None

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "orchestration_history" not in st.session_state:
    st.session_state.orchestration_history = []

if "voice_active" not in st.session_state:
    st.session_state.voice_active = False

if "live_context" not in st.session_state:
    st.session_state.live_context = None

if "last_context_sync" not in st.session_state:
    st.session_state.last_context_sync = None


# ---------------------------------------------------------------------------
# Cliente HTTP unificado (Fase 4: Pipeline de Comunicación Backend)
# ---------------------------------------------------------------------------
# Perfiles de timeout por canal: (connect, read) en segundos
CHAT_CHANNEL_TIMEOUT = (2.0, 15.0)    # Canal Autónomo: prioriza baja latencia
TECH_CHANNEL_TIMEOUT = (2.0, 120.0)   # Canal Técnico: orquestación pesada
MGMT_CHANNEL_TIMEOUT = (2.0, 5.0)     # Gestión de sesiones
HEALTH_PROBE_TIMEOUT = (1.0, 2.0)     # Sonda de salud (no bloqueante)

# Contratos del Canal Técnico (espejo local de OrchestrateRequest / IntentSchema)
TECH_INTENT_CATEGORIES = frozenset({
    "analysis", "synthesis", "verification", "decision",
    "planning", "execution", "clarification", "monitoring",
})
TECH_INTENT_COMPLEXITIES = frozenset({"atomic", "simple", "moderate", "complex"})
TECH_INTENT_PRIORITIES = frozenset({"low", "normal", "high", "critical"})


class HPRCommunicationError(Exception):
    """Error base del pipeline de comunicación HPR."""

    def __init__(self, message: str, channel: str = "unknown",
                 status_code: Optional[int] = None):
        super().__init__(message)
        self.channel = channel
        self.status_code = status_code


class HPRTimeoutError(HPRCommunicationError):
    """Timeout agotado en un canal de comunicación."""


class HPRConnectionError(HPRCommunicationError):
    """Fallo de conexión con el backend."""


class HPRHTTPError(HPRCommunicationError):
    """Respuesta HTTP de error (4xx/5xx) del backend."""


class HPRContractError(HPRCommunicationError):
    """Violación de contrato Pydantic detectada localmente (Canal Técnico)."""


class ChannelStats:
    """Métricas de observabilidad por canal (Fase 4)."""

    def __init__(self):
        self.requests = 0
        self.errors = 0
        self.timeouts = 0
        self._latencies: List[float] = []

    def record(self, latency_ms: float, error: bool = False,
               timeout: bool = False) -> None:
        self.requests += 1
        self._latencies.append(latency_ms)
        if len(self._latencies) > 100:
            self._latencies.pop(0)
        if error:
            self.errors += 1
        if timeout:
            self.timeouts += 1

    @property
    def avg_latency_ms(self) -> float:
        if not self._latencies:
            return 0.0
        return sum(self._latencies) / len(self._latencies)


class HPRClient:
    """Cliente HTTP unificado del motor HPR (Fase 4).

    Características:
    - Sesión reutilizable con connection pooling (keep-alive entre turnos).
    - Timeouts robustos por canal: tupla (connect, read) en segundos.
    - Reintentos seguros solo en métodos idempotentes (GET/DELETE).
    - Dos canales de comunicación diferenciados:
        * Canal Autónomo  → POST /api/v1/chat      (baja latencia, sin
          validaciones manuales de triggers; fluidez del diálogo).
        * Canal Técnico   → POST /api/v1/orchestrate (contratos Pydantic
          estrictos del TaskOrchestrator, validación local previa).
    - Observabilidad: estadísticas de latencia/errores por canal.
    """

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.timeouts: Dict[str, tuple] = {
            "autonomous": CHAT_CHANNEL_TIMEOUT,
            "technical": TECH_CHANNEL_TIMEOUT,
            "management": MGMT_CHANNEL_TIMEOUT,
        }
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "MotorHPR-DualInterface/4.0",
        })
        # Pool de conexiones reutilizables + reintentos idempotentes
        retry = Retry(
            total=2,
            connect=2,
            read=0,
            backoff_factor=0.3,
            status_forcelist=(502, 503, 504),
            allowed_methods=frozenset({"GET", "DELETE"}),
        )
        adapter = HTTPAdapter(pool_connections=10, pool_maxsize=10,
                              max_retries=retry)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        # Observabilidad por canal
        self.stats: Dict[str, ChannelStats] = {
            "autonomous": ChannelStats(),
            "technical": ChannelStats(),
            "management": ChannelStats(),
        }
        self.last_latency_ms: Dict[str, float] = {}

    # ------------------------------------------------------------------
    # Núcleo de transporte
    # ------------------------------------------------------------------
    def _request(self, method: str, path: str, channel: str,
                 json_payload: Optional[Dict[str, Any]] = None,
                 params: Optional[Dict[str, Any]] = None) -> requests.Response:
        """Ejecuta una petición con timeout y trazabilidad por canal."""
        url = f"{self.base_url}{path}"
        timeout = self.timeouts.get(channel, MGMT_CHANNEL_TIMEOUT)
        headers = {"X-HPR-Channel": channel}
        start = time.perf_counter()
        try:
            resp = self.session.request(
                method, url, json=json_payload, params=params,
                timeout=timeout, headers=headers,
            )
            latency = (time.perf_counter() - start) * 1000.0
            self.last_latency_ms[channel] = latency
            if 400 <= resp.status_code < 600:
                self.stats[channel].record(latency, error=True)
                raise HPRHTTPError(
                    f"HTTP {resp.status_code} en {method} {path}: "
                    f"{resp.text[:300]}",
                    channel=channel, status_code=resp.status_code,
                )
            self.stats[channel].record(latency)
            return resp
        except requests.exceptions.Timeout as e:
            latency = (time.perf_counter() - start) * 1000.0
            self.stats[channel].record(latency, error=True, timeout=True)
            raise HPRTimeoutError(
                f"Timeout agotado en canal '{channel}' "
                f"(connect={timeout[0]}s, read={timeout[1]}s)",
                channel=channel,
            ) from e
        except requests.exceptions.ConnectionError as e:
            latency = (time.perf_counter() - start) * 1000.0
            self.stats[channel].record(latency, error=True)
            raise HPRConnectionError(
                f"No se pudo conectar al backend en {self.base_url}",
                channel=channel,
            ) from e
        except requests.exceptions.RequestException as e:
            latency = (time.perf_counter() - start) * 1000.0
            self.stats[channel].record(latency, error=True)
            raise HPRCommunicationError(str(e), channel=channel) from e

    # ------------------------------------------------------------------
    # CANAL AUTÓNOMO — pipeline simplificado de turnos conversacionales
    # ------------------------------------------------------------------
    def chat(self, session_id: Optional[str], message: str,
             use_voice: bool = False, language: str = "es") -> Dict[str, Any]:
        """POST /api/v1/chat (Canal Autónomo).

        Conexión optimizada para baja latencia: payload mínimo, conexión
        reutilizada (keep-alive) y sin validaciones manuales de triggers —
        la fluidez del diálogo tiene prioridad.
        """
        payload: Dict[str, Any] = {
            "message": message,
            "use_voice": use_voice,
            "language": language,
        }
        if session_id:
            payload["session_id"] = session_id
        resp = self._request("POST", "/api/v1/chat", "autonomous",
                             json_payload=payload)
        return resp.json()

    # ------------------------------------------------------------------
    # CANAL TÉCNICO — contratos estrictos del TaskOrchestrator
    # ------------------------------------------------------------------
    def orchestrate(self, session_id: str, intent_summary: str,
                    intent_category: str = "analysis",
                    intent_complexity: str = "simple",
                    intent_priority: str = "normal",
                    constraints: Optional[List[str]] = None,
                    success_criteria: Optional[List[str]] = None,
                    dry_run: bool = False) -> Dict[str, Any]:
        """POST /api/v1/orchestrate (Canal Técnico).

        Acceso estricto a los contratos Pydantic del TaskOrchestrator:
        validación local previa (fail-fast sin round-trip) y timeout
        amplio para planificación/ejecución de DAGs.
        """
        self._validate_technical_contract(
            session_id=session_id,
            intent_summary=intent_summary,
            intent_category=intent_category,
            intent_complexity=intent_complexity,
            intent_priority=intent_priority,
            constraints=constraints,
            success_criteria=success_criteria,
        )
        payload: Dict[str, Any] = {
            "session_id": session_id,
            "intent_summary": intent_summary,
            "intent_category": intent_category,
            "intent_complexity": intent_complexity,
            "intent_priority": intent_priority,
            "constraints": constraints or [],
            "success_criteria": success_criteria or [],
            "dry_run": dry_run,
        }
        resp = self._request("POST", "/api/v1/orchestrate", "technical",
                             json_payload=payload)
        return resp.json()

    @staticmethod
    def _validate_technical_contract(session_id, intent_summary,
                                     intent_category, intent_complexity,
                                     intent_priority, constraints,
                                     success_criteria) -> None:
        """Validación local espejo del contrato ``OrchestrateRequest`` (Pydantic).

        Detecta violaciones de contrato antes del round-trip, con mensajes
        deterministas para auditoría.
        """
        if not session_id:
            raise HPRContractError(
                "session_id es obligatorio en el Canal Técnico (contrato: UUID)",
                channel="technical",
            )
        try:
            uuid.UUID(str(session_id))
        except (ValueError, TypeError, AttributeError):
            raise HPRContractError(
                f"session_id inválido, debe ser un UUID: {session_id}",
                channel="technical",
            )
        summary = (intent_summary or "").strip()
        if not (1 <= len(summary) <= 500):
            raise HPRContractError(
                "intent_summary debe tener entre 1 y 500 caracteres "
                f"(contrato OrchestrateRequest), recibidos: {len(summary)}",
                channel="technical",
            )
        if intent_category not in TECH_INTENT_CATEGORIES:
            raise HPRContractError(
                f"intent_category inválida: '{intent_category}'. "
                f"Permitidas: {', '.join(sorted(TECH_INTENT_CATEGORIES))}",
                channel="technical",
            )
        if intent_complexity not in TECH_INTENT_COMPLEXITIES:
            raise HPRContractError(
                f"intent_complexity inválida: '{intent_complexity}'. "
                f"Permitidas: {', '.join(sorted(TECH_INTENT_COMPLEXITIES))}",
                channel="technical",
            )
        if intent_priority not in TECH_INTENT_PRIORITIES:
            raise HPRContractError(
                f"intent_priority inválida: '{intent_priority}'. "
                f"Permitidas: {', '.join(sorted(TECH_INTENT_PRIORITIES))}",
                channel="technical",
            )
        for field_name, values in (
            ("constraints", constraints),
            ("success_criteria", success_criteria),
        ):
            if values is not None and (
                not isinstance(values, list)
                or not all(isinstance(v, str) for v in values)
            ):
                raise HPRContractError(
                    f"{field_name} debe ser una lista de strings "
                    "(contrato OrchestrateRequest)",
                    channel="technical",
                )

    # ------------------------------------------------------------------
    # Canal de gestión de sesiones
    # ------------------------------------------------------------------
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """GET /api/v1/sessions/{session_id}"""
        try:
            resp = self._request("GET", f"/api/v1/sessions/{session_id}",
                                 "management")
            return resp.json()
        except HPRCommunicationError:
            return None

    def get_session_context(self, session_id: str) -> Optional[Dict[str, Any]]:
        """GET /api/v1/sessions/{session_id}/context"""
        try:
            resp = self._request("GET",
                                 f"/api/v1/sessions/{session_id}/context",
                                 "management")
            return resp.json()
        except HPRCommunicationError:
            return None

    def list_sessions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """GET /api/v1/sessions"""
        try:
            resp = self._request("GET", "/api/v1/sessions", "management",
                                 params={"limit": limit})
            return resp.json()
        except HPRCommunicationError:
            return []

    def delete_session(self, session_id: str) -> bool:
        """DELETE /api/v1/sessions/{session_id}"""
        try:
            resp = self._request("DELETE", f"/api/v1/sessions/{session_id}",
                                 "management")
            return resp.status_code == 200
        except HPRCommunicationError:
            return False

    def health_check(self) -> Dict[str, Any]:
        """Sonda de salud con timeout agresivo (no bloquea la UI)."""
        try:
            start = time.perf_counter()
            resp = self.session.get(f"{self.base_url}/",
                                    timeout=HEALTH_PROBE_TIMEOUT)
            latency = (time.perf_counter() - start) * 1000.0
            return {
                "ok": resp.status_code == 200,
                "status": resp.status_code,
                "latency_ms": round(latency, 1),
            }
        except requests.RequestException:
            return {"ok": False, "status": None, "latency_ms": None}


@st.cache_resource
def get_client(api_url: str = DEFAULT_API_URL) -> HPRClient:
    """Singleton del cliente HTTP (cacheado por resource + URL base)."""
    return HPRClient(api_url)


def build_orchestration_events(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Reconstruye la traza de eventos de orquestación (contrato
    ``OrchestrationEvent``) desde la respuesta del Canal Técnico.

    El orquestador emite ``OrchestrationEvent`` internamente; esta
    reconstrucción determinista permite inspeccionar la traza de eventos
    en la interfaz sin sobrecargar el contrato de respuesta.
    """
    events: List[Dict[str, Any]] = []
    metrics = result.get("metrics") or {}
    base_ts = metrics.get("started_at") or time.strftime("%Y-%m-%dT%H:%M:%S")
    task_id = result.get("task_id")

    def _emit(event_type: str, message: str,
              payload: Optional[Dict[str, Any]] = None):
        events.append({
            "event_type": event_type,
            "message": message,
            "timestamp": base_ts,
            "task_id": task_id,
            "payload": payload or {},
        })

    _emit("intent_received", "Intención técnica recibida por el orquestador",
          {"session_id": result.get("session_id")})

    phase = result.get("phase_reached", "unknown")
    _emit("decomposition_completed",
          f"Descomposición completada — fase alcanzada: {phase}",
          {"phase": phase, "subtasks_planned": result.get("subtasks_planned", 0)})

    for node in result.get("dag_structure") or []:
        node_name = node.get("name", "Sin nombre")
        node_status = node.get("status", "pending")
        node_payload = {
            "subtask_id": node.get("id"),
            "type": node.get("type"),
            "depends_on": node.get("depends_on", []),
        }
        _emit("subtask_started", f"Subtarea iniciada: {node_name}", node_payload)
        if node_status == "completed":
            _emit("subtask_completed", f"Subtarea completada: {node_name}",
                  node_payload)
        elif node_status == "failed":
            _emit("subtask_failed", f"Subtarea fallida: {node_name}",
                  node_payload)
        else:
            _emit("subtask_pending",
                  f"Subtarea pendiente: {node_name} ({node_status})",
                  node_payload)

    if result.get("success"):
        _emit("task_completed",
              f"Orquestación completada: {result.get('subtasks_executed', 0)}/"
              f"{result.get('subtasks_planned', 0)} subtareas ejecutadas",
              {"tokens_used": metrics.get("tokens_used", 0),
               "latency_ms": metrics.get("latency_ms", 0)})
    else:
        _emit("task_failed",
              result.get("error_message") or "Orquestación fallida sin mensaje",
              {"phase_reached": phase})

    for warning in result.get("warnings", []):
        _emit("warning_issued", f"Advertencia: {warning}")

    return events


# ---------------------------------------------------------------------------
# Estilos CSS: identidad HPR + layout dual
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
        /* --- Variables de identidad HPR --- */
        :root {
            --hpr-primary: #1e3a5f;
            --hpr-secondary: #2c5f8a;
            --hpr-accent: #e87d38;
            --hpr-accent-2: #4a9fd1;
            --hpr-background: #f0f4f8;
            --hpr-card: #ffffff;
            --hpr-text: #1a2a3a;
            --hpr-text-muted: #5a7a8a;
            --hpr-success: #28a745;
            --hpr-error: #dc3545;
            --hpr-warning: #ffc107;
        }

        .stApp {
            background: var(--hpr-background);
            font-family: "Segoe UI", Tahoma, Verdana, sans-serif;
        }

        /* --- Encabezado dual --- */
        .hpr-header {
            background: linear-gradient(135deg, var(--hpr-primary), var(--hpr-secondary));
            color: #ffffff;
            padding: 0.75rem 1.25rem;
            border-radius: 0 0 12px 12px;
            margin: -1rem -1rem 1rem -1rem;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }
        .hpr-header h1 {
            margin: 0;
            font-size: 1.35rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        .hpr-header p {
            margin: 0.15rem 0 0;
            font-size: 0.8125rem;
            opacity: 0.9;
        }

        /* --- Contenedor de chat (Pestaña 1) --- */
        .hpr-chat-container {
            background: var(--hpr-card);
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 0.75rem;
            min-height: 320px;
            max-height: 60vh;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 0.6rem;
            justify-content: flex-start;
        }

        /* Mensajes */
        .hpr-message {
            display: flex;
            flex-direction: column;
            gap: 0.2rem;
            max-width: 88%;
        }
        .hpr-message.user { align-self: flex-end; }
        .hpr-message.assistant { align-self: flex-start; }

        .hpr-message .avatar {
            width: 30px;
            height: 30px;
            border-radius: 50%;
            font-weight: bold;
            font-size: 0.8125rem;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 0.2rem;
        }
        .hpr-message.user .avatar {
            background: var(--hpr-primary);
            color: #fff;
            align-self: flex-end;
        }
        .hpr-message.assistant .avatar {
            background: var(--hpr-accent);
            color: #fff;
            align-self: flex-start;
        }

        .hpr-message .text {
            background: var(--hpr-card);
            border: 1px solid #dfe6e9;
            border-radius: 10px;
            padding: 0.65rem 0.9rem;
            line-height: 1.4;
            word-wrap: break-word;
            white-space: pre-wrap;
        }
        .hpr-message.user .text {
            background: var(--hpr-primary);
            color: #fff;
            margin-left: 36px;
        }
        .hpr-message.assistant .text {
            background: #f8fafc;
            margin-right: 36px;
        }

        /* --- Barra de entrada fija inferior (Pestaña 1) --- */
        .hpr-input-dock {
            position: sticky;
            bottom: 0;
            background: var(--hpr-card);
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 0.6rem 0.75rem;
            margin-top: 0.75rem;
            box-shadow: 0 -2px 8px rgba(0,0,0,0.06);
        }
        .hpr-input-row {
            display: flex;
            gap: 0.5rem;
            align-items: center;
        }
        .hpr-input-row input[type="text"] {
            flex: 1;
            border: 1px solid #a0aec0;
            border-radius: 8px;
            padding: 0.45rem 0.7rem;
            font-size: 0.9375rem;
        }
        .hpr-input-row input[type="text"]:focus {
            border-color: var(--hpr-primary);
            outline: none;
        }
        .hpr-voice-btn {
            border: none;
            border-radius: 8px;
            width: 40px;
            height: 40px;
            background: var(--hpr-accent);
            color: #fff;
            font-size: 1.1rem;
            cursor: pointer;
            transition: background 0.2s, transform 0.1s;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .hpr-voice-btn:hover { background: #d46a28; }
        .hpr-voice-btn:active { transform: scale(0.95); }
        .hpr-voice-btn.listening {
            background: var(--hpr-error);
            animation: pulse 1.2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .hpr-send-btn {
            border: none;
            border-radius: 8px;
            padding: 0 1.1rem;
            height: 40px;
            background: var(--hpr-primary);
            color: #fff;
            font-weight: 500;
            font-size: 0.9375rem;
            cursor: pointer;
            transition: background 0.2s;
        }
        .hpr-send-btn:hover { background: var(--hpr-secondary); }

        /* --- Pestaña 2: Motor Técnico --- */
        .hpr-tech-header {
            background: linear-gradient(135deg, #2d3748, #4a5568);
            color: #fff;
            padding: 0.6rem 1rem;
            border-radius: 8px;
            margin-bottom: 0.75rem;
        }
        .hpr-tech-header h3 {
            margin: 0;
            font-size: 1.05rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        .hpr-command-bar {
            background: var(--hpr-card);
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            padding: 0.6rem 0.75rem;
            margin-bottom: 0.75rem;
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
            align-items: center;
        }
        .hpr-command-bar input[type="text"],
        .hpr-command-bar select {
            border: 1px solid #a0aec0;
            border-radius: 6px;
            padding: 0.35rem 0.6rem;
            font-size: 0.875rem;
        }
        .hpr-command-bar button {
            border: none;
            border-radius: 6px;
            padding: 0.4rem 0.9rem;
            background: var(--hpr-primary);
            color: #fff;
            font-size: 0.875rem;
            cursor: pointer;
        }
        .hpr-command-bar button:hover { background: var(--hpr-secondary); }

        /* DAG de subtareas */
        .hpr-dag-node {
            background: #f8fafc;
            border: 1px solid #cbd5e0;
            border-left: 4px solid var(--hpr-accent-2);
            border-radius: 8px;
            padding: 0.5rem 0.75rem;
            margin: 0.4rem 0;
            font-size: 0.8125rem;
        }
        .hpr-dag-node.completed { border-left-color: var(--hpr-success); }
        .hpr-dag-node.failed { border-left-color: var(--hpr-error); }
        .hpr-dag-node.running { border-left-color: var(--hpr-warning); }
        .hpr-dag-node .node-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.2rem;
        }
        .hpr-dag-node .node-name {
            font-weight: 600;
            color: var(--hpr-text);
        }
        .hpr-dag-node .node-type {
            background: var(--hpr-primary);
            color: #fff;
            padding: 0.1rem 0.4rem;
            border-radius: 4px;
            font-size: 0.6875rem;
            text-transform: uppercase;
        }
        .hpr-dag-node .node-deps {
            font-size: 0.6875rem;
            color: var(--hpr-text-muted);
            margin-top: 0.2rem;
        }

        /* Tarjetas de métricas */
        .hpr-metric-card {
            background: var(--hpr-card);
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            padding: 0.6rem 0.75rem;
            text-align: center;
        }
        .hpr-metric-card .metric-value {
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--hpr-primary);
        }
        .hpr-metric-card .metric-label {
            font-size: 0.75rem;
            color: var(--hpr-text-muted);
            text-transform: uppercase;
        }

        /* Código/JSON */
        .hpr-code-block {
            background: #1e293b;
            color: #e2e8f0;
            border-radius: 8px;
            padding: 0.6rem 0.75rem;
            font-family: "Consolas", "Monaco", monospace;
            font-size: 0.75rem;
            overflow-x: auto;
            white-space: pre-wrap;
            word-break: break-all;
        }

        /* Responsividad */
        @media (max-width: 768px) {
            .hpr-header { padding: 0.5rem; }
            .hpr-chat-container { min-height: 240px; max-height: 50vh; padding: 0.5rem; }
            .hpr-message .text { padding: 0.5rem; }
            .hpr-input-row { flex-wrap: wrap; }
            .hpr-input-row input[type="text"] { width: 100%; }
        }

        /* Scrollbar */
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #a0aec0; border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: #718096; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Encabezado de la aplicación
# ---------------------------------------------------------------------------
def _backend_status() -> Dict[str, Any]:
    """Sonda de salud cacheada (TTL 30 s) para el indicador del encabezado."""
    now = time.time()
    cached = st.session_state.get("backend_health")
    if cached and (now - cached.get("ts", 0.0)) < 30.0:
        return cached
    client = get_client(st.session_state.api_url)
    health = client.health_check()
    health["ts"] = now
    st.session_state.backend_health = health
    return health


_health = _backend_status()
if _health.get("ok"):
    _pill = (
        '<span style="background:rgba(40,167,69,0.25); color:#d4f5dd; '
        f'padding:0.15rem 0.6rem; border-radius:12px; font-size:0.75rem;">'
        f'● Backend en línea · {_health.get("latency_ms", 0):.0f} ms</span>'
    )
else:
    _pill = (
        '<span style="background:rgba(220,53,69,0.3); color:#ffd6da; '
        'padding:0.15rem 0.6rem; border-radius:12px; font-size:0.75rem;">'
        '● Backend fuera de línea</span>'
    )

st.markdown(
    f"""
    <div class="hpr-header">
        <h1><span style="font-size:1.2rem;">🛡️</span> Motor HPR — Interfaz Dual</h1>
        <p>Chat Autónomo / Natural &nbsp;·&nbsp; Motor Técnico / Manual &nbsp;·&nbsp; Identidad: HPR-CORE-DETERMINISTIC</p>
        <p style="margin-top:0.3rem;">{_pill}</p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# BARRA DE GESTIÓN DE SESIONES (Fase 3) — Barra superior
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="hpr-session-bar" style="
        background: var(--hpr-card);
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 0.5rem 0.75rem;
        margin-bottom: 0.75rem;
        display: flex;
        gap: 0.5rem;
        align-items: center;
        flex-wrap: wrap;
    ">
        <span style="font-size:0.8125rem; font-weight:600; color: var(--hpr-text);">🗂️ Sesiones:</span>
    </div>
    """,
    unsafe_allow_html=True,
)

sess_col1, sess_col2, sess_col3, sess_col4, sess_col5 = st.columns([2, 1, 1, 1, 1])

with sess_col1:
    # Selector de sesión activa (se sincroniza con backend)
    session_options = ["(nueva)"]
    try:
        client_tmp = get_client(st.session_state.api_url)
        sessions_list = client_tmp.list_sessions(limit=20)
        for s in sessions_list:
            sid = str(s.get("id", ""))[:8]
            title = s.get("title") or "Sin título"
            session_options.append(f"{sid}… — {title[:24]}")
    except Exception:
        pass

    selected_session = st.selectbox(
        "Sesión activa",
        options=session_options,
        index=0,
        label_visibility="collapsed",
        key="session_selector",
    )

with sess_col2:
    new_chat_session = st.button("🆕 Nueva", key="btn_new_session", use_container_width=True)
with sess_col3:
    refresh_sessions = st.button("🔄 Listar", key="btn_refresh_sessions", use_container_width=True)
with sess_col4:
    sync_context_btn = st.button("📡 Contexto", key="btn_sync_context", use_container_width=True)
with sess_col5:
    delete_session_btn = st.button("🗑️ Eliminar", key="btn_delete_session", use_container_width=True)

# --- Acciones de gestión de sesiones ---
if new_chat_session:
    st.session_state.active_session_id = None
    st.session_state.chat_history = []
    st.session_state.live_context = None
    st.info("Nueva sesión de chat creada. Se inicializará en el primer mensaje.")
    st.rerun()

if refresh_sessions:
    # Forzar relectura de sesiones
    st.rerun()

if sync_context_btn and st.session_state.active_session_id:
    client = get_client(st.session_state.api_url)
    ctx = client.get_session_context(st.session_state.active_session_id)
    if ctx:
        st.session_state.live_context = ctx
        st.success("Contexto sincronizado correctamente.")
    else:
        st.warning("No se pudo obtener el contexto de la sesión.")
    st.rerun()

if delete_session_btn and st.session_state.active_session_id:
    client = get_client(st.session_state.api_url)
    success = client.delete_session(st.session_state.active_session_id)
    if success:
        st.session_state.active_session_id = None
        st.session_state.chat_history = []
        st.session_state.live_context = None
        st.success("Sesión eliminada (archivada) correctamente.")
    else:
        st.error("No se pudo eliminar la sesión.")
    st.rerun()

# --- Selección manual de sesión existente ---
if selected_session and selected_session != "(nueva)":
    # Extraer el ID de la opción seleccionada (formato: "xxxxxxxx… — título")
    selected_id_full = selected_session.split("…")[0].strip()
    if selected_id_full and selected_id_full != st.session_state.active_session_id:
        # Buscar el ID completo en la lista de sesiones
        try:
            client_tmp = get_client(st.session_state.api_url)
            sessions_list = client_tmp.list_sessions(limit=20)
            for s in sessions_list:
                if str(s.get("id", "")).startswith(selected_id_full):
                    st.session_state.active_session_id = s.get("id")
                    # Cargar historial de la sesión seleccionada
                    full_session = client_tmp.get_session(st.session_state.active_session_id)
                    if full_session:
                        st.session_state.chat_history = []
                        for turn in full_session.get("turns", []):
                            role = "user" if turn.get("role") == "user" else "assistant"
                            st.session_state.chat_history.append({
                                "role": role,
                                "content": turn.get("content", ""),
                            })
                    st.session_state.live_context = None
                    st.rerun()
                    break
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Barra de estado / configuración (API URL)
# ---------------------------------------------------------------------------
with st.expander("⚙️ Configuración de conexión", expanded=False):
    api_url = st.text_input(
        "URL del backend FastAPI",
        value=st.session_state.api_url,
        help="Dirección del servidor FastAPI del motor HPR",
    )
    if st.button("Actualizar y verificar conexión"):
        st.session_state.api_url = api_url
        client = get_client(st.session_state.api_url)
        health = client.health_check()
        if health["ok"]:
            st.success(
                f"✅ Conexión exitosa con el backend HPR "
                f"({health['latency_ms']:.0f} ms)"
            )
        else:
            st.error("❌ No se pudo conectar al backend. Verifica que "
                     "FastAPI esté corriendo.")

    # Observabilidad por canal (Fase 4)
    client = get_client(st.session_state.api_url)
    with st.expander("📊 Estadísticas de canales de comunicación",
                     expanded=False):
        sc1, sc2, sc3 = st.columns(3)
        channel_meta = (
            ("autonomous", "💬 Canal Autónomo", "/api/v1/chat"),
            ("technical", "🔧 Canal Técnico", "/api/v1/orchestrate"),
            ("management", "🗂️ Gestión", "/api/v1/sessions"),
        )
        for col, (key, label, endpoint) in zip((sc1, sc2, sc3),
                                                 channel_meta):
            stats = client.stats[key]
            with col:
                st.markdown(f"**{label}**")
                st.markdown(
                    f"`{endpoint}`\n\n"
                    f"- Peticiones: **{stats.requests}**\n"
                    f"- Errores: **{stats.errors}** "
                    f"(timeouts: **{stats.timeouts}**)\n"
                    f"- Latencia media: **{stats.avg_latency_ms:.0f} ms**",
                )


# ---------------------------------------------------------------------------
# DOBLE PESTAÑA (Tabbed View)
# ---------------------------------------------------------------------------
tab_chat, tab_tech = st.tabs(["💬 Chat Autónomo / Natural", "🔧 Motor Técnico / Manual"])


# ===========================================================================
# PESTAÑA 1: CHAT AUTÓNOMO / NATURAL
# ===========================================================================
with tab_chat:
    st.markdown(
        """
        <div style="margin-bottom:0.5rem; color: var(--hpr-text-muted); font-size:0.8125rem;">
            Conversación fluida con memoria de sesión. Entrada fija inferior, flujo ascendente,
            voz integrada vía Web Speech API. El agente opera de forma autónoma sin comandos forzados.
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --- Estado de sesión ---
    col_info1, col_info2, col_info3, col_info4 = st.columns(4)
    with col_info1:
        st.markdown(
            f'<div class="hpr-metric-card"><div class="metric-label">Sesión</div>'
            f'<div class="metric-value" style="font-size:0.9rem;">'
            f'{(st.session_state.active_session_id or "nueva")[:8]}…</div></div>',
            unsafe_allow_html=True,
        )
    with col_info2:
        turnos = sum(1 for m in st.session_state.chat_history if m["role"] == "user")
        st.markdown(
            f'<div class="hpr-metric-card"><div class="metric-label">Turnos</div>'
            f'<div class="metric-value">{turnos}</div></div>',
            unsafe_allow_html=True,
        )
    with col_info3:
        st.markdown(
            f'<div class="hpr-metric-card"><div class="metric-label">Voz</div>'
            f'<div class="metric-value" style="font-size:0.9rem;">'
            f'{"ON" if st.session_state.voice_active else "OFF"}</div></div>',
            unsafe_allow_html=True,
        )
    with col_info4:
        last_latency = st.session_state.get("last_chat_latency_ms")
        latency_text = "—" if last_latency is None else f"{last_latency:.0f} ms"
        st.markdown(
            f'<div class="hpr-metric-card"><div class="metric-label">Últ. turno</div>'
            f'<div class="metric-value" style="font-size:0.9rem;">{latency_text}</div></div>',
            unsafe_allow_html=True,
        )

    # --- Panel de Contexto en Tiempo Real (Fase 3) ---
    # Sincronización automática del contexto de sesión para reflejar
    # temas activos, ambigüedades detectadas y referencias pendientes.
    if st.session_state.active_session_id:
        client = get_client(st.session_state.api_url)
        ctx = client.get_session_context(st.session_state.active_session_id)
        if ctx:
            st.session_state.live_context = ctx
            st.session_state.last_context_sync = time.strftime("%H:%M:%S")

    if st.session_state.live_context:
        ctx = st.session_state.live_context
        with st.expander("📡 Contexto de Sesión en Tiempo Real", expanded=False):
            # Temas activos
            active_topics = ctx.get("active_topics", [])
            if active_topics:
                st.markdown("**🏷️ Temas activos:**")
                topics_str = " · ".join(active_topics[:8])
                st.markdown(
                    f'<div style="background:#f0f4f8; border-radius:6px; padding:0.4rem 0.6rem; '
                    f'font-size:0.8125rem; margin-bottom:0.4rem;">{topics_str}</div>',
                    unsafe_allow_html=True,
                )

            # Ambigüedades detectadas
            ambiguities = ctx.get("unresolved_ambiguities", [])
            if ambiguities:
                st.markdown("**⚠️ Ambigüedades detectadas:**")
                for amb in ambiguities[:5]:
                    st.markdown(f"• {amb}")

            # Referencias pendientes
            pending_refs = ctx.get("pending_references", [])
            pending_count = ctx.get("pending_references_count", len(pending_refs))
            if pending_count > 0:
                st.markdown(f"**🔗 Referencias pendientes:** `{pending_count}`")
                for ref in pending_refs[:3]:
                    ref_text = ref.get("reference_text", "")
                    ref_conf = ref.get("confidence", 0)
                    st.markdown(f"• _{ref_text}_ (confianza: {ref_conf:.0%})")
            else:
                st.markdown("**🔗 Referencias pendientes:** `0` — todas resueltas ✅")

            # Meta de sincronización
            sync_ts = st.session_state.last_context_sync or "N/A"
            st.markdown(
                f'<div style="font-size:0.6875rem; color: var(--hpr-text-muted); '
                f'margin-top:0.4rem;">Última sincronización: {sync_ts}</div>',
                unsafe_allow_html=True,
            )

    # --- Contenedor de mensajes (flujo ascendente) ---
    st.markdown('<div class="hpr-chat-container" id="chat-container">', unsafe_allow_html=True)

    if not st.session_state.chat_history:
        st.markdown(
            """
            <div class="hpr-message assistant">
                <div class="avatar">H</div>
                <div class="text">Hola 👋 Soy el agente HPR. Puedes conversar conmigo de forma natural,
                escribir o usar el micrófono 🎤 para dictar tu consulta. La memoria de sesión se mantiene
                automáticamente.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        avatars = {"user": "T", "assistant": "H"}
        for msg in st.session_state.chat_history:
            role = msg["role"]
            content = html.escape(str(msg["content"]))
            avatar = avatars.get(role, "?")
            st.markdown(
                f"""
                <div class="hpr-message {role}">
                    <div class="avatar">{avatar}</div>
                    <div class="text">{content}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown('</div>', unsafe_allow_html=True)

    # --- Auto-scroll al final (mensajes crecen de abajo hacia arriba) ---
    st.markdown(
        """
        <script>
            setTimeout(() => {
                const chat = window.parent.document.getElementById('chat-container');
                if (chat) { chat.scrollTop = chat.scrollHeight; }
            }, 120);
        </script>
        """,
        unsafe_allow_html=True,
    )

    # --- Dock de entrada fija inferior con micrófono ---
    st.markdown(
        """
        <div class="hpr-input-dock">
            <div class="hpr-input-row">
                <button class="hpr-voice-btn" id="voice-btn" title="Dictar con voz">🎤</button>
                <input type="text" id="chat-text-input" placeholder="Escribe o dicta tu consulta... (Enter para enviar)"
                       onkeypress="if(event.key==='Enter') document.querySelector('.hpr-send-btn').click()" />
                <button class="hpr-send-btn" title="Enviar mensaje">Enviar</button>
            </div>
            <div id="voice-status" style="font-size:0.6875rem; color: var(--hpr-text-muted); margin-top:0.3rem; display:none;">
                🎤 Escuchando... habla ahora
            </div>
        </div>

        <script>
        // --- Web Speech API: reconocimiento de voz en tiempo real ---
        (function() {
            const voiceBtn = document.getElementById('voice-btn');
            const textInput = document.getElementById('chat-text-input');
            const voiceStatus = document.getElementById('voice-status');
            if (!voiceBtn || !textInput) return;

            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            let recognition = null;
            let isListening = false;

            if (SpeechRecognition) {
                recognition = new SpeechRecognition();
                recognition.continuous = false;
                recognition.interimResults = true;
                recognition.lang = 'es-ES';

                recognition.onstart = function() {
                    isListening = true;
                    voiceBtn.classList.add('listening');
                    if (voiceStatus) voiceStatus.style.display = 'block';
                };

                recognition.onresult = function(event) {
                    let interimTranscript = '';
                    let finalTranscript = '';
                    for (let i = event.resultIndex; i < event.results.length; i++) {
                        const transcript = event.results[i][0].transcript;
                        if (event.results[i].isFinal) {
                            finalTranscript += transcript;
                        } else {
                            interimTranscript += transcript;
                        }
                    }
                    if (finalTranscript) {
                        textInput.value = finalTranscript;
                        voiceStatus.style.display = 'none';
                    } else if (interimTranscript) {
                        textInput.value = interimTranscript;
                    }
                };

                recognition.onerror = function(event) {
                    console.warn('Speech recognition error:', event.error);
                    isListening = false;
                    voiceBtn.classList.remove('listening');
                    if (voiceStatus) voiceStatus.style.display = 'none';
                };

                recognition.onend = function() {
                    isListening = false;
                    voiceBtn.classList.remove('listening');
                    if (voiceStatus) voiceStatus.style.display = 'none';
                };

                voiceBtn.addEventListener('click', function() {
                    if (isListening) {
                        recognition.stop();
                    } else {
                        try {
                            recognition.start();
                        } catch (e) {
                            console.warn('Could not start recognition:', e);
                        }
                    }
                });
            } else {
                voiceBtn.style.display = 'none';
                if (voiceStatus) {
                    voiceStatus.style.display = 'block';
                    voiceStatus.textContent = '⚠️ Web Speech API no soportada en este navegador';
                }
            }
        })();
        </script>
        """,
        unsafe_allow_html=True,
    )

    # --- Entrada de chat de Streamlit (captura real del mensaje) ---
    prompt = st.chat_input("Escribe o dicta tu consulta...")

    if prompt:
        client = get_client(st.session_state.api_url)
        use_voice = st.session_state.voice_active
        language = "es"  # detectado del input de voz; puede extenderse

        with st.spinner("Procesando..."):
            try:
                result = client.chat(
                    session_id=st.session_state.active_session_id,
                    message=prompt,
                    use_voice=use_voice,
                    language=language,
                )
                st.session_state.active_session_id = result.get("session_id")
                assistant_text = result.get("response", "Sin respuesta")
                # Fase 4: latencia del turno en el Canal Autónomo
                st.session_state.last_chat_latency_ms = \
                    client.last_latency_ms.get("autonomous")

                st.session_state.chat_history.append({"role": "user", "content": prompt})
                st.session_state.chat_history.append({"role": "assistant", "content": assistant_text})

                # Fase 3: actualizar contexto en vivo desde la respuesta del chat
                resp_ctx = result.get("session_context")
                if resp_ctx:
                    st.session_state.live_context = resp_ctx
                    st.session_state.last_context_sync = time.strftime("%H:%M:%S")

                st.rerun()
            except HPRTimeoutError:
                st.error("⏱️ Tiempo de espera agotado en el Canal Autónomo. "
                         "El backend no respondió a tiempo.")
            except HPRConnectionError:
                st.error("🔌 No se pudo conectar al backend. Verifica que "
                         "FastAPI esté corriendo en "
                         f"`{st.session_state.api_url}`.")
            except HPRHTTPError as e:
                st.error(f"❌ Error HTTP del backend: {e}")
            except HPRCommunicationError as e:
                st.error(f"❌ Error de comunicación (canal "
                         f"'{e.channel}'): {e}")
            except Exception as e:
                st.error(f"❌ Error inesperado: {e}")


# ===========================================================================
# PESTAÑA 2: MOTOR TÉCNICO / MANUAL
# ===========================================================================
with tab_tech:
    st.markdown(
        """
        <div class="hpr-tech-header">
            <h3>🔧 Motor Técnico / Manual — Auditoría y Control de DAGs</h3>
        </div>
        <div style="margin-bottom:0.5rem; color: var(--hpr-text-muted); font-size:0.8125rem;">
            Control manual de triggers, descomposición de intenciones, visualización de DAGs de
            dependencias, autorizaciones y auditoría de ingeniería. Endpoint: <code>POST /api/v1/orchestrate</code>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --- Barra de comandos superior ---
    st.markdown('<div class="hpr-command-bar">', unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
    with col1:
        intent_summary = st.text_input(
            "📝 Resumen de intención",
            value="Analizar documento técnico y extraer hallazgos verificables",
            key="tech_intent_summary",
        )
    with col2:
        intent_category = st.selectbox(
            "Categoría",
            ["analysis", "synthesis", "verification", "decision", "planning",
             "execution", "clarification", "monitoring"],
            index=0,
            key="tech_category",
        )
    with col3:
        intent_complexity = st.selectbox(
            "Complejidad",
            ["atomic", "simple", "moderate", "complex"],
            index=1,
            key="tech_complexity",
        )
    with col4:
        dry_run = st.checkbox("Dry run", value=True, key="tech_dry_run")

    col5, col6, col7 = st.columns(3)
    with col5:
        intent_priority = st.selectbox(
            "Prioridad",
            ["low", "normal", "high", "critical"],
            index=1,
            key="tech_priority",
        )
    with col6:
        constraints_input = st.text_input(
            "Restricciones (coma separada)",
            value="",
            key="tech_constraints",
        )
    with col7:
        criteria_input = st.text_input(
            "Criterios éxito (coma separada)",
            value="",
            key="tech_criteria",
        )

    st.markdown('</div>', unsafe_allow_html=True)

    # --- Botones de acción ---
    col_btn1, col_btn2, col_btn3, col_btn4 = st.columns(4)
    with col_btn1:
        run_orchestrate = st.button("▶️ Ejecutar Orquestación", use_container_width=True, type="primary")
    with col_btn2:
        new_session = st.button("🆕 Nueva Sesión Técnica", use_container_width=True)
    with col_btn3:
        refresh_ctx = st.button("🔄 Refrescar Contexto", use_container_width=True)
    with col_btn4:
        clear_history = st.button("🧹 Limpiar Historial", use_container_width=True)

    # --- Acciones de botones ---
    if new_session:
        st.session_state.tech_session_id = None
        st.session_state.orchestration_history = []
        st.info("Sesión técnica reseteada. Se creará una nueva al ejecutar la orquestación.")
        st.rerun()

    if clear_history:
        st.session_state.orchestration_history = []
        st.rerun()

    if refresh_ctx and st.session_state.tech_session_id:
        client = get_client(st.session_state.api_url)
        ctx = client.get_session_context(st.session_state.tech_session_id)
        if ctx:
            st.session_state.orchestration_history.append({
                "type": "context",
                "timestamp": time.strftime("%H:%M:%S"),
                "data": ctx,
            })
        st.rerun()

    # --- Ejecución de orquestación ---
    if run_orchestrate:
        if not intent_summary.strip():
            st.error("Debes proporcionar un resumen de intención.")
        else:
            client = get_client(st.session_state.api_url)

            # Asegurar sesión técnica
            if not st.session_state.tech_session_id:
                # Crear sesión vía chat con mensaje inicial
                try:
                    chat_result = client.chat(
                        session_id=None,
                        message=f"[TÉCNICO] {intent_summary}",
                    )
                    st.session_state.tech_session_id = chat_result.get("session_id")
                except HPRCommunicationError:
                    # Si falla, generar un UUID local (el backend lo validará)
                    st.session_state.tech_session_id = str(uuid.uuid4())

            constraints = [c.strip() for c in constraints_input.split(",") if c.strip()]
            criteria = [c.strip() for c in criteria_input.split(",") if c.strip()]

            with st.spinner("Ejecutando orquestación técnica..."):
                try:
                    orch_result = client.orchestrate(
                        session_id=st.session_state.tech_session_id,
                        intent_summary=intent_summary,
                        intent_category=intent_category,
                        intent_complexity=intent_complexity,
                        intent_priority=intent_priority,
                        constraints=constraints,
                        success_criteria=criteria,
                        dry_run=dry_run,
                    )
                    st.session_state.orchestration_history.append({
                        "type": "orchestration",
                        "timestamp": time.strftime("%H:%M:%S"),
                        "data": orch_result,
                    })
                    st.rerun()
                except HPRContractError as e:
                    # Violación de contrato detectada localmente (sin round-trip)
                    st.error(f"📜 Violación de contrato Pydantic: {e}")
                except HPRTimeoutError:
                    st.error("⏱️ Tiempo de espera agotado en el Canal "
                             "Técnico (la orquestación puede requerir "
                             "más tiempo de lectura).")
                except HPRConnectionError:
                    st.error("🔌 No se pudo conectar al backend.")
                except HPRHTTPError as e:
                    st.error(f"❌ Error HTTP: {e}")
                except HPRCommunicationError as e:
                    st.error(f"❌ Error de comunicación (canal "
                             f"'{e.channel}'): {e}")
                except Exception as e:
                    st.error(f"❌ Error inesperado: {e}")

    # --- Panel de resultados en cascada ---
    if st.session_state.orchestration_history:
        st.markdown("---")
        st.markdown("#### 📊 Resultados de Orquestación (cascada descendente)")

        for entry in reversed(st.session_state.orchestration_history):
            entry_type = entry.get("type", "unknown")
            ts = entry.get("timestamp", "")
            data = entry.get("data", {})

            if entry_type == "orchestration":
                success = data.get("success", False)
                phase = data.get("phase_reached", "unknown")
                planned = data.get("subtasks_planned", 0)
                executed = data.get("subtasks_executed", 0)
                task_id = data.get("task_id")
                warnings = data.get("warnings", [])
                error_msg = data.get("error_message")
                dag = data.get("dag_structure")
                metrics = data.get("metrics", {})

                status_icon = "✅" if success else "❌"
                with st.container():
                    st.markdown(
                        f"**{status_icon} Orquestación** — `{ts}` — "
                        f"Tarea: `{str(task_id)[:8] if task_id else 'N/A'}…` — "
                        f"Fase: **{phase}** — Subtareas: **{planned} planificadas / {executed} ejecutadas**"
                    )

                    # Métricas (presupuesto de tokens, latencia y progreso)
                    if metrics:
                        mc1, mc2, mc3, mc4 = st.columns(4)
                        with mc1:
                            st.markdown(
                                f'<div class="hpr-metric-card"><div class="metric-label">Tokens</div>'
                                f'<div class="metric-value">{metrics.get("tokens_used", 0)}</div></div>',
                                unsafe_allow_html=True,
                            )
                        with mc2:
                            st.markdown(
                                f'<div class="hpr-metric-card"><div class="metric-label">Latencia (ms)</div>'
                                f'<div class="metric-value">{metrics.get("latency_ms", 0)}</div></div>',
                                unsafe_allow_html=True,
                            )
                        with mc3:
                            started = metrics.get("started_at", "")
                            st.markdown(
                                f'<div class="hpr-metric-card"><div class="metric-label">Inicio</div>'
                                f'<div class="metric-value" style="font-size:0.75rem;">{str(started)[:19] if started else "N/A"}</div></div>',
                                unsafe_allow_html=True,
                            )
                        with mc4:
                            planned = data.get("subtasks_planned", 0)
                            executed = data.get("subtasks_executed", 0)
                            progress_pct = (
                                f"{(executed / planned * 100):.0f}%"
                                if planned > 0 else "0%"
                            )
                            st.markdown(
                                f'<div class="hpr-metric-card"><div class="metric-label">Progreso</div>'
                                f'<div class="metric-value" style="font-size:1rem;">{executed}/{planned}</div>'
                                f'<div class="metric-label">{progress_pct}</div></div>',
                                unsafe_allow_html=True,
                            )

                    # DAG de subtareas (inspección detallada)
                    if dag:
                        st.markdown("**🌐 DAG de Dependencias:**")
                        node_icons = {
                            "completed": "✅", "failed": "❌",
                            "running": "🔄", "pending": "⏳",
                            "scheduled": "📅", "waiting": "⏸️",
                        }
                        for node in dag:
                            node_status = node.get("status", "pending")
                            status_class = "running" if node_status == "running" else (
                                "completed" if node_status == "completed" else (
                                    "failed" if node_status == "failed" else ""
                                )
                            )
                            deps = node.get("depends_on", [])
                            deps_str = ", ".join([str(d)[:8] for d in deps]) if deps else "— (raíz)"
                            node_icon = node_icons.get(node_status, "⏳")
                            node_name = html.escape(str(node.get("name", "Sin nombre")))
                            node_desc = html.escape(str(node.get("description", "")))
                            node_id = str(node.get("id", ""))[:8]
                            st.markdown(
                                f"""
                                <div class="hpr-dag-node {status_class}">
                                    <div class="node-header">
                                        <span class="node-name">{node_icon} {node_name} <code style="font-size:0.625rem; color:var(--hpr-text-muted);">#{node_id}</code></span>
                                        <span class="node-type">{node.get('type', 'unknown')}</span>
                                    </div>
                                    <div>{node_desc}</div>
                                    <div class="node-deps">Dependencias: {deps_str} · Estado: <strong>{node_status}</strong></div>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )

                    # Eventos de orquestación (traza reconstruida, Fase 4)
                    orch_events = build_orchestration_events(data)
                    with st.expander("📡 Eventos de Orquestación (traza en tiempo real)",
                                     expanded=False):
                        event_icons = {
                            "intent_received": "📥",
                            "decomposition_started": "🔨",
                            "decomposition_completed": "🧩",
                            "planning_started": "📋",
                            "planning_completed": "📋",
                            "task_started": "🚀",
                            "subtask_started": "▶️",
                            "subtask_completed": "✅",
                            "subtask_failed": "❌",
                            "subtask_pending": "⏳",
                            "task_completed": "🏁",
                            "task_failed": "💥",
                            "warning_issued": "⚠️",
                        }
                        for ev in orch_events:
                            icon = event_icons.get(ev["event_type"], "•")
                            ev_ts = str(ev.get("timestamp", ""))[:19]
                            ev_type = html.escape(str(ev.get("event_type", "")))
                            ev_msg = html.escape(str(ev.get("message", "")))
                            st.markdown(
                                f'<div style="font-size:0.8125rem; '
                                f'padding:0.3rem 0; '
                                f'border-bottom:1px dashed #e2e8f0;">'
                                f'<strong>{icon} <code>{ev_type}</code></strong> '
                                f'<span style="color:var(--hpr-text-muted); '
                                f'font-size:0.6875rem;">{ev_ts}</span><br/>'
                                f'{ev_msg}</div>',
                                unsafe_allow_html=True,
                            )

                    # Warnings y errores
                    if warnings:
                        for w in warnings:
                            st.warning(f"⚠️ {w}")
                    if error_msg:
                        st.error(f"❌ {error_msg}")

                    # Resultado final (JSON)
                    final_result = data.get("final_result")
                    if final_result:
                        st.markdown("**📦 Resultado Final (JSON):**")
                        st.markdown(
                            f'<div class="hpr-code-block">{html.escape(json.dumps(final_result, ensure_ascii=False, indent=2))}</div>',
                            unsafe_allow_html=True,
                        )

                    st.markdown("---")

            elif entry_type == "context":
                st.markdown(f"**🔄 Contexto de Sesión** — `{ts}`")
                st.markdown(
                    f'<div class="hpr-code-block">{html.escape(json.dumps(data, ensure_ascii=False, indent=2))}</div>',
                    unsafe_allow_html=True,
                )
                st.markdown("---")

    else:
        st.markdown(
            """
            <div style="text-align:center; padding:2rem; color: var(--hpr-text-muted);">
                <p>🔧 No hay resultados de orquestación todavía.</p>
                <p>Configura la intención en la barra de comandos superior y pulsa
                <strong>▶️ Ejecutar Orquestación</strong>.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div style="text-align:center; padding:1rem 0 0.5rem; color: var(--hpr-text-muted); font-size:0.75rem;">
        Motor HPR — Arquitectura Híbrida · Determinista · Auditable · Soberano
    </div>
    """,
    unsafe_allow_html=True,
)
