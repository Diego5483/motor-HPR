"""Pruebas del triaje determinista (src/core/triage.py).

Reglas de la Constitución: P3 (determinismo), P4 (casos negativos),
D1 (misma entrada, misma salida).
"""

import pytest

from src.core.triage import triage_query
from src.models.contracts import CategoriaConsulta, NivelRiesgo


@pytest.mark.parametrize(
    "consulta",
    [
        "<script>alerta</script>",  # inyección XSS
        "DROP TABLE usuarios",  # inyección SQL
        "OVERRIDE_ROOT ahora",  # anulación de identidad
    ],
)
def test_triaje_bloquea_ingesta_maliciosa(consulta):
    resultado = triage_query(consulta)
    assert resultado.categoria is CategoriaConsulta.SEGURIDAD
    assert resultado.nivel_riesgo is NivelRiesgo.CRITICO
    assert any("patrón" in razon for razon in resultado.razones)


@pytest.mark.parametrize(
    "consulta",
    [
        "Por favor login y verify tu cuenta",
        "Reset your password urgently",
    ],
)
def test_triaje_bloquea_phishing(consulta):
    resultado = triage_query(consulta)
    assert resultado.categoria is CategoriaConsulta.SEGURIDAD
    assert resultado.nivel_riesgo is NivelRiesgo.ALTO


@pytest.mark.parametrize(
    "consulta",
    [
        "¿Cuál es el estado del motor HPR?",
        "Reporte de latencia y rendimiento",
    ],
)
def test_triaje_clasifica_operativa(consulta):
    resultado = triage_query(consulta)
    assert resultado.categoria is CategoriaConsulta.OPERATIVA
    assert resultado.nivel_riesgo is NivelRiesgo.BAJO


@pytest.mark.parametrize(
    "consulta",
    [
        "¿Qué es la bóveda HPR?",
        "¿Cómo funciona el motor?",
    ],
)
def test_triaje_clasifica_conocimiento(consulta):
    resultado = triage_query(consulta)
    assert resultado.categoria is CategoriaConsulta.CONOCIMIENTO
    assert resultado.nivel_riesgo is NivelRiesgo.BAJO


@pytest.mark.parametrize("consulta", [None, "", "   "])
def test_triaje_consulta_vacia(consulta):
    resultado = triage_query(consulta)
    assert resultado.categoria is CategoriaConsulta.DESCONOCIDA
    assert resultado.nivel_riesgo is NivelRiesgo.MEDIO
    assert "consulta vacía" in resultado.razones


def test_triaje_consulta_no_reconocida():
    resultado = triage_query("Consulta normal de sistema")
    assert resultado.categoria is CategoriaConsulta.DESCONOCIDA
    assert resultado.nivel_riesgo is NivelRiesgo.MEDIO


def test_triaje_prioriza_seguridad_sobre_operativa():
    # Una consulta con señal operativa y patrón malicioso es de seguridad primero.
    resultado = triage_query("estado del sistema DROP TABLE usuarios")
    assert resultado.categoria is CategoriaConsulta.SEGURIDAD
    assert resultado.nivel_riesgo is NivelRiesgo.CRITICO


def test_triaje_es_determinista():
    primera = triage_query("¿Qué es la bóveda HPR?")
    segunda = triage_query("¿Qué es la bóveda HPR?")
    assert primera == segunda
