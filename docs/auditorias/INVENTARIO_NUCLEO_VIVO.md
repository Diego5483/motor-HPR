# Inventario del núcleo vivo (Escenario B) y exclusiones justificadas

**Plan Maestro de Auditoría Arquitectónica — Motor HPR · Cierre de Fase 1**
**Commit base de la medición:** `350a36d` · **Acta de cierre:** `docs/auditorias/ACTA_CIERRE_P5.md` (commit `55e225e`)
**Alcance oficial ratificado:** Escenario B — núcleo vivo (**2 949 sentencias**, 18 módulos)
**Naturaleza:** delimitación formal del alcance de cobertura P5 y **catálogo exhaustivo** de lo excluido por no alcanzabilidad. No es enmienda constitucional.

> Regla de honestidad (R6-1/R6-2): excluir del *denominador* un módulo **no** es declararlo cubierto, no autoriza a borrar sus pruebas y no infla el indicador. La exclusión se funda **exclusivamente** en la no alcanzabilidad demostrable desde los puntos de entrada vivos.

---

## 1. Puntos de entrada vivos (evidencia)

| Entrada | Invocación real | Archivo:línea |
|---|---|---|
| **API backend** `src.main` | `python run.py` → `uvicorn.run("src.main:app", …)` | `HPR/run.py:17` |
| **App de escritorio** `src.desktop` (**lanzador oficial**) | `ejecutar.bat` → `python -m src.desktop` | `HPR/ejecutar.bat:35-37` |
| App de escritorio (vía alternativa) | `start_hpr.bat` → `launch_hpr.py` → `runpy.run_module("src.desktop")` | `HPR/start_hpr.bat:4`, `HPR/launch_hpr.py:24` |
| App de escritorio (vía alternativa) | `start_hpr.py` → `from src.desktop.app import main` | `HPR/start_hpr.py:27-28` |
| **Frontend web vivo** `src/web_ui/` | Servido por la API en `/ui` (StaticFiles) | `HPR/src/main.py:1615-1617` |

**Sin lanzador (no vivos):** `src/app.py` (Streamlit; requiere `streamlit run`, ausente de todo lanzador), `src/web_interface.py` y `src/dual_interface.py` (sin importador). Confirmado por la bóveda documental: `HPR/boveda y vitacoras/PROMPT_OPENCODE_IMPLEMENTACION_INTERFAZ_DUAL_HPR.md:42`.

---

## 2. Método del inventario (reproducible)

1. Grafo de imports construido con **AST** sobre las 45 unidades de producción de `src/` (**sin importar** los módulos: sin efectos, sin red, sin reloj).
2. Resolución de imports relativos y de estilo mixto (`from .core.engine import …`, `from src.x import …`, `from core.x import …`).
3. Cierre transitivo desde cada punto de entrada vivo.
4. Análisis de aristas dinámicas: la **única** del árbol es `HPR/src/desktop/voice.py:33` (`__import__` de backends de terceros), por lo que el grafo estático cubre todo el código de `src/`.
5. Cifras de cobertura tomadas de la **medición real** (`covered_lines` / `num_statements` / ramas), no de porcentajes derivados.

**Invocación de la medición:**
```powershell
$env:PYTHONPATH="…\motor HPR\HPR;…\motor HPR\HPR\src"
& "…\.venv\Scripts\python.exe" -m pytest -q -o addopts="" --continue-on-collection-errors `
  --cov=src --cov-branch --cov-report=json:<tmp>\cov.json --cov-report=term --cov-fail-under=0
```
**Resultado en `350a36d`:** `435 passed`; producción 2 716/6 115 = 44.42 %. Script del diagnóstico (AST) en el Anexo A de `docs/alcance-formal-cobertura-p5-nucleo-vivo.md`.

---

## 3. Catálogo de integrantes del núcleo vivo (Escenario B — 18 módulos, 2 949 st)

| Módulo | st | cub. | Cob. líneas | Cob. oficial (ramas) | Importador de producción que lo sostiene |
|---|---|---|---|---|---|
| `src.main` | 495 | 495 | 100.00 % | 99.3 % | raíz API (`run.py:17`) |
| `src.core.deep_synthesizer` | 480 | 480 | 100.00 % | 99.7 % | `src.main`, `src.core.verified_reasoning` |
| `src.core.task_orchestrator` | 478 | 380 | 79.50 % | 74.6 % | `src.main` (`orchestrate_endpoint`) |
| `src.core.structural_threading` | 279 | 211 | 75.63 % | 69.8 % | `src.core.deep_synthesizer` |
| `src.core.session_manager` | 229 | 189 | 82.53 % | 77.6 % | `src.main` |
| `src.core.verified_reasoning` | 156 | 141 | 90.38 % | 84.4 % | `src.core.task_orchestrator` |
| `src.core.claim_evaluator` | 117 | 110 | 94.02 % | 92.0 % | `src.core.verified_reasoning` |
| `src.execution_log` | 108 | 91 | 84.26 % | 80.6 % | `src.main` (endpoints `/api/v1/logs*`) |
| `src.schemas` | 59 | 59 | 100.00 % | 100 % | `src.main` |
| `src.desktop.app` | 89 | 26 | 29.21 % | 26.7 % | `src.desktop.__main__` |
| `src.desktop.agent` | 57 | 55 | 96.49 % | 96.2 % | `src.desktop.app` |
| `src.desktop.voice` | 51 | 29 | 56.86 % | 54.1 % | `src.desktop.app` |
| `src.desktop.__main__` | 2 | 0 | 0.00 % | 0 % | `ejecutar.bat:37` (`python -m src.desktop`) |
| `src.models.contracts` | 163 | 163 | 100.00 % | 100 % | `src.main`, `src.desktop.agent`, … |
| `src.security_agent` | 100 | 100 | 100.00 % | 100 % | `src.main`, `src.desktop.agent`, `src.desktop.app` |
| `src.core.engine` | 63 | 63 | 100.00 % | 100 % | `src.main:36`, `src.desktop.agent:28` |
| `src.core.security_agent` | 14 | 14 | 100.00 % | 100 % | `src.core.engine` |
| `src.validador_niveles_confianza` | 9 | 9 | 100.00 % | 100 % | `src.desktop.agent:36`, `src.security_agent` |
| **TOTAL núcleo vivo** | **2 949** | **2 615** | **88.67 %** | **86.64 %** | 18 módulos |

---

## 4. Exclusiones justificadas por no alcanzabilidad

### 4.1 `HUÉRFANO` — 1 284 sentencias en 7 módulos (22 cubiertas, 1.71 %)

| Módulo | st | cub. | Cob. | Importadores de producción | Nota |
|---|---|---|---|---|---|
| `src.core.reasoning_engine` | 350 | 0 | 0 % | **ninguno** | `MotorRazonamientoSuperior` (`:89`) y `crear_motor_razonamiento` (`:744`) sin llamadores → **H1/H2** |
| `src.core.episodic_memory` | 253 | 0 | 0 % | `causal_synthesis`, `iterative_planner` (ambos huérfanos) | |
| `src.core.causal_synthesis` | 231 | 0 | 0 % | **ninguno** | |
| `src.core.iterative_planner` | 179 | 0 | 0 % | **ninguno** | |
| `src.core.causal_templates` | 155 | 0 | 0 % | `causal_synthesis` (huérfano) | |
| `src.core.agent_task_manager` | 94 | 0 | 0 % | **ninguno** | |
| `src.core.triage` | 22 | 22 | 100 % | **ninguno** (sólo `src/test_triage.py:9`) | implementación canónica **muerta**; la ruta viva usa el duplicado → **H3** |
| **TOTAL HUÉRFANO** | **1 284** | **22** | **1.71 %** | — | exclusión por no alcanzabilidad |

### 4.2 `ALT-LEGACY` — 1 762 sentencias en 10 módulos (0 %), + 7 st de la fachada `nexus_root/__init__`

| Módulo | st | cub. | Importadores | Motivo de exclusión |
|---|---|---|---|---|
| `src.dual_interface` | 524 | 0 | **ninguno** | UI Streamlit legacy reemplazada por `src/web_ui/` |
| `src.nexus_root.executor` | 341 | 0 | `nexus_root` (paquete inalcanzable), `iterative_planner` (huérfano) | consola externa legacy |
| `src.nexus_root.router` | 249 | 0 | ídem | ídem |
| `src.nexus_root.query_builder` | 184 | 0 | **ninguno** | ídem |
| `src.nexus_root.synthesizer` | 115 | 0 | ídem | ídem |
| `src.nexus_root.precedencia` | 109 | 0 | ídem | ídem |
| `src.nexus_root.nexus_voice` | 79 | 0 | ídem | TTS de consola legacy |
| `src.core.stratified_reasoning` | 75 | 0 | `src.nexus_root.executor:25` (inalcanzable) | sólo invocable desde la consola legacy |
| `src.web_interface` | 63 | 0 | **ninguno** | UI legacy |
| `src.nexus_root.sanitizer` | 23 | 0 | ídem | ídem |
| `src.nexus_root.__init__` (fachada) | 7 | 0 | ídem | fachada del paquete inalcanzable |
| **TOTAL ALT-LEGACY** | **1 769** | **0** | — | exclusión por no alcanzabilidad |

### 4.3 Fachadas `__init__` restantes (no clasificadas en ningún grupo)

| Módulo | st | cub. | Nota |
|---|---|---|---|
| `src.__init__` | 1 | 1 | fachada del paquete raíz (cubierta) |
| `src.models.__init__` | 2 | 2 | fachada (cubierta) |
| `src.multilingual.__init__` | 4 | 4 | fachada (cubierta) |
| `src.core.__init__` | 0 | 0 | vacía |
| `src.desktop.__init__` | 0 | 0 | vacía |
| **Subtotal fachadas** | **14** | **7** | 7 cubiertas (no alteran el denominador del núcleo vivo) |

### 4.4 Anexo (Escenario C, **no** es el alcance oficial) — `ALT-STREAMLIT` 106 st

| Módulo | st | cub. | Situación |
|---|---|---|---|
| `src.app` | 34 | 0 | entrada Streamlit **sin lanzador** (no viva hoy) |
| `src.multilingual.detector` | 21 | 21 | capa multilingüe (R4), consumida sólo por `src.app` |
| `src.multilingual.router` | 28 | 28 | ídem (corregida en R4-FIX) |
| `src.multilingual.selector` | 23 | 23 | ídem |

→ Escenario C = **3 055 st, 2 687 cubiertas = 87.95 %** (líneas) / 85.92 % (oficial). Se mantiene como anexo: si se añade un lanzador Streamlit, **reingresa automáticamente** al denominador (regla R6-3).

---

## 5. Aritmética de cierre (verificación cruzada)

| Comprobación | Valor |
|---|---|
| Producción total (`src/` sin `test_*`) | 6 115 st |
| = núcleo vivo 2 949 + Escenario C 106 + ALT-LEGACY 1 762 + HUÉRFANO 1 284 + fachadas no clasificadas 14 | 6 115 ✓ |
| Cubiertas de producción | 2 716 = núcleo vivo 2 615 + C 72 + huérfano 22 + fachadas cubiertas 7 ✓ |
| Sentencias excluidas por no alcanzabilidad | **3 031** = ALT-LEGACY 1 762 + HUÉRFANO 1 262 + fachada `nexus_root/__init__` 7 |
| Techo del denominador completo | 3 084/6 115 = **50.4 %** → el 80 % global es matemáticamente inalcanzable (ver R6 §6) |
| Verificación de las 45 unidades | grupos + 6 fachadas = 6 115 exactas, coincidiendo con `--cov=src` |

---

## 6. Salvaguardas vinculantes (R6-1…R6-6, vigentes)

- **R6-1 · La exclusión es por alcanzabilidad, no por conveniencia.** Un módulo sale del denominador sólo si ningún punto de entrada vivo lo alcanza, con evidencia registrada aquí.
- **R6-2 · Excluido ≠ cubierto.** Los módulos excluidos **no** cuentan como líneas cubiertas en ningún reporte derivado de este alcance.
- **R6-3 · Reingreso automático.** Si un módulo excluido pasa a ser alcanzable (nuevo import, lanzador o endpoint), **reingresa al denominador de P5 en la misma compuerta** que lo conecta.
- **R6-4 · Prohibido cubrir código muerto con pruebas artificiales.** No se escribirán tests cuyo único fin sea elevar el indicador sobre módulos inalcanzables (P2/P3, «prohibido falso verde»).
- **R6-5 · Deuda declarada (D6).** Los módulos excluidos permanecen en el repositorio como **deuda declarada** hasta que una compuerta específica decida y ejecute su retiro/archivo o su reconexión. Este inventario **no autoriza** borrar ni reescribir nada.
- **R6-6 · Re-verificación.** El diagnóstico de alcanzabilidad (§2) se repite en cada cierre de bloque; si el grafo cambia, este documento se actualiza.
