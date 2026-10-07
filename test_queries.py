import sys
sys.path.insert(0, r'C:\Users\USUARIO\Desktop\motor HPR\HPR')
from src.security_agent import HPRSecurityEngine

e = HPRSecurityEngine()

queries = [
    '¿Qué avances hay en tecnología 2024?',
    '¿Noticias sobre IA actual?',
    '¿Qué lanzar NVIDIA este año?',
]

for q in queries:
    r = e.proceso_pipeline(q, {'identity': 'HPR-CORE-DETERMINISTIC'}, [])
    print(f'Query: {q}')
    print(f'  requiere_web: {r["requiere_web"]}')
    print(f'  fuente: {r["fuente"]}')
    print(f'  nivel_confianza: {r["nivel_confianza"]}')
    print()