# Deuda técnica declarada — Fase 1 (hallazgos H1–H5b)

**Plan Maestro de Auditoría Arquitectónica — Motor HPR · Cierre de Fase 1**
**Commit de registro:** `55e225e` · **Acta de cierre P5:** `docs/auditorias/ACTA_CIERRE_P5.md`
**Naturaleza:** registro formal de los hallazgos detectados durante el bloque R (R1–R5.1) y el cierre de P5. **Ninguno está corregido.** Todos constituyen **deuda declarada** (D6, `docs/constitution.md:48`); su corrección exige compuerta propia con prueba rojo→verde.

> Este documento **no** autoriza borrar, reescribir ni reconectar nada. Sólo **declara y clasifica** la deuda, su impacto y la compuerta prevista para resolverla.

---

## 1. Resumen y clasificación

| ID | Hallazgo | Criticidad | Impacto principal | Compuerta prevista |
|---|---|---|---|---|
| **H1** | «Núcleo de razonamiento» desconectado del motor vivo (1 337 st) | **Media** (estructural) | Arquitectura / expectativa del producto; **raíz de H2** | Estructural (H1/H3/H4) |
| **H2** | Triggers `N1_BUSQUEDA`/`N2_GRAFO`/`MOTOR_RAZON` afirman trabajo no realizado | **Alta** | Veracidad / confianza del usuario; defecto funcional demostrable | **G2 — corrección (rojo→verde)** |
| **H3** | `core/triage.py` (canónico de R1) es código muerto; la ruta viva usa el duplicado | **Media** | Seguridad / mantenibilidad (divergencia de triaje) | Estructural (H1/H3/H4) |
| **H4** | Colisión de nombres `nexus_root` (validación viva vs paquete legacy) | **Media** | Mantenibilidad / auditabilidad | Estructural (H1/H3/H4) |
| **H5** | Helpers sin invocador en módulo vivo (`deep_synthesizer.py`) | **Baja** | Mantenibilidad (código muerto acotado) | Helpers (H5/H5b) |
| **H5b** | Corpus perdido por clave inexistente (`"corpus"`) en ruta sin invocador | **Media** (latente) | Correctitud latente (se manifiesta si se reconecta H5) | Helpers (H5/H5b) |

**Escala de criticidad:** *Alta* = afecta la veracidad o la seguridad del producto; *Media* = deuda estructural/mantenibilidad o defecto latente; *Baja* = código muerto acotado sin efecto observable.

---

## 2. Fichas de hallazgo

### H1 · El «núcleo de razonamiento» está desconectado del motor vivo

- **Descripción:** `MotorRazonamientoSuperior` (`src/core/reasoning_engine.py:89`) y su factoría `crear_motor_razonamiento` (`:744-746`) **no tienen llamadores**. Con `iterative_planner.py:193,326`, `episodic_memory.py:451-462`, `causal_synthesis.py:20-25` y `causal_templates.py` suman **1 337 sentencias alcanzables sólo desde sí mismas**. `stratified_reasoning.py` sólo se invoca desde la consola legacy (`nexus_root/executor.py:25`).
- **Evidencia:** la suite completa ejecuta los handlers de `MOTOR_RAZON` (`src/main.py:1191-1200`) y, aun así, `reasoning_engine.py`, `iterative_planner.py`, `episodic_memory.py` y `causal_synthesis.py` permanecen al **0 %** de ejecución (medición R5.1/R6).
- **Criticidad:** **Media** (estructural).
- **Impacto:** el producto anuncia «MotorRazonamientoSuperior (síntesis)» (`src/schemas.py:36`; textos en `src/main.py:590,636,641`) sin ejecutar la síntesis del módulo. Es la **raíz** de la deshonestidad de H2. Además, 1 337 sentencias lastran el denominador de cobertura (excluidas del núcleo vivo por no alcanzabilidad; ver `INVENTARIO_NUCLEO_VIVO.md` §4.1).
- **Compuerta prevista:** **estructural** (junto con H3/H4). Decidir **reconexión real** o **retiro/archivo** (D6, R6-5). Toca `src/` ⇒ requiere plan propio.
- **Criterio de cierre:** o bien el motor vivo invoca realmente el núcleo de razonamiento (y las 1 337 st reingresan al denominador, R6-3), o bien el código se retira/archiva con decisión registrada.

### H2 · Honestidad de los handlers de trigger (discrepancia demostrable)

- **Descripción:** tres handlers afirman trabajo no realizado:

| Handler | Líneas | Devuelve | Trabajo real |
|---|---|---|---|
| `N1_BUSQUEDA` | `src/main.py:1168-1179` | `"resultados": []` + *«Búsqueda cognitiva **ejecutada** sobre el último turno.»* | ninguno |
| `N2_GRAFO` | `src/main.py:1181-1189` | `"conflictos": []` + *«Grafo de consistencia **verificado**: no se detectaron conflictos.»* | ninguno |
| `MOTOR_RAZON` | `src/main.py:1191-1200` | `"sintesis": f"Síntesis de sesión {id} con {N} turnos."` (cadena literal) | ninguno |

- **Contraste que fija el estándar:** `WEB_SEARCH` (`src/main.py:1150-1166`) **sí** es honesto desde la Fase 1 — devuelve `estado="no_disponible"` y declara textualmente que el motor no genera resultados simulados. El proyecto ya tiene el criterio; estos tres handlers no lo cumplen.
- **Criticidad:** **Alta** (veracidad / confianza).
- **Impacto:** el sistema comunica al usuario éxito de operaciones que no ocurren (viola el principio de veracidad y la prohibición de falso éxito). Es un **defecto funcional demostrable**, no una hipótesis.
- **Compuerta prevista:** **G2 — corrección funcional**, con **prueba rojo→verde** sobre `src/main.py`. *(Única tarea autorizada tras G1.)*
- **Criterio de cierre:** los tres handlers devuelven el **estado real** (p. ej. `no_disponible`/`no_implementado`, siguiendo el patrón de `WEB_SEARCH`), sin afirmar trabajo no realizado, con pruebas que fijen el nuevo contrato.

### H3 · Duplicado muerto en el triaje

- **Descripción:** `src/core/triage.py:19` —la implementación que R1 identificó como **canónica y correcta**— sólo es importada por `src/test_triage.py:9` (código muerto en producción). La ruta viva usa el **duplicado** `src/core/engine.py:178`, invocado desde `src/desktop/agent.py:33,112`.
- **Criticidad:** **Media** (seguridad / mantenibilidad).
- **Impacto:** la versión «correcta» no es la que ejecuta el producto; riesgo de **divergencia** de comportamiento en el triaje (función sensible). Deuda de duplicación agravada.
- **Compuerta prevista:** **estructural** (H1/H3/H4). Unificar en una única implementación canónica (reconectar o retirar el duplicado).
- **Criterio de cierre:** una sola implementación viva de triaje, referenciada por la ruta de producción y por las pruebas, con decisión registrada sobre el duplicado.

### H4 · Colisión de nombres `nexus_root`

- **Descripción:** `nexus_root_validation` —validación de identidad **viva**— vive en `src/core/engine.py` y se usa en `src/main.py:1380`. El paquete `src/nexus_root/` (1 769 sentencias legacy, inalcanzable) usa el **mismo nombre** en su documentación (`src/nexus_root/__init__.py:1-2`).
- **Criticidad:** **Media** (mantenibilidad / auditabilidad).
- **Impacto:** no es un defecto funcional hoy, pero induce a confusión en auditorías futuras (dos «nexus_root»: validación viva vs paquete legacy inalcanzable).
- **Compuerta prevista:** **estructural** (H1/H3/H4). Renombrar para desambiguar o retirar el paquete legacy.
- **Criterio de cierre:** un único significado de `nexus_root` sin ambigüedad, documentado.

### H5 · Código sin invocador dentro del módulo vivo

- **Descripción:** `_extraer_metricas_agrupadas` (`src/core/deep_synthesizer.py:264-283`) y `_generar_informe_con_expansion` (`:1110-1146`) **no tienen invocador** (grep en todo el repositorio: sólo su definición), pese a que el módulo está cubierto al 100 % de líneas por la suite R5.1.
- **Criticidad:** **Baja** (mantenibilidad).
- **Impacto:** código muerto acotado dentro de un módulo vivo (≈41 líneas). Al estar cubierto por pruebas sin llamador de producción, es candidato a **retiro** o a **reconexión** (y, si se reconecta, activa H5b).
- **Compuerta prevista:** **helpers (H5/H5b)**. Retirar o reconectar en `core/deep_synthesizer.py`.
- **Criterio de cierre:** o se reconectan con invocador real (y prueba de la ruta completa), o se retiran con decisión registrada.

### H5b · Corpus perdido en la ruta de expansión sin invocador

- **Descripción:** en `_generar_informe_con_expansion`, la expansión consulta la clave inexistente `"corpus"` de `metricas_procesamiento`:

  ```python
  # src/core/deep_synthesizer.py:1126
  expansion = self._generar_expansion_contextual(
      query, informe_base.hallazgos_tecnicos,
      informe_base.metricas_procesamiento.get("corpus", ""))   # clave inexistente
  ```
  La clave real construida en `procesar_resultados` es **`total_caracteres_procesados`** (`src/core/deep_synthesizer.py:114`).
- **Criticidad:** **Media** (latente).
- **Impacto:** defecto de **correctitud latente**. Hoy no se manifiesta porque la ruta no tiene invocador (H5); si se reconecta sin corregir, la expansión contextual recibiría **siempre corpus vacío** ⇒ informe degradado silenciosamente.
- **Compuerta prevista:** **helpers (H5/H5b)**, en la **misma** compuerta que H5 (no reconectar sin corregir la clave).
- **Criterio de cierre:** la clave consultada coincide con la construida, con prueba que verifique el corpus no vacío en la ruta de expansión.

---

## 3. Priorización recomendada

1. **H2 (Alta)** — primero: es un defecto funcional demostrable que afecta la veracidad del producto y tiene corrección acotada (`src/main.py`). **Compuerta G2.**
2. **H1 + H3 + H4 (Media, estructural)** — en segundo lugar: comparten naturaleza (código muerto/duplicado/colisión) y una misma decisión de fondo (retiro/archivo vs reconexión real). Requiere plan propio (D6).
3. **H5 + H5b (Baja/Media, latente)** — tercero: limpieza acotada de un módulo vivo; **H5b no debe reconectarse sin corregirse**.
4. **Instrumentación del umbral (Decisión nº 5)** — transversal; ver `ACTA_CIERRE_P5.md` §7 (O5-a/O5-b/O5-c), pendiente de autorización.

---

## 4. Reglas de tratamiento (vinculantes)

- **D6 / R6-5:** los hallazgos permanecen como **deuda declarada**; este registro no autoriza borrar ni reescribir código.
- **Prueba rojo→verde obligatoria:** toda corrección funcional (H2, H5b) exige una prueba que falle antes y pase después. Si un hallazgo tenía marcador `xfail(strict=True)`, se **retira** en la compuerta de corrección (precedente: R1-FIX, R4-FIX).
- **Prohibido falso verde:** no se eleva cobertura de código muerto con pruebas artificiales; no se relajan pruebas existentes.
- **Reingreso automático (R6-3):** si una corrección reconecta módulos excluidos (p. ej. H1), **reingresan al denominador de P5 en la misma compuerta** que los conecta.
- **Trazabilidad:** cada corrección se registra con `archivo:línea`, hash del commit y prueba asociada; el estado de esta tabla se actualiza al cerrar cada compuerta.

---

## 5. Firma

| Rol | Nombre | Estado |
|---|---|---|
| Coordinación / responsable del proyecto | Coordinación HPR | **Registrado** — deuda declarada, sin corregir (2026-10-17) |
| Reviewer (auditoría independiente) | Reviewer HPR | H1–H5b verificados con evidencia `archivo:línea` |
