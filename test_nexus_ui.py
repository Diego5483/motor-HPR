import streamlit as st
import logging
import sys
import os

# Añadir el directorio HPR/src al path para importaciones directas
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "HPR", "src"))

from security_agent import HPRSecurityEngine
from models.contracts import PipelineState
from nexus_root import crear_nexus_router

logging.basicConfig(level=logging.INFO)

st.set_page_config(page_title="Test Nexus Root - HPR", page_icon="🛡️", layout="wide")
st.title("🛡️ Sandbox de Pruebas: Motor Nexus Root (Fase 3)")
st.markdown("Interfaz gráfica aislada para probar la **Matriz de Precedencia Lógica** determinista con ejecución de herramientas externas.")

if "router" not in st.session_state:
    with st.spinner("Inicializando HPR Security Engine y Nexus Router..."):
        motor_seguridad = HPRSecurityEngine()
        st.session_state.router = crear_nexus_router(motor_seguridad)
        st.success("¡Nexus Router ensamblado y listo!")

st.subheader("Ingreso de Comandos")
entrada_usuario = st.text_input(
    "Escribe un prompt para probar la cadena de responsabilidad:",
    placeholder="Ej: @web_search últimas noticias sobre tecnología"
)

col1, col2 = st.columns([1, 5])
with col1:
    btn_probar = st.button("Ejecutar Enrutamiento", type="primary")
with col2:
    btn_vacio = st.button("Simular Input Vacío (Probar Max Priority)")

input_a_evaluar = None
if btn_probar and entrada_usuario:
    input_a_evaluar = entrada_usuario
elif btn_vacio:
    input_a_evaluar = ""

if input_a_evaluar is not None:
    st.divider()
    st.subheader("📊 Resultado del Enrutamiento Determinista")

    estado_simulado = PipelineState(identity="TEST-GUI-USER")

    resultado = st.session_state.router.enrutar(
        entrada=input_a_evaluar,
        state=estado_simulado
    )

    nivel = resultado.get("nivel", "")
    decision = resultado.get("decision", "")
    override = resultado.get("override", "")
    entrada_proc = resultado.get("entrada_procesada", "")

    # Renderizado semántico según decisión
    if "MAX" in nivel or "SANITIZER" in nivel:
        st.error(f"🛑 BLOQUEO PREVENTIVO: {decision}")
    elif "HIGH" in nivel:
        st.warning(f"⚠️ OVERRIDE DE SEGURIDAD: {decision}")
    elif "MEDIUM" in nivel:
        if decision == "ejecucion_externa_completada":
            st.success(f"✅ EJECUCIÓN EXTERNA COMPLETADA: {decision}")
        else:
            st.info(f"⚙️ PIPELINE OPERATIVO: {decision}")
    else:
        st.success(f"🌐 LENGUAJE NATURAL (Capa Base): {decision}")

    st.markdown(f"**Handler que decidió:** `{resultado.get('handler', 'N/A')}`")
    st.markdown(f"**Override:** `{override if override else 'N/A'}`")
    st.markdown(f"**Entrada procesada:** `{entrada_proc}`")

    # NUEVO: Mostrar resultados de búsqueda externa si existen
    metadata = resultado.get("metadata", {})
    resultados_externos = metadata.get("resultados_externos")
    if resultados_externos:
        st.divider()
        st.subheader("🔍 Resultados de Búsqueda Externa")
        for i, res in enumerate(resultados_externos, 1):
            with st.expander(f"🔧 Herramienta: {res['herramienta']} | {'✅ Éxito' if res['exito'] else '❌ Error'}"):
                if res["exito"]:
                    st.markdown(f"**Fuente:** `{res['fuente']}`")
                    st.markdown(f"**Payload ejecutado:** `{res.get('metadatos', {}).get('query_original', 'N/A')}`")
                    st.markdown("**Contenido:**")
                    st.code(res["contenido"], language="text")
                    st.markdown("**Metadatos:**")
                    st.json(res["metadatos"])
                else:
                    st.error(f"Error: {res['error']}")
                    st.json(res["metadatos"])

    st.markdown("**Metadatos Completos del Enrutador:**")
    st.json(resultado)

    # Mostrar la cadena de handlers evaluados
    with st.expander("🔍 Detalle de la Cadena de Responsabilidad"):
        metadata = resultado.get("metadata", {})
        handlers_eval = metadata.get("handlers_evaluados", [])
        st.markdown("**Handlers evaluados en orden:**")
        for i, h in enumerate(handlers_eval, 1):
            decisor = " ⭐ **DECISOR**" if h == metadata.get("handler_decisor") else ""
            st.markdown(f"{i}. `{h}`{decisor}")

        st.markdown("**Metadata completa:**")
        st.json(metadata)