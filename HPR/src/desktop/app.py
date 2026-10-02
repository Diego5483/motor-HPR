"""Aplicación de escritorio nativa del motor HPR (CustomTkinter).

Interfaz ligera y local: sin Streamlit ni navegador web (E1).

- Chat con el núcleo determinista HPR (D1).
- Identidad visual: el escudo oficial del proyecto es el
  icono de la ventana nativa y el logotipo de la cabecera.
- Voz local: síntesis con pyttsx3 y reconocimiento offline
  con CMU Sphinx; nunca servicios remotos (S2, E5).
"""

import threading
from pathlib import Path

import customtkinter as ctk
from PIL import Image

from ..models.contracts import IDENTIDAD_DETERMINISTA
from ..security_agent import HPRSecurityEngine
from .agent import AgenteChat
from .voice import VozLocal

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
        self._cargar_icono_ventana()
        self._construir_interfaz()
        self._actualizar_estado()

    def _cargar_icono_ventana(self) -> None:
        """Establece el escudo oficial como icono de la ventana nativa."""
        if not RUTA_ICONO.exists():
            return
        try:
            self.iconbitmap(str(RUTA_ICONO))
        except Exception:
            # Plataforma sin soporte para .ico: degradación silenciosa.
            pass

    def _construir_encabezado(self, marco: ctk.CTkFrame) -> None:
        """Cabecera de la aplicación con el logotipo oficial del proyecto."""
        encabezado = ctk.CTkFrame(marco, fg_color="transparent")
        encabezado.pack(fill="x", pady=(0, 8))

        if RUTA_LOGO.exists():
            try:
                imagen = Image.open(RUTA_LOGO)
                logotipo = ctk.CTkImage(light_image=imagen, size=(60, 40))
                ctk.CTkLabel(encabezado, image=logotipo, text="").pack(side="left")
            except Exception:
                # Logotipo no legible: la aplicación continúa sin él.
                pass

        ctk.CTkLabel(
            encabezado,
            text="Motor HPR",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(side="left", padx=(10, 0))

    def _construir_interfaz(self) -> None:
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        marco = ctk.CTkFrame(self)
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
        self.boton_voz.pack(side="left")

        self.estado = ctk.CTkLabel(marco, text="")
        self.estado.pack(anchor="w", pady=(8, 0))

    def _actualizar_estado(self) -> None:
        capacidades = self.voz.capacidades
        voz_texto = (
            f"síntesis {'✓' if capacidades.sintesis else '✗'} · "
            f"reconocimiento {'✓' if capacidades.reconocimiento else '✗'}"
        )
        if capacidades.motivo_reconocimiento:
            voz_texto += f" ({capacidades.motivo_reconocimiento})"
        self.estado.configure(text=f"Identidad: {IDENTIDAD_DETERMINISTA} · {voz_texto}")

    def _mostrar(self, autor: str, texto: str) -> None:
        self.chat.configure(state="normal")
        self.chat.insert("end", f"{autor}: {texto}\n\n")
        self.chat.configure(state="disabled")
        self.chat.see("end")

    def _enviar(self, event=None) -> None:
        consulta = self.entrada.get().strip()
        if not consulta:
            return
        self._mostrar("Tú", consulta)
        self.entrada.delete(0, "end")

        respuesta = self.agente.responder(consulta)
        self._mostrar("HPR", respuesta)

        if self.voz_activa:
            threading.Thread(target=self.voz.hablar, args=(respuesta,), daemon=True).start()

    def _alternar_voz(self) -> None:
        if not self.voz.capacidades.sintesis:
            self._mostrar("HPR", "Síntesis de voz no disponible en este entorno.")
            return
        self.voz_activa = not self.voz_activa
        self.boton_voz.configure(text=f"🔊 Voz: {'on' if self.voz_activa else 'off'}")

    def _dictar(self) -> None:
        if not self.voz.capacidades.reconocimiento:
            motivo = self.voz.capacidades.motivo_reconocimiento or "motor no disponible"
            self._mostrar("HPR", f"Entrada de voz no disponible: {motivo}")
            return
        self._mostrar("HPR", "Escuchando… (habla ahora)")
        threading.Thread(target=self._escuchar_hilo, daemon=True).start()

    def _escuchar_hilo(self) -> None:
        texto = self.voz.escuchar()
        if texto:
            self.after(0, lambda: self.entrada.insert(0, texto))


def main() -> None:
    """Punto de entrada: conecta la UI con el núcleo determinista HPR."""
    motor = HPRSecurityEngine()
    agente = AgenteChat(
        knowledge_base=motor.knowledge_base,
        nexus_identity=motor.nexus_identity,
    )
    voz = VozLocal()
    AplicacionHPR(agente, voz).mainloop()


if __name__ == "__main__":
    main()
