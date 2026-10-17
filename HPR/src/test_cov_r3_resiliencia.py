"""Cobertura R3 (P5.4) — Resiliencia, excepciones, backoff y fallbacks honestos.

Cierra las brechas residuales de la ruta R3 (Constitución HPR) SIN tocar ``src/``:

- ``src/main.py`` · ``RetryConfig.calculate_delay`` y el decorador ``with_retry``.
- ``src/main.py`` · ``LocalFallback`` (chat y trigger).
- ``src/main.py`` · guardas defensivas del chat (turnos no creados, pipeline no-dict,
  error del motor de razonamiento) y sus bucles de reintento/fallback.
- ``src/main.py`` · bucle de reintentos/fallback del trigger.
- ``src/main.py`` · endpoints de telemetría, sesiones y logs/integridad.
- ``src/main.py`` · ``_infer_confidence_level``.

Reglas aplicadas (Constitución HPR):
- P3: determinismo estricto — **ningún** ``time.sleep`` real (se sustituye el reloj
  por un doble que registra los backoff), jitter fijado con ``random.random``
  controlado, cero red y cero azar en las aserciones.
- P4: se atacan los caminos de fallo (4xx no reintentable, 5xx reintentable,
  excepción inesperada, motor caído, límites de sesión).
- P7: no mutan — el registro de ejecución se neutraliza para no escribir en la
  bóveda durante las pruebas de trigger.
"""

import asyncio
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

# Convención del proyecto (ver run.py y test_etapa_d.py): HPR/ y HPR/src/ en path.
_HPR_DIR = Path(__file__).resolve().parent.parent
_SRC_DIR = _HPR_DIR / "src"
for _path in (str(_HPR_DIR), str(_SRC_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from src.main import (  # noqa: E402
    LocalFallback,
    RetryConfig,
    _infer_confidence_level,
    app,
    get_session_manager,
    with_retry,
)

#: UUID válido que garantizadamente no existe en el gestor de sesiones.
_UUID_INEXISTENTE = "00000000-0000-0000-0000-000000000000"


# ===========================================================================
# Dobles y utilidades de prueba (sin red, sin reloj real, sin azar)
# ===========================================================================

class _RelojFalso:
    """Reloj controlado: registra los backoff en lugar de dormir el proceso."""

    def __init__(self) -> None:
        self.dormido: list[float] = []

    def sleep(self, segundos: float) -> None:
        self.dormido.append(segundos)

    def time(self) -> float:
        return 0.0


class _MotorSeguridadDoble:
    """Doble del motor de seguridad: simula fallos de API externa (sin red)."""

    def __init__(self, comportamiento) -> None:
        self._comportamiento = comportamiento

    def process_pipeline(self, payload, state, truth):
        return self._comportamiento()


class _ContextoFalso:
    """Contexto de sesión mínimo para ``_infer_confidence_level``."""

    def __init__(self, turnos: int = 1, temas=None) -> None:
        self.current_turn_number = turnos
        self.active_topics = list(temas or [])


class _ContextoQueFalla:
    """Contexto corrupto: fuerza la rama de excepción de la heurística."""

    @property
    def current_turn_number(self):
        raise RuntimeError("contexto corrupto")


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Cliente en proceso (sin red real)."""
    return TestClient(app)


@pytest.fixture
def reloj(monkeypatch) -> _RelojFalso:
    """Intercepta ``time.sleep`` para que ningún backoff duerma el proceso (P3).

    Se parchea el ``sleep`` del módulo ``time`` y no la referencia de ``src.main``
    porque ``execute_trigger_endpoint`` hace ``import time`` local (main.py:1338),
    lo que crea un enlace propio que un parche a ``src.main.time`` no alcanzaría.
    """
    falso = _RelojFalso()
    monkeypatch.setattr("time.sleep", falso.sleep)
    return falso


@pytest.fixture
def motor_seguridad(monkeypatch):
    """Instala un motor de seguridad doble en ``src.main``."""
    def _instalar(comportamiento) -> None:
        monkeypatch.setattr(
            "src.main.get_security_engine", lambda: _MotorSeguridadDoble(comportamiento)
        )

    return _instalar


@pytest.fixture
def sin_log(monkeypatch) -> None:
    """Neutraliza el registro de ejecución para no escribir en la bóveda (P7)."""
    monkeypatch.setattr("src.main.log_execution", lambda **kwargs: None)


def _crear_sesion(client: TestClient, mensaje: str = "hola") -> str:
    """Crea una sesión real vía el endpoint de chat y devuelve su id."""
    respuesta = client.post("/api/v1/chat", json={"message": mensaje})
    assert respuesta.status_code == 200
    return respuesta.json()["session_id"]


# ===========================================================================
# A · RetryConfig.calculate_delay (backoff exponencial + jitter)
# ===========================================================================

def test_calculate_delay_sin_jitter_y_con_tope() -> None:
    """Backoff exponencial determinista, recortado por ``max_delay``."""
    config = RetryConfig(base_delay=1.0, exponential_base=2.0, max_delay=30.0, jitter=False)
    assert config.calculate_delay(0) == 1.0
    assert config.calculate_delay(1) == 2.0
    assert config.calculate_delay(4) == 16.0
    assert config.calculate_delay(5) == 30.0  # tope alcanzado


def test_calculate_delay_con_jitter_es_controlable(monkeypatch) -> None:
    """El jitter ±25% se fija inyectando ``random.random`` (determinista)."""
    config = RetryConfig(base_delay=2.0, exponential_base=2.0, max_delay=30.0, jitter=True)

    monkeypatch.setattr("src.main.random.random", lambda: 0.0)
    assert config.calculate_delay(0) == pytest.approx(1.5)  # 2 * 0.75

    monkeypatch.setattr("src.main.random.random", lambda: 0.5)
    assert config.calculate_delay(0) == pytest.approx(2.0)  # 2 * 1.0

    monkeypatch.setattr("src.main.random.random", lambda: 1.0 - 1e-9)
    assert config.calculate_delay(1) == pytest.approx(4.0 * 1.25, rel=1e-6)


# ===========================================================================
# B · with_retry (decorador de reintentos)
# ===========================================================================

def test_with_retry_exito_primer_intento(reloj: _RelojFalso) -> None:
    """Si la función no falla, no hay espera ni reintento."""
    llamadas = []

    @with_retry(RetryConfig(max_attempts=3, base_delay=0.0, jitter=False))
    async def _operacion():
        llamadas.append(1)
        return "resultado"

    assert asyncio.run(_operacion()) == "resultado"
    assert len(llamadas) == 1
    assert reloj.dormido == []


def test_with_retry_reintenta_y_logra(reloj: _RelojFalso) -> None:
    """Un fallo transitorio se reintenta y termina en éxito."""
    intentos = []

    @with_retry(RetryConfig(max_attempts=3, base_delay=0.0, jitter=False))
    async def _falla_una_vez():
        intentos.append(1)
        if len(intentos) < 2:
            raise RuntimeError("fallo transitorio")
        return "recuperado"

    assert asyncio.run(_falla_una_vez()) == "recuperado"
    assert len(intentos) == 2
    assert len(reloj.dormido) == 1  # esperó entre intentos


def test_with_retry_http_no_reintentable_se_re_lanza(reloj: _RelojFalso) -> None:
    """Un 4xx (no 429) no se reintenta: se propaga de inmediato."""
    intentos = []

    @with_retry(RetryConfig(max_attempts=3, base_delay=0.0, jitter=False))
    async def _error_de_cliente():
        intentos.append(1)
        raise HTTPException(status_code=400, detail="petición inválida")

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(_error_de_cliente())
    assert excinfo.value.status_code == 400
    assert len(intentos) == 1
    assert reloj.dormido == []


def test_with_retry_http_reintentable_agota_y_re_lanza_ultimo(reloj: _RelojFalso) -> None:
    """Un 5xx se reintenta y, agotado, re-lanza la última HTTPException."""
    intentos = []

    @with_retry(RetryConfig(max_attempts=3, base_delay=0.0, jitter=False))
    async def _servicio_caido():
        intentos.append(1)
        raise HTTPException(status_code=503, detail="servicio caído")

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(_servicio_caido())
    assert excinfo.value.status_code == 503
    assert len(intentos) == 3
    assert len(reloj.dormido) == 2  # solo entre intentos, no tras el último


def test_with_retry_excepcion_generica_agota_y_da_503(reloj: _RelojFalso) -> None:
    """Una excepción inesperada se envuelve en 503 tras agotar reintentos."""
    @with_retry(RetryConfig(max_attempts=2, base_delay=0.0, jitter=False))
    async def _red_caida():
        raise RuntimeError("red caída")

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(_red_caida())
    assert excinfo.value.status_code == 503
    assert "tras 2 reintentos" in excinfo.value.detail
    assert len(reloj.dormido) == 1


# ===========================================================================
# C · LocalFallback (respuestas honestas sin API externa)
# ===========================================================================

@pytest.mark.parametrize(
    "mensaje, fragmento",
    [
        ("hola", "modo local (fallback)"),
        ("gracias", "¡De nada!"),
        ("adiós", "Hasta luego"),
        ("quién eres", "Hybrid Predictive Reasoning"),
        ("consulta sin patrón reconocido", "Procesando en modo local"),
    ],
)
def test_chat_fallback_ramas(mensaje: str, fragmento: str) -> None:
    """Cada rama del fallback conversacional es honesta y local."""
    datos = LocalFallback.chat_fallback(mensaje)
    assert fragmento in datos["response"]
    assert datos["metadata"]["fallback"] is True
    assert datos["metadata"]["security_status"] == "local_fallback"
    assert datos["session_context"] is None


def test_chat_fallback_respeta_session_id() -> None:
    """Si se conoce la sesión, el fallback no inventa otra."""
    datos = LocalFallback.chat_fallback("hola", session_id="sesion-conocida")
    assert datos["session_id"] == "sesion-conocida"


def test_trigger_fallback_contrato() -> None:
    """El fallback de trigger declara el estado real, sin fingir éxito."""
    datos = LocalFallback.trigger_fallback("@web_search", 2)
    assert datos["estado"] == "fallback_local"
    assert datos["trigger"] == "@web_search"
    assert datos["nivel_confianza"] == 2


# ===========================================================================
# D · _infer_confidence_level (heurística con rama de excepción)
# ===========================================================================

def test_infer_confidence_nivel3_por_tema_sensible() -> None:
    """Un tema sensible en la sesión eleva el nivel a 3."""
    assert _infer_confidence_level(_ContextoFalso(1, ["seguridad"])) == 3


def test_infer_confidence_nivel3_por_muchos_turnos() -> None:
    """Más de 10 turnos eleva el nivel a 3."""
    assert _infer_confidence_level(_ContextoFalso(11, [])) == 3


def test_infer_confidence_nivel2() -> None:
    """Entre 4 y 10 turnos -> nivel 2."""
    assert _infer_confidence_level(_ContextoFalso(5, [])) == 2


def test_infer_confidence_nivel1() -> None:
    """Sesión nueva sin temas sensibles -> nivel 1."""
    assert _infer_confidence_level(_ContextoFalso(1, [])) == 1


def test_infer_confidence_ante_error_devuelve_1() -> None:
    """Contexto corrupto -> nivel 1 (degradación segura, nunca excepción)."""
    assert _infer_confidence_level(_ContextoQueFalla()) == 1


# ===========================================================================
# E · Endpoints de telemetría, sesiones y logs
# ===========================================================================

def test_telemetry_global(client: TestClient) -> None:
    """La telemetría global expone backend, componentes y estadísticas."""
    datos = client.get("/api/v1/telemetry").json()
    assert datos["backend"]["estado"] == "en línea"
    assert datos["componentes"]["nexus_root"] == "activo"
    assert "total_sessions" in datos["telemetria"]


def test_telemetry_con_sesion_valida(client: TestClient) -> None:
    """Con session_id válido se informa el nivel de confianza inferido."""
    session_id = _crear_sesion(client)
    datos = client.get("/api/v1/telemetry", params={"session_id": session_id}).json()
    assert datos["session_actual"] is not None
    assert datos["telemetria"]["confidence_level"] in (1, 2, 3)


def test_telemetry_session_id_invalido_no_rompe(client: TestClient) -> None:
    """Un session_id no-UUID no debe romper la telemetría."""
    respuesta = client.get("/api/v1/telemetry", params={"session_id": "no-es-uuid"})
    assert respuesta.status_code == 200
    assert respuesta.json()["session_actual"] is None
    assert respuesta.json()["telemetria"]["confidence_level"] is None


def test_get_session_existente(client: TestClient) -> None:
    """Recupera una sesión real por id."""
    session_id = _crear_sesion(client)
    respuesta = client.get(f"/api/v1/sessions/{session_id}")
    assert respuesta.status_code == 200
    assert respuesta.json()["id"] == session_id


def test_get_session_inexistente_da_404(client: TestClient) -> None:
    """Sesión desconocida -> 404 sanitizado."""
    respuesta = client.get(f"/api/v1/sessions/{_UUID_INEXISTENTE}")
    assert respuesta.status_code == 404


def test_get_session_context_existente(client: TestClient) -> None:
    """El contexto de una sesión real se expone al frontend."""
    session_id = _crear_sesion(client)
    respuesta = client.get(f"/api/v1/sessions/{session_id}/context")
    assert respuesta.status_code == 200
    assert "current_turn_number" in respuesta.json()


def test_get_session_context_inexistente_da_404(client: TestClient) -> None:
    """Contexto de sesión desconocida -> 404."""
    respuesta = client.get(f"/api/v1/sessions/{_UUID_INEXISTENTE}/context")
    assert respuesta.status_code == 404


def test_delete_session_existente(client: TestClient) -> None:
    """Eliminar (archivar) una sesión real la deja inaccesible."""
    session_id = _crear_sesion(client)
    respuesta = client.delete(f"/api/v1/sessions/{session_id}")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"status": "deleted", "session_id": session_id}
    assert client.get(f"/api/v1/sessions/{session_id}").status_code == 404


def test_delete_session_inexistente_da_404(client: TestClient) -> None:
    """Eliminar una sesión desconocida -> 404."""
    respuesta = client.delete(f"/api/v1/sessions/{_UUID_INEXISTENTE}")
    assert respuesta.status_code == 404


def test_list_sessions(client: TestClient) -> None:
    """El listado devuelve una colección de sesiones."""
    _crear_sesion(client)
    respuesta = client.get("/api/v1/sessions")
    assert respuesta.status_code == 200
    assert isinstance(respuesta.json(), list)


def test_list_sessions_status_valido(client: TestClient) -> None:
    """Un estado válido del enum se aplica como filtro."""
    respuesta = client.get("/api/v1/sessions", params={"status": "active"})
    assert respuesta.status_code == 200
    assert isinstance(respuesta.json(), list)


def test_list_sessions_status_invalido_se_ignora(client: TestClient) -> None:
    """Un estado fuera del enum se ignora sin romper el listado."""
    respuesta = client.get("/api/v1/sessions", params={"status": "no-existe"})
    assert respuesta.status_code == 200
    assert isinstance(respuesta.json(), list)


def test_logs_integrity_sin_directorio(client: TestClient, monkeypatch) -> None:
    """Despliegue sin bóveda de logs -> estado 'no_logs' honesto (no error)."""
    original = Path.exists

    def _exists(self) -> bool:
        if self.name == "logs" and "vitacoras" in str(self):
            return False
        return original(self)

    monkeypatch.setattr(Path, "exists", _exists)

    respuesta = client.get("/api/v1/logs/integrity")
    assert respuesta.status_code == 200
    assert respuesta.json()["status"] == "no_logs"


# ===========================================================================
# F · Guardas defensivas y bucles de reintento del chat
# ===========================================================================

def test_chat_pipeline_no_dict_se_normaliza(client: TestClient, motor_seguridad, reloj) -> None:
    """Guarda B3: un pipeline que no devuelve dict se normaliza (sin fallback)."""
    motor_seguridad(lambda: "texto plano del pipeline")

    datos = client.post("/api/v1/chat", json={"message": "hola"}).json()
    assert datos["response"]
    assert datos["metadata"]["fallback"] is False
    assert reloj.dormido == []


def test_chat_error_del_motor_usa_fallback(client: TestClient, motor_seguridad, reloj, monkeypatch) -> None:
    """Un fallo del motor de razonamiento agota reintentos y cae a fallback local."""
    motor_seguridad(lambda: {"estado": "activo"})

    def _motor_caido(*args, **kwargs):
        raise RuntimeError("API externa caída")

    monkeypatch.setattr("src.main._generate_contextual_response", _motor_caido)

    datos = client.post("/api/v1/chat", json={"message": "hola"}).json()
    assert datos["metadata"]["fallback"] is True
    assert datos["metadata"]["security_status"] == "local_fallback"
    assert len(reloj.dormido) == 2  # 3 intentos -> 2 esperas


def test_chat_http_no_reintentable_se_propaga(client: TestClient, motor_seguridad, reloj) -> None:
    """Un 4xx del pipeline no se reintenta: se propaga tal cual."""
    def _error_de_cliente():
        raise HTTPException(status_code=400, detail="petición inválida")

    motor_seguridad(_error_de_cliente)

    respuesta = client.post("/api/v1/chat", json={"message": "hola"})
    assert respuesta.status_code == 400
    assert reloj.dormido == []


def test_chat_excepcion_inesperada_usa_fallback(client: TestClient, motor_seguridad, reloj) -> None:
    """Una excepción inesperada del pipeline cae a fallback local honesto."""
    def _red_caida():
        raise RuntimeError("red caída")

    motor_seguridad(_red_caida)

    datos = client.post("/api/v1/chat", json={"message": "hola"}).json()
    assert datos["metadata"]["fallback"] is True
    assert datos["metadata"]["security_status"] == "local_fallback_error"
    assert len(reloj.dormido) == 2


def test_chat_limite_turnos_usuario(client: TestClient) -> None:
    """P4: sin cupo para el turno de usuario -> 500 explícito."""
    sesion = get_session_manager().create_session(initial_query="x", title="tope-usuario")
    sesion.max_turns = 0

    respuesta = client.post(
        "/api/v1/chat", json={"message": "hola", "session_id": str(sesion.id)}
    )
    assert respuesta.status_code == 500
    assert "turno de usuario" in respuesta.json()["detail"]


def test_chat_limite_turnos_asistente(client: TestClient) -> None:
    """P4: sin cupo para el turno de asistente -> 500 explícito."""
    sesion = get_session_manager().create_session(initial_query="x", title="tope-asistente")
    sesion.max_turns = 1

    respuesta = client.post(
        "/api/v1/chat", json={"message": "hola", "session_id": str(sesion.id)}
    )
    assert respuesta.status_code == 500
    assert "turno de asistente" in respuesta.json()["detail"]


# ===========================================================================
# G · Reintentos y fallback honesto del trigger
# ===========================================================================

def test_trigger_error_no_reintentable(client: TestClient, sin_log, reloj, monkeypatch) -> None:
    """Un 4xx del trigger no se reintenta: se reporta el error real."""
    async def _trigger_invalido(request):
        raise HTTPException(status_code=400, detail="trigger inválido")

    monkeypatch.setattr("src.main._execute_trigger_internal", _trigger_invalido)

    datos = client.post(
        "/api/v1/trigger", json={"trigger": "@nivel1", "confidence_level": 1}
    ).json()

    assert datos["success"] is False
    assert datos["error_message"] == "trigger inválido"
    assert datos["telemetry"]["error_type"] == "HTTPException"
    assert reloj.dormido == []


def test_trigger_http_reintentable_usa_fallback(client: TestClient, sin_log, reloj, monkeypatch) -> None:
    """Un 5xx persistente del trigger agota reintentos y cae a fallback local."""
    async def _servicio_caido(request):
        raise HTTPException(status_code=503, detail="servicio caído")

    monkeypatch.setattr("src.main._execute_trigger_internal", _servicio_caido)

    datos = client.post(
        "/api/v1/trigger", json={"trigger": "@nivel1", "confidence_level": 1}
    ).json()

    assert datos["result"]["estado"] == "fallback_local"
    assert datos["success"] is True  # fallback_local no es error ni no_disponible
    assert datos["telemetry"]["fallback"] is True
    assert len(reloj.dormido) == 1  # 2 intentos -> 1 espera


def test_trigger_excepcion_inesperada_usa_fallback(client: TestClient, sin_log, reloj, monkeypatch) -> None:
    """Una excepción inesperada del trigger cae a fallback local honesto."""
    async def _red_caida(request):
        raise RuntimeError("red caída")

    monkeypatch.setattr("src.main._execute_trigger_internal", _red_caida)

    datos = client.post(
        "/api/v1/trigger", json={"trigger": "@nivel1", "confidence_level": 1}
    ).json()

    assert datos["result"]["estado"] == "fallback_local"
    assert datos["telemetry"]["fallback"] is True
    assert len(reloj.dormido) == 1


# ===========================================================================
# H · Ramas defensivas: sesión sin contexto y orquestador sin tarea
# ===========================================================================

class _FaseAlcanzada:
    """Doble del enum de fase del orquestador (expone ``.value``)."""

    def __init__(self, valor: str) -> None:
        self.value = valor


class _SalidaSinTarea:
    """Salida del orquestador que no planifica tarea (contrato defensivo)."""

    task = None
    success = True
    phase_reached = _FaseAlcanzada("planning")
    total_subtasks_planned = 0
    total_subtasks_executed = 0
    final_result = None
    error_message = None
    warnings: list = []
    tokens_used = 0
    latency_ms = 0
    started_at = None
    completed_at = None


class _OrquestadorSinTarea:
    """Orquestador doble que no produce DAG (simula planificación vacía)."""

    def process_intent(self, input_data):
        return _SalidaSinTarea()


def test_chat_sin_contexto_responde_igual(client: TestClient, monkeypatch) -> None:
    """Defensivo: sin contexto de sesión disponible, el chat responde igual (nivel 1)."""
    monkeypatch.setattr(
        "src.core.session_manager.SessionManager.get_session_context",
        lambda self, session_id: None,
    )

    respuesta = client.post("/api/v1/chat", json={"message": "hola"})
    assert respuesta.status_code == 200

    datos = respuesta.json()
    assert datos["session_context"] is None
    assert datos["metadata"]["confidence_level"] == 1


def test_orchestrate_sin_tarea_deja_dag_vacio(client: TestClient, monkeypatch) -> None:
    """Defensivo: si el orquestador no planifica tarea, el DAG queda vacío (None)."""
    session_id = _crear_sesion(client)
    monkeypatch.setattr("src.main.get_task_orchestrator", lambda: _OrquestadorSinTarea())

    respuesta = client.post(
        "/api/v1/orchestrate",
        json={"session_id": session_id, "intent_summary": "planificar"},
    )
    assert respuesta.status_code == 200

    datos = respuesta.json()
    assert datos["task_id"] is None
    assert datos["dag_structure"] is None
    assert datos["subtasks_planned"] == 0
