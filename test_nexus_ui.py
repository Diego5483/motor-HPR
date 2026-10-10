import streamlit as st
import logging
import sys
import os
import tempfile

# Añadir el directorio HPR/src al path para importaciones directas
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "HPR", "src"))

from security_agent import HPRSecurityEngine
from models.contracts import PipelineState
from nexus_root import crear_nexus_router

logging.basicConfig(level=logging.INFO)

st.set_page_config(page_title="Test Nexus Root - HPR", page_icon="🛡️", layout="wide")
st.title("🛡️ Sandbox de Pruebas: Motor Nexus Root (Fase 3)")
st.markdown("Interfaz gráfica aislada para probar la **Matriz de Precedencia Lógica** determinista con ejecución de herramientas externas y **síntesis en lenguaje natural**.")

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

    # ============================================================
    # PESTAÑAS: Respuesta en Lenguaje Natural | Trazabilidad y Metadatos
    # ============================================================
    tab1, tab2 = st.tabs(["📝 Respuesta en Lenguaje Natural", "🔧 Trazabilidad y Metadatos"])

    with tab1:
        st.subheader("📝 Informe en Lenguaje Natural")
        
        # Verificar si hay informe de síntesis (para decisiones con ejecución externa)
        informe_sintesis = resultado.get("informe_sintesis")
        if informe_sintesis:
            # Encabezado de confianza
            st.markdown(informe_sintesis.get("encabezado_confianza", ""))
            st.divider()
            
            # Introducción
            if informe_sintesis.get("introduccion"):
                st.markdown("### Introducción")
                st.markdown(informe_sintesis["introduccion"])
                st.divider()
            
            # Hallazgos clave
            hallazgos = informe_sintesis.get("hallazgos_clave", [])
            if hallazgos:
                st.markdown("### Hallazgos Clave")
                for hallazgo in hallazgos:
                    st.markdown(f"- {hallazgo}")
                st.divider()
            
            # Análisis técnico
            if informe_sintesis.get("analisis_tecnico"):
                st.markdown("### Análisis Técnico")
                st.markdown(informe_sintesis["analisis_tecnico"])
                st.divider()
            
            # Conclusiones
            if informe_sintesis.get("conclusiones"):
                st.markdown("### Conclusiones y Recomendaciones")
                st.markdown(informe_sintesis["conclusiones"])
                st.divider()
            
            # Advertencias
            advertencias = informe_sintesis.get("advertencias", [])
            if advertencias:
                st.markdown("### Advertencias")
                for adv in advertencias:
                    st.markdown(f"- {adv}")
            
            # ============================================================
            # BOTÓN DE REPRODUCCIÓN DE AUDIO (ESTABLE)
            # ============================================================
            st.divider()
            st.subheader("🔊 Reproducción en Voz Alta")
            
            # Inicializar estado de audio en session_state si no existe
            if "audio_generado" not in st.session_state:
                st.session_state.audio_generado = False
                st.session_state.audio_path = None
                st.session_state.audio_bytes = None
                st.session_state.audio_texto = None
                st.session_state.audio_voz = None
                st.session_state.audio_generando = False
                st.session_state.audio_error = None
                st.session_state.audio_duracion = 0
                st.session_state.audio_tamano = 0
            
            # Construir texto completo del informe para síntesis de voz (solo una vez)
            if "audio_texto_completo" not in st.session_state:
                texto_informe = ""
                if informe_sintesis.get("introduccion"):
                    texto_informe += informe_sintesis["introduccion"] + "\n\n"
                if informe_sintesis.get("hallazgos_clave"):
                    texto_informe += "Hallazgos clave:\n" + "\n".join(f"- {h}" for h in informe_sintesis["hallazgos_clave"]) + "\n\n"
                if informe_sintesis.get("analisis_tecnico"):
                    texto_informe += informe_sintesis["analisis_tecnico"] + "\n\n"
                if informe_sintesis.get("conclusiones"):
                    texto_informe += informe_sintesis["conclusiones"] + "\n\n"
                if informe_sintesis.get("advertencias"):
                    texto_informe += "Advertencias:\n" + "\n".join(f"- {a}" for a in informe_sintesis["advertencias"])
                st.session_state.audio_texto_completo = texto_informe
            
            if st.session_state.get("audio_texto_completo", "").strip():
                col_audio1, col_audio2 = st.columns([1, 3])
                with col_audio1:
                    # Botón deshabilitado mientras se genera
                    btn_audio = st.button(
                        "🔊 Escuchar Informe en Voz Alta", 
                        type="primary", 
                        use_container_width=True,
                        disabled=st.session_state.get("audio_generando", False),
                        key="btn_generar_audio"
                    )
                with col_audio2:
                    voz_seleccionada = st.selectbox(
                        "Voz:",
                        options=["es-ES-ElviraNeural", "es-ES-AlvaroNeural", "es-MX-DaliaNeural", "es-MX-JorgeNeural"],
                        format_func=lambda x: {
                            "es-ES-ElviraNeural": "🇪🇸 Elvira (España)",
                            "es-ES-AlvaroNeural": "🇪🇸 Álvaro (España)",
                            "es-MX-DaliaNeural": "🇲🇽 Dalia (México)",
                            "es-MX-JorgeNeural": "🇲🇽 Jorge (México)"
                        }.get(x, x),
                        index=0,
                        key="select_voz_tts"
                    )
                
                # Botón para limpiar audio
                col_limpiar1, col_limpiar2 = st.columns([1, 3])
                with col_limpiar1:
                    btn_limpiar = st.button(
                        "🗑️ Limpiar Audio", 
                        use_container_width=True,
                        key="btn_limpiar_audio"
                    )
                    if btn_limpiar:
                        st.session_state.audio_generado = False
                        st.session_state.audio_path = None
                        st.session_state.audio_bytes = None
                        st.session_state.audio_texto = None
                        st.session_state.audio_voz = None
                        st.session_state.audio_generando = False
                        st.session_state.audio_error = None
                        st.rerun()
                
                # Manejar generación de audio
                if st.session_state.get("audio_generando", False):
                    st.session_state.audio_generando = False  # Reset flag immediately
                    with st.spinner("Generando audio con Edge TTS..."):
                        try:
                            import logging
                            from nexus_root.nexus_voice import crear_voice_synthesizer
                            voice_synthesizer = crear_voice_synthesizer()
                            
                            # Crear archivo temporal persistente
                            import tempfile
                            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                                audio_path = tmp.name
                            
                            # Obtener texto completo del informe
                            texto_completo = st.session_state.get("audio_texto_completo", "")
                            
                            # Generar audio
                            voice_synthesizer = crear_voice_synthesizer()
                            resultado_audio = voice_synthesizer.generar_audio_informe(
                                texto_informe=st.session_state.get("audio_texto_completo", ""),
                                output_path=audio_path,
                                voz=st.session_state.get("audio_voz", "es-ES-ElviraNeural")
                            )
                            
                            if resultado_audio.get("exito"):
                                st.session_state.audio_generado = True
                                st.session_state.audio_path = resultado_audio.get("archivo_audio")
                                # Cache audio bytes for download
                                with open(resultado_audio["archivo_audio"], "rb") as f:
                                    st.session_state.audio_bytes = f.read()
                                st.session_state.audio_duracion = resultado_audio.get('duracion_estimada', 0)
                                st.session_state.audio_tamano = resultado_audio.get('tamaño_bytes', 0)
                                st.session_state.audio_voz = resultado_audio.get('voz_usada', 'es-ES-ElviraNeural')
                                st.session_state.audio_error = None
                            else:
                                st.session_state.audio_error = resultado_audio.get('error', 'Error desconocido')
                                st.session_state.audio_generado = False
                                st.session_state.audio_path = None
                        except Exception as e:
                            logging.error(f"Error generando audio: {e}", exc_info=True)
                            st.session_state.audio_error = f"Error generando audio: {str(e)}"
                            st.session_state.audio_generado = False
                            st.session_state.audio_path = None
                        
                        st.rerun()
                
                # Mostrar resultados de audio si existe
                if st.session_state.get("audio_generado", False) and st.session_state.get("audio_path"):
                    if os.path.exists(st.session_state.audio_path):
                        st.success(f"✅ Audio generado ({st.session_state.get('audio_duracion', 0):.1f}s, {st.session_state.get('audio_tamano', 0)} bytes)")
                        st.audio(st.session_state.audio_path, format="audio/wav")
                        
                        # Ofrecer descarga
                        try:
                            st.download_button(
                                label="⬇️ Descargar Audio",
                                data=st.session_state.audio_bytes,
                                file_name="informe_nexus.wav",
                                mime="audio/wav",
                                key="download_audio_btn"
                            )
                        except Exception as e:
                            logging.warning(f"No se pudo leer audio para descarga: {e}")
                            st.download_button(
                                label="⬇️ Descargar Audio",
                                data=open(st.session_state.audio_path, "rb").read(),
                                file_name="informe_nexus.wav",
                                mime="audio/wav",
                                key="download_audio_btn_fallback"
                            )
                        
                        # Botón para limpiar
                        st.button("🗑️ Limpiar Audio", on_click=lambda: setattr(st.session_state, 'audio_generado', False), key="btn_limpiar_audio_2")
                    
                    elif st.session_state.get("audio_error"):
                        st.error(f"Error generando audio: {st.session_state.audio_error}")
                        if st.button("🔄 Reintentar", key="btn_reintentar_audio"):
                            st.session_state.audio_error = None
                            st.session_state.audio_generado = False
                            st.rerun()
                else:
                    # Botón para generar audio
                    col_audio1, col_audio2 = st.columns([1, 3])
                    with col_audio1:
                        btn_audio = st.button(
                            "🔊 Generar Audio del Informe", 
                            type="primary", 
                            use_container_width=True,
                            disabled=st.session_state.get("audio_generando", False),
                            key="btn_generar_audio_inicial"
                        )
                    with col_audio2:
                        voz_seleccionada = st.selectbox(
                            "Voz:",
                            options=["es-ES-ElviraNeural", "es-ES-AlvaroNeural", "es-MX-DaliaNeural", "es-MX-JorgeNeural"],
                            format_func=lambda x: {
                                "es-ES-ElviraNeural": "🇪🇸 Elvira (España)",
                                "es-ES-AlvaroNeural": "🇪🇸 Álvaro (España)",
                                "es-MX-DaliaNeural": "🇲🇽 Dalia (México)",
                                "es-MX-JorgeNeural": "🇲🇽 Jorge (México)"
                            }.get(x, x),
                            index=0,
                            key="select_voz_tts_inicial"
                        )
                    
                    if btn_audio:
                        # Guardar voz seleccionada y marcar generación en curso
                        st.session_state.audio_voz = voz_seleccionada
                        st.session_state.audio_texto = st.session_state.get("audio_texto_completo", "")
                        st.session_state.audio_generando = True
                        st.rerun()
            else:
                st.info("ℹ️ No hay contenido suficiente en el informe para generar audio.")
        else:
            st.info("ℹ️ El informe está vacío, no hay contenido para generar audio.")

    with tab2:
        # NUEVO: Mostrar resultados de búsqueda externa si existen
        metadata = resultado.get("metadata", {})
        resultados_externos = metadata.get("resultados_externos")
        if resultados_externos:
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