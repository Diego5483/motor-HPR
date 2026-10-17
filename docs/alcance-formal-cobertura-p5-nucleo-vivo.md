# Alcance formal de la cobertura P5 (núcleo vivo) y registro de hallazgos R5

**Plan Maestro de Auditoría Arquitectónica — Motor HPR · Bloque R (compuerta P5.6 / R6)**
**Commit base del diagnóstico:** `94fd4bd` · **HEAD:** `94fd4bd` · **Fecha:** 2026-10-17
**Naturaleza:** delimitación de alcance para el criterio P5 (deriva de la decisión **D2** ya aprobada) + registro de hallazgos. **No** es enmienda constitucional (§7 de la Constitución).
**Estado: RATIFICADA — el alcance oficial de P5 es el Escenario B (núcleo vivo).** Ratificada por la Coordinación del proyecto el **2026-10-17** (registro en §10).

> Este documento **no afirma éxito**. Declara qué parte de `src/` es alcanzable por los puntos de entrada vivos, qué parte no lo es, y con qué evidencia. La cobertura del núcleo vivo está hoy en **79.0 %**, por debajo del umbral configurado.

---

## 1. Objeto y autoridad normativa

| Norma | Referencia | Cómo aplica aquí |
|---|---|---|
| **P5** (cobertura medible) | `docs/constitution.md:58` | "Se mide la cobertura sobre `src/`; los módulos de seguridad exigen cobertura completa de ramas." Define **qué** se mide, no un umbral numérico. |
| Umbral 80 % | `HPR/pyproject.toml:18` (`[tool.coverage.report] fail_under = 80`) | El 80 % es la compuerta **configurada** y aplicada por `--cov=src` sobre el conjunto completo. |
| **D6** (sin placeholders) | `docs/constitution.md:48` | Los módulos sin contrato vivo y sin uso son **deuda declarada**, no avance. |
| Decisión **D2** (aprobada) | Hoja de ruta de la auditoría (Pasos 1–13 / P5) | Delimitar el alcance formal de cobertura sobre el **núcleo vivo**, excluyendo módulos huérfanos/legacy **con justificación documentada** — este documento. |
| Decisión **D3** (aprobada) | Ídem | La medición real de producción (no la global, que incluye `test_*.py`) es la **línea base oficial**. |
| **P2/P3/P7** | `docs/constitution.md:55-60` | Prohíben tests con `print`/`sleep`, no deterministas, o que muten la bóveda. Refuerza que **no** se cubrirá código muerto con pruebas artificiales. |

**Regla de honestidad que este acta hace explícita:** excluir del *denominador* un módulo **no** es declararlo cubierto, ni autoriza a borrar sus tests, ni infla el indicador. La exclusión se funda exclusivamente en la **no alcanzabilidad demostrable** desde los puntos de entrada vivos.

---

## 2. Puntos de entrada vivos (evidencia)

| Entrada | Invocación real | Archivo:línea |
|---|---|---|
| **API backend** `src.main` | `python run.py` → `uvicorn.run("src.main:app", …)` | `HPR/run.py:17` |
| **App de escritorio** `src.desktop` (**lanzador oficial**) | `ejecutar.bat` → `python -m src.desktop` | `HPR/ejecutar.bat:35-37` |
| **App de escritorio** (vía alternativa) | `start_hpr.bat` → `launch_hpr.py` → `runpy.run_module("src.desktop")` | `HPR/start_hpr.bat:4`, `HPR/launch_hpr.py:24` |
| **App de escritorio** (vía alternativa) | `start_hpr.py` → `from src.desktop.app import main` | `HPR/start_hpr.py:27-28` |
| **Frontend web vivo** `src/web_ui/` | Servido por la API en `/ui` (StaticFiles) | `HPR/src/main.py:1615-1617` |

**Sin lanzador (no vivos):** `src/app.py` (Streamlit) requiere `streamlit run`, que **no aparece en ningún lanzador del repositorio**; `src/web_interface.py` y `src/dual_interface.py` no tienen importador alguno. La bóveda documental lo confirma: `HPR/boveda y vitacoras/PROMPT_OPENCODE_IMPLEMENTACION_INTERFAZ_DUAL_HPR.md:42` advierte que `web_interface.py`, `app.py`, `detector.py`, `selector.py` y `router.py` son *"pistas de búsqueda, no una orden de asumir que todos esos archivos siguen siendo el punto de entrada actual"*.

---

## 3. Método del diagnóstico (reproducible)

1. Grafo de imports construido con **AST** sobre las 45 unidades de producción de `src/` (**sin importar** los módulos: sin efectos, sin red, sin reloj).
2. Resolución de imports relativos y de estilo mixto (`from .core.engine import …`, `from src.x import …`, `from core.x import …`).
3. Cierre transitivo desde cada punto de entrada vivo.
4. Análisis de aristas dinámicas: la **única** del árbol es `HPR/src/desktop/voice.py:33` (`__import__` de backends de terceros: `pyttsx3`, `speech_recognition`, `pocketsphinx`), por lo que el grafo estático cubre todo el código de `src/`.
5. Cifras de cobertura tomadas de la medición real (`covered_lines` / `num_statements`), no de porcentajes derivados. Script íntegro en el **Anexo A**.

**Invocación de la medición (P6, mismo entorno que producción local):**

```powershell
$env:PYTHONPATH="…\motor HPR\HPR;…\motor HPR\HPR\src"
& "…\.venv\Scripts\python.exe" -m pytest -q -o addopts="" --continue-on-collection-errors `
  --cov=src --cov-branch --cov-report=json:<tmp>\cov.json --cov-fail-under=0
```

**Resultado en `94fd4bd`:** `382 passed / 0 failed / 0 xfailed`; producción **2432/6115 = 39.77 %**.

---

## 4. Alcance propuesto: el núcleo vivo

### 4.1 Definición

> **Núcleo vivo (P5):** toda unidad de código de `src/` **alcanzable transitivamente desde un punto de entrada vivo** (`src.main` y/o `src.desktop`), incluidas sus dependencias compartidas.

**Alcance propuesto (Escenario B) = 2949 sentencias, 2331 cubiertas = 79.0 %.**

| Grupo | Módulos | Sent. | Cub. | Faltan | Cob. |
|---|---|---|---|---|---|
| VIVO-API | 9 | 2401 | 1872 | 529 | 78.0 % |
| VIVO-DESKTOP | 4 | 199 | 110 | 89 | 55.3 % |
| VIVO-COMPARTIDO | 5 | 349 | 349 | 0 | 100 % |
| **TOTAL núcleo vivo** | **18** | **2949** | **2331** | **618** | **79.0 %** |

### 4.2 Integrantes y por qué (evidencia de importadores de producción)

| Módulo | Sent. | Cob. | Importador de producción que lo sostiene |
|---|---|---|---|
| `src.main` | 495 | 99.3 % | raíz API (`run.py:17`) |
| `src.core.deep_synthesizer` | 480 | 40.3 % | `src.main`, `src.core.verified_reasoning` |
| `src.core.task_orchestrator` | 478 | 74.6 % | `src.main` (`orchestrate_endpoint`) |
| `src.core.structural_threading` | 279 | 59.0 % | `src.core.deep_synthesizer` |
| `src.core.session_manager` | 229 | 77.6 % | `src.main` |
| `src.core.verified_reasoning` | 156 | 84.4 % | `src.core.task_orchestrator` |
| `src.core.claim_evaluator` | 117 | 92.0 % | `src.core.verified_reasoning` |
| `src.execution_log` | 108 | 80.6 % | `src.main` (endpoints `/api/v1/logs*`) |
| `src.schemas` | 59 | 100 % | `src.main` |
| `src.desktop.app` | 89 | 26.7 % | `src.desktop.__main__` |
| `src.desktop.agent` | 57 | 96.2 % | `src.desktop.app` |
| `src.desktop.voice` | 51 | 54.1 % | `src.desktop.app` |
| `src.desktop.__main__` | 2 | 0 % | `ejecutar.bat:37` (`python -m src.desktop`) |
| `src.models.contracts` | 163 | 100 % | `src.main`, `src.desktop.agent`, … |
| `src.security_agent` | 100 | 100 % | `src.main`, `src.desktop.agent`, `src.desktop.app` |
| `src.core.engine` | 63 | 100 % | `src.main:36`, `src.desktop.agent:28` |
| `src.core.security_agent` | 14 | 100 % | `src.core.engine` |
| `src.validador_niveles_confianza` | 9 | 100 % | `src.desktop.agent:36`, `src.security_agent` |

### 4.3 Anexo opcional (Escenario C) = núcleo vivo + `ALT-STREAMLIT`

| Módulo | Sent. | Cob. | Situación |
|---|---|---|---|
| `src.app` | 34 | 0 % | entrada Streamlit **sin lanzador** (no viva hoy) |
| `src.multilingual.detector` | 21 | 100 % | capa multilingüe (R4), consumida sólo por `src.app` |
| `src.multilingual.router` | 28 | 100 % | ídem (corregida en R4-FIX) |
| `src.multilingual.selector` | 23 | 100 % | ídem |

→ Escenario C = **3055 sent., 2403 cub. = 78.7 %** (faltan ≈41 líneas).

*Recomendación:* el **alcance oficial** es el **Escenario B**. El Escenario C se documenta como anexo porque `src.app` no es alcanzable desde ningún lanzador; si en el futuro se añade un lanzador Streamlit, **reingresa automáticamente** al alcance (regla R6-3).

---

## 5. Exclusión del denominador (justificada por no alcanzabilidad)

### 5.1 `ALT-LEGACY` — 1762 sentencias en 10 módulos (0 %), + 7 st de la fachada `nexus_root/__init__`

| Módulo | Sent. | Importadores | Motivo de exclusión |
|---|---|---|---|
| `src.dual_interface` | 524 | **ninguno** | UI Streamlit legacy reemplazada por `src/web_ui/` |
| `src.nexus_root.executor` | 341 | `nexus_root` (paquete inalcanzable), `iterative_planner` (huérfano) | consola externa legacy |
| `src.nexus_root.router` | 249 | ídem | ídem |
| `src.nexus_root.query_builder` | 184 | **ninguno** | ídem |
| `src.nexus_root.synthesizer` | 115 | ídem | ídem |
| `src.nexus_root.precedencia` | 109 | ídem | ídem |
| `src.nexus_root.nexus_voice` | 79 | ídem | TTS de consola legacy |
| `src.core.stratified_reasoning` | 75 | `src.nexus_root.executor:25` (inalcanzable) | sólo invocable desde la consola legacy |
| `src.web_interface` | 63 | **ninguno** | UI legacy |
| `src.nexus_root.sanitizer` | 23 | ídem | ídem |
| `src.nexus_root.__init__` | 7 | ídem | fachada del paquete inalcanzable |

### 5.2 `HUÉRFANO` — 1284 sentencias en 7 módulos (22 cub., 1.7 %), + 7 st de fachadas `__init__`

| Módulo | Sent. | Importadores de producción | Nota |
|---|---|---|---|
| `src.core.reasoning_engine` | 350 | **ninguno** | `MotorRazonamientoSuperior` (`:89`) y `crear_motor_razonamiento` (`:744`) sin llamadores → ver **H1/H2** |
| `src.core.episodic_memory` | 253 | `causal_synthesis`, `iterative_planner` (ambos huérfanos) | |
| `src.core.causal_synthesis` | 231 | **ninguno** | |
| `src.core.iterative_planner` | 179 | **ninguno** | |
| `src.core.causal_templates` | 155 | `causal_synthesis` (huérfano) | |
| `src.core.agent_task_manager` | 94 | **ninguno** | |
| `src.core.triage` | 22 | **ninguno** (sólo `src/test_triage.py:9`) | ver **H3** |
| paquetes `__init__` (`src`, `src.core`, `src.models`, `src.multilingual`) | 7 | — | fachadas |

### 5.3 Salvaguardas anti-maquillaje (vinculantes para futuras compuertas)

- **R6-1 · La exclusión es por alcanzabilidad, no por conveniencia.** Un módulo sale del denominador únicamente si ningún punto de entrada vivo lo alcanza, y la evidencia se registra aquí.
- **R6-2 · Excluido ≠ cubierto.** Los módulos excluidos **no** cuentan como líneas cubiertas en ningún reporte derivado de este alcance.
- **R6-3 · Reingreso automático.** Si un módulo excluido pasa a ser alcanzable (nuevo import, lanzador o endpoint), **reingresa al denominador de P5 en la misma compuerta** que lo conecta.
- **R6-4 · Prohibido cubrir código muerto con pruebas artificiales.** No se escribirán tests cuyo único fin sea elevar el indicador sobre módulos inalcanzables (P2/P3 y "prohibido falso verde").
- **R6-5 · Deuda declarada (D6).** Los módulos excluidos permanecen en el repositorio como **deuda declarada** hasta que una compuerta específica decida y ejecute su retiro/archivo o su reconexión. Este acta **no autoriza** borrar ni reescribir nada.
- **R6-6 · Re-verificación.** El diagnóstico de alcanzabilidad (§3) se repite en cada cierre de bloque; si el grafo cambia, este documento se actualiza.

---

## 6. Aritmética de la meta P5 (≥ 80 %)

| Escenario | Denominador | Cubierto | Cob. | Meta 80 % | Faltan |
|---|---|---|---|---|---|
| **A · base completa vigente** (toda `src/` sin `test_*`) | 6115 | 2432 | **39.77 %** | 4892 | **+2460** |
| **B · núcleo vivo** (propuesto) | 2949 | 2331 | **79.0 %** | 2359 | **+28.2** |
| C · núcleo vivo + ALT-STREAMLIT | 3055 | 2403 | 78.7 % | 2444 | +41 |
| D · + ALT-LEGACY | 4817 | 2403 | 49.9 % | 3854 | +1451 |
| E · absoluto sin huérfanos (techo real de A) | — | **3084/6115 = 50.4 %** | — | — | **inalcanzable** |

**Conclusión dura:** con el denominador vigente (A), el 80 % es **matemáticamente imposible** (techo 50.4 %), porque 3031 sentencias son código no alcanzable cuya única "cobertura" posible sería artificial (prohibida). Con el alcance del núcleo vivo (B) faltan **≈28 líneas**, y **una sola unidad** — `core/deep_synthesizer.py` (260 líneas faltantes) — llevaría el núcleo vivo a **≈87.9 %**.

---

## 7. Hallazgos registrados (evidencia en `archivo:línea`; ninguno corregido en esta compuerta)

### H1 · El "núcleo de razonamiento" está desconectado del motor vivo
`MotorRazonamientoSuperior` —es decir `src/core/reasoning_engine.py:89`— y su factoría `crear_motor_razonamiento` (`:744-746`) **no tienen llamadores**. Junto con `iterative_planner.py:193,326`, `episodic_memory.py:451-462`, `causal_synthesis.py:20-25` y `causal_templates.py`, suman **1337 sentencias alcanzables sólo desde sí mismas**. `stratified_reasoning.py` sólo se invoca desde la consola legacy (`nexus_root/executor.py:25`).

### H2 · Honestidad de los handlers de trigger (discrepancia demostrable)
Ejercitados al 100 % de líneas (`src/main.py` tiene **0 líneas sin cubrir**), pero los tres devuelven **afirmaciones de trabajo no realizado**:

| Handler | Líneas | Devuelve | Trabajo real |
|---|---|---|---|
| `N1_BUSQUEDA` | `src/main.py:1168-1179` | `"resultados": []` + *"Búsqueda cognitiva **ejecutada** sobre el último turno."* | ninguno |
| `N2_GRAFO` | `src/main.py:1181-1189` | `"conflictos": []` + *"Grafo de consistencia **verificado**: no se detectaron conflictos."* | ninguno |
| `MOTOR_RAZON` | `src/main.py:1191-1200` | `"sintesis": f"Síntesis de sesión {id} con {N} turnos."` | ninguno (cadena literal) |

**Prueba objetiva:** durante toda la suite —que sí ejecuta esos handlers— `src/core/reasoning_engine.py`, `iterative_planner.py`, `episodic_memory.py` y `causal_synthesis.py` permanecen al **0 %** de ejecución. El sistema anuncia "MotorRazonamientoSuperior (síntesis)" como trigger (`src/schemas.py:36`; textos en `src/main.py:590,636,641`) sin ejecutar síntesis alguna.

**Contraste que fija el estándar:** `WEB_SEARCH` (`src/main.py:1150-1166`) **sí** es honesto desde la Fase 1 — devuelve `estado="no_disponible"` y declara textualmente que el motor no genera resultados simulados. El proyecto ya tiene el criterio; estos tres handlers no lo cumplen.

### H3 · Duplicado muerto en el triaje
`src/core/triage.py:19` (la implementación que R1 identificó como **canónica y correcta**) sólo es importada por `src/test_triage.py:9`. La ruta viva usa el duplicado `src/core/engine.py:178` desde `src/desktop/agent.py:33,112`. La deuda de "duplicación divergente" se agrava: la versión correcta es **código muerto** y la que ejecuta el producto es la otra.

### H4 · Colisión de nombres `nexus_root`
`nexus_root_validation` —validación de identidad **viva**— vive en `src/core/engine.py` y se usa en `src/main.py:1380`. El paquete `src/nexus_root/` (1769 sentencias legacy, inalcanzable) usa el **mismo nombre** en su documentación (`src/nexus_root/__init__.py:1-2`). Riesgo de confusión en auditorías futuras.

---

## 8. Estado del repositorio al emitir este acta

| Hecho | Evidencia |
|---|---|
| HEAD | `94fd4bd` (`fix(multilingual): corregir NameError usando detector.JUSTIFICATIONS en router (R4-fix)`) |
| Cambios pendientes en `src/` | **ninguno** |
| Bóveda | intacta (`BOVEDA_INTACTA: True`) |
| Suite | `382 passed / 0 failed / 0 xfailed` |
| Cobertura de producción | 2432/6115 = **39.77 %** (línea base oficial, D3) |

---

## 9. Decisiones pendientes (no ejecutadas por este acta)

1. ~~**Ratificar el alcance oficial** (Escenario B, o B+C si se declara viva la entrada Streamlit).~~ → **RESUELTA: ratificado el Escenario B (núcleo vivo) el 2026-10-17 — ver §10.**
2. **Compuertas de cobertura** sobre el núcleo vivo: R5.1 `deep_synthesizer` (260), R5.2 `task_orchestrator` (98) + `structural_threading` (92), R5.3 `desktop/*` (87) + `session_manager` (40) + `execution_log` (17) + `verified_reasoning` (15) + `claim_evaluator` (7).
3. **Compuerta de corrección H2** (honestidad de `N1_BUSQUEDA`, `N2_GRAFO`, `MOTOR_RAZON`) con prueba rojo→verde; toca `src/main.py`.
4. **Compuerta estructural H1/H3/H4**: decidir retiro/archivo del código muerto o su reconexión real; toca `src/` y requiere plan propio (D6).
5. **Ajuste del umbral/medición**: si se ratifica un alcance reducido, definir cómo se invoca `fail_under` (p. ej. medición acotada al núcleo vivo) sin falsear el indicador global, que debe seguir publicándose.

---

## 10. Registro de ratificación

| Fecha | Decisión | Detalle | Evidencia |
|---|---|---|---|
| 2026-10-17 | **Ratificado el Escenario B** como alcance oficial de P5 | núcleo vivo = 18 módulos, **2949 sentencias**; el Escenario C (Streamlit, 3055 st) queda como **anexo**, no como alcance | Aprobación de la Coordinación del proyecto en la compuerta **P5.6/R6** |
| 2026-10-17 | Autorizada la compuerta **R5.1** | cobertura de `src/core/deep_synthesizer.py` (260 líneas faltantes del núcleo vivo) | Compuerta siguiente de P5, una sola tarea por turno |

**Efecto de la ratificación:** el criterio P5 se evalúa desde ahora sobre el **núcleo vivo** (2949 st). Estado de partida de esa medición: **2331/2949 = 79.0 %** → faltan **≈28 líneas** para el umbral del 80 %. Las salvaguardas **R6-1…R6-6** (§5.3) siguen vigentes: la exclusión no declara cubierto ningún módulo excluido y todo módulo que pase a ser alcanzable **reingresa** al denominador en la misma compuerta que lo conecte.

---

## Anexo A · Script del diagnóstico (reproducible)

```python
import ast, json
from pathlib import Path

SRC = Path("HPR/src")                      # ajustar a la ruta local

def canonico(p):
    partes = list(p.relative_to(SRC.parent).with_suffix("").parts)
    if partes[-1] == "__init__":
        partes = partes[:-1]
    return ".".join(partes)

modulos = {canonico(p): p for p in SRC.rglob("*.py")
           if "__pycache__" not in p.parts and not p.name.startswith("test_")}

def imports_de(ruta):
    arbol = ast.parse(ruta.read_text(encoding="utf-8", errors="replace"))
    origen = canonico(ruta)
    paquete = origen.rsplit(".", 1)[0] if ruta.name != "__init__.py" else origen
    destinos = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            for a in nodo.names:
                destinos.add(a.name)
        elif isinstance(nodo, ast.ImportFrom):
            nivel = nodo.level or 0
            base = paquete
            for _ in range(max(nivel - 1, 0)):
                base = base.rsplit(".", 1)[0] if "." in base else base
            destinos.add(f"{base}.{nodo.module}" if (nivel and nodo.module)
                         else (nodo.module or base))
            if not nodo.module:
                destinos |= {f"{base}.{a.name}" for a in nodo.names}
    normal = {m: m for m in modulos}
    normal |= {m[4:]: m for m in modulos if m.startswith("src.")}
    return {normal[d] for d in destinos if d in normal}

grafo = {m: imports_de(p) for m, p in modulos.items()}

def alcanzables(raices):
    vistos, pila = set(), list(raices)
    while pila:
        actual = pila.pop()
        if actual in vistos or actual not in modulos:
            continue
        vistos.add(actual)
        pila.extend(d for d in grafo[actual] if d not in vistos)
    return vistos

API = alcanzables(["src.main"])
DESKTOP = alcanzables(["src.desktop", "src.desktop.__main__", "src.desktop.app"])
print("VIVO:", len(API | DESKTOP), "de", len(modulos), "modulos de produccion")
for m in sorted(modulos):
    etiqueta = ("VIVO-API" if m in API else "") + ("VIVO-DESKTOP" if m in DESKTOP else "")
    print(f"  {(etiqueta or 'NO VIVO'):22s} {m}")
```

**Verificación cruzada realizada:** la única arista dinámica del árbol es `src/desktop/voice.py:33`; los grupos de §4 y §5 suman **6101** sentencias y las 6 fachadas `__init__` restantes aportan **14** → **6115** exactas, coincidiendo con la medición de `pyproject.toml` (`--cov=src`).

---

### Firma

| Rol | Nombre | Estado |
|---|---|---|
| Coordinación / responsable del proyecto | Coordinación HPR | **RATIFICADO el 2026-10-17 — Escenario B (núcleo vivo) como alcance oficial de P5 (§10)** |
| Reviewer (auditoría independiente) | Reviewer HPR | Diagnóstico emitido (R5.0); hallazgos H1–H4 registrados; salvaguardas R6-1…R6-6 fijadas |
