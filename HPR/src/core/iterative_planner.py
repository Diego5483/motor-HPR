"""Planificador de Búsqueda Iterativa - Pilar 3 Fase Beta.

Detecta brechas de conocimiento en MemoriaEpisodica y genera/ejecuta
sub-consultas automáticas para llenar gaps antes de síntesis final.

Flujo:
1. Consultar memoria.get_brechas_abiertas(sesion_id)
2. Para cada brecha → generar sub-query @web_search dirigida
3. Ejecutar búsqueda via ExternalToolExecutor
4. Procesar resultados → nuevos hallazgos → reiniciar pipeline razonamiento
5. Repetir hasta: no hay brechas O límite iteraciones alcanzado
"""

from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
import logging
import re

from core.episodic_memory import MemoriaEpisodica, TipoEpisodio
from nexus_root.executor import crear_executor, ExternalToolExecutor
from nexus_root.router import crear_nexus_router
from security_agent import HPRSecurityEngine

logger = logging.getLogger(__name__)


@dataclass
class BrechaConocimiento:
    """Brecha identificada con metadatos para planificación."""
    hipotesis_id: str
    claim: str
    brecha: str                    # Descripción de qué falta
    entidades: List[str]           # Entidades involucradas
    tipo_hipotesis: str            # causal, implicacion, restriccion, etc.
    prioridad: int = 1             # 1=alta, 2=media, 3=baja
    subqueries_generadas: List[str] = field(default_factory=list)
    intentos: int = 0
    resuelta: bool = False


@dataclass
class ResultadoSubquery:
    """Resultado de una sub-consulta ejecutada."""
    subquery: str
    brecha_origen: str             # ID de brecha que motivó la query
    exito: bool
    hallazgos_nuevos: List[Dict[str, Any]]  # HallazgoTecnico-like dicts
    error: Optional[str] = None


class GeneradorSubqueries:
    """
    Genera sub-consultas @web_search dirigidas a partir de brechas.
    
    Estrategias por tipo de hipótesis:
    - CAUSAL: "¿Cómo [causa] habilita [efecto]? mecanismo técnico"
    - IMPLICACION: "[arquitectura] [tecnologia] soporte implementación detalles"
    - RESTRICCION: "[requerido] requiere [requisito] por qué condición necesaria"
    - INDETERMINADA: "[entidades] especificación técnica documentación oficial"
    """
    
    PLANTILLAS = {
        "causal": [
            "cómo {causa} habilita {efecto} mecanismo técnico detalles",
            "{causa} {efecto} funcionamiento arquitectura implementación",
            "mecanismo {causa} provoca {efecto} explicación técnica",
        ],
        "implicacion": [
            "{arquitectura} {tecnologia} soporte implementación detalles técnicos",
            "{arquitectura} incluye {tecnologia} especificaciones características",
            "cómo {arquitectura} soporta {tecnologia} arquitectura diseño",
        ],
        "restriccion": [
            "{requerido} requiere {requisito} por qué condición necesaria razón",
            "{requerido} {requisito} dependencia requisito obligatorio explicación",
            "por qué {requerido} necesita {requisito} arquitectura hardware",
        ],
        "indeterminada": [
            "{entidades} especificación técnica documentación oficial detalles",
            "{entidades} arquitectura implementación características funcionamiento",
        ],
    }
    
    # Palabras clave para extraer entidades de roles en claim
    ROLES = {
        "causal": ["causa", "efecto"],
        "implicacion": ["arquitectura", "tecnologia"],
        "restriccion": ["requerido", "requisito"],
    }

    def __init__(self, max_subqueries_por_brecha: int = 2):
        self.max_subqueries = max_subqueries_por_brecha

    def generar_para_brecha(self, brecha: BrechaConocimiento) -> List[str]:
        """Genera sub-queries para una brecha específica."""
        tipo = brecha.tipo_hipotesis.lower()
        plantillas = self.PLANTILLAS.get(tipo, self.PLANTILLAS["indeterminada"])
        
        # Extraer entidades con roles del claim
        entidades_rol = self._extraer_roles_claim(brecha.claim, tipo)
        
        # Preparar valores de sustitución
        valores = dict(entidades_rol)
        valores["entidades"] = " ".join(brecha.entidades)
        for j, ent in enumerate(brecha.entidades):
            valores[f"entidad{j}"] = ent
        
        subqueries = []
        for plantilla in plantillas[:self.max_subqueries]:
            query = plantilla
            # Sustituir todos los placeholders
            for key, val in valores.items():
                query = query.replace(f"{{{key}}}", val)
            
            # Limpiar placeholders no resueltos
            query = re.sub(r'\{[^}]+\}', '', query)
            query = re.sub(r'\s+', ' ', query).strip()
            
            if query:
                query = f"@web_search {query}"
                if query not in subqueries:
                    subqueries.append(query)
        
        brecha.subqueries_generadas = subqueries
        return subqueries

    def _extraer_roles_claim(self, claim: str, tipo: str) -> Dict[str, str]:
        """Intenta extraer entidades con roles semánticos del claim."""
        roles = {}
        claim_lower = claim.lower()
        
        if tipo == "causal":
            # "A causa/habilita B" o "A implica B"
            match = re.search(r'(\w+)\s+(?:causa|habilita|implica|permite)\s+(\w+)', claim_lower)
            if match:
                roles["causa"] = match.group(1)
                roles["efecto"] = match.group(2)
        elif tipo == "implicacion":
            # "A implica/soporta B"
            match = re.search(r'(\w+)\s+(?:implica|soporta)\s+(\w+)', claim_lower)
            if match:
                roles["arquitectura"] = match.group(1)
                roles["tecnologia"] = match.group(2)
        elif tipo == "restriccion":
            # "A requiere B"
            match = re.search(r'(\w+)\s+requiere\s+(\w+)', claim_lower)
            if match:
                roles["requerido"] = match.group(1)
                roles["requisito"] = match.group(2)
        
        return roles


class PlanificadorBusquedaIterativa:
    """
    Orquesta el ciclo iterativo de detección de brechas → búsqueda → integración.
    
    Se integra con:
    - MemoriaEpisodica: leer brechas, guardar nuevos hallazgos
    - ExternalToolExecutor: ejecutar sub-consultas
    - DeepSynthesizer + ReasoningEngine: reprocesar con nuevos datos
    """
    
    def __init__(
        self,
        memoria: MemoriaEpisodica,
        executor: Optional[ExternalToolExecutor] = None,
        max_iteraciones: int = 3,
        max_subqueries_por_brecha: int = 2,
        umbral_confianza_nueva: float = 0.5
    ):
        self.memoria = memoria
        self.executor = executor or crear_executor()
        self.max_iteraciones = max_iteraciones
        self.generador = GeneradorSubqueries(max_subqueries_por_brecha)
        self.umbral_confianza = umbral_confianza_nueva
        
        # Stats
        self.stats = {
            "iteraciones_totales": 0,
            "brechas_procesadas": 0,
            "subqueries_ejecutadas": 0,
            "hallazgos_nuevos": 0,
            "brechas_resueltas": 0
        }

    def ejecutar_ciclo_iterativo(
        self,
        sesion_id: str,
        hallazgos_iniciales: List[Any],
        corpus_inicial: str,
        reasoning_engine,
        deep_synthesizer
    ) -> Dict[str, Any]:
        """
        Ejecuta el ciclo iterativo completo.
        
        Args:
            sesion_id: Sesión de memoria episódica
            hallazgos_iniciales: Hallazgos del DeepSynthesizer inicial
            corpus_inicial: Corpus de evidencia inicial
            reasoning_engine: Instancia de MotorRazonamientoSuperior
            deep_synthesizer: Instancia de DeepSynthesizer
            
        Returns:
            Dict con resultado final + métricas del ciclo iterativo
        """
        logger.info(f"PlanificadorIterativo: Iniciando ciclo para sesión {sesion_id}")
        
        # Estado acumulado
        todos_hallazgos = list(hallazgos_iniciales)
        corpus_acumulado = corpus_inicial
        brechas_historial: List[BrechaConocimiento] = []
        hipotesis_procesadas: Set[str] = set()  # Track para evitar duplicados
        
        for iteracion in range(1, self.max_iteraciones + 1):
            self.stats["iteraciones_totales"] = iteracion
            logger.info(f"PlanificadorIterativo: Iteración {iteracion}/{self.max_iteraciones}")
            
            # 1. Ejecutar razonamiento con hallazgos actuales (pasar hipótesis existentes para deduplicación)
            hipotesis_existentes = list(reasoning_engine._hipotesis.values())
            resultado = reasoning_engine.ejecutar_pipeline_completo(
                hallazgos=todos_hallazgos,
                corpus=corpus_acumulado,
                hipotesis_existentes=hipotesis_existentes
            )
            
            # 2. Detectar brechas desde memoria (ya persistidas por ReasoningConMemoria)
            brechas_dict = self.memoria.get_brechas_abiertas(sesion_id)
            if not brechas_dict:
                logger.info("PlanificadorIterativo: No hay brechas abiertas. Ciclo completado.")
                break
            
            # Convertir a objetos BrechaConocimiento - buscar claim en hipótesis
            brechas_actuales = []
            for b in brechas_dict:
                hipotesis_id = b.get("hipotesis_id", "")
                
                # Saltar si ya procesamos esta hipótesis
                if hipotesis_id in hipotesis_procesadas:
                    continue
                
                # Buscar claim en episodio de hipótesis
                claim = ""
                if hipotesis_id:
                    hyp_ep = self.memoria.obtener_episodio(hipotesis_id)
                    if hyp_ep and hyp_ep.tipo == TipoEpisodio.HIPOTESIS:
                        claim = hyp_ep.contenido.get("claim", "")
                
                bc = BrechaConocimiento(
                    hipotesis_id=hipotesis_id,
                    claim=claim,
                    brecha=b.get("brecha", ""),
                    entidades=b.get("entidades", []),
                    tipo_hipotesis=self._inferir_tipo_hipotesis(claim),
                )
                brechas_actuales.append(bc)
                brechas_historial.append(bc)
                hipotesis_procesadas.add(hipotesis_id)
            
            if not brechas_actuales:
                logger.info("PlanificadorIterativo: Todas las brechas ya procesadas. Ciclo completado.")
                break
            
            logger.info(f"PlanificadorIterativo: {len(brechas_actuales)} brechas nuevas detectadas")
            
            # 3. Generar sub-queries para cada brecha
            todas_subqueries = []
            for brecha in brechas_actuales:
                subqueries = self.generador.generar_para_brecha(brecha)
                brecha.intentos += 1
                todas_subqueries.extend([(sq, brecha) for sq in subqueries])
            
            if not todas_subqueries:
                logger.warning("PlanificadorIterativo: No se generaron sub-queries. Terminando.")
                break
            
            # 4. Ejecutar sub-queries
            hallazgos_nuevos_iteracion = []
            for subquery, brecha_origen in todas_subqueries:
                self.stats["subqueries_ejecutadas"] += 1
                logger.info(f"PlanificadorIterativo: Ejecutando subquery: {subquery[:80]}...")
                
                resultado_subq = self._ejecutar_subquery(subquery, brecha_origen.hipotesis_id)
                
                if resultado_subq.exito and resultado_subq.hallazgos_nuevos:
                    hallazgos_nuevos_iteracion.extend(resultado_subq.hallazgos_nuevos)
                    self.stats["hallazgos_nuevos"] += len(resultado_subq.hallazgos_nuevos)
                    logger.info(f"  -> {len(resultado_subq.hallazgos_nuevos)} hallazgos nuevos")
                else:
                    logger.warning(f"  -> Falló: {resultado_subq.error}")
            
            if not hallazgos_nuevos_iteracion:
                logger.warning("PlanificadorIterativo: Sub-queries no produjeron hallazgos nuevos. Terminando.")
                break
            
            # 5. Convertir hallazgos nuevos a formato HallazgoTecnico y acumular
            from core.deep_synthesizer import HallazgoTecnico
            for h_dict in hallazgos_nuevos_iteracion:
                h = HallazgoTecnico(
                    tipo=h_dict.get("tipo", "especificacion"),
                    descripcion=h_dict.get("descripcion", ""),
                    fuente=h_dict.get("fuente", "busqueda_iterativa"),
                    confianza=h_dict.get("confianza", 0.6),
                    evidencia=h_dict.get("evidencia", "")
                )
                todos_hallazgos.append(h)
            
            # 6. Actualizar corpus con evidencia nueva
            for h_dict in hallazgos_nuevos_iteracion:
                if h_dict.get("evidencia"):
                    corpus_acumulado += f"\n\n---\n[FUENTE: {h_dict.get('fuente', 'iterativa')}]\n{h_dict['evidencia']}"
            
            # 7. Verificar si brechas se resolvieron (heurística: hallazgos nuevos cubren entidades)
            brechas_resueltas = self._evaluar_resolucion_brechas(brechas_actuales, hallazgos_nuevos_iteracion)
            self.stats["brechas_resueltas"] += brechas_resueltas
            
            if brechas_resueltas == len(brechas_actuales):
                logger.info("PlanificadorIterativo: Todas las brechas resueltas. Terminando ciclo.")
                break
            
            self.stats["brechas_procesadas"] += len(brechas_actuales)
        
        # Ejecución final con todos los hallazgos acumulados (incluir hipótesis existentes)
        hipotesis_existentes = list(reasoning_engine._hipotesis.values())
        resultado_final = reasoning_engine.ejecutar_pipeline_completo(
            hallazgos=todos_hallazgos,
            corpus=corpus_acumulado,
            hipotesis_existentes=hipotesis_existentes
        )
        
        return {
            "resultado_final": resultado_final,
            "metricas_iterativo": self.stats,
            "total_hallazgos_acumulados": len(todos_hallazgos),
            "corpus_final_chars": len(corpus_acumulado),
            "brechas_historial": [
                {
                    "hipotesis_id": b.hipotesis_id,
                    "claim": b.claim,
                    "brecha": b.brecha,
                    "resuelta": b.resuelta,
                    "subqueries": b.subqueries_generadas,
                    "intentos": b.intentos
                }
                for b in brechas_historial
            ]
        }

    def _ejecutar_subquery(self, subquery: str, hipotesis_id: str) -> ResultadoSubquery:
        """Ejecuta una sub-query via ExternalToolExecutor."""
        try:
            # El executor espera payload sin @web_search
            payload = subquery.replace("@web_search", "").strip()
            
            resultado = self.executor.ejecutar(
                herramienta="web_search",
                payload=payload,
                contexto={"trigger": "busqueda_iterativa", "peso_operativo": 8, "hipotesis_origen": hipotesis_id}
            )
            
            if not resultado.exito or not resultado.resultados:
                return ResultadoSubquery(
                    subquery=subquery,
                    brecha_origen=hipotesis_id,
                    exito=False,
                    hallazgos_nuevos=[],
                    error=resultado.error or "Sin resultados"
                )
            
            # Convertir resultados a hallazgos
            hallazgos = []
            for item in resultado.resultados:
                if item.contenido_completo and len(item.contenido_completo) > 100:
                    hallazgos.append({
                        "tipo": "especificacion",
                        "descripcion": f"{item.titulo}: {item.snippet[:150]}",
                        "fuente": item.fuente,
                        "confianza": min(0.8, item.relevancia),
                        "evidencia": item.contenido_completo[:2000]
                    })
            
            return ResultadoSubquery(
                subquery=subquery,
                brecha_origen=hipotesis_id,
                exito=True,
                hallazgos_nuevos=hallazgos
            )
            
        except Exception as e:
            logger.error(f"Error ejecutando subquery: {e}")
            return ResultadoSubquery(
                subquery=subquery,
                brecha_origen=hipotesis_id,
                exito=False,
                hallazgos_nuevos=[],
                error=str(e)
            )

    def _inferir_tipo_hipotesis(self, claim: str) -> str:
        """Infiere tipo de hipótesis desde el claim."""
        claim_lower = claim.lower()
        if any(kw in claim_lower for kw in ["causa", "habilita", "permite", "provoca"]):
            return "causal"
        elif any(kw in claim_lower for kw in ["implica", "soporta", "incluye"]):
            return "implicacion"
        elif any(kw in claim_lower for kw in ["requiere", "necesita", "depende"]):
            return "restriccion"
        return "indeterminada"

    def _evaluar_resolucion_brechas(
        self, 
        brechas: List[BrechaConocimiento], 
        hallazgos_nuevos: List[Dict]
    ) -> int:
        """Evalúa cuántas brechas quedaron resueltas por hallazgos nuevos."""
        if not hallazgos_nuevos:
            return 0
        
        # Construir texto combinado de hallazgos nuevos
        texto_hallazgos = " ".join(
            h.get("descripcion", "") + " " + h.get("evidencia", "") 
            for h in hallazgos_nuevos
        )
        
        # Extraer entidades técnicas del texto
        entidades_nuevas = set(re.findall(r'\b[A-Z]{2,}\b', texto_hallazgos))
        entidades_nuevas.update(texto_hallazgos.split())
        
        resueltas = 0
        for brecha in brechas:
            # Si al menos una entidad de la brecha aparece en hallazgos nuevos
            if any(ent in texto_hallazgos for ent in brecha.entidades):
                brecha.resuelta = True
                resueltas += 1
        
        return resueltas


def crear_planificador_iterativo(
    memoria: MemoriaEpisodica,
    executor: Optional[ExternalToolExecutor] = None,
    max_iteraciones: int = 3
) -> PlanificadorBusquedaIterativa:
    """Factoría para PlanificadorBusquedaIterativa."""
    return PlanificadorBusquedaIterativa(
        memoria=memoria,
        executor=executor,
        max_iteraciones=max_iteraciones
    )