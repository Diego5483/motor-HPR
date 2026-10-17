"""Pruebas de regresión — G.2 (Contrato de trigger).

Verifica las dos correcciones de G.2:

1. `TriggerExecutionResponse.success` se DERIVA del estado real del resultado
   (`estado not in {"error", "no_disponible"}`), eliminando el falso éxito.
   -> Antes de G.2 el endpoint fijaba `success=True` incondicionalmente, por lo
      que `test_success_no_se_asume_con_estado_error` FALLABA.
2. `TriggerExecutionResponse.result` es un modelo tipado (`TriggerResult`) y no
   un dict libre ciego: una clave desconocida es rechazada.

Reglas (Constitución HPR): deterministas, sin red, sin mutar la bóveda.
"""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

# Convención del proyecto: HPR/ y HPR/src/ en sys.path (ver test_etapa_d.py).
_HPR_DIR = Path(__file__).resolve().parent.parent
_SRC_DIR = _HPR_DIR / "src"
for _path in (str(_HPR_DIR), str(_SRC_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from src.main import app
from src.schemas import TriggerResult


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Cliente de pruebas en proceso (sin red real)."""
    return TestClient(app)


# ---------------------------------------------------------------------------
# G.2.1 · success derivado del estado (sin falso éxito)
# ---------------------------------------------------------------------------

def test_success_no_se_asume_con_estado_error(client: TestClient) -> None:
    """Un resultado con estado 'error' NO debe reportarse como éxito.

    Regresión: antes de G.2 el endpoint devolvía success=True aunque el
    resultado fuera un error honesto.
    """
    resp = client.post("/api/v1/trigger", json={
        "trigger": "@web_search",
        "confidence_level": 1,
    })
    assert resp.status_code == 200
    data = resp.json()
    # @web_search sin payload => estado "error" => success derivado False.
    assert data["result"]["estado"] == "error"
    assert data["success"] is False, "el error se reportó como falso éxito"


def test_success_derivado_verdadero_en_estado_activo(client: TestClient) -> None:
    """Un resultado con estado operativo sigue siendo éxito."""
    resp = client.post("/api/v1/trigger", json={
        "trigger": "@hpr_confianza",
        "confidence_level": 1,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["result"]["estado"] == "activo"
    assert data["success"] is True


def test_error_derivado_expone_mensaje(client: TestClient) -> None:
    """Cuando success es derivado False, error_message refleja el mensaje real."""
    resp = client.post("/api/v1/trigger", json={
        "trigger": "@web_search",
        "confidence_level": 1,
    })
    data = resp.json()
    assert data["success"] is False
    assert data["error_message"] == data["result"]["mensaje"]


# ---------------------------------------------------------------------------
# G.2.2 · result es un contrato tipado, no un dict libre ciego
# ---------------------------------------------------------------------------

def test_trigger_result_rechaza_clave_desconocida() -> None:
    """TriggerResult(extra='forbid') rechaza campos no declarados."""
    with pytest.raises(ValidationError):
        TriggerResult(campo_inventado="x")


def test_trigger_result_expone_campos_tipados() -> None:
    """Los campos conocidos existen explícitamente en el modelo."""
    model_fields = set(TriggerResult.model_fields)
    esperados = {
        "estado", "mensaje", "nivel_confianza", "turnos", "contexto",
        "perfil", "operaciones_permitidas", "restricciones",
        "query", "resultados_simulados", "sugerencia_configuracion",
        "resultados", "filtro_usuario", "conflictos", "turnos_analizados",
        "sintesis", "foco_usuario", "temas_activos", "ambiguedades",
        "soberania", "ingestión_permitida", "cambios_sensibles",
        "trigger", "fallback",
    }
    assert esperados.issubset(model_fields)


def test_result_serializado_valida_contra_modelo(client: TestClient) -> None:
    """La respuesta real del endpoint es parseable por el contrato tipado."""
    resp = client.post("/api/v1/trigger", json={
        "trigger": "@hpr_confianza",
        "confidence_level": 2,
    })
    data = resp.json()
    parsed = TriggerResult(**data["result"])
    assert parsed.estado == "activo"
    assert parsed.nivel_confianza == 2
