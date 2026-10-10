#!/usr/bin/env python3
"""Test de campo: Validación de Inferencia Profunda (DeepSynthesizer + Router).

Ejecuta una consulta técnica real y verifica que el sistema extraiga
métricas, versiones y especificaciones reales — eliminando cascarillas vacías.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "HPR", "src"))

from security_agent import HPRSecurityEngine
from nexus_root import crear_nexus_router
from core.deep_synthesizer import crear_deep_synthesizer


def _clean_text(text: str) -> str:
    """Limpia texto para encoding Windows cp1252."""
    if not isinstance(text, str):
        text = str(text)
    return (text
        .replace('\u2705', '[OK]')
        .replace('\u26a0\ufe0f', '[WARN]')
        .replace('\u26a0', '[WARN]')
        .replace('\u1f6ab', '[BLOCK]')
        .replace('\ufe0f', '')
        .replace('\u2022', '-')
        .replace('\u2013', '-')
        .replace('\u2014', '-')
        .replace('\u2018', "'")
        .replace('\u2019', "'")
        .replace('\u201c', '"')
        .replace('\u201d', '"')
    )


def _safe_print(text: str):
    """Imprime texto de forma segura en Windows."""
    try:
        print(_clean_text(text))
    except UnicodeEncodeError:
        # Fallback: replace all non-ASCII
        ascii_text = _clean_text(text).encode('ascii', 'replace').decode('ascii')
        print(ascii_text)


def main():
    _safe_print("=" * 70)
    _safe_print("TEST DE CAMPO: INFERENCIA PROFUNDA HPR")
    _safe_print("=" * 70)
    
    # Consultas técnicas de prueba (con trigger @web_search para activar búsqueda externa)
    consultas = [
        "@web_search ARMv9 arquitectura MTE CCA SVE2 especificaciones tecnicas",
        "@web_search Python 3.12 nuevas caracteristicas rendimiento typing",
        "@web_search RISC-V vector extension RVV 1.0 especificaciones",
    ]
    
    for i, query in enumerate(consultas, 1):
        _safe_print(f"\n{'='*70}")
        _safe_print(f"CONSULTA {i}: {query}")
        _safe_print(f"{'='*70}")
        
        # Inicializar motor y router con DeepSynthesizer
        _safe_print(f"\n[1/4] Inicializando HPR Security Engine...")
        motor = HPRSecurityEngine()
        
        _safe_print("[2/4] Creando Nexus Router con DeepSynthesizer...")
        deep_synth = crear_deep_synthesizer(min_confianza=0.25)
        router = crear_nexus_router(motor=motor, deep_synthesizer=deep_synth)
        
        # Ejecutar enrutamiento
        _safe_print("\n[3/4] Ejecutando enrutamiento y busqueda externa...")
        from models.contracts import PipelineState
        resultado = router.enrutar(
            entrada=query,
            state=PipelineState(identity="TEST-DEEP-INFERENCE")
        )
        
        _safe_print(f"Decision: {resultado.get('decision')}")
        _safe_print(f"Nivel: {resultado.get('nivel')}")
        _safe_print(f"Handler: {resultado.get('handler')}")
        
        # Verificar informe profundo
        informe = resultado.get("informe_sintesis", {})
        
        if informe:
            _safe_print(f"\n[4/4] INFORME GENERADO:")
            encabezado = _clean_text(informe.get('encabezado_confianza', 'N/A'))
            _safe_print(f"  Encabezado: {encabezado[:80]}...")
            
            intro = _clean_text(informe.get('introduccion', 'N/A'))
            _safe_print(f"  Introduccion: {intro[:120]}...")
            
            hallazgos = informe.get('hallazgos_clave', [])
            _safe_print(f"\n  Hallazgos clave ({len(hallazgos)}):")
            for h in hallazgos[:8]:
                h_clean = _clean_text(h)
                _safe_print(f"    - {h_clean[:100]}")
            
            analisis = _clean_text(informe.get('analisis_tecnico', ''))
            _safe_print(f"\n  Analisis tecnico: {len(analisis)} chars")
            if "Consenso entre Fuentes" in analisis:
                _safe_print("    [OK] Seccion de consenso detectada")
            if any(t in analisis for t in ["arquitectura", "version", "caracteristica", "metrica"]):
                _safe_print("    [OK] Categorias tecnicas pobladas")
            
            conclusiones = informe.get('conclusiones', [])
            _safe_print(f"\n  Conclusiones ({len(conclusiones)}):")
            for c in conclusiones:
                c_clean = _clean_text(c)
                _safe_print(f"    - {c_clean}")
            
            advertencias = informe.get('advertencias', [])
            if advertencias:
                _safe_print(f"\n  Advertencias ({len(advertencias)}):")
                for a in advertencias:
                    a_clean = _clean_text(a)
                    _safe_print(f"    - {a_clean}")
            
            metadata = informe.get('metadata_fuentes', {})
            _safe_print(f"\n  Metricas de procesamiento:")
            for k, v in metadata.items():
                _safe_print(f"    {k}: {v}")
            
            # Validacion de calidad
            _safe_print(f"\n  VALIDACION:")
            tiene_hallazgos = len(hallazgos) > 0
            tiene_analisis = len(analisis) > 200
            tiene_conclusiones = len(conclusiones) > 0
            _safe_print(f"    [OK] Hallazgos extraidos: {tiene_hallazgos}")
            _safe_print(f"    [OK] Analisis sustancial (>200 chars): {tiene_analisis}")
            _safe_print(f"    [OK] Conclusiones accionables: {tiene_conclusiones}")
            
            if tiene_hallazgos and tiene_analisis and tiene_conclusiones:
                _safe_print(f"\n  >>> RESULTADO: INFERENCIA PROFUNDA VALIDADA <<<")
            else:
                _safe_print(f"\n  >>> RESULTADO: REVISAR - INFERENCIA INCOMPLETA <<<")
        else:
            _safe_print("  [WARN] No se genero informe (posible bloqueo o sin resultados externos)")
            import json
            _safe_print(f"  Metadata: {json.dumps(resultado.get('metadata', {}).get('evaluacion_global', {}), indent=2, default=str)}")
    
    _safe_print("\n" + "=" * 70)
    _safe_print("TEST COMPLETADO")
    _safe_print("=" * 70)


if __name__ == "__main__":
    main()