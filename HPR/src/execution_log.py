"""Persistencia de logs de ejecución del motor HPR (Etapa D4).

Los logs se almacenan en la bóveda local (`HPR/boveda y vitacoras/logs/`)
como archivos JSON Lines (.jsonl) — un archivo por día.

Soberanía (S1/S2): los logs nunca salen de la máquina local.
Integridad (S5): cada entrada incluye un hash SHA-256 para verificación.
"""

import hashlib
import json
import os
from datetime import datetime, date, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# Ruta de logs dentro de la bóveda (soberanía S1)
_BOVEDA_DIR = Path(__file__).resolve().parent.parent / "boveda y vitacoras"
_LOGS_DIR = _BOVEDA_DIR / "logs"


def _ensure_logs_dir() -> Path:
    """Crea el directorio de logs si no existe."""
    _LOGS_DIR.mkdir(parents=True, exist_ok=True)
    return _LOGS_DIR


def _compute_hash(entry: Dict[str, Any]) -> str:
    """Computa hash SHA-256 de una entrada de log (integridad S5)."""
    # Excluir el campo 'hash' del cómputo para evitar recursión
    data = {k: v for k, v in entry.items() if k != "hash"}
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _get_log_file() -> Path:
    """Obtiene el archivo de log del día actual."""
    today = date.today().isoformat()
    return _ensure_logs_dir() / f"execution_{today}.jsonl"


def log_execution(
    trigger: str,
    success: bool,
    session_id: Optional[str] = None,
    confidence_level: int = 1,
    result: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None,
    telemetry: Optional[Dict[str, Any]] = None,
    execution_time_ms: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Registra una ejecución de trigger en el log persistente.

    Retorna la entrada de log creada (con hash de integridad).
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trigger": trigger,
        "success": success,
        "session_id": session_id,
        "confidence_level": confidence_level,
        "result": result,
        "error_message": error_message,
        "telemetry": telemetry or {},
        "execution_time_ms": execution_time_ms,
    }
    
    # Añadir hash de integridad (S5)
    entry["hash"] = _compute_hash(entry)
    
    # Persistir en archivo JSON Lines
    log_file = _get_log_file()
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    
    return entry


def get_logs(
    limit: int = 100,
    trigger: Optional[str] = None,
    success: Optional[bool] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Obtiene logs de ejecución con filtros opcionales.

    Args:
        limit: Máximo número de entradas a retornar (más recientes primero).
        trigger: Filtrar por nombre de trigger.
        success: Filtrar por estado de éxito.
        date_from: Fecha ISO desde la cual filtrar (YYYY-MM-DD).
        date_to: Fecha ISO hasta la cual filtrar (YYYY-MM-DD).
    """
    logs: List[Dict[str, Any]] = []
    
    # Buscar todos los archivos de log
    if not _LOGS_DIR.exists():
        return []
    
    for log_file in sorted(_LOGS_DIR.glob("execution_*.jsonl"), reverse=True):
        # Filtrar por fecha si se especifica
        if date_from or date_to:
            file_date = log_file.stem.replace("execution_", "")
            if date_from and file_date < date_from:
                continue
            if date_to and file_date > date_to:
                continue
        
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                
                # Aplicar filtros
                if trigger and entry.get("trigger") != trigger:
                    continue
                if success is not None and entry.get("success") != success:
                    continue
                
                logs.append(entry)
                
                # Respetar límite
                if len(logs) >= limit:
                    return logs
    
    return logs


def get_log_stats() -> Dict[str, Any]:
    """Obtiene estadísticas globales de los logs de ejecución."""
    all_logs = get_logs(limit=10000)
    
    if not all_logs:
        return {
            "total_executions": 0,
            "successful": 0,
            "failed": 0,
            "avg_execution_time_ms": 0,
            "triggers_used": {},
        }
    
    successful = sum(1 for log in all_logs if log.get("success"))
    failed = len(all_logs) - successful
    
    # Tiempo promedio de ejecución
    exec_times = [
        log.get("execution_time_ms", 0)
        for log in all_logs
        if log.get("execution_time_ms") is not None
    ]
    avg_time = sum(exec_times) / len(exec_times) if exec_times else 0
    
    # Triggers más usados
    triggers: Dict[str, int] = {}
    for log in all_logs:
        t = log.get("trigger", "unknown")
        triggers[t] = triggers.get(t, 0) + 1
    
    return {
        "total_executions": len(all_logs),
        "successful": successful,
        "failed": failed,
        "avg_execution_time_ms": round(avg_time, 2),
        "triggers_used": triggers,
    }


def export_logs(format: str = "json", **filters) -> str:
    """
    Exporta logs en formato JSON o CSV.

    Args:
        format: "json" o "csv".
        **filters: Filtros para get_logs (trigger, success, date_from, etc.).

    Retorna:
        Ruta del archivo exportado.
    """
    logs = get_logs(limit=10000, **filters)
    
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    export_dir = _ensure_logs_dir() / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    
    if format == "json":
        export_file = export_dir / f"logs_export_{timestamp}.json"
        with open(export_file, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2, default=str)
    
    elif format == "csv":
        import csv
        export_file = export_dir / f"logs_export_{timestamp}.csv"
        if logs:
            with open(export_file, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=logs[0].keys())
                writer.writeheader()
                writer.writerows(logs)
        else:
            # CSV vacío con headers mínimos
            with open(export_file, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["timestamp", "trigger", "success"])
                writer.writeheader()
    
    else:
        raise ValueError(f"Formato no soportado: {format}")
    
    return str(export_file)


def verify_log_integrity(log_file: Path) -> Dict[str, Any]:
    """
    Verifica la integridad de un archivo de log (S5).

    Retorna:
        Dict con total de entradas, válidas e inválidas.
    """
    total = 0
    valid = 0
    invalid = 0
    
    with open(log_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total += 1
            try:
                entry = json.loads(line)
                stored_hash = entry.pop("hash", None)
                computed_hash = _compute_hash(entry)
                if stored_hash == computed_hash:
                    valid += 1
                else:
                    invalid += 1
            except json.JSONDecodeError:
                invalid += 1
    
    return {
        "file": str(log_file),
        "total_entries": total,
        "valid_entries": valid,
        "invalid_entries": invalid,
        "integrity_ok": invalid == 0,
    }
