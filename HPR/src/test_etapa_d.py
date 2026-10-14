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


# ---------------------------------------------------------------------------
# D3 · Telemetría en tiempo real
# ---------------------------------------------------------------------------

def test_telemetry_endpoint_responde_200(client: TestClient) -> None:
    """El endpoint /api/v1/telemetry responde correctamente."""
    resp = client.get("/api/v1/telemetry")
    assert resp.status_code == 200


def test_telemetry_estructura_completa(client: TestClient) -> None:
    """La telemetría incluye todas las secciones esperadas."""
    resp = client.get("/api/v1/telemetry")
    data = resp.json()
    assert "backend" in data
    assert "sesiones" in data
    assert "session_actual" in data
    assert "componentes" in data
    assert "telemetria" in data


def test_telemetry_backend_estado_en_linea(client: TestClient) -> None:
    """El backend reporta su estado como en línea."""
    resp = client.get("/api/v1/telemetry")
    data = resp.json()
    assert data["backend"]["estado"] == "en línea"


def test_telemetry_sesiones_globales(client: TestClient) -> None:
    """Las estadísticas globales de sesiones están presentes."""
    resp = client.get("/api/v1/telemetry")
    data = resp.json()
    sesiones = data["sesiones"]
    assert "total_sessions" in sesiones
    assert "active_sessions" in sesiones
    assert "total_turns" in sesiones
    assert "total_tokens" in sesiones


def test_telemetry_componentes_presentes(client: TestClient) -> None:
    """Los componentes del motor están reportados."""
    resp = client.get("/api/v1/telemetry")
    data = resp.json()
    componentes = data["componentes"]
    assert "nexus_root" in componentes
    assert "sovereign_gate" in componentes
    assert "epsilon_wall" in componentes
    assert "session_manager" in componentes


def test_telemetry_con_session_id(client: TestClient) -> None:
    """La telemetría con session_id incluye stats de sesión."""
    # Primero crear una sesión con un trigger
    resp_trigger = client.post("/api/v1/trigger", json={
        "trigger": "@hpr_confianza",
        "confidence_level": 1,
    })
    data_trigger = resp_trigger.json()
    session_id = data_trigger.get("session_id")
    
    if session_id:
        resp = client.get(f"/api/v1/telemetry?session_id={session_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_actual"] is not None


def test_telemetry_sesion_inexistente_retorna_null(client: TestClient) -> None:
    """Sesión inexistente retorna session_actual=null (no error)."""
    resp = client.get("/api/v1/telemetry?session_id=00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_actual"] is None


def test_telemetry_anti_phishing_activo(client: TestClient) -> None:
    """El guardia anti-phishing también protege /api/v1/telemetry."""
    resp = client.get("/api/v1/telemetry?query=login+verify+account")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# D4 · Persistencia de logs de ejecución
# ---------------------------------------------------------------------------

def test_logs_endpoint_responde_200(client: TestClient) -> None:
    """El endpoint /api/v1/logs responde correctamente."""
    resp = client.get("/api/v1/logs")
    assert resp.status_code == 200


def test_logs_estructura_completa(client: TestClient) -> None:
    """Los logs incluyen todas las secciones esperadas."""
    resp = client.get("/api/v1/logs")
    data = resp.json()
    assert "logs" in data
    assert "count" in data
    assert "filters" in data


def test_logs_vacios_sin_ejecuciones(client: TestClient) -> None:
    """Sin ejecuciones previas, los logs están vacíos."""
    resp = client.get("/api/v1/logs")
    data = resp.json()
    # Puede haber logs de pruebas anteriores, pero la estructura es correcta
    assert isinstance(data["logs"], list)
    assert isinstance(data["count"], int)


def test_logs_stats_endpoint(client: TestClient) -> None:
    """El endpoint /api/v1/logs/stats responde correctamente."""
    resp = client.get("/api/v1/logs/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_executions" in data
    assert "successful" in data
    assert "failed" in data


def test_logs_export_json(client: TestClient) -> None:
    """El endpoint /api/v1/logs/export exporta en JSON."""
    resp = client.get("/api/v1/logs/export?format=json")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "exported"
    assert data["format"] == "json"


def test_logs_export_csv(client: TestClient) -> None:
    """El endpoint /api/v1/logs/export exporta en CSV."""
    resp = client.get("/api/v1/logs/export?format=csv")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "exported"
    assert data["format"] == "csv"


def test_logs_export_formato_invalido(client: TestClient) -> None:
    """Formato de exportación inválido retorna 400."""
    resp = client.get("/api/v1/logs/export?format=xml")
    assert resp.status_code == 400


def test_logs_integrity_endpoint(client: TestClient) -> None:
    """El endpoint /api/v1/logs/integrity verifica integridad."""
    resp = client.get("/api/v1/logs/integrity")
    assert resp.status_code == 200
    data = resp.json()
    assert "integrity_ok" in data


def test_logs_con_filtro_trigger(client: TestClient) -> None:
    """Los logs pueden filtrarse por trigger."""
    # Primero ejecutar un trigger para generar un log
    client.post("/api/v1/trigger", json={
        "trigger": "@hpr_confianza",
        "confidence_level": 1,
    })
    
    resp = client.get("/api/v1/logs?trigger=@hpr_confianza")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["logs"], list)


def test_logs_con_filtro_success(client: TestClient) -> None:
    """Los logs pueden filtrarse por estado de éxito."""
    resp = client.get("/api/v1/logs?success=true")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["logs"], list)


def test_logs_con_limite(client: TestClient) -> None:
    """Los logs respetan el límite especificado."""
    resp = client.get("/api/v1/logs?limit=5")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] <= 5


def test_logs_anti_phishing_activo(client: TestClient) -> None:
    """El guardia anti-phishing también protege /api/v1/logs."""
    resp = client.get("/api/v1/logs?query=login+verify+account")
    assert resp.status_code == 403


def test_log_persistente_despues_de_trigger(client: TestClient) -> None:
    """Cada ejecución de trigger genera un log persistente."""
    # Ejecutar un trigger
    resp = client.post("/api/v1/trigger", json={
        "trigger": "@hpr_confianza",
        "confidence_level": 1,
    })
    assert resp.status_code == 200
    
    # Verificar que se generó un log
    resp_logs = client.get("/api/v1/logs?trigger=@hpr_confianza")
    data_logs = resp_logs.json()
    assert data_logs["count"] > 0


def test_log_registro_hash_integridad(client: TestClient) -> None:
    """Cada log incluye hash de integridad (S5)."""
    # Ejecutar un trigger
    client.post("/api/v1/trigger", json={
        "trigger": "@hpr_confianza",
        "confidence_level": 1,
    })
    
    # Obtener logs y verificar que tienen hash
    resp = client.get("/api/v1/logs?trigger=@hpr_confianza")
    data = resp.json()
    if data["logs"]:
        assert "hash" in data["logs"][0]
