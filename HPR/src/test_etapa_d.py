"""Pruebas de la Etapa D — Ejecución real de triggers y telemetría.

Verifica:
- Contrato de ejecución de triggers (schemas)
- Endpoint POST /api/v1/trigger
- Guardia de seguridad SOVEREIGN-GATE
- Telemetría de ejecución
- Manejo de errores

Reglas aplicadas (Constitución HPR):
- P1: prueba o no existe — toda entrega nueva llega con pruebas.
- P3: deterministas — sin red, sin reloj en las aserciones, sin estado
  global compartido (TestClient ejecuta la app en proceso).
- P7: no mutan — no escriben en la bóveda ni en datos reales.
"""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Convención de ejecución del proyecto (ver run.py): los módulos de src/
# se importan como paquete (src.main) Y como top-level (models, security_agent),
# por lo que HPR/ y HPR/src/ deben estar en sys.path (E3, D6).
# ---------------------------------------------------------------------------
_HPR_DIR = Path(__file__).resolve().parent.parent
_SRC_DIR = _HPR_DIR / "src"
for _path in (str(_HPR_DIR), str(_SRC_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from src.main import app
from src.schemas import TriggerExecutionRequest, TriggerType


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Cliente de pruebas en proceso (sin red real)."""
    return TestClient(app)


# ---------------------------------------------------------------------------
# D1 · Contrato de ejecución de triggers
# ---------------------------------------------------------------------------

def test_trigger_type_enum_contiene_todos_los_triggers() -> None:
    """Todos los triggers definidos en el frontend existen en el enum."""
    expected = {
        "@hpr_confianza",
        "@nivel1",
        "@web_search",
        "N1 · Búsqueda Cognitiva",
        "N2 · Grafo de Consistencia",
        "MotorRazonamientoSuperior",
        "SOVEREIGN-GATE",
    }
    actual = {t.value for t in TriggerType}
    assert expected == actual, f"Triggers faltantes: {expected - actual}"


def test_trigger_execution_request_campos_requeridos() -> None:
    """El contrato exige trigger y confidence_level válido."""
    req = TriggerExecutionRequest(trigger=TriggerType.CONFIANZA)
    assert req.confidence_level == 1
    assert req.parameters == {}
    assert req.session_id is None


def test_trigger_execution_request_valida_nivel_rango() -> None:
    """confidence_level debe estar entre 1 y 3."""
    with pytest.raises(Exception):  # pydantic ValidationError
        TriggerExecutionRequest(trigger=TriggerType.CONFIANZA, confidence_level=0)
    with pytest.raises(Exception):
        TriggerExecutionRequest(trigger=TriggerType.CONFIANZA, confidence_level=4)


def test_trigger_execution_request_nivel_valido() -> None:
    """Niveles 1, 2 y 3 son aceptados."""
    for level in (1, 2, 3):
        req = TriggerExecutionRequest(trigger=TriggerType.CONFIANZA, confidence_level=level)
        assert req.confidence_level == level


# ---------------------------------------------------------------------------
# D2 · Endpoint POST /api/v1/trigger
# ---------------------------------------------------------------------------

def test_trigger_confianza_ejecucion_exitosa(client: TestClient) -> None:
    """Trigger @hpr_confianza se ejecuta correctamente con nivel 1."""
    resp = client.post("/api/v1/trigger", json={
        "trigger": "@hpr_confianza",
        "confidence_level": 1,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["trigger"] == "@hpr_confianza"
    assert data["result"] is not None
    assert "estado" in data["result"]


def test_trigger_nivel1_ejecucion_exitosa(client: TestClient) -> None:
    """Trigger @nivel1 retorna perfil de interacción."""
    resp = client.post("/api/v1/trigger", json={
        "trigger": "@nivel1",
        "confidence_level": 1,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "perfil" in data["result"]
    assert "operaciones_permitidas" in data["result"]


def test_trigger_sovereign_gate_bloqueado_sin_autorizacion(client: TestClient) -> None:
    """SOVEREIGN-GATE rechaza ejecución sin autorización explícita."""
    resp = client.post("/api/v1/trigger", json={
        "trigger": "SOVEREIGN-GATE",
        "confidence_level": 1,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert "SOVEREIGN-GATE" in data["error_message"]
    assert data["telemetry"]["auth_required"] is True


def test_trigger_nivel3_bloqueado_sin_autorizacion(client: TestClient) -> None:
    """Nivel 3 requiere autorización SOVEREIGN-GATE explícita."""
    resp = client.post("/api/v1/trigger", json={
        "trigger": "@hpr_confianza",
        "confidence_level": 3,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert data["telemetry"]["auth_required"] is True


def test_trigger_telemetria_presente(client: TestClient) -> None:
    """Toda respuesta incluye telemetría de ejecución."""
    resp = client.post("/api/v1/trigger", json={
        "trigger": "@hpr_confianza",
        "confidence_level": 1,
    })
    data = resp.json()
    assert "telemetry" in data
    assert "execution_time_ms" in data["telemetry"]
    assert data["execution_time_ms"] is not None


def test_trigger_desconocido_retorna_error(client: TestClient) -> None:
    """Trigger no definido retorna error de validación (422)."""
    resp = client.post("/api/v1/trigger", json={
        "trigger": "trigger_inexistente",
        "confidence_level": 1,
    })
    assert resp.status_code == 422


def test_trigger_sesion_inexistente_retorna_error(client: TestClient) -> None:
    """Sesión no existente retorna error 200 con success=False."""
    resp = client.post("/api/v1/trigger", json={
        "trigger": "@hpr_confianza",
        "session_id": "00000000-0000-0000-0000-000000000000",
        "confidence_level": 1,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert "Sesión no encontrada" in data["error_message"]


def test_trigger_web_search_estado_no_disponible(client: TestClient) -> None:
    """Web search informa honestamente que no está configurado (sin simulación)."""
    resp = client.post("/api/v1/trigger", json={
        "trigger": "@web_search",
        "confidence_level": 1,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["result"]["estado"] == "no_disponible"
    assert "motor de búsqueda" in data["result"]["mensaje"].lower()


def test_trigger_n1_busqueda_sesion_vacia(client: TestClient) -> None:
    """N1 sobre sesión sin turnos informa resultado vacío honesto."""
    resp = client.post("/api/v1/trigger", json={
        "trigger": "N1 · Búsqueda Cognitiva",
        "confidence_level": 1,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    # Sin turnos previos: resultado vacío
    assert data["result"]["resultados"] == []


def test_trigger_n2_grafo_sesion_vacia(client: TestClient) -> None:
    """N2 sobre sesión sin turnos informa que se necesitan al menos 2."""
    resp = client.post("/api/v1/trigger", json={
        "trigger": "N2 · Grafo de Consistencia",
        "confidence_level": 1,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["result"]["conflictos"] == []


def test_trigger_motor_razon_ejecucion_exitosa(client: TestClient) -> None:
    """MotorRazonamientoSuperior genera síntesis de sesión."""
    resp = client.post("/api/v1/trigger", json={
        "trigger": "MotorRazonamientoSuperior",
        "confidence_level": 1,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "sintesis" in data["result"]


def test_trigger_respuesta_idempotente_campos_obligatorios(client: TestClient) -> None:
    """Estructura de respuesta consistente en éxito y error."""
    # Éxito
    resp_ok = client.post("/api/v1/trigger", json={
        "trigger": "@hpr_confianza",
        "confidence_level": 1,
    })
    data_ok = resp_ok.json()
    required_keys = {"success", "trigger", "session_id", "result", "error_message", "telemetry", "execution_time_ms"}
    assert required_keys.issubset(set(data_ok.keys())), f"Faltan claves: {required_keys - set(data_ok.keys())}"

    # Error
    resp_err = client.post("/api/v1/trigger", json={
        "trigger": "SOVEREIGN-GATE",
        "confidence_level": 1,
    })
    data_err = resp_err.json()
    assert required_keys.issubset(set(data_err.keys())), f"Faltan claves: {required_keys - set(data_err.keys())}"


def test_guardia_anti_phishing_bloquea_trigger(client: TestClient) -> None:
    """verify_security_guard bloquea patrones de phishing en ?query=."""
    # El endpoint /api/v1/trigger no usa ?query= directamente,
    # pero el guardia global debe funcionar en otros endpoints
    resp = client.get("/api/v1/communications/query?query=login+verify+account")
    assert resp.status_code == 403
    assert "phishing" in resp.json()["detail"].lower() or "bloqueada" in resp.json()["detail"].lower()


def test_contrato_sin_cuerpo_retorna_422(client: TestClient) -> None:
    """Cuerpo vacío en /api/v1/trigger se rechaza con 422 (D4)."""
    resp = client.post("/api/v1/trigger", json={})
    assert resp.status_code == 422
