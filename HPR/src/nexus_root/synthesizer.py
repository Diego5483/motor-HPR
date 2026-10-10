"""Módulo de Síntesis en Lenguaje Natural para el Nexus Root.

Transforma los resultados de búsqueda validados y auditados en informes
profesionales en lenguaje natural, adaptados al nivel de confianza.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class NivelConfianza(Enum):
    """Niveles de confianza del sistema de auditoría."""
    CONFIANZA_ALTA = "CONFIANZA_ALTA"
    CONFIANZA_MEDIA = "CONFIANZA_MEDIA"
    CONFIANZA_BAJA = "CONFIANZA_BAJA"
    CONFIANZA_NULA = "CONFIANZA_NULA"
    RECHAZO_CRITICO = "RECHAZO_CRITICO"


@dataclass
class InformeSintesis:
    """Informe de síntesis estructurado para presentación."""
    nivel_confianza: str
    aprobado: bool
    encabezado_confianza: str
    introduccion: str
    hallazgos_clave: List[str]
    analisis_tecnico: str
    conclusiones: str
    advertencias: List[str]
    metadata_fuentes: Dict[str, Any]


class NexusSynthesizer:
    """
    Generador de informes en lenguaje natural a partir de resultados auditados.
    
    Transforma los resultados técnicos del NexusRouter en informes
    profesionales legibles, adaptando el tono y profundidad según
    el nivel de confianza de la auditoría.
    """
    
    # Plantillas de encabezado por nivel de confianza
    ENCABEZADOS_CONFIANZA = {
        "CONFIANZA_ALTA": (
            "✅ **Información auditada con CONFIANZA ALTA** "
            "(Score: {score:.2f}) — Fuente verificada, segura y relevante."
        ),
        "CONFIANZA_MEDIA": (
            "⚠️ **Información auditada con CONFIANZA MODERADA** "
            "(Score: {score:.2f}) — Parcialmente verificable, presentar con cautela."
        ),
        "CONFIANZA_BAJA": (
            "⚠️ **Información auditada con CONFIANZA BAJA** "
            "(Score: {score:.2f}) — Muy poca verificabilidad, usar con precaución extrema."
        ),
        "CONFIANZA_NULA": (
            "🚫 **BLOQUEO DE SEGURIDAD** — Información sin valor confiable verificable. "
            "Contenido descartado por auditoría de seguridad."
        ),
        "RECHAZO_CRITICO": (
            "🛑 **BLOQUEO CRÍTICO DE SEGURIDAD** — Contenido malicioso o altamente sospechoso detectado. "
            "Acceso denegado por política de seguridad del motor HPR."
        ),
    }
    
    # Mensajes de bloqueo por nivel
    MENSAJES_BLOQUEO = {
        "CONFIANZA_NULA": (
            "❌ **La información solicitada no ha superado la auditoría de confianza.**\n\n"
            "El contenido recuperado no cumple los umbrales mínimos de verificabilidad "
            "y ha sido descartado por el sistema de seguridad HPR. "
            "No se genera informe para proteger la integridad del usuario."
        ),
        "RECHAZO_CRITICO": (
            "🛑 **ACCESO DENEGADO POR SEGURIDAD CRÍTICA**\n\n"
            "El contenido solicitado ha sido interceptado por contener patrones maliciosos, "
            "código sospechoso o intentos de inyección. "
            "El motor HPR ha bloqueado la respuesta para proteger la integridad del sistema."
        ),
    }
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def sintetizar(
        self, 
        resultado_busqueda: dict, 
        evaluacion_global: dict,
        query_original: str
    ) -> InformeSintesis:
        """
        Genera un informe de síntesis completo a partir de resultados auditados.
        
        Args:
            resultado_busqueda: ResultadoBusqueda del executor (con resultados, sintesis, etc.)
            evaluacion_global: Evaluación global del NexusRouter (nivel_confianza, score, etc.)
            query_original: Consulta original del usuario
            
        Returns:
            InformeSintesis estructurado para presentación
        """
        nivel_confianza = evaluacion_global.get("nivel_confianza", "DESCONOCIDO")
        score_final = evaluacion_global.get("score_final", 0.0)
        aprobado = evaluacion_global.get("aprobado", False)
        
        # Si está bloqueado, generar informe de bloqueo
        if not aprobado:
            return self._generar_informe_bloqueo(nivel_confianza, score_final, query_original)
        
        # Generar informe aprobado
        return self._generar_informe_aprobado(
            nivel_confianza=nivel_confianza,
            score_final=evaluacion_global.get("score_final", 0.0),
            score_seguridad=evaluacion_global.get("score_seguridad", 0.0),
            score_calidad=evaluacion_global.get("score_calidad", 0.0),
            query_original=query_original,
            resultados=query_original,  # Se usará para extraer info de resultados
            evaluacion_global=evaluacion_global,
        )
    
    def _generar_informe_bloqueo(
        self, 
        nivel_confianza: str, 
        score: float, 
        query: str
    ) -> InformeSintesis:
        """Genera informe de bloqueo para niveles no aprobados."""
        mensaje = self.MENSAJES_BLOQUEO.get(
            nivel_confianza, 
            f"Contenido bloqueado por nivel de confianza: {nivel_confianza}"
        )
        
        return InformeSintesis(
            nivel_confianza=nivel_confianza,
            aprobado=False,
            encabezado_confianza=self._formatear_encabezado(nivel_confianza, 0.0),
            introduccion=mensaje,
            hallazgos_clave=[],
            analisis_tecnico="",
            conclusiones="",
            advertencias=["Contenido bloqueado por auditoría de seguridad"],
            metadata_fuentes={}
        )
    
    def _generar_informe_aprobado(
        self,
        nivel_confianza: str,
        score_final: float,
        score_seguridad: float,
        score_calidad: float,
        query_original: str,
        resultados: str,  # query_original, se usará para contexto
        evaluacion_global: dict,
    ) -> InformeSintesis:
        """Genera informe completo para contenido aprobado."""
        
        # Extraer métricas de la evaluación global
        metricas = evaluacion_global.get("metricas", {})
        score_seguridad = evaluacion_global.get("score_seguridad", 0.0)
        score_calidad = evaluacion_global.get("score_calidad", 0.0)
        clasificacion_seguridad = evaluacion_global.get("clasificacion_seguridad", "DESCONOCIDA")
        
        # 1. Encabezado de confianza
        encabezado = self._formatear_encabezado(nivel_confianza, evaluacion_global.get("score_final", 0.0))
        
        # 2. Introducción contextual
        introduccion = self._generar_introduccion(
            query_original, 
            nivel_confianza, 
            score_final=score_final
        )
        
        # 3. Hallazgos clave (extraídos de métricas y resultados)
        hallazgos = self._extraer_hallazgos_clave(evaluacion_global)
        
        # 4. Análisis técnico detallado
        analisis_tecnico = self._generar_analisis_tecnico(evaluacion_global)
        
        # 5. Conclusiones y recomendaciones
        conclusiones = self._generar_conclusiones(nivel_confianza, score_final)
        
        # 6. Advertencias según nivel
        advertencias = self._generar_advertencias(nivel_confianza, score_final)
        
        # Metadata de fuentes
        metadata_fuentes = {
            "score_final": round(score_final, 2),
            "score_seguridad": round(score_seguridad, 2),
            "score_calidad": round(score_calidad, 2),
            "clasificacion_seguridad": evaluacion_global.get("clasificacion_seguridad", "N/A"),
            "total_resultados": 1,  # Se actualizará si hay más
        }
        
        return InformeSintesis(
            nivel_confianza=nivel_confianza,
            aprobado=True,
            encabezado_confianza=encabezado,
            introduccion=introduccion,
            hallazgos_clave=hallazgos,
            analisis_tecnico=analisis_tecnico,
            conclusiones=conclusiones,
            advertencias=advertencias,
            metadata_fuentes=metadata_fuentes,
        )
    
    def _formatear_encabezado(self, nivel: str, score: float) -> str:
        """Formatea el encabezado según nivel de confianza."""
        template = self.ENCABEZADOS_CONFIANZA.get(nivel, "Nivel de confianza: {nivel} (Score: {score:.2f})")
        return template.format(score=0.0)  # Se formateará con score real
    
    def _generar_introduccion(self, query: str, nivel: str, score_final: float) -> str:
        """Genera introducción contextual."""
        base = f"Análisis de la consulta: **\"{query}\"**\n\n"
        
        if "ALTA" in nivel:
            return base + (
                f"La consulta ha sido procesada exitosamente mediante el motor HPR, "
                f"superando la auditoría de tres niveles de confianza con una puntuación "
                f"final de **{score_final:.2f}/1.00**. "
                f"La información presentada a continuación proviene de fuentes verificadas "
                f"y ha superado los filtros de seguridad, relevancia y calidad del motor HPR."
            )
        elif "MEDIA" in nivel:
            return base + (
                f"La consulta ha sido procesada con **confianza moderada** (Score: {score_final:.2f}). "
                f"La información presentada es parcialmente verificable y se recomienda "
                f"corroborar con fuentes adicionales antes de tomar decisiones críticas."
            )
        else:
            return base + (
                f"La consulta ha sido procesada con **confianza baja** (Score: {score_final:.2f}). "
                f"La información tiene verificabilidad limitada y se recomienda "
                f"usar con extrema precaución y validar independientemente."
            )
    
    def _extraer_hallazgos_clave(self, evaluacion: dict) -> List[str]:
        """Extrae hallazgos clave de la evaluación global."""
        hallazgos = []
        metricas = evaluacion.get("metricas", {})
        
        # Hallazgo 1: Total de resultados
        total = evaluacion.get("metricas", {}).get("total_resultados", 0)
        if total > 0:
            hallazgos.append(f"Se recuperaron **{total} resultado(s) relevante(s)** tras la búsqueda.")
        
        # Hallazgo 2: Contenido enriquecido
        enriquecidos = evaluacion.get("metricas", {}).get("resultados_con_contenido_completo", 0)
        if enriquecidos > 0:
            hallazgos.append(
                f"**{enriquecidos} resultado(s) fueron enriquecidos** con contenido completo "
                f"extraído de las fuentes originales."
            )
        
        # Hallazgo 3: Diversidad de fuentes
        fuentes = evaluacion.get("metricas", {}).get("fuentes_unicas", 0)
        if fuentes >= 2:
            hallazgos.append(f"Se identificaron **{fuentes} fuentes únicas** independientes.")
        elif fuentes == 1:
            hallazgos.append(f"La información proviene de **una única fuente** ({list(evaluacion.get('score_seguridad', {}).get('metricas', {}).keys())[0] if evaluacion.get('score_seguridad', {}).get('metricas') else 'desconocida'}).")
        
        # Hallazgo 4: Relevancia
        relevancia = evaluacion.get("metricas", {}).get("relevancia_promedio", 0)
        if relevancia >= 0.5:
            hallazgos.append(f"La relevancia promedio de los resultados es **alta ({relevancia:.0%})**.")
        elif relevancia >= 0.3:
            hallazgos.append(f"La relevancia promedio es **moderada ({relevancia:.0%})**.")
        
        # Hallazgo 5: Seguridad
        score_seg = evaluacion.get("score_seguridad", {}).get("score_seguridad", 0)
        clasificacion = evaluacion.get("score_seguridad", {}).get("clasificacion", "DESCONOCIDA")
        if "ALTA" in str(clasificacion):
            hallazgos.append("**Seguridad: ALTA** — Fuentes verificadas en whitelist, sin amenazas detectadas.")
        elif "MEDIA" in str(clasificacion):
            hallazgos.append("**Seguridad: MEDIA** — Fuentes parcialmente verificadas, sin amenazas críticas.")
        elif "BAJA" in str(clasificacion) or "NULA" in str(clasificacion):
            hallazgos.append("**Seguridad: BAJA/NULA** — Fuentes no verificadas completamente.")
        
        return hallazgos if hallazgos else ["No se generaron hallazgos específicos."]
    
    def _generar_analisis_tecnico(self, evaluacion: dict) -> str:
        """Genera análisis técnico detallado."""
        metricas = evaluacion.get("metricas", {})
        score_seg = evaluacion.get("score_seguridad", {})
        
        partes = [
            "## Análisis Técnico de la Auditoría",
            "",
            "### 1. Validación de Seguridad",
            f"- **Clasificación de seguridad:** {evaluacion.get('clasificacion_seguridad', 'N/A')}",
            f"- **Score de seguridad:** {evaluacion.get('score_seguridad', 0):.2f}/1.00",
            f"- **Amenazas detectadas:** {evaluacion.get('score_seguridad', {}).get('amenazas_detectadas', 0)} "
            f"(críticas: {evaluacion.get('score_seguridad', {}).get('amenazas_criticas', 0)})",
            f"- **Dominios verificados:** {evaluacion.get('score_seguridad', {}).get('dominios_verificados', 0)} "
            f"de {evaluacion.get('metricas', {}).get('total_resultados', 0)} resultados",
            "",
            "### 2. Calidad de Contenido",
            f"- **Resultados con contenido completo:** "
            f"{evaluacion.get('metricas', {}).get('resultados_con_contenido_completo', 0)} "
            f"de {evaluacion.get('metricas', {}).get('total_resultados', 0)}",
            f"- **Fuentes únicas:** {evaluacion.get('metricas', {}).get('fuentes_unicas', 0)}",
            f"- **Relevancia promedio:** {evaluacion.get('metricas', {}).get('relevancia_promedio', 0):.0%}",
            "",
            "### 3. Evaluación de Calidad",
            f"- **Score de calidad:** {evaluacion.get('score_calidad', 0):.2f}/1.00",
            f"- **Score de seguridad:** {evaluacion.get('score_seguridad', 0):.2f}",
            f"- **Score final combinado:** {evaluacion.get('score_final', 0):.2f}",
            "",
            "### 4. Decisión de Auditoría",
            f"- **Nivel de confianza:** {evaluacion.get('nivel_confianza', 'N/A')}",
            f"- **Decisión:** {'APROBADO' if evaluacion.get('aprobado') else 'BLOQUEADO'}",
            f"- **Acción recomendada:** {evaluacion.get('accion_recomendada', 'N/A')}",
        ]
        
        return "\n".join(partes)
    
    def _generar_conclusiones(self, nivel: str, score: float) -> str:
        """Genera conclusiones y recomendaciones."""
        if "ALTA" in nivel:
            return (
                "## Conclusiones y Recomendaciones\n\n"
                "✅ **La información es confiable y lista para uso.**\n\n"
                "La consulta ha sido procesada con el máximo nivel de confianza. "
                "Los resultados provienen de fuentes verificadas en whitelist, "
                "han superado la detección de amenazas y ofrecen contenido relevante "
                "y completo. Se recomienda su uso directo para toma de decisiones."
            )
        elif "MEDIA" in nivel:
            return (
                "## Conclusiones y Recomendaciones\n\n"
                "⚠️ **La información es parcialmente confiable — usar con cautela.**\n\n"
                "Los resultados ofrecen valor informativo pero presentan limitaciones "
                "en verificabilidad o completitud. Se recomienda:\n"
                "1. Corroborar datos críticos con fuentes primarias\n"
                "2. Usar como referencia orientativa, no como única fuente\n"
                "3. Validar información sensible independientemente"
            )
        else:
            return (
                "## Conclusiones y Recomendaciones\n\n"
                "⚠️ **Información de baja verificabilidad — usar con extrema precaución.**\n\n"
                "Los resultados tienen limitaciones significativas. Se recomienda:\n"
                "1. **No usar para decisiones críticas** sin validación independiente\n"
                "2. Buscar fuentes primarias adicionales\n"
                "3. Considerar la información como orientativa únicamente"
            )
    
    def _generar_advertencias(self, nivel: str, score: float) -> List[str]:
        """Genera advertencias según nivel de confianza."""
        advertencias = []
        
        if "CRITICO" in nivel or "NULA" in nivel:
            advertencias.append("🛑 **CONTENIDO BLOQUEADO** — No usar bajo ninguna circunstancia.")
        elif "BAJA" in nivel:
            advertencias.append("⚠️ **VERIFICACIÓN REQUERIDA** — Validar independientemente antes de usar.")
        elif "MEDIA" in nivel:
            advertencias.append("⚠️ **PRECAUCIÓN** — Corroborar datos críticos con fuentes primarias.")
        
        # Advertencias genéricas
        advertencias.append(
            "ℹ️ La información refleja el estado de las fuentes al momento de la búsqueda."
        )
        advertencias.append(
            "ℹ️ El motor HPR no garantiza la actualidad absoluta de información externa."
        )
        
        return advertencias


# ============================================================
# FUNCIÓN DE CONVENIENCIA
# ============================================================

def crear_synthesizer() -> NexusSynthesizer:
    """Factoría para crear una instancia de NexusSynthesizer."""
    return NexusSynthesizer()