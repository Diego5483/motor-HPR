import sys
sys.path.insert(0, 'HPR/src')
from security_agent import HPRSecurityEngine
e = HPRSecurityEngine()

tests = [
    '@hpr_confianza',
    '@nivel1', 
    'consulta normal',
    '<script>malicioso</script>',
    'consulta normal sin trigger',
]

for t in tests:
    r = e.sovereign_gate_validation(t)
    print(f'sovereign_gate_validation({t!r}): {r}')