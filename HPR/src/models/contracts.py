"""Contratos de dominio del motor HPR (Regla D4 de la Constitución).

Todo dato que cruza la frontera del motor se valida con esquemas
Pydantic estrictos. Los contratos son puros: no dependen del reloj,
de la red ni del azar (Reglas D2 y E5).
"""

from enum import Enum

from pydantic import BaseModel, Field

#: Identidad inmutable del sistema (Regla D5).
IDENTIDAD_DETERMINISTA = "HPR-CORE-DETERMINISTIC"


class EstadoPipeline(str, Enum):
    """Estados terminales del pipeline de seguridad."""

    VERIFICADO = "verificado"
    BLOQUEADO = "bloqueado"
    DENEGADO = "denegado"


class NivelRiesgo(str, Enum):
    """Niveles de riesgo del triaje determinista."""

    BAJO = "bajo"
    MEDIO = "medio"
    ALTO = "alto"
    CRITICO = "critico"


class CategoriaConsulta(str, Enum):
    """Categorías de consulta del motor HPR."""

    SEGURIDAD = "seguridad"
    OPERATIVA = "operativa"
    CONOCIMIENTO = "conocimiento"
    DESCONOCIDA = "desconocida"


class PipelineState(BaseModel):
    """Estado del pipeline: identidad inmutable y propósito del sistema (D5)."""

    identity: str = Field(
        default=IDENTIDAD_DETERMINISTA,
        description="Identidad determinista que valida la raíz Nexus.",
    )


class PipelineRequest(BaseModel):
    """Contrato de entrada del pipeline: payload, estado y verdad de referencia."""

    payload: str = Field(
        description="Texto de entrada del usuario; la Sovereign Gate lo valida.",
    )
    state: PipelineState = Field(default_factory=PipelineState)
    truth: list[str] = Field(
        default_factory=list,
        description="Verdad de referencia (ground truth) para el muro Epsilon.",
    )


class PipelineResult(BaseModel):
    """Resultado estructurado y determinista del pipeline (D1)."""

    estado: EstadoPipeline
    mensaje: str
    conocimiento: str | None = Field(
        default=None,
        description="Extracto de la bóveda, cuando el pipeline lo extrae.",
    )
    caracteres_totales: int | None = Field(
        default=None,
        description="Tamaño total de la base de conocimiento, cuando aplica.",
    )


class TriageResult(BaseModel):
    """Resultado del triaje determinista de una consulta."""

    categoria: CategoriaConsulta
    nivel_riesgo: NivelRiesgo
    razones: list[str] = Field(
        default_factory=list,
        description="Reglas que dispararon la clasificación.",
    )
