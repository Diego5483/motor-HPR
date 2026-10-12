"""Contratos de dominio del motor HPR (Regla D4 de la Constitución).

Todo dato que cruza la frontera del motor se valida con esquemas
Pydantic estrictos. Los contratos son puros: no dependen del reloj,
de la red ni del azar (Reglas D2 y E5).
"""

from enum import Enum
from typing import Optional, Literal
from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, HttpUrl

#: Identidad inmutable del sistema (Regla D5).
IDENTIDAD_DETERMINISTA = "HPR-CORE-DETERMINISTIC"


# =============================================================================
# FASE 5: MOTOR DE PENSAMIENTO VERIFICABLE - CONTRATOS DE DATOS
# =============================================================================

class EvidenceType(str, Enum):
    """Tipos de evidencia soportados por el motor de verificación."""
    DOCUMENT = "document"           # Documento completo (paper, artículo, manual)
    SNIPPET = "snippet"             # Fragmento de texto extraído
    TABLE = "table"                 # Tabla de datos estructurados
    CODE = "code"                   # Fragmento de código fuente
    LOG = "log"                     # Log de ejecución o sistema
    METRIC = "metric"               # Métrica cuantitativa
    CITATION = "citation"           # Cita bibliográfica
    SPECIFICATION = "specification" # Especificación técnica oficial


class EvidenceSource(str, Enum):
    """Procedencia de la evidencia según taxonomía de confianza."""
    OFFICIAL = "official"           # Fuentes oficiales (gov, edu, corporativo verificado)
    TECHNICAL = "technical"         # Fuentes técnicas (repos, foros oficiales, docs)
    COMMUNITY = "community"         # Comunidad (StackOverflow, blogs técnicos)
    GENERAL = "general"             # Web general, blogs, redes sociales
    INTERNAL = "internal"           # Conocimiento interno / bóveda HPR


class Evidence(BaseModel):
    """
    Evidencia atómica para el motor de verificación.
    
    Cada pieza de evidencia es inmutable y trazable.
    La puntuación de relevancia NO se interpreta como probabilidad de verdad.
    """
    id: UUID = Field(default_factory=uuid4, description="Identificador único estable")
    content: str = Field(..., min_length=1, description="Contenido relevante de la evidencia")
    source: EvidenceSource = Field(..., description="Procedencia según taxonomía de confianza")
    evidence_type: EvidenceType = Field(..., description="Tipo de evidencia")
    source_url: Optional[HttpUrl] = Field(None, description="URL original de la evidencia")
    source_title: Optional[str] = Field(None, description="Título del documento origen")
    author: Optional[str] = Field(None, description="Autor o entidad emisora")
    published_at: Optional[datetime] = Field(None, description="Fecha de publicación")
    retrieved_at: datetime = Field(default_factory=datetime.utcnow, description="Fecha de recuperación")
    relevance_score: float = Field(
        ..., ge=0.0, le=1.0,
        description="Puntuación de relevancia (NO es probabilidad de verdad)"
    )
    metadata: dict = Field(default_factory=dict, description="Metadatos adicionales extensibles")


class ClaimStatus(str, Enum):
    """Estados obligatorios de evaluación de afirmaciones.
    
    No se permiten estados intermedios ni probabilísticos.
    """
    SUPPORTED = "supported"                 # La evidencia apoya la afirmación
    CONTRADICTED = "contradicted"           # La evidencia contradice la afirmación
    UNVERIFIED = "unverified"               # No hay evidencia suficiente para decidir
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"  # Evidencia existe pero no es concluyente


class ClaimEvaluation(BaseModel):
    """
    Evaluación de una afirmación contra la evidencia disponible.
    
    Cada afirmación se evalúa independientemente con estado binario/ternario estricto.
    """
    claim: str = Field(..., min_length=1, description="Afirmación a evaluar")
    status: ClaimStatus = Field(..., description="Estado de evaluación obligatorio")
    supporting_evidence: list[UUID] = Field(
        default_factory=list, description="IDs de evidencia que apoyan la afirmación"
    )
    contradicting_evidence: list[UUID] = Field(
        default_factory=list, description="IDs de evidencia que contradicen la afirmación"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0,
        description="Confianza en la evaluación (basada en calidad/cobertura de evidencia)"
    )
    reasoning: str = Field(..., min_length=1, description="Razonamiento textual de la evaluación")
    limitations: list[str] = Field(
        default_factory=list, description="Limitaciones conocidas de la evaluación"
    )


class Decision(str, Enum):
    """Decisiones finales del motor de pensamiento verificable."""
    ACCEPT = "accept"           # Aceptar la hipótesis/consulta
    REJECT = "reject"           # Rechazar la hipótesis/consulta
    DEFER = "defer"             # Diferir (requiere más evidencia)
    ABSTAIN = "abstain"         # Abstenerse (no responder por baja confianza/riesgo)


class StructuredResult(BaseModel):
    """
    Resultado estructurado final del motor de pensamiento verificable.
    
    Contiene la conclusión, evaluaciones detalladas, decisión final,
    limitaciones y referencias trazables.
    """
    conclusion: str = Field(..., min_length=1, description="Conclusión textual principal")
    claim_evaluations: list[ClaimEvaluation] = Field(
        default_factory=list, description="Evaluaciones de cada afirmación clave"
    )
    decision: Decision = Field(..., description="Decisión final del motor")
    overall_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confianza global en el resultado"
    )
    limitations: list[str] = Field(
        default_factory=list, description="Limitaciones globales del análisis"
    )
    references: list[UUID] = Field(
        default_factory=list, description="IDs de evidencia referenciada en el resultado"
    )
    metadata: dict = Field(default_factory=dict, description="Metadatos adicionales")


# =============================================================================
# CONTRATOS EXISTENTES (MANTENIDOS PARA COMPATIBILIDAD)
# =============================================================================


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
