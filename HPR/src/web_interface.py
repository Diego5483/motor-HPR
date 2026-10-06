"""Interfaz web limpia y responsiva para el motor HPR.

Migración de la experiencia del chat de escritorio a un entorno web
responsivo, modular y alineado con la identidad visual del motor HPR.

Características:
- Diseño responsivo que se adapta a móvil, tablet y escritorio.
- Área de mensajes modular.
- Panel de control con selector de idioma (Fase 2).
- Entrada de chat fluida idéntica a la versión de escritorio.
- Estilos alineados con la identidad HPR (colores, tipografía).
"""

import streamlit as st
from src.security_agent import HPRSecurityEngine
from src.models.contracts import IDENTIDAD_DETERMINISTA

# ---------------------------------------------------------------------------
# Configuración de la página (debe ser la primera llamada de Streamlit)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="HPR Local Agent",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar="collapsed",
)

# ---------------------------------------------------------------------------
# Estilos CSS personalizados: identidad HPR, responsividad y utilidades
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
        /* --- Variables y raíces --- */
        :root {
            --hpr-primary: #1e3a5f;
            --hpr-secondary: #2c5f8a;
            --hpr-accent: #e87d38;
            --hpr-background: #f0f4f8;
            --hpr-card: #ffffff;
            --hpr-text: #1a2a3a;
            --hpr-text-muted: #5a7a8a;
        }

        /* Fondo general */
        .stApp {
            background: var(--hpr-background);
            font-family: "Segoe UI", Tahoma, Verdana, sans-serif;
        }

        /* Encabezado superior */
        .hpr-header {
            background: linear-gradient(135deg, var(--hpr-primary), var(--hpr-secondary));
            color: #ffffff;
            padding: 1rem 1.5rem;
            border-radius: 0 0 12px 12px;
            margin: -1rem -1rem 1.5rem -1rem;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }

        .hpr-header h1 {
            margin: 0;
            font-size: 1.5rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .hpr-header p {
            margin: 0.2rem 0 0;
            font-size: 0.875rem;
            opacity: 0.9;
        }

        /* Contenedor principal del chat */
        .hpr-chat-container {
            background: var(--hpr-card);
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 1rem;
            min-height: 400px;
            max-height: 60%;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
        }

        /* Mensajes de chat */
        .hpr-message {
            display: flex;
            flex-direction: column;
            gap: 0.25rem;
            max-width: 85%;
        }

        .hpr-message.user {
            align-self: flex-end;
        }

        .hpr-message.assistant {
            align-self: flex-start;
        }

        .hpr-message .avatar {
            width: 32px;
            height: 32px;
            border-radius: 50%;
            font-weight: bold;
            font-size: 0.875rem;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-right: 0.5rem;
        }

        .hpr-message.user .avatar {
            background: var(--hpr-primary);
            color: #fff;
        }

        .hpr-message.assistant .avatar {
            background: var(--hpr-accent);
            color: #fff;
        }

        .hpr-message .text {
            background: var(--hpr-card);
            border: 1px solid #dfe6e9;
            border-radius: 10px;
            padding: 0.75rem 1rem;
            line-height: 1.4;
            word-wrap: break-word;
        }

        .hpr-message.user .text {
            background: var(--hpr-primary);
            color: #fff;
            margin-left: 48px; /* espacio para avatar */
        }

        .hpr-message.assistant .text {
            background: var(--hpr-card);
            margin-right: 48px; /* espacio para avatar */
        }

        /* Input y barra de envío */
        .hpr-input-bar {
            display: flex;
            gap: 0.5rem;
            margin-top: 0.75rem;
            align-items: stretch;
        }

        .hpr-input-bar input {
            flex: 1;
            border: 1px solid #a0aec0;
            border-radius: 8px;
            padding: 0.5rem 0.75rem;
            font-size: 0.9375rem;
        }

        .hpr-input-bar input:focus {
            border-color: var(--hpr-primary);
            outline: none;
        }

        .hpr-input-bar button {
            border: none;
            border-radius: 8px;
            padding: 0 1rem;
            background: var(--hpr-primary);
            color: #ffffff;
            font-weight: 500;
            font-size: 0.9375rem;
            cursor: pointer;
            white-space: nowrap;
            transition: background 0.2s;
        }

        .hpr-input-bar button:hover {
            background: var(--hpr-secondary);
        }

        /* Selector de idioma (Fase 2) */
        .hpr-language-selector {
            display: inline-flex;
            align-items: center;
            gap: 0.25rem;
            padding: 0.25rem 0.5rem;
            border: 1px solid #dfe6e9;
            border-radius: 6px;
            background: #fff;
            font-size: 0.8125rem;
        }

        .hpr-language-selector .flag {
            width: 16px;
            height: 11px;
            font-size: 0.75rem;
        }

        /* Responsividad */
        @media (max-width: 768px) {
            .hpr-header {
                padding: 0.75rem;
            }
            .hpr-chat-container {
                min-height: 300px;
                max-height: 50%;
                padding: 0.5rem;
            }
            .hpr-message .text {
                padding: 0.5rem;
            }
            .hpr-input-bar {
                flex-direction: column;
                gap: 0.5rem;
            }
            .hpr-input-bar input,
            .hpr-input-bar button {
                width: 100%;
            }
        }

        /* Scrollbar personalizado */
        ::-webkit-scrollbar {
            width: 6px;
        }
        ::-webkit-scrollbar-track {
            background: transparent;
        }
        ::-webkit-scrollbar-thumb {
            background: #a0aec0;
            border-radius: 3px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: #718096;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Inicialización del motor de seguridad en la sesión
# ---------------------------------------------------------------------------
if "engine" not in st.session_state:
    st.session_state.engine = HPRSecurityEngine()

if "messages" not in st.session_state:
    st.session_state.messages = []

if "language" not in st.session_state:
    st.session_state.language = "es"  # español por defecto

# Paquetes de idioma modulares: solo se cargan bajo demanda
_LANGUAGE_PACKAGES = {
    "es": {"name": "Español", "flag": "🇪🇸", "loaded": True},
    "en": {"name": "English", "flag": "🇺🇸", "loaded": False},
    "pt": {"name": "Português", "flag": "🇵🇹", "loaded": False},
}


def _load_language_pack(lang: str) -> None:
    """Marca el paquete de idioma como cargado (simulación de download bajo demanda)."""
    if lang in _LANGUAGE_PACKAGES:
        _LANGUAGE_PACKAGES[lang]["loaded"] = True


def _detect_language(text: str) -> str:
    """Autodetección simple de idioma basado en patrones de palabras."""
    import re

    # Palabras clave en inglés
    en_keywords = {
        "the", "and", "or", "but", "if", "then", "else", "for", "while",
        "return", "import", "from", "class", "def", "true", "false", "None"
    }

    # Palabras clave en portugués
    pt_keywords = {
        "o", "a", "os", "as", "é", "è", "ê", "é", "está", "estou", "você",
        "nós", "eles", "elas", "é", "não", "é", "isso", "isso", "para",
        "com", "por", "em", "uma", "um", "que", "porém", "também"
    }

    terms = {t.lower() for t in re.findall(r"\w+", text) if len(t) >= 3}

    en_count = len(terms.intersection(en_keywords))
    pt_count = len(terms.intersection(pt_keywords))

    if pt_count > en_count and pt_count > 0:
        return "pt"
    if en_count > 0:
        return "en"
    return "es"  # default a español

# ---------------------------------------------------------------------------
# Helper: renderizado de un mensaje
# ---------------------------------------------------------------------------
def render_message(role: str, content: str) -> None:
    """Renderiza un mensaje en el área de chat."""
    # Avatar simple según rol
    avatars = {
        "user": "T",
        "assistant": "H",
    }
    avatar = avatars.get(role, "?")

    # Alineación según rol
    alignment_class = "user" if role == "user" else "assistant"

    # Elegir clase de color según rol
    text_color_class = "user" if role == "user" else "assistant"

    st.markdown(
        f"""
        <div class="hpr-message {alignment_class}">
            <div class="avatar">{avatar}</div>
            <div class="text">{content}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Encabezado de la aplicación
# ---------------------------------------------------------------------------
# Selector de idioma modular (Fase 2) — se muestra en el encabezado
_lang_cols = st.columns([0.1, 0.8, 0.1, 0.1, 0.1, 0.1])
for i, (code, pack) in enumerate(_LANGUAGE_PACKAGES.items()):
    with _lang_cols[i]:
        if st.button(
            f"{pack['flag']} {pack['name']}",
            key=f"lang_btn_{code}",
            help=f"Cambiar a {pack['name']}",
            use_container_width=True,
        ):
            st.session_state.language = code
            _load_language_pack(code)
            st.rerun()

st.markdown(
    """
    <div style="margin-left: 1rem;">
        <h1>
            <span style="font-size:1.2rem;">🛡️</span>
            <span>Motor HPR</span>
        </h1>
        <p>Interfaz Local — Identidad: HPR-CORE-DETERMINISTIC</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Área de mensajes
# ---------------------------------------------------------------------------
st.markdown('<div class="hpr-chat-container">', unsafe_allow_html=True)

# Renderizar historial
for msg in st.session_state.messages:
    render_message(msg["role"], msg["content"])

# Auto-scroll al final
st.markdown(
    """
    <script>
        const chat = window.parent.document.querySelector('.hpr-chat-container');
        if (chat) {
            chat.scrollTop = chat.scrollHeight;
        }
    </script>
    """,
    unsafe_allow_html=True,
)

st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Barra de entrada de chat
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="hpr-input-bar">
        <input
            type="text"
            id="chat-input"
            placeholder="Escribe tu consulta para el agente..."
            onkeypress="if(event.key==='Enter') document.querySelector('button').click()"
        />
        <button type="button">Enviar</button>
    </div>
    """,
    unsafe_allow_html=True,
)

# Manejo del input mediante chat_input de Streamlit
prompt = st.chat_input("Escribe tu consulta para el agente...")

if prompt:
    # Autodetección de idioma (Fase 2): detectar si el usuario escribió en
    # inglés o portugués y establecer el idioma correspondiente
    detected_lang = _detect_language(prompt)
    # Preferir el idioma detectado, pero mantener el seleccionado en la UI
    if st.session_state.language == "es":
        st.session_state.language = detected_lang

    # === Fase 3: Convivencia lógica y excepciones (Nexus Root) ===
    # Asegurar que los filtros de seguridad convivan correctamente con
    # el circuito de excepciones de ruta al procesar distintos idiomas.
    # - Sovereign Gate: patrones universales (no dependen del idioma)
    # - Nexus Root: validación de identidad (siempre permitido para consultas web)
    # - Niveles de confianza: gobernan la información web externa
    # - Evitar bloqueos falsos o colisiones de comandos al procesar idiomas

    # Normalizar el payload para validaciones de seguridad
    normalized_prompt = prompt.strip()

    # Verificación de patrones Sovereign Gate (universales, no idioma-dependent)
    # Estos patrones son revisados independientemente del idioma de la consulta:
    # "<script>", "DROP TABLE", "OVERRIDE_ROOT"
    from src.core.engine import sovereign_gate_validation

    sovereign_result = sovereign_gate_validation(normalized_prompt)

    if not sovereign_result:
        # Patrón de seguridad detectado -> bloqueo transparente mediante
        # el circuito de excepciones de ruta; no hay colisiones con comandos
        # en otros idiomas, ya que los patrones son universales.
        agent_reply = "BLOQUEO SOVEREIGN GATE: Patrón de seguridad detectado en la consulta."
    else:
        # Nexus Root: validación de identidad. No se bloquean consultas que
        # requieran investigación externa; solo se registra el estado para
        # efectos de rastreo. El sistema de tres niveles de confianza goberna
        # el acceso web y la veracidad de la información.
        try:
            response = st.session_state.engine.process_pipeline(
                payload=str(prompt),
                state={"identity": "HPR-CORE-DETERMINISTIC"},
                truth=[],
            )
            agent_reply = response.get("estado", "Sin respuesta")
        except Exception as e:
            agent_reply = f"BLOQUEO DE SEGURIDAD: {e}"

# Auto-scroll final después de renderizar
st.markdown(
    """
    <script>
        setTimeout(() => {
            const chat = window.parent.document.querySelector('.hpr-chat-container');
            if (chat) {
                chat.scrollTop = chat.scrollHeight;
            }
        }, 100);
    </script>
    """,
    unsafe_allow_html=True,
)