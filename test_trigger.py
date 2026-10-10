import sys
sys.path.insert(0, 'HPR/src')
from core.engine import evaluar_intencion_externa, TRIGGER_ARROBA_PATTERN

# Probar el patrón trigger
tests = [
    "@hpr_confianza",
    "busca información @hpr_confianza",
    "@nivel1",
    "sin trigger aquí",
]

for t in tests:
    match = TRIGGER_ARROBA_PATTERN.search(t)
    print(f'Trigger en "{t}": {match.group(0) if match else None}')

# Probar el evaluador de intenciones con triggers
queries = [
    "@hpr_confianza",
    "Basándose en los tres niveles de confianza del sistema HPR, busca y explica qué es el sistema SQL",
    "Qué es el sistema SQL y para qué sirve",
]

knowledge_base = ""

for q in queries:
    result = evaluar_intencion_externa(q, knowledge_base)
    print(f'\nQUERY: {q[:60]}...')
    print(f'  requiere_externa={result["requiere_externa"]}, riesgo={result["nivel_riesgo"]}, justif={result["justificación"][:50]}...')