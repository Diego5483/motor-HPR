"""
Módulo QueryBuilder - Construcción Inteligente de Consultas con Operadores de Indexación Avanzada
FASE FINAL: Alineación total de indexación y búsqueda inteligente

Este módulo implementa la Capa 2: Operadores de Indexación Avanzada en Consultas
para construir queries que extraen información directamente de los índices técnicos
más limpios y autorizados usando operadores de Google/DuckDuckGo.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Set, Tuple
import re
import logging

logger = logging.getLogger(__name__)


class GoogleOperator(str, Enum):
    """Operadores de indexación de Google/DuckDuckGo soportados."""
    SITE = "site:"              # Restringir a dominio/subdominio
    INTITLE = "intitle:"        # Palabras en título de página
    INURL = "inurl:"            # Palabras en URL
    INTEXT = "intext:"          # Palabras en cuerpo de texto
    FILETYPE = "filetype:"      # Tipo de archivo (pdf, doc, etc.)
    AFTER = "after:"            # Fecha posterior (YYYY-MM-DD)
    BEFORE = "before:"          # Fecha anterior (YYYY-MM-DD)
    AROUND = "AROUND(n)"        # Proximidad entre términos
    MINUS = "-"                 # Exclusión de término
    OR = "OR"                   # Alternativa lógica
    QUOTES = '"'                # Frase exacta
    WILDCARD = "*"              # Comodín
    CACHE = "cache:"            # Versión en caché
    RELATED = "related:"        # Sitios relacionados
    INFO = "info:"              # Información sobre URL
    DEFINE = "define:"          # Definición
    MAP = "map:"                # Mapa
    WEATHER = "weather:"        # Clima
    STOCKS = "stocks:"          # Acciones


@dataclass(frozen=True)
class OperatorConfig:
    """Configuración de un operador con validación y peso de relevancia."""
    operator: GoogleOperator
    syntax: str                 # Sintaxis completa (ej: "site:")
    requires_value: bool = True
    max_length: int = 256
    weight: float = 1.0         # Peso de relevancia para scoring
    description: str = ""


# Configuración estándar de operadores
OPERATOR_CONFIGS: Dict[GoogleOperator, OperatorConfig] = {
    GoogleOperator.SITE: OperatorConfig(
        operator=GoogleOperator.SITE,
        syntax="site:",
        weight=1.5,
        description="Restringe resultados a dominio/subdominio específico"
    ),
    GoogleOperator.INTITLE: OperatorConfig(
        operator=GoogleOperator.INTITLE,
        syntax="intitle:",
        weight=1.3,
        description="Requiere términos en título de página (H1/H2)"
    ),
    GoogleOperator.INURL: OperatorConfig(
        operator=GoogleOperator.INURL,
        syntax="inurl:",
        weight=1.1,
        description="Requiere términos en URL"
    ),
    GoogleOperator.INTEXT: OperatorConfig(
        operator=GoogleOperator.INTEXT,
        syntax="intext:",
        weight=1.0,
        description="Requiere términos en cuerpo de texto"
    ),
    GoogleOperator.FILETYPE: OperatorConfig(
        operator=GoogleOperator.FILETYPE,
        syntax="filetype:",
        weight=1.2,
        description="Filtra por tipo de archivo (pdf, docx, ppt, etc.)"
    ),
    GoogleOperator.AFTER: OperatorConfig(
        operator=GoogleOperator.AFTER,
        syntax="after:",
        weight=1.1,
        description="Resultados posteriores a fecha (YYYY-MM-DD)"
    ),
    GoogleOperator.BEFORE: OperatorConfig(
        operator=GoogleOperator.BEFORE,
        syntax="before:",
        weight=1.1,
        description="Resultados anteriores a fecha (YYYY-MM-DD)"
    ),
    GoogleOperator.AROUND: OperatorConfig(
        operator=GoogleOperator.AROUND,
        syntax="AROUND(",
        weight=1.2,
        description="Proximidad entre términos (n=palabras de distancia)"
    ),
}


@dataclass
class QueryComponent:
    """Componente individual de una query construida."""
    operator: Optional[GoogleOperator]  # None = término libre
    value: str
    is_negative: bool = False           # Para operador MINUS (-)
    group: Optional[str] = None         # Grupo lógico (para paréntesis)


@dataclass
class BuiltQuery:
    """Query construida con metadatos de calidad."""
    raw_query: str                      # Query final lista para motor de búsqueda
    components: List[QueryComponent]    # Componentes parseados
    operators_used: Set[GoogleOperator] # Operadores empleados
    estimated_precision: float          # 0.0-1.0 estimación de precisión
    target_domains: List[str]           # Dominios objetivo (site:)
    freshness_filter: Optional[str]     # Filtro temporal si aplica
    filetype_filter: Optional[str]      # Filtro de tipo archivo si aplica
    metadata: Dict = field(default_factory=dict)


class QueryBuilder:
    """
    Constructor de consultas inteligentes con operadores de indexación avanzada.
    
    Responsabilidades:
    1. Parsear query natural y detectar intención técnica
    2. Aplicar operadores de indexación (site:, intitle:, filetype:, etc.)
    3. Inyectar filtros de frescura, tipo de archivo, dominios autorizados
    4. Optimizar para extracción desde índices técnicos autorizados
    5. Generar variantes de query para búsqueda en cascada (amplia -> específica)
    """
    
    VERSION = "1.0.0"
    
    # Dominios técnicos autorizados por categoría (E-E-A-T aligned)
    AUTHORITATIVE_DOMAINS: Dict[str, List[str]] = {
        "oficiales": [
            "developer.arm.com", "arm.com",
            "nvidia.com", "developer.nvidia.com", "docs.nvidia.com",
            "intel.com", "amd.com", "qualcomm.com",
            "python.org", "docs.python.org", "peps.python.org",
            "rust-lang.org", "doc.rust-lang.org",
            "golang.org", "pkg.go.dev", "go.dev",
            "kubernetes.io", "cncf.io",
            "docker.com", "docs.docker.com",
            "linuxfoundation.org", "kernel.org", "lwn.net",
            "github.com", "gitlab.com", "bitbucket.org",
            "w3.org", "ietf.org", "iso.org", "ecma-international.org",
            "open-group.org", "khronos.org",
        ],
        "academicos": [
            "arxiv.org", "doi.org", "scholar.google.com",
            "pubmed.ncbi.nlm.nih.gov", "ieee.org", "acm.org",
            "research.google.com", "research.fb.com", "research.nvidia.com",
            "microsoft.com/research", "ai.googleblog.com",
        ],
        "documentacion_oficial": [
            "docs.python.org", "developer.mozilla.org", "developer.chrome.com",
            "cloud.google.com/docs", "aws.amazon.com/documentation",
            "azure.microsoft.com/documentation", "docs.microsoft.com",
            "kubernetes.io/docs", "kubernetes.io/docs/reference",
            "terraform.io/docs", "packer.io/docs",
            "prometheus.io/docs", "grafana.com/docs",
        ],
        "tecnicos_especializados": [
            "anandtech.com", "tomshardware.com", "phoronix.com",
            "servethehome.com", "chipsandcheese.com",
            "lwn.net", "kernelnewbies.org",
            "realpython.com", "docs.python.org/3/howto",
        ],
    }
    
    # Patrones de intención técnica para detección automática
    TECHNICAL_INTENT_PATTERNS: Dict[str, List[str]] = {
        "especificacion": [
            r"\b(especificaci[oó]n|spec|specs|datasheet|hoja de datos)\b",
            r"\b(arquitectura|architecture|microarquitectura|ISA)\b",
            r"\b(registros|registers|opcode|instrucci[oó]n)\b",
        ],
        "comparativa": [
            r"\b(comparativa|comparaci[oó]n|vs|versus|benchmark)\b",
            r"\b(rendimiento|performance|throughput|latencia|latency)\b",
            r"\b(ventajas?|desventajas?|pros?|cons?|trade.?off)\b",
        ],
        "implementacion": [
            r"\b(c[oó]mo|how to|tutorial|gu[ií]a|guide|implementar)\b",
            r"\b(c[oó]digo|code|ejemplo|example|snippet|sample)\b",
            r"\b(configurar|setup|install|instalar|compilar|build)\b",
        ],
        "debugging": [
            r"\b(error|bug|fallo|crash|exception|traceback)\b",
            r"\b(soluci[oó]n|fix|workaround|parche|patch)\b",
            r"\b(no funciona|doesn't work|broken|failing)\b",
        ],
        "version": [
            r"\b(versi[oó]n|version|release|changelog|what's new)\b",
            r"\b(actualizaci[oó]n|update|upgrade|migraci[oó]n)\b",
            r"\b(v?\d+\.\d+(\.\d+)?)\b",
        ],
        "seguridad": [
            r"\b(seguridad|security|vulnerabilidad|vulnerability|cve)\b",
            r"\b(parche|patch|mitigaci[oó]n|hardening)\b",
            r"\b(cifrado|encryption|tls|ssl|certificado)\b",
        ],
    }
    
    # Extensiones de archivo técnico relevantes
    TECHNICAL_FILETYPES: Dict[str, List[str]] = {
        "documentacion": ["pdf", "doc", "docx", "txt", "md", "rst"],
        "especificaciones": ["pdf", "html", "xml", "json", "yaml", "yml"],
        "codigo": ["py", "rs", "go", "js", "ts", "java", "cpp", "c", "h", "hpp"],
        "datos": ["csv", "json", "xml", "parquet", "avro"],
        "presentaciones": ["ppt", "pptx", "pdf"],
    }

    def __init__(
        self,
        default_freshness_days: int = 365,
        max_site_operators: int = 4,
        enable_freshness: bool = True,
        enable_filetype: bool = True,
        enable_intitle: bool = True,
    ):
        """
        Args:
            default_freshness_days: Días hacia atrás para filtro after: (default 1 año)
            max_site_operators: Máximo operadores site: por query
            enable_freshness: Activar filtros temporales automáticos
            enable_filetype: Activar filtros filetype automáticos
            enable_intitle: Activar intitle: para términos clave
        """
        self.default_freshness_days = default_freshness_days
        self.max_site_operators = max_site_operators
        self.enable_freshness = enable_freshness
        self.enable_filetype = enable_filetype
        self.enable_intitle = enable_intitle
        
        # Compilar patrones de intención
        self._intent_patterns_compiled = {
            intent: [re.compile(p, re.IGNORECASE) for p in patterns]
            for intent, patterns in self.TECHNICAL_INTENT_PATTERNS.items()
        }
    
    def build(
        self,
        natural_query: str,
        intent: Optional[str] = None,
        target_domains: Optional[List[str]] = None,
        freshness_days: Optional[int] = None,
        filetypes: Optional[List[str]] = None,
        require_intitle: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
        exclude_terms: Optional[List[str]] = None,
    ) -> BuiltQuery:
        """
        Construye una query optimizada con operadores de indexación.
        
        Args:
            natural_query: Query en lenguaje natural del usuario
            intent: Intención detectada ("especificacion", "comparativa", "implementacion", "debugging", "version", "seguridad")
            target_dominios: Dominios objetivo para site: (sobrescribe auto-detección)
            freshness_days: Días hacia atrás para filtro after:
            filetypes: Extensiones de archivo para filetype:
            require_intitle: Términos obligatorios en título
            exclude_domains: Dominios a excluir con -site:
            exclude_terms: Términos a excluir con -
            
        Returns:
            BuiltQuery con query final y metadatos
        """
        components: List[QueryComponent] = []
        operators_used: Set[GoogleOperator] = set()
        target_domains_final: List[str] = []
        freshness_filter: Optional[str] = None
        filetype_filter: Optional[str] = None
        
        # 1. Detectar intención si no se proporciona
        if intent is None:
            intent = self._detect_intent(natural_query)
        
        # 2. Términos base (query natural limpia)
        base_terms = self._extract_base_terms(natural_query)
        for term in base_terms:
            components.append(QueryComponent(operator=None, value=term))
        
        # 3. OPERADOR SITE: - Dominios autorizados
        if target_domains:
            domains_to_use = target_domains
        else:
            domains_to_use = self._select_authoritative_domains(natural_query, intent)
        
        if domains_to_use:
            domains_limited = domains_to_use[:self.max_site_operators]
            target_domains_final = domains_limited
            # Agrupar en paréntesis con OR
            site_group = "site_group"
            for i, domain in enumerate(domains_limited):
                components.append(QueryComponent(
                    operator=GoogleOperator.SITE,
                    value=domain,
                    group=site_group
                ))
            operators_used.add(GoogleOperator.SITE)
        
        # 3b. EXCLUSIONES DE DOMINIO (-site:)
        if exclude_domains:
            for domain in exclude_domains:
                components.append(QueryComponent(
                    operator=GoogleOperator.SITE,
                    value=domain,
                    is_negative=True
                ))
        
        # 4. OPERADOR INTITLE: - Términos en título (H1/H2)
        if self.enable_intitle:
            intitle_terms = require_intitle or self._extract_intitle_terms(natural_query, intent)
            for term in intitle_terms[:3]:  # Máx 3 intitle
                components.append(QueryComponent(
                    operator=GoogleOperator.INTITLE,
                    value=term
                ))
                operators_used.add(GoogleOperator.INTITLE)
        
        # 5. OPERADOR FILETYPE: - Tipos de archivo técnicos
        if self.enable_filetype and filetypes:
            for ft in filetypes[:2]:  # Máx 2 filetype
                components.append(QueryComponent(
                    operator=GoogleOperator.FILETYPE,
                    value=ft
                ))
                operators_used.add(GoogleOperator.FILETYPE)
                filetype_filter = ft
        
        # 6. FILTRO DE FRESCURA (after:/before:)
        if self.enable_freshness:
            days = freshness_days or self.default_freshness_days
            from datetime import datetime, timedelta
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            components.append(QueryComponent(
                operator=GoogleOperator.AFTER,
                value=cutoff_date
            ))
            operators_used.add(GoogleOperator.AFTER)
            freshness_filter = f"after:{cutoff_date}"
        
        # 7. EXCLUSIONES DE TÉRMINOS (-)
        if exclude_terms:
            for term in exclude_terms:
                components.append(QueryComponent(
                    operator=None,
                    value=term,
                    is_negative=True
                ))
        
        # 8. Construir query final
        raw_query = self._assemble_query(components)
        
        # Estimar precisión basada en operadores usados
        precision = self._estimate_precision(operators_used, len(target_domains_final), len(base_terms))
        
        return BuiltQuery(
            raw_query=raw_query,
            components=components,
            operators_used=operators_used,
            estimated_precision=precision,
            target_domains=target_domains_final,
            freshness_filter=freshness_filter,
            filetype_filter=filetype_filter,
            metadata={
                "intent": intent,
                "base_terms": base_terms,
                "builder_version": self.VERSION,
                "operators_count": len(operators_used),
            }
        )
    
    def _detect_intent(self, query: str) -> str:
        """Detecta intención técnica principal de la query."""
        scores = {}
        for intent, patterns in self._intent_patterns_compiled.items():
            scores[intent] = sum(1 for p in patterns if p.search(query))
        
        if not scores or max(scores.values()) == 0:
            return "general"
        return max(scores, key=scores.get)
    
    def _extract_base_terms(self, query: str) -> List[str]:
        """Extrae términos base significativos de la query."""
        stopwords = {
            'de', 'la', 'el', 'en', 'y', 'a', 'un', 'una', 'por', 'para', 'con', 'sin',
            'sobre', 'entre', 'hacia', 'desde', 'hasta', 'bajo', 'tras', 'durante',
            'mediante', 'según', 'con', 'del', 'al', 'lo', 'las', 'los', 'unas',
            'este', 'esta', 'estos', 'estas', 'ese', 'esa', 'esos', 'esas',
            'qué', 'cuál', 'cómo', 'por qué', 'cuándo', 'dónde', 'quién',
            'the', 'and', 'or', 'for', 'to', 'in', 'on', 'at', 'by', 'with',
            'what', 'which', 'how', 'why', 'when', 'where', 'who',
        }
        
        # Extraer palabras (incluyendo términos con guiones, puntos, números)
        words = re.findall(r'\b[\w\-\.\+]+\b', query.lower())
        
        terms = []
        for w in words:
            if w not in stopwords and len(w) > 2:
                # Preservar términos técnicos compuestos
                if any(c.isdigit() for c in w) or '.' in w or '-' in w or '+' in w:
                    terms.append(w)
                elif len(w) > 3:
                    terms.append(w)
        
        return terms[:8]  # Máximo 8 términos base
    
    def _select_authoritative_domains(self, query: str, intent: str) -> List[str]:
        """Selecciona dominios autorizados basados en query e intención."""
        query_lower = query.lower()
        selected = []
        
        # Mapeo de palabras clave a dominios (extendido desde executor)
        domain_mapping = {
            # ARM
            'arm': ['developer.arm.com', 'arm.com'],
            'armv9': ['developer.arm.com', 'arm.com'],
            'mte': ['developer.arm.com', 'arm.com'],
            'cca': ['developer.arm.com', 'arm.com'],
            'sve2': ['developer.arm.com', 'arm.com'],
            'rme': ['developer.arm.com', 'arm.com'],
            # RISC-V
            'riscv': ['riscv.org', 'github.com', 'sifive.com'],
            'risc-v': ['riscv.org', 'github.com'],
            'rvv': ['riscv.org', 'github.com', 'sifive.com'],
            'vector': ['riscv.org', 'github.com', 'sifive.com'],
            # NVIDIA
            'nvidia': ['nvidia.com', 'developer.nvidia.com', 'docs.nvidia.com'],
            'rtx': ['nvidia.com', 'developer.nvidia.com'],
            'geforce': ['nvidia.com', 'developer.nvidia.com'],
            'ada lovelace': ['nvidia.com', 'developer.nvidia.com'],
            'cuda': ['developer.nvidia.com', 'nvidia.com'],
            'tensor core': ['developer.nvidia.com', 'nvidia.com'],
            # Python
            'python': ['python.org', 'docs.python.org', 'peps.python.org', 'realpython.com'],
            # Rust
            'rust': ['rust-lang.org', 'doc.rust-lang.org'],
            # Go
            'go': ['golang.org', 'pkg.go.dev'],
            'golang': ['golang.org', 'pkg.go.dev'],
            # Linux/Kernel
            'linux': ['kernel.org', 'lwn.net'],
            'kernel': ['kernel.org', 'lwn.net'],
            # Hardware
            'gpu': ['nvidia.com', 'amd.com', 'anandtech.com', 'tomshardware.com'],
            'cpu': ['intel.com', 'amd.com', 'anandtech.com'],
            'especificaciones': ['anandtech.com', 'tomshardware.com', 'phoronix.com'],
            'specs': ['anandtech.com', 'tomshardware.com', 'phoronix.com'],
            # Kubernetes/Cloud
            'kubernetes': ['kubernetes.io', 'cncf.io', 'github.com'],
            'k8s': ['kubernetes.io', 'cncf.io'],
            'docker': ['docker.com', 'docs.docker.com', 'github.com'],
            'terraform': ['terraform.io', 'github.com'],
        }
        
        # Buscar coincidencias
        for term, domains in domain_mapping.items():
            if term in query_lower:
                for d in domains:
                    if d not in selected:
                        selected.append(d)
        
        # Fallback por intención
        if not selected:
            intent_domains = {
                "especificacion": self.AUTHORITATIVE_DOMAINS["documentacion_oficial"] + self.AUTHORITATIVE_DOMAINS["oficiales"],
                "comparativa": self.AUTHORITATIVE_DOMAINS["tecnicos_especializados"] + self.AUTHORITATIVE_DOMAINS["oficiales"],
                "implementacion": self.AUTHORITATIVE_DOMAINS["documentacion_oficial"] + ["github.com", "gitlab.com"],
                "debugging": ["stackoverflow.com", "github.com", "gitlab.com"] + self.AUTHORITATIVE_DOMAINS["documentacion_oficial"],
                "version": self.AUTHORITATIVE_DOMAINS["oficiales"] + self.AUTHORITATIVE_DOMAINS["documentacion_oficial"],
                "seguridad": self.AUTHORITATIVE_DOMAINS["oficiales"] + ["github.com", "gitlab.com"],
            }
            if intent in intent_domains:
                selected = intent_domains[intent][:self.max_site_operators]
        
        return selected[:self.max_site_operators]
    
    def _extract_intitle_terms(self, query: str, intent: str) -> List[str]:
        """Extrae términos que deberían estar en el título (H1/H2)."""
        # Términos técnicos clave que suelen estar en títulos de páginas autorizadas
        technical_title_terms = {
            "especificacion": ["architecture", "specification", "reference manual", "datasheet", "technical reference"],
            "comparativa": ["comparison", "benchmark", "versus", "vs", "performance"],
            "implementacion": ["tutorial", "guide", "how to", "implementation", "getting started"],
            "debugging": ["error", "fix", "solution", "troubleshooting", "debug"],
            "version": ["release notes", "changelog", "what's new", "version"],
            "seguridad": ["security", "vulnerability", "hardening", "best practices"],
        }
        
        terms = technical_title_terms.get(intent, [])
        
        # También extraer sustantivos técnicos de la query
        query_nouns = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', query)
        terms.extend(query_nouns[:2])
        
        return list(dict.fromkeys(terms))[:3]  # Únicos, máx 3
    
    def _assemble_query(self, components: List[QueryComponent]) -> str:
        """Ensambla componentes en query final con agrupación lógica."""
        parts = []
        groups: Dict[str, List[str]] = {}
        
        for comp in components:
            prefix = "-" if comp.is_negative else ""
            
            if comp.operator:
                op_config = OPERATOR_CONFIGS.get(comp.operator)
                if op_config:
                    syntax = op_config.syntax
                    if comp.operator == GoogleOperator.AROUND:
                        # AROUND requiere sintaxis especial: term1 AROUND(n) term2
                        # Simplificado: no soportar AROUND en ensamblaje automático por ahora
                        continue
                    value = comp.value
                    # Comillas para frases multi-palabra en intitle/intext
                    if comp.operator in (GoogleOperator.INTITLE, GoogleOperator.INTEXT) and ' ' in value:
                        value = f'"{value}"'
                    part = f"{prefix}{syntax}{value}"
                else:
                    part = f"{prefix}{comp.value}"
            else:
                # Término libre
                value = comp.value
                if ' ' in value:
                    value = f'"{value}"'
                part = f"{prefix}{value}"
            
            if comp.group:
                groups.setdefault(comp.group, []).append(part)
            else:
                parts.append(part)
        
        # Agregar grupos con paréntesis y OR
        for group_parts in groups.values():
            if len(group_parts) > 1:
                parts.append(f"({' OR '.join(group_parts)})")
            else:
                parts.extend(group_parts)
        
        return ' '.join(parts)
    
    def _estimate_precision(
        self, 
        operators: Set[GoogleOperator], 
        num_domains: int, 
        num_terms: int
    ) -> float:
        """Estima precisión de la query (0.0-1.0)."""
        base = 0.3
        
        # Bonus por operadores de alta precisión
        op_weights = {
            GoogleOperator.SITE: 0.2,
            GoogleOperator.INTITLE: 0.15,
            GoogleOperator.FILETYPE: 0.1,
            GoogleOperator.INURL: 0.08,
            GoogleOperator.AFTER: 0.05,
            GoogleOperator.BEFORE: 0.05,
        }
        
        for op in operators:
            base += op_weights.get(op, 0.05)
        
        # Bonus por dominios específicos
        base += min(num_domains * 0.05, 0.15)
        
        # Bonus por términos base
        base += min(num_terms * 0.02, 0.1)
        
        return min(base, 0.95)
    
    def build_variants(self, natural_query: str, intent: Optional[str] = None) -> List[BuiltQuery]:
        """
        Genera variantes de query en cascada: específica -> media -> amplia.
        Útil para búsqueda en cascada si la específica no retorna resultados.
        """
        variants = []
        
        # Variante 1: Específica (todos los operadores)
        variants.append(self.build(natural_query, intent=intent))
        
        # Variante 2: Media (site + intitle, sin filetype/freshness)
        if self.enable_filetype or self.enable_freshness:
            builder_medium = QueryBuilder(
                default_freshness_days=self.default_freshness_days,
                max_site_operators=self.max_site_operators,
                enable_freshness=False,
                enable_filetype=False,
                enable_intitle=self.enable_intitle,
            )
            variants.append(builder_medium.build(natural_query, intent=intent))
        
        # Variante 3: Amplia (solo site: con dominios genéricos)
        builder_broad = QueryBuilder(
            default_freshness_days=self.default_freshness_days,
            max_site_operators=2,
            enable_freshness=False,
            enable_filetype=False,
            enable_intitle=False,
        )
        variants.append(builder_broad.build(natural_query, intent=intent))
        
        return variants


def create_query_builder(
    default_freshness_days: int = 365,
    max_site_operators: int = 4,
) -> QueryBuilder:
    """Factoría para QueryBuilder configurado."""
    return QueryBuilder(
        default_freshness_days=default_freshness_days,
        max_site_operators=max_site_operators,
    )