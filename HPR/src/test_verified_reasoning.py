"""Pruebas para el Motor de Razonamiento Verificado - Fase 5."""

import sys
sys.path.insert(0, 'HPR/src')

from models.contracts import (
    Evidence, EvidenceSource, EvidenceType, ClaimStatus, 
    ClaimEvaluation, StructuredResult, Decision
)
from core.claim_evaluator import create_claim_evaluator, ClaimEvaluator, EvaluationRule, SourceQuality
from core.verified_reasoning import (
    VerifiedReasoningEngine, create_verified_reasoning_engine,
    DecisionPolicy, DecisionPolicyEngine, DecisionContext
)
from core.deep_synthesizer import DeepSynthesizer, HallazgoTecnico, InformeProfundo
from uuid import uuid4
from datetime import datetime

print("=== TESTS VERIFIED REASONING ENGINE ===\n")

# ============================================================================
# MOCKS Y FIXTURES
# ============================================================================

def make_evidence(content, source="official", evidence_type="document", relevance=0.8, source_url="https://example.com/doc"):
    from models.contracts import EvidenceSource, EvidenceType
    return Evidence(
        content=content, 
        source=EvidenceSource(source.upper()), 
        evidence_type=EvidenceType(evidence_type), 
        relevance_score=relevance, 
        source_url=source_url
    )

def make_informe_simple(claims_list=None):
    """Crea un InformeProfundo simple para testing."""
    if claims_list is None:
        claims_list = ["La Tierra es redonda", "El agua hierve a 100°C"]
    
    hallazgos = []
    for i, claim in enumerate(claims_list):
        hallazgos.append(HallazgoTecnico(
            tipo="especificacion",
            descripcion=claim,
            fuente=f"fuente_{i}",
            confianza=0.8,
            evidencia=claim[:100]
        ))
    
    return InformeProfundo(
        query="test query",
        introduccion="Introducción de prueba",
        hallazgos_tecnicos=hallazgos,
        analisis_detallado="Análisis detallado con afirmaciones técnicas.",
        conclusiones=claims_list,
        advertencias=[],
        metricas_procesamiento={}
    )

# ============================================================================
# TESTS: DecisionPolicyEngine
# ============================================================================

def test_decision_policy_answer():
    """Policy ANSWER cuando alta confianza y mayoría soportada."""
    engine = DecisionPolicyEngine(answer_threshold=0.7, investigate_threshold=0.5)
    
    evals = [
        ClaimEvaluation(claim="c1", status="supported", confidence=0.9, reasoning="test", 
                       supporting_evidence=[], contradicting_evidence=[]),
        ClaimEvaluation(claim="c2", status="supported", confidence=0.85, reasoning="test",
                       supporting_evidence=[], contradicting_evidence=[]),
    ]
    
    context = DecisionContext(
        query="test",
        claim_evaluations=evals,
        informe=make_informe_simple(),
        overall_confidence=0.87,
        high_confidence_count=2,
        contradicted_count=0,
        insufficient_count=0,
        unverified_count=0,
        total_claims=2,
    )
    
    policy_engine = DecisionPolicyEngine()
    policy, reasoning, metadata = policy_engine.decide(context)
    
    assert policy == DecisionPolicy.ANSWER, f"Expected ANSWER, got {policy}"
    assert context.overall_confidence >= 0.75
    print("PASS: test_decision_policy_answer")


def test_decision_policy_abstain_contradiction():
    """Policy ABSTAIN cuando hay contradicción de alta confianza."""
    evals = [
        ClaimEvaluation(claim="c1", status="supported", confidence=0.6, reasoning="test",
                       supporting_evidence=[], contradicting_evidence=[]),
        ClaimEvaluation(claim="c2", status="contradicted", confidence=0.9, reasoning="contradiction found",
                       supporting_evidence=[], contradicting_evidence=[]),
    ]
    
    context = DecisionContext(
        query="test",
        claim_evaluations=evals,
        informe=make_informe_simple(),
        overall_confidence=0.75,
        high_confidence_count=1,
        contradicted_count=1,
        insufficient_count=0,
        unverified_count=0,
        total_claims=2,
    )
    
    policy_engine = DecisionPolicyEngine()
    policy, reasoning, metadata = policy_engine.decide(context)
    
    assert policy == DecisionPolicy.ABSTAIN, f"Expected ABSTAIN, got {policy}"
    print("PASS: test_decision_policy_abstain_contradiction")


def test_decision_policy_investigate():
    """Policy INVESTIGATE cuando confianza media y algunas soportadas."""
    evals = [
        ClaimEvaluation(claim="c1", status="supported", confidence=0.7, reasoning="test",
                       supporting_evidence=[], contradicting_evidence=[]),
        ClaimEvaluation(claim="c2", status="insufficient_evidence", confidence=0.4, reasoning="test",
                       supporting_evidence=[], contradicting_evidence=[]),
    ]
    
    context = DecisionContext(
        query="test",
        claim_evaluations=evals,
        informe=make_informe_simple(),
        overall_confidence=0.6,
        high_confidence_count=0,
        contradicted_count=0,
        insufficient_count=1,
        unverified_count=0,
        total_claims=2,
    )
    
    policy_engine = DecisionPolicyEngine()
    policy, reasoning, metadata = policy_engine.decide(context)
    
    assert policy == DecisionPolicy.INVESTIGATE, f"Expected INVESTIGATE, got {policy}"
    print("PASS: test_decision_policy_investigate")


def test_decision_policy_abstain_all_insufficient():
    """Policy ABSTAIN cuando todas las claims tienen evidencia insuficiente."""
    evals = [
        ClaimEvaluation(claim="c1", status="insufficient_evidence", confidence=0.3, reasoning="test",
                       supporting_evidence=[], contradicting_evidence=[]),
        ClaimEvaluation(claim="c2", status="insufficient_evidence", confidence=0.2, reasoning="test",
                       supporting_evidence=[], contradicting_evidence=[]),
    ]
    
    context = DecisionContext(
        query="test",
        claim_evaluations=evals,
        informe=make_informe_simple(),
        overall_confidence=0.25,
        high_confidence_count=0,
        contradicted_count=0,
        insufficient_count=2,
        unverified_count=0,
        total_claims=2,
    )
    
    policy_engine = DecisionPolicyEngine()
    policy, reasoning, metadata = policy_engine.decide(context)
    
    assert policy == DecisionPolicy.ABSTAIN, f"Expected ABSTAIN, got {policy}"
    print("PASS: test_decision_policy_abstain_all_insufficient")


# ============================================================================
# TESTS: VerifiedReasoningEngine
# ============================================================================

def test_verified_reasoning_engine_init():
    """Inicialización básica del engine."""
    engine = create_verified_reasoning_engine()
    assert engine is not None
    assert engine.deep_synthesizer is not None
    assert engine.claim_evaluator is not None
    assert engine.decision_policy is not None
    print("PASS: test_verified_reasoning_engine_init")


def test_verified_reasoning_engine_abstain_no_results():
    """Engine retorna ABSTAIN cuando no hay resultados."""
    # Mock: deep_synthesizer que retorna informe vacío
    from core.deep_synthesizer import DeepSynthesizer, InformeProfundo, HallazgoTecnico
    
    class MockSynthesizer:
        def procesar_resultados(self, query, resultados, evaluacion_global):
            return InformeProfundo(
                query="test",
                introduccion="",
                hallazgos_tecnicos=[],
                analisis_detallado="",
                conclusiones=[],
                advertencias=[],
                metricas_procesamiento={}
            )
    
    engine = create_verified_reasoning_engine(deep_synthesizer=MockSynthesizer())
    result = engine.reason("test query", [])
    
    assert result["decision"] == "abstain"
    assert "No se pudieron extraer" in result["conclusion"]
    print("PASS: test_verified_reasoning_engine_abstain_no_results")


def test_verified_reasoning_engine_basic():
    """Test básico del engine con resultados mock."""
    from core.deep_synthesizer import DeepSynthesizer, InformeProfundo, HallazgoTecnico
    
    class MockSynthesizer:
        def procesar_resultados(self, query, resultados, evaluacion_global):
            h = HallazgoTecnico(
                tipo="especificacion",
                descripcion="ARMv9 incluye MTE para seguridad de memoria",
                fuente="developer.arm.com",
                confianza=0.9,
                evidencia="ARMv9 Architecture Reference Manual"
            )
            return InformeProfundo(
                query="ARMv9 MTE",
                introduccion="Análisis de ARMv9 MTE",
                hallazgos_tecnicos=[h],
                analisis_detallado="ARMv9 incluye MTE que permite detección de memory safety bugs.",
                conclusiones=["ARMv9 incluye MTE para seguridad de memoria"],
                advertencias=[],
                metricas_procesamiento={}
            )
    
    class MockEvaluator:
        def evaluate_multiple_claims(self, claims, evidence_pool, claim_evidence_map):
            from models.contracts import ClaimEvaluation, ClaimStatus
            results = []
            for claim in claims:
                results.append(ClaimEvaluation(
                    claim=claim,
                    status="supported",
                    confidence=0.85,
                    reasoning="Fuente oficial de alta calidad",
                    supporting_evidence=[],
                    contradicting_evidence=[],
                    limitations=[]
                ))
            return results
    
    engine = create_verified_reasoning_engine(
        deep_synthesizer=MockSynthesizer(),
        claim_evaluator=MockEvaluator()
    )
    
    mock_results = [{
        'titulo': 'ARMv9 MTE Reference',
        'url': 'https://developer.arm.com/architectures/mte',
        'snippet': 'ARMv9 MTE provides hardware memory safety...',
        'fuente': 'developer.arm.com',
        'relevancia': 0.95,
        'contenido_completo': 'ARMv9 introduces MTE for hardware memory safety...',
        'autor': 'ARM Architecture Team',
        'fecha_publicacion': '2024-03-15',
    }]
    
    result = engine.reason('ARMv9 MTE architecture specification', mock_results)
    
    assert "decision" in result
    assert "conclusion" in result
    assert "claim_evaluations" in result
    assert "metrics" in result
    print(f"  Decision: {result['decision']}")
    assert result["decision"] in ["accept", "abstain"]
    print("PASS: test_verified_reasoning_engine_basic")


# ============================================================================
# TESTS: DecisionContext y metadata
# ============================================================================

def test_decision_context_metadata():
    """Verifica que metadata se construye correctamente."""
    from core.verified_reasoning import DecisionPolicyEngine, DecisionContext
    from core.deep_synthesizer import InformeProfundo, HallazgoTecnico
    from models.contracts import ClaimEvaluation, ClaimStatus
    
    evals = [
        ClaimEvaluation(claim="c1", status="supported", confidence=0.9, reasoning="test",
                       supporting_evidence=[], contradicting_evidence=[]),
        ClaimEvaluation(claim="c2", status="supported", confidence=0.8, reasoning="test",
                       supporting_evidence=[], contradicting_evidence=[]),
    ]
    
    h = HallazgoTecnico(tipo="espec", descripcion="test", fuente="test", confianza=0.9, evidencia="test")
    informe = InformeProfundo(
        query="test", introduccion="", hallazgos_tecnicos=[h],
        analisis_detallado="", conclusiones=[], advertencias=[], metricas_procesamiento={}
    )
    
    context = DecisionContext(
        query="test",
        claim_evaluations=evals,
        informe=informe,
        overall_confidence=0.85,
        high_confidence_count=2,
        contradicted_count=0,
        insufficient_count=0,
        unverified_count=0,
        total_claims=2,
    )
    
    engine = DecisionPolicyEngine()
    policy, reasoning, metadata = engine.decide(context)
    
    assert "support_ratio" in metadata
    assert "overall_confidence" in metadata
    assert metadata["support_ratio"] == 1.0
    assert metadata["overall_confidence"] == 0.85
    print("PASS: test_decision_context_metadata")


# ============================================================================
# RUN ALL TESTS
# ============================================================================

if __name__ == "__main__":
    import sys
    
    test_functions = [
        test_decision_policy_answer,
        test_decision_policy_abstain_contradiction,
        test_decision_policy_investigate,
        test_decision_policy_abstain_all_insufficient,
        test_verified_reasoning_engine_init,
        test_verified_reasoning_engine_abstain_no_results,
        test_verified_reasoning_engine_basic,
        test_decision_context_metadata,
    ]
    
    passed = 0
    failed = 0
    
    for test_func in test_functions:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"FAIL: {test_func.__name__} - {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR: {test_func.__name__} - {e}")
            failed += 1
    
    print(f"\n{'='*50}")
    print(f"Resultados: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)