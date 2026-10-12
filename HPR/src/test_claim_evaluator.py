"""Pruebas unitarias para el Evaluador Mínimo de Afirmaciones - Fase 5."""

import sys
sys.path.insert(0, 'HPR/src')

from models.contracts import (
    Evidence, EvidenceSource, EvidenceType, ClaimStatus, ClaimEvaluation
)
from core.claim_evaluator import (
    ClaimEvaluator, create_claim_evaluator, EvaluationRule, SourceQuality,
    _classify_source_quality, _count_independent_sources, _get_unique_sources
)

# ============================================================================
# FIXTURES: Evidencia de prueba
# ============================================================================

def make_evidence(
    content: str,
    source: EvidenceSource = EvidenceSource.OFFICIAL,
    evidence_type: str = "document",
    relevance: float = 0.8,
    source_url: str = "https://example.com/doc",
    author: str = None,
) -> Evidence:
    """Factory para crear evidencia de prueba."""
    return Evidence(
        content=content,
        source=source,
        evidence_type=evidence_type,
        relevance_score=relevance,
        source_url=source_url,
        author=author,
    )


def make_official_evidence(content: str, relevance: float = 0.8, source_url: str = "https://official.gov/doc") -> Evidence:
    return make_evidence(content, EvidenceSource.OFFICIAL, "document", relevance, 
                         source_url, "Official Authority")


def make_technical_evidence(content: str, relevance: float = 0.7, source_url: str = "https://tech.example.com/doc") -> Evidence:
    return make_evidence(content, EvidenceSource.TECHNICAL, "document", relevance,
                         source_url, "Tech Author")


def make_community_evidence(content: str, relevance: float = 0.6, source_url: str = "https://community.example.com/post") -> Evidence:
    return make_evidence(content, EvidenceSource.COMMUNITY, "snippet", relevance,
                         source_url, "Community User")


def make_general_evidence(content: str, relevance: float = 0.4, source_url: str = "https://blog.example.com/post") -> Evidence:
    return make_evidence(content, EvidenceSource.GENERAL, "snippet", relevance,
                         source_url, "Blogger")


def make_internal_evidence(content: str, relevance: float = 0.5, source_url: str = None) -> Evidence:
    return make_evidence(content, EvidenceSource.INTERNAL, "document", relevance,
                         source_url, "HPR Vault")


# ============================================================================
# TESTS: Clasificación de calidad de fuente
# ============================================================================

def test_classify_source_quality_official_high():
    """Fuente oficial con alta relevancia = HIGH"""
    ev = make_official_evidence("test", 0.8)
    assert _classify_source_quality(ev) == SourceQuality.HIGH


def test_classify_source_quality_official_medium():
    """Fuente oficial con relevancia media = MEDIUM"""
    ev = make_official_evidence("test", 0.55)
    assert _classify_source_quality(ev) == SourceQuality.MEDIUM


def test_classify_source_quality_technical_medium():
    """Fuente técnica con buena relevancia = MEDIUM"""
    ev = make_technical_evidence("test", 0.65)
    assert _classify_source_quality(ev) == SourceQuality.MEDIUM


def test_classify_source_quality_community_medium():
    """Comunidad con buena relevancia = MEDIUM"""
    ev = make_community_evidence("test", 0.65)
    assert _classify_source_quality(ev) == SourceQuality.MEDIUM


def test_classify_source_quality_low():
    """General o baja relevancia = LOW"""
    ev = make_general_evidence("test", 0.4)
    assert _classify_source_quality(ev) == SourceQuality.LOW


# ============================================================================
# TESTS: Deduplicación de fuentes
# ============================================================================

def test_unique_sources_deduplication():
    """Fuentes repetidas se deduplican"""
    ev1 = make_official_evidence("content 1", 0.8)
    ev2 = make_official_evidence("content 2", 0.7)
    ev2.source_url = ev1.source_url  # Mismo dominio
    
    unique = _get_unique_sources([ev1, ev2])
    assert len(unique) == 1  # Misma fuente


def test_count_independent_sources():
    """Cuenta fuentes independientes correctamente"""
    ev1 = make_official_evidence("c1", 0.8, "https://gov1.gov/doc")
    ev2 = make_official_evidence("c2", 0.7, "https://gov2.gov/doc") 
    ev3 = make_official_evidence("c3", 0.7, "https://gov1.gov/other")  # Mismo dominio que ev1
    
    count = _count_independent_sources([ev1, ev2, ev3])
    assert count == 2  # Solo 2 dominios únicos


# ============================================================================
# TESTS: Evaluación de afirmaciones - Casos base
# ============================================================================

def test_evaluate_supported_by_single_official_high_quality():
    """Afirmación soportada por una fuente oficial de alta calidad = SUPPORTED"""
    evaluator = create_claim_evaluator()
    
    claim = "ARMv9 incluye MTE para seguridad de memoria"
    evidence = [make_official_evidence("ARMv9 incluye MTE para seguridad de memoria hardware", 0.85)]
    
    result = evaluator.evaluate_claim(claim, evidence)
    
    assert result.status == ClaimStatus.SUPPORTED
    assert result.confidence >= 0.8
    assert len(result.supporting_evidence) == 1


def test_evaluate_supported_by_multiple_independent_sources():
    """Afirmación con múltiples fuentes independientes = SUPPORTED"""
    evaluator = create_claim_evaluator()
    
    claim = "DLSS 5 usa IA para generación de frames"
    evidence = [
        make_official_evidence("DLSS 5 usa IA para frame generation", 0.8),
        make_technical_evidence("NVIDIA DLSS 5 frame generation usa redes neuronales", 0.75),
    ]
    
    result = evaluator.evaluate_claim(claim, evidence)
    
    assert result.status == ClaimStatus.SUPPORTED
    assert result.confidence >= 0.75
    assert len(result.supporting_evidence) == 2


def test_evaluate_contradicted_by_high_quality_source():
    """Afirmación contradicha por fuente de alta calidad = CONTRADICTED"""
    evaluator = create_claim_evaluator()
    
    claim = "La Tierra es plana"
    supporting = [make_general_evidence("Algunos creen que la Tierra es plana", 0.3)]
    contradicting = [make_official_evidence("La Tierra es un geoide esférico", 0.95)]
    
    result = evaluator.evaluate_claim(claim, supporting, contradicting)
    
    assert result.status == ClaimStatus.CONTRADICTED
    assert result.confidence >= 0.8
    assert len(result.contradicting_evidence) == 1


def test_evaluate_insufficient_evidence_no_support():
    """Sin evidencia de apoyo = INSUFFICIENT_EVIDENCE"""
    evaluator = create_claim_evaluator()
    
    claim = "Afirmación sin evidencia"
    evidence = []
    
    result = evaluator.evaluate_claim(claim, evidence)
    
    assert result.status == ClaimStatus.INSUFFICIENT_EVIDENCE
    assert result.confidence < 0.3


def test_evaluate_unverified_no_rules_match():
    """Sin reglas aplicables = UNVERIFIED"""
    evaluator = create_claim_evaluator(min_confidence_threshold=0.9)  # Umbral muy alto
    
    claim = "Afirmación rara"
    evidence = [make_general_evidence("Algo vago", 0.3)]
    
    result = evaluator.evaluate_claim(claim, evidence)
    
    assert result.status == ClaimStatus.UNVERIFIED
    assert result.confidence < 0.3


def test_single_repeated_source_not_independent_confirmation():
    """Una fuente repetida NO cuenta como confirmación independiente"""
    evaluator = create_claim_evaluator()
    
    claim = "Afirmación con fuente repetida"
    # Misma URL = misma fuente
    ev1 = make_official_evidence("La afirmación es cierta", 0.8, "https://official.gov/doc")
    ev2 = make_official_evidence("La afirmación es cierta", 0.8, "https://official.gov/doc")
    
    result = evaluator.evaluate_claim(claim, [ev1, ev2])
    
    # Solo 1 fuente independiente -> soporte débil
    assert result.status in (ClaimStatus.SUPPORTED, ClaimStatus.INSUFFICIENT_EVIDENCE)
    # Pero NO debe tener alta confianza por "corroboración múltiple"
    if result.status == ClaimStatus.SUPPORTED:
        assert result.confidence < 0.85  # No es strong_support con múltiples fuentes


# ============================================================================
# TESTS: Evaluación múltiple
# ============================================================================

def test_evaluate_multiple_claims():
    """Evaluación de múltiples afirmaciones"""
    evaluator = create_claim_evaluator()
    
    claims = [
        "Afirmación 1: La Tierra es redonda",
        "Afirmación 2: El agua hierve a 100°C",
    ]
    evidence_pool = [
        make_official_evidence("La Tierra es un geoide", 0.9),
        make_official_evidence("El agua hierve a 100°C a nivel del mar", 0.9),
    ]
    
    results = evaluator.evaluate_multiple_claims(claims, evidence_pool)
    
    assert len(results) == 2
    assert all(r.status == ClaimStatus.SUPPORTED for r in results)


def test_evaluate_multiple_claims_with_map():
    """Evaluación múltiple con mapeo claim -> evidencia"""
    evaluator = create_claim_evaluator()
    
    claims = ["Claim A", "Claim B"]
    e1 = make_official_evidence("Evidencia para A", 0.9)
    e2 = make_official_evidence("Evidencia para B", 0.9)
    evidence_pool = [e1, e2]
    
    claim_evidence_map = {
        "Claim A": [e1.id],
        "Claim B": [e2.id],
    }
    
    results = evaluator.evaluate_multiple_claims(claims, evidence_pool, claim_evidence_map)
    
    assert len(results) == 2
    assert results[0].status == ClaimStatus.SUPPORTED
    assert results[1].status == ClaimStatus.SUPPORTED
    assert e1.id in results[0].supporting_evidence
    assert e2.id in results[1].supporting_evidence


def test_limitations_generated():
    """Se generan limitaciones apropiadas"""
    evaluator = create_claim_evaluator()
    
    claim = "Test claim"
    evidence = [make_general_evidence("Fuente general", 0.4)]
    
    result = evaluator.evaluate_claim(claim, evidence)
    
    assert len(result.limitations) > 0
    # Debe mencionar fuente de baja calidad o fuente única
    limitation_text = " ".join(result.limitations).lower()
    assert any(kw in limitation_text for kw in ["baja calidad", "única", "interna"])


def test_internal_source_limitation():
    """Evidencia solo interna genera limitación"""
    evaluator = create_claim_evaluator()
    
    claim = "Afirmación interna"
    evidence = [make_internal_evidence("Solo en bóveda HPR", 0.7)]
    
    result = evaluator.evaluate_claim(claim, evidence)
    
    limitation_text = " ".join(result.limitations).lower()
    assert "interna" in limitation_text or "bóveda" in limitation_text


def test_contradiction_with_low_quality_source():
    """Contradicción con fuente de baja calidad = menor confianza"""
    evaluator = create_claim_evaluator()
    
    claim = "Afirmación dudosa"
    supporting = [make_official_evidence("La afirmación es cierta", 0.8)]
    contradicting = [make_general_evidence("No es cierta", 0.3)]  # Baja calidad
    
    result = evaluator.evaluate_claim(claim, supporting, contradicting)
    
    # Debe detectar contradicción pero con menor confianza
    assert result.status == ClaimStatus.CONTRADICTED
    assert result.confidence < 0.8  # Menor que contradicción con fuente alta


# ============================================================================
# TESTS: Reglas personalizadas
# ============================================================================

def test_custom_rules():
    """Reglas de evaluación personalizadas"""
    custom_rules = [
        EvaluationRule(
            name="custom_strict",
            description="Regla estricta personalizada",
            min_supporting_sources=3,
            min_source_quality=SourceQuality.HIGH,
            require_corroboration=True,
            allow_single_high_quality=False,
        )
    ]
    
    evaluator = ClaimEvaluator(rules=custom_rules, min_confidence_threshold=0.6)
    
    claim = "Afirmación que necesita 3 fuentes oficiales"
    evidence = [
        make_official_evidence("Apoyo 1", 0.8),
        make_official_evidence("Apoyo 2", 0.8),
    ]
    
    result = evaluator.evaluate_claim(claim, evidence)
    
    # No cumple regla estricta (necesita 3 fuentes HIGH)
    assert result.status in (ClaimStatus.INSUFFICIENT_EVIDENCE, ClaimStatus.UNVERIFIED)


if __name__ == "__main__":
    # Ejecutar tests manualmente sin pytest.main() para evitar conflictos de config
    import sys
    
    test_functions = [
        test_classify_source_quality_official_high,
        test_classify_source_quality_official_medium,
        test_classify_source_quality_technical_medium,
        test_classify_source_quality_community_medium,
        test_classify_source_quality_low,
        test_unique_sources_deduplication,
        test_count_independent_sources,
        test_evaluate_supported_by_single_official_high_quality,
        test_evaluate_supported_by_multiple_independent_sources,
        test_evaluate_contradicted_by_high_quality_source,
        test_evaluate_insufficient_evidence_no_support,
        test_evaluate_unverified_no_rules_match,
        test_single_repeated_source_not_independent_confirmation,
        test_evaluate_multiple_claims,
        test_evaluate_multiple_claims_with_map,
        test_limitations_generated,
        test_internal_source_limitation,
        test_contradiction_with_low_quality_source,
        test_custom_rules,
    ]
    
    passed = 0
    failed = 0
    
    for test_func in test_functions:
        try:
            test_func()
            print(f"PASS: {test_func.__name__}")
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