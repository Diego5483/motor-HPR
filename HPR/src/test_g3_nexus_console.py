"""Pruebas de regresión — G.3 (Nexus Console · render honesto).

Corrige el defecto Fase F escenario D ("la interfaz recibe los datos, pero los
interpreta incorrectamente") y el agravante E ("los datos mostrados pertenecen a
otra ejecución / valores por defecto").

Regresión cubierta:
1. La métrica rotulada "SUBTAREAS" mostraba el recuento de TURNOS.
2. La métrica rotulada "VALIDACIONES" mostraba `active_sessions` (sondeo) o el
   nivel de confianza como "N/3" (trigger): dos semánticas en una casilla.
3. `updateTelemetry` leía campos inexistentes del contrato (`result.tokens_used`,
   `result.subtasks_executed`) que nunca llegan (G.2 los tipa).
4. La descripción de @web_search prometía "resultados simulados".
5. La traza del resultado incluía campos nulos del contrato tipado.

Reglas (Constitución HPR): deterministas, sin red, no mutan datos.
"""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_HPR_DIR = Path(__file__).resolve().parent.parent
_SRC_DIR = _HPR_DIR / "src"
for _path in (str(_HPR_DIR), str(_SRC_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from src.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Cliente de pruebas en proceso (sin red real)."""
    return TestClient(app)


@pytest.fixture(scope="module")
def html(client: TestClient) -> str:
    resp = client.get("/ui/")
    assert resp.status_code == 200
    return resp.text


@pytest.fixture(scope="module")
def appjs(client: TestClient) -> str:
    resp = client.get("/ui/app.js")
    assert resp.status_code == 200
    return resp.text


# ---------------------------------------------------------------------------
# G.3.1 · El rótulo coincide con el dato (sin misinterpretación)
# ---------------------------------------------------------------------------

def test_no_rotula_turnos_como_subtareas(html: str) -> None:
    """'SUBTAREAS' era el rótulo de un recuento de turnos: se elimina."""
    assert ">SUBTAREAS<" not in html
    assert 'id="subtasks"' not in html
    # El dato real (turnos) se expone con su nombre.
    assert ">TURNOS<" in html
    assert 'id="turns"' in html


def test_no_rotula_sesiones_como_validaciones(html: str) -> None:
    """'VALIDACIONES' mostraba sesiones activas o el nivel de confianza."""
    assert ">VALIDACIONES<" not in html
    assert 'id="validations"' not in html
    # El dato real (sesiones activas) se expone con su nombre.
    assert "SESIONES ACTIVAS" in html
    assert 'id="sessions"' in html


def test_mapeo_telemetria_honesto(appjs: str) -> None:
    """Cada métrica se escribe desde su fuente real."""
    assert "$('turns')" in appjs
    assert "t.total_turns" in appjs
    assert "$('sessions')" in appjs
    assert "t.active_sessions" in appjs
    assert "$('tokens')" in appjs
    assert "t.total_tokens" in appjs


# ---------------------------------------------------------------------------
# G.3.2 · Sin campos fantasma del contrato
# ---------------------------------------------------------------------------

def test_sin_campos_fantasma_en_resultado(appjs: str) -> None:
    """El contrato (G.2) no expone tokens_used ni subtasks_executed."""
    assert "result.tokens_used" not in appjs
    assert "result.subtasks_executed" not in appjs
    assert "$('subtasks')" not in appjs
    assert "$('validations')" not in appjs


def test_traza_filtra_campos_nulos(appjs: str) -> None:
    """La traza del resultado descarta null/vacíos antes de mostrarse."""
    assert "Object.entries(data.result)" in appjs
    assert "v != null" in appjs


# ---------------------------------------------------------------------------
# G.3.3 · Limpieza de etiquetas (sin promesas de datos simulados)
# ---------------------------------------------------------------------------

def test_web_search_sin_promesa_simulada(appjs: str) -> None:
    """La descripción no debe prometer resultados simulados (Constitución: no inventar)."""
    assert "resultados simulados" not in appjs


# ---------------------------------------------------------------------------
# Compuerta 2 · Render honesto del estado no_disponible (@web_search)
# ---------------------------------------------------------------------------

def test_consola_registra_estado_no_disponible(appjs: str) -> None:
    """La consola distingue 'no_disponible' de un error real (Fase 1 · #3/#5).

    Regresión: antes, un @web_search sin proveedor caía en el genérico
    'TRIGGER_ERROR' sin surfacear el estado explícito ni los campos del resultado.
    """
    assert "estado === 'no_disponible'" in appjs
    assert "TRIGGER_NO_DISPONIBLE" in appjs
    assert "sugerencia_configuracion" in appjs
