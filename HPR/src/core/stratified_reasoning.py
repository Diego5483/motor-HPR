"""Módulo de Razonamiento Estratificado - Fase 1: Nivel 1 Búsqueda Cognitiva.

Implementa filtrado y ranking de fuentes por relevancia conceptual,
densidad técnica y diversidad de entidades para reducir ruido
antes de la síntesis profunda.
"""

from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
import re
import logging
from collections import Counter

logger = logging.getLogger(__name__)


# Feature flag para activación gradual
USE_STRATIFIED_REASONING = True
COGNITIVE_SCORE_THRESHOLD = 0.35  # Umbral mínimo para considerar fuente válida
COGNITIVE_WEIGHTS = {
    "lexical_relevance": 0.35,      # Relevancia léxica original
    "technical_density": 0.30,      # Densidad de entidades técnicas / 100 chars
    "entity_diversity": 0.20,       # Número de entidades técnicas únicas
    "content_completeness": 0.15,   # Tiene contenido_completo vs solo snippet
}


@dataclass
class FuenteCognitiva:
    """Fuente enriquecida con score cognitivo y metadatos de calidad."""
    resultado_original: Any  # ResultadoItem del executor
    score_cognitivo: float
    score_lexical: float
    densidad_tecnica: float
    diversidad_entidades: int
    completitud_contenido: float
    entidades_detectadas: List[str]
    pasa_umbral: bool
    metadata: Dict[str, Any] = field(default_factory=dict)


class Nivel1_BusquedaCognitiva:
    """
    Nivel 1: Búsqueda Cognitiva.
    
    Filtra y rankea fuentes por relevancia conceptual, no solo léxica.
    Evalúa densidad técnica, diversidad de entidades y completitud.
    """
    
    # Entidades técnicas conocidas para detección de densidad
    ENTIDADES_TECNICAS = {
        # Arquitecturas
        "ARMv9", "ARMv8", "ARMv7", "x86_64", "x64", "RISC-V", "RVV",
        "aarch64", "AArch64", "MIPS", "PowerPC",
        # Tecnologías ARM
        "MTE", "CCA", "SVE2", "SVE", "PAC", "BTI", "GCS", "RME",
        "EL3", "EL2", "EL1", "EL0", "RME", "RMM", "RAT",
        # NVIDIA
        "RTX 4090", "RTX 4080", "RTX 4070", "Ada Lovelace", "Ampere",
        "Hopper", "Blackwell", "Tensor cores", "RT cores", "CUDA cores",
        "NVENC", "DLSS", "SER", "TMA",
        # Memoria
        "GDDR6X", "GDDR6", "GDDR5X", "GDDR5", "HBM", "HBM2", "HBM3",
        "L1", "L2", "L3", "L1D", "L1I", "L2", "L3",
        # Procesadores
        "Ryzen", "Core", "Xeon", "EPYC", "Threadripper", "Cortex",
        "Neoverse", "Cortex-X", "Cortex-A", "Neoverse V", "Neoverse N",
        # RISC-V
        "RVV", "VLEN", "SEW", "LMUL", "Zvkb", "Zvkc", "Zvkg",
        "Zvknh", "Zvkn", "Zvksed", "Zvksh", "Zvkt",
        # General
        "Tensor cores", "RT cores", "CUDA cores", "NVENC", "DLSS",
        "PCIe", "DDR", "GDDR", "HBM", "SRAM", "Cache", "TLB",
        "SPECint", "SPECfp", "GFLOPS", "TFLOPS", "TOPS",
        "TDP", "GHz", "MHz", "GB", "TB", "GB/s", "TB/s",
    }
    
    PATRON_VERSION = re.compile(r'\b(v?\d+\.\d+(\.\d+)?(-[a-z]+)?)\b', re.IGNORECASE)
    PATRON_METRICA = re.compile(r'\b(\d+(?:\.\d+)?)\s*(GHz|MHz|GB|MB|KB|TB|W|nm|ns|ms|%|GB/s|TB/s|TFLOPS|TFLOP/s|TOPS)\b', re.IGNORECASE)

    def __init__(self, umbral: float = COGNITIVE_SCORE_THRESHOLD, pesos: Optional[Dict[str, float]] = None):
        self.umbral = umbral
        self.pesos = pesos or COGNITIVE_WEIGHTS
        self._compilar_patrones()
    
    def _compilar_patrones(self):
        """Pre-compila regex para entidades técnicas."""
        # Ordenar por longitud descendente para match más específico primero
        entidades_ordenadas = sorted(self.ENTIDADES_TECNICAS, key=len, reverse=True)
        patron = r'\b(' + '|'.join(re.escape(e) for e in entidades_ordenadas) + r')\b'
        self.patron_entidades = re.compile(patron, re.IGNORECASE)

    def rankear_fuentes(self, resultados: List[Dict[str, Any]]) -> List[FuenteCognitiva]:
        """
        Evalúa y rankea fuentes por score cognitivo.
        
        Args:
            resultados: Lista de dicts con keys: titulo, url, snippet, fuente, 
                       contenido_completo, relevancia
            
        Returns:
            Lista de FuenteCognitiva ordenada por score descendente
        """
        if not USE_STRATIFIED_REASONING:
            # Modo compatibilidad: todas pasan con score 1.0
            return [FuenteCognitiva(
                resultado_original=r,
                score_cognitivo=1.0,
                score_lexical=r.get("relevancia", 1.0),
                densidad_tecnica=1.0,
                diversidad_entidades=1,
                completitud_contenido=1.0,
                entidades_detectadas=[],
                pasa_umbral=True
            ) for r in resultados]
        
        fuentes_evaluadas = []
        
        for r in resultados:
            fuente = self._evaluar_fuente(r)
            fuentes_evaluadas.append(fuente)
        
        # Ordenar por score cognitivo descendente
        fuentes_evaluadas.sort(key=lambda f: f.score_cognitivo, reverse=True)
        
        # Log de fuentes filtradas
        filtradas = [f for f in fuentes_evaluadas if not f.pasa_umbral]
        if filtradas:
            logger.info(f"Nivel1: {len(filtradas)}/{len(fuentes_evaluadas)} fuentes filtradas por score cognitivo < {self.umbral}")
            for f in filtradas[:3]:
                logger.debug(f"  Filtrada: {f.resultado_original.get('fuente', 'N/A')} score={f.score_cognitivo:.2f}")
        
        return fuentes_evaluadas
    
    def _evaluar_fuente(self, resultado: Dict[str, Any]) -> FuenteCognitiva:
        """Evalúa una fuente individual y calcula score cognitivo."""
        contenido = resultado.get("contenido_completo") or resultado.get("snippet", "")
        snippet = resultado.get("snippet", "")
        relevancia_lexical = resultado.get("relevancia", 0.5)
        
        # 1. Densidad técnica: entidades técnicas / 100 chars
        densidad = self._calcular_densidad_tecnica(contenido)
        
        # 2. Diversidad de entidades: entidades únicas detectadas
        entidades = self._extraer_entidades(contenido)
        diversidad = len(entidades)
        
        # 3. Completitud: tiene contenido_completo vs solo snippet
        completitud = 1.0 if resultado.get("contenido_completo") else 0.5
        if resultado.get("contenido_completo") and len(resultado["contenido_completo"]) > 500:
            completitud = 1.0
        elif resultado.get("contenido_completo"):
            completitud = 0.75
        else:
            completitud = 0.4  # Solo snippet
        
        # Score cognitivo ponderado
        score = (
            self.pesos["lexical_relevance"] * relevancia_lexical +
            self.pesos["technical_density"] * min(densidad * 2, 1.0) +  # Normalizar ~0.5 dens = 1.0
            self.pesos["entity_diversity"] * min(diversidad / 8.0, 1.0) +  # 8 entidades = 1.0
            self.pesos["content_completeness"] * completitud
        )
        
        return FuenteCognitiva(
            resultado_original=resultado,
            score_cognitivo=round(score, 3),
            score_lexical=relevancia_lexical,
            densidad_tecnica=round(densidad, 3),
            diversidad_entidades=diversidad,
            completitud_contenido=completitud,
            entidades_detectadas=list(entidades)[:10],
            pasa_umbral=score >= self.umbral
        )
    
    def _calcular_densidad_tecnica(self, texto: str) -> float:
        """Calcula densidad de entidades técnicas por 100 caracteres."""
        if not texto or len(texto) < 50:
            return 0.0
        
        matches = self.patron_entidades.findall(texto)
        total_chars = len(texto)
        densidad = (len(matches) / total_chars) * 100 if total_chars > 0 else 0.0
        return min(densidad, 2.0)  # Cap a 2.0 (muy denso)
    
    def _extraer_entidades(self, texto: str) -> Set[str]:
        """Extrae entidades técnicas únicas del texto."""
        if not texto:
            return set()
        matches = self.patron_entidades.findall(texto)
        return set(m.lower() for m in matches)
    
    def obtener_fuentes_validas(self, resultados: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Retorna solo los resultados originales que pasan el umbral cognitivo."""
        fuentes_cognitivas = self.rankear_fuentes(resultados)
        validas = [f.resultado_original for f in fuentes_cognitivas if f.pasa_umbral]
        
        if not validas and resultados:
            # Fallback: si todas filtradas, tomar top 2 por score cognitivo
            logger.warning("Nivel1: Todas las fuentes filtradas, usando top 2 por score cognitivo")
            fuentes_cognitivas.sort(key=lambda f: f.score_cognitivo, reverse=True)
            validas = [f.resultado_original for f in fuentes_cognitivas[:2]]
        
        return validas


# Factoría
def crear_nivel1_busqueda(umbral: float = COGNITIVE_SCORE_THRESHOLD) -> Nivel1_BusquedaCognitiva:
    """Factoría para Nivel1_BusquedaCognitiva."""
    return Nivel1_BusquedaCognitiva(umbral=umbral)