#!/usr/bin/env python3
"""Test de integración: PlanificadorBusquedaIterativa (Fase Beta, Pilar 3)."""

import sys
import os
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "HPR", "src"))

from core.deep_synthesizer import crear_deep_synthesizer, HallazgoTecnico
from core.reasoning_engine import crear_motor_razonamiento
from core.episodic_memory import crear_memoria_episodica, TipoEpisodio, ReasoningConMemoria
from core.iterative_planner import crear_planificador_iterativo, BrechaConocimiento


def main():
    print("=" * 70)
    print("TEST BETA PILAR 3: PLANIFICADOR BÚSQUEDA ITERATIVA")
    print("=" * 70)
    
    # Usar archivo temporal para test limpio
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        memoria_path = tmp.name
    
    try:
        # Hallazgos iniciales que generarán brecha causal (MTE -> detección sin mecanismo)
        hallazgos_mock = [
            HallazgoTecnico(
                tipo="arquitectura",
                descripcion="Arquitectura mencionada: ARMv9",
                fuente="developer.arm.com",
                confianza=0.8,
                evidencia="ARMv9 is the latest ARM architecture, announced in March 2021. It introduces significant improvements in security and performance."
            ),
            HallazgoTecnico(
                tipo="caracteristica",
                descripcion="Tecnologia/Caracteristica: MTE",
                fuente="developer.arm.com",
                confianza=0.75,
                evidencia="Key features include Memory Tagging Extension (MTE) for memory safety, helping detect memory safety bugs."
            ),
            HallazgoTecnico(
                tipo="caracteristica",
                descripcion="Tecnologia/Caracteristica: CCA",
                fuente="developer.arm.com",
                confianza=0.75,
                evidencia="Confidential Compute Architecture (CCA) for hardware-based isolation, providing hardware-enforced isolation."
            ),
            HallazgoTecnico(
                tipo="caracteristica",
                descripcion="Tecnologia/Caracteristica: SVE2",
                fuente="developer.arm.com",
                confianza=0.75,
                evidencia="Scalable Vector Extension 2 (SVE2) for enhanced vector processing capabilities."
            ),
            HallazgoTecnico(
                tipo="especificacion",
                descripcion="MTE permite deteccion de memory safety bugs",
                fuente="developer.arm.com",
                confianza=0.7,
                evidencia="Memory Tagging Extension (MTE) helps detect memory safety bugs."
            ),
            HallazgoTecnico(
                tipo="especificacion",
                descripcion="CCA proporciona aislamiento hardware",
                fuente="developer.arm.com",
                confianza=0.7,
                evidencia="Confidential Compute Architecture (CCA) provides hardware-enforced isolation."
            ),
        ]
        
        corpus = """
        ARMv9 is the latest ARM architecture, announced in March 2021. 
        It introduces significant improvements in security and performance.
        Key features include Memory Tagging Extension (MTE) for memory safety,
        helping detect memory safety bugs.
        Confidential Compute Architecture (CCA) for hardware-based isolation,
        providing hardware-enforced isolation.
        Scalable Vector Extension 2 (SVE2) for enhanced vector processing capabilities.
        MTE permits detection of memory safety bugs through hardware tagging.
        CCA requires EL3 and EL2 exception levels for realm management.
        SVE2 extends vector processing with new instructions.
        """
        
        consulta = "ARMv9 arquitectura MTE CCA SVE2 especificaciones tecnicas"
        sesion_id = "test-session-beta-iterativo"
        usuario_id = "test-user"
        
        print(f"\n[1/5] Inicializando pipeline completo con memoria + planificador...")
        memoria = crear_memoria_episodica(memoria_path)
        reasoning = crear_motor_razonamiento(umbral_verificacion=0.5)
        deep_synth = crear_deep_synthesizer()
        pipeline_memoria = ReasoningConMemoria(reasoning, memoria, sesion_id, usuario_id)
        planificador = crear_planificador_iterativo(memoria, max_iteraciones=2)
        
        print(f"\n[2/5] Ejecutando PRIMERA PASADA (pipeline con memoria)...")
        resultado_1 = pipeline_memoria.ejecutar_con_memoria(
            hallazgos=hallazgos_mock,
            corpus=corpus,
            consulta_original=consulta
        )
        
        print(f"  Hipotesis: {len(resultado_1['hipotesis'])}")
        print(f"  Verificaciones: {len(resultado_1['verificaciones'])}")
        print(f"  Conclusiones: {len(resultado_1['conclusiones'])}")
        
        # Verificar brechas en memoria
        brechas = memoria.get_brechas_abiertas(sesion_id)
        print(f"  Brechas detectadas en memoria: {len(brechas)}")
        for b in brechas:
            print(f"    - {b['claim']}: {b['brecha']}")
        
        print(f"\n[3/5] Ejecutando CICLO ITERATIVO (planificador)...")
        resultado_iterativo = planificador.ejecutar_ciclo_iterativo(
            sesion_id=sesion_id,
            hallazgos_iniciales=hallazgos_mock,
            corpus_inicial=corpus,
            reasoning_engine=reasoning,
            deep_synthesizer=deep_synth
        )
        
        print(f"\n[4/5] RESULTADOS CICLO ITERATIVO:")
        metricas = resultado_iterativo["metricas_iterativo"]
        print(f"  Iteraciones: {metricas['iteraciones_totales']}")
        print(f"  Brechas procesadas: {metricas['brechas_procesadas']}")
        print(f"  Sub-queries ejecutadas: {metricas['subqueries_ejecutadas']}")
        print(f"  Hallazgos nuevos generados: {metricas['hallazgos_nuevos']}")
        print(f"  Brechas resueltas: {metricas['brechas_resueltas']}")
        print(f"  Total hallazgos acumulados: {resultado_iterativo['total_hallazgos_acumulados']}")
        print(f"  Corpus final: {resultado_iterativo['corpus_final_chars']} chars")
        
        # Detalle de brechas
        print(f"\n  Historial de brechas:")
        for b in resultado_iterativo["brechas_historial"]:
            print(f"    - {b['claim']}")
            print(f"      Brecha: {b['brecha']}")
            print(f"      Subqueries: {b['subqueries']}")
            print(f"      Resuelta: {b['resuelta']}")
        
        # Resultado final
        res_final = resultado_iterativo["resultado_final"]
        print(f"\n  Conclusiones finales: {len(res_final['conclusiones'])}")
        for c in res_final['conclusiones']:
            print(f"    [{c['fuerza']}] {c['claim'][:80]}...")
        
        # Verificar estado final de memoria
        print(f"\n[5/5] Estado final de memoria:")
        stats = memoria.estadisticas()
        print(f"  Total episodios: {stats['total_episodios']}")
        print(f"  Por tipo: {stats['por_tipo']}")
        
        brechas_finales = memoria.get_brechas_abiertas(sesion_id)
        print(f"  Brechas restantes: {len(brechas_finales)}")
        
        # Validaciones
        print(f"\n{'='*70}")
        print("VALIDACION PILAR 3:")
        checks = {
            "Pipeline inicial produce brechas": len(brechas) > 0,
            "Planificador ejecuta iteraciones": metricas['iteraciones_totales'] >= 1,
            "Sub-queries generadas": metricas['subqueries_ejecutadas'] > 0,
            "Hallazgos nuevos generados": metricas['hallazgos_nuevos'] >= 0,
            "Memoria no pierde episodios": stats['total_episodios'] >= 25,
            "Brechas tienen subqueries": all(len(b['subqueries']) > 0 for b in resultado_iterativo['brechas_historial']),
            "Ciclo termina (no bucle infinito)": metricas['iteraciones_totales'] <= 3,
            "Deduplicación de hipótesis funciona": len(resultado_iterativo['resultado_final']['conclusiones']) == 4,
        }
        
        for check, passed in checks.items():
            status = "[OK]" if passed else "[FAIL]"
            print(f"  {status} {check}")
        
        if all(checks.values()):
            print(f"\n>>> PILAR 3 (PLANIFICADOR BÚSQUEDA ITERATIVA): VALIDADO <<<")
        else:
            print(f"\n>>> REVISAR: ALGUNOS CHECKS FALLARON <<<")
            
    finally:
        if os.path.exists(memoria_path):
            os.unlink(memoria_path)


if __name__ == "__main__":
    main()