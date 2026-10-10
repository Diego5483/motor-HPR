import sys
sys.path.insert(0, 'HPR/src')
from security_agent import HPRSecurityEngine
import re

engine = HPRSecurityEngine()

# Probar trigger @hpr_confianza
t = "@hpr_confianza"
trigger_pattern = re.match(r"^@(\S+)", t)
print(f"Trigger pattern: {trigger_pattern}")
if trigger_pattern:
    trigger_id = trigger_pattern.group(1)
    print(f"Trigger ID: {trigger_id}")
    result = engine.process_pipeline(payload=trigger_id, state={"identity": "HPR-CORE-DETERMINISTIC"}, truth=[])
    print(f"Result type: {type(result)}")
    print(f"Result: {result}")
    if result:
        print(f"Requiere externa: {result.get("requiere_externa")}")
        print(f"Estado: {result.get("estado")}")