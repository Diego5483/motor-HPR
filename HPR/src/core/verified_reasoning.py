"""
Motor de Razonamiento Verificado - Fase 5: Motor de Pensamiento Verificable

Integra:
1. DeepSynthesizer - Extrae hallazgos técnicos del contenido
2. ClaimEvaluator - Evalúa afirmaciones contra evidencia (determinista)
3. DecisionPolicy - Aplica política de decisión (answer, investigate, clarify, abstain)

Flujo:
DeepSynthesizer.hallazgos -> Claims -> ClaimEvaluator -> ClaimEvaluations -> DecisionPolicy -> StructuredResult
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID, uuid4
import logging

from models.contracts import (
    Evidence, EvidenceSource, EvidenceType, ClaimEvaluation, ClaimStatus,
    StructuredResult, Decision
)
from core.claim_evaluator import ClaimEvaluator, create_claim_evaluator, EvaluationRule, SourceQuality
from core.deep_synthesizer import DeepSynthesizer, HallazgoTecnico, InformeProfundo

logger = logging.getLogger(__name__)


class DecisionPolicy(str, Enum):
    """Políticas de decisión del motor de razonamiento verificado."""
    ANSWER = "answer"           # Responder directamente (alta confianza)
    INVESTIGATE = "investigate" # Investigar más (confianza media, brechas)
    CLARIFY = "clarify"         # Pedir aclaración (ambigüedad en la query)
    ABSTAIN = "abstain"         # Abstenerse (baja confianza, contradicciones, riesgo)


@dataclass
class DecisionContext:
    """Contexto para la política de decisión."""
    query: str
    claim_evaluations: List[ClaimEvaluation]
    informe: InformeProfundo
    overall_confidence: float
    high_confidence_count: int
    contradicted_count: int
    insufficient_count: int
    unverified_count: int
    total_claims: int


class DecisionPolicyEngine:
    """
    Motor de política de decisión para el motor de razonamiento verificado.
    
    Aplica reglas deterministas para decidir la acción final:
    - ANSWER: Responder directamente
    - INVESTIGATE: Investigar más (iterar búsqueda)
    - CLARIFY: Pedir aclaración al usuario
    - ABSTAIN: Abstenerse (no responder)
    """
    
    def __init__(
        self,
        answer_threshold: float = 0.75,
        investigate_threshold: float = 0.5,
        max_iterations: int = 3,
        max_budget_tokens: int = 8000,
    ):
        self.answer_threshold = answer_threshold
        self.investigate_threshold = investigate_threshold
        self.max_iterations = max_iterations
        self.max_budget_tokens = max_budget_tokens
    
    def decide(self, context: DecisionContext) -> Tuple[DecisionPolicy, str, Dict[str, Any]]:
        """
        Decide la política basada en el contexto de evaluación.
        
        Returns:
            (policy, reasoning, metadata)
        """
        # Calcular métricas agregadas
        supported_count = sum(1 for c in context.claim_evaluations if c.status == "supported")
        contradicted_count = context.contradicted_count
        insufficient_count = context.insufficient_count
        unverified_count = context.unverified_count
        
        # Ratio de afirmaciones soportadas
        support_ratio = supported_count / context.total_claims if context.total_claims > 0 else 0
        
        # Métricas de calidad
        has_contradictions = contradicted_count > 0
        has_insufficient = insufficient_count > 0
        high_unsupported = (unverified_count + insufficient_count) > context.total_claims * 0.3
        
        metadata = {
            "support_ratio": round(support_ratio, 3),
            "overall_confidence": round(context.overall_confidence, 3),
            "supported_count": supported_count,
            "contradicted_count": contradicted_count,
            "insufficient_count": insufficient_count,
            "unverified_count": unverified_count,
            "total_claims": context.total_claims,
            "high_confidence_count": context.high_confidence_count,
        }
        
        # Regla 1: Contradicciones fuertes -> ABSTAIN
        if contradicted_count > 0 and any(c.confidence > 0.8 for c in context.claim_evaluations if c.status == "contradicted"):
            return DecisionPolicy.ABSTAIN, "Evidencia contradictoria de alta confianza detectada", metadata
        
        # Regla 2: Alta confianza general y mayoría soportada -> ANSWER
        if context.overall_confidence >= self.answer_threshold and support_ratio >= 0.7:
            return DecisionPolicy.ANSWER, "Confianza general alta con mayoría de afirmaciones soportadas", metadata
        
        # Regla 3: Confianza media pero algunas afirmaciones soportadas -> INVESTIGATE
        if context.overall_confidence >= self.investigate_threshold and supported_count > 0:
            return DecisionPolicy.INVESTIGATE, "Confianza media: requiere investigación adicional para afirmaciones no verificadas", metadata
        
        # Regla 3b: Algunas soportadas pero confianza baja -> INVESTIGATE
        if supported_count > 0 and context.overall_confidence < self.investigate_threshold:
            return DecisionPolicy.INVESTIGATE, "Algunas afirmaciones soportadas pero confianza global baja", metadata
        
        # Regla 4: Demasiadas afirmaciones no verificadas/insuficientes -> ABSTAIN
        if high_unsupported or (unverified_count + insufficient_count) == context.total_claims:
            return DecisionPolicy.ABSTAIN, "Demasiadas afirmaciones sin evidencia suficiente o no verificadas", metadata
        
        # Regla 5: Default -> ABSTAIN por seguridad
        return DecisionPolicy.ABSTAIN, "No se cumple criterio para responder o investigar", metadata


class VerifiedReasoningEngine:
    """
    Motor de Razonamiento Verificado - Fase 5.
    
    Orquesta el pipeline completo:
    1. DeepSynthesizer extrae hallazgos técnicos
    2. Convierte hallazgos a claims (afirmaciones verificables)
    3. ClaimEvaluator evalúa cada claim contra evidencia
    4. DecisionPolicy decide la acción final
    5. Genera StructuredResult con decisión y trazabilidad
    """
    
    def __init__(
        self,
        deep_synthesizer: Optional[DeepSynthesizer] = None,
        claim_evaluator: Optional[ClaimEvaluator] = None,
        decision_policy: Optional[DecisionPolicyEngine] = None,
        max_iterations: int = 3,
    ):
        self.deep_synthesizer = deep_synthesizer or DeepSynthesizer()
        self.claim_evaluator = claim_evaluator or create_claim_evaluator()
        self.decision_policy = decision_policy or DecisionPolicyEngine()
        self.max_iterations = max_iterations
        self.iteration_count = 0
    
    def _extract_claims_from_informe(self, informe: InformeProfundo, query: str) -> List[str]:
        """
        Extrae afirmaciones verificables (claims) del informe profundo.
        
        Convierte hallazgos técnicos, conclusiones y análisis en afirmaciones atómicas verificables.
        """
        claims = []
        
        # 1. De conclusiones directas
        for conclusion in informe.conclusiones:
            if len(conclusion) > 20:  # Filtrar muy cortas
                claims.append(conclusion)
        
        # 2. De hallazgos técnicos (convertir a afirmaciones)
        for hallazgo in informe.hallazgos_tecnicos:
            if hallazgo.confianza >= 0.5:  # Solo hallazgos con cierta confianza
                claim = f"{hallazgo.descripcion} (Fuente: {hallazgo.fuente})"
                if len(claim) > 20:
                    claims.append(claim)
        
        # 3. Del análisis técnico (extraer oraciones clave con afirmaciones)
        if hasattr(informe, 'analisis_detallado') and informe.analisis_detallado:
            # Extraer oraciones que contienen afirmaciones técnicas
            import re
            sentences = re.split(r'[.!?]+', informe.analisis_detallado)
            for sent in sentences:
                sent = sent.strip()
                if len(sent) > 30 and any(kw in sent.lower() for kw in [
                    "es", "tiene", "incluye", "soporta", "permite", "implementa", 
                    "usa", "utiliza", "requiere", "define", "especifica"
                ]):
                    claims.append(sent)
        
        # Deduplicar y limitar
        unique_claims = []
        seen = set()
        for c in claims:
            key = c.lower()[:100]
            if key not in seen and len(c) > 20:
                seen.add(key)
                unique_claims.append(c)
        
        return unique_claims[:20]  # Limitar a 20 claims máx
    
    def _build_claim_evidence_map(
        self, 
        claims: List[str], 
        informe: InformeProfundo
    ) -> Dict[str, List[UUID]]:
        """
        Mapea cada claim a la evidencia relevante del informe.
        """
        claim_evidence_map = {}
        evidence_by_id = {}
        
        # Construir índice de evidencia desde hallazgos
        for hallazgo in informe.hallazgos_tecnicos:
            # Crear evidencia pseudo para mapear (usando hallazgo como evidencia)
            # En implementación real, usaríamos la evidencia real del SourceEvaluator
            pass
        
        # Por ahora, mapeo simple: todos los claims usan toda la evidencia
        # En producción, usaríamos matching semántico
        return {}
    
    def reason(
        self, 
        query: str, 
        search_results: List[Dict[str, Any]],
        iteration: int = 0,
    ) -> Dict[str, Any]:
        """
        Ejecuta el pipeline completo de razonamiento verificado.
        
        Args:
            query: Consulta original del usuario
            search_results: Resultados de búsqueda (del UnifiedSearchPipeline o NexusRouter)
            iteration: Número de iteración actual (para control de bucles)
            
        Returns:
            Dict con resultado estructurado, decisión, y metadatos
        """
        self.iteration_count = iteration
        
        # 1. DeepSynthesizer: procesar resultados y generar informe profundo
        logger.info(f"VerifiedReasoningEngine: Iteración {iteration}, procesando query: {query[:80]}")
        
        informe = self.deep_synthesizer.procesar_resultados(
            query=query,
            resultados=search_results,
            evaluacion_global=None
        )
        
        # 2. Extraer claims del informe
        claims = self._extract_claims_from_informe(informe, query)
        logger.info(f"VerifiedReasoningEngine: {len(claims)} claims extraídos")
        
        if not claims:
            return self._build_abstain_result(query, "No se pudieron extraer afirmaciones verificables")
        
        # 3. Preparar evidencia para el evaluador
        # Convertir resultados de búsqueda a Evidence objects
        evidence_pool = self._convert_results_to_evidence(query)
        
        # 3b. Mapear claims a evidencia (simplificado: todo para todos)
        claim_evidence_map = {claim: [e.id for e in evidence_pool] for claim in claims}
        
        # 4. Evaluar cada claim
        claim_evaluations = self.claim_evaluator.evaluate_multiple_claims(
            claims=claims,
            evidence_pool=evidence_pool,
            claim_evidence_map=claim_evidence_map,
        )
        
        # 5. Calcular métricas agregadas
        supported = sum(1 for c in claim_evaluations if c.status == "supported")
        contradicted = sum(1 for c in claim_evaluations if c.status == "contradicted")
        insufficient = sum(1 for c in claim_evaluations if c.status == "insufficient_evidence")
        unverified = sum(1 for c in claim_evaluations if c.status == "unverified")
        high_conf = sum(1 for c in claim_evaluations if c.confidence > 0.7)
        overall_conf = sum(c.confidence for c in claim_evaluations) / len(claim_evaluations) if claim_evaluations else 0
        
        # 6. Construir contexto de decisión
        context = DecisionContext(
            query=query,
            claim_evaluations=claim_evaluations,
            informe=informe,
            overall_confidence=overall_conf,
            high_confidence_count=high_conf,
            contradicted_count=contradicted,
            insufficient_count=insufficient,
            unverified_count=unverified,
            total_claims=len(claims),
        )
        
        # 7. Aplicar política de decisión
        policy, reasoning, metadata = self.decision_policy.decide(context)
        
        # 8. Mapear política a decisión final
        decision_map = {
            DecisionPolicy.ANSWER: Decision.ACCEPT,
            DecisionPolicy.INVESTIGATE: Decision.ACCEPT,  # Con flag de iterar
            DecisionPolicy.CLARIFY: Decision.ACCEPT,      # Con flag de aclarar
            DecisionPolicy.ABSTAIN: Decision.ABSTAIN,
        }
        
        # 8b. Si INVESTIGATE y no hemos llegado a max_iterations, sugerir iterar
        should_iterate = (policy == DecisionPolicy.INVESTIGATE and iteration < self.max_iterations - 1)
        
        # 9. Construir StructuredResult
        final_decision = decision_map[policy]
        if should_iterate:
            # Para iterar, marcamos como ACCEPT pero con flag de iterar
            final_decision = Decision.ACCEPT
        
        result = StructuredResult(
            conclusion=self._build_conclusion(informe, claim_evaluations, policy),
            claim_evaluations=claim_evaluations,
            decision=final_decision,
            overall_confidence=round(overall_conf, 3),
            limitations=self._collect_limitations(claim_evaluations, informe),
            references=self._collect_references(claim_evaluations),
            metadata={
                **metadata,
                "decision_policy": policy.value,
                "policy_reasoning": reasoning,
                "iteration": iteration,
                "should_iterate": should_iterate,
                "claims_extracted": len(claims),
                "claims_evaluated": len(claim_evaluations),
            }
        )
        
        result_dict = result.model_dump()
        # Añadir metrics al nivel superior para compatibilidad
        result_dict["metrics"] = {
            "total_claims": len(claims),
            "high_confidence": sum(1 for c in claim_evaluations if c.confidence > 0.7),
            "supported": sum(1 for c in claim_evaluations if c.status == "supported"),
            "contradicted": sum(1 for c in claim_evaluations if c.status == "contradicted"),
            "insufficient": sum(1 for c in claim_evaluations if c.status == "insufficient_evidence"),
            "unverified": sum(1 for c in claim_evaluations if c.status == "unverified"),
            "avg_confidence": round(sum(c.confidence for c in claim_evaluations) / len(claim_evaluations), 3) if claim_evaluations else 0,
            "avg_combined": round(sum(c.confidence for c in claim_evaluations) / len(claim_evaluations), 3) if claim_evaluations else 0,
        }
        return result_dict
    
    def _convert_results_to_evidence(self, query: str) -> List[Any]:
        """
        Convierte resultados de búsqueda a objetos Evidence.
        En integración real, esto usaría los resultados del UnifiedSearchPipeline.
        Por ahora, retornamos lista vacía - se usa evidence_pool vacío.
        """
        # En integración real, esto se conectaría con los resultados del UnifiedSearchPipeline
        return []
    
    def _build_conclusion(
        self, 
        informe: InformeProfundo, 
        evaluations: List[ClaimEvaluation],
        policy: DecisionPolicy
    ) -> str:
        """Construye conclusión textual basada en evaluaciones y política."""
        supported = [c for c in evaluations if c.status == "supported"]
        contradicted = [c for c in evaluations if c.status == "contradicted"]
        
        parts = []
        
        if policy == DecisionPolicy.ANSWER:
            parts.append("Con base en la evidencia disponible:")
            for c in supported[:3]:
                parts.append(f"- {c.claim} (confianza: {c.confidence:.0%})")
        elif policy == DecisionPolicy.INVESTIGATE:
            parts.append("Se requiere investigación adicional. Hallazgos preliminares:")
            for c in evaluations:
                if c.status == "supported":
                    parts.append(f"- Soportado: {c.claim[:100]}")
                elif c.status == "insufficient_evidence":
                    parts.append(f"- Evidencia insuficiente: {c.claim[:100]}")
        elif policy == DecisionPolicy.ABSTAIN:
            parts.append("No es posible emitir una conclusión definitiva:")
            for c in contradicted[:2]:
                parts.append(f"- Contradicción: {c.claim[:100]}")
            if not contradicted:
                parts.append("- Evidencia insuficiente o no verificable")
        
        return "\n".join(parts) if parts else "Análisis completado sin conclusión definitiva."
    
    def _collect_limitations(
        self, 
        evaluations: List[ClaimEvaluation], 
        informe: InformeProfundo
    ) -> List[str]:
        """Recopila limitaciones de todas las evaluaciones y del informe."""
        limitations = list(informe.advertencias) if hasattr(informe, 'advertencias') else []
        
        for eval in evaluations:
            limitations.extend(eval.limitations)
        
        # Deduplicar
        unique = []
        seen = set()
        for lim in limitations:
            key = lim.lower()[:100]
            if key not in seen:
                seen.add(key)
                unique.append(lim)
        
        return unique[:10]
    
    def _collect_references(self, evaluations: List[ClaimEvaluation]) -> List[UUID]:
        """Recopila todas las referencias de evidencia usadas."""
        refs = set()
        for eval in evaluations:
            refs.update(eval.supporting_evidence)
            refs.update(eval.contradicting_evidence)
        return list(refs)
    
    def _build_abstain_result(self, query: str, reason: str) -> Dict[str, Any]:
        """Construye resultado de abstención."""
        from models.contracts import StructuredResult, Decision
        return StructuredResult(
            conclusion=f"No se pudo responder: {reason}",
            claim_evaluations=[],
            decision=Decision.ABSTAIN,
            overall_confidence=0.0,
            limitations=[reason],
            references=[],
            metadata={"decision_policy": "abstain", "reason": reason}
        ).model_dump()


def create_verified_reasoning_engine(
    deep_synthesizer: Optional[DeepSynthesizer] = None,
    claim_evaluator: Optional[ClaimEvaluator] = None,
    decision_policy: Optional[DecisionPolicyEngine] = None,
    max_iterations: int = 3,
) -> VerifiedReasoningEngine:
    """Factoría para VerifiedReasoningEngine."""
    return VerifiedReasoningEngine(
        deep_synthesizer=deep_synthesizer,
        claim_evaluator=claim_evaluator,
        decision_policy=decision_policy,
        max_iterations=max_iterations,
    )