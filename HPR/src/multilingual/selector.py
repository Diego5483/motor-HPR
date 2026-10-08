"""Selector de idioma para la interfaz Streamlit HPR.

Proporciona un widget en la barra lateral para seleccionar o
auto-detectar el idioma de las consultas del chat.
"""

import streamlit as st
from src.multilingual.detector import detectar_idioma

# Mapeo de idiomas a nombres y banderas
IDIOMAS = {
    "es": {"nombre": "Español", "flag": "🇪🇸", "nativo": "Español"},
    "en": {"nombre": "English", "flag": "🇺🇸", "nativo": "English"},
    "pt": {"nombre": "Português", "flag": "🇧🇷", "nativo": "Português"},
    "unknown": {"nombre": "Auto-detectar", "flag": "🤖", "nativo": "Auto-detect"},
}


def render_selector_idioma() -> str:
    """
    Renderiza un selector de idioma en la barra lateral de Streamlit.

    El selector permite al usuario elegir manualmente el idioma
    o dejarlo en 'unknown' para auto-detección automática.

    Retorna:
        str: Código del idioma ('es', 'en', 'pt' o 'unknown').
    """
    with st.sidebar:
        st.markdown("### 🌐 Configuración de Idioma")

        # Opción: auto-detectar primero
        if st.session_state.get("idioma_actual") == "unknown":
            st.info("Idioma: Auto-detectar 🤖")

        # Selector radio visible
        idioma_seleccionado = st.radio(
            "Seleccionar idioma / Select language / Selecionar idioma",
            options=list(IDIOMAS.keys()),
            format_func=lambda k: f"{IDIOMAS[k]['flag']} {IDIOMAS[k]['nombre']}",
            index=list(IDIOMAS.keys()).index(
                st.session_state.get("idioma_actual", "unknown")
            ),
            key="selector_idioma",
            help="Elija el idioma para la interfaz y detección de consultas",
        )

        # Actualizar estado de sesión
        st.session_state["idioma_actual"] = idioma_seleccionado

        # Mostrar estado actual con bandera
        info = IDIOMAS[idioma_seleccionado]
        st.caption(f"Idioma actual: {info['nombre']} {info['flag']}")

    return idioma_seleccionado


def actualizar_idioma_por_detector(consulta: str) -> str:
    """
    Intenta auto-detectar idioma y actualiza el estado si aún no tiene uno.

    Si el estado actual es 'unknown', usa el detector para adivinar el idioma
    basándose en señales lexicas de la consulta.

    Args:
        consulta: Texto de entrada del usuario.

    Retorna:
        str: Código de idioma ('es', 'en', 'pt' o 'unknown').
    """
    if st.session_state.get("idioma_actual") == "unknown":
        detectado = detectar_idioma(consulta)
        if detectado != "unknown":
            st.session_state["idioma_actual"] = detectado
            # Toast breve para notificar al usuario
            try:
                st.toast(f"Idioma auto-detectado: {IDIOMAS[detectado]['nombre']}")
            except Exception:
                pass  # toast puede no estar disponible en todas las versiones
        # Si detecto es 'unknown', mantenemos 'unknown' en el estado
    return st.session_state.get("idioma_actual", "unknown")