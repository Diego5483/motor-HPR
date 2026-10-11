"""Módulo de Enhebrado Estructural - Fase 2: Nivel 2 Grafo de Consistencia.

Implementa validación y enhebrado lógico de hallazgos técnicos,
asegurando que métricas, especificaciones y versiones estén
correctamente asociadas a sus entidades técnicas.
"""

from typing import Dict, Any, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class TipoNodo(Enum):
    """Tipos de nodos en el grafo de consistencia."""
    ENTIDAD = "entidad"
    METRICA = "metrica"
    ESPECIFICACION = "especificacion"
    VERSION = "version"
    ARQUITECTURA = "arquitectura"
    CARACTERISTICA = "caracteristica"


class TipoRelacion(Enum):
    """Tipos de relaciones en el grafo."""
    TIENE_METRICA = "tiene_metrica"
    TIENE_ESPECIFICACION = "tiene_especificacion"
    TIENE_VERSION = "tiene_version"
    IMPLEMENTA = "implementa"
    SOPORTA = "soporta"
    HABILITA = "habilita"
    REQUIERE = "requiere"
    CORRELACIONA_CON = "correlaciona_con"


@dataclass
class NodoGrafo:
    """Nodo en el grafo de consistencia."""
    id: str
    tipo: TipoNodo
    nombre: str
    descripcion: str
    fuente: str
    confianza: float
    hallazgo_original: Optional[Any] = None
    atributos: Dict[str, Any] = field(default_factory=dict)
    
    def __hash__(self):
        return hash(self.id)
    
    def __eq__(self, other):
        return isinstance(other, NodoGrafo) and self.id == other.id


@dataclass
class AristaGrafo:
    """Arista dirigida en el grafo de consistencia."""
    origen_id: str
    destino_id: str
    tipo: TipoRelacion
    peso: float = 1.0
    evidencia: str = ""
    bidireccional: bool = False
    
    def __hash__(self):
        return hash((self.origen_id, self.destino_id, self.tipo))


@dataclass
class Inconsistencia:
    """Representa una inconsistencia detectada en el grafo."""
    tipo: str  # "metrica_huerfana", "spec_sin_entidad", "version_sin_entidad", "conflicto_version"
    descripcion: str
    nodos_afectados: List[str]
    severidad: str  # "critica", "advertencia", "info"
    sugerencia_correccion: str = ""


@dataclass
class GrafoConsistencia:
    """Grafo de consistencia estructural para hallazgos técnicos."""
    nodos: Dict[str, NodoGrafo] = field(default_factory=dict)
    aristas: List[AristaGrafo] = field(default_factory=list)
    inconsistencias: List[Inconsistencia] = field(default_factory=list)
    metricas: Dict[str, Any] = field(default_factory=dict)
    
    def agregar_nodo(self, nodo: NodoGrafo) -> None:
        """Agrega nodo al grafo si no existe."""
        if nodo.id not in self.nodos:
            self.nodos[nodo.id] = nodo
    
    def agregar_arista(self, arista: AristaGrafo) -> None:
        """Agrega arista al grafo."""
        # Verificar que ambos nodos existen
        if arista.origen_id in self.nodos and arista.destino_id in self.nodos:
            self.aristas.append(arista)
        else:
            logger.warning(f"Arista ignorada: nodos no existen {arista.origen_id} -> {arista.destino_id}")
    
    def obtener_nodo(self, nodo_id: str) -> Optional[NodoGrafo]:
        return self.nodos.get(nodo_id)
    
    def obtener_vecinos(self, nodo_id: str, tipo_relacion: Optional[TipoRelacion] = None) -> List[Tuple[AristaGrafo, NodoGrafo]]:
        """Obtiene vecinos de un nodo."""
        vecinos = []
        for arista in self.aristas:
            if arista.origen_id == nodo_id:
                if tipo_relacion is None or arista.tipo == tipo_relacion:
                    destino = self.nodos.get(arista.destino_id)
                    if destino:
                        vecinos.append((arista, destino))
            elif arista.bidireccional and arista.destino_id == nodo_id:
                if tipo_relacion is None or arista.tipo == tipo_relacion:
                    origen = self.nodos.get(arista.origen_id)
                    if origen:
                        vecinos.append((arista, origen))
        return vecinos
    
    def obtener_metricas_huerfanas(self) -> List[NodoGrafo]:
        """Retorna métricas sin entidad asociada."""
        huérfanas = []
        for nodo_id, nodo in self.nodos.items():
            if nodo.tipo == TipoNodo.METRICA:
                # Verificar si tiene arista entrante de tipo TIENE_METRICA
                tiene_entidad = any(
                    a.destino_id == nodo_id and a.tipo == TipoRelacion.TIENE_METRICA
                    for a in self.aristas
                )
                if not tiene_entidad:
                    huérfanas.append(nodo)
        return huérfanas
    
    def obtener_specs_sin_entidad(self) -> List[NodoGrafo]:
        """Retorna especificaciones sin entidad asociada."""
        sin_entidad = []
        for nodo_id, nodo in self.nodos.items():
            if nodo.tipo == TipoNodo.ESPECIFICACION:
                tiene_entidad = any(
                    a.destino_id == nodo_id and a.tipo == TipoRelacion.TIENE_ESPECIFICACION
                    for a in self.aristas
                )
                if not tiene_entidad:
                    sin_entidad.append(nodo)
        return sin_entidad
    
    def obtener_versiones_sin_entidad(self) -> List[NodoGrafo]:
        """Retorna versiones sin entidad asociada."""
        sin_entidad = []
        for nodo_id, nodo in self.nodos.items():
            if nodo.tipo == TipoNodo.VERSION:
                tiene_entidad = any(
                    a.destino_id == nodo_id and a.tipo == TipoRelacion.TIENE_VERSION
                    for a in self.aristas
                )
                if not tiene_entidad:
                    sin_entidad.append(nodo)
        return sin_entidad
    
    def calcular_metricas(self) -> Dict[str, Any]:
        """Calcula métricas del grafo."""
        total_nodos = len(self.nodos)
        total_aristas = len(self.aristas)
        
        por_tipo = defaultdict(int)
        for nodo in self.nodos.values():
            por_tipo[nodo.tipo.value] += 1
        
        metricas_huerfanas = len(self.obtener_metricas_huerfanas())
        specs_sin_entidad = len(self.obtener_specs_sin_entidad())
        versiones_sin_entidad = len(self.obtener_versiones_sin_entidad())
        
        return {
            "total_nodos": total_nodos,
            "total_aristas": total_aristas,
            "nodos_por_tipo": dict(por_tipo),
            "metricas_huerfanas": metricas_huerfanas,
            "specs_sin_entidad": specs_sin_entidad,
            "versiones_sin_entidad": versiones_sin_entidad,
            "inconsistencias_totales": len(self.inconsistencias),
            "densidad": total_aristas / total_nodos if total_nodos > 0 else 0,
        }
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodos": {k: {
                "id": v.id, "tipo": v.tipo.value, "nombre": v.nombre,
                "descripcion": v.descripcion, "fuente": v.fuente,
                "confianza": v.confianza
            } for k, v in self.nodos.items()},
            "aristas": [{
                "origen": a.origen_id, "destino": a.destino_id,
                "tipo": a.tipo.value, "peso": a.peso,
                "evidencia": a.evidencia
            } for a in self.aristas],
            "inconsistencias": [{
                "tipo": i.tipo, "descripcion": i.descripcion,
                "nodos": i.nodos_afectados, "severidad": i.severidad
            } for i in self.inconsistencias],
            "metricas": self.calcular_metricas()
        }


class Nivel2_EnhebradoEstructural:
    """
    Nivel 2: Enhebrado Estructural.
    
    Construye grafo de consistencia a partir de hallazgos técnicos,
    valida integridad lógica y detecta inconsistencias.
    """
    
    def __init__(self, min_confianza: float = 0.3):
        self.min_confianza = min_confianza
        self._contador_nodos = 0
    
    def _nuevo_id(self, prefijo: str) -> str:
        self._contador_nodos += 1
        return f"{prefijo}_{self._contador_nodos:04d}"
    
    def _determinar_tipo_nodo(self, hallazgo: Any) -> TipoNodo:
        """Determina tipo de nodo según hallazgo."""
        tipo = getattr(hallazgo, 'tipo', '')
        if tipo == "metrica":
            return TipoNodo.METRICA
        elif tipo == "especificacion":
            return TipoNodo.ESPECIFICACION
        elif tipo == "version":
            return TipoNodo.VERSION
        elif tipo == "arquitectura":
            return TipoNodo.ARQUITECTURA
        elif tipo == "caracteristica":
            return TipoNodo.CARACTERISTICA
        else:
            return TipoNodo.ENTIDAD
    
    def _extraer_entidad_principal(self, descripcion: str) -> str:
        """Extrae entidad técnica principal de descripción."""
        entidades_conocidas = [
            "RTX 4090", "RTX 4080", "RTX 4070 Ti", "RTX 4070",
            "Ada Lovelace", "Ampere", "Hopper", "ARMv9", "ARMv8",
            "MTE", "CCA", "SVE2", "RISC-V", "RVV",
            "Ryzen", "Core", "Xeon", "EPYC", "Cortex", "Neoverse",
            "GDDR6X", "GDDR6", "HBM", "L2", "L3", "L1",
            "Tensor cores", "RT cores", "CUDA cores",
            "NVENC", "DLSS", "RISC-V", "RVV"
        ]
        
        desc_lower = descripcion.lower()
        for entidad in sorted(entidades_conocidas, key=len, reverse=True):
            if entidad.lower() in desc_lower:
                return entidad
        return "Entidad_General"
    
    def construir_grafo(self, hallazgos: List[Any]) -> GrafoConsistencia:
        """
        Construye grafo de consistencia a partir de hallazgos.
        
        Args:
            hallazgos: Lista de HallazgoTecnico
            
        Returns:
            GrafoConsistencia con nodos, aristas e inconsistencias
        """
        grafo = GrafoConsistencia()
        self._contador_nodos = 0
        
        # 1. Crear nodos a partir de hallazgos
        nodos_por_hallazgo = {}
        for h in hallazgos:
            if hasattr(h, 'confianza') and h.confianza < 0.3:
                continue  # Filtrar baja confianza
            
            tipo_nodo = self._determinar_tipo_nodo(h)
            entidad = self._extraer_entidad_principal(h.descripcion)
            
            nodo_id = self._nuevo_id(tipo_nodo.value)
            nodo = NodoGrafo(
                id=nodo_id,
                tipo=tipo_nodo,
                nombre=entidad,
                descripcion=h.descripcion,
                fuente=h.fuente,
                confianza=h.confianza,
                hallazgo_original=h,
                atributos={"tipo_original": h.tipo}
            )
            grafo.agregar_nodo(nodo)
            nodos_por_hallazgo[id(h)] = nodo
        
        # 2. Crear aristas basadas en relaciones lógicas
        self._crear_aristas_logicas(grafo, nodos_por_hallazgo)
        
        # 3. Detectar inconsistencias
        self._detectar_inconsistencias(grafo)
        
        logger.info(f"Nivel2: Grafo construido - {len(grafo.nodos)} nodos, {len(grafo.aristas)} aristas, {len(grafo.inconsistencias)} inconsistencias")
        return grafo
    
    def _determinar_tipo_nodo(self, hallazgo: Any) -> TipoNodo:
        tipo = getattr(hallazgo, 'tipo', '')
        if tipo == "metrica":
            return TipoNodo.METRICA
        elif tipo == "especificacion":
            return TipoNodo.ESPECIFICACION
        elif tipo == "version":
            return TipoNodo.VERSION
        elif tipo == "arquitectura":
            return TipoNodo.ARQUITECTURA
        elif tipo == "caracteristica":
            return TipoNodo.CARACTERISTICA
        return TipoNodo.ENTIDAD
    
    def _crear_aristas_logicas(self, grafo: GrafoConsistencia, nodos_por_hallazgo: Dict) -> None:
        """Crea aristas basadas en relaciones lógicas entre nodos."""
        nodos = list(grafo.nodos.values())
        
        # Agrupar nodos por entidad para conexiones intra-entidad
        por_entidad = defaultdict(list)
        for nodo in nodos:
            por_entidad[nodo.nombre].append(nodo)
        
        for entidad, nodos_entidad in por_entidad.items():
            # Encontrar nodo entidad principal
            nodo_entidad = None
            otros_nodos = []
            for n in nodos_entidad:
                if n.tipo == TipoNodo.ENTIDAD or n.tipo == TipoNodo.ARQUITECTURA:
                    nodo_entidad = n
                else:
                    otros_nodos.append(n)
            
            if not nodo_entidad:
                # Crear nodo entidad si no existe
                nodo_entidad = self._crear_nodo_entidad(grafo, entidad)
            
            # Conectar otros nodos a la entidad
            for n in otros_nodos:
                relacion = self._inferir_relacion(nodo_entidad, n)
                if relacion:
                    arista = AristaGrafo(
                        origen_id=nodo_entidad.id,
                        destino_id=n.id,
                        tipo=relacion,
                        peso=0.8,
                        evidencia=f"Relación {relacion.value} inferida"
                    )
                    grafo.agregar_arista(arista)
        
        # Conexiones cruzadas entre entidades
        self._crear_aristas_cruzadas(grafo)
    
    def _crear_nodo_entidad(self, grafo: GrafoConsistencia, nombre: str) -> NodoGrafo:
        """Crea nodo entidad si no existe."""
        for nodo in grafo.nodos.values():
            if nodo.nombre == nombre and nodo.tipo in (TipoNodo.ENTIDAD, TipoNodo.ARQUITECTURA):
                return nodo
        
        nodo_id = f"ent_{len(grafo.nodos):04d}"
        nodo = NodoGrafo(
            id=nodo_id,
            tipo=TipoNodo.ENTIDAD,
            nombre=nombre,
            descripcion=f"Entidad técnica: {nombre}",
            fuente="inferida",
            confianza=0.7
        )
        grafo.agregar_nodo(nodo)
        return nodo
    
    def _inferir_relacion(self, entidad: NodoGrafo, nodo: NodoGrafo) -> Optional[TipoRelacion]:
        """Infierte tipo de relación entre entidad y nodo."""
        if nodo.tipo == TipoNodo.METRICA:
            return TipoRelacion.TIENE_METRICA
        elif nodo.tipo == TipoNodo.ESPECIFICACION:
            return TipoRelacion.TIENE_ESPECIFICACION
        elif nodo.tipo == TipoNodo.VERSION:
            return TipoRelacion.TIENE_VERSION
        elif nodo.tipo == TipoNodo.CARACTERISTICA:
            # Analizar descripción para inferir relación
            desc = nodo.descripcion.lower()
            if any(kw in desc for kw in ["habilita", "permite", "permite que", "hace posible"]):
                return TipoRelacion.HABILITA
            elif any(kw in desc for kw in ["requiere", "necesita", "depende"]):
                return TipoRelacion.REQUIERE
            elif any(kw in desc for kw in ["implica", "soporta", "incluye"]):
                return TipoRelacion.SOPORTA
            return TipoRelacion.SOPORTA
        elif nodo.tipo == TipoNodo.ARQUITECTURA:
            return TipoRelacion.IMPLEMENTA
        return TipoRelacion.CORRELACIONA_CON
    
    def _crear_aristas_cruzadas(self, grafo: GrafoConsistencia) -> None:
        """Crea aristas cruzadas entre entidades relacionadas."""
        nodos = list(grafo.nodos.values())
        entidades = [n for n in nodos if n.tipo in (TipoNodo.ENTIDAD, TipoNodo.ARQUITECTURA)]
        
        for i, e1 in enumerate(entidades):
            for e2 in entidades[i+1:]:
                # Verificar relación causal o de requisito
                rel = self._inferir_relacion_entidades(e1, e2)
                if rel:
                    arista = AristaGrafo(
                        origen_id=e1.id,
                        destino_id=e2.id,
                        tipo=rel,
                        peso=0.6,
                        evidencia=f"Relación {rel.value} entre entidades"
                    )
                    grafo.agregar_arista(arista)
    
    def _inferir_relacion_entidades(self, e1: NodoGrafo, e2: NodoGrafo) -> Optional[TipoRelacion]:
        """Infierte relación entre dos entidades."""
        d1 = e1.descripcion.lower()
        d2 = e2.descripcion.lower()
        
        # Patrones causales
        if any(kw in d1 for kw in ["habilita", "permite", "hace posible"]) and any(kw in d2 for kw in ["requiere", "necesita", "depende"]):
            return TipoRelacion.HABILITA
        if any(kw in d2 for kw in ["habilita", "permite", "hace posible"]) and any(kw in d1 for kw in ["requiere", "necesita", "depende"]):
            return TipoRelacion.HABILITA
        
        # Requisito
        if any(kw in d1 for kw in ["requiere", "necesita", "depende"]) and "mte" in d1 and "cc" in d2:
            return TipoRelacion.REQUIERE
        
        return None
    
    def _detectar_inconsistencias(self, grafo: GrafoConsistencia) -> None:
        """Detecta y registra inconsistencias en el grafo."""
        
        # 1. Métricas huérfanas
        metricas_huerfanas = grafo.obtener_metricas_huerfanas()
        for m in metricas_huerfanas:
            grafo.inconsistencias.append(Inconsistencia(
                tipo="metrica_huerfana",
                descripcion=f"Métrica '{m.descripcion}' no tiene entidad asociada",
                nodos_afectados=[m.id],
                severidad="advertencia",
                sugerencia_correccion="Asociar métrica a entidad técnica correspondiente o buscar entidad faltante"
            ))
        
        # 2. Especificaciones sin entidad
        specs_sin_entidad = grafo.obtener_specs_sin_entidad()
        for s in specs_sin_entidad:
            grafo.inconsistencias.append(Inconsistencia(
                tipo="spec_sin_entidad",
                descripcion=f"Especificación '{s.descripcion[:80]}' sin entidad asociada",
                nodos_afectados=[s.id],
                severidad="advertencia",
                sugerencia_correccion="Vincular especificación a entidad técnica correspondiente"
            ))
        
        # 3. Versiones sin entidad
        versiones_sin_entidad = grafo.obtener_versiones_sin_entidad()
        for v in versiones_sin_entidad:
            grafo.inconsistencias.append(Inconsistencia(
                tipo="version_sin_entidad",
                descripcion=f"Versión '{v.descripcion[:80]}' sin entidad asociada",
                nodos_afectados=[v.id],
                severidad="info",
                sugerencia_correccion="Asociar versión a entidad técnica correspondiente"
            ))
        
        # 4. Conflictos de versión (múltiples versiones para misma entidad)
        self._detectar_conflictos_version(grafo)
    
    def _detectar_conflictos_version(self, grafo: GrafoConsistencia) -> None:
        """Detecta múltiples versiones para misma entidad."""
        versiones_por_entidad = defaultdict(list)
        
        for arista in grafo.aristas:
            if arista.tipo == TipoRelacion.TIENE_VERSION:
                origen = grafo.nodos.get(arista.origen_id)
                destino = grafo.nodos.get(arista.destino_id)
                if origen and destino and destino.tipo == TipoNodo.VERSION:
                    versiones_por_entidad[origen.id].append(destino)
        
        for entidad_id, versiones in versiones_por_entidad.items():
            if len(versiones) > 1:
                entidad = grafo.nodos.get(entidad_id)
                grafo.inconsistencias.append(Inconsistencia(
                    tipo="conflicto_version",
                    descripcion=f"Entidad '{entidad.nombre}' tiene {len(versiones)} versiones diferentes",
                    nodos_afectados=[v.id for v in versiones] + [entidad_id],
                    severidad="advertencia",
                    sugerencia_correccion="Verificar consistencia de versiones o especificar contexto de cada versión"
                ))
    
    def validar_grafo(self, grafo: GrafoConsistencia) -> Tuple[bool, List[str]]:
        """Valida grafo y retorna (es_valido, lista_errores)."""
        errores = []
        
        # Verificar métricas huérfanas
        huerfanas = grafo.obtener_metricas_huerfanas()
        if huerfanas:
            errores.append(f"{len(huerfanas)} métricas huérfanas sin entidad asociada")
        
        # Verificar specs sin entidad
        specs_orfanas = grafo.obtener_specs_sin_entidad()
        if specs_orfanas:
            errores.append(f"{len(specs_orfanas)} especificaciones sin entidad asociada")
        
        # Verificar inconsistencia críticas
        criticas = [i for i in grafo.inconsistencias if i.severidad == "critica"]
        if criticas:
            errores.extend([f"CRÍTICA: {c.descripcion}" for c in criticas])
        
        return len(errores) == 0, errores
    
    def obtener_brechas_para_planificador(self, grafo: GrafoConsistencia) -> List[Dict[str, Any]]:
        """Genera lista de brechas para el planificador iterativo."""
        brechas = []
        
        # Métricas huérfanas -> buscar entidad
        for m in grafo.obtener_metricas_huerfanas():
            brechas.append({
                "tipo": "metrica_huerfana",
                "hipotesis_id": m.hallazgo_original.id if m.hallazgo_original else m.id,
                "claim": f"Métrica '{m.descripcion}' requiere entidad asociada",
                "brecha": f"Métrica '{m.descripcion}' no tiene entidad asociada",
                "entidades": [m.nombre],
                "tipo_hipotesis": "metrica",
                "subquery_sugerida": f"@web_search {m.nombre} especificaciones tecnicas {m.descripcion}"
            })
        
        # Specs sin entidad
        for s in grafo.obtener_specs_sin_entidad():
            brechas.append({
                "tipo": "spec_sin_entidad",
                "hipotesis_id": s.hallazgo_original.id if s.hallazgo_original else s.id,
                "claim": f"Especificación requiere entidad",
                "brecha": f"Especificación '{s.descripcion[:80]}' sin entidad",
                "entidades": [s.nombre],
                "tipo_hipotesis": "especificacion",
                "subquery_sugerida": f"@web_search {s.nombre} arquitectura implementacion"
            })
        
        return brechas


def crear_nivel2_enhebrado(min_confianza: float = 0.3) -> Nivel2_EnhebradoEstructural:
    """Factoría para Nivel2_EnhebradoEstructural."""
    return Nivel2_EnhebradoEstructural(min_confianza=min_confianza)


# Import re para _inferir_relacion
import re
from collections import defaultdict
from typing import Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import logging

# Re-exportar tipos principales
__all__ = [
    "TipoNodo", "TipoRelacion", "NodoGrafo", "AristaGrafo",
    "Inconsistencia", "GrafoConsistencia", "Nivel2_EnhebradoEstructural",
    "crear_nivel2_enhebrado"
]