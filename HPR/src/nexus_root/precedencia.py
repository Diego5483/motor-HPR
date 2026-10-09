"""Motor de Matriz de Precedencia Lógica para Nexus Root.

Implementa la cadena de responsabilidad (Chain of Responsibility) 
según la jerarquía de 4 niveles definida para el procesamiento
determinista y robusto del motor HPR.

NIVELES DE PRECEDENCIA (de mayor a menor):
1. MAXIMA: None, vacío, caracteres inválidos → bloqueo preventivo
2. ALTA: Trigger @hpr_confianza → ejecución prioritaria
3. MEDIA: Triggers @nivel1, @web_search → pipeline operativo/ web
4. BASE: Texto NL sin comandos → auto-detección multilingüe
"""

from typing import Optional, Tuple, Dict, Any, Callable
import logging

from src.security_agent import HPRSecurityEngine
from src.models.contracts import PipelineState, NivelRiesgo, CategoriaConsulta
from src.nexus_root.sanitizer import InputSanitizer

# Configuración de logging
logger = logging.getLogger(__name__)


# ============================================================
# HANDLER BASE Y TIPOS
# ============================================================

HandlerResult = Tuple[bool, Optional[str], Dict[str, Any]]
"""
Tuple[bool, Optional[str], Dict[str, Any]]:
    - bool: True si el handler asumió el procesamiento (short-circuit)
    - Optional[str]: Respuesta/estado override si aplica (ej. "BLOQUEO NONE_TYPE")
    - Dict: Metadatos adicionales (idioma, requiere_externa, etc.)
"""


class BaseHandler:
    """Clase base abstracta para todos los handlers de la cadena."""
    
    def __init__(self, nombre: str, motor: HPRSecurityEngine):
        self.nombre = nombre
        self.motor = motor
    
    def manejar(
        self, 
        entrada: str, 
        state: PipelineState,
        truth: list = []
    ) -> HandlerResult:
        """
        Método que debe ser implementado por subclasses.
        Retorna (condicion_cumplida, override, metadatos).
        Si condicion_cumplida es True, el pipeline se detiene.
        """
        raise NotImplementedError("Subclasses deben implementar este método")


# ============================================================
# HANDLER DE PRIORIDAD MÁXIMA
# ============================================================

class MaxPriorityHandler(BaseHandler):
    """
    PRIORIDAD MÁXIMA (Defensa Absoluta).
    
    Condición: Entradas None, strings vacíos (""), o caracteres inválidos/corruptos.
    Acción: Interceptación inmediata en la capa más superficial.
    Bloqueo preventivo de excepciones tipo NoneType.
    Salida controlada con log de advertencia.
    """
    
    def __init__(self, motor: HPRSecurityEngine):
        super().__init__("MAX_PRIORITY", motor)
    
    def manejar(
        self, 
        entrada: str, 
        state: PipelineState,
        truth: list = []
    ) -> HandlerResult:
        """
        Valida la entrada según Prioridad Máxima.
        
        Returns:
            HandlerResult: (True, mensaje_bloqueo, metadata) si entrada inválida.
                           (False, None, metadata) si entrada válida, continuar cadena.
        """
        # Usar el sanitizer validación
        es_seguro, override, log_msg = InputSanitizer.validar_entrada_segura(
            entrada, nombre_fuente=self.nombre
        )
        
        if not es_seguro:
            # Bloqueo preventivo - short-circuit
            logger.warning(f"{self.nombre}: {log_msg}")
            metadata = {
                "nivel": "MAXIMA",
                "bloqueo_tipo": override,
                "idioma": state.identity if state else "unknown",
            }
            return True, override, metadata
        
        # Entrada válida, pasar al siguiente handler
        logger.debug(f"{self.nombre}: entrada válida, continuar cadena")
        return False, None, {"nivel": "MAXIMA", "siguiente": "ALTA"}


# ============================================================
# HANDLER DE PRIORIDAD ALTA
# ============================================================

class HighPriorityHandler(BaseHandler):
    """
    PRIORIDAD ALTA (Seguridad y Confianza).
    
    Condición: Detección del trigger '@hpr_confianza'.
    Acción: Ejecución prioritaria de los parámetros de estado y validación del motor.
    Este trigger SOBREESCRIBE cualquier otra intención de nivel inferior.
    """
    
    def __init__(self, motor: HPRSecurityEngine):
        super().__init__("HIGH_PRIORITY", motor)
    
    def manejar(
        self, 
        entrada: str, 
        state: PipelineState,
        truth: list = []
    ) -> HandlerResult:
        """
        Detecta el trigger @hpr_confianza y activa procesamiento prioritario.
        
        Returns:
            HandlerResult: (True, override, metadata) si trigger detectado.
                           (False, None, metadata) si no es trigger, continuar cadena.
        """
        entrada_limpia = InputSanitizer.limpiar_entrada(entrada)
        
        # Verificar trigger @hpr_confianza (patrón exacto)
        import re
        patron = re.compile(r"^@hpr_confianza\s*")
        match = patron.match(entrada_limpia)
        
        if match:
            # Extraer el identificador después del trigger
            trigger_id = entrada_limpia.replace("@hpr_confianza", "").strip()
            logger.info(f"{self.nombre}: trigger @hpr_confianza detectado | trigger_id='{trigger_id}'")
            
            # Ejecutar validación prioritaria del motor
            # Nota: en producción real, aquí llamaría al motor con los parámetros
            # específicos del trigger. Por ahora, retornamos metadata de activación.
            metadata = {
                "nivel": "ALTA",
                "trigger": "@hpr_confianza",
                "trigger_id": trigger_id,
                "requiere_externa": True,  # triggers de confianza marcan REQUIRE_EXTERNA
                "idioma": state.identity if state else "unknown",
                "accion": "validacion_prioritaria",
            }
            logger.warning(f"{self.nombre}: trigger prioritario activado - {trigger_id}")
            return True, "@hpr_confianza", metadata
        
        # No es trigger @hpr_confianza, continuar cadena
        logger.debug(f"{self.nombre}: no es trigger @hpr_confianza, continuar cadena")
        return False, None, {"nivel": "ALTA", "siguiente": "MEDIA"}


# ============================================================
# HANDLER DE PRIORIDAD MEDIA
# ============================================================

class MediumPriorityHandler(BaseHandler):
    """
    PRIORIDAD MEDIA (Control Operativo).
    
    Condición: Detección de triggers combinados como @nivel1 o @web_search.
    Acción: Activación del pipeline operativo y/o consulta web en paralelo,
    evaluando posibles colisiones. Si un input tiene múltiples triggers,
    separarlos y procesarlos en orden de peso operativo.
    """
    
    # Pesos operativos para ordenamiento (mayor = más prioritario)
    _PESO_OPERATIVO = {"web_search": 10, "nivel1": 5}
    
    def __init__(self, motor: HPRSecurityEngine):
        super().__init__("MEDIUM_PRIORITY", motor)
    
    def manejar(
        self, 
        entrada: str, 
        state: PipelineState,
        truth: list = []
    ) -> HandlerResult:
        """
        Detecta triggers @nivel1 y @web_search y activa pipelines correspondientes.
        
        Returns:
            HandlerResult: (True, override, metadata) si trigger detectado.
                           (False, None, metadata) si no es trigger, continuar cadena.
        """
        import re
        
        entrada_limpia = InputSanitizer.limpiar_entrada(entrada)
        metadata = {"nivel": "MEDIA"}
        
        # Patrones de triggers - buscar en cualquier posición (no solo inicio)
        patron_nivel1 = re.compile(r"@nivel1\b")
        patron_web_search = re.compile(r"@web_search\b")
        
        triggers_detectados = []
        
        # Verificar @nivel1 en cualquier posición
        matches_nivel1 = list(patron_nivel1.finditer(entrada_limpia))
        if matches_nivel1:
            # Extraer payload después del último @nivel1
            last_match = matches_nivel1[-1]
            trigger_id = entrada_limpia[last_match.end():].strip()
            triggers_detectados.append(("nivel1", trigger_id))
            logger.info(f"{self.nombre}: trigger @nivel1 detectado | trigger_id='{trigger_id}'")
        
        # Verificar @web_search en cualquier posición
        matches_web = list(patron_web_search.finditer(entrada_limpia))
        if matches_web:
            last_match = matches_web[-1]
            trigger_id = entrada_limpia[last_match.end():].strip()
            triggers_detectados.append(("web_search", trigger_id))
            logger.info(f"{self.nombre}: trigger @web_search detectado | trigger_id='{trigger_id}'")
        
        # Si hay triggers detectados
        if triggers_detectados:
            # Construir lista de triggers con información detallada
            metadata["triggers"] = []
            
            # Ordenar triggers por peso operativo descendente (mayor peso primero)
            triggers_ordenados = sorted(
                triggers_detectados, 
                key=lambda t: self._PESO_OPERATIVO.get(t[0], 0), 
                reverse=True
            )
            
            # Procesar triggers en orden de peso operativo (mayor primero)
            for trigger_tipo, trigger_id in triggers_ordenados:
                metadata[f"trigger_{trigger_tipo}"] = trigger_id
                metadata[f"accion_{trigger_tipo}"] = "pipeline_operativo" if trigger_tipo == "nivel1" else "busqueda_web"
                
                # Añadir a la lista de triggers detallados
                trigger_info = {
                    "tipo": trigger_tipo,
                    "payload": trigger_id,
                    "peso_operativo": self._PESO_OPERATIVO.get(trigger_tipo, 0),
                    "accion": "pipeline_operativo" if trigger_tipo == "nivel1" else "busqueda_web",
                }
                metadata["triggers"].append(trigger_info)
            
            metadata["triggers_detectados"] = len(triggers_detectados)
            metadata["accion"] = "pipeline_operativo_paralelo"
            
            logger.warning(
                f"{self.nombre}: triggers operativos detectados {triggers_detectados} | "
                f"activando pipeline operativo (ordenado por peso)"
            )
            # CAMBIO: NO short-circuit aquí. Retornamos instrucción para que el
            # NexusRouter ejecute las herramientas externas tras la validación determinista.
            return False, "EJECUTAR_HERRAMIENTAS_EXTERNAS", metadata
        
        # No es trigger de prioridad media, continuar cadena
        logger.debug(f"{self.nombre}: no hay triggers operativos, continuar cadena")
        return False, None, metadata


# ============================================================
# HANDLER DE PRIORIDAD BASE
# ============================================================

class BasePriorityHandler(BaseHandler):
    """
    PRIORIDAD BASE (Multilingüe).
    
    Condición: Texto en lenguaje natural sin comandos explícitos.
    Acción: Auto-detección y delegación a la capa multilingüe 
    (detector.py, selector.py, router.py).
    """
    
    def __init__(self, motor: HPRSecurityEngine):
        super().__init__("BASE_PRIORITY", motor)
    
    def manejar(
        self, 
        entrada: str, 
        state: PipelineState,
        truth: list = []
    ) -> HandlerResult:
        """
        Entrada de lenguaje natural sin triggers explícitos.
        Delegar a la capa multilingüe existente.
        
        Returns:
            HandlerResult: Retorna (True, override, metadata) para short-circuit
                           en la delegación multilingüe.
        """
        metadata = {
            "nivel": "BASE",
            "accion": "delegacion_multilingue",
            "descripcion": "Entrada lenguaje natural, delegar a capa multilingüe",
        }
        
        logger.debug(f"{self.nombre}: entrada lenguaje natural, delegar a capa multilingüe")
        return True, "delegacion_multilingue", metadata


# ============================================================
# MOTOR PRINCIPAL: NexusRootEngine
# ============================================================

class NexusRootPrecedenceEngine:
    """
    Motor principal que ejecuta la cadena de responsabilidad 
    de precedencia lógica para el Nexus Root del motor HPR.
    
    Características:
    - Cadena de handlers en orden de precedencia estricto
    - Inyección de dependencias del motor HPR
    - Logging estructurado de cada decisión
    - Retorno de metadatos completos para rastreo
    """
    
    def __init__(self, motor: HPRSecurityEngine):
        """
        Inicializa el motor con la instancia del security engine.
        
        Args:
            motor: Instancia de HPRSecurityEngine ya configurada
        """
        self.motor = motor
        
        # Construir la cadena de responsabilidad en orden de precedencia
        self._cadena = [
            MaxPriorityHandler(motor),       # Nivel 1: Defensa Absoluta
            HighPriorityHandler(motor),       # Nivel 2: Seguridad y Confianza
            MediumPriorityHandler(motor),     # Nivel 3: Control Operativo
            BasePriorityHandler(motor),       # Nivel 4: Multilingüe
        ]
    
    def procesar(
        self, 
        entrada: str, 
        state: PipelineState,
        truth: list = []
    ) -> Dict[str, Any]:
        """
        Ejecuta la matriz de precedencia lógica sobre la entrada dada.
        
        Flujo:
        1. Iterar por cada handler en orden de precedencia
        2. Cada handler evalúa su condición
        3. Si handler.devuelve True → short-circuit, retornar su resultado
        4. Si handler.devuelve False → pasar al siguiente handler
        5. Si ningún handler toma el control (debería ser imposible con Base) → fallback
        
        Args:
            entrada: Texto de entrada del usuario
            state: PipelineState con identidad y contexto
            truth: Lista de verdades de referencia para validación
            
        Returns:
            Dict con la decisión tomada:
                - "decision": tipo de decisión tomada (bloqueo, trigger, delegación)
                - "nivel": nivel de precedencia activado (MAX/ALTA/MEDIA/BASE)
                - "metadatos": diccionario con triggers, acciones, idioma, etc.
                - "override": mensaje de bloqueo o trigger si aplica
        """
        logger.info(f"NEXUS_ROOT: Iniciando procesamiento de entrada | len={len(entrada) if entrada else 0}")
        
        # Estado acumulado de metadatos
        metadatos_acumulados: Dict[str, Any] = {
            "entrada_original": entrada,
            "procesado_por": [],
            "nivel_activado": None,
            "bloqueo": None,
            "trigger": None,
        }
        
        # Ejecutar cadena de responsabilidad
        for handler in self._cadena:
            logger.debug(f"NEXUS_ROOT: Evaluando handler {handler.nombre}")
            
            condicion_cumplida, override, metadatos_handler = handler.manejar(
                entrada, state, truth
            )
            
            # Acumular metadatos
            metadatos_acumulados["procesado_por"].append(handler.nombre)
            
            if condicion_cumplida:
                # Short-circuit: este handler asumió el procesamiento
                metadatos_acumulados["nivel_activado"] = handler.nombre
                metadatos_acumulados["bloqueo"] = override
                metadatos_acumulados["trigger"] = override  # override contiene el trigger
                
                logger.info(
                    f"NEXUS_ROOT: DECISIÓN FINAL | nivel={handler.nombre} | "
                    f"override={override} | trigger={override}"
                )
                
                return {
                    "decision": "bloqueo_override" if override and override.startswith("BLOQUEO") else "trigger_activado",
                    "nivel": handler.nombre,
                    "metadatos": metadatos_acumulados,
                    "override": override,
                }
        
        # Si llegamos aquí, ningún handler tomó la decisión (caso borde)
        # Debería ser imposible dado que el BaseHandler siempre captura,
        # pero por seguridad, retornar fallback
        logger.warning("NEXUS_ROOT: Ningún handler tomó la decisión - fallback BASE")
        metadatos_acumulados["nivel_activado"] = "BASE_PRIORITY_FALLBACK"
        
        return {
            "decision": "fallback_base",
            "nivel": "BASE_PRIORITY_FALLBACK",
            "metadatos": metadatos_acumulados,
            "override": "Entrada procesada por defecto Base",
        }
    
    def reset(self):
        """Resetear el estado interno del motor (por si hay estado mutable)."""
        pass  # El motor es esencialmente stateless en esta implementación


# ============================================================
# FUNCIÓN DE CONVENIENCIA
# ============================================================

def crear_nexus_root(motor: HPRSecurityEngine) -> NexusRootPrecedenceEngine:
    """
    Factoría para crear una instancia de NexusRootPrecedenceEngine.
    
    Args:
        motor: Instancia de HPRSecurityEngine
        
    Returns:
        NexusRootPrecedenceEngine configurado
    """
    return NexusRootPrecedenceEngine(motor)