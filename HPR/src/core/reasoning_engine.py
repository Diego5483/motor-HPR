"""Motor de Razonamiento Superior - Hypothesis & Verification Engine (Fase Beta).

Convierte hallazgos del DeepSynthesizer en premisas lógicas,
genera hipótesis verificables y las valida contra evidencia disponible.

Arquitectura:
- Premisa: Hallazgo técnico estructurado (tipo, descripción, fuente, confianza, evidencia)
- Hipótesis: Proposición derivada de premisas (claim, premisas_soporte, prediccion_verificable)
- Verificación: Comprobación de predicción contra corpus/evidencia
- Conclusión Verificada: Hipótesis validada/refutada con grado de certeza
"""

from typing import Dict, Any, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging
import re
from collections import defaultdict

logger = logging.getLogger(__name__)


class TipoHipotesis(Enum):
    """Tipos de hipótesis que puede generar el motor."""
    CAUSAL = "causal"              # A causa B (ej: MTE permite detección de memory safety bugs)
    IMPLICACION = "implicacion"    # A implica B (ej: ARMv9 incluye CCA → aislamiento hardware)
    COMPARATIVA = "comparativa"    # A vs B en dimensión X (ej: SVE2 vs SVE1 rendimiento)
    RESTRICCION = "restriccion"    # A requiere B (ej: CCA requiere EL3/EL2)
    PREDICCION = "prediccion"      # Si A entonces esperar B en contexto C
    CLASIFICATORIA = "clasificatoria"  # X pertenece a categoría Y


class EstadoVerificacion(Enum):
    """Resultado de la verificación de una hipótesis."""
    VERIFICADA = "verificada"           # Evidencia directa soporta la hipótesis
    REFUTADA = "refutada"               # Evidencia contradice la hipótesis
    PARCIAL = "parcial"                 # Evidencia mixta / soporte limitado
    INDETERMINADA = "indeterminada"     # Insuficiente evidencia para decidir
    ESPECULATIVA = "especulativa"       # Plausible pero sin evidencia directa


@dataclass
class PremisaLogica:
    """Premisa derivada de un hallazgo técnico validado."""
    id: str
    tipo: str                          # arquitectura, tecnologia, metrica, especificacion, version
    proposicion: str                   # Enunciado en lenguaje natural formalizado
    fuente: str
    confianza: float                   # 0.0 - 1.0 (del hallazgo original)
    evidencia_textual: str             # Fragmento que la soporta
    entidades: List[str] = field(default_factory=list)  # Entidades clave mencionadas
    metadatos: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Hipotesis:
    """Hipótesis generada a partir de premisas."""
    id: str
    tipo: TipoHipotesis
    claim: str                         # Enunciado principal de la hipótesis
    premisas_ids: List[str]            # IDs de premisas que la soportan
    prediccion_verificable: str        # Qué se espera observar si es verdadera
    condiciones: List[str] = field(default_factory=list)  # Contexto necesario
    confianza_inicial: float = 0.5     # Prior basada en fuerza de premisas
    metadatos: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResultadoVerificacion:
    """Resultado de verificar una hipótesis contra evidencia."""
    hipotesis_id: str
    estado: EstadoVerificacion
    evidencia_soporte: List[str]       # Fragmentos que apoyan
    evidencia_contra: List[str]        # Fragmentos que contradicen
    puntuacion: float                  # 0.0 - 1.0 grado de certeza final
    razonamiento: str                  # Explicación del resultado
    brechas: List[str] = field(default_factory=list)  # Qué falta para verificar


@dataclass
class ConclusionVerificada:
    """Conclusión final: hipótesis verificada con grado de certeza."""
    hipotesis: Hipotesis
    verificacion: ResultadoVerificacion
    fuerza_epistemica: str             # "fuerte", "moderada", "débil", "especulativa"
    implicaciones: List[str] = field(default_factory=list)  # Qué sigue de esto


class MotorRazonamientoSuperior:
    """
    Motor de Hipótesis y Verificación (Fase Beta).
    
    Flujo:
    1. RECEPTAR premisas desde DeepSynthesizer (HallazgoTecnico → PremisaLogica)
    2. GENERAR hipótesis via reglas de inferencia (patterns causales, implícitos, etc.)
    3. VERIFICAR cada hipótesis contra el corpus de evidencia disponible
    4. PRODUCIR conclusiones verificadas con gradiente de certeza
    """

    # Patrones para detectar relaciones causales/implícitas en texto
    PATRONES_CAUSAL = [
        r'\b(permite|habilita|facilita|hace posible|provoca|causa|genera|produce)\b',
        r'\b(dado que|ya que|porque|debido a|como resultado de)\b',
        r'\b(si .+ entonces|en caso de .+ se espera)\b',
    ]
    
    PATRONES_IMPLICACION = [
        r'\b(incluye|incorpora|integra|trae|viene con|soporta)\b',
        r'\b(requiere|necesita|depende de|presupone)\b',
        r'\b(basado en|construido sobre|extiende|hereda de)\b',
    ]
    
    PATRONES_RESTRICCION = [
        r'\b(solo|únicamente|exclusivamente|requiere|condición)\b',
        r'\b(limitado a|restringido a|compatible con)\b',
    ]

    def __init__(self, umbral_verificacion: float = 0.6):
        self.umbral_verificacion = umbral_verificacion
        self._premisas: Dict[str, PremisaLogica] = {}
        self._hipotesis: Dict[str, Hipotesis] = {}
        self._verificaciones: Dict[str, ResultadoVerificacion] = {}
        self._conclusiones: List[ConclusionVerificada] = []
        self._corpus_evidencia: str = ""
        self._contador = 0

    # ============================================================
    # 1. RECEPCIÓN DE PREMISAS (desde DeepSynthesizer)
    # ============================================================
    
    def recibir_hallazgos(self, hallazgos: List[Any], corpus: str) -> List[PremisaLogica]:
        """
        Convierte hallazgos del DeepSynthesizer en premisas lógicas formales.
        
        Args:
            hallazgos: Lista de HallazgoTecnico del DeepSynthesizer
            corpus: Texto completo de evidencia para referencias
            
        Returns:
            Lista de PremisaLogica registradas
        """
        self._corpus_evidencia = corpus
        premisas_nuevas = []
        
        for h in hallazgos:
            self._contador += 1
            pid = f"P{self._contador:04d}"
            
            # Extraer entidades de la descripción
            entidades = self._extraer_entidades(h.descripcion)
            
            premisa = PremisaLogica(
                id=pid,
                tipo=h.tipo,
                proposicion=self._formalizar_proposicion(h),
                fuente=h.fuente,
                confianza=h.confianza,
                evidencia_textual=h.evidencia,
                entidades=entidades,
                metadatos={"hallazgo_original_tipo": h.tipo}
            )
            
            self._premisas[pid] = premisa
            premisas_nuevas.append(premisa)
            
            logger.debug(f"Premisa registrada: {pid} | {premisa.proposicion[:80]}...")
        
        logger.info(f"MotorRazonamiento: {len(premisas_nuevas)} premisas registradas desde {len(hallazgos)} hallazgos")
        return premisas_nuevas

    def _extraer_entidades(self, texto: str) -> List[str]:
        """Extrae entidades técnicas clave (mayúsculas, siglas, versiones, nombres específicos)."""
        entidades = set()
        
        # 1. Siglas técnicas (2+ mayúsculas): MTE, CCA, SVE2, ARM, etc.
        entidades.update(re.findall(r'\b[A-Z]{2,}\b', texto))
        
        # 2. Versiones: 3.12, 1.0, v2.5, etc.
        entidades.update(re.findall(r'\bv?\d+\.\d+(\.\d+)?\b', texto))
        
        # 3. Nombres propios técnicos (CamelCase o con números): ARMv9, RISC-V, Python, etc.
        entidades.update(re.findall(r'\b[A-Z][a-z]+(?:[A-Z][a-z]+)*\d*\b', texto))
        entidades.update(re.findall(r'\b[A-Z]+-[A-Z0-9]+\b', texto))  # RISC-V
        
        # 4. NOMBRE ESPECÍFICO tras dos puntos: "Arquitectura: ARMv9" -> capturar ARMv9
        for match in re.finditer(r':\s*([A-Z][\w\-\.]+)', texto):
            entidades.add(match.group(1))
        
        # 5. Nombres compuestos con versión: ARMv9, Python3.12, etc.
        entidades.update(re.findall(r'\b[A-Z][a-z]*\d+(?:\.\d+)*\b', texto))
        
        return list(entidades)

    def _formalizar_proposicion(self, hallazgo) -> str:
        """Convierte hallazgo informal en proposición lógica."""
        tipo = hallazgo.tipo
        desc = hallazgo.descripcion
        
        if tipo == "arquitectura":
            return f"EXISTE(arquitectura:{desc.split(':')[-1].strip()})"
        elif tipo == "tecnologia" or tipo == "caracteristica":
            tech = desc.split(':')[-1].strip() if ':' in desc else desc
            return f"SOPORTA(sistema, tecnologia:{tech})"
        elif tipo == "metrica":
            return f"MIDE(metrica:{desc})"
        elif tipo == "especificacion":
            return f"ESPECIFICA(sistema, {desc[:100]})"
        elif tipo == "version":
            return f"VERSION(sistema, {desc.split(':')[-1].strip()})"
        return f"AFIRMA({desc[:100]})"

    # ============================================================
    # 2. GENERACIÓN DE HIPÓTESIS (Reglas de Inferencia)
    # ============================================================
    
    def generar_hipotesis(self, hipotesis_existentes: Optional[List[Hipotesis]] = None) -> List[Hipotesis]:
        """
        Genera hipótesis aplicando reglas de inferencia sobre premisas.
        
        Args:
            hipotesis_existentes: Lista de hipótesis ya generadas para evitar duplicados.
                                  Se comparan por claim similar y premisas_ids.
        
        Reglas:
        - Co-ocurrencia arquitectura + tecnología → Hipótesis IMPLICACION
        - Tecnología + especificación "permite/habilita" → Hipótesis CAUSAL
        - Métrica + arquitectura → Hipótesis PREDICCION
        - Múltiples fuentes confirman misma entidad → Hipótesis CLASIFICATORIA
        - Tecnología A requiere B (patrón "requiere") → Hipótesis RESTRICCION
        """
        hipotesis_nuevas = []
        
        # Construir set de claims existentes para deduplicación
        claims_existentes = set()
        premisas_ids_existentes = set()
        if hipotesis_existentes:
            for h in hipotesis_existentes:
                claims_existentes.add(h.claim.lower().strip())
                premisas_ids_existentes.update(h.premisas_ids)
        
        def _es_duplicada(claim: str, premisas_ids: List[str]) -> bool:
            claim_lower = claim.lower().strip()
            if claim_lower in claims_existentes:
                return True
            # También verificar overlap significativo de premisas
            if set(premisas_ids) & premisas_ids_existentes:
                return True
            return False
        
        # Agrupar premisas por entidad
        por_entidad = defaultdict(list)
        for p in self._premisas.values():
            for ent in p.entidades:
                por_entidad[ent].append(p)
        
        # Regla 1: Co-ocurrencia arquitectura + tecnología → IMPLICACION
        for arch_premisas in [p for p in self._premisas.values() if p.tipo == "arquitectura"]:
            for tech_premisas in [p for p in self._premisas.values() if p.tipo in ("tecnologia", "caracteristica")]:
                if self._coocurren_en_fuente(arch_premisas, tech_premisas):
                    h = self._crear_hipotesis_implicacion(arch_premisas, tech_premisas)
                    if h and not _es_duplicada(h.claim, h.premisas_ids):
                        hipotesis_nuevas.append(h)
        
        # Regla 2: Especificación con patrón causal → CAUSAL
        for esp in [p for p in self._premisas.values() if p.tipo == "especificacion"]:
            if any(re.search(pat, esp.proposicion, re.IGNORECASE) for pat in self.PATRONES_CAUSAL):
                h = self._crear_hipotesis_causal(esp)
                if h and not _es_duplicada(h.claim, h.premisas_ids):
                    hipotesis_nuevas.append(h)
        
        # Regla 3: Múltiples fuentes para misma entidad → CLASIFICATORIA
        for entidad, premisas in por_entidad.items():
            fuentes = set(p.fuente for p in premisas)
            if len(fuentes) >= 2 and len(premisas) >= 2:
                h = self._crear_hipotesis_clasificatoria(entidad, premisas)
                if h and not _es_duplicada(h.claim, h.premisas_ids):
                    hipotesis_nuevas.append(h)
        
        # Regla 4: Patrón "requiere/necesita" en especificación → RESTRICCION
        for esp in [p for p in self._premisas.values() if p.tipo == "especificacion"]:
            if any(re.search(pat, esp.proposicion, re.IGNORECASE) for pat in self.PATRONES_RESTRICCION):
                h = self._crear_hipotesis_restriccion(esp)
                if h and not _es_duplicada(h.claim, h.premisas_ids):
                    hipotesis_nuevas.append(h)
        
        # Registrar
        for h in hipotesis_nuevas:
            self._hipotesis[h.id] = h
        
        logger.info(f"MotorRazonamiento: {len(hipotesis_nuevas)} hipótesis generadas")
        return hipotesis_nuevas

    def _coocurren_en_fuente(self, p1: PremisaLogica, p2: PremisaLogica) -> bool:
        """Verifica si dos premisas comparten fuente o aparecen cerca en el corpus."""
        if p1.fuente == p2.fuente:
            return True
        # Buscar proximidad en corpus
        idx1 = self._corpus_evidencia.find(p1.evidencia_textual[:50])
        idx2 = self._corpus_evidencia.find(p2.evidencia_textual[:50])
        if idx1 >= 0 and idx2 >= 0 and abs(idx1 - idx2) < 500:
            return True
        return False

    def _crear_hipotesis_implicacion(self, arch: PremisaLogica, tech: PremisaLogica) -> Optional[Hipotesis]:
        self._contador += 1
        hid = f"H{self._contador:04d}"
        arch_name = arch.entidades[0] if arch.entidades else "arquitectura"
        tech_name = tech.entidades[0] if tech.entidades else "tecnología"
        
        return Hipotesis(
            id=hid,
            tipo=TipoHipotesis.IMPLICACION,
            claim=f"{arch_name} implica/soporta {tech_name}",
            premisas_ids=[arch.id, tech.id],
            prediccion_verificable=f"En documentación de {arch_name}, debe mencionarse {tech_name} como característica soportada",
            condiciones=[f"Contexto: arquitectura {arch_name}"],
            confianza_inicial=min(arch.confianza, tech.confianza) * 0.8,
            metadatos={"regla": "coocurrencia_arch_tech", "arch": arch.id, "tech": tech.id}
        )

    def _crear_hipotesis_causal(self, esp: PremisaLogica) -> Optional[Hipotesis]:
        self._contador += 1
        hid = f"H{self._contador:04d}"
        
        # Extraer causa y efecto de la proposición
        match = re.search(r'(\w+)\s+(permite|habilita|facilita)\s+(\w+)', esp.proposicion, re.IGNORECASE)
        if not match:
            match = re.search(r'(\w+)\s+(causa|genera|produce|provoca)\s+(\w+)', esp.proposicion, re.IGNORECASE)
        
        if match:
            causa, _, efecto = match.groups()
            return Hipotesis(
                id=hid,
                tipo=TipoHipotesis.CAUSAL,
                claim=f"{causa} causa/habilita {efecto}",
                premisas_ids=[esp.id],
                prediccion_verificable=f"Evidencia técnica que demuestre mecanismo: {causa} → {efecto}",
                condiciones=[f"Fuente: {esp.fuente}"],
                confianza_inicial=esp.confianza * 0.7,
                metadatos={"regla": "patron_causal", "causa": causa, "efecto": efecto}
            )
        return None

    def _crear_hipotesis_clasificatoria(self, entidad: str, premisas: List[PremisaLogica]) -> Optional[Hipotesis]:
        self._contador += 1
        hid = f"H{self._contador:04d}"
        tipos = set(p.tipo for p in premisas)
        
        return Hipotesis(
            id=hid,
            tipo=TipoHipotesis.CLASIFICATORIA,
            claim=f"{entidad} es una entidad técnica validada (múltiples fuentes: {', '.join(set(p.fuente for p in premisas))})",
            premisas_ids=[p.id for p in premisas],
            prediccion_verificable=f"Consenso entre fuentes independientes sobre {entidad}",
            condiciones=[f"Entidad: {entidad}", f"Tipos de hallazgo: {', '.join(tipos)}"],
            confianza_inicial=0.7,
            metadatos={"regla": "consenso_multi_fuente", "entidad": entidad, "fuentes": list(set(p.fuente for p in premisas))}
        )

    def _crear_hipotesis_restriccion(self, esp: PremisaLogica) -> Optional[Hipotesis]:
        self._contador += 1
        hid = f"H{self._contador:04d}"
        
        match = re.search(r'(\w+)\s+(requiere|necesita|depende de)\s+(\w+)', esp.proposicion, re.IGNORECASE)
        if match:
            a, _, b = match.groups()
            return Hipotesis(
                id=hid,
                tipo=TipoHipotesis.RESTRICCION,
                claim=f"{a} requiere {b} como condición necesaria",
                premisas_ids=[esp.id],
                prediccion_verificable=f"Documentación confirma que sin {b}, {a} no funciona",
                condiciones=[f"Fuente: {esp.fuente}"],
                confianza_inicial=esp.confianza * 0.75,
                metadatos={"regla": "patron_restriccion", "requerido": a, "requisito": b}
            )
        return None

    # ============================================================
    # 3. VERIFICACIÓN DE HIPÓTESIS CONTRA EVIDENCIA
    # ============================================================
    
    def verificar_hipotesis(self, hipotesis_id: Optional[str] = None) -> List[ResultadoVerificacion]:
        """
        Verifica hipótesis contra el corpus de evidencia.
        
        Args:
            hipotesis_id: ID específico o None para verificar todas
            
        Returns:
            Lista de ResultadoVerificacion
        """
        targets = [hipotesis_id] if hipotesis_id else list(self._hipotesis.keys())
        resultados = []
        
        for hid in targets:
            h = self._hipotesis.get(hid)
            if not h:
                continue
            
            resultado = self._verificar_una_hipotesis(h)
            self._verificaciones[hid] = resultado
            resultados.append(resultado)
        
        logger.info(f"MotorRazonamiento: {len(resultados)} hipótesis verificadas")
        return resultados

    def _verificar_una_hipotesis(self, h: Hipotesis) -> ResultadoVerificacion:
        """Verifica una hipótesis buscando evidencia en el corpus."""
        evidencia_soporte = []
        evidencia_contra = []
        brechas = []
        
        # Obtener premisas vinculadas
        premisas = [self._premisas[pid] for pid in h.premisas_ids if pid in self._premisas]
        
        # Estrategia según tipo de hipótesis
        if h.tipo == TipoHipotesis.IMPLICACION:
            evidencia_soporte, evidencia_contra, brechas = self._verificar_implicacion(h, premisas)
        elif h.tipo == TipoHipotesis.CAUSAL:
            evidencia_soporte, evidencia_contra, brechas = self._verificar_causal(h, premisas)
        elif h.tipo == TipoHipotesis.CLASIFICATORIA:
            evidencia_soporte, evidencia_contra, brechas = self._verificar_clasificatoria(h, premisas)
        elif h.tipo == TipoHipotesis.RESTRICCION:
            evidencia_soporte, evidencia_contra, brechas = self._verificar_restriccion(h, premisas)
        else:
            evidencia_soporte, evidencia_contra, brechas = self._verificar_generica(h, premisas)
        
        # Calcular puntuación
        puntuacion = self._calcular_puntuacion(evidencia_soporte, evidencia_contra, h.confianza_inicial)
        
        # Determinar estado
        if puntuacion >= self.umbral_verificacion and len(evidencia_soporte) > len(evidencia_contra):
            estado = EstadoVerificacion.VERIFICADA
        elif len(evidencia_contra) > len(evidencia_soporte):
            estado = EstadoVerificacion.REFUTADA
        elif evidencia_soporte and not evidencia_contra:
            estado = EstadoVerificacion.PARCIAL
        elif not evidencia_soporte and not evidencia_contra:
            estado = EstadoVerificacion.INDETERMINADA
        else:
            estado = EstadoVerificacion.ESPECULATIVA
        
        razonamiento = self._generar_razonamiento(h, estado, evidencia_soporte, evidencia_contra, brechas)
        
        return ResultadoVerificacion(
            hipotesis_id=h.id,
            estado=estado,
            evidencia_soporte=evidencia_soporte,
            evidencia_contra=evidencia_contra,
            puntuacion=puntuacion,
            razonamiento=razonamiento,
            brechas=brechas
        )

    def _verificar_implicacion(self, h: Hipotesis, premisas: List[PremisaLogica]) -> Tuple[List[str], List[str], List[str]]:
        soporte = []
        contra = []
        brechas = []
        
        # Recopilar todas las entidades de todas las premisas
        todas_entidades = set()
        for p in premisas:
            todas_entidades.update(p.entidades)
        
        if len(todas_entidades) < 2:
            brechas.append("Insuficientes entidades para verificar implicacion")
            return soporte[:3], contra[:3], brechas
        
        # Dividir corpus en oraciones
        oraciones = re.split(r'[.!?]+', self._corpus_evidencia)
        
        # Buscar oraciones que mencionen al menos 2 entidades distintas
        for oracion in oraciones:
            oracion = oracion.strip()
            if len(oracion) < 20:
                continue
            entidades_en_oracion = [e for e in todas_entidades if re.search(re.escape(e), oracion, re.IGNORECASE)]
            if len(entidades_en_oracion) >= 2:
                soporte.append(f"[{', '.join(entidades_en_oracion)}] {oracion[:200]}")
        
        if not soporte:
            # Fallback: buscar mención individual de cada entidad
            for ent in todas_entidades:
                matches = [o.strip() for o in oraciones if re.search(re.escape(ent), o, re.IGNORECASE) and len(o.strip()) > 20]
                if matches:
                    soporte.append(f"[{ent}] {matches[0][:200]}")
            if not soporte:
                brechas.append("No se encontro mencion conjunta ni individual de las entidades en el corpus")
        
        return soporte[:3], contra[:3], brechas

    def _verificar_causal(self, h: Hipotesis, premisas: List[PremisaLogica]) -> Tuple[List[str], List[str], List[str]]:
        soporte = []
        contra = []
        brechas = []
        
        causa = h.metadatos.get("causa", "")
        efecto = h.metadatos.get("efecto", "")
        
        if causa and efecto:
            # Dividir en oraciones
            oraciones = re.split(r'[.!?]+', self._corpus_evidencia)
            
            # Buscar oraciones que mencionen tanto causa como efecto
            for oracion in oraciones:
                oracion = oracion.strip()
                if len(oracion) < 20:
                    continue
                if re.search(re.escape(causa), oracion, re.IGNORECASE) and re.search(re.escape(efecto), oracion, re.IGNORECASE):
                    soporte.append(oracion[:200])
            
            # Buscar mecanismo técnico en oraciones con ambos
            mech_patterns = [r'mediante', r'mecanismo', r'funciona', r'implementa', r'arquitectura', r'permite', r'habilita']
            for s in soporte[:]:
                if any(re.search(mp, s, re.IGNORECASE) for mp in mech_patterns):
                    soporte.append(f"[MECANISMO] {s}")
        
        if not soporte:
            brechas.append(f"No se encontró explicación mecánica para {causa} -> {efecto}")
        
        return soporte[:3], contra[:3], brechas

    def _verificar_clasificatoria(self, h: Hipotesis, premisas: List[PremisaLogica]) -> Tuple[List[str], List[str], List[str]]:
        soporte = []
        contra = []
        brechas = []
        
        entidad = h.metadatos.get("entidad", "")
        fuentes = h.metadatos.get("fuentes", [])
        
        if entidad:
            # Contar menciones por fuente
            for fuente in fuentes:
                count = len(re.findall(re.escape(entidad), self._corpus_evidencia, re.IGNORECASE))
                if count > 0:
                    soporte.append(f"Entidad '{entidad}' mencionada {count} veces en fuente {fuente}")
            
            if len(fuentes) >= 2:
                soporte.append(f"Consenso confirmado: {len(fuentes)} fuentes independientes")
        
        return soporte[:3], contra[:3], brechas

    def _verificar_restriccion(self, h: Hipotesis, premisas: List[PremisaLogica]) -> Tuple[List[str], List[str], List[str]]:
        soporte = []
        contra = []
        brechas = []
        
        requerido = h.metadatos.get("requerido", "")
        requisito = h.metadatos.get("requisito", "")
        
        if requerido and requisito:
            # Buscar "requiere X para Y" o "Y necesita X"
            patterns = [
                rf'{requisito}.*(?:requiere|necesario|necesita).*{requerido}',
                rf'{requerido}.*(?:requiere|necesario|necesita).*{requisito}',
            ]
            for pat in patterns:
                matches = re.findall(pat, self._corpus_evidencia, re.IGNORECASE)
                soporte.extend([m.strip() for m in matches[:2]])
        
        if not soporte:
            brechas.append(f"No se confirmó relación de requisito {requerido} → {requisito}")
        
        return soporte[:3], contra[:3], brechas

    def _verificar_generica(self, h: Hipotesis, premisas: List[PremisaLogica]) -> Tuple[List[str], List[str], List[str]]:
        soporte = []
        contra = []
        brechas = []
        
        for p in premisas:
            if p.evidencia_textual in self._corpus_evidencia:
                soporte.append(p.evidencia_textual[:200])
        
        if not soporte:
            brechas.append("Sin evidencia directa en corpus para esta hipótesis")
        
        return soporte[:3], contra[:3], brechas

    def _calcular_puntuacion(self, soporte: List[str], contra: List[str], prior: float) -> float:
        """Bayesiano simplificado: prior + evidencia."""
        n_soporte = len(soporte)
        n_contra = len(contra)
        
        if n_soporte == 0 and n_contra == 0:
            return prior * 0.3  # Penalizar falta de evidencia
        
        likelihood = (n_soporte + 1) / (n_soporte + n_contra + 2)
        # Combinar prior y likelihood
        posterior = 0.4 * prior + 0.6 * likelihood
        return round(min(max(posterior, 0.0), 1.0), 2)

    def _generar_razonamiento(self, h: Hipotesis, estado: EstadoVerificacion, 
                              soporte: List[str], contra: List[str], brechas: List[str]) -> str:
        parts = [
            f"Hipótesis {h.id} ({h.tipo.value}): {h.claim}",
            f"Estado: {estado.value.upper()} (puntuación: {self._verificaciones[h.id].puntuacion if h.id in self._verificaciones else 'N/A'})",
            f"Premisas base: {len(h.premisas_ids)}",
            f"Evidencia a favor: {len(soporte)}",
            f"Evidencia en contra: {len(contra)}",
        ]
        if brechas:
            parts.append(f"Brechas detectadas: {'; '.join(brechas)}")
        return " | ".join(parts)

    # ============================================================
    # 4. PRODUCCIÓN DE CONCLUSIONES VERIFICADAS
    # ============================================================
    
    def producir_conclusiones(self) -> List[ConclusionVerificada]:
        """Genera conclusiones finales a partir de verificaciones."""
        conclusiones = []
        
        for hid, verificacion in self._verificaciones.items():
            h = self._hipotesis[hid]
            
            # Determinar fuerza epistemica
            if verificacion.estado == EstadoVerificacion.VERIFICADA and verificacion.puntuacion >= 0.8:
                fuerza = "fuerte"
            elif verificacion.estado == EstadoVerificacion.VERIFICADA:
                fuerza = "moderada"
            elif verificacion.estado == EstadoVerificacion.PARCIAL:
                fuerza = "débil"
            else:
                fuerza = "especulativa"
            
            # Generar implicaciones
            implicaciones = self._generar_implicaciones(h, verificacion)
            
            conclusion = ConclusionVerificada(
                hipotesis=h,
                verificacion=verificacion,
                fuerza_epistemica=fuerza,
                implicaciones=implicaciones
            )
            conclusiones.append(conclusion)
        
        self._conclusiones = conclusiones
        logger.info(f"MotorRazonamiento: {len(conclusiones)} conclusiones producidas")
        return conclusiones

    def _generar_implicaciones(self, h: Hipotesis, v: ResultadoVerificacion) -> List[str]:
        impl = []
        
        if h.tipo == TipoHipotesis.CAUSAL and v.estado == EstadoVerificacion.VERIFICADA:
            impl.append(f"Relación causal establecida: {h.claim} — usable para razonamiento predictivo")
        elif h.tipo == TipoHipotesis.IMPLICACION and v.estado == EstadoVerificacion.VERIFICADA:
            impl.append(f"Dependencia confirmada: {h.claim} — considerar en análisis de arquitectura")
        elif h.tipo == TipoHipotesis.RESTRICCION and v.estado == EstadoVerificacion.VERIFICADA:
            impl.append(f"Restricción técnica validada: {h.claim} — aplicar en planificación")
        elif h.tipo == TipoHipotesis.CLASIFICATORIA and v.estado == EstadoVerificacion.VERIFICADA:
            impl.append(f"Entidad confirmada multi-fuente: {h.claim} — elevar confianza base")
        
        if v.brechas:
            impl.append(f"Investigación pendiente: {v.brechas[0]}")
        
        return impl

    # ============================================================
    # API PÚBLICA: PIPELINE COMPLETO
    # ============================================================
    
    def ejecutar_pipeline_completo(
        self, 
        hallazgos: List[Any], 
        corpus: str,
        hipotesis_existentes: Optional[List[Hipotesis]] = None
    ) -> Dict[str, Any]:
        """
        Ejecuta el pipeline completo: Premisas → Hipótesis → Verificación → Conclusiones.
        
        Args:
            hallazgos: Hallazgos del DeepSynthesizer
            corpus: Corpus de evidencia
            hipotesis_existentes: Hipótesis ya generadas en iteraciones previas (para deduplicación)
        
        Returns:
            Dict con todas las etapas para trazabilidad
        """
        logger.info("MotorRazonamiento: Iniciando pipeline completo Beta")
        
        # 1. Premisas
        premisas = self.recibir_hallazgos(hallazgos, corpus)
        
        # 2. Hipótesis (con deduplicación contra iteraciones previas)
        hipotesis = self.generar_hipotesis(hipotesis_existentes=hipotesis_existentes)
        
        # 3. Verificación
        verificaciones = self.verificar_hipotesis()
        
        # 4. Conclusiones
        conclusiones = self.producir_conclusiones()
        
        return {
            "premisas": [self._premisa_a_dict(p) for p in premisas],
            "hipotesis": [self._hipotesis_a_dict(h) for h in hipotesis],
            "verificaciones": [self._verificacion_a_dict(v) for v in verificaciones],
            "conclusiones": [self._conclusion_a_dict(c) for c in conclusiones],
            "metricas": {
                "total_premisas": len(premisas),
                "total_hipotesis": len(hipotesis),
                "verificadas": sum(1 for v in verificaciones if v.estado == EstadoVerificacion.VERIFICADA),
                "refutadas": sum(1 for v in verificaciones if v.estado == EstadoVerificacion.REFUTADA),
                "parciales": sum(1 for v in verificaciones if v.estado == EstadoVerificacion.PARCIAL),
                "indeterminadas": sum(1 for v in verificaciones if v.estado == EstadoVerificacion.INDETERMINADA),
                "fuerza_promedio": sum(c.verificacion.puntuacion for c in conclusiones) / len(conclusiones) if conclusiones else 0
            }
        }

    def _premisa_a_dict(self, p: PremisaLogica) -> Dict:
        return {
            "id": p.id, "tipo": p.tipo, "proposicion": p.proposicion,
            "fuente": p.fuente, "confianza": p.confianza,
            "entidades": p.entidades, "evidencia": p.evidencia_textual[:200]
        }

    def _hipotesis_a_dict(self, h: Hipotesis) -> Dict:
        return {
            "id": h.id, "tipo": h.tipo.value, "claim": h.claim,
            "premisas": h.premisas_ids, "prediccion": h.prediccion_verificable,
            "confianza_inicial": h.confianza_inicial, "metadatos": h.metadatos
        }

    def _verificacion_a_dict(self, v: ResultadoVerificacion) -> Dict:
        return {
            "hipotesis_id": v.hipotesis_id, "estado": v.estado.value,
            "puntuacion": v.puntuacion, "razonamiento": v.razonamiento,
            "soporte": len(v.evidencia_soporte), "contra": len(v.evidencia_contra),
            "brechas": v.brechas
        }

    def _conclusion_a_dict(self, c: ConclusionVerificada) -> Dict:
        return {
            "claim": c.hipotesis.claim,
            "tipo": c.hipotesis.tipo.value,
            "estado": c.verificacion.estado.value,
            "puntuacion": c.verificacion.puntuacion,
            "fuerza": c.fuerza_epistemica,
            "implicaciones": c.implicaciones
        }


def crear_motor_razonamiento(umbral_verificacion: float = 0.6) -> MotorRazonamientoSuperior:
    """Factoría para MotorRazonamientoSuperior."""
    return MotorRazonamientoSuperior(umbral_verificacion=umbral_verificacion)