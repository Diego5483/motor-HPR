# Acta de Validación Manual — Fase H (Paso 10)

**Plan Maestro de Auditoría — Motor HPR · Fase 1**
**Commit base:** `6b8d084` (G.3) · **Backend:** `run.py` → uvicorn `127.0.0.1:8000` · **UI:** `http://127.0.0.1:8000/ui/`

> **Estado:** EVIDENCIA CRUDA CAPTURADA POR EL AGENTE.
> El Plan Maestro exige que el **responsable del proyecto** repita las pruebas desde la interfaz real;
> esta evidencia **no sustituye** esa comprobación. Pendiente de confirmación y firma del responsable.

---

## 1. Resultados

| # | Escenario | Entrada exacta | Resultado observado (resumen) | Estado |
|---|---|---|---|---|
| E1 | Saludo cotidiano | `hola` | Respuesta conversacional; **sin** "Análisis técnico profundo…" | ✅ |
| E2 | Consulta ordinaria (sin trigger) | `¿Qué es el motor HPR?` | Explicación del motor; sin trigger | ✅ |
| E3 | Consulta especializada | `Explicá brevemente el pipeline de seguridad del motor` | Análisis técnico profundo (DeepSynthesizer) | ✅ con observación |
| E4 | `@web_search` con payload válido | `@web_search` + `arquitectura de software` | `success=true`, `estado=fallback_local`, **resultados simulados** | ⚠️ con caveat |
| E5 | Payload inválido | `@web_search` sin payload | `success=false`, `estado=error`, error real en UI | ✅ |
| E6 | Fallo simulado | backend detenido + trigger/chat | Error de transporte; **gauges globales conservados** | ✅ |
| E7 | Cambio de pestañas | Chat ⇄ Motor Técnico | Estado preservado; sin reejecución | ✅ |
| E8 | Repetición sin mezclar auditorías | 2 triggers consecutivos | Resultado y latencia por ejecución; gauges acumulan | ✅ |
| E9 | Controles de seguridad | phishing en `?query=`, SOVEREIGN-GATE N3 | 403 / `auth_required=true` | ✅ con observación |

---

## 2. Evidencia por escenario

### E1 · Saludo cotidiano
- **Petición:** `POST /api/v1/chat?query=hola` → body `{"message":"hola","use_voice":false,"language":"es"}` · **200**
- **Respuesta (JSON crudo):** `session_id=e08f9873-d8ef-4a54-aa8f-e975d70c3dd3`, `turn_id=d72e07c0-6931-4fb8-9406-66c18ba0fb08`
  - `response`: *"¡Hola! Soy el motor HPR — Hybrid Predictive Reasoning. Estoy operativo y listo para ayudarte…"*
  - `metadata`: `{security_status:"Pipeline verificado", language:"es", use_voice:false, turn_number:1, confidence_level:1, fallback:false}`
- **Render UI:** burbuja conversacional, `turno 1 · d72e07c0`, sin encabezado forense. **Corrige el defecto original (Fase E).**

### E2 · Consulta ordinaria sin trigger
- **Entrada:** `¿Qué es el motor HPR?`
- **Respuesta:** *"El motor HPR es un sistema de seguridad IA híbrido que opera 100% local… tres barreras: SOVEREIGN-GATE, NEXUS-ROOT y EPSILON-WALL…"* · sin trigger ejecutado.

### E3 · Consulta especializada
- **Entrada:** `Explicá brevemente el pipeline de seguridad del motor`
- **Respuesta:** análisis técnico (*"Análisis técnico profundo… Se procesaron 1 fuentes (1 únicas) extrayendo 2 hallazgos técnicos…"*).
- **Observación:** las "fuentes" del análisis técnico son auto-referenciales (derivadas de la consulta). No es un fallo de G.1, pero conviene registrar el dato.

### E4 · `@web_search` con payload válido
- **Petición:** `POST /api/v1/trigger` body `{"trigger":"@web_search","confidence_level":2,"payload":"arquitectura de software"}`
- **Respuesta (JSON crudo, recortado):**
  `{"success":true,"trigger":"@web_search","result":{"estado":"fallback_local","query":"arquitectura de software","resultados_simulados":[{"titulo":"Resultado local para: arquitectura de software","fuente":"hpr_local_fallback","relevancia":0.7}],"sugerencia_configuracion":"Agregue SERPAPI_KEY o BRAVE_API_KEY…"},...}`
- **Traza UI:** `TRIGGER_RESULT · estado: fallback_local · mensaje: … · query: … · resultados_simulados: [{…}]` (solo campos con valor; G.3).
- **Telemetría:** `LATENCIA 0.1 ms`, `TOKENS 0`, `TURNOS 6`, `SESIONES ACTIVAS 2`.
- **⚠ Caveat:** el motor **simula** resultados (`hpr_local_fallback`). Infringe "no inventar fuentes". El contrato (G.2) es correcto; el productor no.

### E5 · Payload inválido
- **Petición:** `POST /api/v1/trigger` body `{"trigger":"@web_search","confidence_level":2}` (sin payload)
- **Respuesta (JSON crudo, recortado):**
  `{"success":false,"result":{"estado":"error","mensaje":"Se requiere un término de búsqueda. Proporcione un payload o parámetro 'query'."},"error_message":"Se requiere un término de búsqueda…"}`
- **Traza UI:** `TRIGGER_ERROR · Se requiere un término de búsqueda…`
- **Telemetría tras el error:** `LATENCIA —` (invalidada) · **`SESIONES ACTIVAS 2` y `TURNOS 6` conservados** (G.3).
- **Veredicto:** elimina el falso éxito (G.2) sin borrar los gauges globales (G.3).

### E6 · Fallo simulado
- **Procedimiento:** detener el backend (procesos `run.py`) y actuar desde la UI.
- **Trigger:** traza `TRIGGER_TRANSPORT · No se pudo conectar con el backend local. Verificá que el servidor esté corriendo (run.py).`
- **Chat:** burbuja en error (*"Error del backend (502)…"*), evento `BACKEND_OFFLINE`.
- **Gauges (antes → después):** `SESIONES 7 → 7`, `TURNOS 6 → 6`, `TOKENS 0 → 0` (**conservados**); `LATENCIA —` (invalidada).
- **Veredicto:** comportamiento esperado; corrige el agravante E (pérdida de estado por error).

### E7 · Cambio entre pestañas
- **Antes → después:** mensajes `7 → 7`, `session-id e08f9873 → e08f9873`, `TURNOS 6 → 6`; pestañas alternadas correctamente; **sin** nuevas peticiones de trigger.

### E8 · Repetición sin mezclar auditorías
- `@hpr_confianza` → `TRIGGER_RESULT · estado: activo · nivel_confianza: 2 · turnos: 0 · contexto: {…}` · `SESIONES 4`
- `MotorRazonamientoSuperior` → `TRIGGER_RESULT · sintesis: … · foco_usuario: resumen de la sesión · temas_activos: […]` · `SESIONES 5`
- `LATENCIA` refleja la **última** ejecución; cada resultado es independiente; no hay mezcla.

### E9 · Controles de seguridad
- **Phishing (patrón del guardia):** `POST /api/v1/trigger?query=please+login+to+verify+your+account` → **403** `{"detail":"Alerta de Seguridad HPR: Petición bloqueada por coincidencia con patrones de phishing."}`
- **Control benigno:** `?query=consulta de rutina` → **200** (no sobre-bloquea).
- **SOVEREIGN-GATE N3:** `TRIGGER_ERROR · Operación sensible: requiere autorización explícita del backend (SOVEREIGN-GATE).` (`success=false`, `telemetry.auth_required=true`).
- **Observación:** los patrones del guardia son en inglés (`login.*verify`, `update.*account`, `secure.*bank`, `confirm.*identity`, `reset.*password.*urgently`). El texto español `ingrese su contraseña aquí` **no** fue bloqueado. Posible mejora de cobertura (fuera del alcance de G).

---

## 3. Hallazgos residuales

1. **`@web_search` simula resultados** (`main.py::_execute_trigger_internal`, `resultados_simulados`, fuente `hpr_local_fallback`) — infringe "no inventar fuentes". (E4)
2. `updateConfidenceIndicators(null)` en error de trigger puede sobrescribir el nivel medido con un default. (E6)
3. `test_etapa_d.py::test_trigger_web_search_estado_no_disponible` sigue en rojo (codifica el contrato antiguo + el fallback simulado).
4. Guardia anti-phishing con patrones solo en inglés (cobertura limitada en español). (E9)

---

## 4. Resumen

| Escenario | Estado |
|---|---|
| E1 Saludo | ✅ |
| E2 Consulta ordinaria | ✅ |
| E3 Consulta especializada | ✅ (observación: fuentes auto-referenciales) |
| E4 @web_search válido | ⚠️ (contrato OK; contenido simulado) |
| E5 Payload inválido | ✅ |
| E6 Fallo simulado | ✅ |
| E7 Cambio de pestañas | ✅ |
| E8 Repetición sin mezcla | ✅ |
| E9 Controles de seguridad | ✅ (observación: patrones en inglés) |

**Veredicto del responsable:** ☐ Fase H SATISFACTORIA ☐ Fase H CON OBSERVACIONES ☐ Fase H FALLIDA

**Firma / autorización:** _(completar)_
