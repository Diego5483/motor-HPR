"""Memoria Episódica - Persistencia y Recuperación Contextual (Fase Beta, Pilar 2).

Almacena premisas, hipótesis, verificaciones y conclusiones por sesión/usuario.
Permite recuperación contextual para razonamiento multi-paso coherente.

Diseño:
- Storage agnóstico (JSON file / SQLite / en memoria)
- Índices por sesión, entidad, timestamp, tipo
- Recuperación por similitud semántica simple (entidades compartidas)
- API: guardar_episodio, recuperar_contexto, consultar_entidad, historial_sesion
"""

from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import json
import os
import uuid
from pathlib import Path
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class TipoEpisodio(Enum):
    """Tipos de episodios almacenables."""
    PREMISA = "premisa"
    HIPOTESIS = "hipotesis"
    VERIFICACION = "verificacion"
    CONCLUSION = "conclusion"
    CONSULTA = "consulta"          # Consulta original del usuario
    HALLAZGO_BRUTO = "hallazgo_bruto"  # HallazgoTecnico del DeepSynthesizer


@dataclass
class Episodio:
    """Unidad atómica de memoria episódica."""
    id: str
    tipo: TipoEpisodio
    sesion_id: str
    usuario_id: Optional[str]
    timestamp: str  # ISO format
    contenido: Dict[str, Any]  # Datos serializados del objeto original
    entidades: List[str] = field(default_factory=list)  # Para indexado y recuperación
    etiquetas: List[str] = field(default_factory=list)  # Tags opcionales
    metadatos: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["tipo"] = self.tipo.value
        return d
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Episodio":
        data = data.copy()
        data["tipo"] = TipoEpisodio(data["tipo"])
        return cls(**data)


class MemoriaEpisodica:
    """
    Gestor de memoria episódica para razonamiento multi-paso.
    
    Características:
    - Persistencia en archivo JSON (simple, portable, auditable)
    - Índices en memoria para recuperación rápida
    - Recuperación contextual por entidades compartidas
    - Soporte multi-sesión y multi-usuario
    - Limpieza automática por antigüedad (opcional)
    """
    
    def __init__(
        self, 
        ruta_storage: str = "memoria_episodica.json",
        max_episodios_por_sesion: int = 1000,
        ttl_dias: int = 30
    ):
        self.ruta_storage = Path(ruta_storage)
        self.max_episodios_por_sesion = max_episodios_por_sesion
        self.ttl_dias = ttl_dias
        
        # Índices en memoria para recuperación rápida
        self._episodios: Dict[str, Episodio] = {}  # id -> Episodio
        self._idx_sesion: Dict[str, Set[str]] = defaultdict(set)  # sesion_id -> {ep_id}
        self._idx_usuario: Dict[str, Set[str]] = defaultdict(set)  # usuario_id -> {ep_id}
        self._idx_entidad: Dict[str, Set[str]] = defaultdict(set)  # entidad -> {ep_id}
        self._idx_tipo: Dict[TipoEpisodio, Set[str]] = defaultdict(set)  # tipo -> {ep_id}
        self._idx_timestamp: List[Tuple[str, str]] = []  # [(timestamp, ep_id)] ordenado
        
        self._cargar_storage()
        logger.info(f"MemoriaEpisodica inicializada: {len(self._episodios)} episodios cargados")

    # ============================================================
    # PERSISTENCIA
    # ============================================================
    
    def _cargar_storage(self) -> None:
        """Carga episodios desde archivo JSON."""
        if not self.ruta_storage.exists():
            return
        
        try:
            with open(self.ruta_storage, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            for ep_data in data.get("episodios", []):
                ep = Episodio.from_dict(ep_data)
                self._indexar_episodio(ep)
            
            logger.info(f"MemoriaEpisodica: cargados {len(self._episodios)} episodios desde {self.ruta_storage}")
        except Exception as e:
            logger.error(f"Error cargando memoria episódica: {e}")

    def _guardar_storage(self) -> None:
        """Guarda todos los episodios a archivo JSON."""
        try:
            data = {
                "version": "1.0",
                "timestamp_guardado": datetime.now().isoformat(),
                "total_episodios": len(self._episodios),
                "episodios": [ep.to_dict() for ep in self._episodios.values()]
            }
            # Escritura atómica
            tmp_path = self.ruta_storage.with_suffix(".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            tmp_path.replace(self.ruta_storage)
        except Exception as e:
            logger.error(f"Error guardando memoria episódica: {e}")

    def _indexar_episodio(self, ep: Episodio) -> None:
        """Añade episodio a todos los índices."""
        self._episodios[ep.id] = ep
        self._idx_sesion[ep.sesion_id].add(ep.id)
        if ep.usuario_id:
            self._idx_usuario[ep.usuario_id].add(ep.id)
        for ent in ep.entidades:
            self._idx_entidad[ent].add(ep.id)
        self._idx_tipo[ep.tipo].add(ep.id)
        self._idx_timestamp.append((ep.timestamp, ep.id))
        self._idx_timestamp.sort(key=lambda x: x[0])

    def _desindexar_episodio(self, ep_id: str) -> None:
        """Elimina episodio de todos los índices."""
        ep = self._episodios.pop(ep_id, None)
        if not ep:
            return
        self._idx_sesion[ep.sesion_id].discard(ep_id)
        if ep.usuario_id:
            self._idx_usuario[ep.usuario_id].discard(ep_id)
        for ent in ep.entidades:
            self._idx_entidad[ent].discard(ep_id)
        self._idx_tipo[ep.tipo].discard(ep_id)
        self._idx_timestamp = [(t, eid) for t, eid in self._idx_timestamp if eid != ep_id]

    # ============================================================
    # API PÚBLICA: ALMACENAMIENTO
    # ============================================================
    
    def guardar_episodio(
        self,
        tipo: TipoEpisodio,
        sesion_id: str,
        contenido: Dict[str, Any],
        usuario_id: Optional[str] = None,
        entidades: Optional[List[str]] = None,
        etiquetas: Optional[List[str]] = None,
        metadatos: Optional[Dict[str, Any]] = None
    ) -> Episodio:
        """
        Guarda un nuevo episodio en memoria.
        
        Args:
            tipo: Tipo de episodio
            sesion_id: Identificador de sesión
            contenido: Datos serializados del objeto (premisa, hipótesis, etc.)
            usuario_id: Identificador de usuario (opcional)
            entidades: Lista de entidades para indexado (auto-extraídas si None)
            etiquetas: Tags opcionales
            metadatos: Metadatos adicionales
            
        Returns:
            Episodio creado
        """
        # Auto-extraer entidades del contenido si no se proveen
        if entidades is None:
            entidades = self._extraer_entidades_contenido(contenido)
        
        ep = Episodio(
            id=str(uuid.uuid4())[:12],
            tipo=tipo,
            sesion_id=sesion_id,
            usuario_id=usuario_id,
            timestamp=datetime.now().isoformat(),
            contenido=contenido,
            entidades=entidades,
            etiquetas=etiquetas or [],
            metadatos=metadatos or {}
        )
        
        self._indexar_episodio(ep)
        self._aplicar_limites_sesion(sesion_id)
        self._guardar_storage()
        
        logger.debug(f"Episodio guardado: {ep.id} [{tipo.value}] sesion={sesion_id} entidades={entidades}")
        return ep

    def _extraer_entidades_contenido(self, contenido: Dict[str, Any]) -> List[str]:
        """Extrae entidades técnicas del contenido serializado."""
        entidades = set()
        texto = json.dumps(contenido, ensure_ascii=False)
        
        # Siglas (2+ mayúsculas)
        entidades.update(re.findall(r'\b[A-Z]{2,}\b', texto))
        # Versiones
        entidades.update(re.findall(r'\bv?\d+\.\d+(\.\d+)?\b', texto))
        # Nombres técnicos CamelCase + números
        entidades.update(re.findall(r'\b[A-Z][a-z]+(?:[A-Z][a-z]+)*\d*\b', texto))
        # Nombres con guión: RISC-V
        entidades.update(re.findall(r'\b[A-Z]+-[A-Z0-9]+\b', texto))
        # Tras dos puntos
        entidades.update(re.findall(r':\s*([A-Z][\w\-\.]+)', texto))
        
        return list(entidades)

    def _aplicar_limites_sesion(self, sesion_id: str) -> None:
        """Aplica límite de episodios por sesión (FIFO)."""
        ep_ids = list(self._idx_sesion.get(sesion_id, set()))
        if len(ep_ids) > self.max_episodios_por_sesion:
            # Ordenar por timestamp y eliminar los más antiguos
            ep_ids_con_ts = [(eid, self._episodios[eid].timestamp) for eid in ep_ids if eid in self._episodios]
            ep_ids_con_ts.sort(key=lambda x: x[1])
            excedente = len(ep_ids_con_ts) - self.max_episodios_por_sesion
            for eid, _ in ep_ids_con_ts[:excedente]:
                self._desindexar_episodio(eid)
            logger.debug(f"Limpieza sesión {sesion_id}: {excedente} episodios antiguos eliminados")

    # ============================================================
    # API PÚBLICA: RECUPERACIÓN CONTEXTUAL
    # ============================================================
    
    def recuperar_contexto(
        self,
        sesion_id: str,
        entidades_clave: Optional[List[str]] = None,
        tipos: Optional[List[TipoEpisodio]] = None,
        limite: int = 20,
        ventana_temporal: Optional[str] = None  # ISO timestamp inicio
    ) -> List[Episodio]:
        """
        Recupera episodios relevantes para una sesión, opcionalmente filtrados
        por entidades clave y tipos. Ordenados por relevancia (entidades compartidas)
        y recencia.
        
        Args:
            sesion_id: Sesión objetivo
            entidades_clave: Entidades para priorizar episodios relacionados
            tipos: Filtrar por tipos de episodio
            limite: Máximo episodios a retornar
            ventana_temporal: Solo episodios después de este timestamp
            
        Returns:
            Lista de episodios ordenados por relevancia
        """
        # Candidatos: episodios de la sesión
        candidatos = self._idx_sesion.get(sesion_id, set())
        if not candidatos:
            return []
        
        # Filtrar por tipo
        if tipos:
            tipo_ids = set()
            for t in tipos:
                tipo_ids.update(self._idx_tipo.get(t, set()))
            candidatos = candidatos & tipo_ids
        
        # Filtrar por ventana temporal
        if ventana_temporal:
            candidatos = {eid for eid in candidatos 
                         if self._episodios[eid].timestamp >= ventana_temporal}
        
        # Scoring por relevancia
        scored = []
        for eid in candidatos:
            ep = self._episodios[eid]
            score = 0.0
            
            # Bonus por recencia (últimas 24h = 1.0, lineal hacia 0)
            try:
                ep_time = datetime.fromisoformat(ep.timestamp.replace("Z", "+00:00"))
                ahora = datetime.now()
                horas_diff = (ahora - ep_time).total_seconds() / 3600
                recencia = max(0.0, 1.0 - (horas_diff / 24))
                score += recencia * 0.3
            except Exception:
                pass
            
            # Bonus por entidades compartidas
            if entidades_clave:
                coincidencias = len(set(ep.entidades) & set(entidades_clave))
                score += min(coincidencias * 0.2, 0.7)
            
            scored.append((score, ep.timestamp, ep))
        
        # Ordenar: score descendente, luego timestamp descendente
        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        
        return [ep for _, _, ep in scored[:limite]]

    def consultar_entidad(
        self,
        entidad: str,
        sesion_id: Optional[str] = None,
        usuario_id: Optional[str] = None,
        limite: int = 10
    ) -> List[Episodio]:
        """
        Recupera todos los episodios relacionados con una entidad técnica.
        Útil para: "¿Qué sabemos sobre MTE en esta sesión?" o cross-sesión.
        """
        candidatos = self._idx_entidad.get(entidad, set())
        
        if sesion_id:
            candidatos = candidatos & self._idx_sesion.get(sesion_id, set())
        if usuario_id:
            candidatos = candidatos & self._idx_usuario.get(usuario_id, set())
        
        # Ordenar por recencia
        episodios = [self._episodios[eid] for eid in candidatos if eid in self._episodios]
        episodios.sort(key=lambda e: e.timestamp, reverse=True)
        
        return episodios[:limite]

    def historial_sesion(
        self,
        sesion_id: str,
        tipos: Optional[List[TipoEpisodio]] = None,
        limite: int = 50
    ) -> List[Episodio]:
        """Retorna historial cronológico completo de una sesión."""
        candidatos = self._idx_sesion.get(sesion_id, set())
        
        if tipos:
            tipo_ids = set()
            for t in tipos:
                tipo_ids.update(self._idx_tipo.get(t, set()))
            candidatos = candidatos & tipo_ids
        
        episodios = [self._episodios[eid] for eid in candidatos if eid in self._episodios]
        episodios.sort(key=lambda e: e.timestamp)
        
        return episodios[-limite:]

    def obtener_episodio(self, episodio_id: str) -> Optional[Episodio]:
        """Recupera un episodio por ID."""
        return self._episodios.get(episodio_id)

    # ============================================================
    # API: CONSULTAS AGREGADAS PARA RAZONAMIENTO
    # ============================================================
    
    def get_premisas_sesion(self, sesion_id: str) -> List[Dict[str, Any]]:
        """Recupera todas las premisas de una sesión como dicts listos para reasoning."""
        eps = self.recuperar_contexto(sesion_id, tipos=[TipoEpisodio.PREMISA], limite=100)
        return [ep.contenido for ep in eps]

    def get_hipotesis_sesion(self, sesion_id: str) -> List[Dict[str, Any]]:
        eps = self.recuperar_contexto(sesion_id, tipos=[TipoEpisodio.HIPOTESIS], limite=100)
        return [ep.contenido for ep in eps]

    def get_conclusiones_sesion(self, sesion_id: str) -> List[Dict[str, Any]]:
        eps = self.recuperar_contexto(sesion_id, tipos=[TipoEpisodio.CONCLUSION], limite=50)
        return [ep.contenido for ep in eps]

    def get_entidades_conocidas(self, sesion_id: str) -> List[str]:
        """Lista todas las entidades técnicas mencionadas en una sesión."""
        entidades = set()
        for eid in self._idx_sesion.get(sesion_id, set()):
            if eid in self._episodios:
                entidades.update(self._episodios[eid].entidades)
        return sorted(entidades)

    def get_brechas_abiertas(self, sesion_id: str) -> List[Dict[str, Any]]:
        """Recupera brechas de verificación pendientes (hipótesis indeterminadas)."""
        eps = self.recuperar_contexto(sesion_id, tipos=[TipoEpisodio.VERIFICACION], limite=50)
        brechas = []
        for ep in eps:
            v = ep.contenido
            if v.get("estado") in ("indeterminada", "especulativa") and v.get("brechas"):
                for b in v["brechas"]:
                    brechas.append({
                        "hipotesis_id": v.get("hipotesis_id"),
                        "claim": v.get("claim", ""),
                        "brecha": b,
                        "entidades": ep.entidades
                    })
        return brechas

    # ============================================================
    # MANTENIMIENTO
    # ============================================================
    
    def limpiar_antiguos(self, dias: Optional[int] = None) -> int:
        """Elimina episodios más antiguos que TTL días."""
        ttl = dias or self.ttl_dias
        cutoff = datetime.now().timestamp() - (ttl * 86400)
        eliminados = 0
        
        for eid, ep in list(self._episodios.items()):
            try:
                ep_time = datetime.fromisoformat(ep.timestamp.replace("Z", "+00:00")).timestamp()
                if ep_time < cutoff:
                    self._desindexar_episodio(eid)
                    eliminados += 1
            except Exception:
                pass
        
        if eliminados:
            self._guardar_storage()
            logger.info(f"MemoriaEpisodica: {eliminados} episodios antiguos eliminados (TTL={ttl}d)")
        
        return eliminados

    def estadisticas(self) -> Dict[str, Any]:
        """Estadísticas de la memoria."""
        return {
            "total_episodios": len(self._episodios),
            "sesiones_activas": len(self._idx_sesion),
            "usuarios": len(self._idx_usuario),
            "entidades_indexadas": len(self._idx_entidad),
            "por_tipo": {t.value: len(ids) for t, ids in self._idx_tipo.items()},
            "storage_path": str(self.ruta_storage),
            "storage_size_kb": round(self.ruta_storage.stat().st_size / 1024, 1) if self.ruta_storage.exists() else 0
        }


# ============================================================
# INTEGRACIÓN CON REASONING ENGINE
# ============================================================

def crear_memoria_episodica(ruta: str = "memoria_episodica.json") -> MemoriaEpisodica:
    """Factoría para MemoriaEpisodica."""
    return MemoriaEpisodica(ruta_storage=ruta)


class ReasoningConMemoria:
    """
    Wrapper que integra MotorRazonamientoSuperior con MemoriaEpisodica.
    Ejecuta pipeline y persiste automáticamente cada etapa.
    """
    
    def __init__(
        self,
        reasoning_engine,
        memoria: MemoriaEpisodica,
        sesion_id: str,
        usuario_id: Optional[str] = None
    ):
        self.reasoning = reasoning_engine
        self.memoria = memoria
        self.sesion_id = sesion_id
        self.usuario_id = usuario_id
    
    def ejecutar_con_memoria(
        self,
        hallazgos: List[Any],
        corpus: str,
        consulta_original: str = ""
    ) -> Dict[str, Any]:
        """Ejecuta pipeline completo y persiste todo en memoria episódica."""
        
        # 1. Guardar consulta original
        if consulta_original:
            self.memoria.guardar_episodio(
                tipo=TipoEpisodio.CONSULTA,
                sesion_id=self.sesion_id,
                usuario_id=self.usuario_id,
                contenido={"consulta": consulta_original, "corpus_chars": len(corpus)},
                etiquetas=["entrada"]
            )
        
        # 2. Guardar hallazgos brutos
        for h in hallazgos:
            self.memoria.guardar_episodio(
                tipo=TipoEpisodio.HALLAZGO_BRUTO,
                sesion_id=self.sesion_id,
                usuario_id=self.usuario_id,
                contenido={
                    "tipo": h.tipo,
                    "descripcion": h.descripcion,
                    "fuente": h.fuente,
                    "confianza": h.confianza,
                    "evidencia": h.evidencia[:500]
                },
                entidades=[h.descripcion.split(":")[-1].strip()] if ":" in h.descripcion else []
            )
        
        # 3. Ejecutar pipeline de razonamiento
        resultado = self.reasoning.ejecutar_pipeline_completo(hallazgos, corpus)
        
        # 4. Persistir cada etapa
        for p in resultado["premisas"]:
            self.memoria.guardar_episodio(
                tipo=TipoEpisodio.PREMISA,
                sesion_id=self.sesion_id,
                usuario_id=self.usuario_id,
                contenido=p,
                entidades=p.get("entidades", [])
            )
        
        for h in resultado["hipotesis"]:
            self.memoria.guardar_episodio(
                tipo=TipoEpisodio.HIPOTESIS,
                sesion_id=self.sesion_id,
                usuario_id=self.usuario_id,
                contenido=h,
                entidades=[h["metadatos"].get("entidad", "")] if h.get("metadatos") else []
            )
        
        # Mapear hipótesis por ID para enriquecer verificaciones
        hipotesis_map = {h["id"]: h for h in resultado["hipotesis"]}
        
        # Claves de metadatos que NO son entidades (filtrar)
        CLAVES_METADATOS_NO_ENTIDADES = {
            "regla", "arch", "tech", "causa", "efecto", "entidad", "fuentes",
            "requerido", "requisito", "patron_causal", "coocurrencia_arch_tech",
            "consenso_multi_fuente", "patron_restriccion"
        }
        
        for v in resultado["verificaciones"]:
            # Enriquecer verificación con claim y entidades de la hipótesis
            hyp_id = v.get("hipotesis_id", "")
            hyp = hipotesis_map.get(hyp_id, {})
            v_enriched = dict(v)
            v_enriched["claim"] = hyp.get("claim", "")
            
            # Extraer entidades de metadatos de la hipótesis (filtrando claves técnicas)
            entidades_hyp = []
            meta = hyp.get("metadatos", {})
            if meta:
                for key, val in meta.items():
                    if key in CLAVES_METADATOS_NO_ENTIDADES:
                        continue
                    if isinstance(val, str) and val:
                        if not re.match(r'^[PH]\d{4}$', val):
                            entidades_hyp.append(val)
                    elif isinstance(val, list):
                        for item in val:
                            if isinstance(item, str) and item and not re.match(r'^[PH]\d{4}$', item):
                                entidades_hyp.append(item)
            
            v_enriched["claim"] = hyp.get("claim", "")
            v_enriched["entidades"] = list(set(entidades_hyp))
            
            self.memoria.guardar_episodio(
                tipo=TipoEpisodio.VERIFICACION,
                sesion_id=self.sesion_id,
                usuario_id=self.usuario_id,
                contenido=v_enriched,
                entidades=v_enriched["entidades"]
            )
        
        for c in resultado["conclusiones"]:
            self.memoria.guardar_episodio(
                tipo=TipoEpisodio.CONCLUSION,
                sesion_id=self.sesion_id,
                usuario_id=self.usuario_id,
                contenido=c,
                entidades=c.get("entidades", [])
            )
        
        # 5. Enriquecer resultado con contexto de memoria
        resultado["memoria"] = {
            "sesion_id": self.sesion_id,
            "episodios_guardados": len(resultado["premisas"]) + len(resultado["hipotesis"]) + len(resultado["verificaciones"]) + len(resultado["conclusiones"]),
            "entidades_sesion": self.memoria.get_entidades_conocidas(self.sesion_id),
            "brechas_abiertas": self.memoria.get_brechas_abiertas(self.sesion_id)
        }
        
        return resultado


# Import re para _extraer_entidades_contenido
import re