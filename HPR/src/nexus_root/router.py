"""Orquestador Principal del Nexus Root - Motor de Decisión Determinista.

Implementa el patrón Chain of Responsibility para la Matriz de
Precedencia Lógica de 4 niveles. Recibe el input del usuario,
ejecuta la cadena de handlers en orden estricto de precedencia
y retorna la decisión de enrutamiento final.

Ubicación: src/nexus_root/router.py
"""

from typing import Dict, Any, Optional, List
import logging

from src.security_agent import HPRSecurityEngine
from src.models.contracts import PipelineState
from src.nexus_root.sanitizer import InputSanitizer
from src.nexus_root.precedencia import (
    MaxPriorityHandler,
    HighPriorityHandler,
    MediumPriorityHandler,
    BasePriorityHandler,
)
from src.nexus_root.executor import ExternalToolExecutor, ResultadoBusqueda, crear_executor

logger = logging.getLogger(__name__)


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
        """
        self.motor = motor
        self.sanitizer = sanitizer or InputSanitizer()
        self.executor = executor or crear_executor()

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
            f"executor={'mock' if isinstance(self.executor, ExternalToolExecutor) else 'custom'}"
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
                
                metadata_acumulado["handler_decisor"] = handler.nombre
                metadata_acumulado["short_circuit"] = True
                metadata_acumulado["resultados_externos"] = resultados_externos

                logger.info(
                    f"NexusRouter: EJECUCIÓN EXTERNA COMPLETADA | "
                    f"herramientas={len(resultados_externos)}"
                )

                return {
                    "decision": "ejecucion_externa_completada",
                    "nivel": handler.nombre,
                    "handler": handler.nombre,
                    "override": override,
                    "metadata": metadata_acumulado,
                    "entrada_procesada": entrada_procesada,
                    "state": state,
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
            
            resultados.append({
                "herramienta": herramienta,
                "exito": resultado.exito,
                "contenido": resultado.contenido,
                "fuente": resultado.fuente,
                "metadatos": resultado.metadatos,
                "error": resultado.error
            })
        
        return resultados

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
) -> NexusRouter:
    """
    Factoría para crear una instancia configurada de NexusRouter.

    Args:
        motor: Instancia de HPRSecurityEngine.
        sanitizer: Instancia opcional de InputSanitizer.
        executor: Instancia opcional de ExternalToolExecutor.

    Returns:
        NexusRouter listo para usar con enrutar().
    """
    return NexusRouter(motor=motor, sanitizer=sanitizer, executor=executor)