"""Pruebas de la interfaz web estática dual (Etapa B).

Verifica la estructura visual base servida por el backend local y la
integridad de los contratos de la API (regresión).

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


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Cliente de pruebas en proceso (sin red real)."""
    return TestClient(app)


# ---------------------------------------------------------------------------
# Estructura visual base (Etapa B)
# ---------------------------------------------------------------------------
def test_frontend_servido_desde_backend_local(client: TestClient) -> None:
    """El frontend estático se sirve desde el propio FastAPI (E1)."""
    resp = client.get("/ui/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_estructura_dual_presente(client: TestClient) -> None:
    """Los dos paneles y sus secciones existen en el HTML servido."""
    resp = client.get("/ui/")
    for marker in (
        "Motor Técnico",
        "Chat Autónomo",
        'id="tech-pane"',
        'id="chat-pane"',
        "Control de sesión",
        "Niveles de confianza",
        "Mapa de orquestación",
        "Telemetría de ejecución",
        "Traza operativa",
        "Ejecutar trigger",
    ):
        assert marker in resp.text, f"Falta marcador visual: {marker}"


def test_componentes_de_seguridad_presentes(client: TestClient) -> None:
    """El mapa de orquestación refleja los componentes reales del motor."""
    resp = client.get("/ui/")
    for componente in (
        "NEXUS-ROOT",
        "Detector · Selector · Router",
        "N1 · Búsqueda Cognitiva",
        "N2 · Grafo de Consistencia",
        "MotorRazonamientoSuperior",
        "EPSILON-WALL",
        "SOVEREIGN-GATE",
    ):
        assert componente in resp.text, f"Componente ausente: {componente}"


def test_tokens_visuales_exactos(client: TestClient) -> None:
    """La paleta de la previsualización se preserva token a token."""
    resp = client.get("/ui/styles.css")
    assert resp.status_code == 200
    css = resp.text
    for token in (
        "#070d16", "#0c1522", "#101d2c", "#132338",
        "#24364b", "#30475f", "#edf4fb", "#8da2b9",
        "#53c9ee", "#209ac5", "#50c7a0", "#e9b76a", "#e47783",
    ):
        assert token in css, f"Token visual ausente: {token}"


def test_assets_del_frontend_servidos(client: TestClient) -> None:
    """CSS y JS del frontend se sirven correctamente."""
    for asset in ("/ui/styles.css", "/ui/app.js"):
        resp = client.get(asset)
        assert resp.status_code == 200, f"Asset no servido: {asset}"


# ---------------------------------------------------------------------------
# Regresión de contratos de la API (la UI no altera el backend)
# ---------------------------------------------------------------------------
def test_contrato_api_raiz_intacto(client: TestClient) -> None:
    """El endpoint raíz conserva su contrato original."""
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["estado"] == "en línea"
    assert "/api/v1/chat" in body["endpoints"]["chat"]
    assert "/api/v1/orchestrate" in body["endpoints"]["orchestrate"]


def test_contrato_chat_validacion_intacta(client: TestClient) -> None:
    """D4: cuerpo vacío en /api/v1/chat se rechaza con 422."""
    resp = client.post("/api/v1/chat", json={})
    assert resp.status_code == 422


def test_contrato_orchestrate_sesion_requerida(client: TestClient) -> None:
    """D4: /api/v1/orchestrate exige session_id UUID (422 si falta)."""
    resp = client.post("/api/v1/orchestrate", json={})
    assert resp.status_code == 422
