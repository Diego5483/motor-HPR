"""Motor de Inferencia Profunda - Deep Synthesizer.

Procesa contenido real de resultados de búsqueda (snippets + contenido_completo)
para extraer entidades, hechos técnicos y generar informes con sustancia.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import re
import logging

logger = logging.getLogger(__name__)


@dataclass
class HallazgoTecnico:
    """Hallazgo técnico extraído del contenido."""
    tipo: str  # "especificacion", "version", "caracteristica", "metrica", "comparativa"
    descripcion: str
    fuente: str
    confianza: float  # 0.0 - 1.0
    evidencia: str  # fragmento original


@dataclass
class InformeProfundo:
    """Informe generado por análisis profundo de contenido."""
    query: str
    introduccion: str
    hallazgos_tecnicos: List[HallazgoTecnico]
    analisis_detallado: str
    conclusiones: List[str]
    advertencias: List[str]
    metricas_procesamiento: Dict[str, Any]


class DeepSynthesizer:
    """
    Sintetizador de inferencia profunda.
    
    No usa plantillas: extrae información real del contenido,
    cruza fuentes y genera análisis basado en evidencia.
    """

    # Patrones para extracción de información técnica
    PATRONES_VERSION = re.compile(r'\b(v?\d+\.\d+(\.\d+)?(-[a-z]+)?)\b', re.IGNORECASE)
    PATRONES_FECHA = re.compile(r'\b(20\d{2}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]20\d{2})\b')
    PATRONES_ARQUITECTURA = re.compile(r'\b(ARMv9|ARMv8|x86_64|x64|RISC-V|MIPS|aarch64|AArch64)\b', re.IGNORECASE)
    PATRONES_TECNOLOGIA = re.compile(r'\b(MTE|CCA|SVE2|SVET|PAC|BTI|GCS|RME|EL3|EL2|EL1|EL0|MMU|TLB|L1|L2|L3)\b', re.IGNORECASE)
    PATRONES_METRICA = re.compile(r'\b(\d+(?:\.\d+)?)\s*(GHz|MHz|GB|MB|KB|TB|W|nm|ns|ms|%)\b', re.IGNORECASE)
    PATRONES_ENTIDAD = re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b')

    def __init__(self, min_confianza: float = 0.3):
        self.min_confianza = min_confianza
        self._cache_entidades: Dict[str, List[str]] = {}

    def procesar_resultados(
        self,
        query: str,
        resultados: List[Dict[str, Any]],
        evaluacion_global: Optional[Dict[str, Any]] = None
    ) -> InformeProfundo:
        """
        Procesa resultados de búsqueda y genera informe profundo.
        
        Args:
            query: Consulta original
            resultados: Lista de dicts con keys: titulo, url, snippet, fuente, contenido_completo, relevancia
            evaluacion_global: Evaluación de auditoría (opcional)
            
        Returns:
            InformeProfundo con hallazgos extraídos del contenido real
        """
        # 1. Consolidar todo el contenido disponible
        corpus = self._construir_corpus(resultados)
        
        # 2. Extraer hallazgos técnicos del corpus
        hallazgos = self._extraer_hallazgos(corpus, resultados)
        
        # 3. Filtrar por confianza mínima
        hallazgos_filtrados = [h for h in hallazgos if h.confianza >= self.min_confianza]
        
        # 4. Generar secciones del informe
        introduccion = self._generar_introduccion(query, hallazgos_filtrados, len(resultados))
        analisis = self._generar_analisis(query, hallazgos_filtrados, corpus)
        conclusiones = self._generar_conclusiones(query, hallazgos_filtrados)
        advertencias = self._generar_advertencias(hallazgos_filtrados, evaluacion_global)
        
        return InformeProfundo(
            query=query,
            introduccion=introduccion,
            hallazgos_tecnicos=hallazgos_filtrados,
            analisis_detallado=analisis,
            conclusiones=conclusiones,
            advertencias=advertencias,
            metricas_procesamiento={
                "total_resultados": len(resultados),
                "total_caracteres_procesados": len(corpus),
                "hallazgos_extraidos": len(hallazgos),
                "hallazgos_filtrados": len(hallazgos_filtrados),
                "fuentes_unicas": len(set(r.get("fuente", "") for r in resultados)),
            }
        )

    def _construir_corpus(self, resultados: List[Dict[str, Any]]) -> str:
        """Construye corpus unificado priorizando contenido_completo."""
        partes = []
        for r in resultados:
            if r.get("contenido_completo"):
                partes.append(f"[FUENTE: {r.get('fuente', 'desconocida')}]\n{r['contenido_completo']}")
            elif r.get("snippet"):
                partes.append(f"[FUENTE: {r.get('fuente', 'desconocida')}]\n{r['snippet']}")
        return "\n\n---\n\n".join(partes)

    def _extraer_hallazgos(
        self, 
        corpus: str, 
        resultados: List[Dict[str, Any]]
    ) -> List[HallazgoTecnico]:
        """Extrae hallazgos técnicos del corpus usando múltiples estrategias."""
        hallazgos = []
        
        # Por cada resultado individual (para atribución precisa)
        for r in resultados:
            texto = r.get("contenido_completo") or r.get("snippet", "")
            if not texto or len(texto) < 50:
                continue
            
            fuente = r.get("fuente", "desconocida")
            
            # Extraer versiones
            hallazgos.extend(self._extraer_versiones(texto, fuente))
            
            # Extraer arquitecturas
            hallazgos.extend(self._extraer_arquitecturas(texto, fuente))
            
            # Extraer tecnologías/características
            hallazgos.extend(self._extraer_tecnologias(texto, fuente))
            
            # Extraer métricas cuantitativas
            hallazgos.extend(self._extraer_metricas(texto, fuente))
            
            # Extraer especificaciones técnicas (patrón "X soporta Y", "X incluye Z")
            hallazgos.extend(self._extraer_especificaciones(texto, fuente))
        
        # Deduplicar hallazgos similares
        return self._deduplicar_hallazgos(hallazgos)

    def _extraer_versiones(self, texto: str, fuente: str) -> List[HallazgoTecnico]:
        hallazgos = []
        for match in self.PATRONES_VERSION.finditer(texto):
            version = match.group(1)
            contexto = self._extraer_contexto(texto, match.start(), match.end(), 100)
            hallazgos.append(HallazgoTecnico(
                tipo="version",
                descripcion=f"Versión detectada: {version}",
                fuente=fuente,
                confianza=0.7,
                evidencia=contexto
            ))
        return hallazgos

    def _extraer_arquitecturas(self, texto: str, fuente: str) -> List[HallazgoTecnico]:
        hallazgos = []
        for match in self.PATRONES_ARQUITECTURA.finditer(texto):
            arch = match.group(1)
            contexto = self._extraer_contexto(texto, match.start(), match.end(), 150)
            hallazgos.append(HallazgoTecnico(
                tipo="arquitectura",
                descripcion=f"Arquitectura mencionada: {arch}",
                fuente=fuente,
                confianza=0.8,
                evidencia=contexto
            ))
        return hallazgos

    def _extraer_tecnologias(self, texto: str, fuente: str) -> List[HallazgoTecnico]:
        hallazgos = []
        for match in self.PATRONES_TECNOLOGIA.finditer(texto):
            tech = match.group(1)
            contexto = self._extraer_contexto(texto, match.start(), match.end(), 150)
            hallazgos.append(HallazgoTecnico(
                tipo="caracteristica",
                descripcion=f"Tecnología/Característica: {tech}",
                fuente=fuente,
                confianza=0.75,
                evidencia=contexto
            ))
        return hallazgos

    def _extraer_metricas(self, texto: str, fuente: str) -> List[HallazgoTecnico]:
        hallazgos = []
        for match in self.PATRONES_METRICA.finditer(texto):
            valor = match.group(1)
            unidad = match.group(2)
            contexto = self._extraer_contexto(texto, match.start(), match.end(), 120)
            hallazgos.append(HallazgoTecnico(
                tipo="metrica",
                descripcion=f"Métrica: {valor} {unidad}",
                fuente=fuente,
                confianza=0.6,
                evidencia=contexto
            ))
        return hallazgos

    def _extraer_especificaciones(self, texto: str, fuente: str) -> List[HallazgoTecnico]:
        """Extrae oraciones con patrones técnicos: 'soporta', 'incluye', 'implementa', 'permite'."""
        hallazgos = []
        patrones = [
            r'\b(soporta|admite|implementa|incluye|proporciona|ofrece|permite|habilita|utiliza|usa)\b',
            r'\b(capaz de|diseñado para|optimizado para|basado en)\b',
        ]
        
        oraciones = re.split(r'[.!?]+', texto)
        for oracion in oraciones:
            oracion = oracion.strip()
            if len(oracion) < 30 or len(oracion) > 500:
                continue
            
            for patron in patrones:
                if re.search(patron, oracion, re.IGNORECASE):
                    # Verificar que tenga contenido técnico
                    if any(kw in oracion.lower() for kw in [
                        'arquitectura', 'memoria', 'procesador', 'cpu', 'gpu', 'núcleo',
                        'seguridad', 'aislamiento', 'vector', 'simd', 'cache', 'frecuencia',
                        'consumo', 'rendimiento', 'latencia', 'ancho de banda'
                    ]):
                        hallazgos.append(HallazgoTecnico(
                            tipo="especificacion",
                            descripcion=oracion[:200],
                            fuente=fuente,
                            confianza=0.65,
                            evidencia=oracion[:300]
                        ))
                        break
        return hallazgos

    def _extraer_contexto(self, texto: str, inicio: int, fin: int, ventana: int) -> str:
        """Extrae contexto alrededor de una coincidencia."""
        start = max(0, inicio - ventana)
        end = min(len(texto), fin + ventana)
        return texto[start:end].strip()

    def _deduplicar_hallazgos(self, hallazgos: List[HallazgoTecnico]) -> List[HallazgoTecnico]:
        """Elimina hallazgos duplicados por descripción similar."""
        vistos = set()
        unicos = []
        for h in hallazgos:
            key = (h.tipo, h.descripcion[:80].lower())
            if key not in vistos:
                vistos.add(key)
                unicos.append(h)
        return unicos

    def _generar_introduccion(self, query: str, hallazgos: List[HallazgoTecnico], n_resultados: int) -> str:
        if not hallazgos:
            return f"Análisis de: \"{query}\". Se procesaron {n_resultados} fuentes pero no se extrajeron hallazgos técnicos con confianza suficiente."
        
        tipos = set(h.tipo for h in hallazgos)
        fuentes = set(h.fuente for h in hallazgos)
        return (
            f"Análisis técnico profundo de: \"{query}\". "
            f"Se procesaron {n_resultados} fuentes ({len(fuentes)} únicas) "
            f"extrayendo {len(hallazgos)} hallazgos técnicos en {len(tipos)} categorías: "
            f"{', '.join(sorted(tipos))}."
        )

    def _generar_analisis(self, query: str, hallazgos: List[HallazgoTecnico], corpus: str) -> str:
        if not hallazgos:
            return "No se pudo generar análisis técnico: contenido insuficiente o sin patrones reconocibles."
        
        # Agrupar por tipo
        por_tipo: Dict[str, List[HallazgoTecnico]] = {}
        for h in hallazgos:
            por_tipo.setdefault(h.tipo, []).append(h)
        
        partes = ["## Análisis Técnico Basado en Evidencia", ""]
        
        orden_tipos = ["arquitectura", "version", "caracteristica", "especificacion", "metrica"]
        for tipo in orden_tipos:
            if tipo not in por_tipo:
                continue
            items = por_tipo[tipo]
            partes.append(f"### {tipo.capitalize()}s ({len(items)})")
            for h in items[:5]:  # Top 5 por tipo
                partes.append(f"- **{h.fuente}** (conf: {h.confianza:.0%}): {h.descripcion}")
                if h.evidencia:
                    partes.append(f"  > \"{h.evidencia[:200]}...\"")
            partes.append("")
        
        # Síntesis cruzada: buscar consenso entre fuentes
        partes.append("### Consenso entre Fuentes")
        consensus = self._buscar_consenso(hallazgos)
        if consensus:
            for c in consensus:
                partes.append(f"- {c}")
        else:
            partes.append("- No se detectó consenso claro entre fuentes.")
        
        return "\n".join(partes)

    def _buscar_consenso(self, hallazgos: List[HallazgoTecnico]) -> List[str]:
        """Busca afirmaciones que aparecen en múltiples fuentes."""
        textos = {}
        for h in hallazgos:
            # Normalizar descripción para comparación
            key = re.sub(r'\s+', ' ', h.descripcion.lower())[:100]
            textos.setdefault(key, []).append(h.fuente)
        
        consenso = []
        for desc, fuentes in textos.items():
            if len(fuentes) >= 2:
                consenso.append(f"Confirmado en {len(fuentes)} fuentes: {desc[:150]}")
        return consenso[:5]

    def _generar_conclusiones(self, query: str, hallazgos: List[HallazgoTecnico]) -> List[str]:
        if not hallazgos:
            return ["No hay datos técnicos suficientes para extraer conclusiones."]
        
        conclusiones = []
        
        # Conclusión por arquitectura detectada
        archs = [h for h in hallazgos if h.tipo == "arquitectura"]
        if archs:
            unicas = set(h.descripcion for h in archs)
            conclusiones.append(f"Arquitecturas identificadas: {', '.join(unicas)}")
        
        # Conclusión por tecnologías clave
        techs = [h for h in hallazgos if h.tipo == "caracteristica"]
        if techs:
            unicas = set(h.descripcion.split(": ")[-1] for h in techs if ": " in h.descripcion)
            if unicas:
                conclusiones.append(f"Tecnologías clave mencionadas: {', '.join(sorted(unicas)[:5])}")
        
        # Conclusión por versiones
        vers = [h for h in hallazgos if h.tipo == "version"]
        if vers:
            conclusiones.append(f"Versiones de software/hardware detectadas: {len(vers)} referencias")
        
        # Calidad de fuentes
        fuentes_unicas = set(h.fuente for h in hallazgos)
        if len(fuentes_unicas) >= 3:
            conclusiones.append(f"Alta diversidad de fuentes ({len(fuentes_unicas)}): mayor confiabilidad")
        elif len(fuentes_unicas) == 1:
            conclusiones.append("Advertencia: una sola fuente única; validar independientemente")
        
        return conclusiones

    def _generar_advertencias(self, hallazgos: List[HallazgoTecnico], evaluacion: Optional[Dict]) -> List[str]:
        adv = []
        
        if not hallazgos:
            adv.append("⚠️ No se extrajo información técnica verificable del contenido disponible.")
        
        fuentes = set(h.fuente for h in hallazgos)
        if len(fuentes) == 1:
            adv.append("⚠️ Una sola fuente única: riesgo de sesgo o información incompleta.")
        
        avg_conf = sum(h.confianza for h in hallazgos) / len(hallazgos) if hallazgos else 0
        if avg_conf < 0.5:
            adv.append(f"⚠️ Confianza promedio baja ({avg_conf:.0%}): hallazgos basados en menciones indirectas.")
        
        if evaluacion and evaluacion.get("nivel_confianza") in ["CONFIANZA_BAJA", "CONFIANZA_NULA"]:
            adv.append(f"⚠️ Auditoría HPR: {evaluacion['nivel_confianza']} — usar con precaución.")
        
        return adv


def crear_deep_synthesizer(min_confianza: float = 0.3) -> DeepSynthesizer:
    """Factoría para DeepSynthesizer."""
    return DeepSynthesizer(min_confianza=min_confianza)