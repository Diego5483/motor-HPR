import streamlit as st
import re
from security_agent import HPRSecurityEngine

# --- NUEVO: Importaciones de la capa multilingüe HPR ---
from src.multilingual import detector, selector, router
# -----------------------------------------------------

st.title("HPR Local Agent Interface")

# --- Forzar cálculo de layout para que st.chat_input aparezca correctamente ---
# Tras integrar la capa multilingüe, Streamlit necesita este "gancho" para
# recomputar las alturas del sidebar y el área principal de chat.
st.caption("")

# Inicializar el motor de seguridad en la sesión
if "engine" not in st.session_state:
    st.session_state.engine = HPRSecurityEngine()

# --- NUEVO: Inyectar engine al router para enrutamiento con idioma ---
router.set_engine(st.session_state.engine)
# --------------------------------------------------------------

# Historial de chat
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- NUEVO: Renderizar selector de idioma en sidebar ---
idioma_actual = selector.render_selector_idioma()
# Auto-detectar idioma si aún no hay uno definido (usando la primera entrada
# o una consulta vacía para iniciar el detector)
if st.session_state.get("idioma_actual", "unknown") == "unknown":
    # Intentar detectar basado en el prompt inicial o mantener unknown
    pass  # El usuario puede seleccionar manualmente o la detección ocurrirá en el primer chat_input
# -----------------------------------------------------------

# Entrada de usuario por chat
if prompt := st.chat_input("Escribe tu consulta para el agente..."):
    # HPR-01: UI_INPUT_RECEIVED
    print(f"HPR-01: UI_INPUT_RECEIVED | prompt='{prompt}'")

    # NUEVO: Actualizar idioma por detector (auto-detección en primera entrada)
    # Si el idioma actual es 'unknown', intentamos detectarlo de la consulta
    if st.session_state.get("idioma_actual", "unknown") == "unknown":
        idioma_detectado = detector.detectar_idioma(prompt)
        if idioma_detectado != "unknown":
            st.session_state["idioma_actual"] = idioma_detectado
            # No mostrar toast aquí para evitar ruido; el selector lo muestra

    # HPR-02: SEGURIDAD_VALIDATION_START (ahora con contexto de idioma)
    # Usar router.procesar_con_idioma en lugar de llamadas directas
    try:
        response = router.procesar_con_idioma(
            payload=prompt,
            state={"identity": "HPR-CORE-DETERMINISTIC"},
            idioma=st.session_state.get("idioma_actual", "unknown"),
            verdad=[],
        )
        agent_reply = response.get("estado", "Sin respuesta")
        # Metadatos opcionales disponibles en 'response':
        # - response["idioma"]
        # - response["requiere_externa"]
        # - response["nivel_confianza"]
        # - response["justificación"]
    except Exception as e:
        # HPR-03: NEXUS_ROOT_DECISION_EXCEPTION
        print(f"HPR-03: NEXUS_ROOT_DECISION_EXCEPTION | error='{e}'")
        agent_reply = f"BLOQUEO DE SEGURIDAD: {e}"

    # HPR-06: TRIAGE_SELECTION_PRE_LOGGING
    print(f"HPR-06: TRIAGE_SELECTION_PRE_LOGGING | agent_reply_len={len(str(agent_reply))}")
    st.session_state.messages.append({"role": "assistant", "content": agent_reply})
    with st.chat_message("assistant"):
        # HPR-07: RESPONSE_LOGGED_TO_UI
        # El contenido ya incluye el estado; en futuro se podría traducir
        print(f"HPR-07: RESPONSE_LOGGED_TO_UI | content='{str(agent_reply)[:80]}...'")
        st.markdown(agent_reply)