# Acta de Aceptación de la Fase 1 — Motor HPR

**Plan Maestro de Auditoría Arquitectónica · Cierre Verificable y Aceptación de la Fase 1**
**Commit evaluado y validado:** `d680e27` (Commit B, G2) · **Fecha:** 2026-10-17
**Acta de cierre P5:** `docs/auditorias/ACTA_CIERRE_P5.md` · **Inventario:** `docs/auditorias/INVENTARIO_NUCLEO_VIVO.md` · **Deuda:** `docs/auditorias/DEUDA_TECNICA_FASE1.md`
**Estado: FASE 1 ACEPTADA — con reserva documentada (Decisión nº 5).**

> Este acta **no** declara verde el indicador global de cobertura. Acepta la Fase 1 sobre el **alcance delimitado y ratificado** (núcleo vivo, Escenario B), publicando además las cifras globales reales y la deuda residual.

---

## 1. Objeto y base normativa

| Norma | Referencia | Aplicación |
|---|---|---|
| **P5** (cobertura medible) | `docs/constitution.md:58` | Medición real de cobertura; módulos de seguridad con cobertura completa de ramas. |
| Umbral 80 % | `HPR/pyproject.toml:18` (`fail_under = 80`) | Compuerta configurada sobre **todo** `src/`; hoy **diferida** al alcance (Decisión nº 5). |
| **D2 / D3** (aprobadas) | Hoja de ruta (Pasos 1–13 / P5) | Alcance por núcleo vivo con justificación; la medición real de producción es la línea base oficial. |
| **D6** (sin placeholders) | `docs/constitution.md:48` | Lo no alcanzable es **deuda declarada**, no avance. |
| Salvaguardas **R6-1…R6-6** | `docs/alcance-formal-cobertura-p5-nucleo-vivo.md` §5.3 | Exclusión ≠ cubierto; reingreso automático; prohibido cubrir código muerto con pruebas artificiales. |

---

## 2. Recorrido de las compuertas (G0–G4)

| Compuerta | Objeto | Commit | Resultado |
|---|---|---|---|
| **G0** | Congelar línea base | `55e225e` | Acta de cierre P5 corregida (métricas etiquetadas, 10 módulos, nombre exacto de la suite) y congelada |
| **G1** | Formalizar P5/R5.1 en `docs/auditorias/` | `8bc0465` | Acta de cierre, inventario del núcleo vivo y registro de deuda |
| **G2** | Corrección funcional **H2** | `d680e27` | Handlers honestos (`no_disponible`); prueba rojo→verde; deuda actualizada |
| **G3** | Auditar regresiones y defectos conocidos | (auditoría de `d680e27`) | Sin regresiones; `xfail` no degradado; integridad verificada (+ hallazgo G3-O1) |
| **G4** | Emitir acta de aceptación de Fase 1 | **Commit C (este documento)** | **ACEPTACIÓN** de la Fase 1 |

---

## 3. Commit evaluado y evidencia reproducible

| Hecho | Evidencia |
|---|---|
| Commit evaluado y validado | **`d680e27`** — `fix(triggers): N1/N2/MotorRazon declaran no_disponible en vez de afirmar trabajo no realizado (H2)` |
| HEAD de la evaluación | `d680e27` |
| Cambios pendientes en `src/` al evaluar | **ninguno** |
| Nada pusheado | sí (`main` por delante de `origin/main`) |

**Invocación de la medición (entorno local, P6):**
```powershell
$env:PYTHONPATH="…\motor HPR\HPR;…\motor HPR\HPR\src"
& "…\.venv\Scripts\python.exe" -m pytest -q -o addopts="" --continue-on-collection-errors `
  --cov=src --cov-branch --cov-report=json:<tmp>\cov.json --cov-fail-under=0
```

---

## 4. Alcance delimitado y métricas finales reproducibles

**Alcance oficial de aceptación = núcleo vivo (Escenario B): 2 945 sentencias, 18 módulos** (alcanzables desde `src.main` y/o `src.desktop`), delimitado y justificado en `docs/auditorias/INVENTARIO_NUCLEO_VIVO.md`.

| Indicador | Líneas | Ramas | Oficial (líneas+ramas) |
|---|---|---|---|
| **NÚCLEO VIVO (Escenario B)** | **2 611/2 945 = 88.66 %** | **799/992 = 80.54 %** | **86.61 %** |
| · VIVO-API | 2 152/2 397 = 89.78 % | 697/872 = 79.93 % | 87.15 % |
| · VIVO-DESKTOP | 110/199 = 55.28 % | 26/44 = 59.09 % | 55.97 % |
| · VIVO-COMPARTIDO | 349/349 = 100 % | 76/76 = 100 % | 100.00 % |
| Escenario C (anexo: núcleo vivo + Streamlit) | 2 683/3 051 = 87.94 % | 817/1 024 = 79.79 % | 85.89 % |
| Producción (`src/` sin `test_*`) | 2 712/6 111 = 44.38 % | 827/2 074 = 39.87 % | 43.24 % |
| `src/` completo (incluye `test_*.py`) | 5 181/8 666 = 59.79 % | 904/2 182 = 41.43 % | **56.09 %** ← métrica del `fail_under` |

- **Meta del 80 % (líneas) = 2 356,0; cubiertas 2 611 → margen de +255 líneas.** El núcleo vivo cumple el umbral **en ambos ejes** (líneas 88.66 % ≥ 80 %; ramas 80.54 % ≥ 80 %).
- **Exclusiones justificadas** (no alcanzables; no cuentan como cubiertas): HUÉRFANO 1 284 st, ALT-LEGACY 1 762 st + fachadas 7 st (total 3 031 st). Ver `INVENTARIO_NUCLEO_VIVO.md` §4.
- **Techo global honesto:** con el denominador completo el 80 % es inalcanzable (techo estructural 50.4 %); de ahí la delimitación ratificada.
- La corrección de H2 retiró 4 sentencias deshonestas de `main.py`, por lo que el denominador del núcleo vivo pasó de 2 949 a **2 945** st (líneas 88.67 % → 88.66 %; sin pérdida de cobertura).

---

## 5. Resultados de la suite de pruebas

| Métrica | Valor |
|---|---|
| **passed** | **441** |
| **failed** | **0** |
| **errors** | **0** |
| **skipped** | **0** |
| **xfailed** | **0** |
| Warnings | 394 (deprecaciones de terceros; no fallos) |
| Marcadores `skip`/`skipif` en `src/` | 0 (la ausencia de *skipped* es real, no ocultamiento) |

- **Composición:** 435 pruebas previas al cierre + **6** nuevas de H2 (`src/test_h2_honestidad_triggers.py`) = 441. En el bloque R se añadieron 190 pruebas (R1–R5.1).
- **Suite oficial tal cual** (`addopts` de `pyproject.toml`): 441 passed y **exit 1** por `Required test coverage of 80.0% not reached. Total coverage: 56.09%` (reserva/Decisión nº 5).
- **Determinismo:** ejecuciones repetidas ⇒ conteos y cobertura idénticos; sin red real, sin `time.sleep` real, sin azar (dobles/mocks controlados).

---

## 6. Evidencia de la corrección funcional de H2

**Defecto (H2):** `N1_BUSQUEDA`, `N2_GRAFO` y `MOTOR_RAZON` afirmaban trabajo no realizado («Búsqueda cognitiva **ejecutada**…», «Grafo de consistencia **verificado**…», `sintesis` literal) sin `estado`, derivando un **falso éxito**.

**Corrección (Commit B, `d680e27`; `src/main.py:1168-1208`):** los tres handlers declaran ahora `estado = "no_disponible"` con mensajes que explicitan que **no se realizó trabajo ni se generan resultados simulados**, alineados con el estándar honesto de `WEB_SEARCH` (`src/main.py:1150-1166`). Por el contrato G.2 (`estado not in {"error","no_disponible"}`) el endpoint deriva **`success=False`**.

| Evidencia | Resultado |
|---|---|
| Prueba **rojo→verde** | 5 fallos sobre el código previo → verde tras la corrección (sin mocks) |
| Pruebas nuevas | `src/test_h2_honestidad_triggers.py` (6), incluidas rutas con y sin historial de sesión |
| Pruebas actualizadas al contrato honesto | `test_etapa_d.py` (3) y `test_cov_r1_seguridad.py` (1 aserción) |
| Garantía | `N1`/`N2`/`MOTOR_RAZON` ya **no** afirman búsqueda, verificación ni síntesis realizadas |

---

## 7. Estado de los contratos arquitectónicos

| Contrato | Estado | Evidencia |
|---|---|---|
| **Retorno unificado `dict` en `process_pipeline`** | **Preservado** | `test_engine.py` (`resultado["estado"].startswith("Pipeline verificado…")`) + guarda de normalización defensiva `src/main.py:794-797` (B3) |
| **G.1 — desacople conversacional/analítico** | **Preservado** | `src/test_cov_r2_ruteo.py` (28): `test_ruteo_saludo_va_a_conversacional`, `test_ruteo_consulta_tecnica_va_a_sintesis`, `test_chat_g1_no_secuestra_saludo`, `test_chat_memoria_de_sesion_crece` |
| **G.2 — contratos tipados + éxito derivado** | **Preservado** | `TriggerResult(extra="forbid")` y `success` derivado del `estado`; `src/test_g2_contrato_trigger.py` (6) |

Sin regresión en ninguno de los tres (controles G3 en verde: 157 passed / 0 failed).

---

## 8. Política de cero alucinaciones y ausencia de respuestas simuladas

- `WEB_SEARCH` y los tres triggers de H2 responden `no_disponible` declarando textualmente que el motor **no genera resultados simulados** (`src/main.py:1166,1181,1192,1208`).
- **Seguridad:** `src/security_agent.py:230` aplica la política de cero alucinaciones («no genero información inventada») ante baja confianza.
- **Pruebas que fijan el criterio:** `test_etapa_d.py:195` (`assert not result["resultados_simulados"]`), `test_g3_nexus_console.py:110` (`assert "resultados simulados" not in appjs`), `src/test_h2_honestidad_triggers.py` (5 aserciones de «no simulado»).
- **Contratos tipados:** `resultados_simulados` es `Optional` y permanece `None` en las rutas honestas (`src/schemas.py:99`).

**Conclusión:** no hay rutas críticas que fabriquen fuentes ni resultados; la ausencia de respuestas simuladas es **verificable** por pruebas.

---

## 9. Deuda técnica residual y decisiones diferidas

Registro completo en `docs/auditorias/DEUDA_TECNICA_FASE1.md`. Resumen de lo **no** resuelto en la Fase 1 (deuda declarada, D6):

| ID | Hallazgo | Criticidad | Compuerta prevista |
|---|---|---|---|
| **H1** | «Núcleo de razonamiento» desconectado del motor vivo (1 337 st) | Media (estructural) | Estructural (H1/H3/H4) |
| **H3** | `core/triage.py` canónico es código muerto; la ruta viva usa el duplicado | Media | Estructural (H1/H3/H4) |
| **H4** | Colisión de nombres `nexus_root` (validación viva vs paquete legacy) | Media | Estructural (H1/H3/H4) |
| **H5** | Helpers sin invocador en `deep_synthesizer.py` | Baja | Helpers (H5/H5b) |
| **H5b** | Corpus perdido por clave `"corpus"` inexistente en ruta sin invocador | Media (latente) | Helpers (H5/H5b) |
| **G3-O1** | Suites **preexistentes** `test_g2_contrato_trigger.py` y `test_etapa_d.py` escriben en el log git-ignored de la bóveda al ejercitar el endpoint de trigger | Observación (mantenibilidad) | Aislamiento de logs en una compuerta futura |

**H2 — resuelto** (Commit B, G2). El resto permanece como deuda declarada; ninguna corrección adicional fue autorizada ni ejecutada.

---

## 10. Tratamiento de la Decisión nº 5 (instrumentación del umbral `fail_under = 80`)

**Estado: DIFERIDA y DOCUMENTADA.** El umbral permanece configurado sobre el conjunto completo, por lo que la invocación oficial **aborta legítimamente** (métrica oficial con ramas = 56.09 %; líneas = 59.79 %) y la verificación automática del criterio **no está instrumentada** para el alcance ratificado.

| Opción | Contenido | Estado |
|---|---|---|
| **O5-a** | Verificación acotada al núcleo vivo (fuentes explícitas) con `--cov-fail-under=80`, publicando además el indicador global | Propuesta (recomendada) |
| **O5-b** | Trinquete anti-regresión: suelo del núcleo vivo en el valor medido (**88.66 % líneas**), sólo al alza | Propuesta (recomendada) |
| **O5-c** | Diferir a CI y aceptar por medición | **Vigente en esta Fase 1** |

**La aceptación de la Fase 1 se otorga bajo O5-c** (aceptación por medición reproducible), con O5-a/O5-b recomendadas para la fase de instrumentación. Ninguna opción baja el umbral.

---

## 11. Declaración formal de aceptación

Se **ACEPTA la Fase 1 del Motor HPR** sobre el alcance delimitado y ratificado (núcleo vivo, Escenario B), con las siguientes condiciones verificadas en el commit evaluado **`d680e27`**:

1. Suite íntegra: **441 passed / 0 failed / 0 errors / 0 skipped / 0 xfailed**, reproducible y determinista.
2. Cobertura del núcleo vivo: **88.66 % líneas** y **80.54 % ramas** (≥ 80 % en ambos ejes; meta de líneas = 2 356,0; cubiertas 2 611).
3. Corrección funcional de **H2** con prueba rojo→verde; handlers honestos (`no_disponible`).
4. Contratos arquitectónicos **G.1**, **G.2** y `process_pipeline` (dict) **preservados**.
5. **Cero alucinaciones**: ausencia verificable de respuestas simuladas en rutas críticas y de seguridad.
6. Deuda residual (H1, H3, H4, H5, H5b, G3-O1) **declarada** y asignada a compuertas futuras; **Decisión nº 5 diferida bajo O5-c**.

**La aceptación es explícita, acotada al alcance declarado y no constituye una declaración de cobertura global del 80 %.**

---

## 12. Firma

| Rol | Nombre | Estado |
|---|---|---|
| Coordinación / responsable del proyecto | Coordinación HPR | **ACEPTADA** la Fase 1 — 2026-10-17 |
| Reviewer (auditoría independiente) | Reviewer HPR | Compuertas G0–G3 verificadas; sin regresiones; deuda y reserva documentadas |
