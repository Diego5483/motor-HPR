"""Pruebas unitarias del motor de seguridad HPR (HPRSecurityEngine).

Migración a pytest conforme a la Constitución del proyecto HPR:
- P2: aserciones formales; sin scripts basados en print/sleep.
- P3: pruebas deterministas (sin red, sin reloj, sin orden, sin estado global mutable).
- P4: casos negativos obligatorios de seguridad.
- D1/D5: misma entrada -> misma salida e identidad inmutable.
"""

import pytest
from docx import Document

from src.security_agent import HPRSecurityEngine

BLOQUEO_SOVEREIGN_GATE = (
    "BLOQUEO DE SEGURIDAD: SOVEREIGN-GATE: Entrada bloqueada por seguridad."
)
DENEGACION_NEXUS_ROOT = "Acceso denegado por Nexus Root."
IDENTIDAD_DETERMINISTA = "HPR-CORE-DETERMINISTIC"


@pytest.fixture(scope="module")
def engine() -> HPRSecurityEngine:
    """Motor real con la bóveda local (E6); uso de solo lectura."""
    return HPRSecurityEngine()


@pytest.fixture()
def isolated_engine() -> HPRSecurityEngine:
    """Motor con base de conocimiento fija para la ruta de éxito (P3)."""
    instance = HPRSecurityEngine()
    instance.knowledge_base = "CONOCIMIENTO FIJO DE PRUEBA HPR"
    return instance


@pytest.fixture()
def empty_vault_engine() -> HPRSecurityEngine:
    """Motor simulando bóveda vacía (P3: estado controlado)."""
    instance = HPRSecurityEngine()
    instance.knowledge_base = ""
    return instance


# ---------------------------------------------------------------------------
# Sovereign Gate: control de ingesta (P4 — casos negativos)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "payload",
    [
        "<script>malicious_injection</script>",  # inyección XSS
        "DROP TABLE users",  # inyección SQL
        "OVERRIDE_ROOT",  # anulación de identidad
        "",  # payload vacío
        "   ",  # payload en blanco
    ],
)
def test_sovereign_gate_bloquea_entradas_maliciosas(engine, payload):
    resultado = engine.process_pipeline(
        payload=payload,
        state={"identity": IDENTIDAD_DETERMINISTA},
        truth=[],
    )
    assert resultado == BLOQUEO_SOVEREIGN_GATE


def test_sovereign_gate_acepta_payload_limpio(engine):
    resultado = engine.process_pipeline(
        payload="Consulta normal de sistema",
        state={"identity": IDENTIDAD_DETERMINISTA},
        truth=[],
    )
    assert resultado != BLOQUEO_SOVEREIGN_GATE
    assert resultado.startswith("Pipeline verificado con éxito")


# ---------------------------------------------------------------------------
# Nexus Root: validación de identidad inmutable (D5)
# ---------------------------------------------------------------------------

def test_nexus_root_rechaza_identidad_no_autorizada(engine):
    resultado = engine.process_pipeline(
        payload="Consulta normal",
        state={"identity": "IDENTIDAD_ATACANTE"},
        truth=[],
    )
    assert resultado == DENEGACION_NEXUS_ROOT


def test_nexus_root_acepta_solo_identidad_determinista(engine):
    assert engine.nexus_root_validation({"identity": IDENTIDAD_DETERMINISTA}) is True
    assert engine.nexus_root_validation({}) is False


def test_identidad_por_defecto_es_determinista():
    assert HPRSecurityEngine().nexus_identity == IDENTIDAD_DETERMINISTA


# ---------------------------------------------------------------------------
# Epsilon Wall: filtro anti-alucinación sobre verdad de referencia
# ---------------------------------------------------------------------------

def test_epsilon_wall_exige_todos_los_terminos(engine):
    assert engine.epsilon_wall_validation("alpha beta gamma", ["alpha", "beta"]) is True
    assert engine.epsilon_wall_validation("alpha gamma", ["alpha", "beta"]) is False


def test_epsilon_wall_con_verdad_vacia_no_filtra(engine):
    # Documenta el comportamiento actual: verdad vacía se considera satisfecha.
    assert engine.epsilon_wall_validation("cualquier respuesta", []) is True


# ---------------------------------------------------------------------------
# Pipeline: rutas de éxito y determinismo (D1)
# ---------------------------------------------------------------------------

def test_pipeline_extrae_conocimiento_fijo_de_la_boveda(isolated_engine):
    resultado = isolated_engine.process_pipeline(
        payload="¿Qué es la bóveda HPR?",
        state={"identity": IDENTIDAD_DETERMINISTA},
        truth=[],
    )
    assert resultado.startswith("Pipeline verificado con éxito")
    assert "CONOCIMIENTO FIJO DE PRUEBA HPR" in resultado


def test_pipeline_reporta_boveda_vacia(empty_vault_engine):
    resultado = empty_vault_engine.process_pipeline(
        payload="Consulta",
        state={"identity": IDENTIDAD_DETERMINISTA},
        truth=[],
    )
    assert "bóveda de documentos se encuentra vacía" in resultado


def test_pipeline_es_determinista(isolated_engine):
    entrada = {
        "payload": "Consulta repetida",
        "state": {"identity": IDENTIDAD_DETERMINISTA},
        "truth": [],
    }
    primera = isolated_engine.process_pipeline(**entrada)
    segunda = isolated_engine.process_pipeline(**entrada)
    assert primera == segunda


def test_carga_de_boveda_cubre_ramas_de_error(tmp_path):
    """Ramas de error de load_knowledge: ruta inexistente, .docx corrupto y párrafo vacío (P5)."""
    # Rama: docs_path no existe (ni la ruta de respaldo)
    engine = HPRSecurityEngine()
    engine.docs_path = str(tmp_path / "inexistente")
    assert engine.load_knowledge() == ""

    # Rama: .docx corrupto (except) y párrafo vacío (texto en blanco)
    (tmp_path / "corrupto.docx").write_bytes(b"NO ES UN DOCX VALIDO")
    documento = Document()
    documento.add_paragraph("")  # párrafo vacío: para.text.strip() es falso
    documento.save(str(tmp_path / "valido.docx"))
    engine.docs_path = str(tmp_path)
    assert engine.load_knowledge() == ""


def test_modulos_principales_son_importables():
    import src.core  # noqa: F401
    import src.models  # noqa: F401
