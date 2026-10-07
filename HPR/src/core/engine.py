"""Motor lógico central del HPR: validaciones puras y deterministas.

Reglas de la Constitución:
- D1: misma entrada -> misma salida; funciones puras sin efectos secundarios.
- D2: sin reloj, red ni azar en el camino crítico.
- D5: la identidad del sistema es inmutable.
- E5: ninguna llamada saliente.

Las tres raíces del motor (Nexus Root, Epsilon Wall, Sovereign Gate)
viven aquí como fuente única de verdad; el adaptador
``src/security_agent.py`` delega en este módulo.
"""

import re

from ..models.contracts import (
    IDENTIDAD_DETERMINISTA,
    EstadoPipeline,
    PipelineRequest,
    PipelineResult,
    CategoriaConsulta,
    NivelRiesgo,
    TriageResult,
)

#: Patrones de ingesta bloqueados por la Sovereign Gate (Regla P4).
PATRONES_SOVEREIGN_GATE = ("<script>", "DROP TABLE", "OVERRIDE_ROOT")

#: Señales deterministas que indican necesidad de información externa (actualidad, tecnología).
SEÑALES_EXTERNAS = (
    "actualidad", "noticias", "última", "hoy", "2024", "2025", "2026",
    "tecnología",
    "lanzamiento", "versión", "actualizar", "tendencia", "desarrollo", "investigación",
    "web", "internet", "internacional", "mercado", "stock", "precio",
)

#: Umbral de cobertura de bóveda interna (porcentaje). Si la consulta contiene
#: señales externas y la bóveda no cubre el tema, se activa búsqueda web.
UMBRAL_COBERTURA_BOVDA = 0.3  # 30% de términos deben estar ausentes en la bóveda

#: Trigger sintáctico determinista: prefijo arroba (@) para activar búsqueda externa condicional.
#: Formato: @identificador (ej. @hpr_confianza, @nivel1, @web_search).
#: La presencia de un trigger @ validado activa REQUIRE_EXTERNA automáticamente,
#: bypassing overlap checks para búsquedas confiables bajo los 3 niveles de confianza.
TRIGGER_ARROBA_PATTERN = re.compile(r"^@\w+|\s@\w+")

#: Mensajes terminales del pipeline (fuente única de verdad).
MENSAJE_BLOQUEO_SOVEREIGN_GATE = (
    "BLOQUEO DE SEGURIDAD: SOVEREIGN-GATE: Entrada bloqueada por seguridad."
)
MENSAJE_DENEGACION_NEXUS_ROOT = "Acceso denegado por Nexus Root."
MENSAJE_PIPELINE_VERIFICADO = "Pipeline verificado con éxito."


def sovereign_gate_validation(incoming_payload: str | None) -> bool:
    """Regla 3 (Sovereign Gate): control de ingesta y mitigación de entradas maliciosas."""
    if not incoming_payload or len(incoming_payload.strip()) == 0:
        return False
    return not any(pattern in incoming_payload for pattern in PATRONES_SOVEREIGN_GATE)


def nexus_root_validation(system_state: dict, nexus_identity: str = IDENTIDAD_DETERMINISTA) -> bool:
    """Regla 1 (Nexus Root): valida la identidad inmutable y el propósito del sistema."""
    return system_state.get("identity") == nexus_identity


def epsilon_wall_validation(response_content: str, ground_truth: list[str]) -> bool:
    """Regla 2 (Epsilon Wall): filtro anti-alucinación basado en verificación estricta."""
    return all(term in response_content for term in ground_truth)


def evaluar_intencion_externa(consulta: str, knowledge_base: str) -> dict:
    """Evalúa si una consulta requiere búsqueda web externa (Regla D1/D2).

    Flujo:
    1. Extrae términos de la consulta (mínimo 4 caracteres).
    2. Verifica presencia de señales de externalidad (actualidad, tecnología, etc.).
    3. Calcula overlap con la knowledge base.
    4. Si hay señales externas y bajo overlap → requiere búsqueda web.

    Retorna dict con:
    - requiere_externa: bool
    - nivel_riesgo: NivelRiesgo
    - justificación: str
    """
    import re
    terminos = [
        termino
        for termino in re.findall(r"\w+", consulta.lower())
        if len(termino) >= 4
    ]

    if not terminos:
        return {
            "requiere_externa": False,
            "nivel_riesgo": "bajo",
            "justificación": "consulta sin términos reconocidos",
        }

    # Verifica señales de externalidad
    senales_externas = [t for t in terminos if t in SEÑALES_EXTERNAS]

    # NUEVO: Detección de trigger sintáctico con prefijo arroba (@)
    # Si el payload incluye un trigger @ validado (ej. @hpr_confianza),
    # activa REQUIRE_EXTERNA de forma directa y sin ambigüedades.
    trigger_match = TRIGGER_ARROBA_PATTERN.search(consulta)
    trigger_validado = trigger_match is not None
    trigger_ident = trigger_match.group(0) if trigger_match else None

    # NUEVO: Patrones explícitos de activación de confianza conditional
    # Estos patrones indican que el usuario quiere búsqueda externa a pesar
    # de que el conocimiento interno pueda ser suficiente
    PATRONES_CONFIANZA = [
        "tres niveles de confianza",
        "niveles de confianza",
        "grados de confianza",
        "politica de confianza",
        "umbral de confianza",
        "confianza conditional",
        "busqueda con confianza",
        "consultar con nivel",
    ]
    patrones_coincidentes = [p for p in PATRONES_CONFIANZA if p in consulta.lower()]

    # Calcula overlap con knowledge base
    if knowledge_base:
        kb_terminos = set(
            termino.lower() for termino in re.findall(r"\w+", knowledge_base)
        )
        overlap = len([t for t in terminos if t in kb_terminos]) / len(terminos)
    else:
        overlap = 0.0

    # Lógica de decisión ENMENDADA
    # 1. TRIGGER ARROBA (@) validado → REQUIRE_EXTERNA directo (primer trigger estándar)
    if trigger_validado:
        return {
            "requiere_externa": True,
            "nivel_riesgo": "medio",
            "justificación": f"Trigger de prefijo arroba detectado: {trigger_ident}. Búsqueda externa activada por sintaxis determinista.",
        }

    # 2. Señales de externalidad tradicionales + bajo overlap
    if senales_externas and overlap < UMBRAL_COBERTURA_BOVDA:
        return {
            "requiere_externa": True,
            "nivel_riesgo": "medio",
            "justificación": f"Señales de externalidad detectadas + bajo overlap bóveda ({overlap:.0%})",
        }

    # 3. Sin señales externas pero SÍ patrón de activación de confianza → externa condicional
    if not senales_externas and patrones_coincidentes:
        # El usuario explícitamente invoca el framework de confianza
        # → permitir búsqueda externa con validación de niveles
        return {
            "requiere_externa": True,
            "nivel_riesgo": "medio",
            "justificación": f"Patrón de activación de confianza detectado: {', '.join(patrones_coincidentes)}. Búsqueda externa condicional activada.",
        }

    # 3. Sin señales externas SIN patrón de confianza → verificar overlap
    if not senales_externas and overlap < 0.5:
        # Consulta desconocida sin señales externas → también considerar externa
        return {
            "requiere_externa": True,
            "nivel_riesgo": "medio",
            "justificación": f"Sin señales reconocidas + bajo overlap bóveda ({overlap:.0%})",
        }

    # 4. Caso general: información interna suficiente
    return {
        "requiere_externa": False,
        "nivel_riesgo": "bajo",
        "justificación": f"Información interna suficiente (overlap {overlap:.0%})",
    }


def triage_query(consulta: str | None, knowledge_base: str = "") -> TriageResult:
    """Clasificación determinista de consultas (D1: misma entrada, misma salida).

    Orden de reglas (primero lo más crítico):
    1. Ingesta maliciosa (patrones Sovereign Gate) -> SEGURIDAD/CRÍTICO.
    2. Phishing (guardia de seguridad) -> SEGURIDAD/ALTO.
    3. Señales operativas -> OPERATIVA/BAJO.
    4. Señales de conocimiento -> CONOCIMIENTO/BAJO.
    5. Señales de externalidad -> CONSULTAR WEB/MEDIO.
    6. Sin señales reconocidas -> DESCONOCIDA/MEDIO (precaución).
    """
    texto = (consulta or "").strip()

    if not texto:
        return TriageResult(
            categoria=CategoriaConsulta.DESCONOCIDA,
            nivel_riesgo="medio",
            razones=["consulta vacía"],
        )

    # 1. Patrones Sovereign Gate
    patron = next((p for p in PATRONES_SOVEREIGN_GATE if p in texto), None)
    if patron is not None:
        return TriageResult(
            categoria=CategoriaConsulta.SEGURIDAD,
            nivel_riesgo="crítico",
            razones=[f"patrón de ingesta bloqueado detectado: {patron}"],
        )

    # 2. Phishing
    from .security_agent import inspect_for_phishing
    if inspect_for_phishing(texto):
        return TriageResult(
            categoria=CategoriaConsulta.SEGURIDAD,
            nivel_riesgo="alto",
            razones=["coincidencia con patrón de phishing"],
        )

    # 3. Señales operativas
    señales_operativas = ("estado", "estatus", "en línea", "latencia", "rendimiento", "salud")
    senales = [s for s in señales_operativas if s in texto.lower()]
    if senales:
        return TriageResult(
            categoria=CategoriaConsulta.OPERATIVA,
            nivel_riesgo="bajo",
            razones=[f"señal operativa: {s}" for s in senales],
        )

    # 4. Señales de conocimiento
    señales_conocimiento = ("qué", "cuál", "cómo", "por qué", "cuándo", "dónde", "quién")
    senales = [s for s in señales_conocimiento if s in texto.lower()]
    if senales:
        return TriageResult(
            categoria=CategoriaConsulta.CONOCIMIENTO,
            nivel_riesgo="bajo",
            razones=[f"señal de conocimiento: {s}" for s in senales],
        )

    # 5. Evaluar intencion externa
    eval_externa = evaluar_intencion_externa(consulta, knowledge_base)
    if eval_externa["requiere_externa"]:
        return TriageResult(
            categoria=CategoriaConsulta.CONOCIMIENTO,
            nivel_riesgo=eval_externa["nivel_riesgo"],
            razones=[eval_externa["justificación"]],
        )

    # 6. Sin señales reconocidas
    return TriageResult(
        categoria=CategoriaConsulta.DESCONOCIDA,
        nivel_riesgo="medio",
        razones=["sin señales reconocidas"],
    )
