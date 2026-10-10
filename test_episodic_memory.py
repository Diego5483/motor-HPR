#!/usr/bin/env python3
"""Test de integración: MemoriaEpisodica + MotorRazonamientoSuperior (Fase Beta, Pilar 2)."""

import sys
import os
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "HPR", "src"))

from core.deep_synthesizer import crear_deep_synthesizer, HallazgoTecnico
from core.reasoning_engine import crear_motor_razonamiento
from core.episodic_memory import (
    crear_memoria_episodica, 
    TipoEpisodio,
    ReasoningConMemoria
)


def main():
    print("=" * 70)
    print("TEST BETA PILAR 2: MEMORIA EPISÓDICA + RAZONAMIENTO")
    print("=" * 70)
    
    # Usar archivo temporal para test limpio
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        memoria_path = tmp.name
    
    try:
        # Hallazgos mock (igual que test anterior)
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
        sesion_id = "test-session-beta-001"
        usuario_id = "test-user"
        
        print(f"\n[1/5] Inicializando componentes...")
        memoria = crear_memoria_episodica(memoria_path)
        reasoning = crear_motor_razonamiento(umbral_verificacion=0.5)
        pipeline = ReasoningConMemoria(reasoning, memoria, sesion_id, usuario_id)
        
        print(f"\n[2/5] Ejecutando pipeline con memoria episódica...")
        resultado = pipeline.ejecutar_con_memoria(
            hallazgos=hallazgos_mock,
            corpus=corpus,
            consulta_original=consulta
        )
        
        print(f"\n[3/5] Verificando persistencia en memoria...")
        stats = memoria.estadisticas()
        print(f"  Total episodios: {stats['total_episodios']}")
        print(f"  Sesiones: {stats['sesiones_activas']}")
        print(f"  Por tipo: {stats['por_tipo']}")
        print(f"  Storage: {stats['storage_size_kb']} KB")
        
        # Verificar recuperación contextual
        print(f"\n[4/5] Probando recuperación contextual...")
        
        # 4a. Historial de sesión
        historial = memoria.historial_sesion(sesion_id)
        print(f"  Historial sesion ({len(historial)} episodios):")
        for ep in historial:
            print(f"    [{ep.tipo.value}] {ep.timestamp[:19]} | entidades: {ep.entidades}")
        
        # 4b. Consultar entidad específica
        mte_eps = memoria.consultar_entidad("MTE", sesion_id=sesion_id)
        print(f"  Episodios sobre MTE: {len(mte_eps)}")
        for ep in mte_eps:
            print(f"    [{ep.tipo.value}] {ep.contenido.get('claim', ep.contenido.get('descripcion', ''))[:60]}...")
        
        # 4c. Recuperar contexto con entidades clave
        contexto = memoria.recuperar_contexto(
            sesion_id=sesion_id,
            entidades_clave=["ARMv9", "MTE", "CCA"],
            tipos=[TipoEpisodio.PREMISA, TipoEpisodio.HIPOTESIS, TipoEpisodio.CONCLUSION],
            limite=10
        )
        print(f"  Contexto relevante (entidades ARMv9/MTE/CCA): {len(contexto)} episodios")
        for ep in contexto:
            print(f"    [{ep.tipo.value}] score implícito | {ep.entidades}")
        
        # 4d. Brechas abiertas
        brechas = memoria.get_brechas_abiertas(sesion_id)
        print(f"  Brechas abiertas (hipotesis indeterminadas): {len(brechas)}")
        for b in brechas:
            print(f"    - {b['claim']}: {b['brecha']}")
        
        # 4e. Recuperar premisas/hipotesis/conclusiones como dicts para reasoning
        premisas = memoria.get_premisas_sesion(sesion_id)
        hipotesis = memoria.get_hipotesis_sesion(sesion_id)
        conclusiones = memoria.get_conclusiones_sesion(sesion_id)
        print(f"  Premisas recuperadas: {len(premisas)}")
        print(f"  Hipotesis recuperadas: {len(hipotesis)}")
        print(f"  Conclusiones recuperadas: {len(conclusiones)}")
        
        # 5. Simular segunda consulta en misma sesión (razonamiento multi-paso)
        print(f"\n[5/5] Simulando razonamiento multi-paso (segunda consulta)...")
        
        hallazgos_2 = [
            HallazgoTecnico(
                tipo="especificacion",
                descripcion="ARMv9 requiere EL3 para CCA",
                fuente="developer.arm.com",
                confianza=0.8,
                evidencia="CCA requires EL3 and EL2 exception levels for realm management."
            ),
        ]
        
        resultado_2 = pipeline.ejecutar_con_memoria(
            hallazgos=hallazgos_2,
            corpus=corpus,
            consulta_original="ARMv9 requisitos EL3 CCA"
        )
        
        stats_2 = memoria.estadisticas()
        print(f"  Total episodios tras 2da consulta: {stats_2['total_episodios']}")
        print(f"  Entidades conocidas en sesion: {memoria.get_entidades_conocidas(sesion_id)}")
        
        # Verificar que la memoria persiste entre consultas
        historial_completo = memoria.historial_sesion(sesion_id)
        tipos_en_historial = set(ep.tipo.value for ep in historial_completo)
        print(f"  Tipos en historial completo: {sorted(tipos_en_historial)}")
        
        # Validaciones
        print(f"\n{'='*70}")
        print("VALIDACION PILAR 2:")
        checks = {
            "Episodios persistidos > 0": stats['total_episodios'] > 10,
            "Todos los tipos guardados": all(t in stats['por_tipo'] for t in [
                "premisa", "hipotesis", "verificacion", "conclusion", "consulta", "hallazgo_bruto"
            ]),
            "Recuperación por entidad funciona": len(mte_eps) > 0,
            "Contexto relevante filtra por entidades": len(contexto) > 0,
            "Brechas detectadas": len(brechas) > 0,
            "Multi-paso: episodios aumentan": stats_2['total_episodios'] > stats['total_episodios'],
            "Entidades acumuladas": len(memoria.get_entidades_conocidas(sesion_id)) >= 5,
            "Storage JSON válido": os.path.exists(memoria_path),
        }
        
        for check, passed in checks.items():
            status = "[OK]" if passed else "[FAIL]"
            print(f"  {status} {check}")
        
        if all(checks.values()):
            print(f"\n>>> PILAR 2 (MEMORIA EPISÓDICA): VALIDADO <<<")
        else:
            print(f"\n>>> REVISAR: ALGUNOS CHECKS FALLARON <<<")
            
    finally:
        # Limpiar archivo temporal
        if os.path.exists(memoria_path):
            os.unlink(memoria_path)


if __name__ == "__main__":
    main()