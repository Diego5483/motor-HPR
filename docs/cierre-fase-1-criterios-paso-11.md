# Cierre de Fase 1 — Criterios obligatorios (Paso 11)

**Plan Maestro de Auditoría — Motor HPR · Fase 1**
**Commit base:** `3e642cc` (acta Fase H) · **Fecha:** (completar)
**Invocación de suite usada:** `PYTHONPATH=HPR;HPR/src` + `pytest -q --continue-on-collection-errors` (desde `HPR/`).

> Regla del Plan: *"Si una sola condición crítica falla, la Fase 1 continúa abierta."*
> *"Ninguna fase se considera concluida por velocidad de implementación, apariencia visual o ausencia de errores evidentes."*

---

## 1. Verificación de las 10 condiciones

| # | Criterio | Estado | Evidencia / observación |
|---|---|---|---|
| 1 | Los fallos originales están reproducidos, explicados y corregidos | ☑ con reserva | Secuestro del chat (Fase E) reproducido → corregido en **G.1** (`test_g1_chat_desacople.py`, 5/5). Reserva: persiste el defecto `@web_search` simulado (ver #3). |
| 2 | Los contratos y las conexiones están auditados dentro del alcance definido | ☑ | Fases B–D; **G.2** tipa `TriggerResult` y deriva `success` del estado real (`test_g2_contrato_trigger.py`, 6/6). |
| 3 | **Los datos técnicos corresponden a ejecuciones reales** | ☐ **NO CUMPLE** | **E4**: `POST /api/v1/trigger` `@web_search` responde `result.estado="fallback_local"` con `resultados_simulados` (fuente `hpr_local_fallback`, `main.py::_execute_trigger_internal`). Son datos **simulados**, no medidos. |
| 4 | La conversación ordinaria funciona naturalmente | ☑ | **E1** (`hola`) y **E2**: respuestas conversacionales sin encabezado forense. |
| 5 | Los triggers y payloads respetan sus contratos | ⚠️ Parcial | Forma del contrato OK (G.2) y payload respetado; pero `@web_search` presenta contenido simulado y `test_etapa_d.py::test_trigger_web_search_estado_no_disponible` sigue en rojo. |
| 6 | Nexus Console muestra correctamente los datos disponibles | ☑ | **G.3** (`test_g3_nexus_console.py` 6/6; `test_web_ui.py` 8/8): TURNOS/SESIONES/TOKENS reales; en fallo se conservan los gauges (**E5/E6/E8**). |
| 7 | **Las pruebas automatizadas, de integración y de regresión están aprobadas** | ☐ **NO CUMPLE** | **209 passed / 19 failed / 1 error de colección**; cobertura **34.42 % < 80 %** (P5, `fail_under=80`). Ver §2. |
| 8 | Las pruebas manuales finales son satisfactorias | ⚠️ Parcial | **Fase H CON OBSERVACIONES** (veredicto del responsable). |
| 9 | Los cambios están documentados y existe un punto de recuperación | ☑ | Commits `55f9fe6` (G.1), `4fbd636` (G.2), `6b8d084` (G.3), `3e642cc` (acta Fase H); `docs/auditoria-fases-A-B-C-plan-maestro-hpr.md`. Punto de recuperación = cualquiera de esos hashes. |
| 10 | El responsable del proyecto autoriza expresamente el cierre | ☐ Pendiente | Requiere firma del responsable. |

---

## 2. Detalle del criterio #7 (pruebas)

**Conteo:** `209 passed / 19 failed / 1 error`. Los 19 fallos + el error son **pre-existentes**
(no introducidos por G.1/G.2/G.3; el árbol de trabajo ya tenía 19 fallos antes de la Fase G).

| Grupo | N.º | Naturaleza |
|---|---|---|
| `test_desktop_agent.py` | 7 | Agente de escritorio (respuestas/bóveda) |
| `test_engine.py` | 10 | `AttributeError` en `SOVEREIGN-GATE`/`NEXUS-ROOT`/pipeline |
| `test_desktop_app.py` | 1 | Proporción de logo |
| `test_etapa_d.py` | 1 | `test_trigger_web_search_estado_no_disponible` (contrato antiguo + simulación) |
| `test_core_engine.py` | 1 (error) | `ImportError: HPREngine` (módulo no expuesto) |

**Cobertura:** `TOTAL 34 %` (`fail_under=80` → **FAIL**). P5 no se cumple globalmente.

**Nota de entorno:** `src/__init__.py` existe, por lo que pytest no añade `src/` al `sys.path`;
la suite requiere `PYTHONPATH` con `HPR` y `HPR/src` (como hace `run.py`). Sin eso aparecen
3 errores de colección adicionales (`No module named 'models'`) que son artefacto de invocación,
no defectos de código.

---

## 3. Veredicto

**La Fase 1 CONTINÚA ABIERTA.** Fallan condiciones críticas **#3** y **#7**; **#5** y **#8** quedan
parciales. **No es una afirmación de éxito.**

### Camino mínimo propuesto para el cierre (acotado, sin reescritura general)
1. **#3 / #5** — Corregir `@web_search` en `main.py`: retirar `resultados_simulados` y devolver
   `estado="no_disponible"` honesto; actualizar `test_trigger_web_search_estado_no_disponible`.
   *Prueba de regresión:* falla antes (devuelve simulados) y pasa después (no_disponible).
2. **#7** — Revisar los 19 fallos y el error de colección (`test_desktop_agent`, `test_engine`,
   `test_desktop_app`, `test_core_engine`).
3. **#7** — Acercar la cobertura a 80 % o establecer, de forma **documentada**, un umbral
   excepcional acordado.
4. **#10** — Cierre con autorización expresa del responsable.

---

## 4. Firma

**Responsable:** _(completar)_ · **Fecha:** _(completar)_
**Decisión:** ☐ Cierre autorizado ☐ Fase 1 permanece abierta
