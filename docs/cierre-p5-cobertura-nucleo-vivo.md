# Cierre del criterio P5 — Cobertura del núcleo vivo

**Plan Maestro de Auditoría Arquitectónica — Motor HPR · Bloque R (cierre de P5)**
**Commit de cierre:** `350a36d` (R5.1) · **Actas previas:** `fcc109c` (alcance formal R6) · **Fecha:** 2026-10-17
**Alcance oficial:** Escenario B — núcleo vivo (ratificado en `docs/alcance-formal-cobertura-p5-nucleo-vivo.md` §10)
**Estado: CERRADA CON RESERVA** — P5 se cumple **por medición**; su **instrumentación automática** queda pendiente de la decisión nº 5 de este acta.

> Este acta **no** declara verde el indicador global. Publica las tres cifras reales, **con su métrica explícita**:
> núcleo vivo **88.67 % líneas / 86.64 % oficial (ramas)**, producción completa **44.42 % líneas / 43.29 % oficial**, `src/` completo **59.51 % líneas / 55.83 % oficial**.
> El umbral de `pyproject.toml` (`fail_under = 80`) sigue apuntando al conjunto completo y compara la métrica **oficial con ramas** (55.83 %); **hoy no se cumple**.

---

## 1. Objeto y criterio

| Norma | Referencia | Aplicación |
|---|---|---|
| **P5** (cobertura medible) | `docs/constitution.md:58` | Se mide la cobertura real sobre `src/`; los módulos de seguridad exigen 100 % de ramas. |
| Umbral 80 % | `HPR/pyproject.toml:18` | Compuerta configurada, aplicada hoy sobre **todo** `src/`. |
| Alcance | `docs/alcance-formal-cobertura-p5-nucleo-vivo.md` (§4 y §10) | **Núcleo vivo = 2949 sentencias** alcanzables desde `src.main` y/o `src.desktop`. Escenario C (Streamlit) queda como anexo; ALT-LEGACY y HUÉRFANO **excluidos del denominador** por no alcanzabilidad demostrada. |
| Línea base | Decisión **D3** | La medición real de producción es el indicador oficial. |
| Salvaguardas | R6-1…R6-6 (`docs/alcance-formal-cobertura-p5-nucleo-vivo.md` §5.3) | La exclusión no declara cubierto nada; reingreso automático si un módulo se conecta; prohibido cubrir código muerto con pruebas artificiales. |

> **Dos métricas, siempre etiquetadas (corrección G0/D-G0-3).** *Líneas* = `covered_lines / num_statements` (la cifra de la línea base y del trinquete). *Oficial (ramas)* = `(covered_lines + covered_branches) / (num_statements + num_branches)`, que es el `percent_covered` de `coverage.py` y la cifra contra la que compara `fail_under`. Donde el acta cita un solo número se indica la métrica; los agregados de §3 y §5 se publican en **ambas**.

---

## 2. Recorrido de las compuertas (evidencia)

| Compuerta | Commit | Suite / artefacto | Objetivo |
|---|---|---|---|
| **R1** · seguridad y triaje | `d2031a7` | `src/test_cov_r1_seguridad.py` (43 pruebas) | `security_agent`, `core/security_agent`, `core/engine`, `main.py` (triggers), `validador_niveles_confianza` |
| **R1-FIX** | `457c2d8` | `src/core/engine.py` (1 línea) | `NivelRiesgo.CRITICO` sin tilde; retirado el `xfail` |
| **R2** · ruteo | `ed2c72f` | `src/test_cov_r2_ruteo.py` (28 pruebas) | `main.py` · ruteo conversacional/técnico, `orchestrate_endpoint` (DAG) |
| **R3** · resiliencia | `b455fba` | `src/test_cov_r3_resiliencia.py` (43 pruebas) | `main.py` · `RetryConfig`, `with_retry`, `LocalFallback`, endpoint de trigger, telemetría/logs |
| **R4** · multilingüe | `d627392` | `src/test_cov_r4_multilingue.py` (23 pruebas) | `multilingual/{detector, router, selector}` |
| **R4-FIX** | `94fd4bd` | `src/multilingual/router.py` (2 líneas) | `NameError` de `IDIOMA_JUSTIFICACIONES` → `detector.JUSTIFICATIONS` |
| **R5.0** · diagnóstico | — (sin artefactos) | Análisis AST de alcanzabilidad | Determina el núcleo vivo y aritmética de P5 |
| **R6** · alcance formal | `fcc109c` | `docs/alcance-formal-cobertura-p5-nucleo-vivo.md` | Denominador oficial + salvaguardas + hallazgos H1–H4 |
| **R5.1** · núcleo de síntesis | `350a36d` | `src/test_cov_r5_1_deep_synthesizer.py` (53 pruebas) | `core/deep_synthesizer.py` (extracción, narrativa, expansión contextual) |

**Pruebas añadidas en el bloque R: 190** (43 + 28 + 43 + 23 + 53). **Ninguna** reescribe ni relaja una prueba previa; **ningún** módulo de `src/` fue modificado salvo las dos correcciones atómicas declaradas (R1-FIX, R4-FIX), cada una con prueba rojo→verde.

### Progresión de la medición de producción

| Momento | Producción (`src/` sin `test_*`) |
|---|---|
| Línea base (pre-R2) | 28.52 % |
| Pre-R3 | 36.43 % |
| Pre-R4 | 38.53 % |
| Post-R4 | 39.77 % |
| **Post-R5.1 (este cierre)** | **44.42 % (2716/6115)** |

---

## 3. Medición de cierre — núcleo vivo (alcance oficial de P5)

| Grupo | st | cub. | Cob. líneas | Cob. oficial (ramas) |
|---|---|---|---|---|
| VIVO-API | 2401 | 2156 | 89.80 % | 87.18 % |
| VIVO-DESKTOP | 199 | 110 | 55.28 % | 55.97 % |
| VIVO-COMPARTIDO | 349 | 349 | 100.00 % | 100.00 % |
| **NÚCLEO VIVO** | **2949** | **2615** | **88.67 %** | **86.64 %** |

**Meta del 80 % = 2359,2 líneas; cubiertas 2615 → margen de +256 líneas (10.8 % relativo sobre el umbral).**

### Detalle por módulo del núcleo vivo

| Módulo | Líneas cub./tot | Cob. líneas | Cob. oficial (ramas) | Sin cubrir |
|---|---|---|---|---|
| `src.core.deep_synthesizer` | 480/480 | 100.00 % | 99.7 % | 0 |
| `src.main` | 495/495 | 100.00 % | 99.3 % | 0 |
| `src.schemas` | 59/59 | 100.00 % | 100 % | 0 |
| `src.core.structural_threading` | 211/279 | 75.63 % | 69.8 % | 68 |
| `src.core.task_orchestrator` | 380/478 | 79.50 % | 74.6 % | 98 |
| `src.core.verified_reasoning` | 141/156 | 90.38 % | 84.4 % | 15 |
| `src.core.claim_evaluator` | 110/117 | 94.02 % | 92.0 % | 7 |
| `src.core.session_manager` | 189/229 | 82.53 % | 77.6 % | 40 |
| `src.execution_log` | 91/108 | 84.26 % | 80.6 % | 17 |
| `src.desktop.app` | 26/89 | 29.21 % | 26.7 % | 63 |
| `src.desktop.agent` | 55/57 | 96.49 % | 96.2 % | 2 |
| `src.desktop.voice` | 29/51 | 56.86 % | 54.1 % | 22 |
| `src.desktop.__main__` | 0/2 | 0.00 % | 0 % | 2 |
| `src.models.contracts` | 163/163 | 100.00 % | 100 % | 0 |
| `src.security_agent` | 100/100 | 100.00 % | 100 % | 0 |
| `src.core.engine` | 63/63 | 100.00 % | 100 % | 0 |
| `src.core.security_agent` | 14/14 | 100.00 % | 100 % | 0 |
| `src.validador_niveles_confianza` | 9/9 | 100.00 % | 100 % | 0 |

*Nota (corrección G0/D-G0-5): en la versión previa de este acta la columna «Cob.» de esta tabla mostraba el porcentaje **oficial con ramas**, mientras que la tabla de grupos de arriba mostraba el porcentaje **de líneas** sin etiquetarlo. Ambas columnas se publican ahora de forma explícita.*

### Indicadores complementarios (se publican, no se ocultan)

| Indicador | Líneas | Oficial (ramas) |
|---|---|---|
| Producción completa (`src/` sin `test_*`) | **44.42 %** (2716/6115) | 43.29 % |
| `src/` completo (incluye `test_*.py`) | **59.51 %** (5120/8604) | **55.83 % ← métrica del `fail_under`** |
| Escenario C (núcleo vivo + `app.py`/multilingüe) | 2615 + 72 = 2687/3055 = **88.0 %** | 85.92 % |
| Escenario A (base completa) | 44.42 % — techo estructural 50.4 % (ver acta R6 §6) | — |

---

## 4. Cumplimiento y reserva

**P5 (≥ 80 % de cobertura sobre el alcance ratificado): CUMPLIDO por medición** — 88.7 % (2615/2949), verificado con la suite completa en `350a36d` (`435 passed / 0 failed / 0 xfailed`).

**Reserva (decisión pendiente nº 5):** el umbral automático sigue configurado sobre el conjunto completo (`fail_under = 80` en `HPR/pyproject.toml:18`), que incluye las 3031 sentencias excluidas por no alcanzabilidad (ALT-LEGACY 1762 + HUÉRFANO 1262 + fachadas 7). Por eso hoy:

- cualquier ejecución sin `--cov-fail-under=0` **aborta** legítimamente: la métrica que compara el umbral es la **oficial con ramas = 55.83 %** (la de líneas es 59.51 %); ambas quedan por debajo del 80 %;
- la verificación automática del criterio **no está instrumentada** para el alcance ratificado.

**Opciones para instrumentarla** (a decidir; ninguna baja el umbral):

| Opción | Contenido | Coste |
|---|---|---|
| **O5-a** | Invocación de verificación acotada al núcleo vivo (fuentes explícitas) con `--cov-fail-under=80`, **manteniendo** la publicación del indicador global completo. | Bajo: comando documentado en CI/acta. |
| **O5-b** | Trinquete anti-regresión: fijar el suelo del núcleo vivo al valor medido (88.7 %) y exigir que sólo pueda subir; el total global se sigue publicando como diagnóstico. | Bajo: una constante documentada. |
| **O5-c** | Diferir la instrumentación automática a la fase de CI y cerrar P5 por medición (como en este acta). | Nulo ahora; deja el criterio sin guardia automática. |

*Recomendación del auditor:* **O5-a + O5-b** (verificación acotada + trinquete), porque cumple el criterio sin reblandecerlo y conserva la trazabilidad del indicador global. No se ejecuta sin autorización.

---

## 5. Registro consolidado de hallazgos (H1–H5)

| ID | Hallazgo | Evidencia (`archivo:línea`) | Estado |
|---|---|---|---|
| **H1** | El "núcleo de razonamiento" está desconectado del motor vivo (1337 sentencias) | `core/reasoning_engine.py:89,744`; `core/iterative_planner.py:193,326`; `core/episodic_memory.py:451`; `core/causal_synthesis.py:20`; `core/stratified_reasoning.py` (importado sólo por `nexus_root/executor.py:25`) | Registrado — sin corregir |
| **H2** | Triggers `N1_BUSQUEDA`, `N2_GRAFO` y `MOTOR_RAZON` afirman trabajo no realizado | `main.py:1168-1179`, `:1181-1189`, `:1191-1200` (contraste honesto: `WEB_SEARCH` `:1150-1166`) | Registrado — sin corregir |
| **H3** | `core/triage.py` (implementación canónica de R1) es código muerto; la ruta viva usa el duplicado | `core/triage.py:19` vs `core/engine.py:178`; único importador `test_triage.py:9`; uso vivo `desktop/agent.py:33,112` | Registrado — sin corregir |
| **H4** | Colisión de nombres `nexus_root` (validación viva vs paquete legacy inalcanzable) | `core/engine.py` + `main.py:1380` vs `nexus_root/__init__.py:1-2` | Registrado — sin corregir |
| **H5** | Código sin invocador dentro del módulo vivo: `_extraer_metricas_agrupadas` y `_generar_informe_con_expansion` | `core/deep_synthesizer.py:264-283` y `:1110-1146` (grep en todo el repositorio: sólo su definición) | **Nuevo (R5.1)** — sin corregir |
| **H5b** | Corpus perdido en la ruta de expansión sin invocador: se consulta la clave `"corpus"`, inexistente en `metricas_procesamiento` | `core/deep_synthesizer.py:1126` vs clave real `total_caracteres_procesados` en `:114` | **Nuevo (R5.1)** — sin corregir |

**Deuda técnica declarada (residual de cobertura, medida y no ocultada):** 2 ramas parciales defensivas e inalcanzables por construcción en `core/deep_synthesizer.py` (`497->491`, `531->525`), documentadas en el docstring de `src/test_cov_r5_1_deep_synthesizer.py`. El módulo queda en **99.72 % de ramas**, con **0 líneas sin cubrir**.

---

## 6. Deuda declarada tras el cierre (no ejecutada)

Conforme a **D6** ("sin placeholders"), sigue declarado y sin autorizar:

1. **Código no alcanzable** (3031 sentencias): retiro/archivo o reconexión real de ALT-LEGACY y HUÉRFANO (H1, H3, H4).
2. **Honestidad de triggers** (H2): requiere compuerta de corrección con prueba rojo→verde sobre `src/main.py`.
3. **Helpers sin invocador** (H5/H5b): retirar o reconectar en `core/deep_synthesizer.py`.
4. **Cobertura del resto del núcleo vivo** (334 líneas en **10 módulos**: 6 de VIVO-API + 4 de VIVO-DESKTOP; principalmente `desktop/app.py` 63, `task_orchestrator` 98, `structural_threading` 68, `session_manager` 40).
5. **Instrumentación del umbral** (decisión nº 5, §4).

---

## 7. Estado del repositorio y evidencia reproducible

| Hecho | Evidencia |
|---|---|
| HEAD | `350a36d` (`test(cov): cubrir DeepSynthesizer: extraccion, narrativa y expansion contextual (P5.6, R5.1)`) |
| Cambios pendientes en `src/` | **ninguno** |
| Suite | **435 passed / 0 failed / 0 xfailed** |
| Bóveda | intacta (`BOVEDA_INTACTA: True`, medida con la suite R5.1 aislada) |
| Nada pusheado | sí |

**Invocación de la medición (P6, entorno local):**

```powershell
$env:PYTHONPATH="…\motor HPR\HPR;…\motor HPR\HPR\src"
& "…\.venv\Scripts\python.exe" -m pytest -q -o addopts="" --continue-on-collection-errors `
  --cov=src --cov-branch --cov-report=json:<tmp>\cov.json --cov-fail-under=0
```

Agregación del núcleo vivo: **Anexo A**.

---

## 8. Firma

| Rol | Nombre | Estado |
|---|---|---|
| Coordinación / responsable del proyecto | Coordinación HPR | **Pendiente de ratificación del cierre** |
| Reviewer (auditoría independiente) | Reviewer HPR | Recorrido R1–R5.1 verificado; hallazgos H1–H5 registrados; 2 ramas residuales declaradas |

---

## Anexo A · Agregación reproducible del núcleo vivo

```python
import json
COV = r"<tmp>\cov.json"           # salida del pytest anterior

GRUPOS = {
    "VIVO-API": ["src.main", "src.schemas", "src.execution_log",
                 "src.core.deep_synthesizer", "src.core.session_manager",
                 "src.core.structural_threading", "src.core.task_orchestrator",
                 "src.core.verified_reasoning", "src.core.claim_evaluator"],
    "VIVO-DESKTOP": ["src.desktop.__main__", "src.desktop.agent",
                     "src.desktop.app", "src.desktop.voice"],
    "VIVO-COMPARTIDO": ["src.core.engine", "src.core.security_agent",
                        "src.models.contracts", "src.security_agent",
                        "src.validador_niveles_confianza"],
    "ALT-STREAMLIT": ["src.app", "src.multilingual.detector",
                      "src.multilingual.router", "src.multilingual.selector"],
    "ALT-LEGACY": ["src.core.stratified_reasoning", "src.dual_interface",
                   "src.nexus_root.executor", "src.nexus_root.nexus_voice",
                   "src.nexus_root.precedencia", "src.nexus_root.query_builder",
                   "src.nexus_root.router", "src.nexus_root.sanitizer",
                   "src.nexus_root.synthesizer", "src.web_interface"],
    "HUERFANO": ["src.core.agent_task_manager", "src.core.causal_synthesis",
                 "src.core.causal_templates", "src.core.episodic_memory",
                 "src.core.iterative_planner", "src.core.reasoning_engine",
                 "src.core.triage"],
}

datos = json.load(open(COV, encoding="utf-8"))["files"]

def buscar(nombre):
    for clave, valor in datos.items():
        if clave.replace("\\", ".").replace("/", ".")[:-3] == nombre:
            return valor["summary"]
    return None

total_st = total_cub = 0
for grupo, modulos in GRUPOS.items():
    st = sum(buscar(m)["num_statements"] for m in modulos)
    cub = sum(buscar(m)["covered_lines"] for m in modulos)
    total_st += st; total_cub += cub
    print(f"{grupo:18s} {st:5d} st {cub:5d} cub {100 * cub / st:6.1f}%")

vivo = sum(buscar(m)["num_statements"] for g in ("VIVO-API", "VIVO-DESKTOP", "VIVO-COMPARTIDO")
           for m in GRUPOS[g])
vivo_cub = sum(buscar(m)["covered_lines"] for g in ("VIVO-API", "VIVO-DESKTOP", "VIVO-COMPARTIDO")
               for m in GRUPOS[g])
print(f"nucleo vivo: {vivo_cub}/{vivo} = {100 * vivo_cub / vivo:.1f}%  (umbral 80% = {0.8 * vivo:.1f})")
```

**Resultado en `350a36d`:** núcleo vivo **2615/2949 = 88.7 %**; producción completa **2716/6115 = 44.42 %**.
