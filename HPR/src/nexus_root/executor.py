"""Ejecutor de herramientas externas para el Nexus Root.

Separa la ejecución de efectos de lado (búsqueda web, APIs) 
del enrutamiento determinista del Nexus Root.

Principio: Enrutamiento determinista (NexusRouter) ≠ Ejecución de efectos de lado (ExternalToolExecutor)

Integración real: DuckDuckGo HTML scraping + síntesis de contenido.
"""

from typing import Dict, Any, Optional, List
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import quote_plus, urljoin

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class ResultadoItem:
    """Un resultado individual de búsqueda con análisis."""
    titulo: str
    url: str
    snippet: str
    fuente: str
    relevancia: float = 1.0
    contenido_completo: Optional[str] = None
    metadatos_extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResultadoBusqueda:
    """Resultado estructurado y analizado de una búsqueda externa."""
    exito: bool
    query_original: str
    sintesis: str                          # Síntesis ejecutiva de hallazgos
    resultados: List[ResultadoItem]        # Resultados individuales desglosados
    fuente: str                            # Motor de búsqueda usado
    metadatos: Dict[str, Any]              # Metadatos de la búsqueda
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    def to_dict(self) -> Dict[str, Any]:
        """Serializa a diccionario para logging/JSON."""
        return {
            "exito": self.exito,
            "query_original": self.query_original,
            "sintesis": self.sintesis,
            "resultados": [
                {
                    "titulo": r.titulo,
                    "url": r.url,
                    "snippet": r.snippet,
                    "fuente": r.fuente,
                    "relevancia": r.relevancia,
                    "contenido_completo": r.contenido_completo[:500] if r.contenido_completo else None,
                    "metadatos_extra": r.metadatos_extra
                }
                for r in self.resultados
            ],
            "fuente": self.fuente,
            "metadatos": self.metadatos,
            "error": self.error,
            "timestamp": self.timestamp
        }


class ExternalToolExecutor:
    """
    Ejecutor de herramientas externas desacoplado del Nexus Router.
    
    Responsabilidad única: Ejecutar efectos de lado (búsquedas, APIs)
    tras la validación determinista del Nexus Root.
    
    Implementación actual: DuckDuckGo HTML scraping con síntesis de contenido.
    """
    
    # Configuración de timeouts y límites
    REQUEST_TIMEOUT = 15
    MAX_RESULTADOS = 5
    MAX_CONTENT_LENGTH = 8000
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    
    # DuckDuckGo endpoints
    DDG_HTML_URL = "https://html.duckduckgo.com/html/"
    DDG_LITE_URL = "https://duckduckgo.com/lite/"

    def __init__(self, session: Optional[requests.Session] = None):
        """
        Inicializa el ejecutor con sesión HTTP reutilizable.
        
        Args:
            session: Sesión requests opcional para connection pooling.
        """
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": self.USER_AGENT})
        
        self._herramientas = {
            "web_search": self._ejecutar_busqueda_web,
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
            ResultadoBusqueda estructurado y analizado
        """
        if herramienta not in self._herramientas:
            return ResultadoBusqueda(
                exito=False,
                query_original=payload,
                sintesis="",
                resultados=[],
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
                query_original=payload,
                sintesis="",
                resultados=[],
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
        Ejecuta búsqueda real en DuckDuckGo con análisis de resultados.
        
        Flujo:
        1. Request a DuckDuckGo HTML
        2. Parseo de resultados (título, URL, snippet)
        3. Fetch opcional de contenido completo de top resultados
        4. Síntesis ejecutiva de hallazgos
        5. Retorno estructurado
        """
        start_time = time.time()
        
        try:
            # 1. Request a DuckDuckGo
            resultados_crudos = self._buscar_duckduckgo(query)
            
            if not resultados_crudos:
                return ResultadoBusqueda(
                    exito=False,
                    query_original=query,
                    sintesis="No se encontraron resultados para la consulta.",
                    resultados=[],
                    fuente="duckduckgo",
                    metadatos={"tiempo_respuesta_ms": int((time.time() - start_time) * 1000)},
                    error="Sin resultados"
                )
            
            # 2. Procesar y enriquecer resultados
            resultados_procesados = self._procesar_resultados(resultados_crudos, query)
            
            # 3. Enriquecer top resultados con contenido completo (opcional)
            resultados_enriquecidos = self._enriquecer_resultados(resultados_procesados)
            
            # 4. Generar síntesis ejecutiva
            sintesis = self._generar_sintesis(query, resultados_enriquecidos)
            
            # 4. Construir respuesta final
            tiempo_ms = int((time.time() - start_time) * 1000)
            
            return ResultadoBusqueda(
                exito=True,
                query_original=query,
                sintesis=sintesis,
                resultados=resultados_enriquecidos,
                fuente="duckduckgo",
                metadatos={
                    "num_resultados": len(resultados_enriquecidos),
                    "tiempo_respuesta_ms": tiempo_ms,
                    "trigger": contexto.get("trigger", "web_search"),
                    "peso_operativo": contexto.get("peso_operativo", 10),
                    "num_resultados_enriquecidos": sum(1 for r in resultados_enriquecidos if r.contenido_completo)
                }
            )
            
        except requests.Timeout:
            logger.error(f"Timeout en búsqueda web: {query}")
            return ResultadoBusqueda(
                exito=False,
                query_original=query,
                sintesis="",
                resultados=[],
                fuente="duckduckgo",
                metadatos={"tiempo_respuesta_ms": int((time.time() - start_time) * 1000)},
                error="Timeout en búsqueda"
            )
        except requests.RequestException as e:
            logger.error(f"Error de red en búsqueda web: {e}")
            return ResultadoBusqueda(
                exito=False,
                query_original=query,
                sintesis="",
                resultados=[],
                fuente="duckduckgo",
                metadatos={},
                error=f"Error de red: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Error inesperado en búsqueda web: {e}")
            return ResultadoBusqueda(
                exito=False,
                query_original=query,
                sintesis="",
                resultados=[],
                fuente="duckduckgo",
                metadatos={},
                error=f"Error interno: {str(e)}"
            )
    
    def _buscar_duckduckgo(self, query: str) -> List[Dict[str, str]]:
        """
        Realiza request a DuckDuckGo HTML y extrae resultados crudos.
        
        Returns:
            Lista de dicts con: titulo, url, snippet
        """
        params = {"q": query, "kl": "es-es", "df": "", "s": "0"}
        response = self.session.post(
            self.DDG_HTML_URL,
            data=params,
            timeout=self.REQUEST_TIMEOUT
        )
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        resultados = []
        
        # DuckDuckGo HTML structure: result links in .result__snippet, .result__title, .result__url
        for result_div in soup.select(".result"):
            # Título y URL
            title_elem = result_div.select_one(".result__title")
            snippet_elem = result_div.select_one(".result__snippet")
            url_elem = result_div.select_one(".result__url")
            
            if not title_elem:
                continue
                
            titulo = title_elem.get_text(strip=True)
            url = title_elem.get("href", "") if title_elem.name == "a" else ""
            
            # Normalizar URL relativa
            if url and url.startswith("/"):
                url = urljoin("https://duckduckgo.com", url)
            # DuckDuckGo a veces usa redirects internos
            if url and "duckduckgo.com" in url and "uddg=" in url:
                # Extraer URL real del parámetro uddg
                import urllib.parse
                parsed = urllib.parse.urlparse(url)
                params = urllib.parse.parse_qs(parsed.query)
                if "uddg" in params:
                    url = params["uddg"][0]
            
            snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
            
            # Filtrar resultados muy cortos o vacíos
            if len(titulo) < 3 or len(snippet) < 10:
                continue
                
            resultados.append({
                "titulo": titulo,
                "url": url,
                "snippet": snippet,
                "fuente": self._extraer_dominio(url)
            })
            
            if len(resultados) >= self.MAX_RESULTADOS:
                break
        
        return resultados
    
    def _extraer_dominio(self, url: str) -> str:
        """Extrae el dominio base de una URL."""
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc
        except Exception:
            return "desconocido"
    
    def _procesar_resultados(
        self, 
        resultados_crudos: List[Dict[str, str]], 
        query: str
    ) -> List[ResultadoItem]:
        """Procesa resultados crudos a ResultadoItem con scoring de relevancia."""
        query_terms = set(query.lower().split())
        items = []
        
        for i, r in enumerate(resultados_crudos):
            # Calcular relevancia simple basada en coincidencia de términos
            titulo_lower = r["titulo"].lower()
            snippet_lower = r["snippet"].lower()
            
            coincidencias = sum(1 for term in query_terms if term in titulo_lower or term in snippet_lower)
            relevancia = min(1.0, 0.3 + (coincidencias / max(len(query_terms), 1)) * 0.7)
            # Penalizar por posición
            relevancia *= (1.0 - i * 0.05)
            
            items.append(ResultadoItem(
                titulo=r["titulo"],
                url=r["url"],
                snippet=r["snippet"],
                fuente=r["fuente"],
                relevancia=round(relevancia, 2),
                metadatos_extra={"posicion": i + 1}
            ))
        
        return items
    
    def _enriquecer_resultados(self, resultados: List[ResultadoItem]) -> List[ResultadoItem]:
        """
        Enriquece los top N resultados fetchando contenido completo.
        
        Nota: En producción, considerar rate limiting y cache.
        """
        enriquecidos = []
        
        for i, item in enumerate(resultados):
            if i >= 3:  # Solo enriquecer top 3 para evitar rate limiting
                enriquecidos.append(item)
                continue
            
            try:
                contenido = self._fetch_contenido_completo(item.url)
                if contenido and len(contenido) > 200:
                    item.contenido_completo = contenido[:self.MAX_CONTENT_LENGTH]
                    item.metadatos_extra["enriquecido"] = True
                    item.metadatos_extra["longitud_contenido"] = len(contenido)
            except Exception as e:
                logger.warning(f"No se pudo enriquecer {item.url}: {e}")
                item.metadatos_extra["enriquecido"] = False
            
            enriquecidos.append(item)
        
        return enriquecidos
    
    def _fetch_contenido_completo(self, url: str) -> Optional[str]:
        """Fetch y extrae texto principal de una URL."""
        try:
            # Headers para evitar bloqueos
            headers = {"User-Agent": self.USER_AGENT, "Accept": "text/html,application/xhtml+xml"}
            resp = self.session.get(url, timeout=10, headers=headers, allow_redirects=True)
            resp.raise_for_status()
            
            # Verificar content-type
            content_type = resp.headers.get("Content-Type", "")
            if "text/html" not in content_type.lower():
                return None
            
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # Remover scripts, styles, nav, footer, etc.
            for elem in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
                elem.decompose()
            
            # Intentar extraer contenido principal
            # Estrategia: main, article, .content, .post, #content
            main_content = None
            for selector in ["main", "article", ".content", ".post", "#content", ".entry-content"]:
                main_content = soup.select_one(selector)
                if main_content:
                    break
            
            if not main_content:
                main_content = soup.body
            
            if main_content:
                texto = main_content.get_text(separator="\n", strip=True)
                # Limpiar líneas vacías excesivas
                lineas = [l.strip() for l in texto.split("\n") if l.strip()]
                return "\n".join(lineas)
            
            return None
            
        except Exception as e:
            logger.debug(f"Error fetching {url}: {e}")
            return None
    
    def _generar_sintesis(self, query: str, resultados: List[ResultadoItem]) -> str:
        """
        Genera una síntesis ejecutiva de los hallazgos.
        
        Combina snippets y contenido enriquecido en una narrativa coherente.
        """
        if not resultados:
            return f"No se encontraron resultados relevantes para: '{query}'"
        
        # Contar resultados exitosos
        total = len(resultados)
        enriquecidos = sum(1 for r in resultados if r.contenido_completo)
        
        # Extraer temas clave de los títulos
        temas = []
        for r in resultados[:3]:
            # Extraer palabras clave del título (sustantivos/proper nouns)
            palabras = re.findall(r'\b[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+\b', r.titulo)
            temas.extend(palabras[:2])
        
        # Construir síntesis
        partes = [
            f"Búsqueda: '{query}' → {total} resultados relevantes encontrados ({enriquecidos} con contenido completo)."
        ]
        
        if temas:
            temas_unicos = list(dict.fromkeys(temas))[:5]  # únicos, max 5
            partes.append(f"Temas clave identificados: {', '.join(temas_unicos)}.")
        
        # Resumen de top 3 resultados
        for i, r in enumerate(resultados[:3], 1):
            partes.append(
                f"{i}. {r.titulo} ({r.fuente}): {r.snippet[:150]}..."
            )
        
        if len(resultados) > 3:
            partes.append(f"... y {len(resultados) - 3} resultados adicionales.")
        
        return " ".join(partes)


# ============================================================
# FUNCIÓN DE CONVENIENCIA / FACTORÍA
# ============================================================

def crear_executor(session: Optional[requests.Session] = None) -> 'ExternalToolExecutor':
    """Factoría para crear una instancia de ExternalToolExecutor."""
    return ExternalToolExecutor(session=session)