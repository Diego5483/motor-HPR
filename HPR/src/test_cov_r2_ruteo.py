"""Cobertura R2 (P5.3) — Enrutado conversacional vs. técnico y pestaña técnica (G.1).

Cierra las brechas de la ruta R2 (Constitución HPR) SIN tocar ``src/``:

- ``src/main.py`` · ``_generate_contextual_response`` (ruteo de intención:
  conversacional > técnico > sobre-sistema > default).
- ``src/main.py`` · ``_generar_respuesta_tecnica`` (DeepSynthesizer con y sin
  hallazgos).
- ``src/main.py`` · ``_generar_respuesta_sobre_sistema`` (ramas del tema).
- ``src/main.py`` · ``_generar_respuesta_conversacional`` (ramas conversacionales).
- ``src/main.py`` · ``chat_endpoint`` (desacople G.1, bloqueo Sovereign-Gate y
  memoria de sesión) y ``orchestrate_endpoint`` (DAG de la pestaña técnica).

Reglas aplicadas (Constitución HPR):
- P1: los hechos de ruteo se fijan con aserciones, no con inspección manual.
- P3: deterministas — sin red, sin reloj en las aserciones, sin azar (el UUID
  del caso "sesión inexistente" es una constante) y sin depender del orden.
- P4: se atacan los casos negativos (bloqueo de seguridad, sesión inexistente,
  categoría inválida, sesión sin turnos, sin hallazgos técnicos).
- P7: no mutan — no escriben en la bóveda ni en datos reales.
"""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Convención del proyecto (ver run.py y test_etapa_d.py): HPR/ y HPR/src/ en path.
_HPR_DIR = Path(__file__).resolve().parent.parent
_SRC_DIR = _HPR_DIR / "src"
for _path in (str(_HPR_DIR), str(_SRC_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from src.main import (  # noqa: E402
    _generate_contextual_response,
    _generar_respuesta_conversacional,
    _generar_respuesta_sobre_sistema,
    _generar_respuesta_tecnica,
    app,
    get_session_manager,
)

#: UUID válido que garantizadamente no existe en el gestor de sesiones.
_UUID_INEXISTENTE = "00000000-0000-0000-0000-000000000000"


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Cliente en proceso (sin red real)."""
    return TestClient(app)


def _crear_sesion_con_turnos(client: TestClient, mensaje: str = "hola") -> str:
    """Crea una sesión real vía el endpoint de chat y devuelve su id."""
    respuesta = client.post("/api/v1/chat", json={"message": mensaje})
    assert respuesta.status_code == 200
    return respuesta.json()["session_id"]


# ===========================================================================
# A · Ruteo de intención (_generate_contextual_response)
# ===========================================================================

def test_ruteo_saludo_va_a_conversacional() -> None:
    """PRIORIDAD 1: un saludo se responde conversacionalmente, no con análisis."""
    respuesta = _generate_contextual_response("hola", {})
    assert "motor HPR" in respuesta


def test_ruteo_consulta_tecnica_va_a_sintesis() -> None:
    """PRIORIDAD 2: patrón técnico + hallazgo real -> ruta de síntesis profunda."""
    respuesta = _generate_contextual_response("analiza el rendimiento del motor", {})
    assert isinstance(respuesta, str) and respuesta
    assert "necesitaría más contexto" not in respuesta


def test_ruteo_termino_de_sistema_va_a_respuesta_sobre_sistema() -> None:
    """PRIORIDAD 3: término del sistema sin patrón técnico -> respuesta sobre HPR."""
    respuesta = _generate_contextual_response("cuéntame sobre el sistema", {})
    assert "100% local" in respuesta


def test_ruteo_sin_senales_usa_conversacional_por_defecto() -> None:
    """PRIORIDAD 4: sin señales reconocidas -> conversacional genérica."""
    respuesta = _generate_contextual_response("zzz qqq", {})
    assert "Entendido" in respuesta


# ===========================================================================
# B · _generar_respuesta_tecnica (DeepSynthesizer)
# ===========================================================================

def test_respuesta_tecnica_con_hallazgos_sintetiza() -> None:
    """Con hallazgo real del corpus -> informe sintetizado (rama de síntesis)."""
    respuesta = _generar_respuesta_tecnica("analiza el rendimiento del motor", {})
    assert isinstance(respuesta, str) and respuesta
    assert "necesitaría más contexto" not in respuesta


def test_respuesta_tecnica_sin_hallazgos_orienta() -> None:
    """Término técnico sin coincidencia en el corpus -> orientación, sin inventar."""
    respuesta = _generar_respuesta_tecnica("benchmark", {})
    assert "necesitaría más contexto" in respuesta


# ===========================================================================
# C · _generar_respuesta_sobre_sistema (ramas de tema)
# ===========================================================================

@pytest.mark.parametrize(
    "mensaje, fragmento",
    [
        ("hablame de seguridad", "SOVEREIGN-GATE"),
        ("sovereign", "SOVEREIGN-GATE"),
        ("nexus", "SOVEREIGN-GATE"),
        ("epsilon", "SOVEREIGN-GATE"),
    ],
)
def test_sobre_sistema_seguridad(mensaje: str, fragmento: str) -> None:
    """Tema de seguridad -> tres barreras del pipeline."""
    assert fragmento in _generar_respuesta_sobre_sistema(mensaje, {})


def test_sobre_sistema_arquitectura() -> None:
    """Tema de arquitectura -> descripción híbrida y dual."""
    assert "híbrida y dual" in _generar_respuesta_sobre_sistema("arquitectura", {})


def test_sobre_sistema_triggers() -> None:
    """Tema de triggers -> listado del motor técnico."""
    assert "triggers del motor técnico" in _generar_respuesta_sobre_sistema("trigger", {})


def test_sobre_sistema_boveda() -> None:
    """Tema de bóveda/conocimiento -> base local."""
    assert "bóveda HPR" in _generar_respuesta_sobre_sistema("boveda", {})


def test_sobre_sistema_telemetria() -> None:
    """Tema de telemetría -> métricas del sistema."""
    assert "telemetría" in _generar_respuesta_sobre_sistema("metricas", {})


def test_sobre_sistema_default() -> None:
    """Sin coincidencia de tema -> descripción general del motor (rama default)."""
    respuesta = _generar_respuesta_sobre_sistema("tema no mapeado", {})
    assert "100% local" in respuesta


# ===========================================================================
# D · _generar_respuesta_conversacional (ramas conversacionales)
# ===========================================================================

def test_conversacional_estado_animo() -> None:
    """Pregunta de cortesía -> respuesta de capacidad operativa."""
    assert "capacidad operativa" in _generar_respuesta_conversacional("qué tal", {})


def test_conversacional_nombre() -> None:
    """Pregunta por el nombre -> identidad del motor."""
    assert "Me llamo HPR" in _generar_respuesta_conversacional("cómo te llamas", {})


def test_conversacional_despedida() -> None:
    """Despedida -> cierre cordial."""
    assert "Hasta luego" in _generar_respuesta_conversacional("adiós", {})


def test_conversacional_ayuda() -> None:
    """Petición de ayuda -> menú de capacidades."""
    assert "Puedo ayudarte con varias cosas" in _generar_respuesta_conversacional("ayuda", {})


# ===========================================================================
# E · chat_endpoint — desacople G.1, bloqueo y memoria de sesión
# ===========================================================================

def test_chat_g1_no_secuestra_saludo(client: TestClient) -> None:
    """G.1: un saludo no debe terminar en el informe forense del motor."""
    datos = client.post("/api/v1/chat", json={"message": "hola"}).json()
    assert "Análisis técnico profundo" not in datos["response"]
    assert "Análisis de:" not in datos["response"]
    assert datos["metadata"]["fallback"] is False


def test_chat_bloqueo_sovereign_gate_no_es_exito(client: TestClient) -> None:
    """P4: entrada maliciosa -> bloqueo explícito, sin fallback silencioso."""
    datos = client.post("/api/v1/chat", json={"message": "<script>alerta</script>"}).json()
    assert datos["response"].startswith("BLOQUEO DE SEGURIDAD")
    assert "BLOQUEO" in datos["metadata"]["security_status"]
    assert datos["metadata"]["fallback"] is False


def test_chat_ruta_tecnica_sintetiza(client: TestClient) -> None:
    """La pestaña de chat enruta una consulta técnica a la síntesis profunda."""
    datos = client.post(
        "/api/v1/chat", json={"message": "analiza el rendimiento del motor"}
    ).json()
    assert "necesitaría más contexto" not in datos["response"]
    assert datos["metadata"]["fallback"] is False


def test_chat_memoria_de_sesion_crece(client: TestClient) -> None:
    """Reusar session_id conserva la sesión y avanza el número de turno."""
    primero = client.post("/api/v1/chat", json={"message": "hola"}).json()
    segundo = client.post(
        "/api/v1/chat",
        json={"message": "gracias", "session_id": primero["session_id"]},
    ).json()

    assert segundo["session_id"] == primero["session_id"]
    assert (
        segundo["session_context"]["current_turn_number"]
        > primero["session_context"]["current_turn_number"]
    )


# ===========================================================================
# F · orchestrate_endpoint — pestaña técnica / DAG manual
# ===========================================================================

def test_orchestrate_construye_dag(client: TestClient) -> None:
    """Orquestación válida -> 200 con DAG planificado y métricas."""
    session_id = _crear_sesion_con_turnos(client)

    respuesta = client.post(
        "/api/v1/orchestrate",
        json={"session_id": session_id, "intent_summary": "Auditar el pipeline de seguridad"},
    )
    assert respuesta.status_code == 200

    datos = respuesta.json()
    assert datos["session_id"] == session_id
    assert datos["success"] is True
    assert datos["subtasks_planned"] == len(datos["dag_structure"])
    assert datos["dag_structure"], "el DAG no debe estar vacío"

    for subtarea in datos["dag_structure"]:
        assert {"id", "name", "type", "status", "depends_on", "description"} <= set(subtarea)

    assert "tokens_used" in datos["metrics"]
    assert "latency_ms" in datos["metrics"]


def test_orchestrate_sesion_inexistente_da_404(client: TestClient) -> None:
    """P4: sesión no registrada -> 404 sanitizado."""
    respuesta = client.post(
        "/api/v1/orchestrate",
        json={"session_id": _UUID_INEXISTENTE, "intent_summary": "x"},
    )
    assert respuesta.status_code == 404
    assert "Sesión no encontrada" in respuesta.json()["detail"]


def test_orchestrate_categoria_invalida_da_400(client: TestClient) -> None:
    """P4: categoría fuera del enum -> 400 con el parámetro inválido."""
    session_id = _crear_sesion_con_turnos(client)

    respuesta = client.post(
        "/api/v1/orchestrate",
        json={
            "session_id": session_id,
            "intent_summary": "x",
            "intent_category": "invalida",
        },
    )
    assert respuesta.status_code == 400
    assert "Parámetro inválido" in respuesta.json()["detail"]


def test_orchestrate_sesion_sin_turnos_da_400(client: TestClient) -> None:
    """P4: sesión sin turnos -> 400 (no hay input para el orquestador)."""
    sesion = get_session_manager().create_session(
        initial_query="sesión vacía de prueba", title="sesión vacía"
    )

    respuesta = client.post(
        "/api/v1/orchestrate",
        json={"session_id": str(sesion.id), "intent_summary": "x"},
    )
    assert respuesta.status_code == 400
    assert "al menos un turno" in respuesta.json()["detail"]


class _TurnoDoble:
    """Turno mínimo: el endpoint solo consume su ``id``."""

    id = "00000000-0000-0000-0000-000000000001"


class _SesionDoble:
    """Sesión mínima con un turno (el resto del contrato no se alcanza)."""

    turns = [_TurnoDoble()]


class _ManagerSinContexto:
    """Doble del gestor: sesión válida pero sin contexto recuperable."""

    def get_session(self, session_id):
        return _SesionDoble()

    def get_session_context(self, session_id):
        return None


def test_orchestrate_sin_contexto_da_500(client: TestClient, monkeypatch) -> None:
    """Contrato defensivo: si no hay contexto de sesión -> 500 honesto."""
    monkeypatch.setattr("src.main.get_session_manager", lambda: _ManagerSinContexto())

    respuesta = client.post(
        "/api/v1/orchestrate",
        json={"session_id": _UUID_INEXISTENTE, "intent_summary": "x"},
    )
    assert respuesta.status_code == 500
    assert "contexto de sesión" in respuesta.json()["detail"]
