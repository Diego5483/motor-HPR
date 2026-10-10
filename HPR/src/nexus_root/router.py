"""Orquestador Principal del Nexus Root - Motor de Decisión Determinista.

Implementa el patrón Chain of Responsibility para la Matriz de
Precedencia Lógica de 4 niveles. Recibe el input del usuario,
ejecuta la cadena de handlers en orden estricto de precedencia
y retorna la decisión de enrutamiento final.

Ubicación: src/nexus_root/router.py
"""

from typing import Dict, Any, Optional, List
import logging
import re

from security_agent import HPRSecurityEngine
from models.contracts import PipelineState
from .sanitizer import InputSanitizer
from .precedencia import (
    MaxPriorityHandler,
    HighPriorityHandler,
    MediumPriorityHandler,
    BasePriorityHandler,
)
from .executor import ExternalToolExecutor, ResultadoBusqueda, crear_executor
from .synthesizer import NexusSynthesizer, crear_synthesizer

logger = logging.getLogger(__name__)


# ============================================================
# PATRONES DE SEGURIDAD PARA AUDITORÍA ACTIVA
# ============================================================

# Patrones de detección de amenazas (malicious patterns)
_PATRONES_MALICIOSOS = [
    # Scripts y ejecución de código
    r"<script\b[^>]*>.*?</script>",
    r"javascript\s*:",
    r"on\w+\s*=",
    r"eval\s*\(",
    r"Function\s*\(",
    r"setTimeout\s*\(",
    r"setInterval\s*\(",
    r"document\.(write|cookie)",
    r"window\.(location|open)",
    
    # Inyección SQL
    r"(union|select|insert|update|delete|drop|create|alter)\s+.*\b(from|into|table)\b",
    r"'\s*(or|and)\s*'1'\s*=\s*'1",
    
    # Inyección de comandos
    r";\s*(cat|ls|rm|wget|curl|nc|bash|sh)\b",
    r"\|\s*(cat|ls|rm|wget|curl)\b",
    r"`.*`",
    r"\$\(.*\)",
    
    # Path traversal
    r"\.\./",
    r"\.\.\\",
    
    # Exfiltración de datos
    r"password\s*[=:]\s*\S+",
    r"api[_-]?key\s*[=:]\s*\S+",
    r"secret\s*[=:]\s*\S+",
    r"token\s*[=:]\s*\S+",
    
    # Ofuscación
    r"\\x[0-9a-f]{2}",
    r"\\u[0-9a-f]{4}",
    r"%[0-9a-f]{2}",
    r"String\.fromCharCode",
    r"unescape\s*\(",
    r"decodeURI\s*\(",
    
    # Prompt injection patterns
    r"ignore\s+(previous|above|all)\s+(instructions|rules|guidelines)",
    r"forget\s+(everything|all|previous)",
    r"you\s+are\s+now\s+(a|an)\s+",
    r"act\s+as\s+(a|an)\s+",
    r"pretend\s+to\s+be",
    r"system\s+prompt",
    r"developer\s+mode",
    r"do\s+not\s+(tell|mention|reveal)",
]

# Compilar patrones para performance
_PATRONES_COMPILADOS = [re.compile(p, re.IGNORECASE) for p in _PATRONES_MALICIOSOS]

# Dominios de alta confianza (whitelist)
_DOMINIOS_CONFIABLES = {
    # Oficiales y gubernamentales
    "github.com", "gitlab.com", "bitbucket.org",
    "stackoverflow.com", "stackexchange.com",
    "wikipedia.org", "wikimedia.org",
    "python.org", "docs.python.org",
    "pypi.org", "npmjs.com",
    "docker.com", "docker.io",
    "kubernetes.io", "cncf.io",
    "apache.org", "mozilla.org",
    "google.com", "developers.google.com",
    "microsoft.com", "docs.microsoft.com",
    "aws.amazon.com", "azure.microsoft.com",
    "cloud.google.com",
    # ARM y arquitectura
    "arm.com", "developer.arm.com",
    # Académicos
    "arxiv.org", "doi.org", "scholar.google.com",
    "pubmed.ncbi.nlm.nih.gov", "ieee.org",
    # Noticias técnicas confiables
    "theverge.com", "arstechnica.com",
    "techcrunch.com", "wired.com",
    "zdnet.com", "cnet.com",
}


def _detectar_amenazas(texto: str) -> List[Dict[str, Any]]:
    """
    Escanea texto en busca de patrones maliciosos.
    
    Returns:
        Lista de amenazas detectadas con tipo, patrón y posición
    """
    amenazas = []
    for patron in _PATRONES_COMPILADOS:
        for match in patron.finditer(texto):
            amenazas.append({
                "tipo": "patron_malicioso",
                "patron": patron.pattern[:50],
                "coincidencia": match.group()[:100],
                "posicion": match.start(),
                "severidad": "critica" if any(k in patron.pattern for k in ["script", "eval", "exec", "sql", "command"]) else "alta"
            })
    return amenazas


def _verificar_dominio_confiable(url: str) -> bool:
    """Verifica si el dominio está en la whitelist de confianza."""
    try:
        from urllib.parse import urlparse
        dominio = urlparse(url).netloc.lower().replace("www.", "")
        return any(dominio.endswith(d) for d in _DOMINIOS_CONFIABLES)
    except Exception:
        return False


def _calcular_score_seguridad(resultado: ResultadoBusqueda) -> Dict[str, Any]:
    """
    Calcula score de seguridad del resultado de búsqueda.
    
    Returns:
        Dict con score, amenazas detectadas, y clasificación
    """
    amenazas_totales = []
    dominios_verificados = 0
    total_resultados = len(resultado.resultados)
    
    for item in resultado.resultados:
        # Verificar dominio
        if _verificar_dominio_confiable(item.url):
            dominios_verificados += 1
        
        # Escanear snippet
        amenazas_snippet = _detectar_amenazas(item.snippet)
        amenazas_totales.extend(amenazas_snippet)
        
        # Escanear contenido completo si existe
        if item.contenido_completo:
            amenazas_contenido = _detectar_amenazas(item.contenido_completo)
            amenazas_totales.extend(amenazas_contenido)
    
    # Clasificar severidad
    criticas = sum(1 for a in amenazas_totales if a.get("severidad") == "critica")
    altas = sum(1 for a in amenazas_totales if a.get("severidad") == "alta")
    
    # Determinar clasificación de seguridad
    if criticas > 0:
        clasificacion = "RECHAZO_CRITICO"
        score = 0.0
    elif altas > 2:
        clasificacion = "RECHAZO_CRITICO"
        score = 0.1
    elif altas > 0:
        clasificacion = "CONFIANZA_NULA"
        score = 0.2
    elif total_resultados > 0 and dominios_verificados / total_resultados >= 0.5:
        clasificacion = "CONFIANZA_ALTA"
        score = 0.9
    elif dominios_verificados > 0:
        clasificacion = "CONFIANZA_MEDIA"
        score = 0.6
    else:
        clasificacion = "CONFIANZA_BAJA"
        score = 0.3
    
    return {
        "score_seguridad": score,
        "clasificacion": clasificacion,
        "amenazas_detectadas": len(amenazas_totales),
        "amenazas_criticas": criticas,
        "amenazas_altas": altas,
        "dominios_verificados": dominios_verificados,
        "total_resultados": total_resultados,
        "detalle_amenazas": amenazas_totales[:10]  # Top 10 para logging
    }


def _evaluar_resultado_externo(
        resultado: ResultadoBusqueda, 
        trigger_info: Dict[str, Any]
    ) -> Dict[str, Any]:
    """
    Evalúa resultado de búsqueda externa con auditoría de tres niveles de confianza.
    
    NIVELES DE CONFIANZA:
    1. CONFIANZA_ALTA (score >= 0.75): Contenido verificado, seguro, relevante
       → Procesar, desglosar, presentar con etiqueta ALTA CONFIANZA
    
    2. CONFIANZA_MEDIA (0.4 <= score < 0.75): Parcialmente verificable, ambiguo
       → Procesar con advertencia, etiqueta CONFIANZA MODERADA
    
    3. CONFIANZA_NULA / RECHAZO_CRITICO (score < 0.4): 
       Patrones sospechosos, scripts, código malicioso, fuentes no verificables
       → BLOQUEAR salida, retornar alerta explícita de seguridad
    
    Args:
        resultado: ResultadoBusqueda del executor
        trigger_info: Info del trigger que disparó la búsqueda
        
    Returns:
        Dict con evaluación estructurada de tres niveles
    """
    if not resultado.exito or not resultado.resultados:
        return {
            "nivel_confianza": "RECHAZO_CRITICO",
            "score": 0.0,
            "aprobado": False,
            "razon": "Búsqueda fallida o sin resultados",
            "accion": "BLOQUEAR - Sin contenido recuperable",
            "filtros_aplicados": ["sin_resultados"],
            "score_seguridad": {"clasificacion": "RECHAZO_CRITICO", "score_seguridad": 0.0}
        }
    
    # Auditoría de seguridad activa
    score_seguridad = _calcular_score_seguridad(resultado)
    clasificacion_seguridad = score_seguridad["clasificacion"]
    score_seg = score_seguridad["score_seguridad"]
    
    # Evaluación de calidad de contenido (complementaria)
    resultados_con_contenido = [r for r in resultado.resultados if r.contenido_completo]
    fuentes_unicas = set(r.fuente for r in resultado.resultados)
    relevancia_promedio = sum(r.relevancia for r in resultado.resultados) / len(resultado.resultados)
    
    # Score de calidad (0-1)
    score_calidad = 0.0
    if resultados_con_contenido:
        score_calidad += 0.3
    if len(fuentes_unicas) >= 2:
        score_calidad += 0.2
    if (relevancia_promedio := sum(r.relevancia for r in resultado.resultados) / len(resultado.resultados)) >= 0.5:
        score_calidad += 0.2
    if resultado.sintesis and len(resultado.sintesis) > 50:
        score_calidad += 0.15
    
    # Score combinado (70% seguridad, 30% calidad)
    score_final = round(0.7 * score_seg + 0.3 * score_calidad, 2)
    
    # DETERMINACIÓN DE NIVEL DE CONFIANZA (tres niveles)
    if score_seguridad["clasificacion"] == "RECHAZO_CRITICO":
        nivel_confianza = "RECHAZO_CRITICO"
        accion = "BLOQUEAR - Contenido malicioso o altamente sospechoso detectado"
        aprobado = False
    elif score_seguridad["clasificacion"] == "CONFIANZA_NULA":
        nivel_confianza = "CONFIANZA_NULA"
        accion = "BLOQUEAR - Información sin valor confiable verificable"
        aprobado = False
    elif score_final >= 0.75:
        nivel_confianza = "CONFIANZA_ALTA"
        accion = "PROCESAR - Contenido verificado, seguro y relevante"
        aprobado = True
    elif score_final >= 0.45:
        nivel_confianza = "CONFIANZA_MEDIA"
        accion = "PROCESAR_CON_ADVERTENCIA - Parcialmente verificable, presentar con cautela"
        aprobado = True
    else:
        nivel_confianza = "CONFIANZA_BAJA"
        accion = "PROCESAR_CON_ADVERTENCIA_FUERTE - Muy poca verificabilidad"
        aprobado = True
    
    # Generar reporte detallado
    return {
        "nivel_confianza": nivel_confianza,
        "score_final": round(score_final, 2),
        "score_seguridad": round(score_seguridad["score_seguridad"], 2),
        "score_calidad": round(score_calidad, 2),
        "aprobado": aprobado,
        "accion": "PROCESAR" if aprobado else "BLOQUEAR",
        "accion_detallada": f"{'PROCESAR' if aprobado else 'BLOQUEAR'} - {nivel_confianza}",
        "clasificacion_seguridad": score_seguridad["clasificacion"],
        "razon": f"Score final: {score_final:.2f} (Seguridad: {score_seguridad['score_seguridad']:.2f}, Calidad: {score_calidad:.2f})",
        "accion_recomendada": "PROCESAR" if aprobado else "BLOQUEAR",
        "filtros_aplicados": [
            "auditoria_tres_niveles",
            "deteccion_patrones_maliciosos",
            "verificacion_dominios_confiables",
            "analisis_relevancia_calidad"
        ],
        "score_seguridad": score_seguridad,
        "metricas": {
            "total_resultados": len(resultado.resultados),
            "resultados_con_contenido_completo": len([r for r in resultado.resultados if r.contenido_completo]),
            "fuentes_unicas": len(set(r.fuente for r in resultado.resultados)),
            "relevancia_promedio": round(sum(r.relevancia for r in resultado.resultados) / len(resultado.resultados), 2),
            "dominios_verificados": score_seguridad.get("dominios_verificados", 0),
            "amenazas_detectadas": score_seguridad.get("amenazas_detectadas", 0),
            "amenazas_criticas": score_seguridad.get("amenazas_criticas", 0)
        }
    }


class NexusRouter:
    """
    Orquestador principal del Nexus Root - Motor de Decisión Determinista.

    Implementa el patrón Chain of Responsibility para la Matriz de
    Precedencia Lógica de 4 niveles. Recibe el input del usuario,
    ejecuta la cadena de handlers en orden estricto de precedencia
    y retorna la decisión de enrutamiento final.

    Características arquitectónicas:
    - Inyección de dependencias: recibe HPRSecurityEngine y ExternalToolExecutor en constructor.
    - Sin estado mutable: cada llamada es pura y determinista.
    - Orden de precedencia garantizado: MAX → HIGH → MEDIUM → BASE.
    - Short-circuit controlado: handlers pueden delegar ejecución externa
      en lugar de hacer short-circuit inmediato.
    - Logging estructurado: trazabilidad completa de cada decisión.
    - Extensibilidad: nuevos handlers se añaden al final de la cadena
      sin modificar los existentes (Open/Closed Principle).
    """

    def __init__(
        self,
        motor: HPRSecurityEngine,
        sanitizer: Optional[InputSanitizer] = None,
        executor: Optional[ExternalToolExecutor] = None,
        synthesizer: Optional[NexusSynthesizer] = None,
    ):
        """
        Inicializa el Nexus Router con la cadena de responsabilidad completa.

        Args:
            motor: Instancia de HPRSecurityEngine ya configurada.
                   Se inyecta en todos los handlers para acceso al pipeline.
            sanitizer: Instancia opcional de InputSanitizer. Si no se
                       proporciona, se usa la clase estática por defecto.
            executor: Instancia opcional de ExternalToolExecutor para
                      ejecutar herramientas externas (web_search, etc.).
                      Si no se proporciona, se crea uno por defecto.
            synthesizer: Instancia opcional de NexusSynthesizer para
                         generar informes en lenguaje natural.
                         Si no se proporciona, se crea uno por defecto.
        """
        self.motor = motor
        self.sanitizer = sanitizer or InputSanitizer()
        self.executor = executor or crear_executor()
        self.synthesizer = synthesizer or crear_synthesizer()

        # Construir la cadena de responsabilidad en ORDEN ESTRICTO DE PRECEDENCIA
        # Cada handler recibe la misma instancia del motor (inyección de dependencias)
        self._cadena: List[BaseHandler] = [
            MaxPriorityHandler(motor),       # NIVEL 1: Defensa Absoluta
            HighPriorityHandler(motor),       # NIVEL 2: Seguridad y Confianza
            MediumPriorityHandler(motor),     # NIVEL 3: Control Operativo
            BasePriorityHandler(motor),       # NIVEL 4: Multilingüe (catch-all)
        ]

        logger.info(
            f"NexusRouter inicializado | handlers={len(self._cadena)} | "
            f"orden=[{', '.join(h.nombre for h in self._cadena)}] | "
            f"executor={'mock' if isinstance(self.executor, ExternalToolExecutor) else 'custom'} | "
            f"synthesizer={'enabled' if self.synthesizer else 'disabled'}"
        )

    def enrutar(
        self,
        entrada: str,
        state: Optional[PipelineState] = None,
        truth: Optional[list] = None,
    ) -> Dict[str, Any]:
        """
        Ejecuta la cadena de responsabilidad sobre la entrada dada.

        Este es el punto de entrada único para el Nexus Root. Itera
        secuencialmente por cada handler hasta que uno asume el control
        (short-circuit) o se agota la cadena.

        Args:
            entrada: Texto crudo del usuario (puede ser None, vacío, triggers, NL).
            state: PipelineState opcional. Si no se provee, se crea uno
                   por defecto con identidad determinista.
            truth: Lista opcional de verdades de referencia para Epsilon Wall.

        Returns:
            Dict con la decisión final de enrutamiento:
                {
                    "decision": "bloqueo" | "trigger_confianza" | 
                                "ejecucion_externa_completada" | "delegacion_multilingue",
                    "nivel": "MAX_PRIORITY" | "HIGH_PRIORITY" | 
                             "MEDIUM_PRIORITY" | "BASE_PRIORITY",
                    "handler": "nombre_del_handler_que_decidio",
                    "override": str | None,  # Mensaje de bloqueo o identificador de trigger
                    "metadata": Dict[str, Any],  # Contexto completo de la decisión
                    "entrada_procesada": str,  # Entrada después de sanitización
                    "state": PipelineState,    # Estado final
                }

        Ejemplo de uso:
            >>> router = NexusRouter(motor)
            >>> resultado = router.enrutar("@hpr_confianza activar...", state)
            >>> resultado["decision"]
            'trigger_confianza'
            >>> resultado["nivel"]
            'HIGH_PRIORITY'
        """
        # Normalizar estado inicial
        if state is None:
            state = PipelineState(identity="HPR-CORE-DETERMINISTIC")
        if truth is None:
            truth = []

        # Sanitización inicial (capa 0 - antes de la cadena)
        es_seguro, override_sanitizer, log_sanitizer = self.sanitizer.validar_entrada_segura(
            entrada, nombre_fuente="NEXUS_ROUTER_ENTRADA"
        )

        entrada_procesada = self.sanitizer.limpiar_entrada(entrada) if es_seguro else ""

        if not es_seguro:
            # Bloqueo en capa 0 - antes de cualquier handler
            logger.warning(f"NexusRouter: BLOQUEO CAPA 0 | {log_sanitizer}")
            return {
                "decision": "bloqueo_sanitizer",
                "nivel": "SANITIZER_LAYER",
                "handler": "InputSanitizer",
                "override": override_sanitizer,
                "metadata": {
                    "bloqueo_tipo": override_sanitizer,
                    "log": log_sanitizer,
                },
                "entrada_procesada": "",
                "state": state,
            }

        # Log de inicio de cadena
        logger.info(
            f"NexusRouter: Iniciando cadena de precedencia | "
            f"entrada='{entrada_procesada[:80]}' | identity={state.identity}"
        )

        # Metadatos acumulados de toda la cadena
        metadata_acumulado: Dict[str, Any] = {
            "entrada_original": entrada,
            "entrada_sanitizada": entrada_procesada,
            "handlers_evaluados": [],
            "handler_decisor": None,
            "short_circuit": False,
        }

        # Iterar cadena de responsabilidad
        for handler in self._cadena:
            metadata_acumulado["handlers_evaluados"].append(handler.nombre)

            logger.debug(f"NexusRouter: Evaluando {handler.nombre}")

            # Ejecutar handler
            condicion_cumplida, override, metadata_handler = handler.manejar(
                entrada_procesada, state, truth
            )

            # Fusionar metadata del handler
            metadata_acumulado.update(metadata_handler)

            # NUEVA LÓGICA: Detectar instrucción de ejecución externa
            if override == "EJECUTAR_HERRAMIENTAS_EXTERNAS":
                # Ejecutar herramientas externas detectadas por el handler
                resultados_externos = self._ejecutar_herramientas_externas(
                    metadata_handler, entrada_procesada
                )
                
                # Evaluación global de todos los resultados externos
                evaluacion_global = self._evaluar_resultados_globales(resultados_externos)
                metadata_acumulado["evaluacion_global"] = evaluacion_global
                metadata_acumulado["resultados_externos"] = resultados_externos

                logger.info(
                    f"NexusRouter: EJECUCIÓN EXTERNA COMPLETADA | "
                    f"herramientas={len(resultados_externos)} | "
                    f"evaluación_global={evaluacion_global.get('nivel_confianza', 'N/A')} "
                    f"(confianza={evaluacion_global.get('confianza', 0):.2f})"
                )

                # Generar informe en lenguaje natural usando el sintetizador
                informe_sintesis = self.synthesizer.sintetizar(
                    resultado_busqueda={
                        "resultados": resultados_externos,
                        "sintesis": "Resultados de búsqueda externa",
                        "metadata": evaluacion_global
                    },
                    evaluacion_global=evaluacion_global,
                    query_original=entrada_procesada
                )

                return {
                    "decision": "ejecucion_externa_completada",
                    "nivel": handler.nombre,
                    "handler": handler.nombre,
                    "override": override,
                    "metadata": metadata_acumulado,
                    "entrada_procesada": entrada_procesada,
                    "state": state,
                    "informe_sintesis": {
                        "encabezado_confianza": informe_sintesis.encabezado_confianza,
                        "introduccion": informe_sintesis.introduccion,
                        "hallazgos_clave": informe_sintesis.hallazgos_clave,
                        "analisis_tecnico": informe_sintesis.analisis_tecnico,
                        "conclusiones": informe_sintesis.conclusiones,
                        "advertencias": informe_sintesis.advertencias,
                        "metadata_fuentes": informe_sintesis.metadata_fuentes,
                    }
                }

            if condicion_cumplida:
                # SHORT-CIRCUIT: este handler tomó la decisión (bloqueo, trigger_confianza, delegacion_multilingue)
                metadata_acumulado["handler_decisor"] = handler.nombre
                metadata_acumulado["short_circuit"] = True

                # Determinar tipo de decisión semántica
                decision_tipo = self._clasificar_decision(handler.nombre, override)

                logger.info(
                    f"NexusRouter: DECISIÓN FINAL | handler={handler.nombre} | "
                    f"decision={decision_tipo} | override={override}"
                )

                return {
                    "decision": decision_tipo,
                    "nivel": handler.nombre,
                    "handler": handler.nombre,
                    "override": override,
                    "metadata": metadata_acumulado,
                    "entrada_procesada": entrada_procesada,
                    "state": state,
                }

        # Si ningún handler hizo short-circuit (teóricamente imposible
        # porque BasePriorityHandler siempre captura), fallback seguro
        logger.warning(
            "NexusRouter: Cadena agotada sin decisión - "
            "fallback a BASE_PRIORITY (no debería ocurrir)"
        )

        return {
            "decision": "fallback_base",
            "nivel": "BASE_PRIORITY_FALLBACK",
            "handler": "BasePriorityHandler",
            "override": "Procesamiento por defecto - lenguaje natural",
            "metadata": metadata_acumulado,
            "entrada_procesada": entrada_procesada,
            "state": state,
        }

    def _ejecutar_herramientas_externas(
        self, 
        metadata_handler: Dict[str, Any], 
        entrada_original: str
    ) -> List[Dict[str, Any]]:
        """
        Ejecuta todas las herramientas externas detectadas por el handler.
        
        Args:
            metadata_handler: Metadata retornada por el handler (contiene triggers)
            entrada_original: Entrada original del usuario para fallback de payload
            
        Returns:
            Lista de resultados de ejecución de herramientas externas
        """
        resultados = []
        triggers = metadata_handler.get("triggers", [])
        
        for trigger_info in triggers:
            herramienta = trigger_info["tipo"]  # "web_search"
            payload = trigger_info["payload"]   # query extraída
            
            if not payload:
                # Si no hay payload específico, usar entrada original
                payload = entrada_original
            
            logger.info(f"NexusRouter: Ejecutando herramienta {herramienta} | payload='{payload[:50]}'")
            
            resultado: ResultadoBusqueda = self.executor.ejecutar(
                herramienta=herramienta,
                payload=payload,
                contexto={
                    "trigger": trigger_info["tipo"],
                    "peso_operativo": trigger_info["peso_operativo"],
                    "entrada_original": entrada_original
                }
            )
            
            # NUEVO: Evaluación y filtrado por Nexus Root
            evaluacion = self._evaluar_resultado_externo(resultado, trigger_info)
            
            resultados.append({
                "herramienta": herramienta,
                "exito": resultado.exito,
                "contenido": resultado.sintesis,  # Usar sintesis como contenido principal
                "fuente": resultado.fuente,
                "metadatos": resultado.metadatos,
                "error": resultado.error,
                # NUEVO: Evaluación del Nexus Root
                "evaluacion_nexus": evaluacion
            })
        
        return resultados
    
    def _evaluar_resultados_globales(self, resultados_externos: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Evalúa globalmente todos los resultados de herramientas externas.
        
        Returns:
            Dict con evaluación global agregada
        """
        if not resultados_externos:
            return {
                "nivel_confianza": "RECHAZO_CRITICO",
                "score_final": 0.0,
                "aprobado": False,
                "accion_recomendada": "BLOQUEAR",
                "accion": "BLOQUEAR - Sin resultados externos",
                "filtros_aplicados": ["sin_resultados_externos"]
            }
        
        # Agregar evaluaciones individuales
        niveles = [r.get("evaluacion_nexus", {}).get("nivel_confianza", "DESCONOCIDO") for r in resultados_externos]
        scores = [r.get("evaluacion_nexus", {}).get("score_final", 0) for r in resultados_externos]
        aprobados = [r.get("evaluacion_nexus", {}).get("aprobado", False) for r in resultados_externos]
        
        # Determinar nivel global (el más restrictivo)
        if "RECHAZO_CRITICO" in niveles:
            nivel_global = "RECHAZO_CRITICO"
        elif "CONFIANZA_NULA" in niveles:
            nivel_global = "CONFIANZA_NULA"
        elif "CONFIANZA_ALTA" in niveles and "CONFIANZA_NULA" not in niveles and "RECHAZO_CRITICO" not in niveles:
            nivel_global = "CONFIANZA_ALTA"
        elif "CONFIANZA_MEDIA" in niveles:
            nivel_global = "CONFIANZA_MEDIA"
        else:
            nivel_global = "CONFIANZA_BAJA"
        
        score_promedio = sum(r.get("evaluacion_nexus", {}).get("score_final", 0) for r in resultados_externos) / len(resultados_externos)
        todos_aprobados = all(r.get("evaluacion_nexus", {}).get("aprobado", False) for r in resultados_externos)
        
        return {
            "nivel_confianza": "RECHAZO_CRITICO" if "RECHAZO_CRITICO" in niveles else 
                              "CONFIANZA_NULA" if "CONFIANZA_NULA" in niveles else
                              "CONFIANZA_ALTA" if "CONFIANZA_ALTA" in niveles and "CONFIANZA_NULA" not in niveles and "RECHAZO_CRITICO" not in niveles else
                              "CONFIANZA_MEDIA" if "CONFIANZA_MEDIA" in niveles else
                              "CONFIANZA_BAJA",
            "score_final": round(sum(r.get("evaluacion_nexus", {}).get("score_final", 0) for r in resultados_externos) / len(resultados_externos), 2),
            "aprobado": all(r.get("evaluacion_nexus", {}).get("aprobado", False) for r in resultados_externos),
            "accion_recomendada": "PROCESAR" if all(r.get("evaluacion_nexus", {}).get("aprobado", False) for r in resultados_externos) else "BLOQUEAR",
            "accion": "PROCESAR" if all(r.get("evaluacion_nexus", {}).get("aprobado", False) for r in resultados_externos) else "BLOQUEAR",
            "filtros_aplicados": ["agregacion_evaluaciones_multiples"],
            "metricas": {
                "total_herramientas": len(resultados_externos),
                "aprobados": sum(1 for r in resultados_externos if r.get("evaluacion_nexus", {}).get("aprobado", False)),
                "niveles_detectados": list(set(niveles))
            }
        }

    def _evaluar_resultado_externo(
        self, 
        resultado: ResultadoBusqueda, 
        trigger_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evalúa resultado de búsqueda externa con auditoría de tres niveles de confianza.
        
        NIVELES DE CONFIANZA:
        1. CONFIANZA_ALTA (score >= 0.75): Contenido verificado, seguro, relevante
           → Procesar, desglosar, presentar con etiqueta ALTA CONFIANZA
        
        2. CONFIANZA_MEDIA (0.4 <= score < 0.75): Parcialmente verificable, ambiguo
           → Procesar con advertencia, etiqueta CONFIANZA MODERADA
        
        3. CONFIANZA_NULA / RECHAZO_CRITICO (score < 0.4): 
           Patrones sospechosos, scripts, código malicioso, fuentes no verificables
           → BLOQUEAR salida, retornar alerta explícita de seguridad
        
        Args:
            resultado: ResultadoBusqueda del executor
            trigger_info: Info del trigger que disparó la búsqueda
            
        Returns:
            Dict con evaluación estructurada de tres niveles
        """
        if not resultado.exito or not resultado.resultados:
            return {
                "nivel_confianza": "RECHAZO_CRITICO",
                "score_final": 0.0,
                "score": 0.0,
                "aprobado": False,
                "razon": "Búsqueda fallida o sin resultados",
                "accion": "BLOQUEAR - Sin contenido recuperable",
                "filtros_aplicados": ["sin_resultados"],
                "score_seguridad": {"clasificacion": "RECHAZO_CRITICO", "score_seguridad": 0.0},
                "metricas": {
                    "total_resultados": 0,
                    "resultados_con_contenido_completo": 0,
                    "fuentes_unicas": 0,
                    "relevancia_promedio": 0.0,
                    "dominios_verificados": 0,
                    "amenazas_detectadas": 0,
                    "amenazas_criticas": 0
                }
            }
        
        # Auditoría de seguridad activa
        score_seguridad = _calcular_score_seguridad(resultado)
        clasificacion_seguridad = score_seguridad["clasificacion"]
        score_seg = score_seguridad["score_seguridad"]
        
        # Evaluación de calidad de contenido (complementaria)
        resultados_con_contenido = [r for r in resultado.resultados if r.contenido_completo]
        fuentes_unicas = set(r.fuente for r in resultado.resultados)
        relevancia_promedio = sum(r.relevancia for r in resultado.resultados) / len(resultado.resultados)
        
        # Score de calidad (0-1)
        score_calidad = 0.0
        if resultados_con_contenido:
            score_calidad += 0.3
        if len(fuentes_unicas) >= 2:
            score_calidad += 0.2
        if (relevancia_promedio := sum(r.relevancia for r in resultado.resultados) / len(resultado.resultados)) >= 0.5:
            score_calidad += 0.2
        if resultado.sintesis and len(resultado.sintesis) > 50:
            score_calidad += 0.15
        
        # Score combinado (70% seguridad, 30% calidad)
        score_final = round(0.7 * score_seg + 0.3 * score_calidad, 2)
        
        # Verificar si es dominio no verificado sin contenido completo
        dominios_verificados = score_seguridad.get("dominios_verificados", 0)
        total_resultados = score_seguridad.get("total_resultados", len(resultado.resultados))
        tiene_contenido_completo = len([r for r in resultado.resultados if r.contenido_completo]) > 0
        dominio_no_verificado = (dominios_verificados == 0 and total_resultados > 0)
        sin_contenido_completo = not tiene_contenido_completo
        
        # DETERMINACIÓN DE NIVEL DE CONFIANZA (tres niveles + umbral estricto)
        if score_seguridad["clasificacion"] == "RECHAZO_CRITICO":
            nivel_confianza = "RECHAZO_CRITICO"
            accion = "BLOQUEAR - Contenido malicioso o altamente sospechoso detectado"
            aprobado = False
        elif score_seguridad["clasificacion"] == "CONFIANZA_NULA":
            nivel_confianza = "CONFIANZA_NULA"
            accion = "BLOQUEAR - Información sin valor confiable verificable"
            aprobado = False
        elif dominio_no_verificado and sin_contenido_completo:
            # Dominio no verificado SIN contenido completo → CONFIANZA_NULA (bloqueo)
            nivel_confianza = "CONFIANZA_NULA"
            accion = "BLOQUEAR - Dominio no verificado sin contenido verificable"
            aprobado = False
        elif score_final >= 0.75:
            nivel_confianza = "CONFIANZA_ALTA"
            accion = "PROCESAR - Contenido verificado, seguro y relevante"
            aprobado = True
        elif score_final >= 0.45:
            nivel_confianza = "CONFIANZA_MEDIA"
            accion = "PROCESAR_CON_ADVERTENCIA - Parcialmente verificable, presentar con cautela"
            aprobado = True
        else:
            nivel_confianza = "CONFIANZA_BAJA"
            accion = "PROCESAR_CON_ADVERTENCIA_FUERTE - Muy poca verificabilidad"
            aprobado = True
        
        # Generar reporte detallado
        return {
            "nivel_confianza": nivel_confianza,
            "score_final": round(score_final, 2),
            "score_seguridad": round(score_seguridad["score_seguridad"], 2),
            "score_calidad": round(score_calidad, 2),
            "aprobado": aprobado,
            "accion": "PROCESAR" if aprobado else "BLOQUEAR",
            "accion_detallada": f"{'PROCESAR' if aprobado else 'BLOQUEAR'} - {nivel_confianza}",
            "clasificacion_seguridad": score_seguridad["clasificacion"],
            "razon": f"Score final: {score_final:.2f} (Seguridad: {score_seguridad['score_seguridad']:.2f}, Calidad: {score_calidad:.2f})",
            "accion_recomendada": "PROCESAR" if aprobado else "BLOQUEAR",
            "filtros_aplicados": [
                "auditoria_tres_niveles",
                "deteccion_patrones_maliciosos",
                "verificacion_dominios_confiables",
                "analisis_relevancia_calidad"
            ],
            "score_seguridad": score_seguridad,
            "metricas": {
                "total_resultados": len(resultado.resultados),
                "resultados_con_contenido_completo": len([r for r in resultado.resultados if r.contenido_completo]),
                "fuentes_unicas": len(set(r.fuente for r in resultado.resultados)),
                "relevancia_promedio": round(sum(r.relevancia for r in resultado.resultados) / len(resultado.resultados), 2),
                "dominios_verificados": score_seguridad.get("dominios_verificados", 0),
                "amenazas_detectadas": score_seguridad.get("amenazas_detectadas", 0),
                "amenazas_criticas": score_seguridad.get("amenazas_criticas", 0)
            }
        }

    def _clasificar_decision(self, handler_nombre: str, override: Optional[str]) -> str:
        """
        Clasifica el tipo de decisión semántica para logging y métricas.

        Args:
            handler_nombre: Nombre del handler que tomó la decisión.
            override: Valor de override retornado por el handler.

        Returns:
            String semántico: "bloqueo", "trigger_confianza", "trigger_operativo", "delegacion_multilingue"
        """
        if handler_nombre == "MAX_PRIORITY":
            return "bloqueo"
        elif handler_nombre == "HIGH_PRIORITY":
            return "trigger_confianza"
        elif handler_nombre == "MEDIUM_PRIORITY":
            return "trigger_operativo"
        elif handler_nombre == "BASE_PRIORITY":
            return "delegacion_multilingue"
        else:
            return "desconocido"

    def obtener_orden_cadena(self) -> List[str]:
        """
        Retorna el orden actual de la cadena para inspección/debugging.

        Returns:
            Lista de nombres de handlers en orden de ejecución.
        """
        return [h.nombre for h in self._cadena]

    def reset(self) -> None:
        """
        Resetea cualquier estado interno mutable (si existiera).
        En la implementación actual es no-op por ser stateless,
        pero se mantiene para compatibilidad futura.
        """
        pass


# ============================================================
# FUNCIÓN DE CONVENIENCIA / FACTORÍA
# ============================================================

def crear_nexus_router(
    motor: HPRSecurityEngine,
    sanitizer: Optional[InputSanitizer] = None,
    executor: Optional[ExternalToolExecutor] = None,
    synthesizer: Optional[NexusSynthesizer] = None,
) -> NexusRouter:
    """
    Factoría para crear una instancia configurada de NexusRouter.

    Args:
        motor: Instancia de HPRSecurityEngine.
        sanitizer: Instancia opcional de InputSanitizer.
        executor: Instancia opcional de ExternalToolExecutor.
        synthesizer: Instancia opcional de NexusSynthesizer.

    Returns:
        NexusRouter listo para usar con enrutar().
    """
    return NexusRouter(
        motor=motor, 
        sanitizer=sanitizer, 
        executor=executor,
        synthesizer=synthesizer
    )