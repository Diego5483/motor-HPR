"""
Módulo SourceEvaluator - Estructuras de datos base para evaluación de fuentes
según la taxonomía de tres niveles de confianza del motor HPR.

FASE 1: Define las estructuras de entrada y salida (tipos/interfaces).
FASE 2: Implementa lógica de evaluación para Nivel Alto (Institucional / Verificado).
FASE 3: Implementa lógica de evaluación para Nivel Medio (Comunitario / Técnico).
FASE 4: Implementa lógica de evaluación para Nivel Bajo (Independiente / Abierto).
FASE 5: Orquestador unificado de evaluación jerárquica.
FASE FINAL: Integración QueryBuilder (operadores Google) + E-E-A-T (calidad semántica) + SourceEvaluator (confianza jerárquica).
"""

from enum import Enum
from typing import Optional, Literal, List, Dict, Set, Tuple, Callable
from pydantic import BaseModel, Field, HttpUrl
from dataclasses import dataclass, field
from datetime import datetime, timezone
import re
import logging
import uuid

logger = logging.getLogger(__name__)


class TrustLevel(str, Enum):
    """Niveles de confianza definidos en la taxonomía HPR."""
    HIGH = "alto"      # Nivel Alto - Institucional / Verificado
    MEDIUM = "medio"   # Nivel Medio - Comunitario / Técnico
    LOW = "bajo"       # Nivel Bajo - Independiente / Abierto


class SourceCategory(str, Enum):
    """Categorías de fuente para clasificación inicial."""
    GOVERNMENT = "gubernamental"        # .gov, .mil
    EDUCATIONAL = "educativo"           # .edu
    OFFICIAL_CORPORATE = "corporativo_oficial"  # Portales corporativos oficiales
    OFFICIAL_FORUM = "foro_oficial"     # Foros oficiales de proyectos/productos
    TECHNICAL_REPO = "repo_tecnico"     # Repositorios técnicos (GitHub, GitLab, etc.)
    INDEPENDENT_BLOG = "blog_independiente"
    OPEN_SOURCE = "fuente_abierta"
    UNKNOWN = "desconocido"


class EvaluationStatus(str, Enum):
    """Estados resultantes de la evaluación."""
    DIRECT_PASS = "paso_directo"              # Nivel Alto: pasa sin validación adicional
    CROSS_VALIDATION_REQUIRED = "validacion_cruzada_requerida"  # Nivel Medio
    STRICT_SANITIZATION = "saneamiento_estricto"  # Nivel Bajo
    REJECTED = "rechazado"                    # No cumple criterios mínimos


@dataclass(frozen=True)
class TrustLevelConfig:
    """Configuración inmutable por nivel de confianza."""
    level: TrustLevel
    weight: float
    min_weight: float
    max_weight: float
    requires_cross_validation: bool
    requires_strict_sanitization: bool
    direct_pass: bool


# Configuración estática de los tres niveles (constantes del sistema)
TRUST_LEVEL_CONFIGS: dict[TrustLevel, TrustLevelConfig] = {
    TrustLevel.HIGH: TrustLevelConfig(
        level=TrustLevel.HIGH,
        weight=1.0,
        min_weight=1.0,
        max_weight=1.0,
        requires_cross_validation=False,
        requires_strict_sanitization=False,
        direct_pass=True,
    ),
    TrustLevel.MEDIUM: TrustLevelConfig(
        level=TrustLevel.MEDIUM,
        weight=0.65,  # Punto medio entre 0.6–0.7
        min_weight=0.6,
        max_weight=0.7,
        requires_cross_validation=True,
        requires_strict_sanitization=False,
        direct_pass=False,
    ),
    TrustLevel.LOW: TrustLevelConfig(
        level=TrustLevel.LOW,
        weight=0.3,
        min_weight=0.0,
        max_weight=0.5,
        requires_cross_validation=False,
        requires_strict_sanitization=True,
        direct_pass=False,
    ),
}


class SourceInput(BaseModel):
    """
    Estructura de entrada para evaluar una fuente.
    Contiene los metadatos mínimos necesarios para la clasificación.
    """
    # Identificación de la fuente
    url: HttpUrl = Field(..., description="URL completa de la fuente")
    domain: str = Field(..., description="Dominio extraído de la URL (ej: example.gov)")
    
    # Metadatos opcionales para clasificación heurística
    title: Optional[str] = Field(None, description="Título de la página/documento")
    content_preview: Optional[str] = Field(None, description="Primeros N caracteres del contenido")
    content_length: Optional[int] = Field(None, ge=0, description="Longitud total del contenido en caracteres")
    
    # Contexto adicional (opcional)
    source_category_hint: Optional[SourceCategory] = Field(
        None, 
        description="Pista de categoría si ya se conoce (ej: de un conector específico)"
    )
    is_official_claimed: bool = Field(
        False, 
        description="Indica si la fuente se autodeclara oficial (requiere verificación)"
    )
    
    # Configuración de evaluación (opcional, para sobrescribir defaults)
    force_level: Optional[TrustLevel] = Field(
        None, 
        description="Forzar nivel de confianza (uso interno/testing)"
    )


class SourceEvaluationResult(BaseModel):
    """
    Estructura de salida resultante de la evaluación.
    Contiene la decisión y metadatos para trazabilidad.
    """
    # Clasificación resultante
    trust_level: TrustLevel = Field(..., description="Nivel de confianza asignado")
    source_category: SourceCategory = Field(..., description="Categoría detectada/asignada")
    evaluation_status: EvaluationStatus = Field(..., description="Estado de procesamiento resultante")
    
    # Pesos y scoring
    assigned_weight: float = Field(..., ge=0.0, le=1.0, description="Peso final asignado (0.0-1.0)")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Score de confianza interno (0.0-1.0)")
    
    # Reglas y razonamiento (para auditoría)
    matched_rules: list[str] = Field(
        default_factory=list, 
        description="Lista de reglas/patrones que coincidieron para la clasificación"
    )
    rejection_reasons: list[str] = Field(
        default_factory=list, 
        description="Razones de rechazo si evaluation_status == REJECTED"
    )
    
    # Acciones requeridas
    requires_cross_validation: bool = Field(..., description="Requiere validación cruzada (Nivel Medio)")
    requires_strict_sanitization: bool = Field(..., description="Requiere saneamiento estricto (Nivel Bajo)")
    direct_pass: bool = Field(..., description="Paso directo sin bloqueos (Nivel Alto)")
    
    # Metadatos de trazabilidad
    evaluated_at: str = Field(..., description="Timestamp ISO 8601 de la evaluación")
    evaluator_version: str = Field(default="1.0.0", description="Versión del evaluador")


class BatchEvaluationInput(BaseModel):
    """Entrada para evaluación en lote de múltiples fuentes."""
    sources: list[SourceInput] = Field(..., min_length=1, max_length=1000)
    default_category: Optional[SourceCategory] = Field(
        None, 
        description="Categoría por defecto si no se puede determinar"
    )


class BatchEvaluationResult(BaseModel):
    """Resultado de evaluación en lote."""
    results: list[SourceEvaluationResult] = Field(...)
    summary: dict[TrustLevel, int] = Field(
        default_factory=dict, 
        description="Conteo de fuentes por nivel de confianza"
    )
    total_evaluated: int = Field(..., ge=0)
    total_rejected: int = Field(..., ge=0)


# =============================================================================
# FASE 2: LÓGICA DE EVALUACIÓN - NIVEL ALTO (Institucional / Verificado)
# =============================================================================

# TLDs oficiales que califican automáticamente como Nivel Alto
OFFICIAL_TLDS: frozenset[str] = frozenset({
    "gov",      # Gobiernos (EE.UU. y otros países usan .gov o .gob)
    "mil",      # Militar (EE.UU.)
    "edu",      # Educativo (EE.UU. y otros)
    "gob",      # Gobiernos (Latam/España: .gob.es, .gob.mx, .gob.ar, etc.)
    "gouv",     # Gobiernos (Francia: .gouv.fr)
    "govt",     # Gobiernos (NZ, UK variants)
    "ac",       # Académico (UK: .ac.uk, Japón: .ac.jp, etc.)
})

# Dominios raíz oficiales de segundo nivel (ej: gov.br, gob.es, ac.uk, edu.au)
# Estos son los dominios "registrables" oficiales que operan como TLDs efectivos
OFFICIAL_SECOND_LEVEL_DOMAINS: frozenset[str] = frozenset({
    # Gobierno
    "gov.br", "gov.ar", "gov.co", "gov.cl", "gov.ec", "gov.pe", "gov.ve", "gov.py", "gov.uy", "gov.bo",
    "gob.es", "gob.mx", "gob.ar", "gob.cl", "gob.pe", "gob.ve", "gob.bo", "gob.ec", "gob.sv", "gob.hn", "gob.ni", "gob.pa", "gob.do",
    "gouv.fr", "gouv.be", "gouv.ca", "gouv.ci", "gouv.sn",
    "govt.nz", "govt.au", "govt.za",
    "gov.uk", "gov.au", "gov.ca", "gov.cn", "gov.in", "gov.jp", "gov.kr", "gov.sg", "gov.ae", "gov.qa", "gov.kw", "gov.bh", "gov.om", "gov.jo", "gov.lb", "gov.iq", "gov.ir", "gov.tr", "gov.il", "gov.pl", "gov.ro", "gov.hu", "gov.cz", "gov.sk", "gov.si", "gov.hr", "gov.rs", "gov.ba", "gov.me", "gov.mk", "gov.al", "gov.md", "gov.ge", "gov.am", "gov.az", "gov.by", "gov.kz", "gov.uz", "gov.kg", "gov.tj", "gov.tm", "gov.af", "gov.pk", "gov.bd", "gov.lk", "gov.np", "gov.mm", "gov.kh", "gov.la", "gov.mn", "gov.kp", "gov.tw", "gov.hk", "gov.mo",
    # Militar
    "mil.br", "mil.ar", "mil.co", "mil.cl", "mil.ec", "mil.pe", "mil.ve", "mil.py", "mil.uy", "mil.bo",
    "mil.uk", "mil.au", "mil.ca", "mil.cn", "mil.in", "mil.jp", "mil.kr", "mil.sg", "mil.ae", "mil.pl", "mil.fr", "mil.de", "mil.it", "mil.es", "mil.nl", "mil.be", "mil.no", "mil.se", "mil.dk", "mil.fi", "mil.at", "mil.ch", "mil.gr", "mil.pt", "mil.ie", "mil.nz", "mil.za", "mil.tr", "mil.il", "mil.ro", "mil.hu", "mil.cz", "mil.sk", "mil.si", "mil.hr", "mil.rs", "mil.ba", "mil.me", "mil.mk", "mil.al", "mil.md", "mil.ge", "mil.am", "mil.az", "mil.by", "mil.kz", "mil.uz", "mil.kg", "mil.tj", "mil.tm", "mil.af", "mil.pk", "mil.bd", "mil.lk", "mil.np", "mil.mm", "mil.kh", "mil.la", "mil.mn", "mil.tw", "mil.hk", "mil.mo",
    # Académico / Educativo
    "ac.uk", "ac.jp", "ac.nz", "ac.au", "ac.za", "ac.il", "ac.in", "ac.cn", "ac.kr", "ac.sg", "ac.th", "ac.my", "ac.id", "ac.ph", "ac.vn", "ac.tw", "ac.hk", "ac.mo",
    "edu.au", "edu.cn", "edu.hk", "edu.mo", "edu.tw", "edu.sg", "edu.my", "edu.ph", "edu.vn", "edu.th", "edu.id", "edu.in", "edu.pk", "edu.bd", "edu.lk", "edu.np", "edu.mm", "edu.kh", "edu.la", "edu.mn", "edu.kz", "edu.uz", "edu.kg", "edu.tj", "edu.tm", "edu.af", "edu.ir", "edu.iq", "edu.jo", "edu.lb", "edu.ps", "edu.sy", "edu.il", "edu.tr", "edu.cy", "edu.gr", "edu.mt", "edu.pt", "edu.es", "edu.it", "edu.fr", "edu.be", "edu.nl", "edu.lu", "edu.de", "edu.at", "edu.ch", "edu.li", "edu.pl", "edu.cz", "edu.sk", "edu.hu", "edu.ro", "edu.bg", "edu.hr", "edu.si", "edu.rs", "edu.ba", "edu.me", "edu.mk", "edu.al", "edu.md", "edu.ge", "edu.am", "edu.az", "edu.by", "edu.ua", "edu.ru", "edu.ee", "edu.lv", "edu.lt", "edu.fi", "edu.se", "edu.no", "edu.dk", "edu.is", "edu.ie", "edu.uk",
})

# Patrones de subdominios oficiales comunes (para detectar .gov.br, .gov.ar, etc.)
OFFICIAL_DOMAIN_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"\.gov\.[a-z]{2}$"),      # .gov.br, .gov.ar, .gov.co, etc.
    re.compile(r"\.gob\.[a-z]{2}$"),      # .gob.es, .gob.mx, .gob.ar, etc.
    re.compile(r"\.gouv\.[a-z]{2}$"),     # .gouv.fr, etc.
    re.compile(r"\.govt\.[a-z]{2}$"),     # .govt.nz, etc.
    re.compile(r"\.ac\.[a-z]{2}$"),       # .ac.uk, .ac.jp, .ac.nz, etc.
    re.compile(r"\.edu\.[a-z]{2}$"),      # .edu.au, .edu.mx, etc.
    re.compile(r"\.mil\.[a-z]{2}$"),      # .mil.br, etc.
)

# Lista curada de portales corporativos oficiales verificados (dominios base)
# Estos son dominios raíz de organizaciones que operan portales oficiales
# de documentación, desarrolladores, APIs, status, security, etc.
OFFICIAL_CORPORATE_DOMAINS: frozenset[str] = frozenset({
    # Tecnología / Semiconductores / IA
    "nvidia.com",
    "amd.com",
    "intel.com",
    "qualcomm.com",
    "apple.com",
    "microsoft.com",
    "google.com",
    "aws.amazon.com",  # Subdominio principal de AWS
    "cloud.google.com",
    "azure.microsoft.com",
    # ARM / Arquitectura de hardware
    "arm.com",
    "developer.arm.com",
    "armdeveloper.com",
    "arm.com.cn",
    
    # Plataformas de desarrollo / Repositorios oficiales
    "github.com",
    "gitlab.com",
    "bitbucket.org",
    
    # Cloud / Infraestructura
    "cloudflare.com",
    "fastly.com",
    "akamai.com",
    "digitalocean.com",
    "linode.com",
    "vultr.com",
    
    # Bases de datos / Infraestructura de datos
    "postgresql.org",
    "mysql.com",
    "mongodb.com",
    "redis.io",
    "elastic.co",
    "confluent.io",
    
    # Observabilidad / Monitoring
    "datadoghq.com",
    "newrelic.com",
    "grafana.com",
    "prometheus.io",
    
    # Seguridad / Certificados
    "letsencrypt.org",
    "digicert.com",
    "globalsign.com",
    "sectigo.com",
    
    # Estándares / Consorcios
    "w3.org",
    "ietf.org",
    "iso.org",
    "ecma-international.org",
    "khronos.org",
    "open-group.org",
    
    # Linux / Open Source Foundations
    "linuxfoundation.org",
    "kernel.org",
    "debian.org",
    "ubuntu.com",
    "redhat.com",
    "suse.com",
    "archlinux.org",
    "fedora-project.org",
    "opensuse.org",
    
    # Lenguajes / Runtimes oficiales
    "python.org",
    "rust-lang.org",
    "golang.org",
    "nodejs.org",
    "openjdk.org",
    "dotnet.microsoft.com",
    "php.net",
    "ruby-lang.org",
    "perl.org",
    "lua.org",
    
    # Navegadores / Web Standards
    "mozilla.org",
    "webkit.org",
    "chromium.org",
    "v8.dev",
    
    # IA / ML Frameworks oficiales
    "pytorch.org",
    "tensorflow.org",
    "jax.dev",
    "huggingface.co",
    "onnx.ai",
    "mlflow.org",
    "lightning.ai",
    
    # Contenedores / Orquestación
    "docker.com",
    "kubernetes.io",
    "cncf.io",
    "helm.sh",
    "istio.io",
    "envoyproxy.io",
    
    # APIs / Especificaciones
    "swagger.io",
    "openapis.org",
    "graphql.org",
    "grpc.io",
    "asyncapi.com",
})


def _extract_tld(domain: str) -> str:
    """Extrae el TLD (último segmento) de un dominio en minúsculas."""
    return domain.lower().split(".")[-1]


def _is_official_second_level_domain(domain: str) -> bool:
    """Verifica si el dominio es un dominio oficial de segundo nivel (ej: gov.br, gob.es, ac.uk)."""
    return domain.lower() in OFFICIAL_SECOND_LEVEL_DOMAINS


def _extract_base_domain(domain: str) -> str:
    """
    Extrae el dominio base (registrable domain) para comparación contra lista corporativa.
    Ej: 'developer.nvidia.com' -> 'nvidia.com'
    Ej: 'docs.aws.amazon.com' -> 'aws.amazon.com'
    """
    parts = domain.lower().split(".")
    if len(parts) >= 2:
        # Manejar casos de dos niveles TLD (co.uk, com.br, gov.br, etc.)
        # Heurística: si el penúltimo es un TLD conocido de dos partes
        two_level_tlds = {"co", "com", "gov", "gob", "gouv", "govt", "ac", "edu", "mil", "org", "net"}
        if len(parts) >= 3 and parts[-2] in two_level_tlds:
            return ".".join(parts[-3:])
        return ".".join(parts[-2:])
    return domain.lower()


def _matches_official_pattern(domain: str) -> bool:
    """Verifica si el dominio coincide con patrones de dominios oficiales de dos niveles."""
    domain_lower = domain.lower()
    return any(pattern.search(domain_lower) for pattern in OFFICIAL_DOMAIN_PATTERNS)


def _is_official_tld(domain: str) -> bool:
    """Verifica si el dominio termina en un TLD oficial reconocido."""
    return _extract_tld(domain) in OFFICIAL_TLDS


def _is_official_domain(domain: str) -> bool:
    """Verifica si el dominio califica como oficial (TLD directo o segundo nivel oficial)."""
    return _is_official_tld(domain) or _is_official_second_level_domain(domain)


def _is_official_corporate_domain(domain: str) -> bool:
    """Verifica si el dominio (o su dominio base) está en la lista corporativa oficial."""
    domain_lower = domain.lower()
    base_domain = _extract_base_domain(domain_lower)
    return domain_lower in OFFICIAL_CORPORATE_DOMAINS or base_domain in OFFICIAL_CORPORATE_DOMAINS


class HighTrustEvaluationError(Exception):
    """Excepción específica para errores en evaluación de Nivel Alto."""
    pass


class HighTrustEvaluator:
    """
    Evaluador especializado para fuentes de Nivel Alto (Institucional / Verificado).
    
    Responsabilidad única: Determinar si una fuente califica como Nivel Alto
    basándose en criterios estrictos de dominios oficiales y corporativos verificados.
    
    Características:
    - Peso fijo 1.0 (sin variación)
    - Paso directo sin bloqueos (direct_pass=True)
    - Sin validación cruzada ni saneamiento requerido
    - Trazabilidad completa de reglas coincidentes
    """
    
    # Versión del evaluador para trazabilidad
    VERSION = "2.0.0"
    
    def __init__(self) -> None:
        # Configuración inmutable desde las constantes del sistema
        self._config = TRUST_LEVEL_CONFIGS[TrustLevel.HIGH]
    
    def evaluate(self, source: SourceInput) -> SourceEvaluationResult:
        """
        Evalúa una fuente para determinar si califica como Nivel Alto.
        
        Args:
            source: SourceInput con url, domain y metadatos opcionales
            
        Returns:
            SourceEvaluationResult con clasificación Nivel Alto si cumple criterios,
            o resultado indicando que no califica (para que otro evaluador lo procese).
        """
        matched_rules: list[str] = []
        trust_level = TrustLevel.HIGH
        source_category = SourceCategory.UNKNOWN
        
        # Normalizar dominio de entrada
        domain = source.domain.lower().strip()
        if not domain:
            raise HighTrustEvaluationError("Dominio vacío en SourceInput")
        
        # --- REGLA 1: TLDs oficiales directos (.gov, .mil, .edu, .gob, .gouv, .govt, .ac) ---
        if _is_official_tld(domain):
            tld = _extract_tld(domain)
            matched_rules.append(f"official_tld:{tld}")
            if tld in ("gov", "gob", "gouv", "govt", "mil"):
                source_category = SourceCategory.GOVERNMENT
            elif tld in ("edu", "ac"):
                source_category = SourceCategory.EDUCATIONAL
        
        # --- REGLA 1b: Dominios oficiales de segundo nivel (gov.br, gob.es, ac.uk, edu.au, etc.) ---
        elif _is_official_second_level_domain(domain):
            matched_rules.append(f"official_second_level_domain:{domain}")
            # Determinar categoría por el dominio
            if any(domain.startswith(prefix) for prefix in ("gov.", "gob.", "gouv.", "govt.", "mil.")):
                source_category = SourceCategory.GOVERNMENT
            elif any(domain.startswith(prefix) for prefix in ("edu.", "ac.")):
                source_category = SourceCategory.EDUCATIONAL
        
        # --- REGLA 2: Patrones de dominios oficiales de dos niveles (.gov.br, .gob.es, .ac.uk, etc.) ---
        elif _matches_official_pattern(domain):
            matched_rules.append("official_two_level_pattern")
            # Determinar categoría por el patrón
            if any(domain.endswith(suf) for suf in (".gov.", ".gob.", ".gouv.", ".govt.", ".mil.")):
                source_category = SourceCategory.GOVERNMENT
            elif any(domain.endswith(suf) for suf in (".edu.", ".ac.")):
                source_category = SourceCategory.EDUCATIONAL
        
        # --- REGLA 3: Portales corporativos oficiales verificados ---
        elif _is_official_corporate_domain(domain):
            matched_rules.append("official_corporate_domain")
            source_category = SourceCategory.OFFICIAL_CORPORATE
        
        # --- REGLA 4: Pista de categoría explícita (source_category_hint) ---
        elif source.source_category_hint in (SourceCategory.GOVERNMENT, SourceCategory.EDUCATIONAL, SourceCategory.OFFICIAL_CORPORATE):
            # La pista ayuda pero requiere confirmación por dominio
            matched_rules.append(f"category_hint:{source.source_category_hint.value}")
            source_category = source.source_category_hint
            # NOTA: No asignamos Nivel Alto solo por hint; requerimos coincidencia de dominio
            # Esto se maneja devolviendo None o un resultado "no califica"
        
        # Si no coincidió ninguna regla de Nivel Alto, indicar que no califica
        if not matched_rules:
            return self._build_non_qualifying_result(source, domain)
        
        # Construir resultado exitoso de Nivel Alto
        return self._build_high_trust_result(
            source=source,
            domain=domain,
            source_category=source_category,
            matched_rules=matched_rules,
        )
    
    def _build_high_trust_result(
        self,
        source: SourceInput,
        domain: str,
        source_category: SourceCategory,
        matched_rules: list[str],
    ) -> SourceEvaluationResult:
        """Construye resultado exitoso para Nivel Alto."""
        now_iso = datetime.now(timezone.utc).isoformat()
        
        return SourceEvaluationResult(
            trust_level=TrustLevel.HIGH,
            source_category=source_category,
            evaluation_status=EvaluationStatus.DIRECT_PASS,
            assigned_weight=self._config.weight,  # 1.0
            confidence_score=1.0,  # Máxima confianza para Nivel Alto verificado
            matched_rules=matched_rules,
            rejection_reasons=[],
            requires_cross_validation=False,
            requires_strict_sanitization=False,
            direct_pass=True,
            evaluated_at=now_iso,
            evaluator_version=self.VERSION,
        )
    
    def _build_non_qualifying_result(
        self,
        source: SourceInput,
        domain: str,
    ) -> SourceEvaluationResult:
        """
        Construye resultado indicando que la fuente NO califica para Nivel Alto.
        Esto permite que el pipeline continúe con evaluadores de nivel medio/bajo.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        
        return SourceEvaluationResult(
            trust_level=TrustLevel.HIGH,  # Nivel intentado
            source_category=SourceCategory.UNKNOWN,
            evaluation_status=EvaluationStatus.REJECTED,  # No califica para este nivel
            assigned_weight=0.0,
            confidence_score=0.0,
            matched_rules=[],
            rejection_reasons=[f"Domain '{domain}' does not match any High Trust criteria (official TLD, official pattern, or verified corporate domain)"],
            requires_cross_validation=False,
            requires_strict_sanitization=False,
            direct_pass=False,
            evaluated_at=now_iso,
            evaluator_version=self.VERSION,
        )
    
    def qualifies_as_high_trust(self, domain: str) -> bool:
        """
        Verificación rápida booleana: ¿el dominio califica como Nivel Alto?
        Útil para pre-filtrado sin construir resultado completo.
        """
        domain_lower = domain.lower().strip()
        return (
            _is_official_tld(domain_lower)
            or _is_official_second_level_domain(domain_lower)
            or _matches_official_pattern(domain_lower)
            or _is_official_corporate_domain(domain_lower)
        )


# Función de conveniencia para uso directo
def evaluate_high_trust(source: SourceInput) -> SourceEvaluationResult:
    """
    Función de conveniencia para evaluar una fuente contra criterios de Nivel Alto.
    
    Args:
        source: SourceInput a evaluar
        
    Returns:
        SourceEvaluationResult con resultado de evaluación Nivel Alto
    """
    evaluator = HighTrustEvaluator()
    return evaluator.evaluate(source)


# =============================================================================
# FASE 3: LÓGICA DE EVALUACIÓN - NIVEL MEDIO (Comunitario / Técnico)
# =============================================================================

# Foros técnicos oficiales y comunidades moderadas verificadas
# Estos son dominios base de comunidades técnicas con moderación activa
MEDIUM_TRUST_TECH_FORUMS: frozenset[str] = frozenset({
    # Stack Exchange Network (moderación comunitaria estricta)
    "stackoverflow.com",
    "stackexchange.com",
    "serverfault.com",
    "superuser.com",
    "askubuntu.com",
    "unix.stackexchange.com",
    "softwareengineering.stackexchange.com",
    "security.stackexchange.com",
    "datascience.stackexchange.com",
    "devops.stackexchange.com",
    "codereview.stackexchange.com",
    "android.stackexchange.com",
    "raspberrypi.stackexchange.com",
    "arduino.stackexchange.com",
    "salesforce.stackexchange.com",
    "sharepoint.stackexchange.com",
    "dba.stackexchange.com",
    "webmasters.stackexchange.com",
    "wordpress.stackexchange.com",
    "magento.stackexchange.com",
    "drupal.stackexchange.com",
    "joomla.stackexchange.com",
    "expressionengine.stackexchange.com",
    "craftcms.stackexchange.com",
    "sitecore.stackexchange.com",
    "kentico.stackexchange.com",
    "umbraco.stackexchange.com",
    "episerver.stackexchange.com",
    "tridion.stackexchange.com",
    "civicrm.stackexchange.com",
    "bitcoin.stackexchange.com",
    "ethereum.stackexchange.com",
    "monero.stackexchange.com",
    "stellar.stackexchange.com",
    "eosio.stackexchange.com",
    "tezos.stackexchange.com",
    "cardano.stackexchange.com",
    "polkadot.stackexchange.com",
    "cosmos.stackexchange.com",
    "solana.stackexchange.com",
    "near.stackexchange.com",
    "avalanche.stackexchange.com",
    "fantom.stackexchange.com",
    "harmony.stackexchange.com",
    "hedera.stackexchange.com",
    "algorand.stackexchange.com",
    "flow.stackexchange.com",
    "celo.stackexchange.com",
    "terra.stackexchange.com",
    "secret.stackexchange.com",
    "oasis.stackexchange.com",
    "filecoin.stackexchange.com",
    "arweave.stackexchange.com",
    "internetcomputer.stackexchange.com",
    "multiversx.stackexchange.com",
    "kadena.stackexchange.com",
    "chia.stackexchange.com",
    "nano.stackexchange.com",
    "iota.stackexchange.com",
    "hedera.stackexchange.com",
    "vechain.stackexchange.com",
    "zilliqa.stackexchange.com",
    "ontology.stackexchange.com",
    "neo.stackexchange.com",
    "qtum.stackexchange.com",
    "waves.stackexchange.com",
    "icon.stackexchange.com",
    "aeternity.stackexchange.com",
    "elrond.stackexchange.com",
    "harmony.stackexchange.com",
    "klaytn.stackexchange.com",
    "klaytn.foundation",
    
    # Foros oficiales de proyectos/lenguajes principales
    "forum.rust-lang.org",
    "users.rust-lang.org",
    "internals.rust-lang.org",
    "discuss.python.org",
    "forum.golang.org",
    "forum.deno.land",
    "community.bun.sh",
    "discuss.kotlinlang.org",
    "forum.dotnet.org",
    "community.jetbrains.com",
    "forums.swift.org",
    "forums.developer.apple.com",
    "developercommunity.visualstudio.com",
    "community.oracle.com",
    "community.sap.com",
    "community.ibm.com",
    "community.redhat.com",
    "access.redhat.com",
    "forums.docker.com",
    "discuss.kubernetes.io",
    "forum.cncf.io",
    "discuss.istio.io",
    "discuss.prometheus.io",
    "community.grafana.com",
    "forum.elastic.co",
    "discuss.mongodb.com",
    "community.couchbase.com",
    "community.datastax.com",
    "community.neo4j.com",
    "discuss.redis.io",
    "community.confluent.io",
    "forum.cloudera.com",
    "community.hortonworks.com",
    "discuss.pivotal.io",
    "community.vmware.com",
    "forums.vmware.com",
    "community.broadcom.com",
    
    # Foros de frameworks/librerías populares
    "discuss.reactjs.org",
    "github.com/facebook/react/discussions",
    "vuejs.org/forum",
    "forum.svelte.dev",
    "discuss.nextjs.org",
    "github.com/vercel/next.js/discussions",
    "remix.run/discussions",
    "github.com/remix-run/remix/discussions",
    "astro.build/chat",
    "github.com/withastro/astro/discussions",
    "discuss.gatsbyjs.org",
    "github.com/gatsbyjs/gatsby/discussions",
    "discuss.nuxtjs.org",
    "github.com/nuxt/nuxt/discussions",
    "angular.io/community",
    "github.com/angular/angular/discussions",
    "emberjs.com/community",
    "github.com/emberjs/ember.js/discussions",
    "backbonejs.org/community",
    "github.com/jashkenas/backbone/discussions",
    "meteor.com/forums",
    "github.com/meteor/meteor/discussions",
    "discuss.meteor.com",
    "community.meteor.com",
    
    # Foros de IA/ML
    "discuss.huggingface.co",
    "github.com/huggingface/transformers/discussions",
    "forum.fast.ai",
    "discuss.pytorch.org",
    "github.com/pytorch/pytorch/discussions",
    "discuss.tensorflow.org",
    "github.com/tensorflow/tensorflow/discussions",
    "discuss.jax.dev",
    "github.com/google/jax/discussions",
    "discuss.ray.io",
    "github.com/ray-project/ray/discussions",
    "forum.mlflow.org",
    "github.com/mlflow/mlflow/discussions",
    "discuss.lightning.ai",
    "github.com/Lightning-AI/lightning/discussions",
    "community.wandb.ai",
    "github.com/wandb/wandb/discussions",
    "forum.clear.ml",
    "github.com/allegro/clearml/discussions",
    "discuss.dvc.org",
    "github.com/iterative/dvc/discussions",
    
    # Foros de infraestructura/DevOps
    "discuss.hashicorp.com",
    "github.com/hashicorp/terraform/discussions",
    "community.pulumi.com",
    "github.com/pulumi/pulumi/discussions",
    "forum.ansible.com",
    "github.com/ansible/ansible/discussions",
    "community.chef.io",
    "github.com/chef/chef/discussions",
    "discuss.puppet.com",
    "github.com/puppetlabs/puppet/discussions",
    "community.saltproject.io",
    "github.com/saltstack/salt/discussions",
    "forum.terraform.io",
    "github.com/gruntwork-io/terragrunt/discussions",
    "community.spacelift.io",
    "github.com/spacelift-io/spacelift/discussions",
    "discuss.env0.com",
    "github.com/env0/env0/discussions",
    "community.terraform-cloud.io",
    
    # Comunidades de bases de datos
    "postgresql.org/list",
    "www.postgresql.org/list",
    "lists.postgresql.org",
    "mysql.com/community",
    "forums.mysql.com",
    "mariadb.org/community",
    "forum.mariadb.org",
    "community.mongodb.com",
    "developer.mongodb.com/community",
    "redis.io/community",
    "forum.redis.io",
    "cassandra.apache.org/community",
    "community.datastax.com",
    "cockroachdb.com/community",
    "forum.cockroachdb.com",
    "timescaledb.com/community",
    "forum.timescaledb.com",
    "clickhouse.com/community",
    "discuss.clickhouse.com",
    "questdb.io/community",
    "github.com/questdb/questdb/discussions",
    "influxdata.com/community",
    "community.influxdata.com",
    "questdb.io/community",
    "neo4j.com/community",
    "community.neo4j.com",
    "arangodb.com/community",
    "forum.arangodb.com",
    "couchbase.com/community",
    "forums.couchbase.com",
    "scylladb.com/community",
    "forum.scylladb.com",
    "singlestore.com/community",
    "forum.singlestore.com",
    "materialize.com/community",
    "github.com/MaterializeInc/materialize/discussions",
    "risingwave.com/community",
    "github.com/risingwavelabs/risingwave/discussions",
    
    # Comunidades de mensajería/streaming
    "kafka.apache.org/community",
    "community.confluent.io",
    "pulsar.apache.org/community",
    "discuss.streamnative.io",
    "github.com/streamnative/pulsar/discussions",
    "nats.io/community",
    "github.com/nats-io/nats.go/discussions",
    "rabbitmq.com/community",
    "github.com/rabbitmq/rabbitmq-server/discussions",
    "zeromq.org/community",
    "github.com/zeromq/libzmq/discussions",
    "crossbar.io/community",
    "github.com/crossbario/autobahn-python/discussions",
    
    # Comunidades de observabilidad
    "community.datadoghq.com",
    "discuss.newrelic.com",
    "discuss.elastic.co",
    "community.grafana.com",
    "forum.prometheus.io",
    "community.splunk.com",
    "answers.splunk.com",
    "community.sumologic.com",
    "discuss.lightstep.com",
    "community.honeycomb.io",
    "discuss.thundra.io",
    "community.rookout.com",
    "github.com/rookout/rookout/discussions",
    "community.lumigo.io",
    "github.com/lumigo/lumigo-discussions/discussions",
    "community.epsagon.com",
    "github.com/epsagon/epsagon/discussions",
    "community.baselime.io",
    "github.com/baselime/discussions/discussions",
    
    # Comunidades de seguridad
    "community.snyk.io",
    "github.com/snyk/snyk/discussions",
    "forum.aquasec.com",
    "github.com/aquasecurity/trivy/discussions",
    "community.prismacloud.io",
    "github.com/paloaltonetworks/prisma-cloud/discussions",
    "community.wiz.io",
    "github.com/wiz-labs/wiz/discussions",
    "community.bridgecrew.io",
    "github.com/bridgecrewio/bridgecrew/discussions",
    "community.checkmarx.com",
    "github.com/checkmarx/checkmarx/discussions",
    "community.sonarqube.org",
    "github.com/SonarSource/sonarqube/discussions",
    "community.veracode.com",
    "github.com/veracode/veracode/discussions",
    "community.whitesourcesoftware.com",
    "github.com/whitesource/unified-agent/discussions",
    "community.fortify.com",
    "github.com/fortify/fortify/discussions",
    "community.synopsys.com",
    "github.com/blackducksoftware/blackduck/discussions",
    
    # Foros de cloud providers
    "community.aws.amazon.com",
    "repost.aws",
    "cloud.google.com/community",
    "community.cloud.oracle.com",
    "community.ibm.com",
    "techcommunity.microsoft.com",
    "community.digitalocean.com",
    "community.linode.com",
    "community.vultr.com",
    "community.hetzner.com",
    "community.scaleway.com",
    "community.upcloud.com",
    "community.cloudflare.com",
    "community.fastly.com",
    "community.akamai.com",
    "community.netlify.com",
    "community.vercel.com",
    "community.render.com",
    "community.railway.app",
    "community.fly.io",
    "community.planetscale.com",
    "community.supabase.com",
    "community.turso.tech",
    "community.neon.tech",
    "community.xata.io",
    "community.tinybird.co",
    "community.motherduck.com",
    "community.duckdb.org",
    "github.com/duckdb/duckdb/discussions",
    "community.apache.org",
    "discuss.apache.org",
    "lists.apache.org",
    "mail-archives.apache.org",
})


# Repositorios de código moderados / plataformas de desarrollo con gobernanza
MEDIUM_TRUST_CODE_REPOS: frozenset[str] = frozenset({
    # GitHub / GitLab - organizaciones verificadas / proyectos con gobernanza
    # Nota: La evaluación real debería verificar organización/proyecto específico
    # Aquí listamos dominios base; la lógica verifica subdominios/paths
    "github.com",
    "github.io",
    "github.dev",
    "githubusercontent.com",
    "gitlab.com",
    "gitlab.io",
    "gitlab.dev",
    "bitbucket.org",
    "sourceforge.net",
    "codeberg.org",
    "sr.ht",
    "git.sr.ht",
    "hg.sr.ht",
    "lists.sr.ht",
    "man.sr.ht",
    "dispatch.sr.ht",
    "builds.sr.ht",
    "gitea.com",
    "gitea.io",
    "notabug.org",
    "framagit.org",
    "git.framasoft.org",
    "github.gnome.org",
    "gitlab.gnome.org",
    "github.kde.org",
    "invent.kde.org",
    "git.kde.org",
    "gitlab.freedesktop.org",
    "gitlab.freedesktop.org",
    "anongit.freedesktop.org",
    "cgit.freedesktop.org",
    "git.savannah.gnu.org",
    "git.savannah.nongnu.org",
    "salsa.debian.org",
    "git.debian.org",
    "anonscm.debian.org",
    "git.archlinux.org",
    "gitlab.archlinux.org",
    "git.fedoraproject.org",
    "src.fedoraproject.org",
    "gitlab.com/redhat",
    "github.com/openshift",
    "github.com/kubernetes",
    "github.com/cncf",
    "github.com/google",
    "github.com/microsoft",
    "github.com/facebook",
    "github.com/apache",
    "github.com/facebookresearch",
    "github.com/pytorch",
    "github.com/tensorflow",
    "github.com/huggingface",
    "github.com/ray-project",
    "github.com/langchain-ai",
    "github.com/ansible",
    "github.com/hashicorp",
    "github.com/pulumi",
    "github.com/grpc",
    "github.com/envoyproxy",
    "github.com/istio",
    "github.com/kubernetes-sigs",
    "github.com/knative",
    "github.com/tektoncd",
    "github.com/argoproj",
    "github.com/fluxcd",
    "github.com/crossplane",
    "github.com/jetstack",
    "github.com/cert-manager",
    "github.com/prometheus",
    "github.com/grafana",
    "github.com/elastic",
    "github.com/mongodb",
    "github.com/redis",
    "github.com/cockroachdb",
    "github.com/timescale",
    "github.com/clickhouse",
    "github.com/questdb",
    "github.com/influxdata",
    "github.com/neo4j",
    "github.com/arangodb",
    "github.com/couchbase",
    "github.com/scylladb",
    "github.com/singlestore",
    "github.com/materializeinc",
    "github.com/risingwavelabs",
    "github.com/confluentinc",
    "github.com/apache/kafka",
    "github.com/apache/pulsar",
    "github.com/nats-io",
    "github.com/rabbitmq",
    "github.com/zeromq",
    "github.com/crossbario",
    "github.com/datadog",
    "github.com/newrelic",
    "github.com/elastic",
    "github.com/grafana",
    "github.com/prometheus",
    "github.com/splunk",
    "github.com/honeycombio",
    "github.com/thundra-io",
    "github.com/rookout",
    "github.com/lumigo",
    "github.com/epsagon",
    "github.com/baselime",
    "github.com/snyk",
    "github.com/aquasecurity",
    "github.com/paloaltonetworks",
    "github.com/wiz-labs",
    "github.com/bridgecrewio",
    "github.com/checkmarx",
    "github.com/sonarsource",
    "github.com/veracode",
    "github.com/whitesource",
    "github.com/fortify",
    "github.com/blackducksoftware",
})


# Patrones para detectar repositorios con gobernanza (org/proyecto conocido)
# Estos patrones se aplican sobre la URL completa o path
GOVERNED_REPO_PATTERNS: tuple[re.Pattern, ...] = (
    # GitHub/GitLab organizaciones oficiales conocidas
    re.compile(r"github\.com/(apache|facebook|google|microsoft|pytorch|tensorflow|huggingface|ray-project|langchain-ai|ansible|hashicorp|pulumi|grpc|envoyproxy|istio|kubernetes|kubernetes-sigs|knative|tektoncd|argoproj|fluxcd|crossplane|jetstack|cert-manager|prometheus|grafana|elastic|mongodb|redis| cockroachdb|timescale|clickhouse|questdb|influxdata|neo4j|arangodb|couchbase|scylladb|singlestore|materializeinc|risingwavelabs|confluentinc|apache/kafka|apache/pulsar|nats-io|rabbitmq|zeromq|crossbario|datadog|newrelic|honeycombio|thundra-io|rookout|lumigo|epsagon|baselime|snyk|aquasecurity|paloaltonetworks|wiz-labs|bridgecrewio|checkmarx|sonarsource|veracode|whitesource|fortify|blackducksoftware)/"),
    re.compile(r"gitlab\.com/(apache|freedesktop|gnome|kde|debian|archlinux|fedoraproject|redhat|openshift|cncf)/"),
    
    # Patrones de repos con gobernanza clara (mantenido por org reconocida)
    re.compile(r"github\.com/[a-z0-9-]+/(linux|kubernetes|tensorflow|pytorch|transformers|ray|langchain|ansible|terraform|pulumi|grpc|envoy|istio|prometheus|grafana|loki|tempo|mimir|thanos|cortex|alertmanager|blackbox-exporter|node-exporter|cadvisor|kube-state-metrics|metrics-server|kube-prometheus|kube-prometheus-stack|prometheus-operator|kubelet|kubectl|kubeadm|kube-apiserver|kube-controller-manager|kube-scheduler|kube-proxy|kube-dns|coredns|etcd|containerd|cri-o|runc|gvisor|kata-containers|firecracker|cloud-hypervisor|qemu|libvirt|virt-manager|ovirt|libguestfs|spice|virtio|vhost|vhost-user|vhost-vsock|vhost-scsi|vhost-net|vhost-blk|vhost-gpu|vhost-crypto|vhost-user-gpu|vhost-user-blk|vhost-user-net|vhost-user-scsi|vhost-user-vsock|vhost-user-crypto|vhost-user-fs|vhost-user-console|vhost-user-input|vhost-user-video|vhost-user-audio|vhost-user-baloon|vhost-user-rng|vhost-user-balloon)/"),
)


def _is_medium_trust_tech_forum(domain: str) -> bool:
    """Verifica si el dominio es un foro técnico oficial conocido."""
    domain_lower = domain.lower()
    base_domain = _extract_base_domain(domain_lower)
    return domain_lower in MEDIUM_TRUST_TECH_FORUMS or base_domain in MEDIUM_TRUST_TECH_FORUMS


def _is_medium_trust_code_repo(domain: str) -> bool:
    """Verifica si el dominio es una plataforma de repositorios de código moderados."""
    domain_lower = domain.lower()
    base_domain = _extract_base_domain(domain_lower)
    return domain_lower in MEDIUM_TRUST_CODE_REPOS or base_domain in MEDIUM_TRUST_CODE_REPOS


def _matches_governed_repo_pattern(url: str) -> bool:
    """Verifica si la URL coincide con patrones de repos con gobernanza conocida."""
    url_lower = url.lower()
    return any(pattern.search(url_lower) for pattern in GOVERNED_REPO_PATTERNS)


def _calculate_medium_weight(source: SourceInput) -> float:
    """
    Calcula peso dinámico para Nivel Medio (0.6 - 0.7) basado en señales de calidad.
    Factores: longitud contenido, presencia de código, respuestas aceptadas, votos, etc.
    """
    base_weight = 0.6  # Peso base mínimo
    max_weight = 0.7   # Peso máximo
    
    # Factores de ajuste (heurísticos simples)
    adjustments = 0.0
    
    # Contenido sustancial
    if source.content_length and source.content_length > 500:
        adjustments += 0.03
    elif source.content_length and source.content_length > 2000:
        adjustments += 0.05
    
    # Título técnico (contiene términos técnicos comunes)
    if source.title:
        tech_terms = {"error", "exception", "bug", "issue", "fix", "patch", "pr", "merge", 
                      "commit", "branch", "rebase", "cherry-pick", "config", "deploy", 
                      "build", "compile", "runtime", "dependency", "library", "framework",
                      "api", "sdk", "cli", "daemon", "service", "microservice", "container",
                      "kubernetes", "docker", "helm", "istio", "prometheus", "grafana"}
        title_lower = source.title.lower()
        if any(term in title_lower for term in tech_terms):
            adjustments += 0.02
    
    # Preview de contenido técnico
    if source.content_preview:
        preview_lower = source.content_preview.lower()
        code_indicators = ["```", "def ", "function ", "class ", "import ", "from ", 
                          "const ", "let ", "var ", "fn ", "pub ", "struct ", "impl ",
                          "interface ", "type ", "export ", "async ", "await ", "try ",
                          "catch ", "finally ", "throw ", "raise ", "except ", "with ",
                          "select ", "insert ", "update ", "delete ", "create ", "drop ",
                          "alter ", "index ", "join ", "where ", "group by", "order by"]
        if any(ind in preview_lower for ind in code_indicators):
            adjustments += 0.03
    
    # Pista de categoría técnica
    if source.source_category_hint in (SourceCategory.TECHNICAL_REPO, SourceCategory.OFFICIAL_FORUM):
        adjustments += 0.02
    
    # Aplicar ajustes con límite
    final_weight = min(base_weight + adjustments, max_weight)
    return round(final_weight, 2)


class MediumTrustEvaluationError(Exception):
    """Excepción específica para errores en evaluación de Nivel Medio."""
    pass


class MediumTrustEvaluator:
    """
    Evaluador especializado para fuentes de Nivel Medio (Comunitario / Técnico).
    
    Responsabilidad única: Determinar si una fuente califica como Nivel Medio
    basándose en foros técnicos oficiales, repositorios con gobernanza y comunidades moderadas.
    
    Características:
    - Peso dinámico 0.6 - 0.7 según señales de calidad
    - Validación cruzada OBLIGATORIA (cross_validation=True)
    - Sin paso directo (direct_pass=False)
    - Sin saneamiento estricto (eso es Nivel Bajo)
    - Trazabilidad completa de reglas coincidentes
    """
    
    VERSION = "2.0.0"
    
    def __init__(self) -> None:
        self._config = TRUST_LEVEL_CONFIGS[TrustLevel.MEDIUM]
    
    def evaluate(self, source: SourceInput) -> SourceEvaluationResult:
        """
        Evalúa una fuente para determinar si califica como Nivel Medio.
        
        Args:
            source: SourceInput con url, domain y metadatos opcionales
            
        Returns:
            SourceEvaluationResult con clasificación Nivel Medio si cumple criterios,
            o resultado indicando que no califica.
        """
        matched_rules: list[str] = []
        source_category = SourceCategory.UNKNOWN
        domain = source.domain.lower().strip()
        url = str(source.url).lower().strip()
        
        if not domain:
            raise MediumTrustEvaluationError("Dominio vacío en SourceInput")
        
        # --- REGLA 1: Foros técnicos oficiales y comunidades moderadas ---
        if _is_medium_trust_tech_forum(domain):
            matched_rules.append("medium_tech_forum")
            source_category = SourceCategory.OFFICIAL_FORUM
        
        # --- REGLA 2: Repositorios de código en plataformas moderadas con gobernanza ---
        elif _is_medium_trust_code_repo(domain):
            # Verificación adicional: ¿el path sugiere un repo con gobernanza?
            if _matches_governed_repo_pattern(url):
                matched_rules.append("governed_code_repo")
                source_category = SourceCategory.TECHNICAL_REPO
            else:
                # Repo en plataforma moderada pero sin gobernanza verificada
                # Aún califica como Nivel Medio pero con peso base
                matched_rules.append("moderated_code_platform")
                source_category = SourceCategory.TECHNICAL_REPO
        
        # --- REGLA 3: Pista de categoría explícita ---
        elif source.source_category_hint in (SourceCategory.OFFICIAL_FORUM, SourceCategory.TECHNICAL_REPO):
            matched_rules.append(f"category_hint:{source.source_category_hint.value}")
            source_category = source.source_category_hint
            # NOTA: El hint ayuda pero no es suficiente solo; requerimos validación de dominio
            # Si no hay matched_rules de dominio, no califica
        
        # Si no coincidió ninguna regla de Nivel Medio, indicar que no califica
        if not matched_rules:
            return self._build_non_qualifying_result(source, domain)
        
        # Calcular peso dinámico
        assigned_weight = _calculate_medium_weight(source)
        confidence_score = min(assigned_weight + 0.1, 0.8)  # Confianza ligeramente superior al peso
        
        # Construir resultado exitoso de Nivel Medio
        now_iso = datetime.now(timezone.utc).isoformat()
        
        return SourceEvaluationResult(
            trust_level=TrustLevel.MEDIUM,
            source_category=source_category,
            evaluation_status=EvaluationStatus.CROSS_VALIDATION_REQUIRED,
            assigned_weight=assigned_weight,
            confidence_score=confidence_score,
            matched_rules=matched_rules,
            rejection_reasons=[],
            requires_cross_validation=True,   # OBLIGATORIO para Nivel Medio
            requires_strict_sanitization=False,
            direct_pass=False,
            evaluated_at=now_iso,
            evaluator_version=self.VERSION,
        )
    
    def _build_non_qualifying_result(
        self,
        source: SourceInput,
        domain: str,
    ) -> SourceEvaluationResult:
        """Construye resultado indicando que la fuente NO califica para Nivel Medio."""
        now_iso = datetime.now(timezone.utc).isoformat()
        
        return SourceEvaluationResult(
            trust_level=TrustLevel.MEDIUM,
            source_category=SourceCategory.UNKNOWN,
            evaluation_status=EvaluationStatus.REJECTED,
            assigned_weight=0.0,
            confidence_score=0.0,
            matched_rules=[],
            rejection_reasons=[f"Domain '{domain}' does not match any Medium Trust criteria (tech forum, governed repo, or moderated platform)"],
            requires_cross_validation=False,
            requires_strict_sanitization=False,
            direct_pass=False,
            evaluated_at=now_iso,
            evaluator_version=self.VERSION,
        )
    
    def qualifies_as_medium_trust(self, domain: str, url: str = "") -> bool:
        """
        Verificación rápida booleana: ¿el dominio califica como Nivel Medio?
        """
        domain_lower = domain.lower().strip()
        url_lower = url.lower().strip()
        return (
            _is_medium_trust_tech_forum(domain_lower)
            or (_is_medium_trust_code_repo(domain_lower) and (_matches_governed_repo_pattern(url_lower) or True))
        )


# Función de conveniencia para uso directo
def evaluate_medium_trust(source: SourceInput) -> SourceEvaluationResult:
    """
    Función de conveniencia para evaluar una fuente contra criterios de Nivel Medio.
    
    Args:
        source: SourceInput a evaluar
        
    Returns:
        SourceEvaluationResult con resultado de evaluación Nivel Medio
    """
    evaluator = MediumTrustEvaluator()
    return evaluator.evaluate(source)


# =============================================================================
# FASE 4: LÓGICA DE EVALUACIÓN - NIVEL BAJO (Independiente / Abierto)
# =============================================================================

# Patrones de dominios de blogs personales y plataformas de publicación abierta
# Estos son dominios base de plataformas donde cualquiera puede publicar
LOW_TRUST_BLOG_PLATFORMS: frozenset[str] = frozenset({
    # Plataformas de blogs generales
    "medium.com",
    "substack.com",
    "ghost.io",
    "ghost.org",
    "wordpress.com",
    "wordpress.org",
    "blogger.com",
    "blogspot.com",
    "tumblr.com",
    "write.as",
    "writefreely.org",
    "plume.org",
    "hablame.io",
    "dev.to",
    "dev.to",
    "hashnode.dev",
    "hashnode.com",
    "velog.io",
    "telegra.ph",
    "telegraph.io",
    "notion.site",
    "notion.so",
    "mirror.xyz",
    "paragraph.xyz",
    "substack.com",
    "buttondown.email",
    "beehiiv.com",
    "convertkit.com",
    "mailerlite.com",
    "mailchimp.com",
    "sendfox.com",
    "review.io",
    "newsletter.io",
    "patreon.com",
    "ko-fi.com",
    "buymeacoffee.com",
    "gumroad.com",
    "itch.io",
    "github.io",
    "gitlab.io",
    "bitbucket.io",
    "surge.sh",
    "netlify.app",
    "vercel.app",
    "pages.dev",
    "cloudflare.pages.dev",
    "firebaseapp.com",
    "web.app",
    "githubusercontent.com",
    "raw.githubusercontent.com",
    "gist.github.com",
    "gist.githubusercontent.com",
    "pastebin.com",
    "hastebin.com",
    "gist.github.com",
    "rentry.co",
    "rentry.org",
    "pastelink.net",
    "controlc.com",
    "dpaste.org",
    "dpaste.com",
    "ideone.com",
    "replit.com",
    "codesandbox.io",
    "codepen.io",
    "jsfiddle.net",
    "stackblitz.com",
    "replit.com",
    "glitch.me",
    "observablehq.com",
    "colab.research.google.com",
    "kaggle.com",
    "huggingface.co",
    "wandb.ai",
    "mlflow.org",
    "clear.ml",
    "dvc.org",
    "dagshub.com",
    "kaggle.io",
    "paperswithcode.com",
    "arxiv.org",
    "biorxiv.org",
    "medrxiv.org",
    "chemrxiv.org",
    "psyarxiv.com",
    "socarxiv.org",
    "edarxiv.org",
    "techrxiv.org",
    "engrxiv.org",
    "osf.io",
    "zenodo.org",
    "figshare.com",
    "dryad.org",
    "datadryad.org",
    "dataverse.harvard.edu",
    "openneuro.org",
    "gin.g-node.org",
    "neurovault.org",
    "openfmri.org",
    "neuroimaging.io",
    "brainlife.io",
    "cbrain.mcgill.ca",
    "loris.ca",
    "fcp-indi.github.io",
    "nilearn.github.io",
    "nipy.org",
    "scikit-learn.org",
    "scipy.org",
    "numpy.org",
    "pandas.pydata.org",
    "matplotlib.org",
    "seaborn.pydata.org",
    "plotly.com",
    "bokeh.org",
    "altair-viz.github.io",
    "holoviz.org",
    "panel.holoviz.org",
    "datashader.org",
    "geoviews.org",
    "hvplot.holoviz.org",
    "lumen.holoviz.org",
    "param.holoviz.org",
    "colorcet.pyviz.org",
    "ctc.pyviz.org",
    "spatialpandas.pyviz.org",
    "geopandas.org",
    "rasterio.readthedocs.io",
    "fiona.readthedocs.io",
    "shapely.readthedocs.io",
    "pyproj.readthedocs.io",
    "cartopy.readthedocs.io",
    "geemap.org",
    "earthengine.google.com",
    "planetarycomputer.microsoft.com",
    "radiantearth.org",
    "stacspec.org",
    "cog-spec.org",
    "zarr.dev",
    "xarray.pydata.org",
    "dask.org",
    "prefect.io",
    "dagster.io",
    "airflow.apache.org",
    "luigi.readthedocs.io",
    "celery.readthedocs.io",
    "rq.readthedocs.io",
    "dramatiq.io",
    "huey.readthedocs.io",
    "apscheduler.readthedocs.io",
    "schedule.readthedocs.io",
    "python-crontab.readthedocs.io",
    "croniter.readthedocs.io",
})


# Patrones para detectar dominios personales / blogs independientes
# Heurísticas: subdominios personales, TLDs personales, patrones de username
PERSONAL_DOMAIN_PATTERNS: tuple[re.Pattern, ...] = (
    # Patrones tipo username.github.io, username.gitlab.io, etc.
    re.compile(r"^[a-z0-9-]+\.(github|gitlab|bitbucket|netlify|vercel|cloudflare|firebase|surge|pages|raw)\.(io|app|dev|com|net|org)$"),
    # Patrones tipo username.medium.com, username.substack.com
    re.compile(r"^[a-z0-9-]+\.(medium|substack|ghost|hashnode|dev|velog|write|telegra|notion|mirror|paragraph)\.(com|io|dev|xyz)$"),
    # Dominios personales con TLDs comunes (.me, .io, .dev, .blog, .site, .online, .space, .tech, .xyz)
    re.compile(r"^[a-z0-9-]+\.(me|io|dev|blog|site|online|space|tech|xyz|app|page|link|fun|club|live|world|info|co|cc|tv|fm|am|gg|sh|ml|ga|cf|tk|top|win|bid|loan|trade|date|faith|review|accountants|science|party|cricket|racing|download|stream|gdn|men|mom|xyz|wang|club|top|win|bid|loan|trade|date|faith|review|accountants|science|party|cricket|racing|download|stream|gdn|men|mom)$"),
    # Patrones de subdominios personales comunes
    re.compile(r"^(blog|personal|home|me|www)\.[a-z0-9-]+\.(com|net|org|io|dev|me|blog|site|online|space|tech|xyz|co|cc|tv|fm|am|gg|sh)$"),
)


# Palabras clave de riesgo en contenido (para evaluación de riesgos)
RISK_KEYWORDS: frozenset[str] = frozenset({
    # Contenido promocional / spam
    "buy now", "click here", "limited time", "act now", "free trial", "discount",
    "coupon", "promo code", "affiliate", "sponsored", "advertisement", "advert",
    "make money", "get rich", "passive income", "work from home", "earn $",
    "double your", "guaranteed", "risk free", "no obligation", "cancel anytime",
    
    # Desinformación / pseudociencia
    "miracle cure", "secret remedy", "doctors hate", "they don't want you to know",
    "ancient secret", "hidden knowledge", "suppressed", "conspiracy", "cover up",
    "mainstream media lies", "wake up sheeple", "do your own research",
    
    # Contenido malicioso / phishing
    "verify your account", "update your password", "security alert", "suspended",
    "unusual activity", "confirm identity", "click to verify", "login immediately",
    
    # Contenido de baja calidad / clickbait
    "you won't believe", "shocking", "amazing trick", "one weird trick",
    "number 5 will shock", "doctors are baffled", "this simple trick",
    
    # Cripto/estafas financieras
    "airdrop", "presale", "ico", "ido", "launchpad", "guaranteed returns",
    "100x", "1000x", "moonshot", "gem", "hidden gem", "early access",
    "whale", "pump", "dump", "rug pull", "honeypot",
})


# Palabras clave de calidad positiva (para ajustar peso hacia arriba)
QUALITY_INDICATORS: frozenset[str] = frozenset({
    # Autoría / credenciales
    "author:", "by ", "written by", "phd", "md", "professor", "researcher",
    "engineer", "developer", "architect", "consultant", "expert", "specialist",
    "senior", "lead", "principal", "staff", "fellow",
    
    # Referencias / fuentes
    "source:", "reference:", "citation:", "doi:", "arxiv:", "pmid:", "isbn:",
    "according to", "study shows", "research indicates", "paper:", "report:",
    "data from", "statistics from", "survey:", "analysis:", "findings:",
    
    # Estructura técnica
    "methodology:", "abstract:", "introduction:", "conclusion:", "results:",
    "discussion:", "background:", "related work:", "future work:", "limitations:",
    "algorithm:", "implementation:", "evaluation:", "benchmark:", "experiment:",
    
    # Código / técnico
    "github.com/", "gitlab.com/", "repository:", "source code:", "implementation:",
    "docker", "kubernetes", "api", "sdk", "cli", "configuration:", "deployment:",
    
    # Transparencia
    "disclosure:", "conflict of interest:", "funding:", "acknowledgments:",
    "license:", "mit license", "apache 2.0", "gpl", "bsd", "creative commons",
})


def _is_low_trust_blog_platform(domain: str) -> bool:
    """Verifica si el dominio es una plataforma de blogs/publicación abierta conocida."""
    domain_lower = domain.lower()
    base_domain = _extract_base_domain(domain_lower)
    return domain_lower in LOW_TRUST_BLOG_PLATFORMS or base_domain in LOW_TRUST_BLOG_PLATFORMS


def _matches_personal_domain_pattern(domain: str) -> bool:
    """Verifica si el dominio coincide con patrones de dominios personales/blogs independientes."""
    domain_lower = domain.lower()
    return any(pattern.search(domain_lower) for pattern in PERSONAL_DOMAIN_PATTERNS)


def _analyze_content_risk(content_preview: Optional[str], title: Optional[str]) -> tuple[float, list[str]]:
    """
    Analiza el contenido para detectar señales de riesgo y calidad.
    
    Returns:
        Tupla (risk_score, risk_flags) donde risk_score ∈ [0.0, 1.0] (mayor = más riesgo)
        y risk_flags lista de banderas detectadas.
    """
    risk_score = 0.0
    risk_flags: list[str] = []
    
    if not content_preview and not title:
        return 0.5, ["no_content_to_analyze"]
    
    # Combinar título y preview para análisis
    full_text = " ".join(filter(None, [title or "", content_preview or ""])).lower()
    
    # Detectar palabras clave de riesgo
    risk_matches = [kw for kw in RISK_KEYWORDS if kw in full_text]
    if risk_matches:
        risk_score += min(len(risk_matches) * 0.1, 0.5)
        risk_flags.extend([f"risk_keyword:{kw}" for kw in risk_matches[:5]])
    
    # Detectar indicadores de calidad (reducen riesgo)
    quality_matches = [kw for kw in QUALITY_INDICATORS if kw in full_text]
    if quality_matches:
        risk_score -= min(len(quality_matches) * 0.05, 0.3)
        risk_flags.extend([f"quality_indicator:{kw}" for kw in quality_matches[:5]])
    
    # Longitud muy corta = mayor riesgo
    if len(full_text) < 100:
        risk_score += 0.2
        risk_flags.append("very_short_content")
    elif len(full_text) < 500:
        risk_score += 0.1
        risk_flags.append("short_content")
    
    # Normalizar score a [0.0, 1.0]
    risk_score = max(0.0, min(1.0, risk_score))
    
    return risk_score, risk_flags


def _calculate_low_weight(source: SourceInput, risk_score: float) -> float:
    """
    Calcula peso para Nivel Bajo (0.0 - 0.5) basado en riesgo y señales de calidad.
    Peso base 0.3, reducido por riesgo, aumentado por calidad.
    """
    base_weight = 0.3
    max_weight = 0.5
    min_weight = 0.0
    
    # Penalizar por riesgo
    risk_penalty = risk_score * 0.3  # Hasta -0.3
    
    # Bonificar por contenido sustancial
    content_bonus = 0.0
    if source.content_length:
        if source.content_length > 5000:
            content_bonus = 0.15
        elif source.content_length > 2000:
            content_bonus = 0.1
        elif source.content_length > 500:
            content_bonus = 0.05
    
    # Bonificar por categoría hint técnica
    category_bonus = 0.0
    if source.source_category_hint in (SourceCategory.INDEPENDENT_BLOG, SourceCategory.OPEN_SOURCE):
        category_bonus = 0.02
    
    final_weight = base_weight - risk_penalty + content_bonus + category_bonus
    return round(max(min_weight, min(max_weight, final_weight)), 2)


class LowTrustEvaluationError(Exception):
    """Excepción específica para errores en evaluación de Nivel Bajo."""
    pass


class LowTrustEvaluator:
    """
    Evaluador especializado para fuentes de Nivel Bajo (Independiente / Abierto).
    
    Responsabilidad única: Evaluar blogs personales, plataformas abiertas y fuentes
    no verificadas, aplicando saneamiento estricto y evaluación de riesgos obligatoria.
    
    Características:
    - Peso dinámico 0.0 - 0.5 según evaluación de riesgos
    - Saneamiento estricto OBLIGATORIO (requires_strict_sanitization=True)
    - Evaluación de riesgos integrada (risk_score, risk_flags)
    - Sin paso directo (direct_pass=False)
    - Sin validación cruzada (eso es Nivel Medio)
    - Trazabilidad completa de reglas y riesgos detectados
    """
    
    VERSION = "2.0.0"
    
    def __init__(self) -> None:
        self._config = TRUST_LEVEL_CONFIGS[TrustLevel.LOW]
    
    def evaluate(self, source: SourceInput) -> SourceEvaluationResult:
        """
        Evalúa una fuente para determinar si califica como Nivel Bajo.
        
        Nivel Bajo es el "captura todo" para fuentes que no califican en Alto ni Medio.
        Cualquier fuente llega aquí si no fue clasificada antes.
        
        Args:
            source: SourceInput con url, domain y metadatos opcionales
            
        Returns:
            SourceEvaluationResult con clasificación Nivel Bajo,
            siempre con requires_strict_sanitization=True
        """
        matched_rules: list[str] = []
        risk_flags: list[str] = []
        source_category = SourceCategory.UNKNOWN
        domain = source.domain.lower().strip()
        
        if not domain:
            raise LowTrustEvaluationError("Dominio vacío en SourceInput")
        
        # --- REGLA 1: Plataformas de blogs/publicación abierta conocidas ---
        if _is_low_trust_blog_platform(domain):
            matched_rules.append("low_blog_platform")
            source_category = SourceCategory.INDEPENDENT_BLOG
        
        # --- REGLA 2: Patrones de dominios personales/independientes ---
        elif _matches_personal_domain_pattern(domain):
            matched_rules.append("personal_domain_pattern")
            source_category = SourceCategory.INDEPENDENT_BLOG
        
        # --- REGLA 3: Captura todo - cualquier otro dominio no clasificado ---
        else:
            matched_rules.append("unclassified_domain_fallback")
            source_category = SourceCategory.OPEN_SOURCE
        
        # --- REGLA 4: Pista de categoría explícita ---
        if source.source_category_hint in (SourceCategory.INDEPENDENT_BLOG, SourceCategory.OPEN_SOURCE):
            if "category_hint" not in " ".join(matched_rules):
                matched_rules.append(f"category_hint:{source.source_category_hint.value}")
            source_category = source.source_category_hint
        
        # Análisis de riesgo obligatorio para Nivel Bajo
        risk_score, content_risk_flags = _analyze_content_risk(source.content_preview, source.title)
        risk_flags.extend(content_risk_flags)
        
        # Calcular peso basado en riesgo
        assigned_weight = _calculate_low_weight(source, risk_score)
        confidence_score = max(0.1, 0.5 - risk_score * 0.4)  # Confianza inversa al riesgo
        
        # Construir resultado de Nivel Bajo
        now_iso = datetime.now(timezone.utc).isoformat()
        
        return SourceEvaluationResult(
            trust_level=TrustLevel.LOW,
            source_category=source_category,
            evaluation_status=EvaluationStatus.STRICT_SANITIZATION,
            assigned_weight=assigned_weight,
            confidence_score=confidence_score,
            matched_rules=matched_rules,
            rejection_reasons=[],  # Nivel Bajo no rechaza; solo flaggea riesgos
            requires_cross_validation=False,
            requires_strict_sanitization=True,  # OBLIGATORIO para Nivel Bajo
            direct_pass=False,
            evaluated_at=now_iso,
            evaluator_version=self.VERSION,
        )
    
    def get_risk_assessment(self, source: SourceInput) -> dict:
        """
        Obtiene evaluación de riesgos detallada sin construir resultado completo.
        Útil para inspección previa.
        """
        domain = source.domain.lower().strip()
        risk_score, risk_flags = _analyze_content_risk(source.content_preview, source.title)
        assigned_weight = _calculate_low_weight(source, risk_score)
        
        return {
            "domain": domain,
            "risk_score": risk_score,
            "risk_level": "high" if risk_score > 0.6 else "medium" if risk_score > 0.3 else "low",
            "risk_flags": risk_flags,
            "estimated_weight": assigned_weight,
            "requires_strict_sanitization": True,
            "platform_type": (
                "blog_platform" if _is_low_trust_blog_platform(domain)
                else "personal_domain" if _matches_personal_domain_pattern(domain)
                else "unclassified"
            ),
        }


# Función de conveniencia para uso directo
def evaluate_low_trust(source: SourceInput) -> SourceEvaluationResult:
    """
    Función de conveniencia para evaluar una fuente contra criterios de Nivel Bajo.
    
    Args:
        source: SourceInput a evaluar
        
    Returns:
        SourceEvaluationResult con resultado de evaluación Nivel Bajo
        (siempre con requires_strict_sanitization=True)
    """
    evaluator = LowTrustEvaluator()
    return evaluator.evaluate(source)


# =============================================================================
# FASE 5: INTEGRACIÓN FINAL - ORQUESTADOR UNIFICADO Y PIPELINE
# =============================================================================

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nexus_root.executor import ResultadoItem, ResultadoBusqueda
    from core.reasoning_engine import MotorRazonamientoSuperior, PremisaLogica


class SourceEvaluationOrchestrator:
    """
    Orquestador unificado de evaluación de fuentes con arquitectura jerárquica de tres niveles.
    
    Responsabilidades:
    1. Ejecuta evaluación en cascada: Alto → Medio → Baja (short-circuit en primera coincidencia)
    2. Procesa resultados de búsqueda externa (ResultadoItem/ResultadoBusqueda) en lote
    3. Genera metadatos de confianza agregados para el motor de razonamiento
    4. Proporciona adaptadores para NexusRouter y ExternalToolExecutor
    5. Exporta premisas ponderadas por confianza al MotorRazonamientoSuperior
    
    Diseño:
    - Stateless: cada evaluación es pura y determinista
    - Inyectable: se usa como dependencia en NexusRouter/Executor
    - Trazabilidad completa: cada decisión registra nivel, reglas, pesos
    """
    
    VERSION = "5.0.0"
    
    def __init__(
        self,
        high_evaluator: Optional["HighTrustEvaluator"] = None,
        medium_evaluator: Optional["MediumTrustEvaluator"] = None,
        low_evaluator: Optional["LowTrustEvaluator"] = None,
    ) -> None:
        """
        Inicializa el orquestador con evaluadores inyectados (para testing/mocking).
        
        Args:
            high_evaluator: Evaluador Nivel Alto (default: nuevo HighTrustEvaluator)
            medium_evaluator: Evaluador Nivel Medio (default: nuevo MediumTrustEvaluator)
            low_evaluator: Evaluador Nivel Bajo (default: nuevo LowTrustEvaluator)
        """
        self.high = high_evaluator or HighTrustEvaluator()
        self.medium = medium_evaluator or MediumTrustEvaluator()
        self.low = low_evaluator or LowTrustEvaluator()
        
        # Caché de evaluaciones recientes para performance (opcional, thread-unsafe)
        self._cache: dict[str, SourceEvaluationResult] = {}
        self._cache_enabled = True
        self._max_cache_size = 1000
    
    def evaluate_source(self, source: SourceInput) -> SourceEvaluationResult:
        """
        Evalúa una única fuente usando la jerarquía de tres niveles.
        
        Flujo:
        1. Intenta Nivel Alto (institucional/verificado) → si califica, retorna (peso 1.0, direct_pass)
        2. Intenta Nivel Medio (comunitario/técnico) → si califica, retorna (peso 0.6-0.7, cross_validation)
        3. Nivel Bajo (independiente/abierto) → siempre retorna (peso 0.0-0.5, strict_sanitization)
        
        Args:
            source: SourceInput con url, domain y metadatos
            
        Returns:
            SourceEvaluationResult con la clasificación final
        """
        # Generar clave de caché
        cache_key = f"{source.domain}:{source.url}"
        
        if self._cache_enabled and cache_key in self._cache:
            cached = self._cache[cache_key]
            # Agregar metadato de cache hit
            cached.matched_rules = cached.matched_rules + ["cache_hit"]
            return cached
        
        # --- NIVEL 1: ALTO (Institucional / Verificado) ---
        result_high = self.high.evaluate(source)
        if result_high.evaluation_status == EvaluationStatus.DIRECT_PASS:
            if self._cache_enabled:
                self._cache_result(cache_key, result_high)
            return result_high
        
        # --- NIVEL 2: MEDIO (Comunitario / Técnico) ---
        result_medium = self.medium.evaluate(source)
        if result_medium.evaluation_status == EvaluationStatus.CROSS_VALIDATION_REQUIRED:
            if self._cache_enabled:
                self._cache_result(cache_key, result_medium)
            return result_medium
        
        # --- NIVEL 3: BAJO (Independiente / Abierto) ---
        # Nivel Bajo es catch-all: siempre retorna un resultado (no rechaza)
        result_low = self.low.evaluate(source)
        if self._cache_enabled:
            self._cache_result(cache_key, result_low)
        return result_low
    
    def _cache_result(self, key: str, result: SourceEvaluationResult) -> None:
        """Almacena resultado en caché con límite de tamaño."""
        if len(self._cache) >= self._max_cache_size:
            # Simple FIFO eviction (primer elemento)
            first_key = next(iter(self._cache))
            del self._cache[first_key]
        self._cache[key] = result
    
    def evaluate_batch(self, sources: list[SourceInput]) -> list[SourceEvaluationResult]:
        """
        Evalúa múltiples fuentes en lote (para resultados de búsqueda).
        
        Args:
            sources: Lista de SourceInput
            
        Returns:
            Lista de SourceEvaluationResult en el mismo orden
        """
        return [self.evaluate_source(s) for s in sources]
    
    def evaluate_search_results(
        self, 
        search_result: "ResultadoBusqueda",
        query: str = ""
    ) -> "ResultadoBusqueda":
        """
        Evalúa todos los resultados de una búsqueda externa y enriquece con metadatos de confianza.
        
        Args:
            search_result: ResultadoBusqueda del ExternalToolExecutor
            query: Query original (para metadatos)
            
        Returns:
            ResultadoBusqueda enriquecido con evaluación de confianza por fuente
        """
        if not search_result.exito or not search_result.resultados:
            return search_result
        
        # Convertir ResultadoItem a SourceInput para evaluación
        sources = []
        for item in search_result.resultados:
            domain = self._extract_domain(item.url)
            source = SourceInput(
                url=item.url,
                domain=domain,
                title=item.titulo,
                content_preview=item.snippet,
                content_length=len(item.contenido_completo) if item.contenido_completo else None,
            )
            sources.append(source)
        
        # Evaluar en lote
        evaluations = self.evaluate_batch(sources)
        
        # Enriquecer cada ResultadoItem con metadatos de confianza
        enriched_results = []
        for item, evaluation in zip(search_result.resultados, evaluations):
            # Agregar metadatos de confianza al item
            item.metadatos_extra = item.metadatos_extra or {}
            item.metadatos_extra["trust_evaluation"] = {
                "trust_level": evaluation.trust_level.value,
                "source_category": evaluation.source_category.value,
                "evaluation_status": evaluation.evaluation_status.value,
                "assigned_weight": evaluation.assigned_weight,
                "confidence_score": evaluation.confidence_score,
                "matched_rules": evaluation.matched_rules,
                "requires_cross_validation": evaluation.requires_cross_validation,
                "requires_strict_sanitization": evaluation.requires_strict_sanitization,
                "direct_pass": evaluation.direct_pass,
                "evaluated_at": evaluation.evaluated_at,
            }
            enriched_results.append(item)
        
        # Calcular métricas agregadas de confianza para el resultado completo
        aggregate = self._calculate_aggregate_trust(evaluations)
        
        # Retornar resultado enriquecido
        return ResultadoBusqueda(
            exito=search_result.exito,
            query_original=search_result.query_original,
            sintesis=search_result.sintesis,
            resultados=enriched_results,
            fuente=search_result.fuente,
            metadatos={
                **search_result.metadatos,
                "trust_aggregate": aggregate,
                "trust_orchestrator_version": self.VERSION,
            },
            error=search_result.error,
            timestamp=search_result.timestamp,
        )
    
    def _calculate_aggregate_trust(self, evaluations: list[SourceEvaluationResult]) -> dict:
        """Calcula métricas agregadas de confianza para un conjunto de evaluaciones."""
        if not evaluations:
            return {
                "avg_weight": 0.0,
                "avg_confidence": 0.0,
                "high_trust_count": 0,
                "medium_trust_count": 0,
                "low_trust_count": 0,
                "direct_pass_count": 0,
                "requires_cross_validation_count": 0,
                "requires_strict_sanitization_count": 0,
                "dominant_level": "none",
                "overall_score": 0.0,
            }
        
        high_count = sum(1 for e in evaluations if e.trust_level == TrustLevel.HIGH)
        medium_count = sum(1 for e in evaluations if e.trust_level == TrustLevel.MEDIUM)
        low_count = sum(1 for e in evaluations if e.trust_level == TrustLevel.LOW)
        
        direct_pass = sum(1 for e in evaluations if e.direct_pass)
        cross_val = sum(1 for e in evaluations if e.requires_cross_validation)
        strict_san = sum(1 for e in evaluations if e.requires_strict_sanitization)
        
        avg_weight = sum(e.assigned_weight for e in evaluations) / len(evaluations)
        avg_confidence = sum(e.confidence_score for e in evaluations) / len(evaluations)
        
        # Nivel dominante
        if high_count >= medium_count and high_count >= low_count:
            dominant = "alto"
        elif medium_count >= low_count:
            dominant = "medio"
        else:
            dominant = "bajo"
        
        # Score general ponderado por confianza
        overall_score = (
            high_count * 1.0 + 
            medium_count * 0.65 + 
            low_count * 0.3
        ) / len(evaluations) if evaluations else 0.0
        
        return {
            "avg_weight": round(avg_weight, 3),
            "avg_confidence": round(avg_confidence, 3),
            "high_trust_count": high_count,
            "medium_trust_count": medium_count,
            "low_trust_count": low_count,
            "direct_pass_count": direct_pass,
            "requires_cross_validation_count": cross_val,
            "requires_strict_sanitization_count": strict_san,
            "dominant_level": dominant,
            "overall_score": round(overall_score, 3),
            "total_sources": len(evaluations),
        }
    
    def _extract_domain(self, url: str) -> str:
        """Extrae dominio de una URL."""
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc.lower().replace("www.", "")
        except Exception:
            return "unknown"
    
    # ============================================================
    # ADAPTADORES PARA INTEGRACIÓN CON PIPELINE EXISTENTE
    # ============================================================
    
    def adapt_for_nexus_router(
        self, 
        search_result: "ResultadoBusqueda"
    ) -> dict:
        """
        Adapta resultado de búsqueda evaluado para el formato que espera NexusRouter.
        
        NexusRouter usa _evaluar_resultado_externo que retorna dict con nivel_confianza.
        Esta función convierte nuestra evaluación granular al formato compatible.
        
        Args:
            search_result: ResultadoBusqueda ya evaluado con trust_evaluation en metadatos_extra
            
        Returns:
            Dict compatible con evaluación de NexusRouter (nivel_confianza, score_final, etc.)
        """
        if not search_result.resultados:
            return {
                "nivel_confianza": "RECHAZO_CRITICO",
                "score_final": 0.0,
                "aprobado": False,
                "accion": "BLOQUEAR - Sin resultados",
            }
        
        # Extraer evaluaciones de confianza de los items
        evaluations = []
        for item in search_result.resultados:
            trust_eval = item.metadatos_extra.get("trust_evaluation", {})
            if trust_eval:
                evaluations.append(trust_eval)
        
        if not evaluations:
            # Fallback: evaluar rápidamente
            return {
                "nivel_confianza": "CONFIANZA_BAJA",
                "score_final": 0.3,
                "aprobado": True,
                "accion": "PROCESAR_CON_ADVERTENCIA_FUERTE - Sin evaluación granular disponible",
            }
        
        # Calcular score agregado ponderado por relevancia del resultado
        total_weight = 0.0
        weighted_score = 0.0
        
        for item, eval_data in zip(search_result.resultados, evaluations):
            weight = eval_data.get("assigned_weight", 0.0)
            relevance = item.relevancia
            confidence = eval_data.get("confidence_score", 0.0)
            
            # Score combinado: peso * relevancia * confianza
            combined = weight * relevance * confidence
            weighted_score += combined
            total_weight += weight * relevance
        
        final_score = weighted_score / total_weight if total_weight > 0 else 0.0
        
        # Determinar nivel dominante
        levels = [e.get("trust_level", "bajo") for e in evaluations]
        high_c = levels.count("alto")
        medium_c = levels.count("medio")
        low_c = levels.count("bajo")
        
        if high_c > 0 and high_c >= medium_c and high_c >= low_c:
            dominant_level = "CONFIANZA_ALTA"
        elif medium_c > 0 and medium_c >= low_c:
            dominant_level = "CONFIANZA_MEDIA"
        elif low_c > 0:
            dominant_level = "CONFIANZA_BAJA"
        else:
            dominant_level = "CONFIANZA_NULA"
        
        # Umbrales de decisión alineados con NexusRouter
        if final_score >= 0.75 and dominant_level == "CONFIANZA_ALTA":
            nivel = "CONFIANZA_ALTA"
            accion = "PROCESAR"
            aprobado = True
        elif final_score >= 0.45:
            nivel = "CONFIANZA_MEDIA"
            accion = "PROCESAR_CON_ADVERTENCIA"
            aprobado = True
        elif final_score >= 0.25:
            nivel = "CONFIANZA_BAJA"
            accion = "PROCESAR_CON_ADVERTENCIA_FUERTE"
            aprobado = True
        else:
            nivel = "CONFIANZA_NULA"
            accion = "BLOQUEAR"
            aprobado = False
        
        return {
            "nivel_confianza": nivel,
            "score_final": round(final_score, 2),
            "aprobado": aprobado,
            "accion": accion,
            "accion_detallada": f"{accion} - {nivel}",
            "dominant_trust_level": dominant_level,
            "aggregate_metrics": search_result.metadatos.get("trust_aggregate", {}),
        }
    
    def create_reasoning_premisas(
        self, 
        search_result: "ResultadoBusqueda",
        query: str = ""
    ) -> list["PremisaLogica"]:
        """
        Convierte resultados de búsqueda evaluados en PremisaLogica para el MotorRazonamientoSuperior.
        
        Cada premisa incluye:
        - confianza: assigned_weight de la evaluación de fuente
        - fuente: dominio original
        - metadatos: trust_level, evaluation_status, matched_rules, etc.
        
        Args:
            search_result: ResultadoBusqueda evaluado con trust_evaluation
            query: Query original (para contexto)
            
        Returns:
            Lista de PremisaLogica listas para MotorRazonamientoSuperior.recibir_hallazgos()
        """
        # Import robusto con fallback para testing
        try:
            from core.reasoning_engine import PremisaLogica
        except ImportError:
            try:
                from HPR.src.core.reasoning_engine import PremisaLogica
            except ImportError:
                # Fallback: dataclass local para testing sin dependencias
                from dataclasses import dataclass, field
                from typing import Dict, Any, List
                
                @dataclass
                class PremisaLogica:
                    id: str
                    tipo: str
                    proposicion: str
                    fuente: str
                    confianza: float
                    evidencia_textual: str
                    entidades: List[str] = field(default_factory=list)
                    metadatos: Dict[str, Any] = field(default_factory=dict)
        
        import uuid
        
        premisas = []
        
        for i, item in enumerate(search_result.resultados):
            trust_eval = item.metadatos_extra.get("trust_evaluation", {})
            
            # Determinar tipo de premisa basado en contenido y categoría
            tipo = self._infer_premise_type(item, trust_eval)
            
            # Confianza = assigned_weight (ya incorpora nivel de confianza)
            confianza = trust_eval.get("assigned_weight", 0.0)
            
            # Si requiere sanitización estricta, reducir confianza adicionalmente
            if trust_eval.get("requires_strict_sanitization", False):
                confianza *= 0.7  # Penalización por riesgo
            
            # Si requiere validación cruzada, confianza moderada
            if trust_eval.get("requires_cross_validation", False):
                confianza *= 0.9  # Ligera penalización
            
            confianza = round(max(0.0, min(1.0, confianza)), 3)
            
            premisa = PremisaLogica(
                id=f"P{uuid.uuid4().hex[:8]}",
                tipo=tipo,
                proposicion=self._formalize_proposition(item, tipo),
                fuente=item.fuente,
                confianza=confianza,
                evidencia_textual=item.contenido_completo or item.snippet,
                entidades=self._extract_entities(item),
                metadatos={
                    "trust_level": trust_eval.get("trust_level", "bajo"),
                    "source_category": trust_eval.get("source_category", "desconocido"),
                    "evaluation_status": trust_eval.get("evaluation_status", "saneamiento_estricto"),
                    "matched_rules": trust_eval.get("matched_rules", []),
                    "requires_cross_validation": trust_eval.get("requires_cross_validation", False),
                    "requires_strict_sanitization": trust_eval.get("requires_strict_sanitization", True),
                    "direct_pass": trust_eval.get("direct_pass", False),
                    "relevance": item.relevancia,
                    "query": query,
                    "position": i + 1,
                }
            )
            premisas.append(premisa)
        
        return premisas
    
    def _infer_premise_type(self, item: "ResultadoItem", trust_eval: dict) -> str:
        """Infiere el tipo de premisa basado en contenido y confianza."""
        category = trust_eval.get("source_category", "desconocido")
        title = item.titulo.lower()
        snippet = (item.snippet or "").lower()
        content = (item.contenido_completo or "").lower()
        full_text = f"{title} {snippet} {content}"
        
        # Palabras clave por tipo
        if any(kw in full_text for kw in ["architecture", "arquitectura", "isa", "instruction set", "cpu", "microarchitecture"]):
            return "arquitectura"
        elif any(kw in full_text for kw in ["specification", "spec", "especificación", "standard", "estándar", "rfc", "ieee"]):
            return "especificacion"
        elif any(kw in full_text for kw in ["benchmark", "performance", "rendimiento", "throughput", "latency", "latencia", "score", "fps", "tflops"]):
            return "metrica"
        elif any(kw in full_text for kw in ["version", "versión", "release", "lanzamiento", "v1.", "v2.", "v3."]):
            return "version"
        elif any(kw in full_text for kw in ["feature", "característica", "support", "soporte", "enable", "habilita", "introduce"]):
            return "tecnologia"
        elif category in ("gubernamental", "educativo", "corporativo_oficial"):
            return "especificacion"  # Fuentes oficiales tienden a ser especs
        elif category == "repo_tecnico":
            return "tecnologia"
        else:
            return "tecnologia"  # Default
    
    def _formalize_proposition(self, item: "ResultadoItem", tipo: str) -> str:
        """Formaliza una proposición lógica a partir del item."""
        title_clean = item.titulo.strip()
        
        if tipo == "arquitectura":
            return f"EXISTE(arquitectura:{title_clean})"
        elif tipo == "tecnologia":
            return f"SOPORTA(sistema, tecnologia:{title_clean})"
        elif tipo == "metrica":
            return f"MIDE(metrica:{title_clean})"
        elif tipo == "especificacion":
            return f"ESPECIFICA(sistema, {title_clean[:100]})"
        elif tipo == "version":
            return f"VERSION(sistema, {title_clean})"
        else:
            return f"AFIRMA({title_clean[:100]})"
    
    def _extract_entities(self, item: "ResultadoItem") -> list[str]:
        """Extrae entidades técnicas del item."""
        import re
        entidades = set()
        
        full_text = f"{item.titulo} {item.snippet} {item.contenido_completo or ''}"
        
        # Siglas técnicas (2+ mayúsculas): MTE, CCA, SVE2, ARM, etc.
        entidades.update(re.findall(r'\b[A-Z]{2,}\b', full_text))
        
        # Versiones: 3.12, 1.0, v2.5, etc.
        entidades.update(re.findall(r'\bv?\d+\.\d+(\.\d+)?\b', full_text))
        
        # Nombres propios técnicos (CamelCase o con números): ARMv9, RISC-V, Python, etc.
        entidades.update(re.findall(r'\b[A-Z][a-z]+(?:[A-Z][a-z]+)*\d*\b', full_text))
        entidades.update(re.findall(r'\b[A-Z]+-[A-Z0-9]+\b', full_text))  # RISC-V
        
        return list(entidades)
    
    def clear_cache(self) -> None:
        """Limpia el caché de evaluaciones."""
        self._cache.clear()
    
    def set_cache_enabled(self, enabled: bool) -> None:
        """Habilita/deshabilita el caché."""
        self._cache_enabled = enabled


# Función de conveniencia para crear orquestador configurado
def create_source_evaluation_orchestrator(
    high_evaluator: Optional["HighTrustEvaluator"] = None,
    medium_evaluator: Optional["MediumTrustEvaluator"] = None,
    low_evaluator: Optional["LowTrustEvaluator"] = None,
) -> SourceEvaluationOrchestrator:
    """
    Factoría para crear SourceEvaluationOrchestrator con evaluadores inyectados.
    
    Args:
        high_evaluator: Evaluador Nivel Alto opcional
        medium_evaluator: Evaluador Nivel Medio opcional
        low_evaluator: Evaluador Nivel Bajo opcional
        
    Returns:
        SourceEvaluationOrchestrator configurado
    """
    return SourceEvaluationOrchestrator(
        high_evaluator=high_evaluator,
        medium_evaluator=medium_evaluator,
        low_evaluator=low_evaluator,
    )


# ============================================================================
# CAPA 1: E-E-A-T (Experience, Expertise, Authoritativeness, Trustworthiness)
# Evaluación semántica de calidad documental para indexación
# ============================================================================

class EEATDimension(str, Enum):
    """Dimensiones E-E-A-T de Google."""
    EXPERIENCE = "experience"       # Experiencia directa del autor
    EXPERTISE = "expertise"         # Conocimiento técnico demostrado
    AUTHORITATIVENESS = "authoritativeness"  # Autoridad en el tema
    TRUSTWORTHINESS = "trustworthiness"      # Fiabilidad/transparencia


@dataclass(frozen=True)
class EEATSignal:
    """Señal E-E-A-T detectada en contenido."""
    dimension: EEATDimension
    signal: str                     # Descripción de la señal
    strength: float                 # 0.0-1.0 fortaleza de la señal
    evidence: str                   # Fragmento que la soporta


@dataclass
class EEATEvaluation:
    """Resultado completo de evaluación E-E-A-T."""
    experience_score: float         # 0.0-1.0
    expertise_score: float          # 0.0-1.0
    authoritativeness_score: float  # 0.0-1.0
    trustworthiness_score: float    # 0.0-1.0
    overall_score: float            # Promedio ponderado
    signals_detected: List[EEATSignal]
    quality_tier: str               # "alto", "medio", "bajo", "insuficiente"
    indexing_priority: float        # 0.0-1.0 prioridad para indexación


# Patrones para detección de señales E-E-A-T
EXPERIENCE_PATTERNS: Dict[str, List[str]] = {
    "first_person": [
        r"\b(yo he|he probado|he implementado|he verificado|mi experiencia|en mi caso)\b",
        r"\b(i have|i tested|i implemented|i verified|my experience|in my case)\b",
    ],
    "practical_details": [
        r"\b(paso a paso|step.by.step|configuraci[oó]n real|en producci[oó]n)\b",
        r"\b(lessons learned|lecciones aprendidas|trucos|tips|gotchas)\b",
        r"\b(troubleshooting|debugging|resoluci[oó]n de problemas)\b",
    ],
    "version_specific": [
        r"\b(versi[oó]n|version|v\d+\.\d+|release \d+)\b",
        r"\b(compatible con|tested on|probado en|works with)\b",
    ],
}

EXPERTISE_PATTERNS: Dict[str, List[str]] = {
    "technical_depth": [
        r"\b(arquitectura|microarquitectura|pipeline|ISA|registros|opcode)\b",
        r"\b(compilador|compiler|optimizaci[oó]n|vectorizaci[oó]n|SIMD)\b",
        r"\b(memoria|cach[eé]|TLB|MMU|paging|virtual memory)\b",
        r"\b(concurrencia|hilos|threads|lock.free|atomic|mutex)\b",
        r"\b(kernel|driver|syscall|sysfs|procfs|eBPF)\b",
    ],
    "standards_references": [
        r"\b(RFC|IEEE|ISO|ECMA|W3C|Khronos|ARM ARM|Intel SDM|AMD APM)\b",
        r"\b(especificaci[oó]n|specification|standard|normativa)\b",
        r"\b(datasheet|hoja de datos|reference manual|programmer's guide)\b",
    ],
    "quantitative_analysis": [
        r"\b(benchmark|throughput|latencia|latency|bandwidth|ancho de banda)\b",
        r"\b(\d+(?:\.\d+)?\s*(?:ns|us|ms|s|GHz|MHz|GB/s|MB/s|TFLOPS|GFLOPS))\b",
        r"\b(perf|vtune|tracy|nsight|rocprof|perfetto)\b",
    ],
}

AUTHORITATIVENESS_PATTERNS: Dict[str, List[str]] = {
    "official_source": [
        r"\b(oficial|official|vendor|proveedor|fabricante|manufacturer)\b",
        r"\b(documentaci[oó]n oficial|official documentation|developer guide)\b",
        r"\b(reference manual|programmer's guide|architecture manual)\b",
    ],
    "citations_references": [
        r"\b(cita|referencia|source|fuente|bibliograf[ií]a)\b",
        r"\[[\d,\s]+\]",  # Citas estilo [1, 2, 3]
        r"\([A-Za-z]+\s+\d{4}\)",  # Citas autor-año (Smith 2023)
    ],
    "peer_recognition": [
        r"\b(acceptado en|published in|presentado en|conferencia|conference)\b",
        r"\b(arXiv|doi\.org|ISBN|ISSN|patent|patente)\b",
    ],
}

TRUSTWORTHINESS_PATTERNS: Dict[str, List[str]] = {
    "transparency": [
        r"\b(limitaci[oó]n|limitations|supuesto|assumption|trade.?off)\b",
        r"\b(no aplica|not applicable|fuera de scope|out of scope)\b",
        r"\b(falso positivo|false positive|falso negativo|false negative)\b",
    ],
    "reproducibility": [
        r"\b(reproducible|reproducir|reproduce|artefactos|artifacts)\b",
        r"\b(c[oó]digo disponible|code available|github\.com|gitlab\.com)\b",
        r"\b(docker|container|entorno|environment|requirements\.txt)\b",
    ],
    "author_identity": [
        r"\b(autor|author|escrito por|written by|por)\s+[A-Z][a-z]+",
        r"\b(linkedin|github|twitter|mastodon|orcid|scholar)\b",
        r"\b(afiliaci[oó]n|affiliation|universidad|empresa|company)\b",
    ],
    "freshness_maintenance": [
        r"\b(actualizado|updated|mantenido|maintained|last modified)\b",
        r"\b(202[3-9]|20[3-9]\d)\b",  # Años recientes
    ],
}


def _detect_eeat_signals(
    content: str,
    title: str,
    url: str,
    author: Optional[str] = None,
    publish_date: Optional[str] = None,
) -> List[EEATSignal]:
    """Detecta señales E-E-A-T en contenido completo."""
    signals: List[EEATSignal] = []
    full_text = f"{title}\n{content}".lower()
    url_lower = url.lower()
    
    # --- EXPERIENCE ---
    for category, patterns in EXPERIENCE_PATTERNS.items():
        for pattern in patterns:
            matches = list(re.finditer(pattern, full_text, re.IGNORECASE))
            if matches:
                strength = min(len(matches) * 0.15, 0.8)
                evidence = matches[0].group()[:100]
                signals.append(EEATSignal(
                    dimension=EEATDimension.EXPERIENCE,
                    signal=f"experience:{category}",
                    strength=strength,
                    evidence=evidence
                ))
    
    # --- EXPERTISE ---
    for category, patterns in EXPERTISE_PATTERNS.items():
        for pattern in patterns:
            matches = list(re.finditer(pattern, full_text, re.IGNORECASE))
            if matches:
                strength = min(len(matches) * 0.12, 0.85)
                evidence = matches[0].group()[:100]
                signals.append(EEATSignal(
                    dimension=EEATDimension.EXPERTISE,
                    signal=f"expertise:{category}",
                    strength=strength,
                    evidence=evidence
                ))
    
    # Bonus por términos técnicos densos
    tech_term_count = len(re.findall(r'\b[A-Z]{2,}\b', full_text))  # Siglas técnicas
    if tech_term_count > 5:
        signals.append(EEATSignal(
            dimension=EEATDimension.EXPERTISE,
            signal="expertise:technical_density",
            strength=min(tech_term_count * 0.02, 0.6),
            evidence=f"{tech_term_count} siglas técnicas detectadas"
        ))
    
    # --- AUTHORITATIVENESS ---
    # Dominio autorizado
    domain = url_lower.split('/')[2] if '://' in url_lower else url_lower.split('/')[0]
    official_domains = {
        "developer.arm.com", "arm.com", "nvidia.com", "developer.nvidia.com",
        "docs.nvidia.com", "intel.com", "amd.com", "python.org", "docs.python.org",
        "rust-lang.org", "doc.rust-lang.org", "golang.org", "pkg.go.dev",
        "kubernetes.io", "cncf.io", "docker.com", "docs.docker.com",
        "kernel.org", "lwn.net", "w3.org", "ietf.org", "iso.org",
        "github.com", "gitlab.com", "arxiv.org", "doi.org",
    }
    if any(domain.endswith(d) for d in official_domains):
        signals.append(EEATSignal(
            dimension=EEATDimension.AUTHORITATIVENESS,
            signal="authoritativeness:official_domain",
            strength=0.9,
            evidence=f"Dominio oficial: {domain}"
        ))
    
    for category, patterns in AUTHORITATIVENESS_PATTERNS.items():
        for pattern in patterns:
            matches = list(re.finditer(pattern, full_text, re.IGNORECASE))
            if matches:
                strength = min(len(matches) * 0.1, 0.7)
                evidence = matches[0].group()[:100]
                signals.append(EEATSignal(
                    dimension=EEATDimension.AUTHORITATIVENESS,
                    signal=f"authoritativeness:{category}",
                    strength=strength,
                    evidence=evidence
                ))
    
    # --- TRUSTWORTHINESS ---
    for category, patterns in TRUSTWORTHINESS_PATTERNS.items():
        for pattern in patterns:
            matches = list(re.finditer(pattern, full_text, re.IGNORECASE))
            if matches:
                strength = min(len(matches) * 0.1, 0.75)
                evidence = matches[0].group()[:100]
                signals.append(EEATSignal(
                    dimension=EEATDimension.TRUSTWORTHINESS,
                    signal=f"trustworthiness:{category}",
                    strength=strength,
                    evidence=evidence
                ))
    
    # Autor identificado
    if author and len(author) > 3:
        signals.append(EEATSignal(
            dimension=EEATDimension.TRUSTWORTHINESS,
            signal="trustworthiness:identified_author",
            strength=0.6,
            evidence=f"Autor: {author[:50]}"
        ))
    
    # Fecha reciente
    if publish_date:
        try:
            from datetime import datetime
            pub_year = int(publish_date[:4])
            current_year = datetime.now().year
            if current_year - pub_year <= 1:
                signals.append(EEATSignal(
                    dimension=EEATDimension.TRUSTWORTHINESS,
                    signal="trustworthiness:fresh_content",
                    strength=0.8,
                    evidence=f"Publicado en {publish_date}"
                ))
            elif current_year - pub_year <= 2:
                signals.append(EEATSignal(
                    dimension=EEATDimension.TRUSTWORTHINESS,
                    signal="trustworthiness:recent_content",
                    strength=0.5,
                    evidence=f"Publicado en {publish_date}"
                ))
        except (ValueError, IndexError):
            pass
    
    return signals


def _calculate_eeat_scores(signals: List[EEATSignal]) -> Tuple[float, float, float, float]:
    """Calcula scores por dimensión a partir de señales."""
    dim_scores: Dict[EEATDimension, List[float]] = {d: [] for d in EEATDimension}
    
    for signal in signals:
        dim_scores[signal.dimension].append(signal.strength)
    
    # Promedio por dimensión (con floor mínimo)
    scores = {}
    for dim in EEATDimension:
        vals = dim_scores[dim]
        if vals:
            scores[dim] = sum(vals) / len(vals)
        else:
            scores[dim] = 0.1  # Floor mínimo
    
    return (
        scores[EEATDimension.EXPERIENCE],
        scores[EEATDimension.EXPERTISE],
        scores[EEATDimension.AUTHORITATIVENESS],
        scores[EEATDimension.TRUSTWORTHINESS],
    )


def evaluate_eeat(
    content: str,
    title: str,
    url: str,
    author: Optional[str] = None,
    publish_date: Optional[str] = None,
    source_trust_level: Optional[str] = None,
) -> EEATEvaluation:
    """
    Evalúa contenido según criterios E-E-A-T para prioridad de indexación.
    
    Args:
        content: Contenido completo de la página
        title: Título (H1)
        url: URL de la fuente
        author: Autor si se conoce
        publish_date: Fecha publicación (YYYY-MM-DD)
        source_trust_level: Nivel de confianza previo ("alto", "medio", "bajo")
        
    Returns:
        EEATEvaluation con scores, tier de calidad y prioridad de indexación
    """
    signals = _detect_eeat_signals(content, title, url, author, publish_date)
    
    exp_score, exp_score, auth_score, trust_score = _calculate_eeat_scores(signals)
    
    # Pesos por dimensión (según guidelines de Google)
    weights = {
        EEATDimension.EXPERIENCE: 0.25,
        EEATDimension.EXPERTISE: 0.30,
        EEATDimension.AUTHORITATIVENESS: 0.25,
        EEATDimension.TRUSTWORTHINESS: 0.20,
    }
    
    overall = (
        exp_score * weights[EEATDimension.EXPERIENCE] +
        exp_score * weights[EEATDimension.EXPERTISE] +
        auth_score * weights[EEATDimension.AUTHORITATIVENESS] +
        trust_score * weights[EEATDimension.TRUSTWORTHINESS]
    )
    
    # Ajuste por nivel de confianza previo
    if source_trust_level == "alto":
        overall = min(overall + 0.1, 1.0)
    elif source_trust_level == "bajo":
        overall = max(overall - 0.15, 0.0)
    
    # Tier de calidad
    if overall >= 0.75:
        tier = "alto"
    elif overall >= 0.55:
        tier = "medio"
    elif overall >= 0.35:
        tier = "bajo"
    else:
        tier = "insuficiente"
    
    # Prioridad de indexación (alineada con trust_level pero semántica)
    indexing_priority = overall
    
    return EEATEvaluation(
        experience_score=round(exp_score, 3),
        expertise_score=round(exp_score, 3),
        authoritativeness_score=round(auth_score, 3),
        trustworthiness_score=round(trust_score, 3),
        overall_score=round(overall, 3),
        signals_detected=signals,
        quality_tier=tier,
        indexing_priority=round(indexing_priority, 3),
    )


def create_eeat_evaluator() -> callable:
    """Factoría para función de evaluación E-E-A-T."""
    return evaluate_eeat


# ============================================================================
# INTEGRACIÓN UNIFICADA: QueryBuilder + E-E-A-T + SourceEvaluator
# ============================================================================

class UnifiedSearchPipeline:
    """
    Pipeline unificado de búsqueda inteligente.
    
    Integra:
    1. QueryBuilder - Operadores de indexación avanzada (Capa 2)
    2. E-E-A-T Evaluator - Calidad documental semántica (Capa 1)
    3. SourceEvaluator - Jerarquía de confianza 3 niveles (Fases 2-4)
    
    Flujo:
    Query Natural -> QueryBuilder (variantes) -> Búsqueda -> E-E-A-T -> SourceEvaluator -> Premisas ponderadas
    """
    
    VERSION = "1.0.0"
    
    def __init__(
        self,
        query_builder: Optional[QueryBuilder] = None,
        eeat_evaluator: Optional[callable] = None,
        source_orchestrator: Optional[SourceEvaluationOrchestrator] = None,
    ):
        # Import directly from file to avoid circular dependency with HPR package
        import importlib.util
        if query_builder is None:
            spec = importlib.util.spec_from_file_location(
                "query_builder", r"C:\Users\USUARIO\Desktop\motor HPR\HPR\src\nexus_root\query_builder.py"
            )
            qb_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(qb_module)
            query_builder = qb_module.create_query_builder()
        self.query_builder = query_builder
        self.eeat_evaluator = eeat_evaluator or evaluate_eeat
        self.source_orchestrator = source_orchestrator or create_source_evaluation_orchestrator()
    
    def process_query(
        self,
        natural_query: str,
        search_results: List[Dict],  # Resultados crudos de búsqueda
        execute_search: Optional[callable] = None,  # Función de búsqueda externa
    ) -> Dict:
        """
        Procesa query completa: construye variantes, busca, evalúa E-E-A-T y confianza.
        
        Args:
            natural_query: Query en lenguaje natural
            search_results: Resultados previos (opcional, si no se usa execute_search)
            execute_search: Función async(query: str) -> List[Dict] para búsqueda real
            
        Returns:
            Dict con query construida, resultados evaluados, premisas para razonamiento
        """
        # 1. Construir variantes de query con operadores avanzados
        query_variants = self.query_builder.build_variants(natural_query)
        primary_query = query_variants[0]
        
        logger.info(f"UnifiedPipeline: Query principal -> {primary_query.raw_query}")
        logger.info(f"UnifiedPipeline: Precision estimada -> {primary_query.estimated_precision:.2f}")
        
        # 2. Ejecutar búsqueda si no hay resultados previos
        if not search_results and execute_search:
            search_results = execute_search(primary_query.raw_query)
        
        # 3. Evaluar cada resultado con E-E-A-T
        enriched_results = []
        for result in search_results:
            content = result.get("contenido_completo") or result.get("snippet", "")
            title = result.get("titulo", "")
            url = result.get("url", "")
            author = result.get("autor")
            publish_date = result.get("fecha_publicacion")
            
            # E-E-A-T evaluation
            eeat = self.eeat_evaluator(
                content=content,
                title=title,
                url=url,
                author=author,
                publish_date=publish_date,
            )
            
            # SourceEvaluator (jerarquía 3 niveles)
            from src.source_evaluator import SourceInput
            source_input = SourceInput(
                url=url,
                domain=self._extract_domain(url),
                title=title,
                content_preview=content[:500],
                content_length=len(content),
            )
            trust_eval = self.source_orchestrator.evaluate_source(source_input)
            
            # Combinar scores
            combined_confidence = (
                trust_eval.assigned_weight * 0.6 +  # Confianza jerárquica (60%)
                eeat.indexing_priority * 0.4         # Calidad semántica E-E-A-T (40%)
            )
            
            enriched_results.append({
                **result,
                "eeat_evaluation": {
                    "experience": eeat.experience_score,
                    "expertise": eeat.expertise_score,
                    "authoritativeness": eeat.authoritativeness_score,
                    "trustworthiness": eeat.trustworthiness_score,
                    "overall": eeat.overall_score,
                    "quality_tier": eeat.quality_tier,
                    "indexing_priority": eeat.indexing_priority,
                    "signals_count": len(eeat.signals_detected),
                },
                "trust_evaluation": {
                    "trust_level": trust_eval.trust_level.value,
                    "source_category": trust_eval.source_category.value,
                    "evaluation_status": trust_eval.evaluation_status.value,
                    "assigned_weight": trust_eval.assigned_weight,
                    "confidence_score": trust_eval.confidence_score,
                    "matched_rules": trust_eval.matched_rules,
                    "requires_cross_validation": trust_eval.requires_cross_validation,
                    "requires_strict_sanitization": trust_eval.requires_strict_sanitization,
                    "direct_pass": trust_eval.direct_pass,
                },
                "combined_confidence": round(combined_confidence, 3),
                "query_used": primary_query.raw_query,
                "query_operators": [op.value for op in primary_query.operators_used],
            })
        
        # 4. Ordenar por confianza combinada descendente
        enriched_results.sort(key=lambda x: x["combined_confidence"], reverse=True)
        
        # 5. Generar premisas para motor de razonamiento
        premisas = self.source_orchestrator.create_reasoning_premisas(
            search_result=self._dict_to_busqueda(enriched_results, natural_query),
            query=natural_query,
        )
        
        return {
            "natural_query": natural_query,
            "built_query": {
                "raw": primary_query.raw_query,
                "operators": [op.value for op in primary_query.operators_used],
                "precision": primary_query.estimated_precision,
                "target_domains": primary_query.target_domains,
                "freshness": primary_query.freshness_filter,
                "filetype": primary_query.filetype_filter,
            },
            "query_variants": [
                {"raw": v.raw_query, "precision": v.estimated_precision}
                for v in query_variants
            ],
            "results": enriched_results,
            "premisas": [
                {
                    "id": p.id,
                    "tipo": p.tipo,
                    "proposicion": p.proposicion,
                    "fuente": p.fuente,
                    "confianza": p.confianza,
                    "entidades": p.entidades,
                    "metadatos": p.metadatos,
                }
                for p in premisas
            ],
            "metrics": {
                "total_results": len(enriched_results),
                "high_confidence": sum(1 for r in enriched_results if r["combined_confidence"] >= 0.7),
                "medium_confidence": sum(1 for r in enriched_results if 0.4 <= r["combined_confidence"] < 0.7),
                "low_confidence": sum(1 for r in enriched_results if r["combined_confidence"] < 0.4),
                "avg_eeat": sum(r["eeat_evaluation"]["overall"] for r in enriched_results) / len(enriched_results) if enriched_results else 0,
                "avg_trust": sum(r["trust_evaluation"]["assigned_weight"] for r in enriched_results) / len(enriched_results) if enriched_results else 0,
                "avg_combined": sum(r["combined_confidence"] for r in enriched_results) / len(enriched_results) if enriched_results else 0,
            },
        }
    
    def _extract_domain(self, url: str) -> str:
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc.lower().replace("www.", "")
        except Exception:
            return "unknown"
    
    def _dict_to_busqueda(self, results: List[Dict], query: str):
        """Convierte resultados enriquecidos a formato ResultadoBusqueda para orquestador."""
        # Usar clases mock inyectadas por test o clases reales si están disponibles
        try:
            from src.source_evaluator import ResultadoItem, ResultadoBusqueda
        except (ImportError, AttributeError):
            # Definir clases mock locales para testing
            from dataclasses import dataclass, field
            from typing import Dict, Any, Optional, List
            from datetime import datetime
            
            @dataclass
            class ResultadoItem:
                titulo: str
                url: str
                snippet: str
                fuente: str
                relevancia: float = 1.0
                contenido_completo: Optional[str] = None
                metadatos_extra: Dict[str, Any] = field(default_factory=dict)
            
            @dataclass
            class ResultadoBusqueda:
                exito: bool
                query_original: str
                sintesis: str
                resultados: List[ResultadoItem]
                fuente: str
                metadatos: Dict[str, Any]
                timestamp: str = field(default_factory=lambda: datetime.now().isoformat() + "Z")
        from datetime import datetime
        
        items = []
        for r in results:
            items.append(ResultadoItem(
                titulo=r.get("titulo", ""),
                url=r.get("url", ""),
                snippet=r.get("snippet", ""),
                fuente=r.get("fuente", ""),
                relevancia=r.get("relevancia", 1.0),
                contenido_completo=r.get("contenido_completo"),
                metadatos_extra={
                    **r.get("metadatos_extra", {}),
                    "eeat_evaluation": r.get("eeat_evaluation"),
                    "trust_evaluation": r.get("trust_evaluation"),
                    "combined_confidence": r.get("combined_confidence"),
                }
            ))
        
        return ResultadoBusqueda(
            exito=len(items) > 0,
            query_original=query,
            sintesis="",  # Se generará en DeepSynthesizer
            resultados=items,
            fuente="unified_pipeline",
            metadatos={},
            timestamp=datetime.now().isoformat() + "Z"
        )


def create_unified_pipeline(
    query_builder: Optional[QueryBuilder] = None,
    source_orchestrator: Optional[SourceEvaluationOrchestrator] = None,
) -> UnifiedSearchPipeline:
    """Factoría para pipeline unificado."""
    # Import directly from file to avoid circular dependency with HPR package
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "query_builder", r"C:\Users\USUARIO\Desktop\motor HPR\HPR\src\nexus_root\query_builder.py"
    )
    qb_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(qb_module)
    qb = query_builder or qb_module.create_query_builder()
    return UnifiedSearchPipeline(
        query_builder=qb,
        source_orchestrator=source_orchestrator,
    )


# ============================================================
# INTEGRACIÓN CON NEXUS ROUTER - ADAPTADOR DE EVALUACIÓN
# ============================================================

def evaluate_external_sources_for_nexus(
    search_result: "ResultadoBusqueda",
    orchestrator: Optional[SourceEvaluationOrchestrator] = None,
) -> dict:
    """
    Función de integración directa para NexusRouter._evaluar_resultado_externo.
    
    Reemplaza/extiende la evaluación de tres niveles existente en router.py
    con la evaluación granular jerárquica del SourceEvaluator.
    
    Args:
        search_result: ResultadoBusqueda del ExternalToolExecutor
        orchestrator: Orquestador opcional (se crea uno por defecto)
        
    Returns:
        Dict compatible con NexusRouter (nivel_confianza, score_final, aprobado, accion, etc.)
    """
    orch = orchestrator or create_source_evaluation_orchestrator()
    
    # Evaluar fuentes si no están ya evaluadas
    needs_evaluation = not any(
        "trust_evaluation" in (item.metadatos_extra or {})
        for item in search_result.resultados
    )
    
    if needs_evaluation:
        search_result = orch.evaluate_search_results(search_result)
    
    # Adaptar al formato NexusRouter
    return orch.adapt_for_nexus_router(search_result)


# ============================================================
# INTEGRACIÓN CON MOTOR DE RAZONAMIENTO - ADAPTADOR DE PREMISAS
# ============================================================

def create_trust_weighted_premisas(
    search_result: "ResultadoBusqueda",
    query: str = "",
    orchestrator: Optional[SourceEvaluationOrchestrator] = None,
) -> list["PremisaLogica"]:
    """
    Crea premisas ponderadas por confianza para el MotorRazonamientoSuperior.
    
    Esta es la función de integración principal para conectar búsqueda evaluada
    con el motor de razonamiento superior.
    
    Args:
        search_result: ResultadoBusqueda (se evaluará si no lo está)
        query: Query original
        orchestrator: Orquestador opcional
        
    Returns:
        Lista de PremisaLogica con confianza = assigned_weight ajustado por riesgo
    """
    orch = orchestrator or create_source_evaluation_orchestrator()
    
    # Evaluar si no está evaluado
    needs_evaluation = not any(
        "trust_evaluation" in (item.metadatos_extra or {})
        for item in search_result.resultados
    )
    
    if needs_evaluation:
        search_result = orch.evaluate_search_results(search_result, query)
    
    return orch.create_reasoning_premisas(search_result, query)


# ============================================================
# EXPORTS PÚBLICOS PARA INTEGRACIÓN FÁCIL
# ============================================================

__all__ = [
    # Enums y tipos base (Fase 1)
    "TrustLevel",
    "SourceCategory", 
    "EvaluationStatus",
    "TrustLevelConfig",
    "TRUST_LEVEL_CONFIGS",
    "SourceInput",
    "SourceEvaluationResult",
    "BatchEvaluationInput",
    "BatchEvaluationResult",
    
    # Nivel Alto (Fase 2)
    "OFFICIAL_TLDS",
    "OFFICIAL_SECOND_LEVEL_DOMAINS",
    "OFFICIAL_DOMAIN_PATTERNS",
    "OFFICIAL_CORPORATE_DOMAINS",
    "HighTrustEvaluator",
    "HighTrustEvaluationError",
    "evaluate_high_trust",
    
    # Nivel Medio (Fase 3)
    "MEDIUM_TRUST_TECH_FORUMS",
    "MEDIUM_TRUST_CODE_REPOS",
    "GOVERNED_REPO_PATTERNS",
    "MediumTrustEvaluator",
    "MediumTrustEvaluationError",
    "evaluate_medium_trust",
    
    # Nivel Bajo (Fase 4)
    "LOW_TRUST_BLOG_PLATFORMS",
    "PERSONAL_DOMAIN_PATTERNS",
    "RISK_KEYWORDS",
    "QUALITY_INDICATORS",
    "LowTrustEvaluator",
    "LowTrustEvaluationError",
    "evaluate_low_trust",
    
    # Orquestador e Integración (Fase 5)
    "SourceEvaluationOrchestrator",
    "create_source_evaluation_orchestrator",
    "evaluate_external_sources_for_nexus",
    "create_trust_weighted_premisas",
    
    # ============================================================================
    # FASE FINAL UNIFICADA: QueryBuilder (Capa 2) + E-E-A-T (Capa 1) + Pipeline
    # ============================================================================
    
    # QueryBuilder - Operadores de indexación avanzada
    "GoogleOperator",
    "OperatorConfig",
    "OPERATOR_CONFIGS",
    "QueryComponent",
    "BuiltQuery",
    "QueryBuilder",
    "create_query_builder",
    
    # E-E-A-T - Calidad documental semántica
    "EEATDimension",
    "EEATSignal",
    "EEATEvaluation",
    "EXPERIENCE_PATTERNS",
    "EXPERTISE_PATTERNS",
    "AUTHORITATIVENESS_PATTERNS",
    "TRUSTWORTHINESS_PATTERNS",
    "_detect_eeat_signals",
    "_calculate_eeat_scores",
    "evaluate_eeat",
    "create_eeat_evaluator",
    
    # Pipeline Unificado - Integración completa
    "UnifiedSearchPipeline",
    "create_unified_pipeline",
]