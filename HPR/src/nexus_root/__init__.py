# Módulo Nexus Root - Motor de Matriz de Precedencia Lógica
# Gestiona la jerarquía de decisión determinista para el motor HPR.

from .precedencia import NexusRootPrecedenceEngine
from .sanitizer import InputSanitizer
from .router import NexusRouter, crear_nexus_router

__all__ = [
    "NexusRootPrecedenceEngine",
    "InputSanitizer",
    "NexusRouter",
    "crear_nexus_router",
]