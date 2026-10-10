import sys
sys.path.insert(0, 'HPR/src')
from security_agent import HPRSecurityEngine
e = HPRSecurityEngine()
short = e.process_pipeline(payload="@hpr_confianza")
main = e.proceso_pipeline(payload="@hpr_confianza", state={"identity": "HPR-CORE-DETERMINISTIC"}, truth=[])
print(f"short: {short}")
print(f"main: {main}")