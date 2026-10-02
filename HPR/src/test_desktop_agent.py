"""Pruebas del agente de chat del escritorio (src/desktop/agent.py).

Reglas de la Constitución:
- P1: prueba o no existe; P2: aserciones formales.
- P3: determinismo (sin red, reloj ni estado global).
- P4: casos negativos de seguridad.
- D1: misma entrada -> misma respuesta.
"""

import pytest

from src.desktop.agent import AgenteChat, _terminos

CONOCIMIENTO_FIJO = (
    "La bóveda HPR almacena documentos de misión crítica localmente.\n"
    "El muro Epsilon verifica las respuestas contra la verdad de referencia.\n"
    "La Sovereign Gate controla la ingesta de entradas maliciosas.\n"
)


@pytest.fixture()
def agente() -> AgenteChat:
    return AgenteChat(knowledge_base=CONOCIMIENTO_FIJO)


# ---------------------------------------------------------------------------
# Validación de entrada: casos negativos (P4)
# ---------------------------------------------------------------------------

def test_agente_bloquea_ingesta_maliciosa(agente):
    respuesta = agente.responder("<script>alerta</script>")
    assert "SOVEREIGN-GATE" in respuesta
    assert "bloqueada" in respuesta.lower()


def test_agente_deniega_identidad_no_autorizada(agente):
    respuesta = agente.responder("Consulta", state={"identity": "ATACANTE"})
    assert "Nexus Root" in respuesta


# ---------------------------------------------------------------------------
# Enrutamiento por triaje
# ---------------------------------------------------------------------------

def test_agente_responde_consulta_operativa(agente):
    respuesta = agente.responder("¿Cuál es el estado del motor HPR?")
    assert "HPR-CORE-DETERMINISTIC" in respuesta
    assert str(len(CONOCIMIENTO_FIJO)) in respuesta


def test_agente_extrae_pasaje_de_la_boveda(agente):
    respuesta = agente.responder("¿Qué es la bóveda HPR?")
    assert "Respuesta extraída de la Bóveda HPR" in respuesta
    assert "La bóveda HPR almacena documentos de misión crítica localmente." in respuesta


def test_agente_consulta_sin_coincidencia_en_la_boveda(agente):
    respuesta = agente.responder("¿Qué es la fotosíntesis cuántica?")
    assert "no encontré" in respuesta.lower()


def test_agente_boveda_vacia_sin_coincidencia():
    agente_vacio = AgenteChat(knowledge_base="")
    respuesta = agente_vacio.responder("¿Qué es la bóveda HPR?")
    assert "no encontré" in respuesta.lower()


def test_agente_bloquea_phishing_como_seguridad(agente):
    respuesta = agente.responder("Por favor login y verify tu cuenta")
    assert "SEGURIDAD" in respuesta
    assert "phishing" in respuesta.lower()


def test_agente_consulta_no_reconocida(agente):
    respuesta = agente.responder("blah blah blah")
    assert "no reconozco" in respuesta.lower()


# ---------------------------------------------------------------------------
# Determinismo (D1)
# ---------------------------------------------------------------------------

def test_agente_es_determinista(agente):
    primera = agente.responder("¿Qué es la bóveda HPR?")
    segunda = agente.responder("¿Qué es la bóveda HPR?")
    assert primera == segunda


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def test_terminos_filtra_cortos_y_minusculas():
    assert _terminos("¿Qué es la bóveda HPR?") == ["bóveda"]


def test_terminos_vacio_sin_consulta():
    assert _terminos("") == []


def test_modulos_de_escritorio_son_importables():
    import src.desktop.agent  # noqa: F401
    import src.desktop.voice  # noqa: F401
    import src.desktop.app  # noqa: F401
