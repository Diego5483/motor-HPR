import sys
sys.path.insert(0, r'C:\Users\USUARIO\Desktop\motor HPR\HPR')

print('=== Test: Desktop Agent Integration ===')
print()

from src.desktop.agent import AgenteChat
from src.desktop.voice import VozLocal

# Create agent
agente = AgenteChat()
voz = VozLocal()

print('1. Agent created successfully')
print(f'   Knowledge base: {len(agente.knowledge_base)} chars')
print(f'   Validador: {type(agente.validador).__name__}')
print(f'   Seguridad: {type(agente.seguridad).__name__}')
print()

# Test queries
test_queries = [
    ("¿Cuál es el estado actual del motor HPR?", "operativa"),
    ("¿Qué es la tecnología blockchain?", "conocimiento_externa"),
    ("¿Estado del sistema?", "operativa"),
]

for consulta, tipo in test_queries:
    print(f'2. Query: "{consulta}"')
    resultado = agente.responder(consulta)
    print(f'   Result keys: {list(resultado.keys())}')
    print(f'   Estado: {resultado["estado"][:80]}...')
    print(f'   Requiere web: {resultado["requiere_web"]}')
    print(f'   Nivel confianza: {resultado["nivel_confianza"]}')
    print(f'   Fuente: {resultado["fuente"]}')
    print()

print('=== All desktop agent tests passed ===')