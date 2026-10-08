"""Enrutador de idioma para el pipeline HPR.

Proporciona la función `procesar_con_idioma` que ejecuta el pipeline
seguridad HPR estándar, pero con metadatos adicionales de idioma
para posible uso futuro en traducción de respuestas.

El router inyecta la instancia del motor HPR desde `app.py` para
evitar importaciones circulares y permitir un estado global único.
"""

from typing import Any, Dict, Optional

from src.security_agent import HPRSecurityEngine
from src.models.contracts import PipelineRequest, PipelineState, NivelRiesgo, CategoriaConsulta
from src.multilingual.detector import detectar_idioma


# Instancia global del motor - inyectada desde app.py al inicio
_engine: Optional[HPRSecurityEngine] = None


def set_engine(instance: HPRSecurityEngine) -> None:
    """
    Inyecta la instancia del motor HPR de seguridad.

    Debe llamarse una vez al iniciar la aplicación (después de
    inicializar `st.session_state.engine`) para que el router
    pueda enrutar las llamadas `process_pipeline`.

    Args:
        instance: Instancia de `HPRSecurityEngine` ya configurada.
    """
    global _engine
    _engine = instance


def obtener_idioma_actual() -> str:
    """
    Obtiene el idioma actual desde el estado de sesión de Streamlit.

    Returns:
        str: Código de idioma ('es', 'en', 'pt' o 'unknown').
    """
    # Intentar importar session_state de streamlit de forma segura
    try:
        from streamlit.session_state import SessionState
        return SessionState.get().get("idioma_actual", "unknown")
    except Exception:
        # Fallback: intentar desde el módulo actual
        try:
            import streamlit as st
            return st.session_state.get("idioma_actual", "unknown")
        except Exception:
            return "unknown"


def procesar_con_idioma(
    payload: str,
    state: dict,
    idioma: str = "unknown",
    verdad: list = [],
) -> Dict[str, Any]:
    """
    Procesa una consulta mediante el pipeline HPR, con manejo de idioma.

    Pasos:
    1. Detectar/validar idioma si es 'unknown'
    2. Ejecutar pipeline normal (security_agent.process_pipeline)
    3. Retornar resultado con metadatos de idioma

    Args:
        payload: Texto de entrada del usuario (consulta).
        state: Diccionario de estado del pipeline (identidad, etc.).
        idioma: Código de idioma ('es', 'en', 'pt' o 'unknown').
        verdad: Lista de verdades de referencia para validación.

    Retorna:
        Dict con claves: 'estado', 'idioma', 'requiere_externa',
        'nivel_confianza', 'justificación'.
    """
    global _engine  # FIX: Declara _engine como global para evitar UnboundLocalError
    # 1. Detectar idioma si es 'unknown' usando el detector puro
    if idioma == "unknown":
        idioma = detectar_idioma(payload)

    # 2. Ejecutar pipeline normal si el motor está disponible
    if _engine is None:
        # Si no hay engine inyectado, intentar fallback directo
        # (esto debería ocurrir solo en tests o inicialización temprana)
        from src.security_agent import HPRSecurityEngine
        _engine = HPRSecurityEngine()

    try:
        response = _engine.process_pipeline(
            payload=payload,
            state=state,
            truth=verdad,
        )
    except Exception as e:
        # Si falla el pipeline, retornar estructura de error con idioma
        return {
            "estado": f"Error en pipeline: {str(e)}",
            "idioma": idioma,
            "requiere_externa": False,
            "nivel_confianza": "alto",
            "justificación": "Error durante el procesamiento del pipeline",
        }

    # 3. Construir y retornar resultado con metadata de idioma
    return {
        "estado": response.get("estado", "Sin respuesta"),
        "idioma": idioma,
        "requiere_externa": response.get("requiere_externa", False),
        "nivel_confianza": response.get("nivel_confianza", "medio"),
        "justificación": response.get(
            "justificación",
            IDIOMA_JUSTIFICACIONES.get(idioma, "Procesamiento completado"),
        ),
    }