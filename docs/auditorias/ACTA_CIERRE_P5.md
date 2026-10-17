# Acta de Cierre P5 — Cobertura del núcleo vivo

**Plan Maestro de Auditoría Arquitectónica — Motor HPR · Cierre de Fase 1**
**Commits asociados:** `350a36d` (medición de cierre R5.1) → `55e225e` (acta de cierre, G0)
**Fecha de cierre:** 2026-10-17 · **Alcance oficial:** Escenario B — núcleo vivo (ratificado en `docs/alcance-formal-cobertura-p5-nucleo-vivo.md` §10)
**Estado:** **P5 CUMPLIDO y CERRADO por medición reproducible** sobre el alcance ratificado. La **instrumentación automática del umbral** permanece como reserva (**Decisión nº 5**, ver §7).

> Este acta **no** declara verde el indicador global. Publica las cifras reales **con su métrica explícita**: núcleo vivo **88.67 % líneas / 86.64 % oficial (ramas)**; producción completa **44.42 % / 43.29 %**; `src/` completo **59.51 % / 55.83 %**. El umbral `fail_under = 80` de `HPR/pyproject.toml:18` sigue apuntando al conjunto completo y **hoy no se cumple**.

---

## 1. Objeto y autoridad normativa

| Norma | Referencia | Cómo aplica |
|---|---|---|
| **P5** (cobertura medible) | `docs/constitution.md:58` | Se mide la cobertura real sobre `src/`; los módulos de seguridad exigen 100 % de ramas. |
| Umbral 80 % | `HPR/pyproject.toml:18` (`[tool.coverage.report] fail_under = 80`) | Compuerta **configurada**, aplicada hoy sobre **todo** `src/` y comparada contra el `percent_covered` (métrica oficial con ramas). |
| Decisión **D2** (aprobada) | Hoja de ruta de la auditoría (Pasos 1–13 / P5) | Delimitar el alcance de cobertura sobre el núcleo vivo, excluyendo huérfanos/legacy **con justificación documentada**. |
| Decisión **D3** (aprobada) | Ídem | La medición real de producción (no la global, que incluye `test_*.py`) es la **línea base oficial**. |
| **D6** (sin placeholders) | `docs/constitution.md:48` | Los módulos sin contrato vivo y sin uso son **deuda declarada**, no avance. |
| Salvaguardas **R6-1…R6-6** | `docs/alcance-formal-cobertura-p5-nucleo-vivo.md` §5.3 | Exclusión ≠ cubierto; reingreso automático; prohibido cubrir código muerto con pruebas artificiales. |

**Dos métricas, siempre etiquetadas.** *Líneas* = `covered_lines / num_statements` (cifra de la línea base y del trinquete). *Oficial (ramas)* = `(covered_lines + covered_branches) / (num_statements + num_branches)`, el `percent_covered` de `coverage.py` y la cifra que compara `fail_under`.

---

## 2. Definición del alcance cerrado

> **Núcleo vivo (P5):** toda unidad de código de `src/` **alcanzable transitivamente desde un punto de entrada vivo** (`src.main` y/o `src.desktop`), incluidas sus dependencias compartidas.

**Denominador oficial = 2 949 sentencias en 18 módulos** (Escenario B = VIVO-API + VIVO-DESKTOP + VIVO-COMPARTIDO). El catálogo exhaustivo de integrantes y de exclusiones vive en `docs/auditorias/INVENTARIO_NUCLEO_VIVO.md`.

| Grupo | Módulos | st | cub. | Cob. líneas | Cob. oficial (ramas) |
|---|---|---|---|---|---|
| VIVO-API | 9 | 2 401 | 2 156 | 89.80 % | 87.18 % |
| VIVO-DESKTOP | 4 | 199 | 110 | 55.28 % | 55.97 % |
| VIVO-COMPARTIDO | 5 | 349 | 349 | 100.00 % | 100.00 % |
| **NÚCLEO VIVO** | **18** | **2 949** | **2 615** | **88.67 %** | **86.64 %** |

**Meta del 80 % (líneas) = 2 359.2; cubiertas 2 615 → margen de +255.8 líneas (+10.84 % relativo sobre el umbral).**
Con la métrica oficial (ramas), el núcleo vivo también supera el umbral: **86.64 % ≥ 80 %**.

---

## 3. Métricas consolidadas (línea base de cierre)

| Indicador | Sent. | Cub. | Cob. líneas | Cob. oficial (ramas) |
|---|---|---|---|---|
| **Núcleo vivo (Escenario B, alcance oficial)** | 2 949 | 2 615 | **88.67 %** | **86.64 %** |
| Producción completa (`src/` sin `test_*`) | 6 115 | 2 716 | 44.42 % | 43.29 % |
| `src/` completo (incluye `test_*.py`) | 8 604 | 5 120 | 59.51 % | **55.83 % ← métrica del `fail_under`** |
| Archivos de prueba (`test_*.py`) | 2 489 | 2 404 | 96.58 % | 95.55 % |
| Escenario C (anexo: núcleo vivo + ALT-STREAMLIT) | 3 055 | 2 687 | 87.95 % | 85.92 % |

**Maquetación imposible del indicador global (registro honesto):** con el denominador completo (6 115 st) el 80 % es matemáticamente inalcanzable (techo estructural **50.4 %**), porque **3 031 sentencias son código no alcanzable** (ALT-LEGACY 1 762 + HUÉRFANO 1 262 + fachada `nexus_root/__init__` 7). Ver §6 del acta de alcance (`docs/alcance-formal-cobertura-p5-nucleo-vivo.md`).

**Residual del núcleo vivo:** 334 líneas en **10 módulos** (6 de VIVO-API + 4 de VIVO-DESKTOP): `task_orchestrator` 98 · `structural_threading` 68 · `desktop/app.py` 63 · `session_manager` 40 · `desktop/voice.py` 22 · `execution_log` 17 · `verified_reasoning` 15 · `claim_evaluator` 7 · `desktop/agent.py` 2 · `desktop/__main__.py` 2.

---

## 4. Comandos reproducibles (entorno local, P6)

Windows PowerShell, desde `HPR/`, con el intérprete del `.venv`:

```powershell
$env:PYTHONPATH="…\motor HPR\HPR;…\motor HPR\HPR\src"

# Suite oficial (configuración de pyproject.toml: --cov=src --cov-branch, fail_under=80)
& "…\.venv\Scripts\python.exe" -m pytest -q --continue-on-collection-errors
#   -> 435 passed / 0 failed / 0 xfailed ; y ABORTA (exit 1) por fail_under sobre todo src/ (55.83 %)

# Medición reproducible + JSON (para agregar el núcleo vivo)
& "…\.venv\Scripts\python.exe" -m pytest -q -o addopts="" --continue-on-collection-errors `
  --cov=src --cov-branch --cov-report=json:<tmp>\cov.json --cov-report=term --cov-fail-under=0
#   -> 435 passed ; TOTAL 8604 st, 3484 miss, 2176 branch, 119 brpart
```

**Agregación del núcleo vivo (script reproducible incluido en el Anexo A del acta de cierre `docs/cierre-p5-cobertura-nucleo-vivo.md`).**
**Resultado verificado en `350a36d` y reproducido en G0 (2026-10-17):** núcleo vivo **2 615/2 949 = 88.67 %** (líneas) / **86.64 %** (oficial).

---

## 5. Commits asociados (recorrido del bloque R + cierre)

| Compuerta | Commit | Artefacto | Objetivo |
|---|---|---|---|
| R1 · seguridad/triaje | `d2031a7` | `src/test_cov_r1_seguridad.py` (43) | `security_agent`, `core/engine`, `main.py` (triggers), `validador_niveles_confianza` |
| R1-FIX | `457c2d8` | `src/core/engine.py` (1 línea) | `NivelRiesgo.CRITICO`; retirado el `xfail` |
| R2 · ruteo | `ed2c72f` | `src/test_cov_r2_ruteo.py` (28) | `main.py` · ruteo conversacional/técnico, DAG |
| R3 · resiliencia | `b455fba` | `src/test_cov_r3_resiliencia.py` (43) | `RetryConfig`, `with_retry`, `LocalFallback`, trigger, telemetría (0 sleeps reales) |
| R4 · multilingüe | `d627392` | `src/test_cov_r4_multilingue.py` (23) | `multilingual/{detector,router,selector}` |
| R4-FIX | `94fd4bd` | `src/multilingual/router.py` (2 líneas) | `NameError` → `detector.JUSTIFICATIONS` |
| R6 · alcance formal | `fcc109c` | `docs/alcance-formal-cobertura-p5-nucleo-vivo.md` | Denominador oficial + salvaguardas + H1–H4 |
| R5.1 · núcleo de síntesis | `350a36d` | `src/test_cov_r5_1_deep_synthesizer.py` (53) | `core/deep_synthesizer.py` → 0 líneas sin cubrir |
| **G0 · congelar línea base** | `55e225e` | `docs/cierre-p5-cobertura-nucleo-vivo.md` | Acta de cierre P5 (medición + reserva) |

**Total de pruebas añadidas en el bloque R: 190** (43+28+43+23+53). **Ningún** módulo de `src/` fue modificado salvo las dos correcciones atómicas declaradas (R1-FIX, R4-FIX), cada una con prueba rojo→verde, retirando su marcador `xfail` en la compuerta de corrección.

---

## 6. Evidencia de la suite

| Hecho | Evidencia |
|---|---|
| HEAD tras el cierre | `55e225e` |
| Suite completa | **435 passed / 0 failed / 0 xfailed / 0 skipped / 0 errors** (370 warnings) |
| Pruebas recolectadas | 435 (`435 tests collected`) |
| Determinismo | 3 ejecuciones ⇒ conteos y cobertura idénticos (sólo varía el tiempo de pared, 6–9 s) |
| `src/` modificado durante el cierre | **ninguno** |
| Nada pusheado | sí (`main` 28 commits por delante de `origin/main`) |

---

## 7. Reserva — Decisión nº 5: instrumentación del umbral

El umbral automático sigue configurado sobre el conjunto completo (`fail_under = 80`, `HPR/pyproject.toml:18`), cuyo denominador incluye las 3 031 sentencias excluidas por no alcanzabilidad. Por eso hoy:

- cualquier ejecución sin `--cov-fail-under=0` **aborta legítimamente** (métrica oficial con ramas = 55.83 %; líneas = 59.51 %);
- la verificación automática del criterio **no está instrumentada** para el alcance ratificado.

| Opción | Contenido | Coste |
|---|---|---|
| **O5-a** | Invocación de verificación acotada al núcleo vivo (fuentes explícitas) con `--cov-fail-under=80`, **manteniendo** la publicación del indicador global completo. | Bajo: comando documentado. |
| **O5-b** | Trinquete anti-regresión: fijar el suelo del núcleo vivo al valor medido (**88.67 % líneas**) y exigir que sólo pueda subir; el total global se sigue publicando como diagnóstico. | Bajo: una constante documentada. |
| **O5-c** | Diferir la instrumentación automática a la fase de CI y cerrar P5 por medición (como en este acta). | Nulo ahora; deja el criterio sin guardia automática. |

**Recomendación del auditor: O5-a + O5-b** (verificación acotada + trinquete), porque cumple el criterio sin reblandecerlo y conserva la trazabilidad del indicador global. **No ejecutada. Pendiente de autorización.**

---

## 8. Estado del repositorio y transparencia

| Hecho | Evidencia |
|---|---|
| HEAD | `55e225e` |
| Cambios pendientes en `src/` | **ninguno** |
| No incorporado al cierre (ajeno) | `HPR/boveda y vitacoras/Hoja_de_ruta_HPR.pdf` — archivo del usuario, fuera de alcance |
| Bóveda | intacta al ejecutar **la suite R5.1 aislada** (`BOVEDA_INTACTA: True`). La **suite completa** sí añade entradas al log local git-ignored `boveda y vitacoras/logs/execution_<fecha>.jsonl` (comportamiento preexistente del endpoint de trigger: `execution_log.py:19-40`; tests `src/test_etapa_d.py:92-132`). |
| Nada pusheado | sí |

---

## 9. Relación con el acta antecedente (transparencia)

`docs/cierre-p5-cobertura-nucleo-vivo.md` (**commit `55e225e`**) **NO** queda absorbida ni reubicada: permanece en `docs/` como **acta antecedente/origen** de la medición de cierre y como anexo técnico (incluye el script de agregación del núcleo vivo). La **estructura normativa** de la Fase 1 es la de `docs/auditorias/`:

- `docs/auditorias/ACTA_CIERRE_P5.md` (este documento) — formaliza la decisión de cierre.
- `docs/auditorias/INVENTARIO_NUCLEO_VIVO.md` — delimitación formal del Escenario B y catálogo de exclusiones.
- `docs/auditorias/DEUDA_TECNICA_FASE1.md` — registro formal de hallazgos H1–H5b.

Si la Coordinación prefiere **reubicar** el acta antecedente dentro de `docs/auditorias/`, se hará con `git mv` en una compuerta documental autorizada (sin pérdida de historia).

---

## 10. Firma

| Rol | Nombre | Estado |
|---|---|---|
| Coordinación / responsable del proyecto | Coordinación HPR | **CERRADO** — P5 cumplido por medición (2026-10-17); Decisión nº 5 pendiente |
| Reviewer (auditoría independiente) | Reviewer HPR | Recorrido R1–R5.1 verificado; H1–H5b registrados; 2 ramas residuales declaradas |
