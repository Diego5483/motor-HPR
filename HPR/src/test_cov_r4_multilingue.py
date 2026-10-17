"""Cobertura R4 (P5.5) — Capa multilingüe HPR (detección, selector y router).

Cierra las brechas residuales del bloque R4 (Constitución HPR) SIN tocar ``src/``:

- ``src/multilingual/detector.py`` · ``detectar_idioma`` (es/en/pt/unknown) y
  sus contratos léxicos.
- ``src/multilingual/selector.py`` · ``render_selector_idioma`` y
  ``actualizar_idioma_por_detector`` (con doble de Streamlit, sin runtime real).
- ``src/multilingual/router.py`` · ``set_engine``, ``obtener_idioma_actual`` y
  ``procesar_con_idioma`` (con motor inyectado, sin red).
- ``src/multilingual/__init__.py`` · superficie pública del paquete.

Reglas aplicadas (Constitución HPR):
- P3: determinismo estricto — dobles de Streamlit y del motor; cero red, cero
  runtime de UI, cero azar.
- P4: se atacan los caminos de fallo (motor caído, sin motor inyectado, sin
  runtime de Streamlit, ``toast`` no disponible, consulta sin señales).
- P7: no mutan — el estado global ``_engine`` del router se restaura siempre.

DEFECTO DEMOSTRADO (R4) — ``src/multilingual/router.py:117``:
referencia a ``IDIOMA_JUSTIFICACIONES``, nombre que **no existe en ningún
módulo** del repositorio. Como el valor por defecto de ``dict.get`` se evalúa
de forma anticipada, la ruta de ÉXITO de ``procesar_con_idioma`` revienta
siempre con ``NameError`` (afecta a ``src/app.py:57``). Se documenta aquí con
un ``xfail(strict=True)`` (contrato correcto) y un caracterizador del fallo
vigente; ambos fuerzan la limpieza de los marcadores cuando se corrija el
código de producción (compuerta R4-FIX).
"""

import sys
from pathlib import Path

import pytest

# Convención del proyecto (ver test_etapa_d.py / test_cov_r3_resiliencia.py).
_HPR_DIR = Path(__file__).resolve().parent.parent
_SRC_DIR = _HPR_DIR / "src"
for _path in (str(_HPR_DIR), str(_SRC_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from src.multilingual import detector, router, selector  # noqa: E402


# ===========================================================================
# Dobles y utilidades de prueba (sin UI real, sin motor real, sin red)
# ===========================================================================

class _MotorOk:
    """Doble del motor de seguridad: respuesta válida de pipeline."""

    def process_pipeline(self, payload=None, state=None, truth=None):
        return {
            "estado": "OK",
            "requiere_externa": False,
            "nivel_confianza": "alto",
            "justificación": "justificacion entregada por el motor",
        }


class _MotorQueFalla:
    """Doble del motor: simula caída del pipeline (sin red)."""

    def process_pipeline(self, payload=None, state=None, truth=None):
        raise RuntimeError("motor caido")


class _EstadoSesionFalso(dict):
    """``st.session_state`` doble: diccionario con ``.get`` y asignación."""


class _SidebarFalso:
    """``st.sidebar`` doble: objeto de contexto."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _StreamlitFalso:
    """Doble mínimo de Streamlit: registra llamadas y devuelve valores fijados."""

    def __init__(self, idioma_inicial="unknown", seleccion=None, toast_falla=False):
        self.session_state = _EstadoSesionFalso()
        self.session_state["idioma_actual"] = idioma_inicial
        self._seleccion = seleccion if seleccion is not None else idioma_inicial
        self._toast_falla = toast_falla
        self.sidebar = _SidebarFalso()
        self.llamadas = []
        self.index_radio = None
        self.opciones_radio = None
        self.opciones_formateadas = None

    def markdown(self, texto, **kwargs):
        self.llamadas.append(("markdown", texto))

    def info(self, texto, **kwargs):
        self.llamadas.append(("info", texto))

    def caption(self, texto, **kwargs):
        self.llamadas.append(("caption", texto))

    def radio(self, etiqueta, options=None, format_func=None, index=None, key=None, help=None):
        self.opciones_radio = list(options)
        self.index_radio = index
        if format_func is not None:
            self.opciones_formateadas = [format_func(k) for k in options]
        self.llamadas.append(("radio", etiqueta))
        return self._seleccion

    def toast(self, texto, **kwargs):
        self.llamadas.append(("toast", texto))
        if self._toast_falla:
            raise RuntimeError("toast no disponible en esta version")


class _ModuloFalso:
    """Módulo doble mínimo: solo expone los atributos indicados."""

    def __init__(self, **atributos):
        self.__dict__.update(atributos)


@pytest.fixture
def streamlit_falso(monkeypatch):
    """Sustituye ``selector.st`` por un doble (sin runtime de Streamlit)."""
    def _instalar(falso):
        monkeypatch.setattr(selector, "st", falso)
        return falso

    return _instalar


@pytest.fixture
def inyectar_motor(monkeypatch):
    """Inyecta un motor doble en el router y restaura el global al terminar."""
    def _instalar(motor):
        monkeypatch.setattr(router, "_engine", motor)
        return motor

    return _instalar


# ===========================================================================
# A · detector.detectar_idioma (autodetección léxica)
# ===========================================================================

@pytest.mark.parametrize(
    "consulta, esperado",
    [
        ("hola, cuánto cuesta el motor", "es"),
        ("hello what is this", "en"),
        ("olá como você está", "pt"),
        ("zzz 123", "unknown"),
        ("", "unknown"),
    ],
)
def test_detectar_idioma(consulta, esperado):
    """Cada idioma se declara por sus señales léxicas; sin señales -> unknown."""
    assert detector.detectar_idioma(consulta) == esperado


def test_detectar_idioma_prioriza_espanol_ante_empate():
    """Precedencia declarada del detector: es > en > pt (detector.py:50-55)."""
    assert detector.detectar_idioma("hello hola") == "es"


def test_detector_contratos_lexicos():
    """Los diccionarios de patrones y justificaciones cubren los 4 idiomas."""
    assert set(detector.PATTERNS_BY_LANGUAGE) == {"es", "en", "pt"}
    assert set(detector.JUSTIFICATIONS) == {"es", "en", "pt", "unknown"}


# ===========================================================================
# B · selector (widget de idioma, con doble de Streamlit)
# ===========================================================================

def test_selector_contrato_idiomas():
    """El selector ofrece exactamente es/en/pt/unknown y su metadata."""
    assert set(selector.IDIOMAS) == {"es", "en", "pt", "unknown"}
    for datos in selector.IDIOMAS.values():
        assert set(datos) == {"nombre", "flag", "nativo"}


def test_render_selector_idioma_autodetect_actualiza_estado(streamlit_falso):
    """Con estado 'unknown' se anuncia autodetección y se fija la selección."""
    falso = streamlit_falso(_StreamlitFalso(idioma_inicial="unknown", seleccion="en"))

    idioma = selector.render_selector_idioma()

    assert idioma == "en"
    assert falso.session_state["idioma_actual"] == "en"
    assert falso.index_radio == 3  # 4ª opción: 'unknown'
    assert ("info", "Idioma: Auto-detectar 🤖") in falso.llamadas
    assert falso.opciones_formateadas[0] == "🇪🇸 Español"


def test_render_selector_idioma_con_idioma_fijado_no_anuncia_autodeteccion(streamlit_falso):
    """Con idioma ya fijado se preselecciona y no se anuncia autodetección."""
    falso = streamlit_falso(_StreamlitFalso(idioma_inicial="pt", seleccion="pt"))

    idioma = selector.render_selector_idioma()

    assert idioma == "pt"
    assert falso.index_radio == 2  # 3ª opción: 'pt'
    assert not [c for c in falso.llamadas if c[0] == "info"]


def test_actualizar_idioma_por_detector_actualiza_y_notifica(streamlit_falso):
    """Idioma 'unknown' + señales -> se fija el idioma y se notifica."""
    falso = streamlit_falso(_StreamlitFalso(idioma_inicial="unknown"))

    resultado = selector.actualizar_idioma_por_detector("hello what is this")

    assert resultado == "en"
    assert falso.session_state["idioma_actual"] == "en"
    assert ("toast", "Idioma auto-detectado: English") in falso.llamadas


def test_actualizar_idioma_por_detector_sin_senales_mantiene_unknown(streamlit_falso):
    """Sin señales claras no se fuerza idioma ni se notifica (honestidad)."""
    falso = streamlit_falso(_StreamlitFalso(idioma_inicial="unknown"))

    resultado = selector.actualizar_idioma_por_detector("zzz 123")

    assert resultado == "unknown"
    assert not [c for c in falso.llamadas if c[0] == "toast"]


def test_actualizar_idioma_por_detector_respeta_idioma_ya_fijado(streamlit_falso):
    """Si el usuario ya eligió idioma, el detector no lo pisa."""
    falso = streamlit_falso(_StreamlitFalso(idioma_inicial="es"))

    resultado = selector.actualizar_idioma_por_detector("hello what is this")

    assert resultado == "es"
    assert falso.session_state["idioma_actual"] == "es"


def test_actualizar_idioma_por_detector_soporta_toast_no_disponible(streamlit_falso):
    """Un fallo del toast no impide la autodetección (selector.py:78-79)."""
    falso = streamlit_falso(_StreamlitFalso(idioma_inicial="unknown", toast_falla=True))

    resultado = selector.actualizar_idioma_por_detector("hello what is this")

    assert resultado == "en"


# ===========================================================================
# C · router (inyección de motor e idioma actual)
# ===========================================================================

def test_set_engine_inyecta_instancia(monkeypatch):
    """``set_engine`` publica la instancia en el global del router."""
    monkeypatch.setattr(router, "_engine", None)
    motor = _MotorOk()

    router.set_engine(motor)

    assert router._engine is motor


def test_obtener_idioma_actual_desde_session_state(monkeypatch):
    """Primera vía: ``streamlit.session_state.SessionState`` (router.py:45-47)."""
    class _SessionState:
        @classmethod
        def get(cls):
            return {"idioma_actual": "pt"}

    monkeypatch.setitem(
        sys.modules, "streamlit.session_state", _ModuloFalso(SessionState=_SessionState)
    )

    assert router.obtener_idioma_actual() == "pt"


def test_obtener_idioma_actual_fallback_a_streamlit(monkeypatch):
    """Segunda vía: ``streamlit.session_state`` global (router.py:50-52)."""
    monkeypatch.setitem(
        sys.modules,
        "streamlit",
        _ModuloFalso(session_state={"idioma_actual": "en"}),
    )
    monkeypatch.delitem(sys.modules, "streamlit.session_state", raising=False)

    assert router.obtener_idioma_actual() == "en"


def test_obtener_idioma_actual_sin_runtime_devuelve_unknown(monkeypatch):
    """Sin runtime de Streamlit -> 'unknown', nunca excepción (router.py:53-54)."""

    class _EstadoQueFalla:
        def get(self, *args, **kwargs):
            raise RuntimeError("sin runtime de streamlit")

    monkeypatch.setitem(
        sys.modules, "streamlit", _ModuloFalso(session_state=_EstadoQueFalla())
    )
    monkeypatch.delitem(sys.modules, "streamlit.session_state", raising=False)

    assert router.obtener_idioma_actual() == "unknown"


# ===========================================================================
# D · router.procesar_con_idioma (pipelines con y sin motor)
# ===========================================================================

def test_procesar_con_idioma_error_del_pipeline_es_honesto(inyectar_motor):
    """Si el pipeline falla, se devuelve el error real con metadatos de idioma."""
    inyectar_motor(_MotorQueFalla())

    resultado = router.procesar_con_idioma("hola", {"identity": "HPR"}, idioma="en")

    assert resultado == {
        "estado": "Error en pipeline: motor caido",
        "idioma": "en",
        "requiere_externa": False,
        "nivel_confianza": "alto",
        "justificación": "Error durante el procesamiento del pipeline",
    }


def test_procesar_con_idioma_autodetecta_antes_del_pipeline(inyectar_motor):
    """Con idioma 'unknown' se autodetecta y se propaga (router.py:83-84)."""
    inyectar_motor(_MotorQueFalla())

    resultado = router.procesar_con_idioma("hello what is this", {"identity": "HPR"})

    assert resultado["idioma"] == "en"
    assert resultado["estado"].startswith("Error en pipeline:")


def test_procesar_con_idioma_instancia_motor_si_no_hay_inyectado(monkeypatch):
    """Sin motor inyectado se construye uno (router.py:87-91)."""
    monkeypatch.setattr(router, "_engine", None)
    monkeypatch.setattr("src.security_agent.HPRSecurityEngine", _MotorQueFalla)

    resultado = router.procesar_con_idioma("consulta", {"identity": "HPR"}, idioma="es")

    assert resultado["estado"].startswith("Error en pipeline:")


@pytest.mark.xfail(
    strict=True,
    reason=(
        "DEFECTO R4: 'IDIOMA_JUSTIFICACIONES' no está definido "
        "(src/multilingual/router.py:117) -> NameError en la ruta de éxito de "
        "procesar_con_idioma. Contrato correcto fijado para la compuerta R4-FIX."
    ),
)
def test_procesar_con_idioma_camino_exitoso_devuelve_contrato(inyectar_motor):
    """Contrato correcto de la ruta de éxito (hoy roto por el NameError)."""
    inyectar_motor(_MotorOk())

    resultado = router.procesar_con_idioma("hola", {"identity": "HPR"})

    assert set(resultado) == {
        "estado",
        "idioma",
        "requiere_externa",
        "nivel_confianza",
        "justificación",
    }
    assert resultado["estado"] == "OK"
    assert resultado["idioma"] == "es"
    assert resultado["requiere_externa"] is False
    assert resultado["nivel_confianza"] == "alto"


def test_procesar_con_idioma_camino_exitoso_falla_por_nameerror(inyectar_motor):
    """Caracteriza el fallo VIGENTE: la ruta de éxito revienta con NameError.

    DEBE ELIMINARSE esta prueba cuando la compuerta R4-FIX corrija
    ``src/multilingual/router.py`` (aquí queda como ancla roja→verde).
    """
    inyectar_motor(_MotorOk())

    with pytest.raises(NameError, match="IDIOMA_JUSTIFICACIONES"):
        router.procesar_con_idioma("hola", {"identity": "HPR"})
