import sys
sys.path.insert(0, 'HPR/src')
from security_agent import HPRSecurityEngine
import re

engine = HPRSecurityEngine()

# Probar triggers @
test_triggers = [
    '@hpr_confianza',
    '@nivel1', 
    '@web_search',
    'consulta normal',
]

for t in test_triggers:
    # Simular lo que hace la UI: extraer trigger si comienza con @
    trigger_pattern = re.match(r'^@(\S+)', t)
    if trigger_pattern:
        trigger_id = trigger_pattern.group(1)
        result = engine.process_pipeline(payload=trigger_id, state={'identity': 'HPR-CORE-DETERMINISTIC'}, truth=[])
        # DEFENSA NoneType: si el pipeline devolvió None, usar valor por defecto
        if result is None:
            print(f'Trigger @{trigger_id}: resultado=None | fallback=Sin respuesta del motor')
        elif isinstance(result, dict):
            print(f'Trigger @{trigger_id}: requiere_externa={result.get("requiere_externa", "N/A")}, estado={result.get("estado", "Sin respuesta")[:50]}...')
        else:
            print(f'Trigger @{trigger_id}: tipo_inesperado={type(result).__name__} | valor={str(result)[:50]}...')
    else:
        print(f'Entrada normal: "{t}"')