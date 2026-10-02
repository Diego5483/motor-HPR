"""Servicios de voz local del motor HPR (Reglas S2 y E5).

Toda la síntesis y el reconocimiento de voz ocurren sin red:

- Síntesis (TTS): ``pyttsx3`` (SAPI5 en Windows, espeak en Linux).
- Reconocimiento (STT): motor offline (CMU Sphinx) cuando está
  disponible. **Nunca** se usan servicios remotos (Google, Azure,
  Wit.ai): recurrir a ellos violaría la soberanía de datos.

Si un motor no está disponible en el entorno (por ejemplo,
``pocketsphinx`` carece de rueda para la versión de Python en
uso), el servicio se degrada con aviso explícito: la funcionalidad
de chat por texto no se ve afectada.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CapacidadesVoz:
    """Capacidades de voz detectadas en el entorno local."""

    sintesis: bool
    reconocimiento: bool
    motor_sintesis: str | None = None
    motor_reconocimiento: str | None = None
    motivo_reconocimiento: str | None = None


def _importable(modulo: str) -> bool:
    """Verifica si un módulo puede importarse (determinista)."""
    try:
        __import__(modulo)
    except ImportError:
        return False
    return True


def detectar_capacidades() -> CapacidadesVoz:
    """Detecta motores de voz locales sin inicializarlos (determinista)."""
    sintesis = _importable("pyttsx3")
    reconocimiento = _importable("speech_recognition") and _importable("pocketsphinx")

    motivo = None
    if not reconocimiento:
        if not _importable("speech_recognition"):
            motivo = "SpeechRecognition no está instalado"
        else:
            motivo = "motor offline (pocketsphinx) no disponible en este entorno"

    return CapacidadesVoz(
        sintesis=sintesis,
        reconocimiento=reconocimiento,
        motor_sintesis="pyttsx3" if sintesis else None,
        motor_reconocimiento="pocketsphinx" if reconocimiento else None,
        motivo_reconocimiento=motivo,
    )


class VozLocal:
    """Interfaz de voz local con degradación elegante (S2, E5)."""

    def __init__(self) -> None:
        self.capacidades = detectar_capacidades()

    def hablar(self, texto: str) -> bool:
        """Sintetiza el texto localmente. Devuelve False si no hay motor."""
        if not self.capacidades.sintesis:
            return False
        try:
            import pyttsx3

            motor = pyttsx3.init()
            motor.say(texto)
            motor.runAndWait()
            return True
        except Exception:
            # Sin dispositivo o motor de voz: degradación silenciosa.
            return False

    def escuchar(self) -> str | None:
        """Transcribe voz localmente. None si no hay motor offline."""
        if not self.capacidades.reconocimiento:
            return None
        try:
            import speech_recognition

            reconocedor = speech_recognition.Recognizer()
            with speech_recognition.Microphone() as fuente:
                audio = reconocedor.listen(fuente)
            # Prefiere español; retrocede a inglés si el modelo no existe.
            for idioma in ("es-ES", "en-US"):
                try:
                    return reconocedor.recognize_sphinx(audio, language=idioma)
                except speech_recognition.UnknownValueError:
                    continue
            return None
        except Exception:
            # Sin micrófono o sin motor: degradación silenciosa.
            return None
