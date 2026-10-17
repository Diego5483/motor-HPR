"""Pruebas del motor lógico central (src/core/engine.py): contrato a nivel de módulo.

Reglas de la Constitución:
- P2: aserciones formales; P3: determinismo; P4: casos negativos.
- D1: misma entrada -> misma salida; D5: identidad inmutable.

Alcance: las funciones puras canónicas (Sovereign Gate, Nexus Root, Epsilon Wall)
que ``src/core/engine.py`` expone como fuente única de verdad. La antigua clase
``HPREngine`` fue retirada del motor; su responsabilidad quedó repartida entre
estas funciones puras (aquí) y el adaptador ``HPRSecurityEngine`` (cubierto por
``test_engine.py``).
"""

import pytest

from src.core.engine import (
    epsilon_wall_validation,
    nexus_root_validation,
    sovereign_gate_validation,
)
from src.models.contracts import IDENTIDAD_DETERMINISTA


# ---------------------------------------------------------------------------
# Sovereign Gate: control de ingesta (P4 — casos negativos)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "payload",
    [
        "<script>alerta</script>",  # inyección XSS
        "DROP TABLE usuarios",  # inyección SQL
        "OVERRIDE_ROOT",  # anulación de identidad
        "",  # vacío
        "   ",  # en blanco
        None,  # ausente
    ],
)
def test_sovereign_gate_bloquea_ingesta_invalida(payload):
    assert sovereign_gate_validation(payload) is False


@pytest.mark.parametrize(
    "payload",
    ["Consulta normal de sistema", "¿Qué es la bóveda HPR?"],
)
def test_sovereign_gate_acepta_ingesta_valida(payload):
    assert sovereign_gate_validation(payload) is True


def test_sovereign_gate_no_evalua_phishing():
    # La gate de ingesta no evalúa phishing: esa responsabilidad es del guardia de la API.
    assert sovereign_gate_validation("login verify tu cuenta") is True


# ---------------------------------------------------------------------------
# Nexus Root: identidad inmutable (D5)
# ---------------------------------------------------------------------------

def test_nexus_root_acepta_identidad_determinista():
    assert nexus_root_validation({"identity": IDENTIDAD_DETERMINISTA}) is True


def test_nexus_root_rechaza_identidad_diferente():
    assert nexus_root_validation({"identity": "IDENTIDAD_ATACANTE"}) is False


def test_nexus_root_rechaza_estado_vacio():
    assert nexus_root_validation({}) is False


def test_nexus_root_acepta_identidad_personalizada():
    assert nexus_root_validation({"identity": "HPR-PERSONALIZADO"}, nexus_identity="HPR-PERSONALIZADO") is True


# ---------------------------------------------------------------------------
# Epsilon Wall: filtro anti-alucinación
# ---------------------------------------------------------------------------

def test_epsilon_wall_exige_todos_los_terminos():
    assert epsilon_wall_validation("alpha beta gamma", ["alpha", "beta"]) is True
    assert epsilon_wall_validation("alpha gamma", ["alpha", "beta"]) is False


def test_epsilon_wall_con_verdad_vacia_no_filtra():
    # Documenta el comportamiento actual: verdad vacía se considera satisfecha.
    assert epsilon_wall_validation("cualquier respuesta", []) is True
