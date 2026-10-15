/* ==========================================================================
 * Motor HPR — Interfaz Dual · app.js
 * Etapa C: conexión real del chat (POST /api/v1/chat) y gestión de audio.
 * Motor técnico real (triggers, telemetría, traza): Etapa D.
 *
 * Reglas de operación (Constitución HPR):
 * - Sin datos simulados: toda acción que dependa del backend informa su
 *   estado real. La autoridad y las validaciones residen en el backend
 *   (NEXUS-ROOT · EPSILON-WALL · SOVEREIGN-GATE).
 * - Ejecución 100% local (S1, S2, E1, E2, E5): este archivo solo contacta
 *   al backend local (127.0.0.1). Excepción divulgada: la captación por
 *   micrófono usa el motor de voz del navegador, que en Chromium/Edge
 *   transita por el servicio del proveedor (activación explícita del
 *   usuario). La síntesis de voz es 100% local (speechSynthesis).
 * ========================================================================== */
'use strict';

/* ------------------------- Utilidades ------------------------- */
const $ = (id) => document.getElementById(id);

function stamp() {
  return new Date().toLocaleTimeString('es-UY', {
    hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
}

let toastTimer = null;
function showToast(message) {
  const t = $('toast');
  if (!t) return;
  t.textContent = message;
  t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), 3200);
}

function addEvent(code, message, kind = 'normal') {
  const log = $('events');
  if (!log) return;
  const row = document.createElement('div');
  row.className = 'event';
  const time = document.createElement('span');
  time.className = 'event-time';
  time.textContent = stamp();
  const mark = document.createElement('i');
  mark.className = 'event-mark' +
    (kind === 'good' ? ' good' : kind === 'warn' ? ' warn' : '');
  const txt = document.createElement('div');
  txt.className = 'event-text';
  const b = document.createElement('b');
  b.textContent = code;
  txt.append(b, document.createTextNode(' · ' + message));
  row.append(time, mark, txt);
  log.prepend(row);
  // Traza acotada en memoria (§10): ventana móvil de eventos.
  const MAX_EVENTS = 200;
  while (log.children.length > MAX_EVENTS) {
    log.removeChild(log.lastChild);
  }
}

/* ------------- Estado real del backend (sonda local, E1) ------------- */
let backendOnline = null; // null = aún no sondeado

async function probeBackend() {
  const sysstate = document.querySelector('.sysstate');
  const ctrl = new AbortController();
  const timeout = setTimeout(() => ctrl.abort(), 2000);
  const started = performance.now();
  try {
    const resp = await fetch('/', {
      method: 'GET', cache: 'no-store', signal: ctrl.signal,
    });
    const latency = Math.round(performance.now() - started);
    backendOnline = resp.ok;
    if (backendOnline && sysstate) {
      sysstate.innerHTML = '<i class="dot"></i> Backend en línea · ' + latency + ' ms';
      return true;
    }
  } catch (err) {
    backendOnline = false;
  } finally {
    clearTimeout(timeout);
  }
  backendOnline = false;
  if (sysstate) {
    sysstate.innerHTML = '<i class="dot"></i> UI disponible · backend no conectado';
  }
  return false;
}

/* ------------------------- Tabs (navegación) ------------------------- */
function focusPane(which) {
  $('tab-tech').classList.toggle('active', which === 'tech');
  $('tab-chat').classList.toggle('active', which === 'chat');
  if (window.innerWidth <= 1080) {
    $(which === 'tech' ? 'tech-pane' : 'chat-pane')
      .scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}
$('tab-tech').addEventListener('click', () => focusPane('tech'));
$('tab-chat').addEventListener('click', () => focusPane('chat'));

/* ------------------- Niveles de confianza (solo UI) -------------------
 * La autorización real la define y valida el backend (NEXUS-ROOT /
 * SOVEREIGN-GATE). Este selector no concede privilegios (D4).          */
const levelNotes = {
  1: 'Consulta y acciones permitidas por la política de Nivel 1.',
  2: 'Controles reforzados representados en UI; los permisos reales los valida el backend.',
  3: 'Las operaciones restringidas requieren autorización real del backend. Esta interfaz no concede privilegios.',
};

function confidenceChanged() {
  const level = +$('confidence').value;
  $('confidence-note').textContent = levelNotes[level];
  document.querySelectorAll('.level').forEach((el) => {
    el.classList.toggle('selected', +el.dataset.level === level);
  });
  addEvent(
    'CONFIDENCE_UI',
    'Nivel ' + level + ' seleccionado en la interfaz; la autorización real reside en el backend.',
    level === 3 ? 'warn' : 'normal',
  );
}

function setLevel(level) {
  $('confidence').value = String(level);
  confidenceChanged();
}
$('confidence').addEventListener('change', confidenceChanged);
document.querySelectorAll('.level').forEach((el) => {
  el.addEventListener('click', () => setLevel(+el.dataset.level));
});

/* ------------------- Triggers (selección; ejecución: Etapa D) ------------------- */
const triggerDescriptions = {
  '@hpr_confianza': 'Consulta de estado y reglas del perímetro de confianza. Ejecución real con el backend.',
  '@nivel1': 'Solicita el perfil de interacción asociado a Nivel 1. Ejecución real con el backend.',
  '@web_search': 'Búsqueda web: el backend informa si está configurado (sin simulación).',
  'N1 · Búsqueda Cognitiva': 'Recuperación semántica sobre la sesión actual. Ejecución real con el backend.',
  'N2 · Grafo de Consistencia': 'Inspección de relaciones y detección de conflictos. Ejecución real con el backend.',
  'MotorRazonamientoSuperior': 'Síntesis y discernimiento de la sesión. Ejecución real con el backend.',
  'SOVEREIGN-GATE': 'Control de soberanía: requiere autorización explícita del backend (rechazado sin nivel 3 + permiso).',
};

function triggerChanged() {
  const trigger = $('trigger').value;
  $('trigger-note').textContent = triggerDescriptions[trigger] || 'Trigger seleccionado.';
  addEvent('TRIGGER_SELECTED', trigger + ' seleccionado; la ejecución real llega con la Etapa D.', 'normal');
}
$('trigger').addEventListener('change', triggerChanged);

/* ------------------------- Etapa D · Ejecución real de triggers -------------------------
 * Conexión real con POST /api/v1/trigger. Flujo:
 * 1. Validación local de parámetros
 * 2. Envío al backend con sesión y nivel de confianza
 * 3. Renderizado de resultado y telemetría en el panel técnico
 * 4. Manejo de estados: ejecutando → completado/error
 * 5. Actualización de la traza operativa con eventos reales          */
let triggerBusy = false;

async function executeTrigger() {
  if (triggerBusy) return; // protección contra doble ejecución
  const trigger = $('trigger').value;
  const level = +$('confidence').value;
  const btn = $('execute-trigger');
  
  addEvent('TRIGGER_EXEC', 'Ejecutando trigger real: ' + trigger + ' · Nivel ' + level, 'normal');
  
  // Estado de ejecución
  triggerBusy = true;
  btn.disabled = true;
  btn.innerHTML = '<svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="m8 5 12 7-12 7z"/></svg> Ejecutando…';
  
  try {
    const resp = await fetch('/api/v1/trigger', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        trigger: trigger,
        confidence_level: level,
        session_id: sessionId,
      }),
      cache: 'no-store',
    });
    
    const data = await resp.json();
    
    if (data.success) {
      addEvent('TRIGGER_OK', 'Trigger ejecutado: ' + data.trigger + ' en ' + (data.execution_time_ms || 0) + ' ms', 'good');
      showToast('Trigger ejecutado correctamente.');
      
      // Actualizar sesión si el backend asignó una nueva
      if (data.session_id) {
        setSessionId(data.session_id);
      }
      
      // Actualizar telemetría en el panel técnico
      updateTelemetry(data.telemetry, data.result);
      
      // Actualizar traza con el resultado
      if (data.result) {
        const resultSummary = Object.entries(data.result)
          .slice(0, 3)
          .map(([k, v]) => k + ': ' + (typeof v === 'object' ? JSON.stringify(v).slice(0, 50) : v))
          .join(' · ');
        addEvent('TRIGGER_RESULT', resultSummary, 'normal');
      }
    } else {
      addEvent('TRIGGER_ERROR', data.error_message || 'Error desconocido', 'warn');
      showToast(data.error_message || 'Error en la ejecución.');
      
      // Limpiar telemetría en caso de error
      clearTelemetry();
    }
  } catch (err) {
    const msg = err.name === 'AbortError'
      ? 'Tiempo de espera agotado: el backend no respondió.'
      : 'No se pudo conectar con el backend local. Verificá que el servidor esté corriendo (run.py).';
    addEvent('TRIGGER_TRANSPORT', msg, 'warn');
    showToast(msg);
    clearTelemetry();
  } finally {
    triggerBusy = false;
    btn.disabled = false;
    btn.innerHTML = '<svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="m8 5 12 7-12 7z"/></svg> Ejecutar trigger';
  }
}
$('execute-trigger').addEventListener('click', executeTrigger);

/* ------------------------- Etapa D · Telemetría en tiempo real -------------------------
 * Actualiza el panel técnico con métricas reales del backend.        */
function updateTelemetry(telemetry, result) {
  if (!telemetry) return;
  
  // Latencia
  const latencyEl = $('latency');
  const latencySub = $('latency-sub');
  if (latencyEl && telemetry.execution_time_ms != null) {
    latencyEl.textContent = telemetry.execution_time_ms.toFixed(1) + ' ms';
    latencySub.textContent = 'última ejecución real';
  }
  
  // Tokens (si están disponibles en el resultado)
  const tokensEl = $('tokens');
  if (tokensEl && result && result.tokens_used != null) {
    tokensEl.textContent = String(result.tokens_used);
  }
  
  // Subtareas (si están disponibles)
  const subtasksEl = $('subtasks');
  if (subtasksEl && result && result.subtasks_executed != null) {
    subtasksEl.textContent = String(result.subtasks_executed);
  }
  
  // Validaciones (nivel de confianza + estado)
  const validationsEl = $('validations');
  if (validationsEl && telemetry.confidence_level != null) {
    const level = telemetry.confidence_level;
    validationsEl.textContent = level + '/3';
    validationsEl.style.color = level === 3 ? 'var(--amber)' : 'var(--green)';
  }
}

function clearTelemetry() {
  const latencyEl = $('latency');
  const latencySub = $('latency-sub');
  const tokensEl = $('tokens');
  const subtasksEl = $('subtasks');
  const validationsEl = $('validations');
  
  if (latencyEl) latencyEl.textContent = '—';
  if (latencySub) latencySub.textContent = 'sin ejecución real';
  if (tokensEl) tokensEl.textContent = '—';
  if (subtasksEl) subtasksEl.textContent = '0';
  if (validationsEl) {
    validationsEl.textContent = '0/3';
    validationsEl.style.color = '';
  }
}

/* ------------------------- Refresco y traza ------------------------- */
async function refreshTech() {
  addEvent('UI_REFRESH', 'Panel técnico actualizado; sondeando backend local…', 'normal');
  const online = await probeBackend();
  addEvent(
    online ? 'BACKEND_ONLINE' : 'BACKEND_OFFLINE',
    online
      ? 'Backend local responde; telemetría real disponible desde la Etapa D.'
      : 'Backend no conectado. Iniciá el servidor (run.py) para la conexión real.',
    online ? 'good' : 'warn',
  );
}
$('refresh-tech').addEventListener('click', refreshTech);

function clearEvents() {
  $('events').innerHTML = '';
  addEvent('TRACE_CLEARED', 'Vista de eventos limpiada localmente.', 'normal');
}
$('clear-events').addEventListener('click', clearEvents);

/* ------------------------- Cliente API · canal autónomo -------------------------
 * Contrato real del backend (HPR/src/main.py):
 *   POST /api/v1/chat  {session_id?, message, use_voice, language}
 * El texto viaja además como parámetro ?query= para que el guardia
 * de seguridad del endpoint (verify_security_guard) lo inspeccione:
 * una coincidencia con patrones de phishing recibe 403 visible.
 * El payload replica al HPRClient probado (dual_interface.py).
 * ------------------------------------------------------------------------- */
const CHAT_TIMEOUT_MS = 20000;

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function apiChat({ message, sessionId, useVoice, language = 'es' }) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), CHAT_TIMEOUT_MS);
  const started = performance.now();
  try {
    // ?query= activa el guardia anti-phishing del endpoint (contrato existente).
    const url = '/api/v1/chat?query=' + encodeURIComponent(message);
    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        use_voice: !!useVoice,
        language,
        ...(sessionId ? { session_id: sessionId } : {}),
      }),
      signal: controller.signal,
      cache: 'no-store',
    });
    const latency = Math.round(performance.now() - started);
    if (!resp.ok) {
      let detail = 'HTTP ' + resp.status;
      try {
        const err = await resp.json();
        if (err && err.detail) detail = String(err.detail);
      } catch (_) { /* sin detalle legible */ }
      throw new ApiError(detail, resp.status);
    }
    return { data: await resp.json(), latency };
  } finally {
    clearTimeout(timer);
  }
}

/* ------------------------- Sesión y estado del chat -------------------------
 * sessionId: null → el próximo envío crea una sesión nueva en el
 * backend (creación lazy, igual que el HPRClient). chatBusy protege
 * contra doble envío (§10). voiceOrigin marca use_voice=true cuando
 * el texto proviene de dictado.                                    */
let sessionId = null;
let chatBusy = false;
let voiceOrigin = false;
let programmaticEdit = false;
let attachedFiles = [];

function setSessionId(id) {
  sessionId = id || null;
  const pill = $('session-id');
  if (pill) pill.textContent = sessionId ? sessionId.slice(0, 8) : 'sin sesión';
}

function setSendEnabled(enabled) {
  const btn = $('send-button');
  if (btn) btn.disabled = !enabled;
}

function setComposerText(text) {
  programmaticEdit = true;
  $('prompt').value = text;
  programmaticEdit = false;
  autoResize();
}

/* ------------------------- Renderizado de mensajes ------------------------- */
function appendMessage(role, text, options = {}) {
  const messages = $('messages');
  const msg = document.createElement('div');
  msg.className = 'message ' + role +
    (options.pending ? ' pending' : '') +
    (options.error ? ' error' : '');
  msg.dataset.role = role;
  const av = document.createElement('div');
  av.className = 'avatar';
  av.textContent = role === 'assistant' ? 'HPR' : 'DR';
  const main = document.createElement('div');
  main.className = 'message-main';
  const meta = document.createElement('div');
  meta.className = 'message-meta';
  const name = document.createElement('strong');
  name.textContent = role === 'assistant' ? 'HPR · Asistente' : 'Vos';
  meta.appendChild(name);
  const time = document.createElement('span');
  time.textContent = options.label || stamp();
  meta.appendChild(time);
  if (options.turnLabel) {
    const turn = document.createElement('span');
    turn.className = 'turn-tag';
    turn.textContent = options.turnLabel;
    meta.appendChild(turn);
  }
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.textContent = text; // textContent: sanitización (§10)
  main.append(meta, bubble);
  if (role === 'assistant') {
    const actions = document.createElement('div');
    actions.className = 'message-actions';
    const listen = document.createElement('button');
    listen.type = 'button';
    listen.className = 'response-audio';
    listen.textContent = '▶ Escuchar';
    listen.title = 'Leer esta respuesta con la voz local del navegador (speechSynthesis)';
    listen.addEventListener('click', () => {
      if (HPRVoice.speak(bubble.textContent)) {
        addEvent('TTS_PLAY', 'Lectura de respuesta iniciada (voz local del navegador).', 'normal');
      } else {
        showToast('Síntesis de voz no disponible en este navegador.');
        addEvent('TTS_UNAVAILABLE', 'speechSynthesis no disponible; la lectura queda deshabilitada.', 'warn');
      }
    });
    const copy = document.createElement('button');
    copy.type = 'button';
    copy.textContent = '▢ Copiar';
    copy.title = 'Copiar el texto de esta respuesta';
    copy.addEventListener('click', () => copyText(bubble.textContent));
    actions.append(listen, copy);
    main.append(actions);
  }
  msg.append(av, main);
  messages.append(msg);
  messages.scrollTop = messages.scrollHeight;
  return msg;
}

/* Actualiza un mensaje existente (pendiente → respuesta real o error). */
function updateMessage(msgEl, text, options = {}) {
  if (!msgEl) return;
  msgEl.classList.toggle('pending', !!options.pending);
  msgEl.classList.toggle('error', !!options.error);
  const bubble = msgEl.querySelector('.bubble');
  if (bubble) bubble.textContent = text;
  const meta = msgEl.querySelector('.message-meta');
  if (meta && options.turnLabel) {
    const prev = meta.querySelector('.turn-tag');
    if (prev) prev.remove();
    const turn = document.createElement('span');
    turn.className = 'turn-tag';
    turn.textContent = options.turnLabel;
    meta.appendChild(turn);
  }
  if (options.onRetry) {
    const actions = msgEl.querySelector('.message-actions');
    if (actions && !actions.querySelector('.retry')) {
      const retry = document.createElement('button');
      retry.type = 'button';
      retry.className = 'retry';
      retry.textContent = '↻ Reintentar';
      retry.title = 'Reenviar este mensaje al backend local';
      retry.addEventListener('click', options.onRetry);
      actions.appendChild(retry);
    }
  }
}

/* Envío real al backend. Flujo: eco de la entrada → petición
 * POST /api/v1/chat → renderizado de la respuesta real.        */
async function sendMessage() {
  if (chatBusy) return; // protección contra doble envío (§10)
  const box = $('prompt');
  const text = box.value.trim();
  if (!text && !attachedFiles.length) return;
  if (!text && attachedFiles.length) {
    showToast('Adjuntos detectados: el backend no consume archivos. Escribí una instrucción para continuar.');
    return;
  }
  chatBusy = true;
  setSendEnabled(false);
  const useVoice = voiceOrigin;
  voiceOrigin = false;
  const names = attachedFiles.slice();
  attachedFiles = [];
  $('file-input').value = '';
  $('file-chip').classList.remove('show');
  $('file-chip').textContent = '';
  appendMessage('user', text, {
    label: useVoice ? 'dictado · ' + stamp() : undefined,
  });
  box.value = '';
  box.style.height = 'auto';
  if (names.length) {
    addEvent('ATTACHMENT_UI', names.length + ' archivo(s) adjuntos; el backend no los procesa (no soportado).', 'warn');
  }
  const pending = appendMessage(
    'assistant',
    'Solicitando respuesta al motor local…',
    { label: 'Procesando…', pending: true },
  );
  addEvent(
    'CHAT_SEND',
    'Enviado a POST /api/v1/chat (' + text.length + ' caracteres' +
      (useVoice ? ', origen: dictado' : '') + ').',
    'normal',
  );
  try {
    const { data, latency } = await apiChat({ message: text, sessionId, useVoice });
    setSessionId(data.session_id);
    const turnNo = data.metadata && data.metadata.turn_number != null
      ? 'turno ' + data.metadata.turn_number
      : '';
    const turnId = data.turn_id ? ' · ' + String(data.turn_id).slice(0, 8) : '';
    const turnLabel = (turnNo + turnId).trim() || undefined;
    updateMessage(
      pending,
      data.response || '(el motor respondió sin contenido)',
      { turnLabel },
    );
    addEvent(
      'CHAT_RESPONSE',
      'Respuesta real recibida en ' + latency + ' ms (' + (turnNo || 'sin n.º de turno') + ').',
      'good',
    );
    if (data.response && $('autoplay') && $('autoplay').checked) {
      if (HPRVoice.speak(data.response)) {
        addEvent('TTS_PLAY', 'Lectura automática de la respuesta (voz local del navegador).', 'normal');
      }
    }
  } catch (err) {
    const isTransport = !(err instanceof ApiError); // abort / red: no se creó turno
    let userText;
    let eventCode;
    if (err && err.name === 'AbortError') {
      userText = 'Tiempo de espera agotado (' + (CHAT_TIMEOUT_MS / 1000) +
        ' s): el backend no respondió. Verificá que el servidor esté corriendo (run.py).';
      eventCode = 'CHAT_TIMEOUT';
    } else if (err instanceof ApiError && err.status === 403) {
      userText = 'Bloqueo de seguridad del motor: ' + err.message;
      eventCode = 'SECURITY_BLOCK';
    } else if (err instanceof ApiError && err.status === 404) {
      setSessionId(null); // la sesión ya no existe: próximo envío crea una nueva
      userText = 'La sesión ya no existe en el backend (¿fue archivada?); el próximo envío creará una sesión nueva. (' + err.message + ')';
      eventCode = 'SESSION_EXPIRED';
    } else if (err instanceof ApiError && err.status === 422) {
      userText = 'El mensaje no cumple el contrato del backend (1–8000 caracteres).';
      eventCode = 'CHAT_CONTRACT';
    } else if (err instanceof ApiError) {
      userText = 'Error del backend (' + err.status + '): ' + err.message;
      eventCode = 'CHAT_ERROR';
    } else {
      userText = 'No se pudo conectar con el backend local. Verificá que el servidor esté corriendo (run.py).';
      eventCode = 'BACKEND_OFFLINE';
      probeBackend();
    }
    updateMessage(pending, userText, {
      error: true,
      onRetry: isTransport ? () => { box.value = text; sendMessage(); } : null,
    });
    addEvent(eventCode, userText, 'warn');
    showToast(eventCode === 'SECURITY_BLOCK'
      ? 'Petición bloqueada por el guardia de seguridad.'
      : 'Error de comunicación con el backend local.');
  } finally {
    chatBusy = false;
    setSendEnabled(true);
    box.focus();
  }
}
$('send-button').addEventListener('click', sendMessage);

function clearChatView() {
  $('messages').innerHTML = '';
}

function clearChat() {
  if (!confirm('¿Limpiar la conversación? Se elimina el historial de esta vista (local).')) return;
  clearChatView();
  addEvent('CHAT_CLEARED', 'Vista de conversación limpiada localmente; la sesión del backend se conserva.', 'normal');
  showToast('Conversación limpiada (vista local).');
}
$('clear-chat').addEventListener('click', clearChat);

function newChat() {
  setSessionId(null); // el próximo envío crea una sesión nueva en el backend
  clearChatView();
  addEvent('SESSION_NEW', 'Nueva conversación: el próximo envío creará una sesión nueva en el backend.', 'normal');
  showToast('Nuevo chat: el próximo mensaje crea una sesión nueva.');
}
$('new-chat').addEventListener('click', newChat);

/* ------------------------- Portapapeles (local) ------------------------- */
function copyText(text) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text)
      .then(() => showToast('Respuesta copiada.'))
      .catch(() => fallbackCopy(text));
  } else {
    fallbackCopy(text);
  }
}

function fallbackCopy(text) {
  const ta = document.createElement('textarea');
  ta.value = text;
  document.body.append(ta);
  ta.select();
  try {
    document.execCommand('copy');
    showToast('Texto copiado.');
  } catch (e) {
    showToast('No se pudo copiar automáticamente; seleccioná el texto manualmente.');
  }
  ta.remove();
}

function copyMessage(button) {
  const main = button.closest('.message-main');
  const bubble = main ? main.querySelector('.bubble') : null;
  if (bubble) copyText(bubble.innerText);
}
$('welcome-copy').addEventListener('click', (e) => copyMessage(e.currentTarget));
$('welcome-listen').addEventListener('click', () => {
  const main = $('welcome-listen').closest('.message-main');
  const bubble = main ? main.querySelector('.bubble') : null;
  const text = bubble ? bubble.textContent : '';
  if (text && HPRVoice.speak(text)) {
    addEvent('TTS_PLAY', 'Lectura del mensaje de bienvenida (voz local del navegador).', 'normal');
  } else {
    showToast('Síntesis de voz no disponible en este navegador.');
    addEvent('TTS_UNAVAILABLE', 'speechSynthesis no disponible; la lectura queda deshabilitada.', 'warn');
  }
});

/* ------------------------- Audio de salida: speechSynthesis -------------------------
 * SOBERANÍA (S2/E2/E5): la síntesis ocurre íntegramente en la
 * máquina del usuario; ningún audio se transmite a servicios
 * remotos. Las voces en español dependen del sistema
 * operativo/navegador: no se asume una voz concreta (§6.4).  */
const HPRVoice = {
  voices: [],
  speaking: false,
  init() {
    if (!('speechSynthesis' in window)) return;
    const load = () => { this.voices = speechSynthesis.getVoices() || []; };
    load();
    if (typeof speechSynthesis.onvoiceschanged !== 'undefined') {
      speechSynthesis.onvoiceschanged = load;
    }
  },
  spanishVoice() {
    const es = this.voices.filter((v) => v.lang && v.lang.toLowerCase().startsWith('es'));
    if (!es.length) return null;
    return es.find((v) => v.lang.toLowerCase().startsWith('es-uy'))
        || es.find((v) => v.lang.toLowerCase().startsWith('es-es'))
        || es[0];
  },
  speak(text, { onEnd, onError } = {}) {
    if (!('speechSynthesis' in window) || !text) return false;
    speechSynthesis.cancel(); // evita solapamiento de lecturas (§6.4)
    const utter = new SpeechSynthesisUtterance(text);
    const voice = this.spanishVoice();
    if (voice) {
      utter.voice = voice;
      utter.lang = voice.lang;
    } else {
      utter.lang = 'es-UY';
    }
    utter.onstart = () => { this.speaking = true; updateAudioState(); };
    utter.onend = () => { this.speaking = false; updateAudioState(); if (onEnd) onEnd(); };
    utter.onerror = (e) => {
      this.speaking = false;
      updateAudioState();
      addEvent('TTS_ERROR', 'La síntesis de voz informó un error (' + (e.error || 'desconocido') + ').', 'warn');
      if (onError) onError(e.error);
    };
    utter.onpause = () => { try { speechSynthesis.resume(); } catch (_) { /* sin cola activa */ } };
    speechSynthesis.speak(utter);
    return true;
  },
  stop() {
    if (!('speechSynthesis' in window)) return;
    speechSynthesis.cancel();
    this.speaking = false;
    updateAudioState();
  },
};

/* Estado de audio: botón Detener y píldora de capacidad con
 * divulgación honesta de dónde se procesa cada canal.       */
function refreshVoicePill() {
  const pill = $('voice-support');
  if (!pill) return;
  const tts = 'speechSynthesis' in window;
  const sr = HPRDictation.isAvailable();
  let text;
  let title;
  if (tts) {
    text = this SpeakingPlaceholder; // reemplazado abajo
  }
  if (tts) {
    text = HPRVoice.speaking ? 'Audio: voz local · reproduciendo' : 'Audio: voz local del navegador';
    title = 'La síntesis de voz es 100% local (speechSynthesis): ningún audio sale de tu máquina.';
    if (sr) {
      text += ' · micrófono vía proveedor del navegador';
      title += ' La captación por micrófono la procesa el motor de voz del navegador y puede transitar por su proveedor (no es local).';
    }
  } else {
    text = 'Audio no compatible';
    title = 'Este navegador no ofrece síntesis de voz; el chat escrito sigue disponible.';
  }
  pill.textContent = text;
  pill.title = title;
  pill.dataset.speaking = HPRVoice.speaking ? 'true' : 'false';
}

function updateAudioState() {
  const stopBtn = $('stop-audio-button');
  if (stopBtn) {
    stopBtn.disabled = !HPRVoice.speaking;
    stopBtn.setAttribute('aria-disabled', String(!HPRVoice.speaking));
    stopBtn.title = HPRVoice.speaking
      ? 'Detener la lectura de voz en curso'
      : 'No hay reproducción de audio en curso';
  }
  refreshVoicePill();
}

$('stop-audio-button').addEventListener('click', () => {
  if (HPRVoice.speaking) {
    HPRVoice.stop();
    addEvent('TTS_STOP', 'Lectura de voz detenida por el usuario.', 'normal');
  }
});

/* ------------------------- Audio de entrada: micrófono -------------------------
 * DIVULGACIÓN DE SOBERANÍA: la captación usa el Web Speech API
 * del navegador. La implementación de Chromium/Edge transita
 * por el servicio de voz del proveedor (NO es procesamiento
 * local). Se activa solo por acción explícita del usuario —
 * nunca al cargar la página (§6.4)— y el chat escrito sigue
 * siendo el canal primario y totalmente funcional sin él.   */
const HPRDictation = {
  recognition: null,
  listening: false,
  baseText: '',
  isAvailable() {
    return !!(window.SpeechRecognition || window.webkitSpeechRecognition);
  },
  start() {
    if (this.listening) return;
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
      showToast('Reconocimiento de voz no disponible en este navegador. El chat escrito sigue disponible.');
      addEvent('MIC_UNAVAILABLE', 'SpeechRecognition no soportado; la captura de texto manual sigue disponible.', 'warn');
      return;
    }
    this.baseText = $('prompt').value.trim();
    const rec = new SR();
    rec.lang = 'es-UY'; // preferencia es-UY (§6.4); el navegador informa si no la soporta
    rec.interimResults = true;
    rec.continuous = false;
    rec.maxAlternatives = 1;
    rec.onstart = () => {
      this.listening = true;
      updateMicUI();
      addEvent('MIC_START', 'Captura activa: la transcripción aparece en el compositor, es editable y nunca se envía automáticamente.', 'warn');
      showToast('Escuchando… (la captura la procesa el motor de voz del navegador)');
    };
    rec.onresult = (event) => {
      let transcript = '';
      for (let i = 0; i < event.results.length; i++) {
        transcript += event.results[i][0].transcript;
      }
      const clean = transcript.trim();
      if (!clean) return;
      // Transcripción editable en el compositor: se reconstruye
      // sobre el texto base; el usuario revisa antes de enviar.
      setComposerText(this.baseText ? this.baseText + ' ' + clean : clean);
      voiceOrigin = true; // el próximo envío marca use_voice=true
    };
    rec.onerror = (event) => {
      const reasons = {
        'not-allowed': 'Permiso de micrófono denegado. Habilitá el acceso en el navegador o seguí por texto.',
        'service-not-allowed': 'El servicio de voz del navegador no está permitido en este contexto.',
        'audio-capture': 'No se encontró un micrófono funcional.',
        'no-speech': 'No se detectó voz. Intentá de nuevo hablando con claridad.',
        'network': 'El motor de voz del navegador no pudo alcanzar su servicio (la transcripción no es local).',
        'aborted': 'Captura abortada.',
      };
      const msg = reasons[event.error] || 'Error de reconocimiento de voz (' + event.error + ').';
      showToast(msg);
      addEvent('MIC_ERROR', msg, 'warn');
    };
    rec.onend = () => {
      this.listening = false;
      updateMicUI();
    };
    this.recognition = rec;
    try {
      rec.start();
    } catch (e) {
      this.listening = false;
      updateMicUI();
      showToast('No se pudo iniciar la captura de voz: ' + e.message);
      addEvent('MIC_ERROR', 'No se pudo iniciar la captura: ' + e.message, 'warn');
    }
  },
  stop() {
    if (this.recognition && this.listening) {
      try { this.recognition.stop(); } catch (_) { /* sin captura activa */ }
    }
    this.listening = false;
    updateMicUI();
  },
  toggle() {
    if (this.listening) this.stop(); else this.start();
  },
};

function updateMicUI() {
  const mic = $('mic-button');
  if (!mic) return;
  mic.classList.toggle('recording', HPRDictation.listening);
  mic.setAttribute('aria-pressed', String(HPRDictation.listening));
  const label = $('mic-label');
  if (label) label.textContent = HPRDictation.listening ? 'Detener' : 'Hablar';
  mic.title = HPRDictation.listening
    ? 'Detener la captura de voz (la transcripción queda editable en el compositor)'
    : 'Dictar un mensaje (la captura la procesa el motor de voz del navegador; puede transitar por su proveedor)';
}

$('mic-button').addEventListener('click', () => HPRDictation.toggle());

/* ------------------------- Archivos adjuntos (UI) ------------------------- */
function filesSelected(files) {
  attachedFiles = Array.from(files).map((f) => f.name);
  if (attachedFiles.length) {
    $('file-chip').textContent = 'Adjuntos seleccionados (no procesados hasta la Etapa C): ' + attachedFiles.join(', ');
    $('file-chip').classList.add('show');
    showToast(attachedFiles.length + ' archivo(s) añadidos a la composición.');
  }
}
$('file-input').addEventListener('change', (e) => filesSelected(e.target.files));
$('attach-button').addEventListener('click', () => $('file-input').click());

/* ------------------------- Composer ------------------------- */
function autoResize() {
  const ta = $('prompt');
  ta.style.height = 'auto';
  ta.style.height = Math.min(ta.scrollHeight, 150) + 'px';
}
$('prompt').addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});
$('prompt').addEventListener('input', autoResize);

/* ------------------------- Etapa D3 · Telemetría en tiempo real -------------------------
 * Sondeo periódico del endpoint /api/v1/telemetry para mantener
 * el panel técnico actualizado con métricas reales del backend.  */
const TELEMETRY_INTERVAL_MS = 5000; // polling cada 5 segundos
let telemetryTimer = null;

async function pollTelemetry() {
  try {
    const url = '/api/v1/telemetry' + (sessionId ? '?session_id=' + encodeURIComponent(sessionId) : '');
    const resp = await fetch(url, {
      method: 'GET',
      cache: 'no-store',
    });
    if (!resp.ok) return;
    
    const data = await resp.json();
    renderTelemetry(data);
  } catch (_) {
    // Si el backend no está disponible, la telemetría se omite silenciosamente.
    // El indicador de estado (probeBackend) ya informa esta condición.
  }
}

function renderTelemetry(data) {
  if (!data || !data.telemetria) return;
  
  const t = data.telemetria;
  
  // Latencia: no hay latencia global en telemetry, usamos la última ejecución
  // (ya actualizada por updateTelemetry durante executeTrigger)
  
  // Tokens
  const tokensEl = $('tokens');
  if (tokensEl && t.total_tokens != null) {
    tokensEl.textContent = String(t.total_tokens);
  }
  
  // Subtasas/turnos
  const subtasksEl = $('subtasks');
  if (subtasksEl && t.total_turns != null) {
    subtasksEl.textContent = String(t.total_turns);
  }
  
  // Validaciones: sesiones activas como indicador de salud
  const validationsEl = $('validations');
  if (validationsEl && t.active_sessions != null) {
    validationsEl.textContent = String(t.active_sessions);
    validationsEl.style.color = t.active_sessions > 0 ? 'var(--green)' : 'var(--muted)';
  }
  
  // Estado del backend
  const sysstate = document.querySelector('.sysstate');
  if (sysstate && data.backend) {
    sysstate.innerHTML = '<i class="dot"></i> Backend en línea · ' +
      (data.componentes.nexus_root || 'activo');
  }
}

function startTelemetryPolling() {
  if (telemetryTimer) clearInterval(telemetryTimer);
  pollTelemetry(); // primera ejecución inmediata
  telemetryTimer = setInterval(pollTelemetry, TELEMETRY_INTERVAL_MS);
}

function stopTelemetryPolling() {
  if (telemetryTimer) {
    clearInterval(telemetryTimer);
    telemetryTimer = null;
  }
}

/* ------------------------- Inicialización ------------------------- */
HPRVoice.init();
refreshVoicePill();
updateMicUI();
probeBackend();
startTelemetryPolling();
