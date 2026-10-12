"""
Evaluador Mínimo de Afirmaciones - Fase 5: Motor de Pensamiento Verificable

Este módulo implementa la evaluación determinista de afirmaciones contra evidencia,
separada completamente de la generación de lenguaje natural.

Principios:
1. Reglas deterministas y explícitas para clasificación de estado
2. Una fuente única, repetida o de baja calidad NO cuenta como confirmación independiente
3. Separación estricta entre evaluación de evidencia y generación de lenguaje natural
4. Puntuaciones de relevancia NO son probabilidades de verdad
"""

from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from uuid import UUID
import logging

from models.contracts import (
    Evidence,
    EvidenceSource,
    EvidenceType,
    ClaimEvaluation,
    ClaimStatus,
    StructuredResult,
    Decision,
)

logger = logging.getLogger(__name__)


class SourceQuality(IntEnum):
    """Clasificación de calidad de fuente para deduplicación (ordenada por jerarquía)."""
    LOW = 1         # GENERAL, o baja relevancia (< 0.5)
    MEDIUM = 2      # TECHNICAL, COMMUNITY con relevancia media
    HIGH = 3        # OFFICIAL, TECHNICAL con alta relevancia


@dataclass(frozen=True)
class EvaluationRule:
    """Regla determinista de evaluación."""
    name: str
    description: str
    min_supporting_sources: int = 1
    min_source_quality: SourceQuality = SourceQuality.MEDIUM
    require_corroboration: bool = False  # Requiere fuentes independientes
    allow_single_high_quality: bool = True  # Fuente oficial única basta si alta calidad


# Reglas de evaluación deterministas (orden de precedencia)
EVALUATION_RULES: List[EvaluationRule] = [
    EvaluationRule(
        name="contradiction",
        description="Evidencia directa contradice la afirmación",
        min_supporting_sources=1,
        min_source_quality=SourceQuality.LOW,
    ),
    EvaluationRule(
        name="strong_support",
        description="Evidencia fuerte: múltiples fuentes independientes O fuente oficial única de alta calidad",
        min_supporting_sources=2,
        min_source_quality=SourceQuality.MEDIUM,
        require_corroboration=False,  # Por defecto NO requiere corroboración estricta
        allow_single_high_quality=True,
    ),
    EvaluationRule(
        name="weak_support",
        description="Evidencia limitada o de fuentes de calidad media/baja",
        min_supporting_sources=1,
        min_source_quality=SourceQuality.LOW,
        require_corroboration=False,
    ),
]


def _classify_source_quality(evidence: Evidence) -> SourceQuality:
    """
    Clasifica la calidad de una pieza de evidencia.
    
    NO usa relevance_score como probabilidad de verdad.
    Usa: tipo de fuente + relevance_score + tipo de evidencia.
    """
    # Fuentes oficiales con alta relevancia = HIGH
    if evidence.source == EvidenceSource.OFFICIAL and evidence.relevance_score >= 0.7:
        return SourceQuality.HIGH
    
    # Fuentes técnicas con buena relevancia = MEDIUM
    if evidence.source == EvidenceSource.TECHNICAL and evidence.relevance_score >= 0.6:
        return SourceQuality.MEDIUM
    
    # Fuentes oficiales/technical con relevancia media = MEDIUM
    if evidence.source in (EvidenceSource.OFFICIAL, EvidenceSource.TECHNICAL) and evidence.relevance_score >= 0.5:
        return SourceQuality.MEDIUM
    
    # Comunidad con buena relevancia = MEDIUM
    if evidence.source == EvidenceSource.COMMUNITY and evidence.relevance_score >= 0.6:
        return SourceQuality.MEDIUM
    
    # Resto = LOW
    return SourceQuality.LOW


def _get_unique_sources(evidence_list: List[Evidence]) -> Set[str]:
    """
    Obtiene fuentes únicas (deduplicación por dominio/autor).
    Una fuente repetida NO cuenta como confirmación independiente.
    """
    unique = set()
    for ev in evidence_list:
        # Usar dominio o autor como identificador de fuente
        if ev.source_url:
            from urllib.parse import urlparse
            domain = urlparse(str(ev.source_url)).netloc
            unique.add(domain)
        elif ev.author:
            unique.add(ev.author)
        else:
            # Fallback: usar tipo de fuente + título
            unique.add(f"{ev.source.value}:{ev.source_title or 'unknown'}")
    return unique


def _count_independent_sources(evidence_list: List[Evidence]) -> int:
    """
    Cuenta fuentes independientes (después de deduplicación).
    Una fuente única, repetida o de baja calidad NO cuenta como confirmación independiente.
    """
    return len(_get_unique_sources(evidence_list))


def _evaluate_against_rule(
    claim: str,
    supporting_evidence: List[Evidence],
    contradicting_evidence: List[Evidence],
    rule: EvaluationRule,
) -> Tuple[ClaimStatus, float, List[str]]:
    """
    Evalúa una afirmación contra una regla específica.
    Retorna: (status, confidence, reasoning_parts)
    """
    # 1. Verificar contradicción (prioridad máxima)
    if contradicting_evidence:
        contradicting_quality = max(
            (_classify_source_quality(e) for e in contradicting_evidence),
            default=SourceQuality.LOW
        )
        # Contradicción de fuente alta/baja calidad
        if contradicting_quality in (SourceQuality.HIGH, SourceQuality.MEDIUM):
            return ClaimStatus.CONTRADICTED, 0.9, [
                f"Contradicción detectada: {len(contradicting_evidence)} evidencia(s) contraria(s) "
                f"con calidad {contradicting_quality.value}"
            ]
        else:
            return ClaimStatus.CONTRADICTED, 0.6, [
                f"Posible contradicción: {len(contradicting_evidence)} evidencia(s) de baja calidad"
            ]
    
    # 2. Sin evidencia de apoyo
    if not supporting_evidence:
        return ClaimStatus.INSUFFICIENT_EVIDENCE, 0.1, [
            "No hay evidencia de apoyo para la afirmación"
        ]
    
    # 3. Contar fuentes independientes de apoyo
    supporting_sources = _get_unique_sources(supporting_evidence)
    independent_count = len(supporting_sources)
    
    # Calidad máxima de evidencia de apoyo
    max_quality = max(
        (_classify_source_quality(e) for e in supporting_evidence),
        default=SourceQuality.LOW
    )
    
    # 4. Aplicar regla
    if rule.name == "strong_support":
        # Requiere corroboración (múltiples fuentes independientes) O fuente oficial única de alta calidad
        # PERO: si require_corroboration=True, siempre requiere múltiples fuentes independientes
        has_high_quality_official = any(
            e.source == EvidenceSource.OFFICIAL and _classify_source_quality(e) == SourceQuality.HIGH
            for e in supporting_evidence
        )
        
        # Si la regla requiere corroboración, siempre necesita múltiples fuentes independientes
        # incluso si hay una fuente oficial de alta calidad
        if rule.require_corroboration:
            if independent_count >= rule.min_supporting_sources and max_quality >= SourceQuality.MEDIUM:
                return ClaimStatus.SUPPORTED, 0.8, [
                    f"Corroboración múltiple: {independent_count} fuente(s) independiente(s) "
                    f"con calidad mínima {max_quality.value}"
                ]
            return ClaimStatus.INSUFFICIENT_EVIDENCE, 0.3, [
                f"Evidencia insuficiente para corroboración: {independent_count} fuente(s) "
                f"calidad máxima {max_quality.value}, se requieren {rule.min_supporting_sources}"
            ]
        
        # Sin requerimiento de corroboración estricta:
        # - Una SOLA pieza de evidencia de fuente oficial alta calidad -> 0.85
        # - Múltiples piezas PERO misma fuente (deduplicadas a 1) -> NO es strong_support
        # - Múltiples fuentes independientes con calidad media -> 0.8
        if rule.allow_single_high_quality and has_high_quality_official:
            # Diferenciar: 1 sola pieza de evidencia vs múltiples piezas de la misma fuente
            if len(supporting_evidence) == 1 and independent_count == 1:
                return ClaimStatus.SUPPORTED, 0.85, [
                    f"Fuente oficial de alta calidad única respalda la afirmación: {claim[:100]}"
                ]
            # Múltiples piezas pero misma fuente (repetida) -> NO es strong_support
            # Cae a la siguiente regla
        
        if independent_count >= rule.min_supporting_sources and max_quality >= SourceQuality.MEDIUM:
            return ClaimStatus.SUPPORTED, 0.8, [
                f"Corroboración múltiple: {independent_count} fuente(s) independiente(s) "
                f"con calidad mínima {max_quality.value}"
            ]
        
        return ClaimStatus.INSUFFICIENT_EVIDENCE, 0.3, [
            f"Evidencia insuficiente para corroboración: {independent_count} fuente(s) "
            f"calidad máxima {max_quality.value}, se requieren {rule.min_supporting_sources}"
        ]
    
    elif rule.name == "weak_support":
        # Soporte débil: al menos una fuente, calidad mínima LOW
        if independent_count >= 1 and max_quality >= SourceQuality.LOW:
            return ClaimStatus.SUPPORTED, 0.5, [
                f"Soporte débil: {independent_count} fuente(s) independiente(s) "
                f"con calidad {max_quality.value}"
            ]
        return ClaimStatus.INSUFFICIENT_EVIDENCE, 0.2, [
            f"Evidencia muy débil: {independent_count} fuente(s), calidad {max_quality.value}"
        ]
    
    # Default: no verificado
    return ClaimStatus.UNVERIFIED, 0.1, ["Regla no aplicable"]


class ClaimEvaluator:
    """
    Evaluador Mínimo de Afirmaciones - Fase 5.
    
    Evalúa afirmaciones contra evidencia usando reglas deterministas.
    Separado de generación de lenguaje natural.
    """
    
    def __init__(
        self,
        rules: Optional[List[EvaluationRule]] = None,
        min_confidence_threshold: float = 0.5,
    ):
        self.rules = rules or EVALUATION_RULES
        self.min_confidence_threshold = min_confidence_threshold
    
    def evaluate_claim(
        self,
        claim: str,
        supporting_evidence: List[Evidence],
        contradicting_evidence: List[Evidence] = None,
    ) -> ClaimEvaluation:
        """
        Evalúa una afirmación contra la evidencia disponible.
        
        Args:
            claim: Afirmación a evaluar
            supporting_evidence: Lista de evidencia que apoya
            contradicting_evidence: Lista de evidencia que contradice (opcional)
            
        Returns:
            ClaimEvaluation con status, confidence, reasoning
        """
        contradicting_evidence = contradicting_evidence or []
        
        # Caso especial: sin evidencia de apoyo
        if not supporting_evidence:
            return ClaimEvaluation(
                claim=claim,
                status=ClaimStatus.INSUFFICIENT_EVIDENCE,
                supporting_evidence=[],
                contradicting_evidence=[e.id for e in contradicting_evidence],
                confidence=0.1,
                reasoning="No hay evidencia de apoyo para la afirmación",
                limitations=["No hay evidencia de apoyo para la afirmación"]
            )
        
        # Aplicar reglas en orden de precedencia
        for rule in self.rules:
            status, confidence, reasoning_parts = _evaluate_against_rule(
                claim, supporting_evidence, contradicting_evidence, rule
            )
            
            # Si la regla produce un resultado concluyente (confidence >= threshold)
            if confidence >= self.min_confidence_threshold:
                reasoning = "; ".join(reasoning_parts)
                return ClaimEvaluation(
                    claim=claim,
                    status=status,
                    supporting_evidence=[e.id for e in supporting_evidence],
                    contradicting_evidence=[e.id for e in contradicting_evidence],
                    confidence=confidence,
                    reasoning=reasoning,
                    limitations=self._generate_limitations(
                        supporting_evidence, contradicting_evidence
                    )
                )
        
        # Si ninguna regla da resultado concluyente
        return ClaimEvaluation(
            claim=claim,
            status=ClaimStatus.UNVERIFIED,
            supporting_evidence=[e.id for e in supporting_evidence],
            contradicting_evidence=[e.id for e in contradicting_evidence or []],
            confidence=0.1,
            reasoning="Ninguna regla de evaluación produjo resultado concluyente",
            limitations=["Ninguna regla aplicable con confianza suficiente"]
        )
    
    def evaluate_multiple_claims(
        self,
        claims: List[str],
        evidence_pool: List[Evidence],
        claim_evidence_map: Optional[Dict[str, List[UUID]]] = None,
    ) -> List[ClaimEvaluation]:
        """
        Evalúa múltiples afirmaciones contra un pool de evidencia.
        
        Args:
            claims: Lista de afirmaciones
            evidence_pool: Pool completo de evidencia disponible
            claim_evidence_map: Mapeo opcional claim -> evidencia_ids relevantes
            
        Returns:
            Lista de evaluaciones
        """
        # Si no hay mapeo, usar toda la evidencia para todas las claims (conservador)
        if claim_evidence_map is None:
            supporting_for_all = evidence_pool
            evaluations = []
            for claim in claims:
                eval_result = self.evaluate_claim(claim, supporting_for_all, [])
                evaluations.append(eval_result)
            return evaluations
        
        # Usar mapeo específico
        evaluations = []
        evidence_by_id = {e.id: e for e in evidence_pool}
        
        for claim in claims:
            evidence_ids = claim_evidence_map.get(claim, [])
            supporting = [evidence_by_id[eid] for eid in evidence_ids if eid in evidence_by_id]
            eval_result = self.evaluate_claim(claim, supporting, [])
            evaluations.append(eval_result)
        
        return evaluations
    
    def _generate_limitations(
        self,
        supporting: List[Evidence],
        contradicting: List[Evidence],
    ) -> List[str]:
        """Genera limitaciones conocidas de la evaluación."""
        limitations = []
        
        unique_sources = _count_independent_sources(supporting)
        if unique_sources == 1:
            limitations.append("Una sola fuente independiente de apoyo")
        
        if not supporting:
            limitations.append("Sin evidencia de apoyo")
        
        if contradicting:
            limitations.append(f"Existen {len(contradicting)} evidencia(s) contradictoria(s)")
        
        # Verificar calidad de fuentes
        low_quality_count = sum(
            1 for e in supporting if _classify_source_quality(e) == SourceQuality.LOW
        )
        if low_quality_count > 0:
            limitations.append(f"{low_quality_count} fuente(s) de apoyo de baja calidad")
        
        # Verificar evidencia interna vs externa
        internal_count = sum(1 for e in supporting if e.source == EvidenceSource.INTERNAL)
        if internal_count == len(supporting) and len(supporting) > 0:
            limitations.append("Toda la evidencia proviene de fuentes internas (bóveda HPR)")
        
        return limitations


def create_claim_evaluator(
    rules: Optional[List[EvaluationRule]] = None,
    min_confidence_threshold: float = 0.5,
) -> ClaimEvaluator:
    """Factoría para ClaimEvaluator."""
    return ClaimEvaluator(rules=rules, min_confidence_threshold=min_confidence_threshold)