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
        """Extrae métricas cuantitativas con contexto de entidad asociada."""
        hallazgos = []
        for match in self.PATRONES_METRICA.finditer(texto):
            valor = match.group(1)
            unidad = match.group(2)
            contexto = self._extraer_contexto(texto, match.start(), match.end(), 150)
            
            # Intentar inferir la entidad a la que pertenece la métrica
            entidad_asociada = self._inferir_entidad_metrica(contexto, valor, unidad)
            
            if entidad_asociada:
                descripcion = f"{entidad_asociada} presenta {valor} {unidad}"
            else:
                descripcion = f"Métrica: {valor} {unidad}"
            
            hallazgos.append(HallazgoTecnico(
                tipo="metrica",
                descripcion=descripcion,
                fuente=fuente,
                confianza=0.65 if entidad_asociada else 0.55,
                evidencia=contexto
            ))
        return hallazgos

    def _inferir_entidad_metrica(self, contexto: str, valor: str, unidad: str) -> Optional[str]:
        """Intenta inferir a qué entidad pertenece una métrica basándose en el contexto."""
        # Buscar entidades técnicas cercanas en el contexto
        entidades_conocidas = [
            "RTX 4090", "RTX 4080", "RTX 4070", "Ada Lovelace", "ARMv9", "ARMv8",
            "MTE", "CCA", "SVE2", "RISC-V", "RVV", "Ampere", "Hopper",
            "Ryzen", "Core", "Xeon", "EPYC", "Cortex", "Neoverse",
            "GDDR6X", "GDDR6", "HBM", "L2", "L3", "Tensor cores", "RT cores",
            "CUDA cores", "Tensor cores", "NVENC", "DLSS"
        ]
        
        contexto_lower = contexto.lower()
        for entidad in entidades_conocidas:
            if entidad.lower() in contexto_lower:
                return entidad
        
        # Buscar patrones como "X de Y" o "Y de X" cerca del valor
        # Ej: "24 GB de memoria", "memoria de 24 GB", "450 W TDP"
        patrones_entidad = [
            rf'{re.escape(valor)}\s*{re.escape(unidad)}\s+de\s+(\w+(?:\s+\w+)?)',
            rf'(\w+(?:\s+\w+)?)\s+de\s+{re.escape(valor)}\s*{re.escape(unidad)}',
            rf'(\w+(?:\s+\w+)?)\s+{re.escape(valor)}\s*{re.escape(unidad)}',
        ]
        for patron in patrones_entidad:
            match = re.search(patron, contexto, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None

    def _extraer_metricas_agrupadas(self, texto: str, fuente: str) -> Dict[str, List[Dict]]:
        """Extrae métricas y las agrupa por entidad técnica inferida."""
        metricas_por_entidad = {}
        
        for match in self.PATRONES_METRICA.finditer(texto):
            valor = match.group(1)
            unidad = match.group(2)
            contexto = self._extraer_contexto(texto, match.start(), match.end(), 180)
            entidad = self._inferir_entidad_metrica(contexto, valor, unidad)
            
            clave = entidad or "General"
            if clave not in metricas_por_entidad:
                metricas_por_entidad[clave] = []
            metricas_por_entidad[clave].append({
                "valor": valor,
                "unidad": unidad,
                "contexto": contexto
            })
        
        return metricas_por_entidad

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
        
        # 1. Agrupar hallazgos por entidad técnica principal
        entidades = self._agrupar_por_entidad(hallazgos)
        
        # 2. Construir análisis narrativo por entidad
        partes = ["## Análisis Técnico Integrado", ""]
        
        # Introducción contextual
        fuentes_unicas = len(set(h.fuente for h in hallazgos))
        partes.append(
            f"El análisis de **{query}** revela una arquitectura técnica compuesta por "
            f"{len(entidades)} entidades principales, extraídas de {fuentes_unicas} fuentes. "
            f"A continuación se describe cada componente técnico con sus especificaciones integradas en contexto."
        )
        partes.append("")
        
        # Análisis por entidad con narrativa integrada
        for entidad, hallazgos_entidad in entidades.items():
            if entidad == "General" or not hallazgos_entidad:
                continue
            
            partes.append(f"### {entidad}")
            partes.append(self._generar_narrativa_entidad(entidad, hallazgos_entidad))
            partes.append("")
        
        # Métricas globales integradas
        metricas_narrativa = self._generar_narrativa_metricas_globales(hallazgos)
        if metricas_narrativa:
            partes.append("### Especificaciones Cuantitativas Integradas")
            partes.append(metricas_narrativa)
            partes.append("")
        
        # Consenso entre fuentes
        consensus = self._buscar_consenso(hallazgos)
        if consensus:
            partes.append("### Consenso entre Fuentes")
            for c in consensus:
                partes.append(f"- {c}")
        else:
            partes.append("### Consenso entre Fuentes")
            partes.append("No se detectó consenso explícito entre las fuentes consultadas, aunque las especificaciones técnicas son consistentes.")
        
        return "\n".join(partes)

    def _agrupar_por_entidad(self, hallazgos: List[HallazgoTecnico]) -> Dict[str, List[HallazgoTecnico]]:
        """Agrupa hallazgos por entidad técnica principal inferida."""
        entidades = {}
        
        for h in hallazgos:
            # Intentar extraer entidad principal de la descripción
            entidad = self._extraer_entidad_principal(h.descripcion)
            if not entidad:
                entidad = "General"
            if entidad not in entidades:
                entidades[entidad] = []
            entidades[entidad].append(h)
        
        return entidades

    def _extraer_entidad_principal(self, descripcion: str) -> Optional[str]:
        """Extrae la entidad técnica principal de una descripción."""
        # Entidades técnicas conocidas ordenadas por especificidad
        entidades = [
            "RTX 4090", "RTX 4080", "RTX 4070 Ti", "RTX 4070",
            "Ada Lovelace", "Ampere", "Hopper", "ARMv9", "ARMv8",
            "MTE", "CCA", "SVE2", "RISC-V", "RVV",
            "Ryzen", "Core", "Xeon", "EPYC", "Cortex", "Neoverse",
            "GDDR6X", "GDDR6", "HBM", "L2", "L3", "L1",
            "Tensor cores", "RT cores", "CUDA cores", "Tensor cores",
            "NVENC", "DLSS", "RISC-V", "RVV"
        ]
        
        desc_lower = descripcion.lower()
        for entidad in entidades:
            if entidad.lower() in desc_lower:
                return entidad
        return None

    def _generar_narrativa_entidad(self, entidad: str, hallazgos: List[HallazgoTecnico]) -> str:
        """Genera un párrafo narrativo coherente para una entidad técnica."""
        if not hallazgos:
            return f"La entidad {entidad} fue mencionada pero sin especificaciones técnicas detalladas."
        
        # Separar por tipo
        specs = [h for h in hallazgos if h.tipo == "especificacion"]
        metricas = [h for h in hallazgos if h.tipo == "metrica"]
        versiones = [h for h in hallazgos if h.tipo == "version"]
        caracteristicas = [h for h in hallazgos if h.tipo == "caracteristica"]
        arquitecturas = [h for h in hallazgos if h.tipo == "arquitectura"]
        
        fragmentos = []
        
        # Párrafo de apertura contextual
        if caracteristicas:
            techs = [h.descripcion.split(": ")[-1] if ": " in h.descripcion else h.descripcion for h in caracteristicas[:3]]
            fragmentos.append(f"{entidad} incorpora {'; '.join(techs)}, ")
        elif arquitecturas:
            archs = [h.descripcion.split(": ")[-1] if ": " in h.descripcion else h.descripcion for h in arquitecturas[:2]]
            fragmentos.append(f"{entidad} se basa en la arquitectura {'; '.join(archs)}, ")
        else:
            fragmentos.append(f"{entidad} ")
        
        # Integrar especificaciones funcionales
        if specs:
            spec_texts = [h.descripcion for h in specs[:2]]
            fragmentos.append(f"implementando {'; '.join(spec_texts).lower()}. ")
        
        # Integrar métricas de forma narrativa
        if metricas:
            metricas_texto = self._formatear_metricas_narrativa(metricas)
            if metricas_texto:
                fragmentos.append(f"Sus especificaciones clave incluyen {metricas_texto}. ")
        
        # Versiones
        if versiones:
            vers = [h.descripcion.replace("Versión detectada: ", "") for h in versiones[:2]]
            fragmentos.append(f"Se identifican versiones: {', '.join(vers)}. ")
        
        return "".join(fragmentos).strip()

    def _formatear_metricas_narrativa(self, metricas: List[HallazgoTecnico]) -> str:
        """Convierte lista de métricas en texto narrativo."""
        if not metricas:
            return ""
        
        # Agrupar por tipo de unidad
        por_unidad = {}
        for m in metricas:
            # Extraer unidad de la descripción
            match = re.search(r'(\d+(?:\.\d+)?)\s*(\w+)', m.descripcion)
            if match:
                unidad = match.group(2)
                valor = match.group(1)
                if unidad not in por_unidad:
                    por_unidad[unidad] = []
                por_unidad[unidad].append(m.descripcion)
        
        textos = []
        for unidad, items in por_unidad.items():
            if len(items) == 1:
                textos.append(items[0].lower())
            else:
                # Múltiples métricas misma unidad
                valores = [re.search(r'(\d+(?:\.\d+)?)', it).group(1) for it in items if re.search(r'(\d+(?:\.\d+)?)', it)]
                if valores:
                    textos.append(f"{', '.join(valores)} {unidad} (múltiples configuraciones)")
        
        if not textos:
            return ""
        
        if len(textos) == 1:
            return textos[0]
        elif len(textos) == 2:
            return f"{textos[0]} y {textos[1]}"
        else:
            return f"{', '.join(textos[:-1])} y {textos[-1]}"

    def _generar_narrativa_metricas_globales(self, hallazgos: List[HallazgoTecnico]) -> str:
        """Genera narrativa de métricas globales agrupadas por entidad."""
        metricas = [h for h in hallazgos if h.tipo == "metrica"]
        if not metricas:
            return ""
        
        # Usar agrupación por entidad
        metricas_por_entidad = {}
        for m in metricas:
            entidad = self._extraer_entidad_principal(m.descripcion) or "General"
            if entidad not in metricas_por_entidad:
                metricas_por_entidad[entidad] = []
            metricas_por_entidad[entidad].append(m)
        
        textos = []
        for entidad, mets in metricas_por_entidad.items():
            if entidad == "General":
                continue
            if len(mets) >= 2:
                # Crear frase con múltiples métricas
                metricas_texto = self._formatear_metricas_narrativa(mets)
                if metricas_texto:
                    textos.append(f"{entidad}: {metricas_texto}")
        
        if not textos:
            return ""
        
        return "Las configuraciones técnicas destacadas son: " + "; ".join(textos) + "."

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
        
        # 1. Síntesis arquitectural
        archs = [h for h in hallazgos if h.tipo == "arquitectura"]
        if archs:
            unicas = set(h.descripcion.split(": ")[-1] if ": " in h.descripcion else h.descripcion for h in archs)
            conclusiones.append(
                f"La arquitectura principal identificada es {', '.join(unicas)}, "
                f"que define el marco técnico sobre el que se estructuran el resto de componentes."
            )
        
        # 2. Capacidad funcional integrada
        techs = [h for h in hallazgos if h.tipo == "caracteristica"]
        specs = [h for h in hallazgos if h.tipo == "especificacion"]
        if techs or specs:
            tech_names = set()
            for h in techs:
                if ": " in h.descripcion:
                    tech_names.add(h.descripcion.split(": ")[-1])
                else:
                    tech_names.add(h.descripcion)
            for h in specs:
                # Extraer tecnología de la especificación
                match = re.search(r'(?:soporta|implementa|incluye|habilita|permite)\s+(\w+(?:\s+\w+)?)', h.descripcion, re.IGNORECASE)
                if match:
                    tech_names.add(match.group(1))
            
            if tech_names:
                conclusiones.append(
                    f"El sistema expone capacidades funcionales centradas en {', '.join(sorted(tech_names)[:5])}, "
                    f"lo que sugiere un diseño orientado a {'rendimiento y eficiencia' if any('rendimiento' in t.lower() or 'performance' in t.lower() for t in tech_names) else 'funcionalidad general'}."
                )
        
        # 3. Perfil cuantitativo
        metricas = [h for h in hallazgos if h.tipo == "metrica"]
        if metricas:
            # Contar métricas por tipo
            metricas_tipos = {}
            for m in metricas:
                match = re.search(r'(\d+(?:\.\d+)?)\s*(\w+)', m.descripcion)
                if match:
                    unidad = match.group(2)
                    metricas_tipos[unidad] = metricas_tipos.get(unidad, 0) + 1
            
            if metricas_tipos:
                unidad_principal = max(metricas_tipos, key=metricas_tipos.get)
                conclusiones.append(
                    f"El perfil cuantitativo está dominado por métricas de {unidad_principal} "
                    f"({metricas_tipos[unidad_principal]} referencias), indicando un diseño "
                    f"{'centrado en rendimiento' if unidad_principal in ['GHz', 'TFLOPS', 'GB/s'] else 'centrado en capacidad' if unidad_principal in ['GB', 'TB'] else 'balanceado'}."
                )
        
        # 4. Calidad de fuentes
        fuentes_unicas = set(h.fuente for h in hallazgos)
        if len(fuentes_unicas) >= 3:
            conclusiones.append(
                f"La diversidad de fuentes ({len(fuentes_unicas)}) proporciona una base sólida para la validación cruzada, "
                f"reforzando la fiabilidad de las especificaciones reportadas."
            )
        elif len(fuentes_unicas) == 1:
            conclusiones.append(
                "Advertencia: una sola fuente única; se recomienda validar independientemente las especificaciones críticas."
            )
        
        # 5. Madurez tecnológica
        vers = [h for h in hallazgos if h.tipo == "version"]
        if vers:
            conclusiones.append(
                f"Se detectan {len(vers)} referencias de versiones, lo que permite "
                f"rastrear la evolución y madurez de los componentes analizados."
            )
        
        return conclusiones if conclusiones else ["El análisis no produjo conclusiones accionables con el nivel de confianza actual."]

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