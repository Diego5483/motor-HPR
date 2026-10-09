"""Ejecutor de herramientas externas para el Nexus Root.

Separa la ejecución de efectos de lado (búsqueda web, APIs) 
del enrutamiento determinista del Nexus Root.

Principio: Enrutamiento determinista (NexusRouter) ≠ Ejecución de efectos de lado (ExternalToolExecutor)
"""

from typing import Dict, Any, Optional, List
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ResultadoBusqueda:
    """Resultado estructurado de una búsqueda externa."""
    exito: bool
    contenido: str
    fuente: str
    metadatos: Dict[str, Any]
    error: Optional[str] = None


class ExternalToolExecutor:
    """
    Ejecutor de herramientas externas desacoplado del Nexus Router.
    
    Responsabilidad única: Ejecutar efectos de lado (búsquedas, APIs)
    tras la validación determinista del Nexus Root.
    """
    
    def __init__(self):
        self._herramientas = {
            "web_search": self._ejecutar_busqueda_web,
            # Futuro: "api_call", "database_query", etc.
        }
    
    def ejecutar(
        self, 
        herramienta: str, 
        payload: str, 
        contexto: Dict[str, Any]
    ) -> ResultadoBusqueda:
        """
        Ejecuta una herramienta externa por nombre.
        
        Args:
            herramienta: Identificador ("web_search", etc.)
            payload: Query o parámetros para la herramienta
            contexto: Metadata del Nexus Router (trigger_id, peso, etc.)
            
        Returns:
            ResultadoBusqueda estructurado
        """
        if herramienta not in self._herramientas:
            return ResultadoBusqueda(
                exito=False,
                contenido="",
                fuente="",
                metadatos={},
                error=f"Herramienta desconocida: {herramienta}"
            )
        
        logger.info(f"ExternalToolExecutor: Ejecutando {herramienta} | payload='{payload[:50]}'")
        
        try:
            return self._herramientas[herramienta](payload, contexto)
        except Exception as e:
            logger.error(f"ExternalToolExecutor: Error en {herramienta} | {e}")
            return ResultadoBusqueda(
                exito=False,
                contenido="",
                fuente=herramienta,
                metadatos={},
                error=str(e)
            )
    
    def _ejecutar_busqueda_web(
        self, 
        query: str, 
        contexto: Dict[str, Any]
    ) -> ResultadoBusqueda:
        """
        Implementación de búsqueda web.
        
        MOCK DETERMINISTA para testing - Reemplazar con conector real
        (DuckDuckGo, Brave Search, Brave API, SerpAPI, etc.)
        """
        # Mock determinista para testing - Reemplazar con conector real
        contenido_mock = (
            f"[BÚSQUEDA WEB SIMULADA] Resultados para: '{query}'\n\n"
            f"1. Artículo técnico sobre {query} - Fuente: tech.example.com\n"
            f"2. Noticia reciente: Avances en {query} - Fuente: news.example.com\n"
            f"3. Paper académico: Estado del arte en {query} - Fuente: arxiv.org\n\n"
            f"[Metadatos: trigger={contexto.get('trigger', 'web_search')}, "
            f"peso={contexto.get('peso_operativo', 10)}]"
        )
        
        return ResultadoBusqueda(
            exito=True,
            contenido=contenido_mock,
            fuente="web_search_mock",
            metadatos={
                "query_original": query,
                "trigger": contexto.get("trigger"),
                "peso_operativo": contexto.get("peso_operativo"),
                "timestamp": "2026-10-09T00:00:00Z"
            }
        )


# Factoría para inyección de dependencias
def crear_executor() -> ExternalToolExecutor:
    """Factoría para crear una instancia de ExternalToolExecutor."""
    return ExternalToolExecutor()