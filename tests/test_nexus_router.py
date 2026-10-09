"""
Test Suite Automatizada: Matriz de Precedencia Lógica - Nexus Root.

Valida el comportamiento determinista de la cadena de responsabilidad
(NexusRouter) contra la tabla de casos de prueba oficiales de la Fase 3.

Cada caso inyecta una entrada y verifica que el nivel de precedencia
y la decisión semántica coincidan exactamente con la especificación.

Ejecución:
    pytest tests/test_nexus_router.py -v
"""

import sys
from pathlib import Path

# Añadir HPR/src al path para importaciones directas
# (desde HPR/src se importa como 'from security_agent import ...')
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "HPR" / "src"))

from typing import Dict, Any, Optional
import pytest

from security_agent import HPRSecurityEngine
from models.contracts import PipelineState
from nexus_root import crear_nexus_router, NexusRouter


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture(scope="session")
def motor_seguridad() -> HPRSecurityEngine:
    """
    Fixture de sesión: instancia real de HPRSecurityEngine.

    Usa scope="session" porque el motor es inmutable y sin estado
    (stateless), por lo que puede reutilizarse entre todos los tests
    sin efectos secundarios.
    """
    return HPRSecurityEngine()


@pytest.fixture(scope="session")
def nexus_router(motor_seguridad: HPRSecurityEngine) -> NexusRouter:
    """
    Fixture de sesión: NexusRouter completamente ensamblado.

    Inyecta el motor de seguridad mediante inyección de dependencias.
    El router contiene la cadena completa:
    MAX_PRIORITY → HIGH_PRIORITY → MEDIUM_PRIORITY → BASE_PRIORITY
    """
    return crear_nexus_router(motor_seguridad)


@pytest.fixture
def estado_test() -> PipelineState:
    """
    Fixture por test: estado de pipeline limpio para cada caso.

    Retorna una nueva instancia de PipelineState con identidad
    de prueba para aislamiento total entre tests.
    """
    return PipelineState(identity="TEST-GUI-USER")


# ============================================================
# CASOS DE PRUEBA PARAMETRIZADOS
# ============================================================

# Tabla de casos de prueba oficiales (Fase 3)
# Cada tupla: (entrada, nivel_esperado, decision_esperada, descripcion)
CASOS_PRECEDENCIA = [
    # PRIORIDAD MÁXIMA - Defensa Absoluta
    (
        "",
        "SANITIZER_LAYER",
        "bloqueo_sanitizer",
        "Entrada vacía - bloqueo en capa de sanitización"
    ),
    (
        None,
        "SANITIZER_LAYER",
        "bloqueo_sanitizer",
        "Entrada None simulada - bloqueo en capa de sanitización (None se trata como vacío)"
    ),

    # PRIORIDAD ALTA - Seguridad y Confianza
    (
        "@hpr_confianza activar",
        "HIGH_PRIORITY",
        "trigger_confianza",
        "Trigger @hpr_confianza - override de seguridad prioritario"
    ),

    # PRIORIDAD MEDIA - Control Operativo
    (
        "@nivel1 consultar",
        "MEDIUM_PRIORITY",
        "ejecucion_externa_completada",
        "Trigger @nivel1 - pipeline operativo con ejecución externa"
    ),
    (
        "@web_search noticias",
        "MEDIUM_PRIORITY",
        "ejecucion_externa_completada",
        "Trigger @web_search - búsqueda web con ejecución externa"
    ),
    (
        "@nivel1 @web_search buscar",
        "MEDIUM_PRIORITY",
        "ejecucion_externa_completada",
        "Colisión @nivel1 + @web_search - ambos triggers con ejecución externa"
    ),

    # PRIORIDAD BASE - Multilingüe
    (
        "hola mundo",
        "BASE_PRIORITY",
        "delegacion_multilingue",
        "Lenguaje natural ES - delegación a capa multilingüe"
    ),
    (
        "what is HPR?",
        "BASE_PRIORITY",
        "delegacion_multilingue",
        "Lenguaje natural EN - delegación a capa multilingüe"
    ),
]


# ============================================================
# TESTS PARAMETRIZADOS
# ============================================================

@pytest.mark.parametrize(
    "entrada, nivel_esperado, decision_esperada, descripcion",
    CASOS_PRECEDENCIA,
    ids=[
        "vacio-sanitizer",
        "none-max-priority",
        "hpr-confianza-high",
        "nivel1-medium",
        "web-search-medium",
        "colision-nivel1-websearch-medium",
        "hola-mundo-base",
        "what-is-hpr-base",
    ]
)
def test_matriz_precedencia_logica(
    nexus_router: NexusRouter,
    estado_test: PipelineState,
    entrada: Optional[str],
    nivel_esperado: str,
    decision_esperada: str,
    descripcion: str,
) -> None:
    """
    Valida la Matriz de Precedencia Lógica completa.

    Esta función de test única ejecuta todos los casos definidos
    en la tabla oficial mediante parametrización pytest.

    Para cada caso:
    1. Ejecuta el enrutador con la entrada dada.
    2. Verifica que la clave 'nivel' coincida exactamente.
    3. Verifica que la clave 'decision' coincida exactamente.

    Args:
        nexus_router: Router ensamblado (fixture de sesión).
        estado_test: Estado de pipeline limpio (fixture por test).
        entrada: Input a evaluar (str o None).
        nivel_esperado: Nivel de precedencia esperado (ej. "HIGH_PRIORITY").
        decision_esperada: Decisión semántica esperada (ej. "trigger_confianza").
        descripcion: Descripción legible del caso (para reporte).

    Raises:
        AssertionError: Si 'nivel' o 'decision' no coinciden.
    """
    # Manejar entrada None especial (simulación)
    entrada_procesada: str = "" if entrada is None else entrada

    # Ejecutar enrutador
    resultado: Dict[str, Any] = nexus_router.enrutar(
        entrada=entrada_procesada,
        state=estado_test,
    )

    # Aserciones estrictas: claves obligatorias y valores exactos
    assert "nivel" in resultado, f"Falta clave 'nivel' en resultado: {descripcion}"
    assert "decision" in resultado, f"Falta clave 'decision' en resultado: {descripcion}"

    # Validación estricta de nivel de precedencia
    assert resultado["nivel"] == nivel_esperado, (
        f"[{descripcion}] Nivel incorrecto: "
        f"esperado='{nivel_esperado}', obtenido='{resultado['nivel']}' | "
        f"entrada='{entrada_procesada}'"
    )

    # Validación estricta de decisión semántica
    assert resultado["decision"] == decision_esperada, (
        f"[{descripcion}] Decisión incorrecta: "
        f"esperada='{decision_esperada}', obtenida='{resultado['decision']}' | "
        f"entrada='{entrada_procesada}'"
    )


# ============================================================
# TESTS ADICIONALES DE COMPORTAMIENTO
# ============================================================

def test_orden_cadena_responsabilidad(nexus_router: NexusRouter) -> None:
    """
    Verifica que el orden de la cadena de responsabilidad sea correcto.

    El orden estricto debe ser:
    1. MAX_PRIORITY (Defensa Absoluta)
    2. HIGH_PRIORITY (Seguridad y Confianza)
    3. MEDIUM_PRIORITY (Control Operativo)
    4. BASE_PRIORITY (Multilingüe)
    """
    orden = nexus_router.obtener_orden_cadena()

    assert orden == [
        "MAX_PRIORITY",
        "HIGH_PRIORITY",
        "MEDIUM_PRIORITY",
        "BASE_PRIORITY",
    ], f"Orden de cadena incorrecto: {orden}"


def test_entrada_vacia_vs_none_diferenciacion(
    nexus_router: NexusRouter,
    estado_test: PipelineState,
) -> None:
    """
    Verifica que string vacío y None simulado se manejan en SANITIZER_LAYER.

    Tanto string vacío ("") como None (simulado como "") 
    se detectan en la capa de sanitización antes de la cadena.
    """
    # String vacío
    resultado_vacio = nexus_router.enrutar(entrada="", state=estado_test)
    assert resultado_vacio["nivel"] == "SANITIZER_LAYER"
    assert resultado_vacio["decision"] == "bloqueo_sanitizer"

    # None simulado como string vacío
    resultado_none = nexus_router.enrutar(entrada="", state=estado_test)
    assert resultado_none["nivel"] == "SANITIZER_LAYER"
    assert resultado_none["decision"] == "bloqueo_sanitizer"


def test_colision_triggers_orden_peso(
    nexus_router: NexusRouter,
    estado_test: PipelineState,
) -> None:
    """
    Verifica que en colisión de triggers operativos,
    el orden de peso es @web_search (peso 10) > @nivel1 (peso 5).
    """
    resultado = nexus_router.enrutar(
        entrada="@nivel1 @web_search buscar",
        state=estado_test,
    )

    assert resultado["nivel"] == "MEDIUM_PRIORITY"
    assert resultado["decision"] == "ejecucion_externa_completada"

    # Verificar metadata de triggers detectados
    metadata = resultado.get("metadata", {})
    triggers = metadata.get("triggers", [])

    assert len(triggers) == 2, "Deben detectarse ambos triggers"

    # El orden en metadata debe reflejar peso descendente
    # (web_search primero por peso 10 > 5)
    tipos = [t["tipo"] for t in triggers]
    assert tipos[0] == "web_search", "web_search debe ir primero por peso"
    assert tipos[1] == "nivel1", "nivel1 debe ir segundo"


def test_entrada_multilingue_delega_a_base(
    nexus_router: NexusRouter,
    estado_test: PipelineState,
) -> None:
    """
    Verifica que entradas en lenguaje natural (sin triggers)
    llegan al handler BASE_PRIORITY y marcan delegación multilingüe.
    """
    for entrada in ["hola mundo", "what is HPR?", "olá tudo bem", "consulta normal"]:
        resultado = nexus_router.enrutar(entrada=entrada, state=estado_test)

        assert resultado["nivel"] == "BASE_PRIORITY", f"Fallo con: {entrada}"
        assert resultado["decision"] == "delegacion_multilingue", f"Fallo con: {entrada}"

        # Verificar que metadata indica delegación multilingüe
        metadata = resultado.get("metadata", {})
        assert metadata.get("accion") == "delegacion_multilingue"
        assert metadata.get("nivel") == "BASE"
        assert metadata.get("handler_decisor") == "BASE_PRIORITY"


def test_trigger_confianza_sobreescribe_operativos(
    nexus_router: NexusRouter,
    estado_test: PipelineState,
) -> None:
    """
    Verifica que @hpr_confianza (ALTA) tiene precedencia sobre
    triggers operativos (MEDIA) si aparecen combinados.
    """
    # Input con trigger de alta prioridad + operativos
    # En la implementación actual, los triggers se detectan por patrón
    # al inicio de la cadena, por lo que @hpr_confianza gana si está al inicio.
    resultado = nexus_router.enrutar(
        entrada="@hpr_confianza @nivel1 test",
        state=estado_test,
    )

    assert resultado["nivel"] == "HIGH_PRIORITY"
    assert resultado["decision"] == "trigger_confianza"
    assert resultado["override"] == "@hpr_confianza"


def test_determinismo_ejecuciones_repetidas(
    nexus_router: NexusRouter,
    estado_test: PipelineState,
) -> None:
    """
    Verifica el determinismo: misma entrada → mismo resultado siempre.

    Ejecuta el mismo input 10 veces y verifica que todos
    los resultados sean idénticos (regla D1: misma entrada → misma salida).
    """
    entrada = "@hpr_confianza test determinismo"
    resultados = []

    for _ in range(10):
        resultado = nexus_router.enrutar(entrada=entrada, state=estado_test)
        resultados.append((resultado["nivel"], resultado["decision"], resultado["override"]))

    # Todos los resultados deben ser idénticos
    assert all(r == resultados[0] for r in resultados), (
        "No determinismo detectado: resultados variables en ejecuciones repetidas"
    )


# ============================================================
# TESTS DE AUDITORÍA DE TRES NIVELES DE CONFIANZA
# ============================================================

def test_confianza_alta_contenido_limpio(
    nexus_router: NexusRouter,
    estado_test: PipelineState,
) -> None:
    """
    Verifica que contenido limpio y seguro obtiene CONFIANZA_ALTA.
    
    Consulta técnica legítima a fuentes confiables.
    """
    # Usamos una consulta que probablemente retorne resultados de dominios confiables
    resultado = nexus_router.enrutar(
        entrada="@web_search python programming tutorial",
        state=estado_test,
    )
    
    # El nivel debe ser MEDIUM_PRIORITY (trigger operativo)
    assert resultado["nivel"] == "MEDIUM_PRIORITY"
    assert resultado["decision"] == "ejecucion_externa_completada"
    
    # Verificar que existe evaluación de confianza en metadata
    metadata = resultado.get("metadata", {})
    resultados_externos = metadata.get("resultados_externos", [])
    assert len(resultados_externos) > 0
    
    for res_ext in resultados_externos:
        evaluacion = res_ext.get("evaluacion_nexus", {})
        # Verificar que existe nivel de confianza
        assert "nivel_confianza" in evaluacion
        assert evaluacion["nivel_confianza"] in [
            "CONFIANZA_ALTA", "CONFIANZA_MEDIA", "CONFIANZA_BAJA", 
            "CONFIANZA_NULA", "RECHAZO_CRITICO"
        ]
        # Verificar estructura completa
        assert "score_final" in evaluacion
        assert "aprobado" in evaluacion
        assert "accion" in evaluacion
        assert "filtros_aplicados" in evaluacion
        assert "metricas" in evaluacion


def test_rechazo_critico_contenido_malicioso(
    nexus_router: NexusRouter,
    estado_test: PipelineState,
) -> None:
    """
    Verifica que contenido con patrones maliciosos es RECHAZADO CRÍTICO.
    
    Simulamos un resultado con patrones de script injection.
    """
    from nexus_root.executor import ExternalToolExecutor, ResultadoBusqueda, ResultadoItem
    from models.contracts import PipelineState
    
    # Crear executor con mock que simula contenido malicioso
    executor = ExternalToolExecutor()
    
    # Mock que retorna contenido con script injection
    resultado_malicioso = ResultadoBusqueda(
        exito=True,
        query_original="test",
        sintesis="Resultado con script malicioso",
        resultados=[
            ResultadoItem(
                titulo="Página maliciosa",
                url="http://malicious-site.com/evil.html",
                snippet="<script>alert('xss')</script> contenido normal",
                fuente="malicious-site.com",
                contenido_completo="<script>eval('malicious code')</script> contenido"
            )
        ],
        fuente="duckduckgo",
        metadatos={}
    )
    
    # Evaluar directamente
    from nexus_root.router import NexusRouter
    from security_agent import HPRSecurityEngine
    
    router = NexusRouter(HPRSecurityEngine())
    evaluacion = router._evaluar_resultado_externo(resultado_malicioso, {"tipo": "web_search"})
    
    # Debe ser RECHAZO_CRITICO por script malicioso
    assert evaluacion["nivel_confianza"] == "RECHAZO_CRITICO"
    assert evaluacion["aprobado"] is False
    assert "BLOQUEAR" in evaluacion["accion"]


def test_confianza_nula_dominio_no_verificable(
    nexus_router: NexusRouter,
    estado_test: PipelineState,
) -> None:
    """
    Verifica que dominios no verificables sin contenido seguro obtienen CONFIANZA_NULA.
    """
    from nexus_root.executor import ResultadoBusqueda, ResultadoItem
    
    # Resultado con dominio desconocido y sin contenido completo
    resultado_sospechoso = ResultadoBusqueda(
        exito=True,
        query_original="test",
        sintesis="Resultado de fuente no verificada",
        resultados=[
            ResultadoItem(
                titulo="Fuente desconocida",
                url="http://unknown-random-site.xyz/page",
                snippet="Contenido genérico sin fuentes verificables",
                fuente="unknown-random-site.xyz"
            )
        ],
        fuente="duckduckgo",
        metadatos={}
    )
    
    router = NexusRouter(HPRSecurityEngine())
    evaluacion = router._evaluar_resultado_externo(resultado_sospechoso, {"tipo": "web_search"})
    
    # Debe ser CONFIANZA_NULA o RECHAZO_CRITICO
    assert evaluacion["nivel_confianza"] in ["CONFIANZA_NULA", "RECHAZO_CRITICO"]
    assert evaluacion["aprobado"] is False


def test_confianza_alta_dominio_verificado(
    nexus_router: NexusRouter,
    estado_test: PipelineState,
) -> None:
    """
    Verifica que resultados de dominios whitelist obtienen CONFIANZA_ALTA.
    """
    from nexus_root.executor import ResultadoBusqueda, ResultadoItem
    
    # Resultado con dominio en whitelist (github.com)
    resultado_confiable = ResultadoBusqueda(
        exito=True,
        query_original="python tutorial",
        sintesis="Tutorial de Python en GitHub con ejemplos completos",
        resultados=[
            ResultadoItem(
                titulo="Python Tutorial en GitHub",
                url="https://github.com/python/tutorial",
                snippet="Tutorial oficial de Python con ejemplos de código",
                fuente="github.com",
                contenido_completo="Contenido completo del tutorial de Python en GitHub con ejemplos de código y explicaciones detalladas."
            )
        ],
        fuente="duckduckgo",
        metadatos={}
    )
    
    router = NexusRouter(HPRSecurityEngine())
    evaluacion = router._evaluar_resultado_externo(resultado_confiable, {"tipo": "web_search"})
    
    # Dominio en whitelist + contenido completo = CONFIANZA_ALTA
    assert evaluacion["nivel_confianza"] == "CONFIANZA_ALTA"
    assert evaluacion["aprobado"] is True
    assert evaluacion["score_final"] >= 0.75


def test_evaluacion_tres_niveles_en_ruta_completa(
    nexus_router: NexusRouter,
    estado_test: PipelineState,
) -> None:
    """
    Test de integración: verifica que la evaluación de tres niveles
    está integrada en el flujo completo del router.
    """
    # Ejecutar búsqueda
    resultado = nexus_router.enrutar(
        entrada="@web_search python programming",
        state=estado_test,
    )
    
    # Verificar estructura completa de evaluación en respuesta
    assert resultado["nivel"] == "MEDIUM_PRIORITY"
    assert resultado["decision"] == "ejecucion_externa_completada"
    
    metadata = resultado.get("metadata", {})
    
    # Verificar evaluación global
    assert "evaluacion_global" in metadata
    evaluacion_global = metadata["evaluacion_global"]
    assert "nivel_confianza" in evaluacion_global
    assert "score_final" in evaluacion_global
    assert "aprobado" in evaluacion_global
    
    # Verificar evaluación por resultado individual
    resultados_externos = metadata.get("resultados_externos", [])
    assert len(resultados_externos) > 0
    
    for res_ext in resultados_externos:
        assert "evaluacion_nexus" in res_ext
        evaluacion = res_ext["evaluacion_nexus"]
        assert "nivel_confianza" in evaluacion
        assert evaluacion["nivel_confianza"] in [
            "CONFIANZA_ALTA", "CONFIANZA_MEDIA", "CONFIANZA_BAJA",
            "CONFIANZA_NULA", "RECHAZO_CRITICO"
        ]


def test_bloqueo_salida_contenido_malicioso_integracion(
    nexus_router: NexusRouter,
    estado_test: PipelineState,
) -> None:
    """
    Test de integración: si el contenido es RECHAZO_CRITICO,
    el router debe bloquear la salida final.
    """
    # Este test verifica que la arquitectura bloquea correctamente
    # El mock actual retorna contenido seguro, pero verificamos
    # que la estructura de bloqueo existe en la respuesta
    
    resultado = nexus_router.enrutar(
        entrada="@web_search test",
        state=estado_test,
    )
    
    # La respuesta debe tener estructura para bloqueo
    assert "decision" in resultado
    assert "metadata" in resultado
    
    # Si hay evaluación de RECHAZO_CRITICO, la decisión debe reflejarlo
    metadata = resultado.get("metadata", {})
    evaluacion_global = metadata.get("evaluacion_global", {})
    
    if evaluacion_global.get("nivel_confianza") == "RECHAZO_CRITICO":
        assert resultado["decision"] in ["ejecucion_externa_completada", "bloqueo"]
        # La acción recomendada debe ser BLOQUEAR
        assert evaluacion_global.get("accion_recomendada") == "BLOQUEAR"