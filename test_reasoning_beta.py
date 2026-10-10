#!/usr/bin/env python3
"""Test de integracion: DeepSynthesizer -> MotorRazonamientoSuperior (Fase Beta)."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "HPR", "src"))

from core.deep_synthesizer import crear_deep_synthesizer, HallazgoTecnico
from core.reasoning_engine import crear_motor_razonamiento


def main():
    print("=" * 70)
    print("TEST BETA: DEEP SYNTHESIZER -> MOTOR RAZONAMIENTO SUPERIOR")
    print("=" * 70)
    
    # Simular hallazgos del DeepSynthesizer (como los que produjo el test ARMv9)
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
    
    # Corpus de evidencia (simulado del contenido completo)
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
    
    print(f"\n[1/4] Hallazgos de entrada: {len(hallazgos_mock)}")
    for h in hallazgos_mock:
        print(f"  - [{h.tipo}] {h.descripcion} (conf: {h.confianza:.0%})")
    
    # Crear motores
    print("\n[2/4] Inicializando motores...")
    deep_synth = crear_deep_synthesizer()
    reasoning = crear_motor_razonamiento(umbral_verificacion=0.5)
    
    # Ejecutar pipeline completo
    print("\n[3/4] Ejecutando pipeline de razonamiento...")
    resultado = reasoning.ejecutar_pipeline_completo(hallazgos_mock, corpus)
    
    # Mostrar resultados
    print("\n[4/4] RESULTADOS DEL PIPELINE BETA")
    print("=" * 70)
    
    print(f"\nMetricas globales:")
    m = resultado["metricas"]
    print(f"  Premisas: {m['total_premisas']}")
    print(f"  Hipotesis generadas: {m['total_hipotesis']}")
    print(f"  Verificadas: {m['verificadas']} | Refutadas: {m['refutadas']} | Parciales: {m['parciales']} | Indeterminadas: {m['indeterminadas']}")
    print(f"  Fuerza promedio: {m['fuerza_promedio']:.2f}")
    
    print(f"\n--- PREMISAS REGISTRADAS ({len(resultado['premisas'])}) ---")
    for p in resultado["premisas"]:
        print(f"  {p['id']}: {p['proposicion']} | entidades: {p['entidades']}")
    
    print(f"\n--- HIPOTESIS GENERADAS ({len(resultado['hipotesis'])}) ---")
    for h in resultado["hipotesis"]:
        claim = h['claim'].replace('\u2192', '->').replace('\u2190', '<-')
        pred = h['prediccion'].replace('\u2192', '->').replace('\u2190', '<-')
        print(f"  {h['id']} [{h['tipo'].upper()}]: {claim}")
        print(f"      Premisas: {h['premisas']}")
        print(f"      Prediccion: {pred[:80]}...")
        print(f"      Confianza inicial: {h['confianza_inicial']:.2f}")
    
    print(f"\n--- VERIFICACIONES ({len(resultado['verificaciones'])}) ---")
    for v in resultado["verificaciones"]:
        estado = v['estado'].upper()
        brechas = [b.replace('\u2192', '->').replace('\u2190', '<-') for b in v['brechas']]
        print(f"  {v['hipotesis_id']}: {estado} (score: {v['puntuacion']:.2f})")
        print(f"      Soporte: {v['soporte']} | Contra: {v['contra']}")
        if brechas:
            print(f"      Brechas: {brechas}")
    
    print(f"\n--- CONCLUSIONES VERIFICADAS ({len(resultado['conclusiones'])}) ---")
    for c in resultado["conclusiones"]:
        claim = c['claim'].replace('\u2192', '->').replace('\u2190', '<-')
        print(f"  [{c['fuerza'].upper()}] {claim}")
        print(f"      Estado: {c['estado']} | Score: {c['puntuacion']:.2f}")
        for imp in c['implicaciones']:
            imp_clean = imp.replace('\u2192', '->').replace('\u2190', '<-')
            print(f"      -> {imp_clean}")
    
    # Validacion de calidad
    print(f"\n{'='*70}")
    print("VALIDACION BETA:")
    checks = {
        "Premisas desde hallazgos": m["total_premisas"] == len(hallazgos_mock),
        "Hipotesis generadas > 0": m["total_hipotesis"] > 0,
        "Al menos una verificada": m["verificadas"] > 0,
        "Conclusiones con implicaciones": all(len(c["implicaciones"]) > 0 for c in resultado["conclusiones"]),
        "Trazabilidad completa": all("id" in p for p in resultado["premisas"]) and all("id" in h for h in resultado["hipotesis"]),
    }
    
    for check, passed in checks.items():
        status = "[OK]" if passed else "[FAIL]"
        print(f"  {status} {check}")
    
    if all(checks.values()):
        print(f"\n>>> FASE BETA (Punto 1): CAPA DE RAZONAMIENTO SUPERIOR VALIDADA <<<")
    else:
        print(f"\n>>> REVISAR: ALGUNOS CHECKS FALLARON <<<")


if __name__ == "__main__":
    main()