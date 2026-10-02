# Constitución del Proyecto HPR

**Proyecto:** Motor HPR — Arquitectura Híbrida
**Versión de la Constitución:** 1.0.0
**Fecha de ratificación:** 2026-10-02
**Autoridad:** Coordinación del proyecto HPR
**Ámbito:** la totalidad del repositorio (`motor HPR/`), incluidos `HPR/src/`, la bóveda documental (`HPR/boveda y vitacoras/`), la configuración de agentes (`.opencode/agents/`) y todo colaborador —humano o agente de IA— que opere sobre el proyecto.

> **Estado: INNEGOCIABLE.** Ninguna regla de esta constitución puede suspenderse por plazos, conveniencia, preferencias estéticas o presión externa. La única vía de cambio es una enmienda formal (§7).

## Pacto fundacional

El Motor HPR es un sistema de misión crítica. Su valor no depende de una funcionalidad aislada, sino de cuatro propiedades que lo hacen confiable: los datos del propietario son suyos (**soberanía**), el sistema vive donde el propietario decide (**ejecución local**), su comportamiento es predecible (**determinismo**) y toda afirmación sobre él se demuestra con pruebas (**rigor**). Estas propiedades se traducen en reglas vinculantes con identificadores estables (`S#`, `E#`, `D#`, `P#`) que los agentes del proyecto citan en planes, implementaciones y revisiones.

## 1. Soberanía de datos (S)

**Principio:** el conocimiento del proyecto —consultas, estados, verdad de referencia, métricas, bitácoras y la bóveda documental— pertenece al propietario y jamás sale de su jurisdicción sin su consentimiento explícito.

- **S1 — Jurisdicción local.** Todos los datos del proyecto se almacenan, procesan y respaldan en el entorno local del propietario. La bóveda (`HPR/boveda y vitacoras/`) es zona de soberanía máxima: su contenido no se sincroniza a servicios en la nube sin cifrado y sin registro en la bitácora.
- **S2 — Sin exfiltración.** Ningún componente del motor —API, pipeline, agente— puede transmitir datos del proyecto a un servicio externo. Toda excepción requiere consentimiento documentado del propietario y registro en la bitácora.
- **S3 — Sin telemetría ajena.** Se prohíbe instrumentar el motor con analíticas o telemetría de terceros. Los registros y vitácoras se escriben exclusivamente en el sistema local.
- **S4 — Secretos fuera del control de versiones.** Credenciales, claves y tokens nunca se consolidan en el repositorio; se gestionan mediante variables de entorno locales.
- **S5 — Integridad verificable.** Los artefactos críticos de la bóveda se protegen con hashes registrados; cualquier alteración debe ser detectable mediante verificación de integridad.
- **S6 — Consentimiento para procesamiento inteligente.** Si un dato se somete a procesamiento con IA, aplica la misma soberanía: el procesamiento remoto no autorizado es una violación grave, no un detalle menor.

*Verificación:* el reviewer audita dependencias con telemetría, llamadas salientes en el runtime y el historial del control de versiones en busca de secretos.

## 2. Ejecución local (E)

**Principio:** el motor se ejecuta, prueba y valida íntegramente en la estación de trabajo local. Un escenario sin red no puede inmovilizar el sistema.

- **E1 — Primacía local.** El ciclo de desarrollo (ejecución, pruebas, validación) ocurre en la máquina local, como declara la propia interfaz (`HPR Local Agent Interface`).
- **E2 — Offline por defecto.** El funcionamiento normal no depende de servicios en la nube. Toda dependencia de red es una excepción justificada y documentada, nunca un supuesto implícito.
- **E3 — Entorno propio y declarado.** Se usa el entorno virtual del proyecto (`.venv/`) y toda dependencia —incluso las importadas por el código— aparece declarada y pinneada en `HPR/requirements.txt`.
- **E4 — Agentes confinados al proyecto.** Los agentes `planner`, `implementer` y `reviewer` operan dentro del repositorio con los permisos definidos en `.opencode/agents/`; su acceso a herramientas web está revocado por defecto.
- **E5 — Sin llamadas ocultas.** El pipeline (`process_pipeline`) y cualquier servicio del motor no pueden realizar llamadas salientes no declaradas en su contrato.
- **E6 — Conocimiento local.** La base de conocimiento del motor es la bóveda local (`.docx` bajo `HPR/boveda y vitacoras/`); el motor nunca obtiene su conocimiento de fuentes remotas no verificadas.

## 3. Determinismo (D)

**Principio:** dada la misma entrada, el mismo estado y la misma verdad de referencia, el motor produce la misma salida, en el mismo orden, en cualquier máquina y en cualquier momento.

- **D1 — Misma entrada, misma salida.** El resultado de `process_pipeline` es función exclusiva de sus argumentos (`payload`, `state`, `truth`).
- **D2 — Azar solo con semilla fija.** Toda fuente de aleatoriedad usa semilla declarada. Prohibido depender del reloj del sistema, del orden de iteración no garantizado o de cachés no versionadas en el camino crítico.
- **D3 — Dependencias exactas.** Las dependencias se fijan por versión exacta (con lockfile); los rangos abiertos (`>=`) quedan prohibidos en el camino crítico.
- **D4 — Contratos estrictos en la frontera.** Toda entrada externa se valida con esquemas Pydantic y restricciones explícitas (como `ge`/`le` en `CommunicationQuerySchema`); nada ingresa al motor sin validar.
- **D5 — Identidad inmutable.** El estado del pipeline porta la identidad `HPR-CORE-DETERMINISTIC`; cualquier cambio que rompa la reproducibilidad se rechaza de plano.
- **D6 — Sin placeholders.** No se consolidan archivos vacíos ni esqueletos sin contrato ni pruebas; son deuda declarada, no avance.

## 4. Rigor en pruebas automatizadas (P)

**Principio:** en HPR, lo que no se prueba localmente no existe. La confianza se gana con aserciones, no con impresiones.

- **P1 — Prueba o no existe.** Toda funcionalidad nueva o modificada se entrega con pruebas automatizadas que se ejecutan en local antes de darse por concluida.
- **P2 — Framework estándar.** Las pruebas usan `pytest` con aserciones explícitas. Los scripts basados en `print`/`sleep` (como los actuales `src/test_*.py`) no son pruebas y deben migrarse.
- **P3 — Pruebas deterministas.** Sin red, sin reloj, sin orden de ejecución, sin estado global compartido. Una prueba válida pasa igual ejecutada una vez o mil veces.
- **P4 — Pruebas negativas obligatorias.** El guardia de seguridad debe demostrar el bloqueo de phishing, inyección (`<script>`), inyección SQL (`DROP TABLE`) y anulación de identidad (`OVERRIDE_ROOT`), además de los casos favorables.
- **P5 — Cobertura medible.** Se mide la cobertura sobre `src/`; los módulos de seguridad (`security_agent`, guardias de validación) exigen cobertura completa de ramas.
- **P6 — Mismo entorno que producción local.** Las pruebas corren con el Python del proyecto (3.14) y el `.venv/` del repositorio. "Pasa en mi máquina" es el requisito mínimo, no una excusa.
- **P7 — Pruebas que no mutan.** Ninguna prueba escribe en la bóveda ni en datos reales; utiliza fixtures temporales y los limpia.

## 5. Orden de precedencia

Ante conflicto entre un requisito y esta constitución, rige la constitución. Ante colisión entre reglas del mismo nivel, rige la de mayor soberanía: **S > E > D > P**.

## 6. Estructura de agentes

Los agentes del proyecto viven en `.opencode/agents/` y están sujetos a esta constitución tanto como cualquier humano:

| Agente | Archivo | Función | Alcance |
| --- | --- | --- | --- |
| `planner` | `.opencode/agents/planner.md` | Explora y planifica; toda tarea nueva requiere un plan aprobado que cite las reglas aplicables (S/E/D/P) | Solo lectura |
| `implementer` | `.opencode/agents/implementer.md` | Ejecuta el plan aprobado con soberanía y determinismo, y prueba en local antes de cerrar | Lectura/escritura, sin web |
| `reviewer` | `.opencode/agents/reviewer.md` | Auditor independiente; verifica S/E/D/P, ejecuta pruebas con aprobación y reporta hallazgos con `archivo:línea` | Solo lectura; veto ante violación |

## 7. Gobernanza, enmienda y veto

- **Enmienda formal:** toda modificación requiere propuesta escrita, revisión por los tres roles (planner, implementer, reviewer) y registro en la bitácora de ingeniería con fecha y motivo.
- **Veto:** toda violación detectada de las reglas S/E/D/P es un veto. El trabajo se detiene hasta la corrección; ninguna entrega se acepta con violaciones abiertas.
- **Control de versiones local:** el proyecto opera bajo control de versiones local (git) como instrumento de soberanía y trazabilidad. Si el repositorio aún no estuviera inicializado, hacerlo es tarea de nivel 0.
- **Aplicación simétrica:** estas reglas vinculan por igual a colaboradores humanos y a agentes de IA.

## Anexo A — Línea base y deuda conocida (2026-10-02)

Situación observada al ratificar esta constitución; cada ítem es deuda por remediar, no permiso para incumplir:

1. **D3/E3:** `HPR/requirements.txt` declara rangos abiertos (`>=`) y omite `python-docx` y `streamlit`, ambos importados por el código. Acción: pinneo exacto y lockfile.
2. **P2/P3:** `HPR/src/test_engine.py` y `HPR/src/test_security.py` son scripts con `print` y `sleep`, sin aserciones. Acción: migrar a pytest con aserciones y pruebas negativas (P4).
3. **D6:** `HPR/src/core/engine.py`, `HPR/src/core/triage.py` y `HPR/src/models/contracts.py` están vacíos. Acción: definir su contrato y pruebas, o eliminarlos.
4. **§7:** el proyecto no es aún un repositorio git. Acción: inicializar control de versiones local.
5. *Nota técnica:* `src/security_agent.py` (legado, `HPRSecurityEngine`) y `src/core/security_agent.py` (guardia de la API) solapan responsabilidad de seguridad; consolidar bajo un mismo contrato sin perder las tres validaciones raíz (Nexus Root, Epsilon Wall, Sovereign Gate).
