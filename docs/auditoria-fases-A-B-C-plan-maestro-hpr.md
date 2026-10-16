# Auditoría Arquitectónica HPR — Fases A, B y C

**Plan Maestro de Auditoría (13 pasos) · Pasos 3, 4 y 5**
Fecha: 2026-10-16 · Rama: `main` · Punto de partida: `6c1afff`
Modo: **solo lectura**. **0 modificaciones de código fuente** en las tres fases.

> Regla rectora: primero inspeccionar, después reproducir, diagnosticar, corregir,
> auditar y verificar. Toda afirmación se respalda con evidencia reproducible.

---

## 0. Estado del repositorio al cierre

- Rama activa: `main` (ahead of `origin/main` by 6).
- Baseline de trabajo: `6c1afff` — "fix(api): Fase 2 - chat con inferencia real via DeepSynthesizer (sin eco)".
- Cambios locales **preservados** (NO forman parte de este commit):
  - Modificados sin preparar: `HPR/src/main.py`, `HPR/src/schemas.py`,
    `HPR/src/web_ui/app.js`, `HPR/src/web_ui/index.html`, `HPR/src/web_ui/styles.css`.
  - No rastreado: `HPR/boveda y vitacoras/Hoja_de_ruta_HPR.pdf`.
- Sin stashes. Sin worktrees residuales (los temporales de auditoría fueron eliminados).

### Baseline de pruebas (comando reproducible)

```powershell
cd "C:\Users\USUARIO\Desktop\motor HPR\HPR"
$env:PYTHONPATH = "...\HPR\src"
..\.venv\Scripts\python.exe -m pytest
```

| Baseline | Pasadas | Fallidas | Error recolección | Cobertura |
|---|---|---|---|---|
| HEAD `6c1afff` | 193 | 18 | 1 (`test_core_engine.py`) | — |
| Working tree actual | 192 | 19 | 1 (`test_core_engine.py`) | 33.16 % (umbral 80 → FAIL) |

- **Delta HEAD→working tree:** `src/test_etapa_d.py::test_trigger_web_search_estado_no_disponible`
  (línea 185) pasa en HEAD y falla en el working tree (el cambio local responde `"error"`
  con `@web_search` sin payload; el test espera `"no_disponible"`).
- Fallos pre-existentes agrupados: `test_engine.py` (8) y `test_desktop_agent.py` (8) por
  drift de contrato (motor devuelve `dict`, tests esperan `str`); `test_desktop_app.py` (1);
  `test_core_engine.py` importa `HPREngine` inexistente.

---

## 1. FASE A — Inventario y preservación (Paso 3)

### Puntos de entrada
- **FastAPI (backend evaluado en vivo):** `HPR/src/main.py:207`; lanzador `HPR/run.py`
  (`uvicorn` 127.0.0.1:8000); UI estática montada en `/ui` (`main.py:1614` → `src/web_ui/`).
- **Escritorio (oficial según README):** `src/desktop/` (CustomTkinter).
- **Streamlit (legado):** `src/app.py`, `src/web_interface.py`, `src/dual_interface.py`.

### Endpoints FastAPI (15 rutas + 1 montaje)
`GET /` · `GET /api/v1/communications/query` · `POST /api/v1/chat` · `POST /api/v1/orchestrate` ·
`GET|DELETE /api/v1/sessions…` · `GET /api/v1/telemetry` · `POST /api/v1/trigger` ·
`GET /api/v1/logs`, `/stats`, `/export`, `/integrity`.

### Triggers (`src/schemas.py:28`)
`@hpr_confianza`, `@nivel1`, `@web_search`, `N1 · Búsqueda Cognitiva`,
`N2 · Grafo de Consistencia`, `MotorRazonamientoSuperior`, `SOVEREIGN-GATE`.

### Servicios / núcleo
`SessionManager` (en memoria, singleton `main.py:217`) · motor determinista `src/core/engine.py` ·
`src/security_agent.py` (+ `src/core/security_agent.py`) · `src/execution_log.py` ·
razonamiento (`deep_synthesizer`, `structural_threading`, `iterative_planner`,
`reasoning_engine`, `causal_synthesis`, `claim_evaluator`, `verified_reasoning`,
`episodic_memory`, `stratified_reasoning`, `triage`).

### UI web (`src/web_ui/`)
`index.html` (paneles `#tech-pane`/`#chat-pane`; indicadores `#conf-ind-1..3`; telemetría
`#latency/#tokens/#subtasks/#validations`; traza `#events`) · `app.js` (~1000 L) · `styles.css`.

### Estado y actualización
Sesión chat: `sessionId` (JS) ↔ SessionManager (memoria). Telemetría: polling cada 5 s
(`TELEMETRY_INTERVAL_MS`, `app.js:909`). Auditoría: append a
`boveda y vitacoras/logs/execution_YYYY-MM-DD.jsonl` con hash SHA-256.

### Evidencia en logs
- `execution_2026-10-15.jsonl`: `@web_search` → `no_disponible` con **`success:true`**.
- `execution_2026-10-16.jsonl` (líneas 5, 19): `@web_search` sin payload → `error` con `success:true`.
- **El chat NO se registra** con `log_execution` → no auditable.

---

## 2. FASE B — Reproducción controlada B1–B5 (Paso 4)

Reproducido con `FastAPI TestClient` contra HEAD `6c1afff`, en worktree aislado.
Arnés: `%TEMP%\opencode\faseb_repro.py`.

| Caso | Entrada exacta | Esperado | Observado | Discrepancia |
|---|---|---|---|---|
| **B1** | `POST /api/v1/chat {"message":"hola"}` | saludo natural | `"Análisis técnico profundo de: \"hola\". Se procesaron 1 fuentes..."` | ❌ |
| **B1-UI** | (render de respuesta) | limpieza DOM | etiqueta "Procesando…" nunca se restablece (`app.js:435` vs `updateMessage` `app.js:478-505`) | ❌ |
| **B2** | `"Como estara la bolsa de valores manana?"` | ruta especializada + datos reales | mismo informe sintético genérico | ❌ |
| **B3** | `@web_search` + payload válido | payload validado y datos presentados | `success:true`, `no_disponible`; **payload descartado** | ❌ |
| **B4.a/b** | `@web_search` sin/`"   "` payload | error explícito | `success:true`, `no_disponible` | ❌ |
| **B4.c** | `SOVEREIGN-GATE` nivel 1 | rechazo | rechazo explícito | ✅ |
| **B4.d** | `session_id` inexistente | error/advertencia | auto-reparación silenciosa | ❌ |
| **B4.e** | `confidence_level:9` | validación de contrato | HTTP 422 | ✅ |
| **B5** | sesión + repetir + polling + tab switch | sin pérdida/doble ejecución | backend OK; **desfase de contador de turnos** (3 vs 5) | ⚠️ parcial |

**7 defectos demostrados:** informe forense a saludo; informe forense a consulta financiera;
payload descartado; éxito engañoso ×2; reparación silenciosa de sesión; etiqueta DOM no limpiada.

El productor del string forense es `src/core/deep_synthesizer.py:341`.

---

## 3. FASE C — Auditoría de contratos (Paso 5)

### Mapa (productor → consumidor)
`ChatRequest/ChatResponse` (`main.py:245/253`) · `OrchestrateRequest/Response` (`main.py:262/274`) ·
`TriggerExecutionRequest/Response` (`schemas.py:40/64`) · `SessionContext` (`contracts.py:277`) ·
`PipelineRequest/PipelineResult` (`contracts.py:332/345`) · `Evidence/ClaimEvaluation/StructuredResult`
(`contracts.py:44/78/110`) · `/telemetry` y `/logs*` (dict crudo, sin `response_model`).

### Hallazgos (26) — críticos
- **C1** `process_pipeline` retorna `dict` **o** `str` (unión no declarada);
  consumidores hacen `.get()` (`main.py:799`, `multilingual/router.py:111`) → `AttributeError` ante bloqueo.
- **C2** Contratos paralelos del pipeline: `proceso_pipeline` (`security_agent.py:119`),
  `process_pipeline` (`:355`), `AgenteChat.responder` (`desktop/agent.py:78`), `PipelineResult` sin uso.
- **C3** `PipelineResult` es eludido por `/api/v1/chat`.
- **C4** `TriggerExecutionResponse.result` sin esquema (7+ formas).
- **C5** `telemetry` del trigger heterogéneo (5 formas).
- **C6** `success=True` con `result.estado ∈ {error, no_disponible}` → éxito engañoso.
- **C7** Correlación: se responde `request.session_id`, no la sesión real creada (`main.py:1457` vs `1118`).
- **C21** `confidence_level` es heurística (`main.py:1291`), no validación real.

### Hallazgos — altos
- **C10** `ChatResponse.session_context` es dict manual con pérdida (`main.py:867-876`).
- **C11/C12** `ChatResponse` sin `execution_id`, `intent/route`, `sources`, `telemetry` → Console no audita el chat.
- **C13/C14** Doble semántica del mismo campo DOM (`#validations`, `#tokens`) y etiquetas
  `total_turns`→SUBTAREAS / `active_sessions`→VALIDACIONES (`app.js:944-953`).
- **C15** `verify_security_guard` sólo inspecciona `?query=`; el chat lo envía (`app.js:359`), el trigger **no** (`app.js:201`).
- **C16** `@web_search` descarta payload/parameters (HEAD).
- **C20** Contratos ricos de evidencia/confianza no conectados al camino chat/trigger.

### Hallazgos — medios
- **C8** `session_id` UUID vs str; `payload` inexistente en HEAD.
- **C17** Rama `SOVEREIGN_GATE` inalcanzable (`main.py:1208` vs `1348`).
- **C18** `confidence_level==3` rechaza cualquier trigger (entrada ≠ autorización).
- **C19** `IDIOMA_JUSTIFICACIONES` no definido (`router.py:117`).
- **C22** `execution_time_ms` duplicado. **C23** `/telemetry` y `/logs*` sin `response_model`.
- **C24** `epsilon_wall_validation` no invocado. **C25** `get_log_stats` infla `successful`.
- **C26** Numeración de turnos no determinista (B5).

### Rutas que eluden los esquemas comunes
`process_pipeline` (dict|str) ≠ `PipelineResult` · `/telemetry` y `/logs*` sin modelo ·
`_execute_trigger_internal` con dicts ad-hoc · `AgenteChat.responder` (4.º camino) ·
ruta de triggers sin `?query=` (elude el guardia).

### Propuesta de corrección mínima (NO implementada)
1. Unificar el pipeline en `PipelineResult` (sin retorno `str`).
2. `response_model` en `/telemetry` y `/logs*`.
3. `TriggerResult` tipado y `success` derivado de `result.estado`.
4. Propagar `session.id` real.
5. Extender `ChatResponse` con bloque `execution` (id, ruta, telemetría, fuentes).
6. Unificar telemetría UI y corregir etiquetas.
7. Alinear `confidence_level` con la validación real.
8. Unificar tipo de `session_id` y aplicar `verify_security_guard` a triggers.

---

## 4. Estado del Plan Maestro

| Paso | Fase | Estado |
|---|---|---|
| 1 | Directiva general | ✅ |
| 2 | Modelo funcional | ✅ |
| 3 | Fase A — Inventario | ✅ (0 cambios) |
| 4 | Fase B — Reproducción B1–B5 | ✅ (0 cambios) |
| 5 | Fase C — Auditoría de contratos | ✅ (0 cambios) |
| **6** | **Fase D — Trazabilidad extremo a extremo (capas 1–8)** | ⏸️ **PENDIENTE** |
| 7–13 | Fases E–H y cierre | ⏸️ pendientes |

**Reactivación:** Paso 6 — Fase D. Sin código hasta la Fase G (Paso 9).

---

## 5. Prompt de reenganche (una línea)

`Retomo el Plan Maestro de Auditoría HPR. Fase A (Paso 3), Fase B (Paso 4) y Fase C (Paso 5) están cerradas con 0 modificaciones; baseline HEAD 6c1afff (main). Ejecuta ahora el PASO 6 — FASE D: Trazabilidad de extremo a extremo (capas 1–8: entrada del usuario → detección de intención → router → trigger → pipeline → construcción de respuesta/contexto → estado de sesión → vistas), en solo lectura, registrando en cada límite datos recibidos/emitidos, modelo, id de ejecución, transformaciones, excepciones y campos descartados; al terminar, detente y solicita autorización antes del Paso 7.`
