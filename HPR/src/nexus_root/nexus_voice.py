"""Módulo de Síntesis de Voz (TTS) para el Nexus Root.

Utiliza edge-tts (Microsoft Edge TTS) para síntesis de voz de alta calidad
en español y otros idiomas, como alternativa robusta a Coqui TTS
compatible con Python 3.14+.
"""

import asyncio
import logging
import os
from typing import Optional, Dict, Any
from dataclasses import dataclass

import edge_tts

try:
    import streamlit as st
    STREAMLIT_DISPONIBLE = True
except ImportError:
    st = None
    STREAMLIT_DISPONIBLE = False

logger = logging.getLogger(__name__)


@dataclass
class ResultadoVoz:
    """Resultado de la síntesis de voz."""
    exito: bool
    archivo_audio: str
    duracion_estimada: float  # segundos
    tamaño_bytes: int
    error: Optional[str] = None
    voz_usada: str = "es-ES-ElviraNeural"


class NexusVoiceSynthesizer:
    """
    Sintetizador de voz usando edge-tts (Microsoft Edge TTS).
    
    Ventajas:
    - Compatible con Python 3.14+
    - Voces de alta calidad (Microsoft Edge TTS)
    - Soporte nativo para español (es-ES) y muchos idiomas
    - No requiere modelos pesados locales
    - Streaming asíncrono eficiente
    """
    
    # Voces en español disponibles en edge-tts
    VOCES_ES = {
        "es-ES-ElviraNeural": "Elvira (España) - Voz femenina natural",
        "es-ES-AlvaroNeural": "Álvaro (España) - Voz masculina natural",
        "es-MX-DaliaNeural": "Dalia (México) - Voz femenina natural",
        "es-MX-JorgeNeural": "Jorge (México) - Voz masculino natural",
    }
    
    VOZ_DEFAULT = "es-ES-ElviraNeural"
    
    def __init__(
        self, 
        voz_default: str = VOZ_DEFAULT,
        velocidad: str = "+0%",
        volumen: str = "+0%",
        cache_modelo: bool = True
    ):
        """
        Inicializa el sintetizador de voz.
        
        Args:
            voz_default: Voz por defecto (ver VOCES_ES)
            velocidad: Velocidad relativa (ej: "+10%", "-20%")
            volumen: Volumen relativo (ej: "+10%", "-20%")
            cache_modelo: No aplicable en edge-tts (sin modelo local)
        """
        self.voz_default = voz_default
        self.velocidad = velocidad
        self.volumen = volumen
        self.cache_modelo = cache_modelo
        
        logger.info(f"NexusVoiceSynthesizer inicializado | voz={voz_default} | velocidad={velocidad} | volumen={volumen}")
    
    async def _generar_audio_async(
        self, 
        texto: str, 
        output_path: str,
        voz: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Genera audio de forma asíncrona usando edge-tts.
        
        Args:
            texto: Texto a convertir a voz
            output_path: Ruta del archivo de salida
            voz: Voz a usar (None = voz por defecto)
            
        Returns:
            Dict con resultado de la síntesis
        """
        voz_usar = voz or self.voz_default
        
        if voz not in self.VOCES_ES and voz != self.VOZ_DEFAULT:
            logger.warning(f"Voz '{voz}' no reconocida, usando default: {self.VOZ_DEFAULT}")
            voz = self.VOZ_DEFAULT
        
        try:
            # Crear comunicador edge-tts
            communicate = edge_tts.Communicate(
                text=texto,
                voice=voz_usar,
                rate=self.velocidad,
                volume=self.volumen
            )
            
            # Guardar archivo
            await communicate.save(output_path)
            
            # Verificar archivo generado
            if os.path.exists(output_path):
                tamaño = os.path.getsize(output_path)
                # Estimar duración: ~150 palabras por minuto
                palabras = len(texto.split())
                duracion_estimada = max(palabras / 150 * 60, 1.0)
                
                logger.info(f"Audio generado: {output_path} ({tamaño} bytes, ~{duracion_estimada:.1f}s)")
                
                return {
                    "exito": True,
                    "archivo_audio": output_path,
                    "duracion_estimada": duracion_estimada,
                    "tamaño_bytes": os.path.getsize(output_path),
                    "voz_usada": voz_usar,
                    "error": None
                }
            else:
                raise RuntimeError("Archivo no se generó correctamente")
                
        except Exception as e:
            logger.error(f"Error generando audio: {e}")
            return {
                "exito": False,
                "archivo_audio": "",
                "duracion_estimada": 0.0,
                "tamaño_bytes": 0,
                "voz_usada": voz_usar,
                "error": str(e)
            }
    
    def generar_audio_informe(
        self, 
        texto_informe: str, 
        output_path: str = "temp_audio.wav",
        voz: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Genera audio a partir de texto de informe (interfaz síncrona).
        
        Args:
            texto_informe: Texto del informe a convertir en audio
            output_path: Ruta del archivo de salida
            voz: Voz a usar (opcional)
            
        Returns:
            Dict con resultado de la síntesis
        """
        if not texto_informe or not texto_informe.strip():
            return {
                "exito": False,
                "archivo_audio": "",
                "duracion_estimada": 0.0,
                "tamaño_bytes": 0,
                "error": "Texto vacío o inválido",
                "voz_usada": self.voz_default
            }
        
        # Asegurar directorio de salida
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_path):
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Ejecutar async en loop síncrono
        try:
            # Obtener o crear event loop
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            resultado = loop.run_until_complete(
                self._generar_audio_async(texto_informe, output_path, voz)
            )
            
            return resultado
            
        except Exception as e:
            logger.error(f"Error en síntesis síncrona: {e}")
            return {
                "exito": False,
                "archivo_audio": "",
                "duracion_estimada": 0.0,
                "tamaño_bytes": 0,
                "error": f"Error en síntesis: {str(e)}",
                "voz_usada": self.voz_default
            }
    
    def obtener_voces_disponibles(self) -> Dict[str, str]:
        """Retorna diccionario de voces disponibles en español."""
        return self.VOCES_ES.copy()
    
    def cambiar_voz(self, voz: str) -> bool:
        """Cambia la voz por defecto."""
        if voz in self.VOCES_ES:
            self.voz_default = voz
            logger.info(f"Voz cambiada a: {voz}")
            return True
        return False


# ============================================================
# FUNCIÓN DE CONVENIENCIA / FACTORÍA
# ============================================================

def crear_voice_synthesizer() -> 'NexusVoiceSynthesizer':
    """Factoría para crear una instancia de NexusVoiceSynthesizer.
    
    Usa cache de Streamlit si está disponible, sino crea instancia directa.
    """
    if STREAMLIT_DISPONIBLE and st is not None:
        try:
            return st.cache_resource(NexusVoiceSynthesizer)()
        except Exception:
            pass
    return NexusVoiceSynthesizer()


# ============================================================
# FUNCIÓN SÍNCRONA SIMPLE PARA USO DIRECTO
# ============================================================

def generar_audio_informe(
    texto: str, 
    output_path: str = "temp_audio.wav",
    voz: str = "es-ES-ElviraNeural"
) -> Dict[str, Any]:
    """
    Función de conveniencia para generar audio síncronamente.
    
    Args:
        texto: Texto a convertir
        output_path: Ruta de salida
        voz: Voz a usar
        
    Returns:
        Dict con resultado
    """
    synthesizer = NexusVoiceSynthesizer()
    return synthesizer.generar_audio_informe(texto, output_path, voz)