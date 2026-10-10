#!/usr/bin/env python3
"""Test de campo: Validación de Inferencia Profunda (DeepSynthesizer + Router).

Ejecuta una consulta técnica real y verifica que el sistema extraiga
métricas, versiones y especificaciones reales — eliminando cascarillas vacías.
"""

import sys
import os
import json

# Añadir paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "HPR", "src"))

from security_agent import HPRSecurityEngine
from nexus_root import crear_nexus_router
from core.deep_synthesizer import crear_deep_synthesizer
from models.contracts import PipelineState


def main():
    print("=" * 70)
    print("TEST DE CAMPO: INFERENCIA PROFUNDA HPR")
    print("=" * 70)
    
    # Inicializar motor y router con DeepSynthesizer
    print("\n[1/4] Inicializando HPR Security Engine...")
    motor = HPRSecurityEngine()
    
    print("[2/4] Creando Nexus Router con DeepSynthesizer...")
    deep_synth = crear_deep_synthesizer(min_confianza=0.25)
    router = crear_nexus_router(motor=motor, deep_synthesizer=deep_synth)
    
    # Consultas técnicas de prueba (con trigger @web_search para activar búsqueda externa)
    consultas = [
        "@web_search ARMv9 arquitectura MTE CCA SVE2 especificaciones técnicas",
        "@web_search Python 3.12 nuevas características rendimiento typing",
        "@web_search RISC-V vector extension RVV 1.0 especificaciones",
    ]
    
    for i, query in enumerate(consultas, 1):
        print(f"\n{'='*70}")
        print(f"CONSULTA {i}: {query}")
        print(f"{'='*70}")
        
        # Ejecutar enrutamiento
        print("\n[3/4] Ejecutando enrutamiento y búsqueda externa...")
        resultado = router.enrutar(
            entrada=query,
            state=PipelineState(identity="TEST-DEEP-INFERENCE")
        )
        
        print(f"Decisión: {resultado.get('decision')}")
        print(f"Nivel: {resultado.get('nivel')}")
        print(f"Handler: {resultado.get('handler')}")
        
        # Verificar informe profundo
        informe = resultado.get("informe_sintesis", {})
        
        if informe:
            print(f"\n[4/4] INFORME GENERADO:")
            encabezado = informe.get('encabezado_confianza', 'N/A')
            # Reemplazar emojis para encoding Windows
            encabezado = encabezado.replace('\u2705', '[OK]').replace('\u26a0', '[WARN]').replace('\u1f6ab', '[BLOCK]')
            print(f"  Encabezado: {encabezado[:80]}...")
            
            intro = informe.get('introduccion', 'N/A')
            print(f"  Introduccion: {intro[:120]}...")
            
            hallazgos = informe.get('hallazgos_clave', [])
            print(f"\n  Hallazgos clave ({len(hallazgos)}):")
            for h in hallazgos[:8]:
                h_clean = h.replace('\u26a0', '[WARN]').replace('\u2705', '[OK]').replace('\u1f6ab', '[BLOCK]')
                print(f"    - {h_clean[:100]}")
            
            analisis = informe.get('analisis_tecnico', '')
            print(f"\n  Analisis tecnico: {len(analisis)} chars")
            if "Consenso entre Fuentes" in analisis:
                print("    [OK] Seccion de consenso detectada")
            if any(t in analisis for t in ["arquitectura", "version", "caracteristica", "metrica"]):
                print("    [OK] Categorias tecnicas pobladas")
            
            conclusiones = informe.get('conclusiones', [])
            print(f"\n  Conclusiones ({len(conclusiones)}):")
            for c in conclusiones:
                c_clean = c.replace('\u26a0', '[WARN]').replace('\u2705', '[OK]').replace('\u1f6ab', '[BLOCK]')
                print(f"    - {c_clean}")
            
            advertencias = informe.get('advertencias', [])
            if advertencias:
                print(f"\n  Advertencias ({len(advertencias)}):")
                for a in advertencias:
                    a_clean = a.replace('\u26a0\ufe0f', '[WARN]').replace('\u26a0', '[WARN]').replace('\u2705', '[OK]').replace('\u1f6ab', '[BLOCK]')
                    print(f"    - {a_clean}")
            
            metadata = informe.get('metadata_fuentes', {})
            print(f"\n  Metricas de procesamiento:")
            for k, v in metadata.items():
                print(f"    {k}: {v}")
            
            # Validacion de calidad
            print(f"\n  VALIDACION:")
            tiene_hallazgos = len(hallazgos) > 0
            tiene_analisis = len(analisis) > 200
            tiene_conclusiones = len(conclusiones) > 0
            print(f"    [OK] Hallazgos extraidos: {tiene_hallazgos}")
            print(f"    [OK] Analisis sustancial (>200 chars): {tiene_analisis}")
            print(f"    [OK] Conclusiones accionables: {tiene_conclusiones}")
            
            if tiene_hallazgos and tiene_analisis and tiene_conclusiones:
                print(f"\n  >>> RESULTADO: INFERENCIA PROFUNDA VALIDADA <<<")
            else:
                print(f"\n  >>> RESULTADO: REVISAR - INFERENCIA INCOMPLETA <<<")
        else:
            print("  [WARN] No se genero informe (posible bloqueo o sin resultados externos)")
            print(f"  Metadata: {json.dumps(resultado.get('metadata', {}).get('evaluacion_global', {}), indent=2, default=str)}")
    
    print("\n" + "=" * 70)
    print("TEST COMPLETADO")
    print("=" * 70)


if __name__ == "__main__":
    main()