# PROMPT MAESTRO PARA OPENCODE — REDISEÑO E IMPLEMENTACIÓN DE LA INTERFAZ DUAL HPR

## Rol que debés asumir

Actuá como un equipo senior de arquitectura de software, ingeniería full-stack, diseño de producto (UX/UI), integración de audio accesible y QA. Tu objetivo no es crear una demo aislada ni reemplazar el motor: debés **inspeccionar el repositorio HPR existente, rediseñar su interfaz actual y conectarla correctamente a las capacidades reales del proyecto**, respetando la arquitectura, los contratos, las políticas de seguridad y las pruebas que ya existan.

Trabajá sobre el repositorio abierto en el workspace actual. No asumas que esta especificación describe exactamente el estado actual del código: primero descubrí cómo está construido hoy y adaptá la implementación a lo que realmente existe.

---

## 1. Objetivo principal

Transformar la interfaz actual, que hoy es visualmente rudimentaria, en una **interfaz dual profesional para HPR — Hybrid Predictive Reasoning**. Debe acercarse visualmente y en distribución a la previsualización HTML de referencia denominada `HPR_interfaz_dual_previsualizacion.html`, si está disponible en el workspace o en los archivos entregados.

La composición de escritorio es obligatoria:

- **LADO IZQUIERDO: MOTOR TÉCNICO.** Panel de ingeniería con selector de triggers, selector de niveles de confianza, pipeline/grafo de ejecución, controles, seguridad, eventos, telemetría disponible y traza operativa.
- **LADO DERECHO: CHAT AUTÓNOMO.** Chat conversacional completo, con entrada por texto, entrada por micrófono, síntesis de voz para escuchar respuestas y opciones comunes de los chats LLM actuales.

Ambos espacios deben sentirse parte de un mismo producto, compartir identidad visual y sesión cuando la arquitectura actual lo permita, pero conservar funciones claramente diferenciadas. El chat permite expresar objetivos en lenguaje natural; el panel técnico permite observar y controlar las operaciones autorizadas.

**Idea rectora:** una inteligencia, dos planos de interacción y un único perímetro de seguridad.

---

## 2. Regla prioritaria: inspeccionar antes de modificar

Antes de escribir código:

1. Inspeccioná la estructura del repositorio, README, documentación técnica, archivos de configuración, dependencias, punto de entrada de la aplicación y estado del control de versiones.
2. Identificá el framework real de interfaz, el framework del backend, el flujo de ejecución actual, la gestión de sesión y los contratos de entrada/salida.
3. Localizá los módulos reales de triggers, niveles de confianza, detección/selección, enrutamiento, pipeline, estado de sesión y controles de seguridad.
4. Leé y respetá las pruebas existentes, en particular las relacionadas con la UI/Nexus, los niveles de confianza, los triggers, el pipeline y las barreras de seguridad. En el historial del proyecto existe una referencia a `test_nexus_ui.py` con 20 pruebas; verificá el estado y resultado actuales, no des por sentado que siguen iguales.
5. Revisá la implementación efectiva de componentes conocidos del motor: NEXUS-ROOT, EPSILON-WALL, SOVEREIGN-GATE, detector/selector/router, N1 Búsqueda Cognitiva, N2 Grafo de Consistencia, E-E-A-T, `query_builder.py`, NexusRouter y MotorRazonamientoSuperior. Usá los nombres y las dependencias que realmente existan en el código.
6. Identificá qué funcionalidades están completas, cuáles son parciales y cuáles no existen todavía. No presentes como operativa una capacidad que no esté implementada.
7. Comprobá el estado del repositorio antes de editar. No sobrescribas ni reviertas cambios ajenos. No hagas commits, pushes ni cambios destructivos salvo que el usuario lo solicite explícitamente.

Después de la inspección, compartí un resumen breve del estado encontrado y empezá la implementación. No te quedes únicamente en un diagnóstico o una propuesta de diseño.

### Referencias arquitectónicas conocidas que debés verificar

- El proyecto ha utilizado una interfaz local con Streamlit y componentes como `web_interface.py`, `app.py`, `security_agent.py`, `detector.py`, `selector.py` y `router.py`. **Son pistas de búsqueda, no una orden de asumir que todos esos archivos siguen siendo el punto de entrada actual.**
- Existe historial de un backend FastAPI/Uvicorn y modelos/contratos Pydantic. Verificá las rutas efectivas antes de invocarlas.
- En el documento conceptual previo se propusieron `/api/v1/chat` para el canal conversacional y `/api/v1/orchestrate` para el canal técnico. No las crees ni las des por disponibles sin comprobar los routers y contratos reales.
- La interfaz debe reutilizar los servicios de backend ya existentes. No dupliques dentro del frontend la lógica central de razonamiento, autorización ni selección de confianza.

---

## 3. Restricciones de arquitectura

- Conservá el stack y el patrón de interfaz existente en la medida en que permitan cumplir el objetivo. No migres de framework, reescribas el backend ni introduzcas una nueva arquitectura completa por comodidad estética.
- Preferí cambios incrementales, componentes reutilizables y dependencias ya presentes. Añadí una dependencia nueva solo si es necesaria, compatible y está justificada.
- No uses el HTML de referencia como sustituto del sistema real. Es una referencia visual y de interacción, no el backend ni el código fuente que deba copiarse ciegamente.
- No dupliques lógica de triggers, niveles de confianza, validaciones o política de seguridad en la UI. La interfaz refleja el estado; la autoridad efectiva permanece en el backend.
- No rompas contratos, nombres públicos, endpoints, rutas de importación ni comportamiento del sistema sin una necesidad probada. Si hace falta modificar alguno, documentá el motivo y añadí pruebas.
- No agregues respuestas ficticias ni telemetría inventada al modo normal de la aplicación. Los datos simulados solo se permiten en una demo aislada y deben estar rotulados como `DEMO`, `SIMULADO` o equivalente. En el producto integrado, mostrar `No disponible` o un estado equivalente cuando falte una métrica real.
- No registres en logs contraseñas, tokens, secretos, payloads privados ni contenido sensible innecesario.
- No neutralices, eludas ni reduzcas las protecciones para simplificar el flujo conversacional.

---

## 4. Sistema visual: acercarse a la demo de referencia

Implementá un entorno de ingeniería oscuro, sobrio y profesional. No uses fondos blancos, verde neón dominante, gradientes llamativos por todas partes ni efectos decorativos que compitan con los datos.

### Tokens visuales de referencia

Usá estos valores como punto de partida; podés ajustarlos levemente solo para mantener contraste y coherencia con el framework actual:

- Fondo general: `#070D16`
- Panel principal: `#0C1522`
- Superficie secundaria: `#101D2C`
- Superficie elevada: `#132338`
- Bordes base: `#24364B`
- Bordes activos: `#30475F`
- Texto primario: `#EDF4FB`
- Texto secundario: `#8DA2B9`
- Cian primario: `#53C9EE`
- Cian profundo: `#209AC5`
- Verde de estado satisfactorio: `#50C7A0`
- Ámbar de advertencia: `#E9B76A`
- Rojo de error/bloqueo: `#E47783`

### Apariencia y jerarquía

- Encabezado superior compartido, con marca `HPR`, subtítulo `HYBRID PREDICTIVE REASONING`, estado general del sistema e identificador de sesión si existe.
- Enlaces/pestañas principales o etiquetas que indiquen con claridad `MOTOR TÉCNICO` y `CHAT AUTÓNOMO`, manteniendo la distribución de escritorio solicitada.
- Paneles oscuros con bordes sutiles, esquinas moderadas, separación visual limpia y sombras discretas.
- Cian para el foco, navegación activa, enlaces del pipeline y controles interactivos; verde solo para éxito confirmado; ámbar para advertencias; rojo moderado para errores o bloqueos.
- Tipografía sans serif legible en conversación y títulos. Fuente monoespaciada solo donde aporte valor: IDs, logs, parámetros y eventos.
- Iconos coherentes y accesibles. Si no hay una librería instalada, reutilizá la solución que ya use el proyecto en lugar de sumar varias librerías.
- Estados visuales expresados también por texto o iconos; **nunca depender únicamente del color**.
- Evitá espacios vacíos exagerados, texto microscópico, paneles excesivamente comprimidos y scroll horizontal innecesario.

Usá variables/tokens de tema centralizados, no valores copiados de forma arbitraria en decenas de componentes.

---

## 5. Layout y comportamiento responsivo

### Escritorio

- Distribución en dos columnas simultáneas: **Motor Técnico a la izquierda y Chat Autónomo a la derecha**.
- Como orientación visual, el panel técnico puede ocupar aproximadamente el 52–56 % del ancho y el chat el 44–48 %, con un espacio consistente entre ambos. Ajustá el ancho mínimo según la resolución y los controles reales.
- Ambos paneles deben tener encabezados propios y áreas de contenido independientes. El encabezado principal de HPR se mantiene arriba.
- El chat debe reservar una zona de conversación desplazable y mantener accesible la caja de composición cerca del borde inferior del panel.
- El panel técnico puede tener scroll vertical propio para sus secciones densas. La telemetría y los registros no deben empujar ni ocultar el compositor del chat.
- No inmovilices toda la página si ello impide usar la interfaz en resoluciones pequeñas. Las barras pegajosas deben respetar el área útil y los límites del contenedor.

### Pantallas estrechas

- Adaptá la interfaz para móvil/tablet: apilá los paneles o convertí su navegación en pestañas accesibles sin eliminar ninguna funcionalidad.
- En pantallas estrechas, el usuario debe poder alternar claramente entre Motor Técnico y Chat Autónomo.
- No comprimas las dos columnas hasta volver ilegibles los controles y el texto.
- Conservá teclado, foco, lectura por tecnologías asistivas y controles de audio funcionales.

---

## 6. Requisitos funcionales del CHAT AUTÓNOMO (panel derecho)

La sección debe sentirse como un chat LLM completo, no como un cuadro de texto decorativo.

### 6.1 Historial y sesión

- Mostrar mensajes de usuario y agente con jerarquía visual diferenciada.
- Distinguir estados como enviando/procesando, respuesta recibida, error y cancelación.
- Mantener el historial durante los reruns/refrescos que formen parte del framework, usando la gestión de sesión ya existente.
- Ofrecer `Nueva conversación` y `Limpiar conversación`; solicitar confirmación cuando una acción borre contenido relevante.
- Si el proyecto dispone de persistencia o historial de conversaciones, reutilizarlo. Si no existe, no inventar persistencia: mantener la sesión local que permita el stack y documentar la limitación.
- Mostrar identificador o contexto de sesión solo si la aplicación lo gestiona realmente.
- Hacer scroll hacia el último mensaje cuando resulte apropiado, sin impedir que el usuario lea mensajes anteriores.

### 6.2 Compositor

- Campo multilínea que crece hasta una altura razonable.
- `Enter` envía y `Shift+Enter` inserta una nueva línea, salvo que el patrón del framework requiera otra convención claramente visible.
- Botón `Enviar` que se deshabilite de forma adecuada mientras no haya contenido o cuando una operación no permita otro envío.
- Botón para detener una generación/ejecución solo si se puede cancelar realmente; si el backend no soporta cancelación, no simular que se detuvo.
- Botón de micrófono para entrada por voz.
- Botón de adjuntar solo si existe soporte real para esos formatos y el backend puede consumir los archivos. Si solo se puede seleccionar un archivo pero no procesarlo, no presentar esa función como habilitada; marcarla como no soportada o dejarla fuera.
- Respetar límites de tamaño y tipo definidos por la aplicación.

### 6.3 Acciones por mensaje

Cuando tengan sentido en el stack, añadir:

- Copiar respuesta.
- Escuchar respuesta.
- Detener audio.
- Regenerar respuesta o volver a intentar, pero solo si puede repetirse la operación de forma correcta y segura.
- Indicadores de error y acción para reintentar.
- Feedback positivo/negativo solo si el proyecto puede registrar ese feedback de forma clara.

Las acciones deben aplicarse al mensaje correcto y no repetir la acción sobre un texto de otra respuesta. Gestioná fallos del portapapeles y errores del navegador con mensajes comprensibles.

### 6.4 Audio bidireccional

**Entrada por voz**

- Integrar reconocimiento de voz en español, con preferencia por `es-UY` cuando el navegador lo soporte.
- Utilizar la API de reconocimiento de voz disponible en el entorno o un componente compatible con el framework existente.
- El usuario inicia explícitamente la captura mediante el micrófono; indicar visualmente `Escuchando…` y permitir detener la captura.
- Mostrar la transcripción en el compositor para que pueda corregirse antes de enviarla. No enviar automáticamente una transcripción parcial.
- Gestionar permisos denegados, API ausente, micrófono ocupado, fin de captura y errores con mensajes claros. El chat escrito debe seguir funcionando si el audio no está disponible.
- No grabar ni enviar audio en segundo plano sin una acción explícita del usuario.

**Salida de voz**

- Añadir `Escuchar` a las respuestas del agente y un control global opcional para habilitar/deshabilitar la lectura automática de respuestas.
- Si se usa síntesis local del navegador, aprovechar `speechSynthesis` y seleccionar una voz en español cuando haya alguna disponible; no asumir que todas las plataformas ofrecen las mismas voces.
- Permitir detener la reproducción. Al comenzar una respuesta nueva, evitar que se mezclen varias lecturas; cancelar o finalizar la anterior de forma controlada.
- Indicar cuándo el audio se reproduce, finaliza o falla. No leer metadatos de interfaz o código salvo que el usuario lo pida.
- Si la aplicación ya tiene un servicio TTS —por ejemplo, una integración existente con `edge-tts`— inspeccionarlo y reutilizarlo si encaja. No sustituirlo automáticamente por una API del navegador sin evaluar la arquitectura y el comportamiento actual.
- No afirmar que se usa voz neuronal, audio en streaming o una voz específica si la implementación real no lo garantiza.

**Accesibilidad y privacidad de audio**

- Los controles de voz deben tener etiquetas accesibles y estados reconocibles por lectores de pantalla.
- No activar el micrófono al cargar la página.
- Hacer explícito si el audio se procesa localmente en el navegador o se envía a un servicio remoto, según la implementación real.

### 6.5 Conexión con el agente real

- El Chat Autónomo debe usar el servicio conversacional que exista en el proyecto, con sus modelos y contratos reales.
- No dejar `fakeReply`, respuestas hardcodeadas o demoras simuladas como comportamiento normal de la UI. Si se conserva un modo demo para pruebas, debe estar aislado, desactivado por defecto y rotulado claramente.
- Mostrar errores del backend sin ocultarlos ni filtrar trazas internas sensibles al usuario final.
- Gestionar respuestas vacías, timeout, pérdida de conexión, doble envío y errores recuperables.
- No crear un segundo motor de razonamiento dentro de la interfaz.

---

## 7. Requisitos del MOTOR TÉCNICO (panel izquierdo)

Esta sección debe reflejar la profundidad de ingeniería de HPR. No debe reducirse a un selector de tres botones con un chat al lado.

### 7.1 Cabecera técnica y control de ejecución

Incluir, de acuerdo con lo que soporte el backend:

- Nombre `MOTOR TÉCNICO` y descripción corta del plano de ingeniería.
- Estado verificable del motor y de la sesión.
- Campo de objetivo/instrucción técnica.
- Selector de trigger alimentado desde el registro o mecanismo real de triggers.
- Selector de nivel de confianza disponible en la implementación.
- Acción explícita para ejecutar/enviar al pipeline técnico.
- Indicador de autorización requerida o de bloqueo si la operación no está permitida.

No usar el mismo flujo de envío que el chat si ambos canales tienen contratos y responsabilidades diferentes. Compartir contexto no significa mezclar operaciones ni enviar la solicitud por el endpoint equivocado.

### 7.2 Selector de triggers

- Descubrí primero cómo se definen y validan los triggers actualmente. Utilizá esa fuente de verdad, no una lista duplicada en el frontend.
- Permitir seleccionar de forma comprensible los triggers disponibles, ver su nombre exacto y mostrar una explicación breve si existe en el código o la documentación.
- Si hay muchos triggers, ofrecer búsqueda/filtro.
- Mostrar el trigger seleccionado y cualquier parámetro requerido.
- Representar el estado como disponible, seleccionado, ejecutando, completado, fallido, bloqueado o requiere autorización, según el resultado real.
- Nombres conocidos en el historial del proyecto que se deben buscar, no dar por hecho: `@hpr_confianza`, `@nivel1`, `@web_search`. Renderizalos solo si están registrados o habilitados realmente.
- No ejecutar un trigger automáticamente por cambiar el selector. La ejecución debe seguir el comportamiento actual y requerir la acción esperada.
- No inferir que seleccionar un trigger concede permisos.

### 7.3 Niveles de confianza

- Presentar los niveles que existan en el sistema actual de manera visible y seleccionable cuando el usuario tenga autorización.
- Hay antecedentes de tres niveles de confianza. Confirmá los identificadores, nombres, transiciones y permisos en el código actual.
- Si el código solo permite identificar `Nivel 1`, `Nivel 2` y `Nivel 3`, usá esas etiquetas neutras hasta confirmar su significado. No inventes umbrales, privilegios, capacidades ni semánticas de seguridad.
- Mostrar el nivel activo y una breve descripción únicamente cuando esa descripción esté respaldada por la implementación/documentación.
- Los niveles son una señal de confianza/política, no un indicador decorativo de progreso.
- Cambiar el nivel debe pasar por la lógica de validación existente y generar los eventos que ya contemple el motor.
- La UI nunca será la autoridad final sobre acceso o confianza. El backend valida todos los permisos.

### 7.4 Vista del pipeline / grafo de ejecución

Crear una visualización compacta pero informativa del flujo real. Reutilizar bibliotecas presentes; si se propone una nueva biblioteca de grafos, justificar su necesidad.

Componentes que deben investigarse y mostrarse cuando existan realmente:

- NEXUS-ROOT — perímetro, estado o validación de entrada según su función implementada.
- Detector, selector y router — detección de intención/idioma, selección de ruta y enrutamiento, según los componentes presentes.
- N1 — Búsqueda Cognitiva, asociada en el historial del proyecto a scoring semántico por embeddings.
- N2 — Grafo de Consistencia, asociado a comprobaciones de consistencia y conflictos.
- E-E-A-T y mecanismos de verificación de evidencia cuando formen parte de esa ejecución.
- `query_builder.py` y operadores de búsqueda (por ejemplo `site:` o `intitle:`) solo cuando el recorrido real los utilice.
- NexusRouter y MotorRazonamientoSuperior, si sus llamadas y dependencias se confirman en el flujo actual.
- EPSILON-WALL — límite epistemológico.
- SOVEREIGN-GATE — soberanía/validación de modificaciones o ingestiones protegidas, de acuerdo con su contrato real.

No dibujar un DAG como si fuera el flujo real si no se dispone de esa información. Diferenciar claramente:

1. **Grafo estático o arquitectura conceptual**: componentes conocidos y relaciones documentadas.
2. **Traza de ejecución real**: etapas, orden, tiempos y estados recibidos del backend para una ejecución concreta.

Colores/estados sugeridos: pendiente, activo, completado, advertencia, fallido/bloqueado; cada uno acompañado por texto. Mostrar dependencias y detalles de un nodo al seleccionarlo si la arquitectura lo permite.

### 7.5 Telemetría

Incluir tarjetas compactas para métricas que el sistema proporcione realmente, por ejemplo:

- Latencia de la ejecución.
- Número de subtareas/nodos procesados.
- Presupuesto/uso de tokens, si se conoce.
- Validaciones, fuentes o eventos procesados, cuando estén disponibles.

Condiciones obligatorias:

- No crear números verosímiles sin medición real.
- Si no hay valor, indicar `—`, `No disponible` o `No emitido por el backend`.
- Distinguir tiempo del backend, tiempo de red y tiempo de UI si el sistema los mide por separado.
- No sumar ni comparar magnitudes incompatibles.
- No mostrar un indicador `100 % seguro` o semejante; una validación puntual no demuestra seguridad absoluta.

### 7.6 Eventos y traza operativa

- Mostrar un registro cronológico de los eventos relevantes recibidos del backend: entrada, ruta seleccionada, trigger invocado, comienzo/fin de etapa, validación, advertencia, autorización, bloqueo o error.
- Cada entrada debe tener sello temporal si está disponible, nivel/severidad, componente/origen y descripción legible.
- Incluir identificadores de correlación de tarea o ejecución cuando el backend los produzca.
- Diferenciar claramente eventos reales de mensajes de debug locales.
- No exponer secretos, datos privados, payloads completos sensibles o información interna no destinada al usuario.
- Permitir filtrar eventos por severidad/componente si el volumen lo justifica.
- Mantener la traza legible, desplazable y acotada; evitar que crezca sin límite en memoria.

### 7.7 Perímetro de seguridad

Representar como áreas diferenciadas los controles que existan en el proyecto:

- NEXUS-ROOT.
- EPSILON-WALL.
- SOVEREIGN-GATE.

Mostrar el estado derivado de validaciones reales o un estado explícito `Sin dato` si no hay telemetría. No convertirlos en badges siempre verdes sin conexión a los controles.

Principios que no se pueden vulnerar:

- Cambiar entre Chat Autónomo y Motor Técnico no modifica la política de seguridad.
- El modo automático no omite las validaciones necesarias ni concede privilegios adicionales.
- Ningún selector de UI puede saltarse las validaciones del backend.
- La interfaz debe respetar el bloqueo y la memoria de bloqueo ya definidos por el proyecto, si continúan vigentes en el código actual.
- Los cambios de identidad, código, parámetros o conocimiento protegido siguen la puerta de autorización soberana existente.

---

## 8. Relación entre los dos paneles

- Compartir identidad de sesión cuando el sistema ya tenga ese concepto, sin inventar una falsa sincronización.
- Si se selecciona un mensaje del chat y existe una traza correlacionada, ofrecer un vínculo `Ver ejecución técnica` que lleve al registro correcto.
- Si no hay una correlación real, no asociar una conversación con un DAG arbitrario.
- Si una ejecución técnica genera un resultado conversacional, distinguir la salida del agente de los metadatos técnicos.
- Los paneles no deben competir por los mismos controles ni realizar dos envíos al mismo tiempo por una única acción.
- Un error técnico debe reflejarse en el chat si afecta esa respuesta, pero sin revelar detalles internos sensibles.

---

## 9. Estados globales y feedback

Implementar mensajes de estado accesibles y consistentes para:

- Disponible/listo.
- Procesando.
- Verificando.
- Requiere autorización.
- Advertencia.
- Bloqueado.
- Completado.
- Fallido.
- Audio escuchando/reproduciendo/detenido/no disponible.
- Backend desconectado o con error, si es posible comprobarlo.

No proclamar `Listo`, `Conectado`, `Seguro` o `Completado` si no existe una señal real que lo respalde. Un estado desconocido debe expresarse como desconocido.

Los mensajes temporales pueden usarse para feedback de acciones de bajo riesgo; los errores y bloqueos deben permanecer visibles el tiempo suficiente y ofrecer una acción útil cuando sea posible.

---

## 10. Accesibilidad, robustez y rendimiento

- Controles operables por teclado, foco claramente visible y etiquetas accesibles.
- Contraste suficiente con la paleta oscura.
- Estados no comunicados solo por color.
- Botones con nombres accesibles aunque visualmente solo muestren un icono.
- Deshabilitar y proteger contra doble envío mientras la petición correspondiente se procesa.
- Errores manejados sin romper toda la interfaz.
- No bloquear el hilo principal con operaciones largas.
- Evitar polling agresivo, reruns innecesarios y refrescos que borren el historial.
- Limitar el historial visible de eventos o aplicar paginación/ventana móvil si es necesario.
- Sanitizar y renderizar texto de usuario y respuestas de forma segura; no ejecutar HTML/JavaScript incluido en mensajes.
- Mantener el comportamiento correcto en las resoluciones habituales del proyecto y comprobar el caso de viewport estrecho.

---

## 11. Plan de implementación obligatorio

Ejecutá el trabajo por etapas, pero completá la mayor parte posible en esta misma tarea. No te limites a responder con un plan.

### Etapa A — Auditoría rápida

- Mapear el frontend, el backend, el estado de sesión, los triggers y las políticas de confianza.
- Identificar componentes reutilizables y pruebas existentes.
- Definir cuáles de las capacidades solicitadas ya están disponibles y cuáles requieren trabajo adicional.

### Etapa B — Estructura visual

- Crear/ajustar el encabezado HPR.
- Implementar la disposición de dos paneles, técnico a la izquierda y chat a la derecha.
- Establecer los tokens de color, espaciado, tipografía, estados y comportamiento responsivo.
- Verificar que el cambio no afecte la carga del motor ni sus rutas.

### Etapa C — Chat real

- Conectar el compositor y el historial al pipeline conversacional existente.
- Implementar acciones por mensaje, estados de carga/error y gestión de sesión.
- Integrar entrada y salida de audio respetando el stack y los servicios disponibles.
- Retirar o aislar las respuestas de demo para evitar que se confundan con las respuestas reales.

### Etapa D — Motor Técnico real

- Conectar el selector al registro real de triggers.
- Mostrar los niveles de confianza que exponga la política implementada.
- Conectar ejecución y permisos a las operaciones actuales.
- Renderizar el pipeline y los eventos con los datos reales disponibles; distinguir la arquitectura conceptual de la traza de ejecución.
- Añadir telemetría solo para las métricas que el backend produce.

### Etapa E — Integración, accesibilidad y validación

- Verificar la relación entre la sesión del chat y la traza técnica.
- Probar audio disponible y no disponible, errores y permisos denegados.
- Revisar el diseño en pantalla amplia y estrecha.
- Ejecutar las pruebas existentes y las nuevas pruebas relevantes.
- Resolver regresiones causadas por los cambios antes de finalizar.

---

## 12. Pruebas y criterios de aceptación

La tarea no se considera completa solo porque la pantalla tenga buen aspecto. Validá visual y funcionalmente los siguientes puntos.

### UI y distribución

- [ ] En escritorio, Motor Técnico está a la izquierda y Chat Autónomo a la derecha.
- [ ] La identidad HPR, el tema oscuro y los colores se acercan claramente a los tokens de la demo.
- [ ] Ambos paneles tienen jerarquía visual clara, scroll controlado y no se superponen.
- [ ] En pantalla estrecha se puede acceder a ambos paneles sin perder funciones.

### Chat

- [ ] Enviar por botón funciona con el servicio real.
- [ ] Enter/Shift+Enter se comportan como se especifica.
- [ ] Historial y estado de sesión sobreviven los reruns previstos por el framework.
- [ ] Nueva conversación y limpiar historial actúan de forma predecible.
- [ ] Copiar respuesta funciona o muestra fallback accesible.
- [ ] Regenerar/reintentar solo aparece si existe soporte real.
- [ ] Los errores del backend se muestran de manera comprensible sin exponer secretos.
- [ ] No hay respuestas de prueba mezcladas silenciosamente con respuestas reales.

### Audio

- [ ] El micrófono no se activa automáticamente.
- [ ] Dictado, detención, transcripción editable y envío se comportan correctamente en navegadores compatibles.
- [ ] Denegar el permiso o carecer de API no inutiliza el chat escrito.
- [ ] Una respuesta se puede escuchar y detener.
- [ ] La opción de lectura automática, si se incorpora, se puede activar/desactivar.
- [ ] No se superponen varias reproducciones.

### Motor Técnico y seguridad

- [ ] Los triggers proceden de la fuente real de verdad del proyecto.
- [ ] Los niveles de confianza corresponden a los niveles implementados, sin semánticas inventadas.
- [ ] Seleccionar un trigger no equivale a autorizarlo.
- [ ] Los estados de nodos y las trazas reflejan datos reales o declaran su ausencia.
- [ ] Las métricas sin fuente real se muestran como no disponibles, nunca como valores simulados.
- [ ] Cambiar de pestaña no elude NEXUS-ROOT, EPSILON-WALL, SOVEREIGN-GATE ni las demás políticas vigentes.
- [ ] Se conserva el bloqueo y las autorizaciones del backend.

### Calidad y regresiones

- [ ] Ejecutar la suite de pruebas existente y las nuevas pruebas relacionadas.
- [ ] Si `test_nexus_ui.py` existe, ejecutarlo y verificar las 20 pruebas referenciadas en el historial o informar si el estado actual difiere.
- [ ] Ejecutar tests del pipeline, controles de acceso, contratos Pydantic y rutas de backend que correspondan.
- [ ] Corregir linter/formateador si forman parte del flujo existente.
- [ ] No afirmar que una prueba pasó si no se ejecutó o si falló.

---

## 13. Entregables al finalizar

Cuando termines, entregá un resumen en español con:

1. Archivos creados o modificados y propósito de cada uno.
2. Qué se conectó al backend real y qué sigue siendo una capacidad pendiente.
3. Cómo se implementó entrada/salida de audio y las limitaciones de compatibilidad encontradas.
4. Qué triggers y niveles reales quedaron visibles y de qué fuente se obtienen.
5. Pruebas ejecutadas y resultado exacto; listar explícitamente las que no se pudieron correr.
6. Riesgos, deuda técnica y próximos pasos concretos.
7. Instrucciones exactas para ejecutar la aplicación y abrir/previsualizar la interfaz.

No declares victoria basándote solo en que el servidor inicia o la pantalla renderiza.

---

## 14. Instrucción final de calidad

La experiencia final debe combinar **la claridad conversacional de un chat LLM moderno** con **la densidad informativa de una consola profesional de ingeniería**, usando la paleta azul noche/cian de la demo como referencia. El panel técnico tiene que reflejar el peso arquitectónico real de HPR; el chat debe sentirse completo y cómodo, incluyendo audio de entrada y salida; y la seguridad debe mantenerse como una propiedad del motor, no como decoración visual.

**Primero verificá el código. Después implementá. Conectá la UI a las capacidades reales. Probá. Documentá con honestidad qué funciona y qué no. No reemplaces ingeniería real por una simulación visual.**
