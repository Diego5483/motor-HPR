"""Pruebas de endpoint de la API del motor HPR (src/main.py).

Reglas de la Constitución:
- P1: toda funcionalidad llega con pruebas; P2: aserciones formales.
- P3: determinismo (TestClient usa transporte ASGI en proceso: sin red).
- P4: casos negativos obligatorios (phishing -> 403, límites -> 422).
- D4: contrato estricto en la frontera (límites del esquema).
"""

import pytest
from fastapi.testclient import TestClient

from src.main import app

cliente = TestClient(app)


# ---------------------------------------------------------------------------
# Endpoint raíz
# ---------------------------------------------------------------------------

def test_root_reporta_motor_en_linea():
    respuesta = cliente.get("/")
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["estado"] == "en línea"
    assert datos["modulo"] == "main"
    assert "transmitiendo" in datos["mensaje"]


# ---------------------------------------------------------------------------
# Consulta de comunicaciones: casos favorables
# ---------------------------------------------------------------------------

def test_consulta_exitosa_sin_parametros():
    respuesta = cliente.get("/api/v1/communications/query")
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["status"] == "procesado seguro"
    assert datos["resultados"] == []
    assert datos["limit"] == 10  # valor por defecto del esquema
    assert datos["query"] is None


def test_consulta_exitosa_con_parametros():
    respuesta = cliente.get(
        "/api/v1/communications/query",
        params={"query": "bóveda HPR", "limit": 5},
    )
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["query"] == "bóveda HPR"
    assert datos["limit"] == 5
    assert datos["status"] == "procesado seguro"


# ---------------------------------------------------------------------------
# Contrato estricto en la frontera (D4): límites del esquema
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("limite", [0, -1, 101, 1000])
def test_consulta_rechaza_limite_fuera_de_rango(limite):
    respuesta = cliente.get(
        "/api/v1/communications/query",
        params={"limit": limite},
    )
    assert respuesta.status_code == 422  # Unprocessable Entity (Pydantic)


def test_consulta_rechaza_limite_no_entero():
    respuesta = cliente.get(
        "/api/v1/communications/query",
        params={"limit": "diez"},
    )
    assert respuesta.status_code == 422


# ---------------------------------------------------------------------------
# Guardia de seguridad: casos negativos obligatorios (P4)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "consulta",
    [
        "Por favor login y verify tu cuenta",
        "Necesito update mi account",
        "Accede a secure bank transfer",
        "Debes confirm tu identity ahora",
        "Reset your password urgently",
    ],
)
def test_guardia_bloquea_phishing_con_403(consulta):
    respuesta = cliente.get(
        "/api/v1/communications/query",
        params={"query": consulta, "limit": 5},
    )
    assert respuesta.status_code == 403
    assert "phishing" in respuesta.json()["detail"].lower()


def test_guardia_permite_consulta_limpia():
    respuesta = cliente.get(
        "/api/v1/communications/query",
        params={"query": "¿Cuál es el estado del motor HPR?", "limit": 5},
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["status"] == "procesado seguro"
