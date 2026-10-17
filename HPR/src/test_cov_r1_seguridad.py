"""Cobertura R1 (P5.2) — Seguridad, Sovereign Gate y Contratos.

Cierra las brechas críticas de la ruta R1 (Constitución HPR) SIN tocar el
código de producción de ``src/``:

- ``src/security_agent.py``: ``sovereign_gate_validation`` (Capa 0 arroba,
  strings vacíos, patrones restrictivos), ``_pasaje_mas_relevante`` /
  ``_terminos`` y las ramas de ``_ejecutar_busqueda_web``.
- ``src/core/engine.py``: ramas no cubiertas de ``evaluar_intencion_externa``
  y ``triage_query`` (vacía, SEGURIDAD, sin señales).
- ``src/validador_niveles_confianza.py``: clasificación de fuentes faltante.
- ``src/main.py``: denegación de NEXUS-ROOT en triggers y contrato de
  ``_execute_trigger_internal`` por tipo de trigger.

Reglas aplicadas (Constitución HPR):
- P3: deterministas — sin red real (todo ``requests.get`` se intercepta),
  sin reloj en las aserciones y sin depender del estado global mutable
  (el gestor de sesiones se sustituye por dobles controlados).
- P4: se atacan los casos negativos (denegación, error de red, validador
  caído, trigger no soportado, entradas vacías/maliciosas).
- P7: no mutan — no escriben en la bóveda ni en datos reales.
"""

import asyncio
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Convención de ejecución del proyecto (ver run.py): HPR/ y HPR/src/ en path.
# ---------------------------------------------------------------------------
_HPR_DIR = Path(__file__).resolve().parent.parent
_SRC_DIR = _HPR_DIR / "src"
for _p in (str(_HPR_DIR), str(_SRC_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from src.core.engine import evaluar_intencion_externa, triage_query  # noqa: E402
from src.main import _execute_trigger_internal, app  # noqa: E402
from src.models.contracts import CategoriaConsulta, NivelRiesgo  # noqa: E402
from src.schemas import TriggerExecutionRequest, TriggerType  # noqa: E402
from src.security_agent import HPRSecurityEngine  # noqa: E402
from src.validador_niveles_confianza import ValidadorNivelesConfianza  # noqa: E402


# ===========================================================================
# A · Sovereign Gate (security_agent.sovereign_gate_validation)
# ===========================================================================

@pytest.fixture(scope="module")
def motor() -> HPRSecurityEngine:
    """Motor real (bóveda local leída una sola vez, uso read-only)."""
    return HPRSecurityEngine()


def test_sovereign_gate_capa0_arroba_otorga_paso(motor: HPRSecurityEngine) -> None:
    """Capa 0: un trigger sintáctico con prefijo @ tiene precedencia soberana."""
    assert motor.sovereign_gate_validation("@web_search algo") is True
    assert motor.sovereign_gate_validation("@hpr_confianza") is True


@pytest.mark.parametrize(
    "payload",
    ["<script>alerta</script>", "DROP TABLE usuarios", "OVERRIDE_ROOT ahora"],
)
def test_sovereign_gate_rechaza_patrones_restrictivos(
    motor: HPRSecurityEngine, payload: str
) -> None:
    """Capa 1: los patrones de ingesta maliciosa se rechazan."""
    assert motor.sovereign_gate_validation(payload) is False


@pytest.mark.parametrize("payload", ["", "   ", "\t\n "])
def test_sovereign_gate_rechaza_entradas_vacias(
    motor: HPRSecurityEngine, payload: str
) -> None:
    """Capa 1: payload vacío o solo espacios -> rechazado."""
    assert motor.sovereign_gate_validation(payload) is False


def test_sovereign_gate_acepta_consulta_limpia(motor: HPRSecurityEngine) -> None:
    """Capa 2: consulta legítima sin patrones -> permitida."""
    assert motor.sovereign_gate_validation("consulta legítima del operador") is True


# ===========================================================================
# B · _pasaje_mas_relevante / _terminos (security_agent)
# ===========================================================================

def _motor_con_boveda(texto: str) -> HPRSecurityEngine:
    """Instancia real con una bóveda controlada (evita leer la bóveda real)."""
    instancia = HPRSecurityEngine()
    instancia.knowledge_base = texto
    return instancia


def test_pasaje_mas_relevante_elige_mayor_puntaje() -> None:
    """Selecciona el pasaje con más coincidencias e ignora líneas vacías."""
    motor_kb = _motor_con_boveda("\nalpha beta gamma\n\nbeta solo\n")
    assert motor_kb._pasaje_mas_relevante("beta gamma") == "alpha beta gamma"


def test_pasaje_mas_relevante_sin_coincidencias_devuelve_none() -> None:
    """Sin términos coincidentes el puntaje es 0 -> None (no inventar pasaje)."""
    motor_kb = _motor_con_boveda("contenido totalmente distinto")
    assert motor_kb._pasaje_mas_relevante("zzzzwwww") is None


def test_pasaje_mas_relevante_boveda_vacia_devuelve_none() -> None:
    """Bóveda vacía -> None aunque existan términos."""
    motor_kb = _motor_con_boveda("")
    assert motor_kb._pasaje_mas_relevante("consulta larga") is None


def test_pasaje_mas_relevante_sin_terminos_devuelve_none() -> None:
    """Consulta sin términos válidos -> None."""
    motor_kb = _motor_con_boveda("contenido")
    assert motor_kb._pasaje_mas_relevante("a b c") is None


def test_terminos_filtra_menores_de_cuatro() -> None:
    """``_terminos`` es determinista y descarta palabras cortas."""
    assert HPRSecurityEngine._terminos("¿Qué es la bóveda HPR?") == ["bóveda"]
    assert HPRSecurityEngine._terminos("") == []


# ===========================================================================
# C · _ejecutar_busqueda_web (security_agent) — sin red real
# ===========================================================================

class _RespuestaFalsa:
    """Doble de una respuesta HTTP de requests: solo expone ``.json()``."""

    def __init__(self, datos: dict) -> None:
        self._datos = datos

    def json(self) -> dict:
        return self._datos


class _ValidadorFijo:
    """Validador de niveles que devuelve siempre el nivel indicado."""

    def __init__(self, nivel: int) -> None:
        self._nivel = nivel

    def clasificar_fuente(self, origen: str, contenido: str, es_oficial: bool = False) -> dict:
        return {"nivel": self._nivel, "etiqueta": "etiqueta", "estado": "estado"}


class _ValidadorQueFalla:
    """Validador que siempre lanza: prueba la degradación a Nivel 3."""

    def clasificar_fuente(self, *args, **kwargs) -> dict:
        raise RuntimeError("validador caído")


def _interceptar_get(monkeypatch, datos: dict) -> None:
    """Sustituye ``requests.get`` por un doble (sin red real, P3)."""
    monkeypatch.setattr("requests.get", lambda *a, **k: _RespuestaFalsa(datos))


def test_ejecutar_busqueda_web_error_de_red(motor: HPRSecurityEngine, monkeypatch) -> None:
    """Fallo de red -> estado transparente, sin inventar datos."""
    def _boom(*args, **kwargs):
        raise ConnectionError("sin red")

    monkeypatch.setattr("requests.get", _boom)
    resultado = motor._ejecutar_busqueda_web("consulta")
    assert "Error de red" in resultado["estado"]
    assert resultado["requiere_web"] is False
    assert resultado["nivel_confianza"] == 3


def test_ejecutar_busqueda_web_sin_resultados(motor: HPRSecurityEngine, monkeypatch) -> None:
    """Sin datos externos -> se informa; prohibido fabricar resultados."""
    _interceptar_get(monkeypatch, {"Abstract": "", "Answer": "", "Description": ""})
    resultado = motor._ejecutar_busqueda_web("consulta")
    assert "No he encontrado" in resultado["estado"]
    assert resultado["nivel_confianza"] == 3


def test_ejecutar_busqueda_web_nivel2_contenido_suficiente(
    motor: HPRSecurityEngine, monkeypatch
) -> None:
    """Contenido >= 40 caracteres -> validación real lo clasifica Nivel 2."""
    _interceptar_get(monkeypatch, {"Abstract": "x" * 80})
    resultado = motor._ejecutar_busqueda_web("consulta")
    assert resultado["nivel_confianza"] == 2
    assert "Nivel 2" in resultado["estado"]


def test_ejecutar_busqueda_web_nivel3_contenido_corto(
    motor: HPRSecurityEngine, monkeypatch
) -> None:
    """Contenido insuficiente -> Nivel 3 (baja confianza)."""
    _interceptar_get(monkeypatch, {"Abstract": "corto"})
    resultado = motor._ejecutar_busqueda_web("consulta")
    assert resultado["nivel_confianza"] == 3
    assert resultado["requiere_web"] is True


def test_ejecutar_busqueda_web_nivel1_fuente_oficial(
    motor: HPRSecurityEngine, monkeypatch
) -> None:
    """Fuente clasificada Nivel 1 -> se inyecta como validada."""
    _interceptar_get(monkeypatch, {"Abstract": "x" * 80})
    monkeypatch.setattr(motor, "validador", _ValidadorFijo(1))
    resultado = motor._ejecutar_busqueda_web("consulta")
    assert resultado["nivel_confianza"] == 1
    assert "Nivel 1" in resultado["estado"]


def test_ejecutar_busqueda_web_validador_falla_degrada_a_nivel3(
    motor: HPRSecurityEngine, monkeypatch
) -> None:
    """Si el validador falla -> se asume Nivel 3 y se informa transparentemente."""
    _interceptar_get(monkeypatch, {"Abstract": "x" * 80})
    monkeypatch.setattr(motor, "validador", _ValidadorQueFalla())
    resultado = motor._ejecutar_busqueda_web("consulta")
    assert resultado["nivel_confianza"] == 3


# ===========================================================================
# D · core/engine.py — evaluar_intencion_externa y triage_query
# ===========================================================================

def test_evaluar_intencion_sin_terminos() -> None:
    """Consulta sin términos reconocidos -> no requiere externa."""
    resultado = evaluar_intencion_externa("a b c", "")
    assert resultado["requiere_externa"] is False
    assert resultado["justificación"] == "consulta sin términos reconocidos"


def test_evaluar_intencion_senales_externas_bajo_overlap() -> None:
    """Señales de externalidad + bóveda vacía (overlap 0.0) -> externa."""
    resultado = evaluar_intencion_externa("noticias recientes", "")
    assert resultado["requiere_externa"] is True


def test_evaluar_intencion_trigger_arroba() -> None:
    """Trigger con prefijo @ -> externa directa por sintaxis determinista."""
    resultado = evaluar_intencion_externa("buscar @web_search algo", "")
    assert resultado["requiere_externa"] is True
    assert "Trigger de prefijo arroba" in resultado["justificación"]


def test_evaluar_intencion_patron_confianza() -> None:
    """Patrón explícito de confianza sin señales externas -> externa condicional."""
    resultado = evaluar_intencion_externa("aplicar niveles de confianza", "")
    assert resultado["requiere_externa"] is True
    assert "Patrón de activación de confianza" in resultado["justificación"]


def test_evaluar_intencion_overlap_suficiente_no_requiere_externa() -> None:
    """Señales externas cubiertas por la bóveda (overlap 1.0) -> interna suficiente."""
    resultado = evaluar_intencion_externa("noticias del motor hpr", "noticias motor hpr")
    assert resultado["requiere_externa"] is False
    assert "Información interna suficiente" in resultado["justificación"]


def test_triage_vacia_es_desconocida() -> None:
    """Consulta vacía -> DESCONOCIDA (precaución)."""
    resultado = triage_query("")
    assert resultado.categoria is CategoriaConsulta.DESCONOCIDA
    assert resultado.razones == ["consulta vacía"]


def test_triage_patron_soberano_es_seguridad() -> None:
    """Patrón de ingesta maliciosa -> SEGURIDAD / crítico (regresión R1-fix)."""
    resultado = triage_query("<script>alerta</script>")
    assert resultado.categoria is CategoriaConsulta.SEGURIDAD
    assert resultado.nivel_riesgo is NivelRiesgo.CRITICO


def test_triage_sin_senales_reconocidas_es_desconocida() -> None:
    """Consulta sin señales ni necesidad externa -> DESCONOCIDA."""
    resultado = triage_query("noticias del motor hpr", "noticias motor hpr")
    assert resultado.categoria is CategoriaConsulta.DESCONOCIDA
    assert resultado.razones == ["sin señales reconocidas"]


# ===========================================================================
# E · validador_niveles_confianza.py
# ===========================================================================

def test_validador_nivel1_es_oficial() -> None:
    """Fuente marcada explícitamente como oficial -> Nivel 1."""
    resultado = ValidadorNivelesConfianza().clasificar_fuente("web", "x", es_oficial=True)
    assert resultado["nivel"] == 1


def test_validador_nivel1_origen_ceo() -> None:
    """Origen del repositorio CEO -> Nivel 1."""
    resultado = ValidadorNivelesConfianza().clasificar_fuente(
        "ceo_knowledge_base", "x", es_oficial=False
    )
    assert resultado["nivel"] == 1


@pytest.mark.parametrize("contenido", ["", "   ", "corto", " menos de cuarenta caracteres "])
def test_validador_nivel3_contenido_insuficiente(contenido: str) -> None:
    """Contenido vacío o < 40 caracteres -> Nivel 3."""
    resultado = ValidadorNivelesConfianza().clasificar_fuente("web_search", contenido)
    assert resultado["nivel"] == 3


def test_validador_nivel2_contenido_suficiente() -> None:
    """Contenido >= 40 caracteres no oficial -> Nivel 2."""
    resultado = ValidadorNivelesConfianza().clasificar_fuente("web_search", "x" * 40)
    assert resultado["nivel"] == 2


# ===========================================================================
# F · main.py — NEXUS-ROOT y contrato de _execute_trigger_internal
# ===========================================================================

@pytest.fixture(scope="module")
def client() -> TestClient:
    """Cliente en proceso (sin red real)."""
    return TestClient(app)


class _TurnoFalso:
    def __init__(self, contenido: str) -> None:
        self.content = contenido


class _ContextoFalso:
    def __init__(self, temas=None, ambiguedades=None) -> None:
        self.active_topics = list(temas or [])
        self.unresolved_ambiguities = list(ambiguedades or [])

    def model_dump(self, mode: str = "json") -> dict:
        return {"active_topics": self.active_topics}


class _SesionFalsa:
    def __init__(self, turnos=None) -> None:
        self.id = "sesion-falsa"
        self.turns = list(turnos or [])


class _ManagerFalso:
    """Doble del gestor de sesiones: control total, sin estado global (P3)."""

    def __init__(self, sesion: "_SesionFalsa", contexto: "_ContextoFalso | None" = None) -> None:
        self._sesion = sesion
        self._contexto = contexto or _ContextoFalso()

    def get_session(self, session_id):
        return self._sesion

    def create_session(self, **kwargs):
        return self._sesion

    def get_session_context(self, session_id):
        return self._contexto


@pytest.fixture
def manager_falso(monkeypatch):
    """Instala un gestor de sesiones controlado en ``src.main``."""
    def _instalar(sesion: "_SesionFalsa", contexto: "_ContextoFalso | None" = None) -> None:
        monkeypatch.setattr("src.main.get_session_manager", lambda: _ManagerFalso(sesion, contexto))

    return _instalar


def test_trigger_denegado_por_nexus_root(client: TestClient, monkeypatch) -> None:
    """Si NEXUS-ROOT no valida la identidad -> acceso denegado (no es éxito)."""
    monkeypatch.setattr("src.main.nexus_root_validation", lambda estado: False)

    respuesta = client.post(
        "/api/v1/trigger", json={"trigger": "@nivel1", "confidence_level": 1}
    )
    assert respuesta.status_code == 200

    datos = respuesta.json()
    assert datos["success"] is False
    assert datos["error_message"] == (
        "Acceso denegado: la identidad del sistema no pudo ser verificada."
    )
    assert datos["telemetry"]["auth_failed"] is True
    assert datos["result"] is None


def test_trigger_interno_web_search_sin_query_es_error(manager_falso) -> None:
    """@web_search sin payload ni parámetro query -> error honesto."""
    manager_falso(_SesionFalsa())
    resultado = asyncio.run(
        _execute_trigger_internal(
            TriggerExecutionRequest(trigger=TriggerType.WEB_SEARCH)
        )
    )
    assert resultado["estado"] == "error"
    assert "término de búsqueda" in resultado["mensaje"]


def test_trigger_interno_web_search_con_query_no_disponible(manager_falso) -> None:
    """Sin proveedor externo -> no_disponible (no se simulan fuentes)."""
    manager_falso(_SesionFalsa())
    resultado = asyncio.run(
        _execute_trigger_internal(
            TriggerExecutionRequest(trigger=TriggerType.WEB_SEARCH, payload="normativa hpr")
        )
    )
    assert resultado["estado"] == "no_disponible"
    assert resultado["query"] == "normativa hpr"


def test_trigger_interno_n1_busqueda_sin_turnos(manager_falso) -> None:
    """N1 · Búsqueda Cognitiva con sesión vacía -> sin resultados."""
    manager_falso(_SesionFalsa([]))
    resultado = asyncio.run(
        _execute_trigger_internal(
            TriggerExecutionRequest(trigger=TriggerType.N1_BUSQUEDA, payload="filtro")
        )
    )
    assert resultado["resultados"] == []
    assert resultado["mensaje"] == "La sesión no tiene turnos para buscar."


def test_trigger_interno_n1_busqueda_con_turnos(manager_falso) -> None:
    """N1 con turnos -> usa el último turno como consulta y el filtro del usuario."""
    manager_falso(_SesionFalsa([_TurnoFalso("primer turno de la sesión")]))
    resultado = asyncio.run(
        _execute_trigger_internal(
            TriggerExecutionRequest(
                trigger=TriggerType.N1_BUSQUEDA, session_id="s-1", payload="filtro x"
            )
        )
    )
    assert resultado["query"] == "primer turno de la sesión"
    assert resultado["filtro_usuario"] == "filtro x"
    assert resultado["resultados"] == []


def test_trigger_interno_n2_grafo_con_dos_turnos(manager_falso) -> None:
    """N2 · Grafo de Consistencia con >= 2 turnos -> analiza y reporta."""
    manager_falso(_SesionFalsa([_TurnoFalso("a"), _TurnoFalso("b")]))
    resultado = asyncio.run(
        _execute_trigger_internal(TriggerExecutionRequest(trigger=TriggerType.N2_GRAFO))
    )
    assert resultado["turnos_analizados"] == 2
    assert resultado["conflictos"] == []


def test_trigger_interno_motor_razon_sintetiza(manager_falso) -> None:
    """Motor de razonamiento superior -> síntesis con temas y ambigüedades."""
    manager_falso(
        _SesionFalsa([_TurnoFalso("t")]),
        _ContextoFalso(temas=["alpha"], ambiguedades=["beta"]),
    )
    resultado = asyncio.run(
        _execute_trigger_internal(
            TriggerExecutionRequest(trigger=TriggerType.MOTOR_RAZON, payload="foco")
        )
    )
    assert resultado["temas_activos"] == ["alpha"]
    assert resultado["ambiguedades"] == ["beta"]
    assert resultado["foco_usuario"] == "foco"


def test_trigger_interno_sovereign_gate_verificado(manager_falso) -> None:
    """SOVEREIGN-GATE (directo) -> verificación de soberanía confirmada."""
    manager_falso(_SesionFalsa())
    resultado = asyncio.run(
        _execute_trigger_internal(TriggerExecutionRequest(trigger=TriggerType.SOVEREIGN_GATE))
    )
    assert resultado["estado"] == "verificado"
    assert resultado["soberania"] == "confirmada"
    assert resultado["ingestión_permitida"] is True


class _TriggerNoSoportado:
    value = "trigger-no-soportado"


class _RequestNoSoportado:
    """Petición que viola el contrato tipado (solo se usa para el doble)."""

    trigger = _TriggerNoSoportado()
    session_id = None
    payload = None
    parameters: dict = {}
    confidence_level = 1


def test_trigger_interno_no_soportado_lanza_valueerror(manager_falso) -> None:
    """Contrato defensivo: un trigger fuera del enum -> ValueError."""
    manager_falso(_SesionFalsa())
    with pytest.raises(ValueError, match="Trigger no soportado"):
        asyncio.run(_execute_trigger_internal(_RequestNoSoportado()))
