import streamlit as st
import re
from security_agent import HPRSecurityEngine

st.title("HPR Local Agent Interface")

# Inicializar el motor de seguridad en la sesión
if "engine" not in st.session_state:
    st.session_state.engine = HPRSecurityEngine()

# Historial de chat
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Entrada de usuario por chat
if prompt := st.chat_input("Escribe tu consulta para el agente..."):
    # DEBUG: Ver texto recibido antes de procesar
    print(f"DEBUG UI INPUT: {prompt}")
    
    # NUEVO: Detectar trigger sintáctico con prefijoarroba (@)
    # Si el usuario ingresa un comando con prefijo @ (ej. @hpr_confianza),
    # se extrae el identificador y se envía limpio al backend para activar
    # la búsqueda externa condicional bajo los 3 niveles de confianza.
    trigger_pattern = re.match(r"^@(\S+)", prompt)
    if trigger_pattern:
        # Usuario ingresó un trigger @xxx: enviar identificación limpia al backend
        trigger_id = trigger_pattern.group(1)
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Inyectar trigger al motor: el backend ya tiene la lógica para
        # reconocer @hpr_confianza, @nivel1, etc. y activar REQUIRE_EXTERNA
        response = st.session_state.engine.process_pipeline(
            payload=trigger_id,  # Enviar solo el identificador después del @
            state={"identity": "HPR-CORE-DETERMINISTIC"},
            truth=[],
        )
        agent_reply = response.get("estado", "Sin respuesta") if isinstance(response, dict) else response
    else:
        # Entrada normal: procesar normalmente
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        try:
            # Validación de seguridad obligatoria
            response = st.session_state.engine.proceso_pipeline(
                payload=str(prompt),
                state={"identity": "HPR-CORE-DETERMINISTIC"},
                truth=[],
            )
            agent_reply = response.get("estado", "Sin respuesta") if isinstance(response, dict) else response
        except Exception as e:
            agent_reply = f"BLOQUEO DE SEGURIDAD: {e}"
    
    st.session_state.messages.append({"role": "assistant", "content": agent_reply})
    with st.chat_message("assistant"):
        st.markdown(agent_reply)