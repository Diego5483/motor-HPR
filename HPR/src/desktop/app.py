"""Aplicación de escritorio nativa del motor HPR (CustomTkinter).

Interfaz ligera y local: sin Streamlit ni navegador web (E1).

- Chat con el núcleo determinista HPR (D1).
- Identidad visual: el escudo oficial del proyecto es el
  icono de la ventana nativa y el logotipo de la cabecera.
- Voz local: síntesis con pyttsx3 y reconocimiento offline
  con CMU Sphinx; nunca servicios remotos (S2, E5).
"""

import sys
import os

# Configurar sys.path para incluir el directorio src
# El archivo app.py está en HPR/src/desktop/app.py,
# por lo que subimos dos niveles para obtener HPR/src
_parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

import threading
from pathlib import Path

import customtkinter as ctk
from PIL import Image

from src.models.contracts import IDENTIDAD_DETERMINISTA
from src.security_agent import HPRSecurityEngine
from src.desktop.agent import AgenteChat
from src.desktop.voice import VozLocal

#: Directorio de recursos de la aplicación (ruta canónica, D3).
_DIRECTORIO_RECURSOS = Path(__file__).resolve().parent / "assets"


def _ruta_recurso(nombre: str) -> Path:
    """Resuelve la ruta canónica de un recurso local de la aplicación."""
    return _DIRECTORIO_RECURSOS / nombre


#: Icono principal de la ventana: escudo oficial del proyecto HPR.
RUTA_ICONO = _ruta_recurso("hpr.ico")

#: Logotipo oficial de la cabecera de la aplicación.
RUTA_LOGO = _ruta_recurso("hpr_logo.png")


class AplicacionHPR(ctk.CTk):
    """Ventana principal del escritorio local HPR."""

    def __init__(self, agente: AgenteChat, voz: VozLocal) -> None:
        super().__init__()
        self.agente = agente
        self.voz = voz
        self.voz_activa = False

        self.title("Motor HPR — Escritorio Local")
        self.geometry("900x640")
        self.logo_path = RUTA_LOGO
        self._configurar_icono()
        self._construir_interfaz()

    def _configurar_icono(self) -> None:
        """Establece el escudo oficial como icono de la ventana nativa."""
        try:
            icon_path = os.path.join(_DIRECTORIO_RECURSOS, "hpr.ico")
            if os.path.exists(icon_path):
                self.iconbitmap(str(icon_path))
        except Exception:
            pass

    def _construir_interfaz(self) -> None:
        """Construye la interfaz de usuario principal."""
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        marco = ctk.CTkFrame(self, fg_color="transparent")
        marco.pack(fill="both", expand=True, padx=12, pady=12)

        self._construir_encabezado(marco)

        self.chat = ctk.CTkTextbox(marco, wrap="word", state="disabled")
        self.chat.pack(fill="both", expand=True, pady=(0, 10))

        barra = ctk.CTkFrame(marco)
        barra.pack(fill="x")

        self.entrada = ctk.CTkEntry(barra)
        self.entrada.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entrada.bind("<Return>", self._enviar)

        ctk.CTkButton(barra, text="Enviar", command=self._enviar).pack(side="left")
        ctk.CTkButton(barra, text="🎤 Voz", command=self._dictar).pack(side="left", padx=8)
        self.boton_voz = ctk.CTkButton(barra, text="🔊 Voz: off", command=self._alternar_voz)
        self.boton_voz.pack(side="left", padx=8)

        self.estado = ctk.CTkLabel(marco, text="")
        self.estado.pack(anchor="w", pady=(8, 0))

    def _construir_encabezado(self, marco: ctk.CTkFrame) -> None:
        """Cabecera de la aplicación con el logotipo oficial del proyecto."""
        encabezado = ctk.CTkFrame(marco, fg_color="transparent")
        encabezado.pack(fill="x", pady=(0, 8))

        if hasattr(self, 'logo_path') and self.logo_path and os.path.exists(self.logo_path):
            try:
                from PIL import Image as PILImage
                img = PILImage.open(self.logo_path)
                logo = ctk.CTkImage(light_image=img, size=(60, 40))
                ctk.CTkLabel(encabezado, image=logo, text="").pack(side="left")
            except Exception:
                pass

        ctk.CTkLabel(
            encabezado,
            text="Motor HPR",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(side="left", padx=(10, 0))

    def _enviar(self, event=None) -> None:
        consulta = self.entrada.get().strip()
        if not consulta:
            return
        self.entrada.delete(0, "end")
        self._mostrar("Tú", consulta)

        respuesta = self.agente.responder(consulta)
        self._mostrar("HPR", respuesta)

        if self.voz_activa:
            threading.Thread(target=self.voz.hablar, args=(respuesta,), daemon=True).start()

    def _dictar(self) -> None:
        if not self.voz_activa:
            self._mostrar("HPR", "Escuchando... (habla ahora)")
            threading.Thread(target=self.voz.hablar, args=(None,), daemon=True).start()

    def _alternar_voz(self) -> None:
        self.voz_activa = not self.voz_activa
        self.boton_voz.configure(text=f"🔊 Voz: {'on' if self.voz_activa else 'off'}")

    def _mostrar(self, autor: str, texto: str) -> None:
        self.chat.configure(state="normal")
        self.chat.insert("end", f"{autor}: {texto}\n\n")
        self.chat.configure(state="disabled")
        self.chat.see("end")