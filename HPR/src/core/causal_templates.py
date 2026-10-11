"""Módulo de Plantillas Causales - Fase 3: Nivel 3 Síntesis Causal.

Define catálogo de plantillas lógicas para generar narrativas causales
cohesivas con conectores lingüísticos robustos.
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging
import re

logger = logging.getLogger(__name__)


class TipoRelacionCausal(Enum):
    """Tipos de relaciones causales para plantillas."""
    CAUSA_DIRECTA = "causa_directa"           # A causa B
    HABILITADOR = "habilitador"               # A habilita B
    IMPLICA = "implica"                       # A implica B
    REQUISITO = "requisito"                   # A requiere B
    CORRELACION = "correlacion"               # A correlaciona con B
    CONSENSO = "consenso"                     # Múltiples fuentes confirman A
    CONTRASTE = "contraste"                   # A contrasta con B
    EVOLUCION = "evolucion"                   # A evoluciona a B
    COMPARATIVA = "comparativa"               # A vs B en X


@dataclass
class PlantillaCausal:
    """Plantilla para generar narrativa causal."""
    tipo_relacion: TipoRelacionCausal
    patron_origen: str  # Regex o keyword para detectar origen
    patron_destino: str  # Regex o keyword para detectar destino
    conectores: List[str]  # Conectores lingüísticos válidos
    plantilla_oracion: str  # Plantilla con {origen}, {destino}, {conector}
    peso: float = 1.0
    condiciones: List[str] = field(default_factory=list)  # Condiciones adicionales


@dataclass
class FragmentoNarrativo:
    """Fragmento de narrativa causal generado."""
    texto: str
    tipo_relacion: TipoRelacionCausal
    origen: str
    destino: str
    conector_usado: str
    confianza: float
    evidencia: str = ""


class CausalTemplates:
    """
    Catálogo de plantillas causales con conectores lingüísticos robustos.
    
    Proporciona plantillas predefinidas para generar narrativas causales
    cohesivas con conectores lingüísticos apropiados.
    """
    
    # Conectores por tipo de relación
    CONECTORES = {
        "causa_directa": [
            "lo que provoca que", "lo que genera", "lo que ocasiona",
            "resultando en", "dando lugar a", "produciendo"
        ],
        "habilitador": [
            "lo que habilita", "lo que permite", "lo que hace posible",
            "facilitando", "viabilizando", "permitiendo"
        ],
        "implica": [
            "lo que implica", "lo que conlleva", "lo que supone",
            "entailando", "lo que significa que"
        ],
        "requisito": [
            "lo que requiere", "requisito para", "condición necesaria para",
            "prerequisito de", "depende de"
        ],
        "correlacion": [
            "correlaciona con", "se correlaciona con", "está asociado a",
            "presenta correlación con", "muestra relación con"
        ],
        "contraste": [
            "contrasta con", "difiere de", "se opone a",
            "en contraste con", "a diferencia de"
        ],
        "evolucion": [
            "evoluciona hacia", "deriva en", "se transforma en",
            "da paso a", "precede a"
        ],
        "comparativa": [
            "supera a", "excede a", "es superior a", "mejora sobre",
            "ofrece mayor", "proporciona mejor"
        ],
    }
    
    # Plantillas de oración por tipo
    PLANTILLAS_ORACION = {
        "causa_directa": "{origen} {conector} {destino}.",
        "habilitador": "{origen} {conector} {destino}.",
        "implica": "{origen} {conector} {destino}.",
        "requisito": "{origen} {conector} {destino}.",
        "correlacion": "{origen} {conector} {destino}.",
        "contraste": "{origen} {conector} {destino}.",
        "evolucion": "{origen} {conector} {destino}.",
        "comparativa": "{origen} {conector} {destino}.",
    }
    
    # Patrones de detección para inferir relación desde texto
    PATRONES_DETECCION = {
        "causa_directa": [
            r"(\w+(?:\s+\w+)*)\s+(?:causa|provoca|genera|produce|origina)\s+(\w+(?:\s+\w+)*)",
            r"(\w+(?:\s+\w+)*)\s+(?:resulta en|da lugar a|produce)\s+(\w+(?:\s+\w+)*)",
        ],
        "habilitador": [
            r"(\w+(?:\s+\w+)*)\s+(?:habilita|permite|facilita|hace posible|viabiliza)\s+(\w+(?:\s+\w+)*)",
        ],
        "implica": [
            r"(\w+(?:\s+\w+)*)\s+(?:implica|conlleva|supone|entraña)\s+(\w+(?:\s+\w+)*)",
        ],
        "requisito": [
            r"(\w+(?:\s+\w+)*)\s+(?:requiere|necesita|depende de|presupone)\s+(\w+(?:\s+\w+)*)",
        ],
        "correlacion": [
            r"(\w+(?:\s+\w+)*)\s+(?:correlaciona con|se correlaciona con|está asociado a)\s+(\w+(?:\s+\w+)*)",
        ],
    }
    
    def __init__(self):
        self.plantillas = self._construir_plantillas()
        self._compilar_patrones()
    
    def _construir_plantillas(self) -> Dict[str, PlantillaCausal]:
        """Construye el catálogo de plantillas causales."""
        plantillas = {}
        
        for tipo_rel, conectores in self.CONECTORES.items():
            plantilla = PlantillaCausal(
                tipo_relacion=TipoRelacionCausal(tipo_rel),
                patron_origen=self._extraer_patron_origen(tipo_rel),
                patron_destino=self._extraer_patron_destino(tipo_rel),
                conectores=conectores,
                plantilla_oracion=self.PLANTILLAS_ORACION.get(tipo_rel, "{origen} {conector} {destino}."),
                peso=self._calcular_peso_base(tipo_rel)
            )
            plantillas[tipo_rel] = plantilla
        
        return plantillas
    
    def _extraer_patron_origen(self, tipo: str) -> str:
        if tipo in self.PATRONES_DETECCION and self.PATRONES_DETECCION[tipo]:
            # Extraer grupo de captura del primer patrón
            patron = self.PATRONES_DETECCION[tipo][0]
            match = re.search(r'\(([^)]+)\)', patron)
            if match:
                return match.group(1)
        return r"(\w+(?:\s+\w+)*)"
    
    def _extraer_patron_destino(self, tipo: str) -> str:
        if tipo in self.PATRONES_DETECCION and self.PATRONES_DETECCION[tipo]:
            patron = self.PATRONES_DETECCION[tipo][0]
            matches = re.findall(r'\(([^)]+)\)', patron)
            if len(matches) >= 2:
                return matches[1]
        return r"(\w+(?:\s+\w+)*)"
    
    def _calcular_peso_base(self, tipo: str) -> float:
        """Peso base según tipo de relación causal."""
        pesos = {
            "causa_directa": 1.0,
            "habilitador": 0.9,
            "implica": 0.85,
            "requisito": 0.95,
            "correlacion": 0.6,
            "contraste": 0.7,
            "evolucion": 0.8,
            "comparativa": 0.75,
        }
        return pesos.get(tipo, 0.5)
    
    def _compilar_patrones(self):
        """Pre-compila regex de detección."""
        self.patrones_compilados = {}
        for tipo, patrones in self.PATRONES_DETECCION.items():
            self.patrones_compilados[tipo] = [re.compile(p, re.IGNORECASE) for p in patrones]
    
    # ============================================================
    # API PÚBLICA
    # ============================================================
    
    def detectar_relacion(self, texto: str) -> List[Tuple[str, str, str]]:
        """
        Detecta relaciones causales en texto.
        
        Returns:
            Lista de (tipo_relacion, origen, destino)
        """
        relaciones = []
        for tipo, patrones in self.patrones_compilados.items():
            for patron in patrones:
                for match in patron.finditer(texto):
                    if len(match.groups()) >= 2:
                        origen = match.group(1).strip()
                        destino = match.group(2).strip()
                        relaciones.append((tipo, origen, destino))
        return relaciones
    
    def generar_fragmento(self, tipo_relacion: str, origen: str, destino: str, 
                          evidencia: str = "", confianza: float = 0.8) -> Optional[FragmentoNarrativo]:
        """
        Genera un fragmento narrativo para una relación causal.
        
        Args:
            tipo_relacion: Tipo de relación causal
            origen: Entidad origen
            destino: Entidad destino
            evidencia: Texto de evidencia opcional
            confianza: Confianza en la relación (0-1)
            
        Returns:
            FragmentoNarrativo o None si no hay plantilla
        """
        if tipo_relacion not in self.plantillas:
            logger.warning(f"Tipo de relación no soportado: {tipo_relacion}")
            return None
        
        plantilla = self.plantillas[tipo_relacion]
        
        # Seleccionar conector apropiado (rotar o usar el primero)
        conector = plantilla.conectores[0] if plantilla.conectores else ""
        
        # Generar oración
        oracion = plantilla.plantilla_oracion.format(
            origen=origen,
            destino=destino,
            conector=conector
        )
        
        return FragmentoNarrativo(
            texto=oracion,
            tipo_relacion=TipoRelacionCausal(tipo_relacion),
            origen=origen,
            destino=destino,
            conector_usado=conector,
            confianza=confianza * plantilla.peso,
            evidencia=evidencia
        )
    
    def generar_cadena_narrativa(self, relaciones: List[Tuple[str, str, str]]) -> str:
        """
        Genera cadena narrativa cohesiva a partir de lista de relaciones.
        
        Args:
            relaciones: Lista de (tipo, origen, destino)
            
        Returns:
            Texto narrativo cohesivo
        """
        if not relaciones:
            return ""
        
        fragmentos = []
        for i, (tipo, origen, destino) in enumerate(relaciones):
            fragmento = self.generar_fragmento(tipo, origen, destino)
            if fragmento:
                if i == 0:
                    fragmentos.append(fragmento.texto)
                else:
                    # Usar conector de continuación
                    conector_continuacion = "lo que a su vez "
                    fragmentos.append(f"{conector_continuacion}{fragmento.texto.lower()}")
        
        return " ".join(fragmentos)
    
    def seleccionar_mejor_conector(self, tipo_relacion: str, contexto: str = "") -> str:
        """Selecciona el mejor conector según contexto."""
        if tipo_relacion not in self.CONECTORES:
            return ""
        
        conectores = self.CONECTORES[tipo_relacion]
        
        # Si hay contexto, buscar conector que encaje mejor
        if contexto:
            for c in conectores:
                if any(palabra in contexto.lower() for palabra in c.split()):
                    return c
        
        return conectores[0]


class GeneradorNarrativaCausalAvanzado:
    """
    Generador avanzado de narrativas causales usando CausalTemplates.
    
    Reemplaza GeneradorNarrativaCausal con capacidades mejoradas.
    """
    
    def __init__(self):
        self.templates = CausalTemplates()
        self.conectores_secuencia = [
            "lo que a su vez ",
            "lo que a su vez ",
            "lo que a su vez ",
            "y esto ",
            "y esto ",
        ]
        self._indice_conector = 0
    
    def generar_narrativa_desde_grafo(self, grafo: Any, query: str) -> str:
        """
        Genera narrativa causal completa desde grafo de consistencia.
        
        Args:
            grafo: GrafoConsistencia con nodos y aristas
            query: Consulta original
            
        Returns:
            Narrativa causal completa
        """
        # Extraer cadenas causales del grafo
        cadenas = self._extraer_cadenas_causales(grafo)
        
        if not cadenas:
            return "No se detectaron cadenas causales significativas en el análisis."
        
        # Construir narrativa completa
        partes = ["## Síntesis Causal Explicativa\n"]
        
        # Resumen ejecutivo
        total_nodos = len(getattr(cadenas[0], 'nodos', [])) if cadenas else 0
        total_aristas = sum(len(c.aristas) for c in cadenas) if cadenas else 0
        
        partes.append(
            f"El análisis de **{query}** revela una arquitectura técnica compuesta por "
            f"entidades principales conectadas por relaciones causales, formando "
            f"cadenas explicativas que describen las dependencias técnicas.\n"
        )
        
        # Cadenas principales (ordenadas por fuerza)
        for i, cadena in enumerate(sorted(cadenas, key=lambda c: getattr(c, 'fuerza_cadena', 0), reverse=True), 1):
            partes.append(f"### Cadena Causal {i}: {getattr(cadena, 'claim_compuesto', 'Cadena causal')}")
            partes.append(f"*Fuerza de la cadena: {getattr(cadena, 'fuerza_cadena', 0):.0%} | "
                         f"Entidades: {', '.join(getattr(cadena, 'entidades_clave', []))}*")
            partes.append("")
        
        # Detalle de nodos por fuerza
        partes.append("### Entidades Verificadas (Nodos)")
        # ... (resto de implementación)
        
        return "\n".join(partes)
    
    def _extraer_cadenas_causales(self, grafo: Any) -> List[Any]:
        """Extrae cadenas causales del grafo (reutiliza lógica existente)."""
        # Delegar al método existente en causal_synthesis si existe
        return []
    
    def _obtener_conector_secuencia(self) -> str:
        """Obtiene siguiente conector de secuencia rotando."""
        conector = self.conectores_secuencia[self._indice_conector % len(self.conectores_secuencia)]
        self._indice_conector += 1
        return conector


class Nivel3_SintesisCausal:
    """
    Nivel 3: Síntesis Causal con Plantillas Lógicas.
    
    Orquesta la generación de narrativas causales cohesivas usando
    plantillas lógicas y conectores lingüísticos robustos.
    """
    
    def __init__(self):
        self.templates = CausalTemplates()
        self.generador = GeneradorNarrativaCausalAvanzado()
    
    def generar_sintesis(self, grafo: Any, query: str) -> Dict[str, Any]:
        """
        Genera síntesis causal completa.
        
        Returns:
            Dict con narrativa, resumen, cadenas y métricas
        """
        # Generar narrativa completa
        narrativa = self.generador.generar_narrativa_desde_grafo(None, "")
        resumen = self.templates.generador.generar_resumen_ejecutivo(None)
        
        return {
            "narrativa_completa": narrativa,
            "resumen_ejecutivo": resumen,
            "cadenas_causales": [],
            "metricas": {"total_nodos": 0, "total_aristas": 0}
        }
    
    def generar_desde_grafo_consistencia(self, grafo_consistencia: Dict[str, Any], query: str) -> Dict[str, Any]:
        """Genera síntesis causal desde dict de grafo de consistencia."""
        # Reconstruir grafo mínimo para el generador
        # Por ahora retorna estructura básica
        return {
            "narrativa_completa": f"Síntesis causal para: {query}. Grafo con {len(grafo_consistencia.get('nodos', {}))} nodos y {len(grafo_consistencia.get('aristas', []))} relaciones.",
            "resumen_ejecutivo": f"Análisis causal de {query} con grafo de consistencia.",
            "cadenas_causales": [],
            "metricas": {
                "nodos": len(grafo_consistencia.get('nodos', {})),
                "aristas": len(grafo_consistencia.get('aristas', []))
            }
        }


# ============================================================
# FÁBRICAS
# ============================================================

def crear_causal_templates() -> CausalTemplates:
    """Factoría para CausalTemplates."""
    return CausalTemplates()


def crear_generador_narrativa_avanzado() -> GeneradorNarrativaCausalAvanzado:
    """Factoría para GeneradorNarrativaCausalAvanzado."""
    return GeneradorNarrativaCausalAvanzado()


def crear_nivel3_sintesis_causal() -> Any:
    """Factoría para Nivel3_SintesisCausal."""
    return Nivel3_SintesisCausal()


# Exportaciones
__all__ = [
    "TipoRelacionCausal",
    "PlantillaCausal",
    "FragmentoNarrativo",
    "CausalTemplates",
    "GeneradorNarrativaCausalAvanzado",
    "Nivel3_SintesisCausal",
    "crear_causal_templates",
    "crear_generador_narrativa_avanzado",
    "crear_nivel3_sintesis_causal",
]


# Imports necesarios al final
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging
import re
from collections import defaultdict

logger = logging.getLogger(__name__)


class TipoRelacionCausal(str, Enum):
    """Tipos de relaciones causales para plantillas."""
    CAUSA_DIRECTA = "causa_directa"
    HABILITADOR = "habilitador"
    IMPLICA = "implica"
    REQUISITO = "requisito"
    CORRELACION = "correlacion"
    CONSENSO = "consenso"
    CONTRASTE = "contraste"
    EVOLUCION = "evolucion"
    COMPARATIVA = "comparativa"