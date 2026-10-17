# Directiva operativa para agentes · Estado oficial de la hoja de ruta (Pasos 12–13)

**Plan Maestro de Auditoría — Motor HPR · Fase 1**
**Commit base:** `d38d0ac` (criterios Paso 11)

---

## Paso 12 · Directiva operativa para agentes de desarrollo

### Texto de la directiva (Plan Maestro)

> Los agentes deben trabajar por etapas y presentar resultados verificables antes de avanzar. Primero
> inventariar; después reproducir; luego auditar contratos y trazabilidad; posteriormente diagnosticar;
> finalmente corregir y validar. No se autoriza una reescritura general, nuevas funcionalidades ni la
> ejecución anticipada de fases posteriores.
> Toda hipótesis debe distinguirse de un defecto demostrado. Toda modificación debe vincularse a una
> causa identificada. Toda afirmación de éxito debe contar con evidencia reproducible.

### Adopción operativa (normas vinculantes derivadas)

1. **Trabajo por etapas con compuerta de aprobación.** Cada paso entrega evidencia y **detiene** la
   ejecución hasta autorización expresa del responsable. *(Cumplido: Pasos 1–13, cada uno con informe y
   aprobación.)*
2. **Secuencia obligatoria:** inventariar → reproducir → auditar contratos y trazabilidad →
   diagnosticar → corregir → validar. *(Cumplido: Fases A–F antes de toda corrección.)*
3. **Hipótesis ≠ defecto demostrado.** Toda causa raíz debe reproducirse antes de corregir.
   *(Ejemplo: Fase F descartó escenarios A/B/C/F con evidencia y fijó D como causa, con E como agravante.)*
4. **Toda modificación se vincula a una causa identificada** y llega con **prueba de regresión** que
   falla antes y pasa después:
   | Corrección | Causa identificada | Prueba (rojo→verde) |
   |---|---|---|
   | **G.1** chat | Fase E: el chat cotidiano caía al motor forense por relleno forzado | `src/test_g1_chat_desacople.py` (5/5) |
   | **G.2** contrato trigger | Fase D: `result` era dict libre ciego y `success` se asumía | `src/test_g2_contrato_trigger.py` (6/6; rojo `assert True is False`) |
   | **G.3** consola | Fase F: la UI interpretaba mal los datos (turnos↔subtóreas, sesiones↔validaciones) | `src/test_g3_nexus_console.py` (6/6; rojo 5/6 en HEAD) |
5. **Sin reescritura general, sin funcionalidades nuevas, sin fases anticipadas.** Las Fases 2–7 no se
   tocaron; las correcciones fueron acotadas a los archivos en alcance de cada sub-paso.
6. **Toda afirmación de éxito exige evidencia reproducible.** Registrada en `docs/` (auditoría A–B–C,
   acta Fase H, criterios Paso 11). Sin evidencia no se declara corrección.
7. **Distinguir datos medidos de valores por defecto** (regla derivada de Fase F). La UI rotula cada
   métrica con su fuente real (G.3) y no muestra un default como si fuera medición.
8. **Preservar el trabajo no versionado ajeno al alcance.** No se borra ni sobrescribe trabajo del
   usuario que no pertenezca al paso en curso.

### Prohibiciones vigentes

- ❌ Reescritura general del motor.
- ❌ Nuevas funcionalidades durante la Fase 1.
- ❌ Ejecución anticipada de fases posteriores (2–7).
- ❌ Debilitar capas de seguridad o límites epistemológicos por naturalidad de la UI.
- ❌ Inventar fuentes, metadatos, confianza o telemetría.

---

## Paso 13 · Estado oficial de la hoja de ruta

| Elemento | Estado |
|---|---|
| **Fase 1 — Auditoría y estabilización** | **ABIERTA · BLOQUEANTE** |
| **Fases 2 a 7** | **APLAZADAS** |
| **Condición de avance** | Auditoría satisfactoria, correcciones verificadas, pruebas manuales aprobadas y autorización expresa. |

**Fundamento del estado ABIERTA:** la verificación de los criterios obligatorios
(`docs/cierre-fase-1-criterios-paso-11.md`) deja **sin cumplir**:

- **#3 Los datos técnicos corresponden a ejecuciones reales** → `@web_search` devuelve
  `resultados_simulados` (fuente `hpr_local_fallback`).
- **#7 Las pruebas automatizadas/integración/regresión están aprobadas** → **209 passed / 19 failed /
  1 error**; cobertura **34.42 % < 80 %** (P5).
- **#5 / #8** quedan parciales (contenido simulado de `@web_search`; Fase H con observaciones).
- **#10** pendiente de autorización expresa del responsable.

**Regla final (Plan Maestro):** *ninguna fase se considera concluida por velocidad de implementación,
apariencia visual o ausencia de errores evidentes. Se concluye cuando el comportamiento esperado queda
demostrado y el responsable del proyecto aprueba el cierre.*

---

## Camino mínimo de cierre (acotado, sin reescritura)

1. **#3/#5** — Retirar la simulación de `@web_search` en `main.py` (`_execute_trigger_internal`):
   devolver `estado="no_disponible"` honesto; actualizar `test_trigger_web_search_estado_no_disponible`.
2. **#7** — Remediar los 19 fallos + 1 error de colección (`test_desktop_agent`, `test_engine`,
   `test_desktop_app`, `test_core_engine`).
3. **#7** — Acercar la cobertura a 80 % o documentar un umbral excepcional acordado.
4. **#10** — Autorización expresa de cierre del responsable.

*(Cada uno de estos puntos deberá ejecutarse como paso propio con prueba de regresión y aprobación.)*
