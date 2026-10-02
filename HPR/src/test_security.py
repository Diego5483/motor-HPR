"""Pruebas del guardia de seguridad de la API (src.core.security_agent).

Migración a pytest conforme a la Constitución del proyecto HPR:
- P2: aserciones formales; sin scripts basados en print/sleep.
- P3: pruebas deterministas (expresiones regulares puras, sin red ni reloj).
- P4: casos negativos obligatorios de phishing.
"""

import pytest
from fastapi import HTTPException

from src.core.security_agent import inspect_for_phishing, verify_security_guard


# ---------------------------------------------------------------------------
# Detección de phishing: casos negativos obligatorios (P4)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "texto",
    [
        "Por favor login y verify tu cuenta",
        "Necesito update mi account",
        "Accede a secure bank transfer",
        "Debes confirm tu identity ahora",
        "Reset your password urgently",
        "LOGIN VERIFY URGENTE",  # insensible a mayúsculas
    ],
)
def test_inspect_for_phishing_detecta_patrones(texto):
    assert inspect_for_phishing(texto) is True


@pytest.mark.parametrize(
    "texto",
    [
        "Consulta normal de sistema",
        "¿Cuál es el estado del motor HPR?",
        "login",  # palabra aislada: no completa el patrón
        "",  # vacío
        "   ",  # en blanco
    ],
)
def test_inspect_for_phishing_no_detecta_textos_limpios(texto):
    assert inspect_for_phishing(texto) is False


def test_inspect_for_phishing_acepta_none():
    assert inspect_for_phishing(None) is False


# ---------------------------------------------------------------------------
# Guardia de seguridad: comportamiento del endpoint (P4)
# ---------------------------------------------------------------------------

def test_verify_security_guard_permite_consulta_limpia():
    assert verify_security_guard("Consulta normal de sistema") is True


@pytest.mark.parametrize(
    "texto",
    [
        "Por favor login y verify tu cuenta",
        "Reset your password urgently",
    ],
)
def test_verify_security_guard_bloquea_phishing_con_403(texto):
    with pytest.raises(HTTPException) as excinfo:
        verify_security_guard(texto)
    assert excinfo.value.status_code == 403
    assert "phishing" in excinfo.value.detail.lower()
