#!/usr/bin/env python
"""Debug script to trace the pipeline flow."""

import sys
sys.path.insert(0, "HPR/src")

from core.engine import (
    sovereign_gate_validation, 
    nexus_root_validation, 
    evaluar_intencion_externa,
    triage_query
)
from models.contracts import IDENTIDAD_DETERMINISTA
from validador_niveles_confianza import ValidadorNivelesConfianza

print("=" * 60)
print("TEST 1: Sovereign Gate validation")
print("=" * 60)
q1 = "busca información de lo que es el sistema SQL"
q2 = "Basándote en los tres niveles de confianza del sistema HPR, busca y explica qué es el sistema SQL"

print(f"Q1 - '{q1}': {sovereign_gate_validation(q1)}")
print(f"Q2 - '{q2}': {sovereign_gate_validation(q2)}")

print("\n" + "=" * 60)
print("TEST 2: evaluar_intencion_externa")
print("=" * 60)
r1 = evaluar_intencion_externa(q1, "")
print(f"Q1: requiere_externa={r1['requiere_externa']}, nivel_riesgo={r1['nivel_riesgo']}, justif={r1['justificación']}")

r2 = evaluar_intencion_externa(q2, "")
print(f"Q2: requiere_externa={r2['requiere_externa']}, nivel_riesgo={r2['nivel_riesgo']}, justif={r2['justificación']}")

print("\n" + "=" * 60)
print("TEST 3: nexus_root_validation")
print("=" * 60)
state = {"identity": IDENTIDAD_DETERMINISTA}
print(f"Q1 valido: {nexus_root_validation(state)}")
print(f"Q2 valido: {nexus_root_validation(state)}")

print("\n" + "=" * 60)
print("TEST 4: triage_query")
print("=" * 60)
from models.contracts import TriageResult, CategoriaConsulta
t1 = triage_query(q1, "")
print(f"Q1: categoria={t1.categoria}, nivel_riesgo={t1.nivel_riesgo}, razones={t1.razones}")

t2 = triage_query(q2, "")
print(f"Q2: categoria={t2.categoria}, nivel_riesgo={t2.nivel_riesgo}, razones={t2.razones}")

print("\n" + "=" * 60)
print("TEST 5: ValidadorNivelesConfianza")
print("=" * 60)
validador = ValidadorNivelesConfianza()
# Prueba con un resultado web simulado
test_result = validador.clasificar_fuente("web_search", "SQL es un sistema de gestión de bases de datos")
print(f"Clasificación: nivel={test_result['nivel']}, etiqueta={test_result['etiqueta']}, estado={test_result['estado']}")

print("\n" + "=" * 60)
print("CONCLUSIONES PARA EL DIAGNÓSTICO")
print("=" * 60)
print("Si Q1 y Q2 pasan Sovereign Gate y retornan requiere_externa=True,")
print("entonces el problema está en el pipeline posterior, no en el gate.")
print("Si falla nexus_root_validation, el pipeline 'passa' pero continúa.")
print("Si triage_query clasifica correctamente, el problema está en")
print("la ramificación CONOCIMIENTO -> sin pasaje -> _ejecutar_busqueda_web")