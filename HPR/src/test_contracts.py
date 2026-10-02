"""Pruebas de los contratos de dominio (src/models/contracts.py) — Regla D4.

Los contratos son la frontera estricta del motor: se validan con
aserciones, no por inspección (P1).
"""

import pytest
from pydantic import ValidationError

from src.models.contracts import (
    IDENTIDAD_DETERMINISTA,
    CategoriaConsulta,
    EstadoPipeline,
    NivelRiesgo,
    PipelineRequest,
    PipelineResult,
    PipelineState,
    TriageResult,
)


def test_identidad_determinista_es_inmutable():
    assert IDENTIDAD_DETERMINISTA == "HPR-CORE-DETERMINISTIC"


def test_pipeline_state_usa_identidad_por_defecto():
    state = PipelineState()
    assert state.identity == IDENTIDAD_DETERMINISTA


def test_pipeline_state_acepta_identidad_personalizada():
    state = PipelineState(identity="HPR-PERSONALIZADO")
    assert state.identity == "HPR-PERSONALIZADO"


def test_pipeline_request_valores_por_defecto():
    peticion = PipelineRequest(payload="Consulta")
    assert peticion.state.identity == IDENTIDAD_DETERMINISTA
    assert peticion.truth == []


def test_pipeline_request_exige_payload():
    with pytest.raises(ValidationError):
        PipelineRequest()


def test_pipeline_request_serializa_dict():
    peticion = PipelineRequest(payload="Consulta", truth=["término"])
    datos = peticion.model_dump()
    assert datos["payload"] == "Consulta"
    assert datos["truth"] == ["término"]
    assert datos["state"]["identity"] == IDENTIDAD_DETERMINISTA


def test_pipeline_result_coerciona_estado_desde_cadena():
    resultado = PipelineResult(estado="bloqueado", mensaje="Bloqueo")
    assert resultado.estado is EstadoPipeline.BLOQUEADO


def test_pipeline_result_rechaza_estado_invalido():
    with pytest.raises(ValidationError):
        PipelineResult(estado="inexistente", mensaje="Bloqueo")


def test_triage_result_exige_categoria_y_nivel():
    with pytest.raises(ValidationError):
        TriageResult(razones=["solo razones"])


@pytest.mark.parametrize(
    "enumeracion, valores",
    [
        (EstadoPipeline, {"verificado", "bloqueado", "denegado"}),
        (NivelRiesgo, {"bajo", "medio", "alto", "critico"}),
        (CategoriaConsulta, {"seguridad", "operativa", "conocimiento", "desconocida"}),
    ],
)
def test_enumeraciones_tienen_valores_estables(enumeracion, valores):
    assert {item.value for item in enumeracion} == valores
