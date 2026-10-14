/* ==========================================================================
 * Motor HPR — Interfaz Dual · app.js
 * Etapa B: estructura visual base.
 * Conexión real del chat/audio: Etapa C · Motor técnico: Etapa D.
 *
 * Reglas de operación (Constitución HPR):
 * - Sin datos simulados: toda acción que dependa del backend informa su
 *   estado real. La autoridad y las validaciones residen en el backend
 *   (NEXUS-ROOT · EPSILON-WALL · SOVEREIGN-GATE).
 * - Ejecución 100% local (S1, S2, E1, E2, E5): este archivo no contacta
 *   servicios externos; la única sonda es al propio backend local.
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
  '@hpr_confianza': 'Consulta de estado y reglas del perímetro de confianza.',
  '@nivel1': 'Solicita el perfil de interacción asociado a Nivel 1.',
  '@web_search': 'Activa la intención de búsqueda web; requiere backend conectado para ejecutar una búsqueda real.',
  'N1 · Búsqueda Cognitiva': 'Recuperación semántica y puntuación de relevancia mediante embeddings.',
  'N2 · Grafo de Consistencia': 'Inspección de relaciones y detección de conflictos entre afirmaciones.',
  'MotorRazonamientoSuperior': 'Área de síntesis, evaluación y discernimiento de resultados.',
  'SOVEREIGN-GATE': 'Control de soberanía de ingestión y cambios sensibles; no concede permisos desde la UI.',
};

function triggerChanged() {
  const trigger = $('trigger').value;
  $('trigger-note').textContent = triggerDescriptions[trigger] || 'Trigger seleccionado.';
  addEvent('TRIGGER_SELECTED', trigger + ' seleccionado; la ejecución real llega con la Etapa D.', 'normal');
}
$('trigger').addEventListener('change', triggerChanged);

function executeTrigger() {
  const trigger = $('trigger').value;
  const level = +$('confidence').value;
  addEvent('TRIGGER_REQUEST', 'Solicitud de ejecución: ' + trigger + ' · Nivel ' + level + '.', 'warn');
  if (trigger === 'SOVEREIGN-GATE' || level === 3) {
    addEvent('AUTH_REQUIRED', 'Operación sensible: debe validar permisos con el backend real (Etapa D).', 'warn');
    showToast('Autorización sensible pendiente: se conectará al backend en la Etapa D.');
    return;
  }
  addEvent('BACKEND_PENDING', 'Ejecución real de triggers: conexión con el motor en la Etapa D.', 'warn');
  showToast('Ejecución real pendiente (Etapa D): ' + trigger);
}
$('execute-trigger').addEventListener('click', executeTrigger);

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

/* ------------------------- Chat (conexión real: Etapa C) ------------------------- */
let attachedFiles = [];

function appendMessage(role, text, options = {}) {
  const messages = $('messages');
  const msg = document.createElement('div');
  msg.className = 'message ' + role;
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
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.textContent = text;
  main.append(meta, bubble);
  if (role === 'assistant') {
    const actions = document.createElement('div');
    actions.className = 'message-actions';
    const listen = document.createElement('button');
    listen.className = 'response-audio';
    listen.type = 'button';
    listen.textContent = '▶ Escuchar';
    listen.addEventListener('click', () => {
      showToast('Síntesis de voz: gestión de audio en la Etapa C.');
    });
    const copy = document.createElement('button');
    copy.type = 'button';
    copy.textContent = '▢ Copiar';
    copy.addEventListener('click', () => copyText(text));
    const regen = document.createElement('button');
    regen.type = 'button';
    regen.textContent = '↻ Regenerar';
    regen.addEventListener('click', () => {
      showToast('Regenerar: requiere backend conectado (Etapa C).');
    });
    actions.append(listen, copy, regen);
    main.append(actions);
  }
  msg.append(av, main);
  messages.append(msg);
  messages.scrollTop = messages.scrollHeight;
  return msg;
}

function sendMessage() {
  const box = $('prompt');
  const text = box.value.trim();
  if (!text && !attachedFiles.length) return;
  if (!text && attachedFiles.length) {
    showToast('Adjuntos detectados: su contenido se procesa con la conexión real (Etapa C). Escribí una instrucción para continuar.');
    return;
  }
  appendMessage('user', text); // eco fiel de tu propia entrada
  box.value = '';
  box.style.height = 'auto';
  const names = attachedFiles.slice();
  if (names.length) {
    addEvent('ATTACHMENT_UI', names.length + ' archivo(s) adjuntos; contenido no procesado hasta la Etapa C.', 'warn');
    attachedFiles = [];
    $('file-input').value = '';
    $('file-chip').classList.remove('show');
    $('file-chip').textContent = '';
  }
  addEvent('CHAT_INPUT', 'Entrada conversacional registrada (' + text.length + ' caracteres); respuesta real pendiente (Etapa C).', 'warn');
  showToast('Backend no conectado: la respuesta real llega con la Etapa C.');
}
$('send-button').addEventListener('click', sendMessage);

function clearChat() {
  $('messages').innerHTML = '';
  addEvent('CHAT_CLEARED', 'Historial visual eliminado localmente.', 'normal');
  showToast('Conversación limpiada (vista local).');
}
$('clear-chat').addEventListener('click', clearChat);

function newChat() {
  clearChat();
  addEvent('SESSION_NEW', 'Sesión real con el backend: se establece en la Etapa C.', 'normal');
  showToast('Nuevo chat: la sesión real se crea con el backend (Etapa C).');
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
  showToast('Síntesis de voz: gestión de audio en la Etapa C.');
});

/* ------------------------- Audio (gestión real: Etapa C) ------------------------- */
function detectAudioSupport() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  const TTS = 'speechSynthesis' in window;
  const pill = $('voice-support');
  if (!pill) return;
  if (SR && TTS) pill.textContent = 'Audio disponible*';
  else if (SR || TTS) pill.textContent = 'Audio parcial / no compatible';
  else pill.textContent = 'Audio no compatible';
}

$('mic-button').addEventListener('click', () => {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    showToast('Reconocimiento de voz no disponible en este navegador. El chat escrito sigue disponible.');
    addEvent('MIC_UNAVAILABLE', 'SpeechRecognition no soportado; la captura de texto manual sigue disponible.', 'warn');
    return;
  }
  addEvent('MIC_PENDING', 'Captura de voz: gestión de audio en la Etapa C.', 'warn');
  showToast('Gestión de voz (micrófono): Etapa C.');
});

$('stop-audio-button').addEventListener('click', () => {
  addEvent('TTS_STOP', 'No hay reproducción activa en esta etapa.', 'normal');
  showToast('Gestión de audio de respuesta: Etapa C.');
});

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

/* ------------------------- Inicialización ------------------------- */
detectAudioSupport();
probeBackend();
