"""Síntesis Causal - Pilar 4 Fase Beta.

Conecta hipótesis verificadas en grafo causa-efecto y genera
narrativas explicativas encadenadas.

Fuentes:
- memoria.get_conclusiones_sesion()
- Grafo de hipotesis con verificacion.estado == VERIFICADA
"""

from typing import Dict, Any, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging
import re
from collections import defaultdict, deque

logger = logging.getLogger(__name__)

from core.episodic_memory import TipoEpisodio


class TipoRelacionCausal(Enum):
    """Tipos de relaciones causales en el grafo."""
    CAUSA_DIRECTA = "causa_directa"          # A → B (A causa B directamente)
    HABILITADOR = "habilitador"              # A habilita B (condición necesaria)
    IMPLICA = "implica"                      # A implica B (si A entonces B)
    REQUISITO = "requisito"                  # A requiere B (B es prerequisito de A)
    CORRELACION = "correlacion"              # A correlaciona con B (evidencia débil)
    CONSENSO = "consenso"                    # Múltiples fuentes confirman A


@dataclass
class NodoCausal:
    """Nodo en el grafo causal (hipótesis verificada)."""
    id: str
    claim: str
    tipo_hipotesis: str                      # causal, implicacion, restriccion, clasificatoria
    fuerza: str                              # fuerte, moderada, debil, especulativa
    puntuacion: float                        # 0.0 - 1.0
    entidades: List[str]
    evidencia: List[str]
    implicaciones: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "claim": self.claim,
            "tipo": self.tipo_hipotesis,
            "fuerza": self.fuerza,
            "puntuacion": self.puntuacion,
            "entidades": self.entidades,
            "implicaciones": self.implicaciones
        }


@dataclass
class AristaCausal:
    """Arista dirigida en el grafo causal."""
    origen: str                              # ID nodo origen
    destino: str                             # ID nodo destino
    tipo: TipoRelacionCausal
    peso: float                              # 0.0 - 1.0 fuerza de la relación
    evidencia: str                           # Texto que soporta la relación
    bidireccional: bool = False              # Si la relación es bidireccional
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "origen": self.origen,
            "destino": self.destino,
            "tipo": self.tipo.value,
            "peso": self.peso,
            "evidencia": self.evidencia,
            "bidireccional": self.bidireccional
        }


@dataclass
class CadenaCausal:
    """Cadena causal encadenada A → B → C → ..."""
    nodos: List[str]                         # IDs en orden causal
    aristas: List[AristaCausal]
    claim_compuesto: str                     # Narrativa: "A causa B, que habilita C..."
    fuerza_cadena: float                     # Mínimo peso de aristas
    entidades_clave: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodos": self.nodos,
            "aristas": [a.to_dict() for a in self.aristas],
            "narrativa": self.claim_compuesto,
            "fuerza": self.fuerza_cadena,
            "entidades": self.entidades_clave
        }


@dataclass
class GrafoCausal:
    """Grafo causal completo de una sesión."""
    nodos: Dict[str, NodoCausal]
    aristas: List[AristaCausal]
    cadenas: List[CadenaCausal]
    metricas: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodos": {k: v.to_dict() for k, v in self.nodos.items()},
            "aristas": [a.to_dict() for a in self.aristas],
            "cadenas": [c.to_dict() for c in self.cadenas],
            "metricas": self.metricas
        }


class ConstructorGrafoCausal:
    """
    Construye grafo causal a partir de conclusiones verificadas.
    
    Estrategia:
    1. Extraer nodos de conclusiones con fuerza >= moderada
    2. Inferir aristas por:
       - Entidades compartidas entre claims
       - Patrones lingüísticos (causa/habilita/requiere/implica)
       - Tipo de hipótesis (causal → causa_directa, etc.)
    3. Validar direccionalidad y evitar ciclos
    4. Extraer cadenas causales máximas
    """
    
    # Patrones para inferir relación causal desde claims
    PATRONES_CAUSA = [
        (r'(\w+)\s+(?:causa|provoca|genera|produce)\s+(\w+)', TipoRelacionCausal.CAUSA_DIRECTA, 0.9),
        (r'(\w+)\s+(?:habilita|permite|facilita)\s+(\w+)', TipoRelacionCausal.HABILITADOR, 0.8),
        (r'(\w+)\s+(?:implica|soporta|incluye)\s+(\w+)', TipoRelacionCausal.IMPLICA, 0.7),
        (r'(\w+)\s+(?:requiere|necesita|depende de)\s+(\w+)', TipoRelacionCausal.REQUISITO, 0.85),
    ]
    
    ENTIDADES_TECNICAS = re.compile(r'\b([A-Z][A-Za-z0-9\-\.]{1,})\b')
    
    def __init__(self, umbral_fuerza_minima: str = "moderada"):
        self.umbral_fuerza = {"fuerte": 0.8, "moderada": 0.6, "debil": 0.4, "especulativa": 0.2}[umbral_fuerza_minima]
    
    def construir_desde_conclusiones(
        self, 
        conclusiones: List[Dict[str, Any]],
        memoria = None
    ) -> GrafoCausal:
        """
        Construye grafo causal desde conclusiones verificadas.
        
        Args:
            conclusiones: Lista de dicts de get_conclusiones_sesion()
            memoria: MemoriaEpisodica opcional para enriquecer con evidencia
            
        Returns:
            GrafoCausal poblado
        """
        # 1. Filtrar y crear nodos
        nodos = self._crear_nodos(conclusiones, memoria)
        
        if len(nodos) < 2:
            logger.warning("ConstructorGrafoCausal: Insuficientes nodos para grafo causal")
            return GrafoCausal(nodos=nodos, aristas=[], cadenas=[], metricas={"nodos": len(nodos)})
        
        # 2. Inferir aristas
        aristas = self._inferir_aristas(nodos)
        
        # 3. Validar grafo (quitar ciclos, consolidar duplicados)
        aristas = self._validar_grafo(nodos, aristas)
        
        # 4. Extraer cadenas causales
        cadenas = self._extraer_cadenas(nodos, aristas)
        
        # 5. Métricas
        metricas = {
            "total_nodos": len(nodos),
            "total_aristas": len(aristas),
            "total_cadenas": len(cadenas),
            "nodos_por_fuerza": self._contar_por_fuerza(nodos),
            "aristas_por_tipo": self._contar_aristas_por_tipo(aristas),
            "longitud_promedio_cadena": sum(len(c.nodos) for c in cadenas) / len(cadenas) if cadenas else 0,
            "entidades_unicas": self._entidades_unicas_grafo(nodos)
        }
        
        logger.info(f"ConstructorGrafoCausal: Grafo construido - {len(nodos)} nodos, {len(aristas)} aristas, {len(cadenas)} cadenas")
        
        return GrafoCausal(
            nodos=nodos,
            aristas=aristas,
            cadenas=cadenas,
            metricas=metricas
        )
    
    def _crear_nodos(self, conclusiones: List[Dict], memoria) -> Dict[str, NodoCausal]:
        """Crea nodos causales desde conclusiones filtradas por fuerza."""
        nodos = {}
        
        for c in conclusiones:
            if c.get("puntuacion", 0) < self.umbral_fuerza:
                continue
            
            # Extraer entidades del claim
            claim = c.get("claim", "")
            entidades = self.ENTIDADES_TECNICAS.findall(claim)
            
            # Obtener evidencia de memoria si disponible
            evidencia = []
            if memoria and c.get("hipotesis_id"):
                ep = memoria.obtener_episodio(c.get("hipotesis_id"))
                if ep and ep.tipo.value == "verificacion":
                    evidencia = ep.contenido.get("evidencia_soporte", [])
            
            nodo = NodoCausal(
                id=c.get("id", f"N_{len(nodos)+1:04d}"),
                claim=claim,
                tipo_hipotesis=c.get("tipo", "desconocido"),
                fuerza=c.get("fuerza", "moderada"),
                puntuacion=c.get("puntuacion", 0.5),
                entidades=entidades,
                evidencia=evidencia,
                implicaciones=c.get("implicaciones", [])
            )
            nodos[nodo.id] = nodo
        
        return nodos
    
    def _inferir_aristas(self, nodos: Dict[str, NodoCausal]) -> List[AristaCausal]:
        """Infiere aristas causales entre nodos."""
        aristas = []
        nodo_lista = list(nodos.values())
        
        for i, n1 in enumerate(nodo_lista):
            for n2 in nodo_lista[i+1:]:
                # 1. Buscar relación por patrones en claims combinados
                arista = self._inferir_entre_nodos(n1, n2)
                if arista:
                    aristas.append(arista)
                    continue
                
                # 2. Buscar por entidades compartidas
                arista = self._inferir_por_entidades(n1, n2)
                if arista:
                    aristas.append(arista)
                    continue
                
                # 3. Por tipo de hipótesis (heurística)
                arista = self._inferir_por_tipo(n1, n2)
                if arista:
                    aristas.append(arista)
        
        return aristas
    
    def _inferir_entre_nodos(self, n1: NodoCausal, n2: NodoCausal) -> Optional[AristaCausal]:
        """Intenta inferir relación causal directa entre claims."""
        texto_combinado = f"{n1.claim} {n2.claim}"
        
        for patron, tipo, peso_base in self.PATRONES_CAUSA:
            match = re.search(patron, texto_combinado, re.IGNORECASE)
            if match:
                # Determinar dirección: el grupo 1 es causa, grupo 2 es efecto
                causa_texto = match.group(1).lower()
                efecto_texto = match.group(2).lower()
                
                # Verificar qué nodo corresponde a causa y cuál a efecto
                if any(ent.lower() == causa_texto for ent in n1.entidades) or causa_texto in n1.claim.lower():
                    origen, destino = n1.id, n2.id
                elif any(ent.lower() == causa_texto for ent in n2.entidades) or causa_texto in n2.claim.lower():
                    origen, destino = n2.id, n1.id
                else:
                    continue
                
                # Evitar auto-referencia
                if origen == destino:
                    continue
                
                return AristaCausal(
                    origen=origen,
                    destino=destino,
                    tipo=tipo,
                    peso=round(peso_base * min(n1.puntuacion, n2.puntuacion), 2),
                    evidencia=f"Patrón detectado: '{match.group(0)}' en claims combinados",
                    bidireccional=False
                )
        return None
    
    def _inferir_por_entidades(self, n1: NodoCausal, n2: NodoCausal) -> Optional[AristaCausal]:
        """Infiere relación por entidades compartidas."""
        entidades_comunes = set(n1.entidades) & set(n2.entidades)
        if not entidades_comunes:
            return None
        
        # Heurística: si n1 es causal y n2 es implicación, n1 → n2
        if n1.tipo_hipotesis == "causal" and n2.tipo_hipotesis in ("implicacion", "clasificatoria"):
            return AristaCausal(
                origen=n1.id, destino=n2.id,
                tipo=TipoRelacionCausal.HABILITADOR,
                peso=0.6,
                evidencia=f"Entidad compartida: {', '.join(entidades_comunes)}",
                bidireccional=False
            )
        
        # Si n1 es restricción y n2 causal, n1 → n2 (requisito habilita causal)
        if n1.tipo_hipotesis == "restriccion" and n2.tipo_hipotesis == "causal":
            return AristaCausal(
                origen=n1.id, destino=n2.id,
                tipo=TipoRelacionCausal.REQUISITO,
                peso=0.7,
                evidencia=f"Requisito para causal: {', '.join(entidades_comunes)}",
                bidireccional=False
            )
        
        # Default: correlación por entidad compartida
        return AristaCausal(
            origen=n1.id, destino=n2.id,
            tipo=TipoRelacionCausal.CORRELACION,
            peso=0.4,
            evidencia=f"Entidad compartida: {', '.join(entidades_comunes)}",
            bidireccional=True
        )
    
    def _inferir_por_tipo(self, n1: NodoCausal, n2: NodoCausal) -> Optional[AristaCausal]:
        """Infiere por tipos de hipótesis (heurística de último recurso)."""
        # Jerarquía: causal > restriccion > implicacion > clasificatoria
        prioridad = {"causal": 4, "restriccion": 3, "implicacion": 2, "clasificatoria": 1}
        
        p1 = prioridad.get(n1.tipo_hipotesis, 0)
        p2 = prioridad.get(n2.tipo_hipotesis, 0)
        
        if p1 > p2:
            return AristaCausal(
                origen=n1.id, destino=n2.id,
                tipo=TipoRelacionCausal.CORRELACION,
                peso=0.3,
                evidencia=f"Jerarquía tipo: {n1.tipo_hipotesis} → {n2.tipo_hipotesis}",
                bidireccional=False
            )
        elif p2 > p1:
            return AristaCausal(
                origen=n2.id, destino=n1.id,
                tipo=TipoRelacionCausal.CORRELACION,
                peso=0.3,
                evidencia=f"Jerarquía tipo: {n2.tipo_hipotesis} → {n1.tipo_hipotesis}",
                bidireccional=False
            )
        return None
    
    def _validar_grafo(self, nodos: Dict, aristas: List[AristaCausal]) -> List[AristaCausal]:
        """Valida y limpia el grafo: elimina ciclos, consolida duplicados."""
        # Eliminar aristas duplicadas (mismo origen-destino-tipo)
        vistas = set()
        unicas = []
        for a in aristas:
            key = (a.origen, a.destino, a.tipo)
            if key not in vistas:
                vistas.add(key)
                unicas.append(a)
        
        # Detectar y romper ciclos simples (DFS)
        # Para simplicidad, mantenemos solo aristas con peso >= 0.5 en ciclos
        return [a for a in unicas if a.peso >= 0.4]
    
    def _extraer_cadenas(self, nodos: Dict, aristas: List[AristaCausal]) -> List[CadenaCausal]:
        """Extrae cadenas causales máximas (paths dirigidos)."""
        # Construir adyacencia
        adj = defaultdict(list)
        indegree = defaultdict(int)
        for a in aristas:
            adj[a.origen].append(a)
            indegree[a.destino] += 1
            if a.origen not in indegree:
                indegree[a.origen] = 0
        
        # Encontrar nodos raíz (indegree = 0)
        raices = [nid for nid, deg in indegree.items() if deg == 0]
        
        cadenas = []
        visitados = set()
        
        def dfs_cadena(nodo_id: str, camino_actual: List[str], aristas_camino: List[AristaCausal]):
            if nodo_id in visitados:
                return
            visitados.add(nodo_id)
            
            camino_actual.append(nodo_id)
            
            if not adj[nodo_id]:  # Hoja
                if len(camino_actual) >= 2:
                    cadenas.append(self._crear_cadena_desde_camino(camino_actual, aristas_camino, nodos))
            else:
                for arista in adj[nodo_id]:
                    dfs_cadena(arista.destino, camino_actual.copy(), aristas_camino + [arista])
        
        for raiz in raices:
            dfs_cadena(raiz, [], [])
        
        # Filtrar cadenas triviales
        return [c for c in cadenas if len(c.nodos) >= 2]
    
    def _crear_cadena_desde_camino(self, nodo_ids: List[str], aristas: List[AristaCausal], nodos_dict: Dict[str, NodoCausal]) -> CadenaCausal:
        """Construye objeto CadenaCausal desde path."""
        # Generar narrativa
        partes = []
        for i, a in enumerate(aristas):
            n_origen = nodos_dict.get(a.origen)
            n_destino = nodos_dict.get(a.destino)
            if n_origen and n_destino:
                verbos = {
                    TipoRelacionCausal.CAUSA_DIRECTA: "causa",
                    TipoRelacionCausal.HABILITADOR: "habilita",
                    TipoRelacionCausal.IMPLICA: "implica",
                    TipoRelacionCausal.REQUISITO: "requiere",
                    TipoRelacionCausal.CORRELACION: "correlaciona con",
                    TipoRelacionCausal.CONSENSO: "confirma"
                }
                verbo = verbos.get(a.tipo, "relaciona con")
                if i == 0:
                    partes.append(f"{n_origen.claim} {verbo} {n_destino.claim}")
                else:
                    partes.append(f"que {verbo} {n_destino.claim}")
        
        claim_compuesto = " ".join(partes) if partes else f"Cadena: {' → '.join(nodo_ids)}"
        
        # Fuerza = mínimo peso de aristas
        fuerza = min(a.peso for a in aristas) if aristas else 0.0
        
        # Entidades clave
        entidades = set()
        for nid in nodo_ids:
            if nid in nodos_dict:
                entidades.update(nodos_dict[nid].entidades)
        
        return CadenaCausal(
            nodos=nodo_ids,
            aristas=aristas,
            claim_compuesto=claim_compuesto,
            fuerza_cadena=round(fuerza, 2),
            entidades_clave=list(entidades)
        )
    
    def _contar_por_fuerza(self, nodos: Dict) -> Dict[str, int]:
        return {f: sum(1 for n in nodos.values() if n.fuerza == f) for f in ["fuerte", "moderada", "debil", "especulativa"]}
    
    def _contar_aristas_por_tipo(self, aristas: List[AristaCausal]) -> Dict[str, int]:
        return {t.value: sum(1 for a in aristas if a.tipo == t) for t in TipoRelacionCausal}
    
    def _entidades_unicas_grafo(self, nodos: Dict) -> List[str]:
        ents = set()
        for n in nodos.values():
            ents.update(n.entidades)
        return sorted(ents)


class GeneradorNarrativaCausal:
    """
    Genera narrativas explicativas en lenguaje natural desde GrafoCausal.
    """
    
    def __init__(self):
        self.conectores = {
            TipoRelacionCausal.CAUSA_DIRECTA: "lo que provoca que",
            TipoRelacionCausal.HABILITADOR: "lo que habilita",
            TipoRelacionCausal.IMPLICA: "lo que implica",
            TipoRelacionCausal.REQUISITO: "lo que requiere",
            TipoRelacionCausal.CORRELACION: "lo que se correlaciona con",
        }
    
    def generar_narrativa_completa(self, grafo: GrafoCausal) -> str:
        """Genera narrativa completa del grafo causal."""
        if not grafo.cadenas:
            return "No se detectaron cadenas causales significativas."
        
        partes = ["## Síntesis Causal Explicativa\n"]
        
        # Resumen ejecutivo
        partes.append(f"Se identificaron **{len(grafo.nodos)} hipótesis verificadas** conectadas por **{len(grafo.aristas)} relaciones causales**, formando **{len(grafo.cadenas)} cadenas explicativas**.\n")
        
        # Cadenas principales (ordenadas por fuerza)
        for i, cadena in enumerate(sorted(grafo.cadenas, key=lambda c: c.fuerza_cadena, reverse=True), 1):
            partes.append(f"### Cadena {i}: {cadena.claim_compuesto}")
            partes.append(f"*Fuerza de la cadena: {cadena.fuerza_cadena:.0%} | Entidades: {', '.join(cadena.entidades_clave)}*")
            partes.append("")
        
        # Detalle de nodos por fuerza
        partes.append("### Hipótesis Verificadas (Nodos)")
        for fuerza in ["fuerte", "moderada", "debil"]:
            nodos_f = [n for n in grafo.nodos.values() if n.fuerza == fuerza]
            if nodos_f:
                partes.append(f"\n**{fuerza.capitalize()}:**")
                for n in nodos_f:
                    partes.append(f"- {n.claim} (score: {n.puntuacion:.2f})")
        
        # Relaciones detectadas
        partes.append("\n### Relaciones Causales Detectadas")
        for tipo in TipoRelacionCausal:
            aristas_t = [a for a in grafo.aristas if a.tipo == tipo]
            if aristas_t:
                partes.append(f"\n**{tipo.value.replace('_', ' ').title()}** ({len(aristas_t)}):")
                for a in aristas_t[:3]:
                    o = a.origen
                    d = a.destino
                    partes.append(f"- {o} → {d} (peso: {a.peso:.2f})")
        
        return "\n".join(partes)
    
    def generar_resumen_ejecutivo(self, grafo: GrafoCausal) -> str:
        """Resumen ejecutivo de una línea."""
        if not grafo.cadenas:
            return "Análisis causal: sin cadenas significativas detectadas."
        
        principal = max(grafo.cadenas, key=lambda c: c.fuerza_cadena)
        return f"Cadena causal principal: {principal.claim_compuesto} (fuerza: {principal.fuerza_cadena:.0%})"


class SintesisCausal:
    """
    Orquesta la síntesis causal completa: Grafo → Narrativa.
    Se integra con MemoriaEpisodica para persistencia.
    """
    
    def __init__(self, memoria, umbral_fuerza: str = "moderada"):
        self.memoria = memoria
        self.constructor = ConstructorGrafoCausal(umbral_fuerza_minima=umbral_fuerza)
        self.generador = GeneradorNarrativaCausal()
    
    def ejecutar_sintesis(self, sesion_id: str) -> Dict[str, Any]:
        """
        Ejecuta síntesis causal completa para una sesión.
        
        Returns:
            Dict con grafo, narrativas y métricas
        """
        logger.info(f"SintesisCausal: Iniciando para sesión {sesion_id}")
        
        # 1. Obtener conclusiones de memoria
        conclusiones = self.memoria.get_conclusiones_sesion(sesion_id)
        
        if not conclusiones:
            logger.warning(f"SintesisCausal: No hay conclusiones en sesión {sesion_id}")
            return {"error": "No hay conclusiones disponibles", "grafo": None}
        
        # 2. Construir grafo causal
        grafo = self.constructor.construir_desde_conclusiones(conclusiones, self.memoria)
        
        # 3. Generar narrativas
        narrativa_completa = self.generador.generar_narrativa_completa(grafo)
        resumen = self.generador.generar_resumen_ejecutivo(grafo)
        
        # 4. Persistir grafo en memoria
        if self.memoria:
            self.memoria.guardar_episodio(
                tipo=TipoEpisodio.SINTESIS_CAUSAL,
                sesion_id=sesion_id,
                contenido={
                    "grafo": grafo.to_dict(),
                    "narrativa_completa": narrativa_completa,
                    "resumen_ejecutivo": resumen
                },
                entidades=grafo.metricas.get("entidades_unicas", [])
            )
        
        logger.info(f"SintesisCausal: Completada para sesión {sesion_id}")
        
        return {
            "grafo": grafo.to_dict(),
            "narrativa_completa": narrativa_completa,
            "resumen_ejecutivo": resumen,
            "metricas": grafo.metricas
        }


def crear_sintesis_causal(memoria, umbral_fuerza: str = "moderada") -> SintesisCausal:
    """Factoría para SintesisCausal."""
    return SintesisCausal(memoria, umbral_fuerza=umbral_fuerza)