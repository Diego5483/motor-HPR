import sys
sys.path.insert(0, 'HPR/src')
from security_agent import HPRSecurityEngine
e = HPRSecurityEngine()
r = e.process_pipeline(payload="@hpr_confianza", state={"identity": "HPR-CORE-DETERMINISTIC"}, truth=[])
print(f"process_pipeline result: {r}")