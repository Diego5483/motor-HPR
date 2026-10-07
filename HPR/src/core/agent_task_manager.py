"""Módulo de gestión de tareas autónomas en segundo plano para el Motor HPR.

Responsable de orquestar consultas web y procesamiento de datos de forma
determinista, aplicando la política de cero alucinaciones a través del
ValidadorNivelesConfianza integrado.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import sys
import os

# Asegurar que el directorio src esté en el path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from validador_niveles_confianza import ValidadorNivelesConfianza


# ---------------------------------------------------------------------------
# Tipos internos
# ---------------------------------------------------------------------------

class EstadoTarea(Enum):
    """Estado posible de una tarea dentro del GestorTareasAgente."""
    PENDING = "pending"       # Esperando ser procesada
    RUNNING = "running"       # En ejecución actúal
    COMPLETED = "completed"   # Finalizada exitosamente
    DISCARDED = "discarded"   # Descartada por política de cero alucinaciones


@dataclass
class Tarea:
    """Estructura que representa una tarea autónoma dentro del gestor."""
    id: str
    descripcion: str
    accion: Callable[[], Any]  # Función callable que ejecuta la tarea
    resultado: Any = field(default=None, repr=False)
    estado: EstadoTarea = EstadoTarea.PENDING
    error: Optional[str] = field(default=None, repr=False)
    creado_en: float = field(default_factory=time.time)
    completado_en: Optional[float] = field(default=None, repr=False)


# ---------------------------------------------------------------------------
# GestorTareasAgente
# ---------------------------------------------------------------------------

class GestorTareasAgente:
    """Orquesta tareas autónomas en segundo plano, validando cada resultado
    mediante el ValidadorNivelesConfianza para garantizar la política de
    cero alucinaciones del sistema HPR.

    La clase mantiene una cola de tareas pendientes, un historial completo
    de ejecuciones y ensures que ninguna información no validada sea difundida
    sin la supervisión adecuada.
    """

    def __init__(self) -> None:
        self._validador = ValidadorNivelesConfianza()
        # Cola de tareas por procesar (orden FIFO)
        self._cola_tareas: "deque[Tarea]" = deque()
        # Historial cronológico de todas las tareas ejecutadas
        self._historial_ejecucion: "deque[Tarea]" = deque()
        # Contador interno de identificadores únicos
        self._id_contador: int = 0

    # ------------------------------------------------------------------
    # API pública: adicionar y gestionar tareas
    # ------------------------------------------------------------------

    def agregar_tarea(self, descripcion: str, accion: Callable[[], Any]) -> str:
        """Inserta una nueva tarea en la cola de segundo plano.

        Args:
            descripcion: Texto descriptivo de qué hará la tarea.
            accion: Función callable sin argumentos que devuelve el resultado
                    de la consulta o proceso.

        Returns:
            El identificador único de la tarea creada.
        """
        self._id_contador += 1
        tarea = Tarea(
            id=f"tarea_{self._id_contador:04d}",
            descripcion=descripcion,
            accion=accion,
        )
        self._cola_tareas.append(tarea)
        return tarea.id

    # ------------------------------------------------------------------
    # Procesamiento iterativo
    # ------------------------------------------------------------------

    def procesar_siguiente(self) -> Optional[Tarea]:
        """Extrae la siguiente tarea de la cola y la procesa íntegramente.

        El ciclo es:
        1. Marcar como RUNNING.
        2. Ejecutar la acción asociada.
        3. Pasar el resultado por ValidadorNivelesConfianza.
        4. Si Nivel 1 o Nivel 2 → marcar COMPLETED con el resultado validado.
        5. Si Nivel 3 o insuficiente → marcar DISCARDED, registrar error,
           y devolver una respuesta de aclaración al usuario (política de
           cero alucinaciones).
        6. Registrar en el historial y retornar la tarea.

        Returns:
            La tarea procesada, o None si no había tareas en cola.
        """
        if not self._cola_tareas:
            return None

        tarea = self._cola_tareas.popleft()
        tarea.estado = EstadoTarea.RUNNING
        tarea.error = None
        tarea.resultado = None

        try:
            raw_resultado = tarea.accion()
        except Exception as exc:  # pragma: no cover - defensive
            tarea.estado = EstadoTarea.DISCARDED
            tarea.error = f"Excepción durante la ejecución: {exc}"
            self._historial_ejecucion.append(tarea)
            return tarea

        # --- Validación de niveles de confianza ---
        validacion = self._validador.clasificar_fuente(
            origen=f"tarea_{tarea.id}",
            contenido=str(raw_resultado) if raw_resultado else "",
            es_oficial=False,
        )

        nivel = validacion["nivel"]

        if nivel in (1, 2):
            # Resultado válido: integrar en el flujo de salida
            tarea.resultado = raw_resultado
            tarea.estado = EstadoTarea.COMPLETED
            tarea.completado_en = time.time()
        else:
            # Nivel 3 (Baja Confianza) o información insuficiente:
            # PROHIBIDO inventar datos. Marcar como Descartado.
            tarea.estado = EstadoTarea.DISCARDED
            tarea.error = (
                f"Validación Nivel 3 - Baja Confianza. "
                "Política de cero alucinaciones: información descartada. "
                "Solicitar aclaración al usuario o ampliar contexto."
            )
            tarea.completado_en = time.time()

        self._historial_ejecucion.append(tarea)
        return tarea

    # ------------------------------------------------------------------
    # Consulta y reporte
    # ------------------------------------------------------------------

    def ver_historial(self, limite: int = 50) -> List[Dict[str, Any]]:
        """Devuelve un resumen del historial de ejecuciones (máximo *límites*).

        Returns:
            Lista de diccionarios con los campos esenciales de cada tarea.
        """
        resumido: List[Dict[str, Any]] = []
        for t in list(self._historial_ejecucion)[-limite:]:
            resumido.append(
                {
                    "id": t.id,
                    "estado": t.estado.value,
                    "descripcion": t.descripcion,
                    "creado_en": round(t.creado_en, 2),
                    "completado_en": round(t.completado_en, 2) if t.completado_en else None,
                    "error": t.error,
                }
            )
        return resumido

    def ver_estado_cola(self) -> Dict[str, int]:
        """Devuelve el conteo de tareas por estado actual en la cola.

        Returns:
            Diccionario mapeando EstadoTarea -> cantidad.
        """
        conteo: Dict[str, int] = {e.value: 0 for e in EstadoTarea}
        for t in self._cola_tareas:
            conteo[t.estado.value] += 1
        # también includo las que ya fueron sacadas del contexto inmediato
        for t in self._historial_ejecucion:
            conteo[t.estado.value] += 1
        return conteo

    # -----------------------------------------------------------------
    # Utilidad: vaciar y reinicio
    # -----------------------------------------------------------------

    def reiniciar(self) -> None:
        """Reinicia el gestor, vaciando cola y historial."""
        self._cola_tareas.clear()
        self._historial_ejecucion.clear()
        self._id_contador = 0


# ---------------------------------------------------------------------------
# Función de ayuda para testeo / integración rápida
# ---------------------------------------------------------------------------

def prueba_integracion_validacion() -> None:
    """Función de verificación rápida que demuestra la integración
    GestorTareasAgente + ValidadorNivelesConfianza."""
    gestor = GestorTareasAgente()

    # Tarea que devuelve contenido largo (debe ser Nivel 2)
    def tarea_nivel2() -> str:
        return "Este es un contenido de prueba con suficiente longitud como para ser evaluado adecuadamente por el sistema de validación HPR, cumpliendo el umbral de 40 caracteres como mínimo."

    # Tarea que devuelve contenido corto (debe ser Nivel 3)
    def tarea_nivel3() -> str:
        return "Corto"

    # Tarea de CEO knowledge base (Nivel 1 por construcción)
    def tarea_ceo() -> str:
        return "Directrices sobre cómo los líderes ejecutivos integran modelos predictivos y agentes autónomos en la toma de decisiones."

    # Agregar y procesar
    gestor.agregar_tarea("Validación nivel 2", tarea_nivel2)
    gestor.agregar_tarea("Validación nivel 3", tarea_nivel3)
    gestor.agregar_tarea("Validación CEO", tarea_ceo)

    print("=== Estados de tareas después del procesamiento ===")
    for i in range(3):
        t = gestor.procesar_siguiente()
        if t is None:
            break
        print(f"  {t.id} | {t.estado.value:12s} | {t.descripcion:30s} | error={t.error}")

    print("\n=== Historial resumido ===")
    for entry in gestor.ver_historial():
        print(f"  {entry['id']:8s} | {entry['estado']:12s} | {entry['descripcion'][:30]:30s}")

    print("\n=== Conteo en cola/Historial ===")
    print(gestor.ver_estado_cola())