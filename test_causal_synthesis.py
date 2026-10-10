#!/usr/bin/env python3
"""Test de integración: SintesisCausal (Fase Beta, Pilar 4)."""

import sys
import os
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "HPR", "src"))

from core.deep_synthesizer import crear_deep_synthesizer, HallazgoTecnico
from core.reasoning_engine import crear_motor_razonamiento
from core.reasoning_engine import crear_motor_razonamiento
from core.episodic_memory import crear_memoria_episodica, TipoEpisodio, ReasoningConMemoria
from core.iterative_planner import crear_planificador_iterativo
from core.causal_synthesis import crear_sintesis_causal


def main():
    print("=" * 70)
    print("TEST BETA PILAR 4: SÍNTESIS CAUSAL")
    print("=" * 70)
    
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        memoria_path = tmp.name
    
    try:
        # Hallazgos que generarán múltiples hipótesis verificadas
        hallazgos_mock = [
            HallazgoTecnico(
                tipo="arquitectura",
                descripcion="Arquitectura mencionada: ARMv9",
                fuente="developer.arm.com",
                confianza=0.85,
                evidencia="ARMv9 is the latest ARM architecture, announced in March 2021. It introduces significant improvements in security and performance."
            ),
            HallazgoTecnico(
                tipo="caracteristica",
                descripcion="Tecnologia/Caracteristica: MTE",
                fuente="developer.arm.com",
                confianza=0.8,
                evidencia="Key features include Memory Tagging Extension (MTE) for memory safety, helping detect memory safety bugs through hardware tagging."
            ),
            HallazgoTecnico(
                tipo="caracteristica",
                descripcion="Tecnologia/Caracteristica: CCA",
                fuente="developer.arm.com",
                confianza=0.8,
                evidencia="Confidential Compute Architecture (CCA) for hardware-based isolation, providing hardware-enforced isolation with realms."
            ),
            HallazgoTecnico(
                tipo="caracteristica",
                descripcion="Tecnologia/Caracteristica: SVE2",
                fuente="developer.arm.com",
                confianza=0.8,
                evidencia="Scalable Vector Extension 2 (SVE2) for enhanced vector processing capabilities."
            ),
            HallazgoTecnico(
                tipo="especificacion",
                descripcion="MTE permite deteccion de memory safety bugs",
                fuente="developer.arm.com",
                confianza=0.75,
                evidencia="Memory Tagging Extension (MTE) helps detect memory safety bugs through hardware tagging mechanism."
            ),
            HallazgoTecnico(
                tipo="especificacion",
                descripcion="CCA proporciona aislamiento hardware",
                fuente="developer.arm.com",
                confianza=0.75,
                evidencia="Confidential Compute Architecture (CCA) provides hardware-enforced isolation with realms for confidential computing."
            ),
            HallazgoTecnico(
                tipo="especificacion",
                descripcion="ARMv9 requiere EL3 para CCA",
                fuente="developer.arm.com",
                confianza=0.8,
                evidencia="CCA requires EL3 and EL2 exception levels for realm management and secure partitioning."
            ),
        ]
        
        corpus = """
        ARMv9 is the latest ARM architecture, announced in March 2021. 
        It introduces significant improvements in security and performance.
        Key features include Memory Tagging Extension (MTE) for memory safety,
        helping detect memory safety bugs through hardware tagging.
        Confidential Compute Architecture (CCA) for hardware-based isolation,
        providing hardware-enforced isolation with realms.
        Scalable Vector Extension 2 (SVE2) for enhanced vector processing capabilities.
        MTE permits detection of memory safety bugs through hardware tagging mechanism.
        CCA provides hardware-enforced isolation with realms for confidential computing.
        CCA requires EL3 and EL2 exception levels for realm management and secure partitioning.
        SVE2 extends vector processing with new instructions for machine learning workloads.
        """
        
        consulta = "ARMv9 arquitectura MTE CCA SVE2 especificaciones tecnicas"
        sesion_id = "test-session-beta-causal"
        usuario_id = "test-user"
        
        print(f"\n[1/6] Inicializando pipeline completo (memoria + iterativo + causal)...")
        memoria = crear_memoria_episodica(memoria_path)
        reasoning = crear_motor_razonamiento(umbral_verificacion=0.5)
        deep_synth = crear_deep_synthesizer()
        pipeline_memoria = ReasoningConMemoria(reasoning, memoria, sesion_id, usuario_id)
        planificador = crear_planificador_iterativo(memoria, max_iteraciones=2)
        sintesis_causal = crear_sintesis_causal(memoria, umbral_fuerza="moderada")
        
        print(f"\n[2/6] Ejecutando pipeline con memoria + planificador iterativo...")
        resultado_iterativo = planificador.ejecutar_ciclo_iterativo(
            sesion_id=sesion_id,
            hallazgos_iniciales=hallazgos_mock,
            corpus_inicial=corpus,
            reasoning_engine=reasoning,
            deep_synthesizer=deep_synth
        )
        
        print(f"  Iteraciones: {resultado_iterativo['metricas_iterativo']['iteraciones_totales']}")
        print(f"  Hallazgos acumulados: {resultado_iterativo['total_hallazgos_acumulados']}")
        print(f"  Conclusiones finales: {len(resultado_iterativo['resultado_final']['conclusiones'])}")
        
        # Verificar conclusiones en memoria
        conclusiones_mem = memoria.get_conclusiones_sesion(sesion_id)
        print(f"\n[3/6] Conclusiones en memoria: {len(conclusiones_mem)}")
        for c in conclusiones_mem:
            print(f"  [{c['fuerza']}] {c['claim'][:80]}... (score: {c['puntuacion']:.2f})")
        
        print(f"\n[4/6] Ejecutando PASADA FINAL via ReasoningConMemoria para persistir conclusiones...")
        # Usar hallazgos acumulados del ciclo iterativo
        hallazgos_finales = []
        # Recuperar hallazgos del resultado iterativo
        for h_dict in resultado_iterativo['resultado_final']['premisas']:
            hallazgos_finales.append(HallazgoTecnico(
                tipo=h_dict.get('tipo', 'especificacion'),
                descripcion=h_dict.get('proposicion', ''),
                fuente=h_dict.get('fuente', 'iterativa'),
                confianza=h_dict.get('confianza', 0.7),
                evidencia=h_dict.get('evidencia', '')
            ))
        
        # corpus_final_chars es int, usar corpus original + hallazgos nuevos
        corpus_final = corpus  # usar corpus original
        
        resultado_final_memoria = pipeline_memoria.ejecutar_con_memoria(
            hallazgos=hallazgos_finales,
            corpus=corpus_final,
            consulta_original=consulta
        )
        
        print(f"  Conclusiones persistidas: {len(resultado_final_memoria['conclusiones'])}")
        
        print(f"\n[5/6] Ejecutando SÍNTESIS CAUSAL...")
        resultado_causal = sintesis_causal.ejecutar_sintesis(sesion_id)
        
        if "error" in resultado_causal:
            print(f"  ERROR: {resultado_causal['error']}")
            return
        
        grafo = resultado_causal["grafo"]
        narrativa = resultado_causal["narrativa_completa"]
        resumen = resultado_causal["resumen_ejecutivo"]
        
        print(f"\n[5/6] RESULTADOS SÍNTESIS CAUSAL:")
        print(f"  Nodos: {grafo['metricas']['total_nodos']}")
        print(f"  Aristas: {grafo['metricas']['total_aristas']}")
        print(f"  Cadenas: {grafo['metricas']['total_cadenas']}")
        print(f"  Entidades únicas: {grafo['metricas']['entidades_unicas']}")
        print(f"  Nodos por fuerza: {grafo['metricas']['nodos_por_fuerza']}")
        print(f"  Aristas por tipo: {grafo['metricas']['aristas_por_tipo']}")
        
        print(f"\n  Resumen ejecutivo: {resumen}")
        
        # Mostrar cadenas
        if grafo.get("cadenas"):
            print(f"\n  Cadenas causales ({len(grafo['cadenas'])}):")
            for i, c in enumerate(grafo["cadenas"], 1):
                print(f"    {i}. {c['narrativa'][:100]}...")
                print(f"       Fuerza: {c['fuerza']:.0%} | Nodos: {len(c['nodos'])}")
        
        # Mostrar narrativa completa (truncada)
        print(f"\n[6/6] NARRATIVA GENERADA (primeras 500 chars):")
        print(narrativa[:500] + "...")
        
        # Validaciones
        print(f"\n{'='*70}")
        print("VALIDACION PILAR 4:")
        checks = {
            "Grafo construido con nodos": grafo['metricas']['total_nodos'] >= 3,
            "Aristas causales detectadas": grafo['metricas']['total_aristas'] >= 2,
            "Cadenas causales extraídas": grafo['metricas']['total_cadenas'] >= 1,
            "Narrativa generada no vacía": len(narrativa) > 200,
            "Resumen ejecutivo presente": len(resumen) > 20,
            "Entidades técnicas extraídas": len(grafo['metricas']['entidades_unicas']) >= 3,
            "Métricas completas": all(k in grafo['metricas'] for k in [
                'total_nodos', 'total_aristas', 'total_cadenas', 'nodos_por_fuerza'
            ]),
            "Persistencia en memoria": os.path.exists(memoria_path),
        }
        
        for check, passed in checks.items():
            status = "[OK]" if passed else "[FAIL]"
            print(f"  {status} {check}")
        
        if all(checks.values()):
            print(f"\n>>> PILAR 4 (SÍNTESIS CAUSAL): VALIDADO <<<")
        else:
            print(f"\n>>> REVISAR: ALGUNOS CHECKS FALLARON <<<")
            
    finally:
        if os.path.exists(memoria_path):
            os.unlink(memoria_path)


if __name__ == "__main__":
    main()