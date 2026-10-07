import sys
import os

# Add the src directory to path
sys.path.insert(0, os.path.join(os.path.dirname('.'), 'HPR', 'src'))

from src.desktop.agent import AgenteChat

# Test with some knowledge base
agente = AgenteChat(knowledge_base="")

# Test 1: CONOCIMIENTO interno
print("Test 1 - Bóveda interna con respuesta:")
resultado = agente.responder("¿Qué es HPR?")
print(f"  Resultado: {resultado[:100]}...")
print()

# Test 2: CONOCIMIENTO no interno (web search placeholder)
print("Test 2 - Bóveda sin respuesta (web search placeholder):")
resultado = agente.responder("¿Quién es el CEO de HPR?")
print(f"  Resultado: {resultado[:150]}...")
print()

# Test 3: Consulta operativa
print("Test 3 - Consulta operativa:")
resultado = agente.responder("¿Cómo estás?")
print(f"  Resultado: {resultado[:100]}...")
print()