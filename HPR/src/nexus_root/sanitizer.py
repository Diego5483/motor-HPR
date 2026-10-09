"""Sanitizador de inputs para el Nexus Root.

Proporciona funciones de validación y sanitización estrictas
según la Prioridad Máxima de la matriz de precedencia lógica.

Reglas de sanitización:
- None o string vacío → bandera de bloqueo
- Caracteres no imprimibles → limpieza o rechazo
- Longitud mínima de términos → validación semántica
"""

from typing import Optional, Tuple, Any
import re

# Patrones de caracteres inválidos o corruptos
_PATRON_CARACTERES_INVALIDOS = re.compile(r'[^\x20-\x7E\r\n]')  # ASCII imprimible básico
_PATRON_VACIO_O_NULO = re.compile(r'^\s*$')  # Solo whitespace


class InputSanitizer:
    """Clase de utilidad para sanitización de inputs en Nexus Root."""
    
    @staticmethod
    def validar_entrada_segura(
        entrada: Optional[str],
        nombre_fuente: str = "desconocido"
    ) -> Tuple[bool, Optional[str], str]:
        """
        Valida si la entrada es segura para procesar según Prioridad Máxima.
        
        Returns:
            Tuple[bool, Optional[str], str]:
                - bool: True si la entrada es válida (pasa a siguiente nivel)
                - Optional[str]: Mensaje de advertencia si es inválido (NoneType block)
                - str: Mensaje de log descriptivo
        
        Ejemplo:
            >>> validar_entrada_segura(None, "test")
            (False, "BLOQUEO NONE_TYPE", "Entrada None detectada en fuente test")
            >>> validar_entrada_segura("", "test")
            (False, "BLOQUEO_VACIO", "Entrada string vacío detectada en fuente test")
        """
        log_msg = f"[SANITIZER-{nombre_fuente}] "
        
        # Prioridad Máxima: None check
        if entrada is None:
            log_msg += "BLOQUEO NONE_TYPE detectado"
            return False, "BLOQUEO NONE_TYPE", log_msg
        
        # Prioridad Máxima: string vacío o solo whitespace
        if not entrada or _PATRON_VACIO_O_NULO.match(entrada):
            log_msg += "BLOQUEO_VACIO detectado"
            return False, "BLOQUEO_VACIO", log_msg
        
        # Validación de caracteres inválidos/control
        if _PATRON_CARACTERES_INVALIDOS.search(entrada):
            log_msg += "CARACTERES_INVALIDOS detectados"
            # No bloqueamos inmediatamente, pero logueamos y marcamos para filtrado
            # Podríamos retornar True pero con metadata de advertencia
            return True, None, log_msg + " - input filtrado"
        
        # Entrada válida
        return True, None, log_msg + " - entrada válida"
    
    @staticmethod
    def limpiar_entrada(
        entrada: str,
        permitir_trigger: bool = True
    ) -> str:
        """
        Limpia un input válido quitando caracteres de control no imprimibles,
        manteniendo triggers y contenido relevante.
        """
        # Remover caracteres de control excepto newline y tab
        limpio = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', '', entrada)
        # Normalizar espacios múltiples
        limpio = re.sub(r'\s+', ' ', limpio).strip()
        return limpio