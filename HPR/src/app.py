import streamlit as st
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
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    try:
        # Validación de seguridad obligatoria
        response = st.session_state.engine.process_pipeline(
            payload=str(prompt),
            state={"identity": "HPR-CORE-DETERMINISTIC"},
            truth=[]
        )
        agent_reply = response
    except Exception as e:
        agent_reply = f"BLOQUEO DE SEGURIDAD: {e}"

    st.session_state.messages.append({"role": "assistant", "content": agent_reply})
    with st.chat_message("assistant"):
        st.markdown(agent_reply)