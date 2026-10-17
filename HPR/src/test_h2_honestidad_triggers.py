"""Pruebas de regresión — H2: honestidad de los handlers de trigger.

Corrige la deshonestidad funcional de tres triggers de `src/main.py` que
afirmaban trabajo realizado sin respaldo:

  * N1 · Búsqueda Cognitiva    -> "Búsqueda cognitiva ejecutada sobre el último turno."
  * N2 · Grafo de Consistencia -> "Grafo de consistencia verificado: no se detectaron conflictos."
  * MotorRazonamientoSuperior  -> "Síntesis de sesión <id> con <N> turnos." (cadena literal)

Estándar aplicado (Hoja de Ruta · H2): el contrato honesto ya adoptado en
WEB_SEARCH (`estado="no_disponible"` + declaración explícita de que NO se generan
resultados simulados). El éxito del endpoint se DERIVA del estado (G.2):
`estado == "no_disponible"` => success=False.

Se prueba el handler interno `_execute_trigger_internal` (no el endpoint HTTP)
porque `log_execution(...)` —la escritura del log de la bóveda— vive en el
endpoint (`src/main.py:1472`); así el conjunto queda con BOVEDA_INTACTA.

Reglas (Constitución HPR): deterministas, sin red real, sin mocks, sin azar.
"""

import asyncio
import sys
from pathlib import Path
from uuid import UUID

# Convención del proyecto: HPR/ y HPR/src/ en sys.path (ver test_etapa_d.py).
_HPR_DIR = Path(__file__).resolve().parent.parent
_SRC_DIR = _HPR_DIR / "src"
for _path in (str(_HPR_DIR), str(_SRC_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from src.main import _execute_trigger_internal, get_session_manager
from src.models.contracts import TurnRole, TurnType
from src.schemas import TriggerExecutionRequest, TriggerType


def _ejecutar(trigger: TriggerType, session_id: UUID = None, **kwargs):
    """Ejecuta el handler interno con el manager REAL (en memoria, sin mocks)."""
    request = TriggerExecutionRequest(trigger=trigger, confidence_level=1, **kwargs)
    if session_id is not None:
        # El handler resuelve la sesión contra el manager real, cuyas claves son UUID.
        request.session_id = session_id  # asignación sin validación (modelo no frozen)
    return asyncio.run(_execute_trigger_internal(request))


def _sesion_con_turnos(n: int) -> UUID:
    """Crea una sesión REAL (SessionManager real, en memoria) con `n` turnos."""
    mgr = get_session_manager()
    session = mgr.create_session(
        initial_query="consulta de prueba H2",
        title="H2 · honestidad de triggers",
    )
    for i in range(n):
        mgr.add_turn(
            session_id=session.id,
            role=TurnRole.USER,
            content=f"turno {i + 1} de prueba",
            turn_type=TurnType.QUERY,
        )
    return session.id


# ---------------------------------------------------------------------------
# N1 · Búsqueda Cognitiva
# ---------------------------------------------------------------------------

def test_n1_sin_turnos_no_afirma_busqueda() -> None:
    """N1 sin turnos: no debe afirmar ninguna búsqueda realizada."""
    resultado = _ejecutar(TriggerType.N1_BUSQUEDA, payload="filtro")
    assert resultado["estado"] == "no_disponible"
    assert resultado["resultados"] == []
    assert "simulad" in resultado["mensaje"].lower()
    assert "ejecutada" not in resultado["mensaje"].lower()


def test_n1_con_turnos_no_afirma_busqueda_ejecutada() -> None:
    """N1 con turnos: usa el último turno como contexto, pero NO finge haber buscado."""
    session_id = _sesion_con_turnos(1)
    resultado = _ejecutar(TriggerType.N1_BUSQUEDA, session_id=session_id, payload="filtro x")
    assert resultado["estado"] == "no_disponible"
    assert resultado["filtro_usuario"] == "filtro x"
    assert resultado["query"] == "turno 1 de prueba"
    assert "ejecutada" not in resultado["mensaje"].lower()
    assert "simulad" in resultado["mensaje"].lower()


# ---------------------------------------------------------------------------
# N2 · Grafo de Consistencia
# ---------------------------------------------------------------------------

def test_n2_con_dos_turnos_no_finge_verificacion() -> None:
    """N2 con >= 2 turnos: no debe afirmar que el grafo quedó 'verificado'."""
    session_id = _sesion_con_turnos(2)
    resultado = _ejecutar(TriggerType.N2_GRAFO, session_id=session_id)
    assert resultado["estado"] == "no_disponible"
    assert resultado["turnos_analizados"] == 2
    assert "verificado" not in resultado["mensaje"].lower()
    assert "simulad" in resultado["mensaje"].lower()


# ---------------------------------------------------------------------------
# MotorRazonamientoSuperior
# ---------------------------------------------------------------------------

def test_motor_razon_no_fabrica_sintesis() -> None:
    """MotorRazonamientoSuperior: no debe devolver una 'síntesis' inexistente."""
    session_id = _sesion_con_turnos(1)
    resultado = _ejecutar(TriggerType.MOTOR_RAZON, session_id=session_id, payload="foco")
    assert resultado["estado"] == "no_disponible"
    assert resultado["sintesis"] is None
    assert resultado["foco_usuario"] == "foco"
    assert "no disponible" in resultado["mensaje"].lower()
    assert "simulad" in resultado["mensaje"].lower()


# ---------------------------------------------------------------------------
# Coherencia con G.2 y con el estándar WEB_SEARCH
# ---------------------------------------------------------------------------

def test_estado_de_los_tres_triggers_implica_no_exito() -> None:
    """Coherencia con G.2: los tres estados deben impedir un falso éxito."""
    for trigger in (TriggerType.N1_BUSQUEDA, TriggerType.N2_GRAFO, TriggerType.MOTOR_RAZON):
        resultado = _ejecutar(trigger)
        assert resultado.get("estado") in ("error", "no_disponible"), (
            f"{trigger.value} derivaría un falso éxito (estado={resultado.get('estado')!r})"
        )


def test_web_search_sigue_siendo_el_estandar_honesto() -> None:
    """Regresión: WEB_SEARCH (el estándar de H2) permanece honesto."""
    resultado = _ejecutar(TriggerType.WEB_SEARCH, payload="normativa hpr")
    assert resultado["estado"] == "no_disponible"
    assert "simulad" in resultado["mensaje"].lower()
