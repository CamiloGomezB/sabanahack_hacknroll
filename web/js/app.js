'use strict';

/* =============================================================================
   N Club — Access Management · Panel web

   Dos fuentes de datos con la misma interfaz (backend()):
     - Supabase (js/supabase.js): sesión real; la seguridad la aplican RLS y las funciones
       de la base de datos.
     - Demostración: filas ficticias con la misma forma que las tablas, y las mismas reglas
       (roles, vigencia de 24 h, limpieza y retención) imitadas en memoria.
   El panel solo adapta la interfaz a los permisos: nunca es la única barrera.
   ========================================================================== */

// =============================================================================
// Utilidades
// =============================================================================
const $ = (sel, ctx = document) => ctx.querySelector(sel);
const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];

function mulberry32(seed) {
  return function () {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function hashString(str) {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

// Semilla fija: los datos de demostración son los mismos en cada recarga.
const rand = mulberry32(20261024);
const pick = (arr) => arr[Math.floor(rand() * arr.length)];
const randInt = (min, max) => min + Math.floor(rand() * (max - min + 1));
const chance = (p) => rand() < p;

const MIN = 60 * 1000;
const HOUR = 60 * MIN;
const DAY = 24 * HOUR;
const NOW = Date.now();

const pad = (n, len = 3) => String(n).padStart(len, '0');
const normalize = (s) => String(s ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
const slug = (s) => normalize(s).replace(/[^a-z0-9]+/g, '.').replace(/^\.|\.$/g, '');
const toMinutes = (hhmm) => { const [h, m] = hhmm.split(':').map(Number); return h * 60 + m; };
const roundTo = (ts, step) => Math.round(ts / step) * step;
const iso = (ts) => (ts == null ? null : new Date(ts).toISOString());
const toTs = (value) => (value ? Date.parse(value) : null);
const toHHMM = (t) => (t ? String(t).slice(0, 5) : null);
const dateOnly = (ts) => { const d = new Date(ts); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };
const clone = (v) => (typeof structuredClone === 'function' ? structuredClone(v) : JSON.parse(JSON.stringify(v)));

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

const icon = (name, cls = '') => `<svg class="icon ${cls}" aria-hidden="true"><use href="#i-${name}"/></svg>`;

const dateFmt = new Intl.DateTimeFormat('es-CO', { day: '2-digit', month: 'short', year: 'numeric' });
const shortDateFmt = new Intl.DateTimeFormat('es-CO', { day: '2-digit', month: 'short' });
const timeFmt = new Intl.DateTimeFormat('es-CO', { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
const longDateFmt = new Intl.DateTimeFormat('es-CO', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });

const fmtDate = (ts) => (ts ? dateFmt.format(ts) : '—');
const fmtTime = (ts) => (ts ? timeFmt.format(ts) : '—');
const nowHHMM = () => timeFmt.format(Date.now());

function dayLabel(ts) {
  const d = new Date(ts).toDateString();
  if (d === new Date().toDateString()) return 'Hoy';
  if (d === new Date(Date.now() + DAY).toDateString()) return 'Mañana';
  if (d === new Date(Date.now() - DAY).toDateString()) return 'Ayer';
  return shortDateFmt.format(ts);
}

const fmtDateTime = (ts) => (ts ? `${dayLabel(ts)}, ${fmtTime(ts)}` : '—');

function fmtWindow(start, end) {
  if (!start || !end) return '—';
  if (new Date(start).toDateString() === new Date(end).toDateString()) {
    return `${dayLabel(start)} · ${fmtTime(start)}–${fmtTime(end)}`;
  }
  return `${fmtDateTime(start)} → ${fmtDateTime(end)}`;
}

function fmtRelative(ts) {
  if (!ts) return 'Nunca';
  const diff = Date.now() - ts;
  const abs = Math.abs(diff);
  if (abs < MIN) return diff >= 0 ? 'hace un momento' : 'en un momento';
  for (const [ms, unit] of [[DAY, 'd'], [HOUR, 'h'], [MIN, 'min']]) {
    if (abs >= ms) {
      const n = Math.floor(abs / ms);
      return diff >= 0 ? `hace ${n} ${unit}` : `en ${n} ${unit}`;
    }
  }
  return '';
}

function toLocalInput(ts) {
  const d = new Date(ts);
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
}

// Los UUID de la base se muestran abreviados.
const shortId = (id) => (/^[0-9a-f]{8}-[0-9a-f-]{27}$/i.test(id || '') ? id.slice(0, 8).toUpperCase() : (id || '—'));

// =============================================================================
// Catálogos (alineados con los enums de la base de datos)
// =============================================================================
const ZONAS = {
  lobby: 'Lobby',
  sala_vip: 'Sala VIP',
  restaurante: 'Restaurante',
  terraza: 'Terraza',
  piscina: 'Piscina',
  canchas: 'Canchas',
  gimnasio: 'Gimnasio',
  oficinas: 'Oficinas del personal',
  mantenimiento: 'Mantenimiento',
};
const CAPACIDAD = { sala_vip: 10, restaurante: 40, terraza: 20, piscina: 30, canchas: 16, gimnasio: 25 };
const ZONAS_MIEMBRO = ['restaurante', 'terraza', 'piscina', 'canchas', 'gimnasio'];
const zoneName = (z) => ZONAS[z] || z || '—';

const CATEGORIAS = {
  vip: { label: 'VIP', tone: 'gold', color: 'var(--gold-500)' },
  regular: { label: 'Regular', tone: 'info', color: 'var(--navy-700)' },
  personal: { label: 'Personal', tone: 'navy', color: 'var(--gray-600)' },
  invitado: { label: 'Invitado', tone: 'teal', color: 'var(--teal)' },
  externo: { label: 'Externo', tone: 'warning', color: 'var(--warning)' },
};
const VINCULOS = { regular: 'Regular', vip: 'VIP', personal: 'Personal' };
const RESULTADOS = {
  orientado: { label: 'Orientado', tone: 'success' },
  rechazado: { label: 'Rechazado', tone: 'danger' },
  pendiente_revision: { label: 'Pendiente de revisión', tone: 'warning' },
  corregido: { label: 'Corregido', tone: 'info' },
};
const ESTADOS_PERSONA = {
  activa: { label: 'Activa', tone: 'success' },
  suspendida: { label: 'Suspendida', tone: 'danger' },
};
const ESTADOS_VISITA = {
  programada: { label: 'Programada', tone: 'info' },
  en_curso: { label: 'En curso', tone: 'success' },
  finalizada: { label: 'Finalizada', tone: 'neutral' },
  cancelada: { label: 'Cancelada', tone: 'danger' },
};
const ROLES = {
  admin: { label: 'Administración', tone: 'gold' },
  informatica: { label: 'Informática', tone: 'teal' },
  operador: { label: 'Operador', tone: 'info' },
  usuario: { label: 'Usuario', tone: 'neutral' },
};
const NIVELES_AYUDA = {
  indicacion: 'Indicación verbal',
  mapa: 'Mapa en pantalla',
  acompanamiento: 'Acompañamiento',
};
const MOTIVOS = {
  fuera_de_horario: 'Fuera de horario',
  credencial_vencida: 'Credencial vencida',
  credencial_revocada: 'Credencial revocada',
  credencial_no_encontrada: 'QR no encontrado',
  credencial_aun_no_valida: 'QR aún no válido',
  no_identificado: 'No identificado',
  persona_suspendida: 'Persona suspendida',
  identidad_dudosa: 'Identidad dudosa',
  identidad_ambigua: 'Identidad ambigua',
  captura_no_valida: 'Captura facial no válida',
  contradiccion_cara_credencial: 'La cara y el QR no coinciden',
  acreditacion_vencida: 'Acreditación vencida',
  sin_visita_activa: 'Sin visita activa',
  visita_cancelada: 'Visita cancelada',
};
const EVIDENCIA_CARA = {
  reconocida: 'Reconocida', dudosa: 'Dudosa', ambigua: 'Ambigua', no_reconocida: 'No reconocida',
  desconocida: 'Desconocida', sin_candidato: 'Sin candidato', captura_no_valida: 'Captura no válida', no_usada: 'No usada',
};
const EVIDENCIA_QR = {
  valida: 'Válido', vencida: 'Vencido', revocada: 'Revocado', aun_no_valida: 'Aún no válido',
  no_encontrada: 'No encontrado', no_presentado: 'No presentado',
};

// Reglas del servidor (migraciones 001–005 y propuesta 009). El panel no las cambia.
const POLICY = {
  accesoTemporalHoras: 24,
  limpiezaMinutos: 5,
  eventosDesvincularDias: 90,
  eventosEliminarDias: 365,
  miembros: ['06:00', '21:00'],
  personal: ['04:00', '22:00'],
  turnoMaxHoras: 8,
  motivoMax: 300,
};

const optionsFrom = (map) => Object.entries(map).map(([value, item]) => [value, item.label ?? item]);

function badge(map, key) {
  const item = map[key];
  return item ? `<span class="badge badge--${item.tone}">${item.label}</span>` : '<span class="cell-muted">—</span>';
}

const categoryBadge = (key) => (key ? badge(CATEGORIAS, key) : '<span class="badge badge--neutral badge--plain">Sin resolver</span>');

// =============================================================================
// Roles y permisos
// =============================================================================
const PANEL_ROLES = ['admin', 'informatica', 'operador'];
const VIEW_TITLES = {
  dashboard: 'Dashboard',
  vip: 'Miembros VIP',
  regulares: 'Miembros regulares',
  invitados: 'Invitados',
  personal: 'Personal del club',
  externos: 'Trabajadores externos',
  historial: 'Historial de accesos',
  usuarios: 'Usuarios y roles',
  configuracion: 'Políticas y sistema',
};
const ROLE_VIEWS = {
  admin: Object.keys(VIEW_TITLES),
  informatica: ['dashboard', 'vip', 'regulares', 'personal', 'historial', 'usuarios', 'configuracion'],
  operador: ['dashboard', 'vip', 'regulares', 'invitados', 'personal', 'externos', 'historial', 'configuracion'],
};
const CAP_KEYS = ['ver_personas', 'ver_visitas', 'ver_eventos', 'invitar', 'revocar', 'corregir_eventos',
  'asignar_roles', 'editar_personas', 'ver_auditoria'];

// Misma lógica que public.panel_permisos() (propuesta 009). Solo se usa en la demostración.
function permisosFor(rol) {
  const is = (...roles) => roles.includes(rol);
  return {
    rol,
    ver_personas: is('admin', 'informatica', 'operador'),
    ver_visitas: is('admin', 'operador'),
    ver_eventos: is('admin', 'informatica', 'operador'),
    invitar: is('admin', 'operador'),
    revocar: is('admin', 'operador'),
    corregir_eventos: is('admin', 'operador'),
    asignar_roles: is('admin', 'informatica'),
    editar_personas: is('admin'),
    ver_auditoria: is('admin', 'informatica'),
  };
}

// Con panel_permisos() (009) manda la base. Sin ella rige el modelo actual: es_operador() da
// los mismos permisos de recepción a operador y admin, y no hay funciones de administración.
function computeCaps(permisos, isOperator, rol) {
  const caps = Object.fromEntries(CAP_KEYS.map((k) => [k, false]));
  if (permisos) {
    CAP_KEYS.forEach((k) => { caps[k] = permisos[k] === true; });
    caps.migracion = true;
    return caps;
  }
  const op = isOperator && (rol === 'admin' || rol === 'operador');
  ['ver_personas', 'ver_visitas', 'ver_eventos', 'invitar', 'revocar', 'corregir_eventos'].forEach((k) => { caps[k] = op; });
  caps.migracion = false;
  return caps;
}

let session = null; // { mode: 'demo'|'live', rol, accountId, caps, configured }
const can = (cap) => !!session?.caps?.[cap];
const isLive = () => session?.mode === 'live';

function allowedViews() {
  if (!session) return [];
  return (ROLE_VIEWS[session.rol] || ['dashboard']).filter((v) => {
    if ((v === 'invitados' || v === 'externos') && !can('ver_visitas')) return false;
    if (v === 'historial' && !can('ver_eventos')) return false;
    return true;
  });
}

// =============================================================================
// Estado del panel (modelo común para demo y Supabase)
// =============================================================================
const state = {
  vip: [],
  regulares: [],
  personal: [],
  invitados: [],
  externos: [],
  eventos: [],
  avisos: null, // null: la tabla avisos (007) no está o el rol no la ve
  auditoria: null,
  loadedAt: null,
  warnings: [],
};

// =============================================================================
// Demostración: filas ficticias con la forma de las tablas reales
// =============================================================================
const NOMBRES = ['Valentina', 'Santiago', 'Mariana', 'Sebastián', 'Camila', 'Mateo', 'Isabella', 'Nicolás',
  'Sofía', 'Alejandro', 'Daniela', 'Samuel', 'Gabriela', 'Tomás', 'Lucía', 'Martín', 'Juliana', 'Emilio',
  'Paula', 'Andrés', 'Catalina', 'Felipe', 'Manuela', 'Joaquín', 'Antonia', 'Diego', 'Renata', 'Esteban',
  'Laura', 'Julián', 'Carolina', 'Ricardo', 'Natalia', 'Simón', 'Elena', 'Pablo', 'Verónica', 'Gonzalo'];
const APELLIDOS = ['Restrepo', 'Gómez', 'Ospina', 'Herrera', 'Duarte', 'Valencia', 'Montoya', 'Salazar',
  'Cárdenas', 'Rojas', 'Mejía', 'Arango', 'Quintero', 'Londoño', 'Navarro', 'Castaño', 'Uribe', 'Bermúdez',
  'Zuluaga', 'Escobar', 'Pardo', 'Villegas', 'Lozano', 'Caicedo', 'Serrano', 'Molina', 'Aguilar', 'Ibáñez'];
const EMPRESAS = [
  ['Climatización Andina S.A.S.', 'Mantenimiento de aire acondicionado', 'mantenimiento'],
  ['AquaPro Servicios', 'Revisión de bombas de la piscina', 'piscina'],
  ['Distribuidora Gourmet del Valle', 'Entrega de insumos de cocina', 'restaurante'],
  ['RedSegura Tecnología', 'Soporte de red y cámaras', 'oficinas'],
  ['Fumigaciones Verde Limpio', 'Fumigación programada', 'terraza'],
  ['Elevadores Cordillera', 'Mantenimiento de ascensor', 'mantenimiento'],
  ['Jardines del Norte', 'Poda y paisajismo', 'terraza'],
  ['DeportiFix', 'Reparación de máquinas del gimnasio', 'gimnasio'],
  ['Eléctricas del Oriente Ltda.', 'Revisión de tablero eléctrico', 'mantenimiento'],
];
const MOTIVOS_INVITACION = ['Almuerzo de negocios', 'Celebración familiar', 'Partido de tenis',
  'Visita de cortesía', 'Clase de prueba en el gimnasio', 'Reunión social', 'Tarde de piscina'];
const TURNOS = [['04:00', '12:00'], ['06:00', '14:00'], ['08:00', '16:00'], ['10:00', '18:00'], ['14:00', '22:00']];
const DEMO_ESPACIOS = Object.entries(ZONAS).map(([clave, nombre]) => ({ clave, nombre, capacidad: CAPACIDAD[clave] || 0 }));

const usedNames = new Set();
function fakeName() {
  let name;
  do { name = `${pick(NOMBRES)} ${pick(APELLIDOS)}`; } while (usedNames.has(name));
  usedNames.add(name);
  return name;
}
const fakeEmail = (name, domain = 'demo.nclub.test') => `${slug(name)}@${domain}`;
const fakePhone = () => `+57 3${randInt(0, 2)}${randInt(0, 9)} 555 ${pad(randInt(0, 9999), 4)}`;
const fakeHex = (n) => Array.from({ length: n }, () => Math.floor(rand() * 16).toString(16)).join('');
const fakeUuid = () => { const h = fakeHex(32); return `${h.slice(0, 8)}-${h.slice(8, 12)}-4${h.slice(13, 16)}-8${h.slice(17, 20)}-${h.slice(20)}`; };
const randomToken = () => {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  return [...bytes].map((b) => b.toString(16).padStart(2, '0')).join('');
};

const demo = { db: null, accounts: {} };

function seedDemo() {
  const db = { personas: [], visitas: [], credenciales: [], eventos: [], avisos: [], auditoria: [], espacios: DEMO_ESPACIOS };

  function persona(vinculo, extra = {}) {
    const nombre = extra.nombre_demo || fakeName();
    const temporal = vinculo === 'ninguno';
    const recent = vinculo === 'regular' && chance(0.22);
    const creado = NOW - (recent ? randInt(2, 26) : randInt(40, 2200)) * DAY;
    const consent = !temporal && chance(vinculo === 'vip' ? 0.8 : 0.6);
    const [hi, hf] = temporal ? [null, null]
      : vinculo === 'personal' ? pick(TURNOS)
        : [pick(['06:00', '06:00', '07:00', '08:00']), pick(['21:00', '21:00', '20:00', '19:00'])];
    const p = {
      id: fakeUuid(),
      usuario_id: temporal ? null : (chance(0.93) ? fakeUuid() : null),
      nombre_demo: nombre,
      email: fakeEmail(nombre, temporal ? 'invitado.demo.test' : 'demo.nclub.test'),
      telefono: temporal ? null : fakePhone(),
      vinculo,
      rol: 'usuario',
      estado: temporal || chance(0.9) ? 'activa' : 'suspendida',
      requiere_tour: recent,
      horario_inicio: hi && `${hi}:00`,
      horario_fin: hf && `${hf}:00`,
      vinculo_hasta: vinculo === 'vip' && chance(0.3) ? dateOnly(NOW + randInt(-5, 240) * DAY) : null,
      consentimiento_biometrico: consent,
      consentimiento_fecha: consent ? iso(Math.min(NOW, creado + randInt(0, 20) * DAY)) : null,
      creado_en: iso(temporal ? NOW : creado),
      ...extra,
    };
    db.personas.push(p);
    return p;
  }

  for (let i = 0; i < 14; i++) persona('vip');
  for (let i = 0; i < 26; i++) persona('regular');

  // Cuentas de la demostración: una por rol del panel.
  const cuenta = { estado: 'activa', usuario_id: null };
  const admin = persona('personal', { ...cuenta, rol: 'admin', horario_inicio: '08:00:00', horario_fin: '16:00:00' });
  const it = persona('personal', { ...cuenta, rol: 'informatica', horario_inicio: '08:00:00', horario_fin: '16:00:00' });
  const op = persona('personal', { ...cuenta, rol: 'operador', horario_inicio: '06:00:00', horario_fin: '14:00:00' });
  [admin, it, op].forEach((p) => { p.usuario_id = fakeUuid(); });
  persona('personal', { rol: 'operador', estado: 'activa' });
  persona('personal', { rol: 'operador', estado: 'activa' });
  for (let i = 0; i < 8; i++) persona('personal');
  demo.accounts = { admin: admin.id, informatica: it.id, operador: op.id };

  const members = db.personas.filter((p) => (p.vinculo === 'vip' || p.vinculo === 'regular') && p.estado === 'activa');
  const staff = db.personas.filter((p) => p.vinculo === 'personal' && p.estado === 'activa');

  // QR personales vigentes (el panel nunca ve el token ni su hash).
  db.personas.filter((p) => p.usuario_id && p.estado === 'activa' && chance(0.85)).forEach((p) => {
    db.credenciales.push({ id: fakeUuid(), persona_id: p.id, visita_id: null, tipo: 'qr_personal', valido_desde: p.creado_en, valido_hasta: null, revocada_en: null, creado_en: p.creado_en });
  });

  // Invitados y externos: solo existen los registrados hace menos de 24 h; los anteriores ya
  // los borró el servidor (limpiar_visitas_vencidas).
  function temporal(categoria, i) {
    const [empresa, motivoExt, destinoExt] = EMPRESAS[i % EMPRESAS.length];
    const host = categoria === 'invitado' ? pick([...members, op]) : pick(staff);
    const p = persona('ninguno');
    const creado = NOW - randInt(10, 23 * 60) * MIN;
    const fin = creado + POLICY.accesoTemporalHoras * HOUR;
    const kind = i % 6;
    let inicio;
    let estado;
    if (kind <= 2) { inicio = Math.max(creado, NOW - randInt(10, 180) * MIN); estado = 'en_curso'; } else {
      const room = Math.max(30, Math.floor((fin - NOW) / MIN) - 30);
      inicio = Math.min(roundTo(NOW + randInt(30, room) * MIN, 15 * MIN), fin - 15 * MIN);
      estado = kind === 5 ? 'cancelada' : 'programada';
    }
    p.creado_en = iso(creado);
    const v = {
      id: fakeUuid(),
      persona_id: p.id,
      responsable_id: host.id,
      categoria,
      motivo: categoria === 'externo' ? motivoExt : pick(MOTIVOS_INVITACION),
      empresa: categoria === 'externo' ? empresa : null,
      destino: categoria === 'externo' ? destinoExt : (host.vinculo === 'vip' && chance(0.4) ? 'sala_vip' : pick(ZONAS_MIEMBRO)),
      inicio: iso(inicio),
      fin: iso(fin),
      estado,
      nivel_ayuda: estado === 'en_curso' ? (categoria === 'externo' ? 'acompanamiento' : pick(Object.keys(NIVELES_AYUDA))) : null,
      creado_en: iso(creado),
    };
    db.visitas.push(v);
    db.credenciales.push({
      id: fakeUuid(), persona_id: p.id, visita_id: v.id, tipo: 'qr_visita', valido_desde: v.inicio, valido_hasta: v.fin,
      revocada_en: estado === 'cancelada' ? iso(creado + 30 * MIN) : null, creado_en: v.creado_en,
    });
  }
  for (let i = 0; i < 12; i++) temporal('invitado', i);
  for (let i = 0; i < 9; i++) temporal('externo', i);

  // Avisos de llegada (trigger visitas_avisar_llegada): uno por visita en curso. Dos quedan sin
  // respuesta del anfitrión o responsable; los demás ya los aceptó en la app.
  db.visitas.filter((v) => v.estado === 'en_curso' && v.responsable_id).forEach((v, i) => {
    const nombre = db.personas.find((p) => p.id === v.persona_id).nombre_demo;
    const llego = Math.max(toTs(v.inicio), NOW - randInt(5, 90) * MIN);
    db.avisos.push({
      id: fakeUuid(), destinatario_id: v.responsable_id, visita_id: v.id, tipo: `llegada_${v.categoria}`,
      mensaje: `${nombre} llegó a N Club. Encuentro: ${zoneName(v.destino)}.`, punto_encuentro: v.destino,
      estado: i < 2 ? 'sin_respuesta' : 'aceptado', creado_en: iso(llego), actualizado_en: iso(llego + randInt(1, 4) * MIN),
    });
  });

  demo.db = db;

  // Eventos: 34 en las últimas 11 h y 56 en los 7 días anteriores.
  const times = [];
  for (let i = 0; i < 34; i++) times.push(NOW - randInt(1, 11 * 60) * MIN);
  for (let i = 0; i < 56; i++) times.push(NOW - randInt(11 * 60, 7 * 24 * 60) * MIN);
  times.sort((a, b) => a - b).forEach((ts) => demoArrival(ts, chance(0.88) ? 'robot' : 'simulacion'));

  // Dos casos recientes para revisar en recepción.
  db.eventos.filter((e) => e.resultado === 'orientado' && e.evidencia.cara === 'reconocida' && NOW - toTs(e.creado_en) < 3 * HOUR)
    .slice(0, 2)
    .forEach((e) => {
      Object.assign(e, { resultado: 'pendiente_revision', motivo: 'identidad_ambigua', categoria: null, orientacion: null, visita_id: null });
      e.evidencia = { ...e.evidencia, cara: 'ambigua', detalle: 'entre_umbrales', distancia: Number((0.42 + rand() * 0.06).toFixed(3)) };
    });

  db.auditoria.push(
    { id: fakeUuid(), actor_id: admin.id, accion: 'asignar_rol', persona_id: it.id, cambios: { rol: ['usuario', 'informatica'] }, creado_en: iso(NOW - 12 * DAY) },
    { id: fakeUuid(), actor_id: it.id, accion: 'asignar_rol', persona_id: op.id, cambios: { rol: ['usuario', 'operador'] }, creado_en: iso(NOW - 9 * DAY) },
    { id: fakeUuid(), actor_id: admin.id, accion: 'actualizar_persona', persona_id: members[0].id, cambios: { vinculo: ['regular', 'vip'], requiere_tour: [true, false] }, creado_en: iso(NOW - 3 * DAY) },
  );
}

// Llegada simplificada (en la base la registra registrar_llegada() con la clave de servicio).
function demoArrival(ts, fuente) {
  const db = demo.db;
  const recent = Date.now() - ts < 11 * HOUR;
  const club = db.personas.filter((p) => p.vinculo !== 'ninguno');
  const enCurso = db.visitas.filter((v) => (v.categoria === 'invitado' || v.categoria === 'externo') && v.estado === 'en_curso');
  const roll = rand();
  let persona = null;
  let visita = null;
  let tempCategoria = null;
  if (roll < 0.76) persona = pick(club);
  else if (roll < 0.93) {
    visita = recent ? pick(enCurso) : null;
    tempCategoria = chance(0.6) ? 'invitado' : 'externo';
    if (visita) persona = db.personas.find((p) => p.id === visita.persona_id);
  }

  const ev = {
    id: fakeUuid(), visita_id: null, persona_candidata_id: persona?.id ?? null, fuente,
    evidencia: { cara: 'no_usada', qr: 'no_presentado' }, categoria: null, resultado: 'orientado', motivo: null,
    orientacion: null, duracion_ms: randInt(1800, 9500), creado_en: iso(ts),
    corregido_por: null, correccion_motivo: null, corregido_en: null, modo_reconocimiento: null,
  };
  const r = rand();

  if (!persona && !tempCategoria) {
    ev.evidencia = { cara: 'desconocida', distancia: null, qr: 'no_presentado', modo: 'real' };
    ev.modo_reconocimiento = 'real';
    ev.resultado = 'rechazado';
    ev.motivo = 'no_identificado';
  } else if (tempCategoria) {
    // Si la visita ya no existe, el servidor borró a la persona: el evento queda sin vínculos.
    ev.categoria = visita?.categoria || tempCategoria;
    ev.evidencia = { cara: 'no_usada', qr: 'valida' };
    if (visita) {
      ev.visita_id = visita.id;
      ev.orientacion = { destino: visita.destino, nivel_ayuda: visita.nivel_ayuda || 'acompanamiento' };
    } else {
      ev.orientacion = { destino: tempCategoria === 'externo' ? 'mantenimiento' : pick(ZONAS_MIEMBRO), nivel_ayuda: 'acompanamiento' };
    }
  } else {
    const face = persona.consentimiento_biometrico && chance(0.75);
    ev.evidencia = face
      ? { cara: 'reconocida', distancia: Number((0.14 + rand() * 0.24).toFixed(3)), qr: 'no_presentado', modo: 'real' }
      : { cara: 'no_usada', qr: 'valida' };
    ev.modo_reconocimiento = face ? 'real' : null;
    ev.categoria = persona.vinculo;
    if (persona.estado !== 'activa') {
      ev.resultado = 'rechazado'; ev.motivo = 'persona_suspendida'; ev.categoria = null;
    } else if (persona.vinculo_hasta && persona.vinculo_hasta < dateOnly(ts)) {
      ev.resultado = 'rechazado'; ev.motivo = 'acreditacion_vencida';
    } else if (r < 0.07) {
      ev.resultado = 'rechazado'; ev.motivo = 'fuera_de_horario';
    } else {
      const destino = persona.vinculo === 'personal' ? pick(['lobby', 'oficinas', 'restaurante', 'mantenimiento'])
        : (persona.vinculo === 'vip' && chance(0.35) ? 'sala_vip' : pick(ZONAS_MIEMBRO));
      const nivel = persona.requiere_tour ? 'acompanamiento' : pick(['indicacion', 'indicacion', 'mapa', 'acompanamiento']);
      const fin = new Date(ts);
      const [h, m] = toHHMM(persona.horario_fin).split(':').map(Number);
      fin.setHours(h, m, 0, 0);
      const v = {
        id: fakeUuid(), persona_id: persona.id, responsable_id: null, categoria: persona.vinculo, motivo: null, empresa: null,
        destino, inicio: iso(ts), fin: iso(Math.max(fin.getTime(), ts + HOUR)),
        estado: Math.max(fin.getTime(), ts + HOUR) < Date.now() ? 'finalizada' : 'en_curso', nivel_ayuda: nivel, creado_en: iso(ts),
      };
      db.visitas.push(v);
      ev.visita_id = v.id;
      ev.orientacion = { destino, nivel_ayuda: nivel };
    }
  }

  // Los pendientes antiguos ya los resolvió recepción.
  if (ev.resultado === 'pendiente_revision' && Date.now() - ts > 6 * HOUR) ev.resultado = 'corregido';
  db.eventos.unshift(ev);
  return ev;
}

// Lo que hacen los jobs de pg_cron en el servidor, imitado en cada lectura de la demostración.
function demoServerJobs() {
  const db = demo.db;
  const now = Date.now();
  // limpiar_visitas_vencidas(): invitados y externos sin visita vigente → se borran en cascada.
  const borrar = new Set(db.personas
    .filter((p) => p.vinculo === 'ninguno' && !p.usuario_id
      && !db.visitas.some((v) => v.persona_id === p.id && toTs(v.fin) >= now))
    .map((p) => p.id));
  if (borrar.size) {
    const visitas = new Set(db.visitas.filter((v) => borrar.has(v.persona_id)).map((v) => v.id));
    db.personas = db.personas.filter((p) => !borrar.has(p.id));
    db.visitas = db.visitas.filter((v) => !visitas.has(v.id));
    db.credenciales = db.credenciales.filter((c) => !borrar.has(c.persona_id));
    db.avisos = db.avisos.filter((a) => !visitas.has(a.visita_id));
    db.eventos.forEach((e) => {
      if (borrar.has(e.persona_candidata_id)) e.persona_candidata_id = null;
      if (visitas.has(e.visita_id)) e.visita_id = null;
    });
  }
  // aplicar_retencion_historial() (propuesta 009).
  db.eventos.forEach((e) => {
    if (now - toTs(e.creado_en) > POLICY.eventosDesvincularDias * DAY) {
      Object.assign(e, { persona_candidata_id: null, visita_id: null, corregido_por: null, correccion_motivo: null });
    }
  });
  db.eventos = db.eventos.filter((e) => now - toTs(e.creado_en) <= POLICY.eventosEliminarDias * DAY);
  db.auditoria = db.auditoria.filter((a) => now - toTs(a.creado_en) <= POLICY.eventosEliminarDias * DAY);
}

// Errores con el mismo texto y tipo que devuelve la base de datos.
function dbError(message, { denied = false } = {}) {
  const err = new Error(message);
  err.denied = denied;
  return err;
}

const demoActor = () => demo.db.personas.find((p) => p.id === session.accountId);
const demoRol = () => { const yo = demoActor(); return yo && yo.estado === 'activa' ? yo.rol : null; };
const demoIsOperator = () => ['admin', 'operador'].includes(demoRol());

const demoBackend = {
  async load() {
    await new Promise((r) => setTimeout(r, 250)); // latencia simulada para ver los estados de carga
    demoServerJobs();
    const db = demo.db;
    const p = permisosFor(demoRol());
    const yo = demoActor();
    const since = Date.now() - 30 * DAY;
    // Mismas políticas RLS que la base (003 + propuesta 009).
    const personas = db.personas.filter((x) => (p.ver_visitas ? true : p.ver_personas ? x.vinculo !== 'ninguno' : x.id === yo?.id));
    return clone({
      personas,
      visitas: p.ver_visitas ? db.visitas.filter((v) => toTs(v.fin) >= since) : [],
      credenciales: p.ver_visitas ? db.credenciales.filter((c) => !c.revocada_en) : [],
      eventos: p.ver_eventos ? db.eventos.filter((e) => toTs(e.creado_en) >= since) : [],
      avisos: p.ver_visitas ? db.avisos.filter((a) => Date.now() - toTs(a.creado_en) <= DAY) : null,
      espacios: db.espacios,
      auditoria: p.ver_auditoria ? db.auditoria.slice().sort((a, b) => toTs(b.creado_en) - toTs(a.creado_en)) : null,
      warnings: [],
      loadedAt: Date.now(),
    });
  },

  // crear_invitacion() de la propuesta 009 + trigger de 24 h.
  async crearInvitacion(d) {
    const db = demo.db;
    const yo = demoActor();
    if (!yo || yo.estado !== 'activa') throw dbError('Necesitas una cuenta activa del club.');
    const sinRol = yo.rol === 'usuario' || yo.rol === 'informatica';
    if (d.categoria === 'invitado' && !['regular', 'vip'].includes(yo.vinculo) && sinRol) throw dbError('Solo los miembros invitan.');
    if (d.categoria === 'externo' && yo.vinculo !== 'personal' && sinRol) throw dbError('Solo el personal o un operador registran trabajadores externos.');
    const creado = Date.now();
    const fin = creado + POLICY.accesoTemporalHoras * HOUR;
    const inicio = new Date(d.inicio).getTime();
    if (inicio >= fin) throw dbError(`La visita debe empezar antes de ${fmtDateTime(fin)} (24 h después del registro).`);
    const p = {
      id: fakeUuid(), usuario_id: null, nombre_demo: d.nombre, email: d.email, telefono: null, vinculo: 'ninguno', rol: 'usuario',
      estado: 'activa', requiere_tour: false, horario_inicio: null, horario_fin: null, vinculo_hasta: null,
      consentimiento_biometrico: false, consentimiento_fecha: null, creado_en: iso(creado),
    };
    const v = {
      id: fakeUuid(), persona_id: p.id, responsable_id: yo.id, categoria: d.categoria, motivo: d.motivo || null,
      empresa: d.empresa || null, destino: d.destino, inicio: iso(inicio), fin: iso(fin), estado: 'programada', nivel_ayuda: null, creado_en: iso(creado),
    };
    db.personas.push(p);
    db.visitas.unshift(v);
    db.credenciales.push({ id: fakeUuid(), persona_id: p.id, visita_id: v.id, tipo: 'qr_visita', valido_desde: v.inicio, valido_hasta: v.fin, revocada_en: null, creado_en: v.creado_en });
    return { visita_id: v.id, token: randomToken() };
  },

  async revocarInvitacion(visitaId) {
    const db = demo.db;
    const v = db.visitas.find((x) => x.id === visitaId);
    if (!v || !(v.responsable_id === session.accountId || demoIsOperator())) throw dbError('No puedes revocar esta invitación.');
    v.estado = 'cancelada';
    db.credenciales.filter((c) => c.visita_id === visitaId && !c.revocada_en).forEach((c) => { c.revocada_en = iso(Date.now()); });
  },

  async corregirEvento(eventoId, categoria, motivo, personaId) {
    if (!demoIsOperator()) throw dbError('Solo un operador de recepción puede corregir eventos.', { denied: true });
    if (!String(motivo || '').trim()) throw dbError('La corrección necesita un motivo.');
    const db = demo.db;
    const e = db.eventos.find((x) => x.id === eventoId);
    if (!e) throw dbError('El evento no existe.');
    let visita = null;
    if (personaId) {
      visita = db.visitas.find((v) => v.persona_id === personaId && ['programada', 'en_curso'].includes(v.estado)
        && Date.now() >= toTs(v.inicio) && Date.now() <= toTs(v.fin));
      if (!visita && (categoria === 'invitado' || categoria === 'externo')) {
        throw dbError('Esa persona no tiene una invitación vigente; créala con crear_invitacion.');
      }
      if (!visita) {
        visita = { id: fakeUuid(), persona_id: personaId, responsable_id: null, categoria, motivo: 'habilitada por recepción', empresa: null, destino: null, inicio: iso(Date.now()), fin: iso(Date.now() + 4 * HOUR), estado: 'en_curso', nivel_ayuda: null, creado_en: iso(Date.now()) };
        db.visitas.push(visita);
      }
    }
    Object.assign(e, {
      categoria, resultado: 'corregido', corregido_por: session.accountId, correccion_motivo: motivo, corregido_en: iso(Date.now()),
      persona_candidata_id: personaId || e.persona_candidata_id, visita_id: visita?.id || e.visita_id,
    });
  },

  async asignarRol(personaId, rol) {
    const db = demo.db;
    const actorRol = demoRol();
    if (!['admin', 'informatica'].includes(actorRol)) throw dbError('Solo administración o informática pueden asignar roles.', { denied: true });
    const obj = db.personas.find((p) => p.id === personaId);
    if (!obj) throw dbError('La persona no existe.');
    if (obj.id === session.accountId) throw dbError('No puedes cambiar tu propio rol.');
    if (!obj.usuario_id) throw dbError('La persona no tiene cuenta en la app.');
    if (rol !== 'usuario' && obj.vinculo !== 'personal') throw dbError('Solo el personal del club puede tener un rol de panel.');
    if (actorRol === 'informatica' && (rol === 'admin' || obj.rol === 'admin')) throw dbError('Informática no puede asignar ni quitar el rol de administrador.', { denied: true });
    if (obj.rol === rol) return;
    db.auditoria.push({ id: fakeUuid(), actor_id: session.accountId, accion: 'asignar_rol', persona_id: obj.id, cambios: { rol: [obj.rol, rol] }, creado_en: iso(Date.now()) });
    obj.rol = rol;
  },

  async actualizarPersona(personaId, c) {
    const db = demo.db;
    if (demoRol() !== 'admin') throw dbError('Solo un administrador puede editar personas.', { denied: true });
    const p = db.personas.find((x) => x.id === personaId);
    if (!p) throw dbError('La persona no existe.');
    if (p.vinculo === 'ninguno') throw dbError('Los invitados y externos se gestionan desde su visita.');
    if (p.id === session.accountId && c.estado === 'suspendida') throw dbError('No puedes suspender tu propia cuenta.');
    const antes = { ...p };
    const vinculo = c.vinculo ?? p.vinculo;
    const next = {
      estado: c.estado ?? p.estado,
      vinculo,
      horario_inicio: c.horario_inicio ? `${c.horario_inicio}:00` : p.horario_inicio,
      horario_fin: c.horario_fin ? `${c.horario_fin}:00` : p.horario_fin,
      vinculo_hasta: c.sin_vencimiento ? null : (c.vinculo_hasta ?? p.vinculo_hasta),
      requiere_tour: vinculo === 'regular' ? (c.requiere_tour ?? p.requiere_tour) : false,
      rol: vinculo === 'personal' ? p.rol : 'usuario',
    };
    // CHECK horario_valido de la tabla personas.
    const ini = toHHMM(next.horario_inicio);
    const fin = toHHMM(next.horario_fin);
    const [lo, hi] = vinculo === 'personal' ? POLICY.personal : POLICY.miembros;
    if (!(fin > ini && ini >= lo && fin <= hi) || (vinculo === 'personal' && toMinutes(fin) - toMinutes(ini) > POLICY.turnoMaxHoras * 60)) {
      throw dbError('Los datos no cumplen las reglas de la base de datos (personas).');
    }
    Object.assign(p, next);
    const cambios = {};
    Object.keys(next).forEach((k) => { if (antes[k] !== p[k]) cambios[k] = [antes[k], p[k]]; });
    db.auditoria.push({ id: fakeUuid(), actor_id: session.accountId, accion: 'actualizar_persona', persona_id: p.id, cambios, creado_en: iso(Date.now()) });
  },
};

const liveBackend = {
  load: () => window.NClubDB.loadSnapshot({ verVisitas: can('ver_visitas'), verEventos: can('ver_eventos'), verAuditoria: can('ver_auditoria') }),
  crearInvitacion: (d) => window.NClubDB.crearInvitacion(d),
  revocarInvitacion: (id, motivo) => window.NClubDB.revocarInvitacion(id, motivo),
  corregirEvento: (id, categoria, motivo, persona) => window.NClubDB.corregirEvento(id, categoria, motivo, persona),
  asignarRol: (id, rol) => window.NClubDB.asignarRol(id, rol),
  actualizarPersona: (id, cambios) => window.NClubDB.actualizarPersona(id, cambios),
};

const backend = () => (isLive() ? liveBackend : demoBackend);

// =============================================================================
// De las filas de la base al modelo del panel (igual para demo y Supabase)
// =============================================================================
function applySnapshot(snap) {
  const now = Date.now();
  const monthStart = new Date(new Date().getFullYear(), new Date().getMonth(), 1).getTime();
  const personaById = new Map(snap.personas.map((p) => [p.id, p]));
  const nameOf = (id) => personaById.get(id)?.nombre_demo ?? null;

  if (snap.espacios) {
    snap.espacios.forEach((e) => { ZONAS[e.clave] = e.nombre; });
    const used = new Set([...snap.visitas.map((v) => v.destino), ...snap.eventos.map((e) => e.orientacion?.destino)]);
    Object.keys(CAPACIDAD).forEach((k) => delete CAPACIDAD[k]);
    snap.espacios
      .filter((e) => e.capacidad > 0 && (used.has(e.clave) || ['sala_vip', ...ZONAS_MIEMBRO].includes(e.clave)))
      .forEach((e) => { CAPACIDAD[e.clave] = e.capacidad; });
  }

  const vigente = (c) => !c.revocada_en && (!c.valido_hasta || toTs(c.valido_hasta) > now);
  const personalCred = new Map();
  const visitCred = new Map();
  snap.credenciales.filter(vigente).forEach((c) => {
    const cred = { valido_desde: toTs(c.valido_desde), valido_hasta: toTs(c.valido_hasta) };
    if (c.tipo === 'qr_personal') personalCred.set(c.persona_id, cred);
    else if (c.visita_id) visitCred.set(c.visita_id, cred);
  });

  const visitaById = new Map(snap.visitas.map((v) => [v.id, v]));
  const eventos = snap.eventos.map((e) => {
    const ev = e.evidencia || {};
    const visita = visitaById.get(e.visita_id);
    const name = nameOf(e.persona_candidata_id);
    const temporal = e.categoria === 'invitado' || e.categoria === 'externo';
    return {
      id: e.id,
      fecha: toTs(e.creado_en),
      visita_id: e.visita_id,
      persona_id: name ? e.persona_candidata_id : null,
      persona: name || (temporal ? `${CATEGORIAS[e.categoria].label} sin datos personales` : 'Persona no identificada'),
      categoria: e.categoria,
      cara: ev.cara || 'no_usada',
      distancia: typeof ev.distancia === 'number' ? ev.distancia : null,
      qr: ev.qr || 'no_presentado',
      modo: e.modo_reconocimiento,
      resultado: e.resultado,
      motivo: e.motivo,
      fuente: e.fuente,
      destino: e.orientacion?.destino || visita?.destino || null,
      nivel_ayuda: e.orientacion?.nivel_ayuda || visita?.nivel_ayuda || null,
      duracion_ms: e.duracion_ms,
      corregido_por: nameOf(e.corregido_por) || (e.corregido_por ? 'Personal del club' : null),
      correccion_motivo: e.correccion_motivo,
      corregido_en: toTs(e.corregido_en),
    };
  });

  const lastAccess = new Map();
  const firstEntry = new Map();
  eventos.filter(isOk).forEach((e) => {
    if (e.persona_id && !lastAccess.has(e.persona_id)) lastAccess.set(e.persona_id, e.fecha);
    if (e.visita_id) firstEntry.set(e.visita_id, e.fecha); // orden descendente: queda la primera
  });
  const monthVisits = new Map();
  snap.visitas
    .filter((v) => v.estado !== 'cancelada' && toTs(v.inicio) >= monthStart)
    .forEach((v) => monthVisits.set(v.persona_id, (monthVisits.get(v.persona_id) || 0) + 1));

  const toPerson = (p) => ({
    id: p.id,
    nombre: p.nombre_demo,
    email: p.email,
    telefono: p.telefono,
    vinculo: p.vinculo,
    rol: p.rol,
    estado: p.estado,
    horario_inicio: toHHMM(p.horario_inicio) || '—',
    horario_fin: toHHMM(p.horario_fin) || '—',
    vinculo_hasta: p.vinculo_hasta,
    biometria: p.consentimiento_biometrico,
    consentimiento_fecha: toTs(p.consentimiento_fecha),
    requiere_tour: p.requiere_tour,
    miembro_desde: toTs(p.creado_en),
    ultimo_acceso: lastAccess.get(p.id) ?? null,
    tiene_cuenta: !!p.usuario_id, // del id de Auth solo se conserva si existe
    visitas_mes: monthVisits.get(p.id) || 0,
    credencial: personalCred.get(p.id) || null,
    qr: personalCred.has(p.id) ? 'vigente' : 'sin_qr',
  });

  const toVisit = (v) => {
    const persona = personaById.get(v.persona_id);
    return {
      id: v.id,
      persona_id: v.persona_id,
      categoria: v.categoria,
      nombre: persona?.nombre_demo || 'Persona sin datos',
      email: persona?.email || null,
      responsable_id: v.responsable_id,
      motivo: v.motivo,
      empresa: v.empresa,
      destino: v.destino,
      inicio: toTs(v.inicio),
      fin: toTs(v.fin),
      estado: v.estado,
      nivel_ayuda: v.nivel_ayuda,
      creado_en: toTs(v.creado_en),
      usado_en: firstEntry.get(v.id) ?? null,
      credencial: visitCred.get(v.id) || null,
    };
  };

  state.vip = snap.personas.filter((p) => p.vinculo === 'vip').map(toPerson);
  state.regulares = snap.personas.filter((p) => p.vinculo === 'regular').map(toPerson);
  state.personal = snap.personas.filter((p) => p.vinculo === 'personal').map(toPerson);
  state.invitados = snap.visitas.filter((v) => v.categoria === 'invitado').map(toVisit);
  state.externos = snap.visitas.filter((v) => v.categoria === 'externo').map(toVisit);
  state.eventos = eventos;
  // Avisos al anfitrión o responsable: los crea la base al empezar la visita y los responde esa
  // persona en la app. Con el contacto del destinatario para que recepción lo llame.
  state.avisos = snap.avisos
    ? snap.avisos.map((a) => {
      const visita = visitaById.get(a.visita_id);
      const dest = personaById.get(a.destinatario_id);
      return {
        id: a.id,
        fecha: toTs(a.creado_en),
        actualizado: toTs(a.actualizado_en),
        estado: a.estado,
        tipo: a.tipo,
        mensaje: a.mensaje,
        punto: a.punto_encuentro || visita?.destino || null,
        visita_id: a.visita_id,
        categoria: visita?.categoria || (a.tipo === 'llegada_externo' ? 'externo' : 'invitado'),
        visitante: nameOf(visita?.persona_id) || 'Visitante',
        destinatario: dest?.nombre_demo || 'Anfitrión',
        telefono: dest?.telefono || null,
        email: dest?.email || null,
      };
    })
    : null;
  state.auditoria = snap.auditoria
    ? snap.auditoria.map((a) => ({
      id: a.id,
      fecha: toTs(a.creado_en),
      actor: nameOf(a.actor_id) || 'Cuenta eliminada',
      persona: nameOf(a.persona_id) || 'Persona eliminada',
      accion: a.accion,
      cambios: a.cambios || {},
    }))
    : null;
  state.loadedAt = snap.loadedAt;
  state.warnings = snap.warnings || [];
}

// =============================================================================
// Consultas
// =============================================================================
const people = () => [...state.personal, ...state.vip, ...state.regulares];
const isOk = (e) => e.resultado === 'orientado' || e.resultado === 'corregido';
const pendingEvents = () => state.eventos.filter((e) => e.resultado === 'pendiente_revision');
const unansweredAvisos = () => (state.avisos || []).filter((a) => a.estado === 'sin_respuesta');
const account = () => people().find((p) => p.id === session?.accountId) || null;

// El invitado o externo es una persona con su visita: se busca por cualquiera de los dos.
function findPerson(id) {
  if (!id) return null;
  return people().find((p) => p.id === id)
    || [...state.invitados, ...state.externos].find((v) => v.id === id || v.persona_id === id)
    || null;
}

const personName = (id) => findPerson(id)?.nombre ?? '—';

function inShift(p) {
  const t = nowHHMM();
  return p.estado === 'activa' && t >= p.horario_inicio && t < p.horario_fin;
}

// Personas dentro: última llegada orientada de cada persona en las últimas 4 horas.
function insideNow() {
  const seen = new Map();
  const limit = Date.now() - 4 * HOUR;
  for (const e of state.eventos) {
    if (e.fecha < limit) break;
    if (isOk(e) && e.persona_id && !seen.has(e.persona_id)) seen.set(e.persona_id, e);
  }
  return [...seen.values()];
}

const pct = (part, total) => (total ? Math.round((part / total) * 100) : 0);
const activeVisit = (v) => v.estado === 'programada' || v.estado === 'en_curso';

// Quién puede recibir un rol de panel (lo vuelve a validar asignar_rol() en la base).
function canChangeRole(p) {
  if (!can('asignar_roles') || !p.tiene_cuenta || p.id === session.accountId || p.vinculo !== 'personal') return false;
  return session.rol === 'admin' || p.rol !== 'admin';
}

// =============================================================================
// Componentes
// =============================================================================
const AVATAR_TONES = [
  ['#e7ecf4', '#1a3254'], ['#f7f0df', '#8a6a22'], ['#e1f1f0', '#19706f'],
  ['#e8eef8', '#2d5893'], ['#eef0f3', '#4b5362'], ['#f4e9e4', '#8a4b33'],
];

function initials(name) {
  return String(name || '?').split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join('').toUpperCase();
}

function avatar(name, size = '', known = true) {
  if (!known || !name) return `<span class="avatar avatar--unknown ${size}">?</span>`;
  const [bg, fg] = AVATAR_TONES[hashString(name) % AVATAR_TONES.length];
  return `<span class="avatar ${size}" style="background:${bg};color:${fg}">${escapeHtml(initials(name))}</span>`;
}

function personCell(name, sub, known = true) {
  return `<div class="cell-person">${avatar(name, '', known)}<div>
    <div class="cell-person__name">${escapeHtml(name)}</div>
    <div class="cell-person__sub">${sub}</div></div></div>`;
}

function identCell(p) {
  return `<span class="cell-icons">
    <span title="${p.biometria ? 'Consentimiento biométrico otorgado' : 'Sin biometría: ingresa con QR'}">${icon('face', p.biometria ? 'on' : '')}</span>
    <span title="${p.qr === 'vigente' ? 'QR personal vigente' : 'Sin QR personal vigente'}">${icon('qr', p.qr === 'vigente' ? 'on' : '')}</span>
  </span>`;
}

function statCard(s) {
  return `<article class="card stat ${s.accent ? 'stat--accent' : ''}">
    <div class="stat__top">
      <span class="stat__label">${s.label}</span>
      <span class="stat__icon ${s.tone ? `stat__icon--${s.tone}` : ''}">${icon(s.icon)}</span>
    </div>
    <div class="stat__value">${s.value}</div>
    ${s.hint ? `<div class="stat__hint">${s.hint}</div>` : ''}
  </article>`;
}

// Estado de una credencial. El token y su hash nunca llegan al panel.
function credentialBox(c, note) {
  const vigencia = c
    ? `Válida desde ${fmtDateTime(c.valido_desde)}${c.valido_hasta ? ` hasta ${fmtDateTime(c.valido_hasta)}` : ', sin vencimiento'}.`
    : 'No hay una credencial QR activa.';
  return `<div class="qr-box"><span class="stat__icon ${c ? 'stat__icon--success' : ''}">${icon('qr')}</span><div>
    <strong>${c ? 'Credencial QR vigente' : 'Sin credencial QR vigente'}</strong>
    <p>${vigencia} ${note}</p>
  </div></div>`;
}

// QR real del token, con la misma codificación que la app (QrCard: solo el token, ECL M).
function qrSvg(text) {
  if (typeof window.qrcode !== 'function') return null;
  const qr = window.qrcode(0, 'M');
  qr.addData(text);
  qr.make();
  return qr.createSvgTag(4, 8);
}

// Código de pase compatible con la pantalla /pase de la app (pass.ts: prefijo NC1. + base64url).
function encodePassCode(pass) {
  const bytes = new TextEncoder().encode(JSON.stringify(pass));
  let bin = '';
  bytes.forEach((b) => { bin += String.fromCharCode(b); });
  return `NC1.${btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')}`;
}

async function copyText(text, label) {
  try {
    await navigator.clipboard.writeText(text);
    toast(`${label} copiado al portapapeles.`);
  } catch {
    toast('No se pudo copiar automáticamente: selecciona el texto y cópialo.', 'info');
  }
}

function setBusy(btn, busy) {
  if (!btn) return;
  btn.disabled = busy;
  btn.classList.toggle('is-loading', busy);
  btn.setAttribute('aria-busy', busy ? 'true' : 'false');
}

// =============================================================================
// Notificaciones y errores
// =============================================================================
function toast(message, type = 'success') {
  const iconName = { success: 'check-circle', danger: 'alert', info: 'info' }[type] || 'info';
  const el = document.createElement('div');
  el.className = `toast toast--${type}`;
  el.setAttribute('role', type === 'danger' ? 'alert' : 'status');
  el.innerHTML = `${icon(iconName)}<span>${message}</span>`;
  $('#toasts').append(el);
  setTimeout(() => {
    el.classList.add('is-leaving');
    setTimeout(() => el.remove(), 220);
  }, type === 'danger' ? 6000 : 3600);
}

function handleError(err, context = '') {
  if (err?.expired) {
    sessionExpired(err.message);
    return;
  }
  toast(`${context ? `${escapeHtml(context)}: ` : ''}${escapeHtml(err?.message || 'Error inesperado.')}`, 'danger');
}

// =============================================================================
// Ventanas modales
// =============================================================================
const modal = $('#modal');
const modalInner = $('#modalInner');

function openModal(html, { size = '', onMount, autofocus } = {}) {
  modal.className = `modal ${size ? `modal--${size}` : ''}`;
  modalInner.innerHTML = html;
  if (!modal.open) modal.showModal();
  onMount?.(modalInner);
  const focusable = autofocus ? $(autofocus, modalInner) : $('input:not([type="hidden"]):not([disabled]), select, textarea', modalInner);
  (focusable || $('[data-close]', modalInner))?.focus({ preventScroll: true });
  const body = $('.modal__body', modalInner);
  if (body) body.scrollTop = 0;
}

const closeModal = () => { if (modal.open) modal.close(); };

modal.addEventListener('click', (e) => {
  if (e.target === modal || e.target.closest('[data-close]')) closeModal();
});
// Al cerrar se borra el contenido: así un token mostrado una vez no queda en la página.
modal.addEventListener('close', () => { if (!modal.open) modalInner.innerHTML = ''; });

function modalHeader({ title, subtitle = '', avatarName, avatarKnown = true, badges = [], hero = false }) {
  return `<div class="modal__header ${hero ? 'modal__header--hero' : ''}">
    ${avatarName !== undefined ? avatar(avatarName, 'avatar--lg', avatarKnown) : ''}
    <div class="modal__titles">
      <h2 class="modal__title" id="modalTitle">${escapeHtml(title)}</h2>
      ${subtitle ? `<p class="modal__subtitle">${subtitle}</p>` : ''}
      ${badges.length ? `<div class="modal__badges">${badges.join('')}</div>` : ''}
    </div>
    <button class="icon-btn" type="button" data-close aria-label="Cerrar">${icon('x')}</button>
  </div>`;
}

function detailSection(title, items) {
  return `<section class="detail-section"><h3>${title}</h3><dl class="detail-grid">
    ${items.filter(Boolean).map(([label, value, full]) => `<div class="detail-item ${full ? 'detail-item--full' : ''}">
      <dt>${label}</dt><dd>${value ?? '—'}</dd></div>`).join('')}
  </dl></section>`;
}

const note = (text, tone = '') => `<p class="note ${tone ? `note--${tone}` : ''}">${icon(tone === 'warning' ? 'alert' : 'info')} <span>${text}</span></p>`;

function openDetail({ title, subtitle, avatarName, avatarKnown, badges, body, footer = [] }) {
  const html = `${modalHeader({ title, subtitle, avatarName, avatarKnown, badges, hero: true })}
    <div class="modal__body">${body}</div>
    <div class="modal__footer">
      ${footer.map((b, i) => `<button class="btn ${b.cls || 'btn--ghost'}" type="button" data-footer="${i}">
        ${b.icon ? icon(b.icon) : ''} ${b.label}</button>`).join('')}
      <button class="btn btn--primary" type="button" data-close>Cerrar</button>
    </div>`;
  openModal(html, {
    onMount: (root) => {
      $$('[data-footer]', root).forEach((btn) => {
        btn.addEventListener('click', () => footer[btn.dataset.footer].onClick());
      });
    },
  });
}

function fieldHtml(f, value) {
  const req = f.required ? ' <span class="req">*</span>' : '';
  const cls = `field ${f.full ? 'field--full' : ''}`;
  const hint = f.hint ? `<small class="field__hint">${f.hint}</small>` : '';
  const attrs = `name="${f.name}" ${f.required ? 'required' : ''} ${f.disabled ? 'disabled' : ''}
    ${f.maxlength ? `maxlength="${f.maxlength}"` : ''} ${f.min ? `min="${f.min}"` : ''} ${f.max ? `max="${f.max}"` : ''}
    ${f.autocomplete ? `autocomplete="${f.autocomplete}"` : ''}`;
  switch (f.type) {
    case 'select':
      return `<label class="${cls}"><span>${f.label}${req}</span>
        <select ${attrs}>
          ${f.placeholder ? `<option value="">${f.placeholder}</option>` : ''}
          ${f.options.map(([v, l]) => `<option value="${escapeHtml(v)}" ${String(value) === String(v) ? 'selected' : ''}>${escapeHtml(l)}</option>`).join('')}
        </select>${hint}</label>`;
    case 'checkbox':
      return `<label class="switch field--full"><input type="checkbox" ${attrs} ${value ? 'checked' : ''}>
        <span class="switch__track"></span><span class="switch__label">${f.label}</span></label>`;
    case 'textarea':
      return `<label class="${cls}"><span>${f.label}${req}</span>
        <textarea ${attrs} placeholder="${escapeHtml(f.placeholder || '')}">${escapeHtml(value ?? '')}</textarea>${hint}</label>`;
    case 'info':
      return `<div class="${cls} field--info"><span>${f.label}</span><output data-info="${f.name}">${value ?? ''}</output>${hint}</div>`;
    default:
      return `<label class="${cls}"><span>${f.label}${req}</span>
        <input type="${f.type || 'text'}" ${attrs} value="${escapeHtml(value ?? '')}" placeholder="${escapeHtml(f.placeholder || '')}">${hint}</label>`;
  }
}

/*
 * Formulario con validación, confirmación opcional y envío asíncrono.
 *   validate(data) → null | 'mensaje' | { message, fields }
 *   confirm(data)  → { message, label, tone } para pedir confirmación antes de enviar
 *   onSubmit(data) → promesa; si falla, el error se muestra en el formulario
 *   onChange(form) → para campos calculados
 */
function openForm({ title, subtitle, fields, values = {}, submitLabel = 'Guardar', validate, confirm, onSubmit, onChange }) {
  const html = `${modalHeader({ title, subtitle })}
    <form class="modal__form" novalidate>
      <div class="modal__body">
        <p class="form-error" role="alert"></p>
        <div class="confirm-strip" role="status" hidden></div>
        <div class="form-grid form-grid--flush">${fields.map((f) => fieldHtml(f, values[f.name])).join('')}</div>
      </div>
      <div class="modal__footer">
        <button class="btn btn--ghost" type="button" data-close>Cancelar</button>
        <button class="btn btn--ghost" type="button" data-back hidden>${icon('chevron-left')} Volver</button>
        <button class="btn btn--gold" type="submit">${icon('check')} <span data-label>${submitLabel}</span></button>
      </div>
    </form>`;

  openModal(html, {
    onMount: (root) => {
      const form = $('form', root);
      const errorBox = $('.form-error', root);
      const strip = $('.confirm-strip', root);
      const submit = $('[type="submit"]', root);
      const back = $('[data-back]', root);
      const cancel = $('[data-close].btn', root);
      let pending = null; // datos validados que esperan confirmación
      let busy = false;

      const showError = (message, bad = []) => {
        errorBox.innerHTML = message ? `${icon('alert')}<span>${escapeHtml(message)}</span>` : '';
        $$('[aria-invalid]', form).forEach((el) => el.removeAttribute('aria-invalid'));
        bad.forEach((name) => form.elements[name]?.setAttribute('aria-invalid', 'true'));
        if (bad[0]) form.elements[bad[0]]?.focus();
      };
      const lock = (on) => fields.forEach((f) => { const el = form.elements[f.name]; if (el && !f.disabled) el.disabled = on; });
      const setConfirming = (c) => {
        pending = c ? pending : null;
        strip.hidden = !c;
        back.hidden = !c;
        cancel.hidden = !!c;
        lock(!!c);
        submit.className = `btn ${c && c.tone === 'danger' ? 'btn--danger' : 'btn--gold'}`;
        $('[data-label]', submit).textContent = c ? c.label || 'Confirmar' : submitLabel;
        if (c) {
          strip.innerHTML = `${icon(c.tone === 'danger' ? 'alert' : 'info')}<div>${c.message}</div>`;
          strip.classList.toggle('confirm-strip--danger', c.tone === 'danger');
          $('.modal__body', root).scrollTop = 0; // el mensaje queda a la vista antes de confirmar
        }
      };

      if (onChange) {
        form.addEventListener('input', () => onChange(form));
        onChange(form);
      }
      back.addEventListener('click', () => setConfirming(null));

      form.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (busy) return;
        let data = pending;
        if (!data) {
          showError('');
          data = {};
          fields.filter((f) => f.type !== 'info').forEach((f) => {
            const el = form.elements[f.name];
            data[f.name] = f.type === 'checkbox' ? el.checked : el.value.trim();
          });
          const missing = fields.filter((f) => f.required && !data[f.name]);
          if (missing.length) return showError(`Completa los campos obligatorios: ${missing.map((f) => f.label).join(', ')}.`, missing.map((f) => f.name));
          const emailField = fields.find((f) => f.type === 'email' && data[f.name]);
          if (emailField && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data[emailField.name])) return showError('El correo no tiene un formato válido.', [emailField.name]);
          const res = validate?.(data);
          if (res) return showError(res.message || res, res.fields || []);
          if (confirm) {
            pending = data;
            setConfirming(confirm(data));
            submit.focus();
            return;
          }
        }
        busy = true;
        setBusy(submit, true);
        back.disabled = true;
        try {
          await onSubmit(data);
          closeModal();
        } catch (err) {
          if (err?.expired) { closeModal(); sessionExpired(err.message); return; }
          setConfirming(null);
          showError(err?.message || 'No se pudo completar la operación.');
        } finally {
          busy = false;
          setBusy(submit, false);
          back.disabled = false;
        }
      });
    },
  });
}

function openConfirm({ title, message, confirmLabel = 'Confirmar', tone = 'danger', iconName = 'alert', onConfirm }) {
  const html = `<div class="modal__body confirm">
      <div class="confirm__row">
        <span class="confirm-icon ${tone === 'gold' ? 'confirm-icon--gold' : ''}">${icon(iconName)}</span>
        <div>
          <h2 class="modal__title" id="modalTitle">${escapeHtml(title)}</h2>
          <p class="confirm__text">${message}</p>
          <p class="form-error" role="alert"></p>
        </div>
      </div>
    </div>
    <div class="modal__footer">
      <button class="btn btn--ghost" type="button" data-close>Cancelar</button>
      <button class="btn ${tone === 'gold' ? 'btn--gold' : 'btn--danger'}" type="button" data-confirm>${confirmLabel}</button>
    </div>`;
  openModal(html, {
    size: 'sm',
    onMount: (root) => {
      const btn = $('[data-confirm]', root);
      btn.addEventListener('click', async () => {
        setBusy(btn, true);
        try {
          await onConfirm();
          closeModal();
        } catch (err) {
          if (err?.expired) { closeModal(); sessionExpired(err.message); return; }
          $('.form-error', root).innerHTML = `${icon('alert')}<span>${escapeHtml(err?.message || 'No se pudo completar.')}</span>`;
        } finally {
          setBusy(btn, false);
        }
      });
    },
  });
}

// =============================================================================
// Operaciones (todas pasan por backend(): RPC en Supabase o su equivalente en la demo)
// =============================================================================
async function afterWrite(message) {
  try {
    await reload();
  } catch (err) {
    handleError(err, 'Se guardó, pero no se pudo actualizar la vista');
  }
  toast(message);
}

function openVisitForm(categoria) {
  if (!can('invitar')) return;
  const isExt = categoria === 'externo';
  const zonas = isExt ? Object.keys(ZONAS) : ['sala_vip', ...ZONAS_MIEMBRO];
  const horas = POLICY.accesoTemporalHoras;
  const vence = () => Date.now() + horas * HOUR;

  const fields = [
    { name: 'nombre', label: isExt ? 'Nombre del trabajador' : 'Nombre del invitado', required: true, full: true, maxlength: 80, autocomplete: 'off' },
    { name: 'email', label: 'Correo', type: 'email', required: true, maxlength: 120, autocomplete: 'off', hint: 'Solo para identificar la visita. Se borra con sus datos al vencer.' },
  ];
  if (isExt) {
    fields.push({ name: 'empresa', label: 'Empresa', required: true, maxlength: 80 });
    fields.push({ name: 'motivo', label: 'Motivo del ingreso', required: true, full: true, maxlength: 120, placeholder: 'Ej.: mantenimiento preventivo' });
  } else {
    fields.push({ name: 'motivo', label: 'Motivo', maxlength: 120, placeholder: 'Ej.: almuerzo de negocios' });
  }
  fields.push(
    { name: 'destino', label: 'Destino', type: 'select', required: true, placeholder: 'Selecciona…', options: zonas.map((z) => [z, zoneName(z)]) },
    { name: 'inicio', label: 'Válido desde', type: 'datetime-local', required: true, hint: `Debe estar dentro de las ${horas} h siguientes al registro.` },
    { name: 'vence', label: 'El acceso vence', type: 'info', full: true, hint: `Exactamente ${horas} h después del registro. Luego el servidor borra sus datos personales.` },
  );

  openForm({
    title: isExt ? 'Registrar trabajador externo' : 'Nueva invitación',
    subtitle: `El responsable será tu cuenta. ${isExt ? 'El externo siempre ingresa acompañado.' : 'El QR solo sirve para el destino elegido.'}`,
    fields,
    values: { inicio: toLocalInput(Date.now()), vence: fmtDateTime(vence()) },
    submitLabel: isExt ? 'Revisar registro' : 'Revisar invitación',
    onChange: (form) => { $('[data-info="vence"]', form).textContent = `${fmtDateTime(vence())} (${dateFmt.format(vence())})`; },
    validate: (d) => {
      if (d.nombre.length < 3) return { message: 'Escribe el nombre completo.', fields: ['nombre'] };
      const ini = new Date(d.inicio).getTime();
      if (Number.isNaN(ini)) return { message: 'La fecha de inicio no es válida.', fields: ['inicio'] };
      if (ini < Date.now() - 5 * MIN) return { message: 'El inicio no puede estar en el pasado.', fields: ['inicio'] };
      if (ini >= vence() - 15 * MIN) return { message: `El inicio debe ser al menos 15 min antes del vencimiento (${fmtDateTime(vence())}).`, fields: ['inicio'] };
      if (!isExt && d.destino === 'sala_vip' && session.rol !== 'admin' && account()?.vinculo !== 'vip') {
        return { message: 'La Sala VIP solo admite invitados de miembros VIP o de administración.', fields: ['destino'] };
      }
      return null;
    },
    confirm: (d) => ({
      message: `Se creará el acceso de <strong>${escapeHtml(d.nombre)}</strong> (${isExt ? `${escapeHtml(d.empresa)}, externo` : 'invitado'})
        a <strong>${escapeHtml(zoneName(d.destino))}</strong>, desde ${fmtDateTime(new Date(d.inicio).getTime())}
        hasta ${fmtDateTime(vence())}. El código QR se mostrará <strong>una sola vez</strong>.`,
      label: isExt ? 'Registrar externo' : 'Crear invitación',
    }),
    onSubmit: async (d) => {
      const fin = vence();
      const res = await backend().crearInvitacion({ ...d, categoria, inicio: new Date(d.inicio).getTime(), fin });
      if (!res?.visita_id || !res.token) throw new Error('Respuesta inesperada del servidor al crear la invitación.');
      try { await reload(); } catch (err) { handleError(err, 'La invitación se creó, pero no se pudo actualizar la vista'); }
      const v = state[isExt ? 'externos' : 'invitados'].find((x) => x.id === res.visita_id);
      // Se abre después de que openForm cierre su ventana.
      setTimeout(() => openPassResult({
        categoria, token: res.token, visitaId: res.visita_id, nombre: d.nombre, empresa: d.empresa || null,
        destino: d.destino, motivo: d.motivo || null, desde: v?.inicio ?? new Date(d.inicio).getTime(), hasta: v?.fin ?? fin,
      }), 0);
    },
  });
}

// El token solo existe en esta ventana: no se guarda ni se vuelve a pedir a la base.
function openPassResult(p) {
  const pass = {
    v: 1,
    kind: isLive() ? 'real' : 'demo',
    tipo: p.categoria,
    token: p.token,
    nombre: p.nombre,
    empresa: p.empresa,
    anfitrion: account()?.nombre || 'N Club',
    destino: p.destino,
    motivo: p.motivo,
    desde: iso(p.desde),
    hasta: iso(p.hasta),
    visitaId: p.visitaId,
  };
  const code = encodePassCode(pass);
  const svg = qrSvg(p.token);
  const html = `${modalHeader({ title: p.categoria === 'externo' ? 'Externo registrado' : 'Invitación creada', subtitle: `${escapeHtml(p.nombre)} · ${escapeHtml(zoneName(p.destino))}` })}
    <div class="modal__body">
      ${note('Este QR y el código de pase <strong>solo se muestran ahora</strong>: la base guarda únicamente el hash del token. Si se pierden, revoca la visita y crea una nueva.', 'warning')}
      <div class="pass-result">
        ${svg ? `<div class="pass-result__qr">${svg}</div>` : '<p class="cell-muted">No se pudo generar la imagen del QR (sin conexión). Usa el código de pase.</p>'}
        <div class="pass-result__info">
          ${detailSection('Acceso', [
            ['Válido desde', fmtDateTime(p.desde)],
            ['Vence', `${fmtDateTime(p.hasta)} (24 h tras el registro)`],
            ['Destino', escapeHtml(zoneName(p.destino))],
            ['Responsable', escapeHtml(pass.anfitrion)],
          ])}
          <label class="field field--full"><span>Código de pase (se abre en la app, pantalla «Pase»)</span>
            <textarea readonly rows="3" class="cell-mono" data-code>${escapeHtml(code)}</textarea></label>
          <div class="pass-result__actions">
            <button class="btn btn--gold btn--sm" type="button" data-copy="code">${icon('copy')} Copiar código de pase</button>
            <button class="btn btn--ghost btn--sm" type="button" data-copy="token">${icon('copy')} Copiar token</button>
          </div>
        </div>
      </div>
      ${isLive() ? '' : note('Demostración: el token es aleatorio y no funciona en recepción.')}
    </div>
    <div class="modal__footer"><button class="btn btn--primary" type="button" data-close data-done>Listo, ya lo compartí</button></div>`;
  openModal(html, {
    autofocus: '[data-done]',
    onMount: (root) => {
      $('[data-copy="code"]', root).addEventListener('click', () => copyText(code, 'Código de pase'));
      $('[data-copy="token"]', root).addEventListener('click', () => copyText(p.token, 'Token'));
      $('[data-code]', root).addEventListener('focus', (e) => e.target.select());
    },
  });
}

function revokeVisit(v) {
  if (!can('revocar') || !activeVisit(v)) return;
  openForm({
    title: v.categoria === 'externo' ? 'Cancelar el ingreso del externo' : 'Revocar la invitación',
    subtitle: `${escapeHtml(v.nombre)} · ${escapeHtml(zoneName(v.destino))}`,
    fields: [{ name: 'motivo', label: 'Motivo (opcional)', type: 'textarea', full: true, maxlength: 200, placeholder: 'Ej.: el anfitrión canceló la visita' }],
    submitLabel: 'Continuar',
    confirm: () => ({
      message: `La visita quedará <strong>cancelada</strong> y su QR dejará de funcionar de inmediato. Esta acción no se puede deshacer:
        para volver a dar acceso hay que crear otra invitación.`,
      label: 'Revocar acceso',
      tone: 'danger',
    }),
    onSubmit: async (d) => {
      await backend().revocarInvitacion(v.id, d.motivo);
      await afterWrite('Visita cancelada y QR revocado.');
    },
  });
}

function openCorrection(e) {
  if (!can('corregir_eventos') || e.resultado !== 'pendiente_revision') return;
  const candidate = e.persona_id ? findPerson(e.persona_id) : null;
  const fields = [
    { name: 'categoria', label: 'Categoría confirmada', type: 'select', required: true, full: true, placeholder: 'Selecciona una categoría', options: optionsFrom(CATEGORIAS) },
    { name: 'motivo', label: 'Motivo de la corrección', type: 'textarea', required: true, full: true, maxlength: POLICY.motivoMax,
      placeholder: 'Ej.: identidad confirmada con documento en recepción.',
      hint: `Máx. ${POLICY.motivoMax} caracteres. No escribas datos personales innecesarios (documentos, teléfonos).` },
  ];
  if (candidate) fields.push({ name: 'confirmar', type: 'checkbox', label: `Confirmo que la persona es ${escapeHtml(candidate.nombre)}` });

  openForm({
    title: 'Corregir evento',
    subtitle: `${shortId(e.id)} · ${escapeHtml(MOTIVOS[e.motivo] || e.motivo || '')}. La evidencia original no se modifica.`,
    fields,
    values: { categoria: candidate?.categoria || candidate?.vinculo || '', confirmar: true },
    submitLabel: 'Revisar corrección',
    validate: (d) => (d.motivo.length < 5 ? { message: 'Describe el motivo de la corrección.', fields: ['motivo'] } : null),
    confirm: (d) => ({
      message: `El evento quedará como <strong>corregido</strong> (${escapeHtml(CATEGORIAS[d.categoria].label)})${d.confirmar && candidate ? ` y ligado a ${escapeHtml(candidate.nombre)}` : ''}.
        La corrección queda registrada con tu cuenta.`,
      label: 'Guardar corrección',
    }),
    onSubmit: async (d) => {
      const personaId = d.confirmar && candidate ? (candidate.persona_id || candidate.id) : null;
      await backend().corregirEvento(e.id, d.categoria, d.motivo, personaId);
      await afterWrite('Evento corregido. El robot puede continuar con la orientación.');
    },
  });
}

function changeRole(p) {
  if (!canChangeRole(p)) return;
  const options = Object.entries(ROLES)
    .filter(([r]) => session.rol === 'admin' || r !== 'admin')
    .map(([r, v]) => [r, v.label]);
  openForm({
    title: 'Cambiar rol',
    subtitle: `${escapeHtml(p.nombre)} · ${escapeHtml(p.email || '')}`,
    fields: [{
      name: 'rol', label: 'Rol', type: 'select', required: true, full: true, options,
      hint: 'Operador: recepción. Informática: cuentas y soporte, sin acceso a invitados. Administración: todo.',
    }],
    values: { rol: p.rol },
    submitLabel: 'Revisar cambio',
    validate: (d) => (d.rol === p.rol ? { message: 'Elige un rol distinto del actual.', fields: ['rol'] } : null),
    confirm: (d) => ({
      message: `El rol de <strong>${escapeHtml(p.nombre)}</strong> pasará de ${ROLES[p.rol].label} a <strong>${ROLES[d.rol].label}</strong>.
        Afecta lo que puede ver y hacer en la app y en el panel. Queda en la auditoría.`,
      label: 'Cambiar rol',
      tone: d.rol === 'admin' || p.rol === 'admin' ? 'danger' : undefined,
    }),
    onSubmit: async (d) => {
      await backend().asignarRol(p.id, d.rol);
      await afterWrite(`${escapeHtml(p.nombre)} ahora tiene el rol ${ROLES[d.rol].label}.`);
    },
  });
}

function editPerson(p) {
  if (!can('editar_personas')) return;
  const isStaff = p.vinculo === 'personal';
  const fields = [
    { name: 'estado', label: 'Estado', type: 'select', options: optionsFrom(ESTADOS_PERSONA) },
    { name: 'vinculo', label: 'Vínculo', type: 'select', options: Object.entries(VINCULOS), hint: 'Al dejar de ser personal, el rol vuelve a «Usuario».' },
    { name: 'horario_inicio', label: 'Ingreso desde', type: 'time', required: true },
    { name: 'horario_fin', label: 'Ingreso hasta', type: 'time', required: true },
    { name: 'vinculo_hasta', label: 'Vigencia del vínculo', type: 'date', hint: 'Último día de la membresía o del contrato.' },
    { name: 'sin_vencimiento', type: 'checkbox', label: 'Sin vencimiento' },
    { name: 'requiere_tour', type: 'checkbox', label: 'Requiere recorrido de bienvenida (solo regulares)' },
  ];
  const values = { ...p, sin_vencimiento: !p.vinculo_hasta, vinculo_hasta: p.vinculo_hasta || '' };
  const labels = { estado: 'Estado', vinculo: 'Vínculo', horario_inicio: 'Desde', horario_fin: 'Hasta', vinculo_hasta: 'Vigencia', requiere_tour: 'Recorrido' };
  const changes = (d) => {
    const c = {};
    ['estado', 'vinculo', 'horario_inicio', 'horario_fin'].forEach((k) => { if (d[k] !== p[k]) c[k] = d[k]; });
    if (d.sin_vencimiento && p.vinculo_hasta) c.sin_vencimiento = true;
    if (!d.sin_vencimiento && d.vinculo_hasta && d.vinculo_hasta !== p.vinculo_hasta) c.vinculo_hasta = d.vinculo_hasta;
    if (d.vinculo === 'regular' && d.requiere_tour !== p.requiere_tour) c.requiere_tour = d.requiere_tour;
    return c;
  };

  openForm({
    title: `Editar ${p.nombre}`,
    subtitle: `${isStaff ? 'Personal' : 'Miembro'} · ${shortId(p.id)}. Los datos personales los edita la propia persona en la app.`,
    fields,
    values,
    submitLabel: 'Revisar cambios',
    validate: (d) => {
      if (Object.keys(changes(d)).length === 0) return 'No hay cambios para guardar.';
      if (d.estado === 'suspendida' && p.id === session.accountId) return { message: 'No puedes suspender tu propia cuenta.', fields: ['estado'] };
      const [lo, hi] = d.vinculo === 'personal' ? POLICY.personal : POLICY.miembros;
      if (d.horario_fin <= d.horario_inicio) return { message: 'La hora final debe ser posterior a la inicial.', fields: ['horario_fin'] };
      if (d.horario_inicio < lo || d.horario_fin > hi) return { message: `Para ${d.vinculo === 'personal' ? 'el personal' : 'miembros'} el horario debe estar entre ${lo} y ${hi}.`, fields: ['horario_inicio', 'horario_fin'] };
      if (d.vinculo === 'personal' && toMinutes(d.horario_fin) - toMinutes(d.horario_inicio) > POLICY.turnoMaxHoras * 60) {
        return { message: `El turno no puede superar ${POLICY.turnoMaxHoras} horas.`, fields: ['horario_fin'] };
      }
      return null;
    },
    confirm: (d) => {
      const c = changes(d);
      const list = Object.entries(c).map(([k, v]) => (k === 'sin_vencimiento'
        ? '<li>Vigencia: sin vencimiento</li>'
        : `<li>${labels[k]}: <strong>${escapeHtml(k === 'requiere_tour' ? (v ? 'sí' : 'no') : (VINCULOS[v] || ESTADOS_PERSONA[v]?.label || v))}</strong></li>`)).join('');
      const warn = c.estado === 'suspendida' ? ' Recepción rechazará su ingreso desde ahora.' : '';
      const rolWarn = p.vinculo === 'personal' && c.vinculo && c.vinculo !== 'personal' && p.rol !== 'usuario' ? ` Perderá el rol ${ROLES[p.rol].label}.` : '';
      return { message: `Se guardarán estos cambios para ${escapeHtml(p.nombre)}:<ul>${list}</ul>${warn}${rolWarn} Quedan en la auditoría.`, label: 'Guardar cambios', tone: warn || rolWarn ? 'danger' : undefined };
    },
    onSubmit: async (d) => {
      await backend().actualizarPersona(p.id, changes(d));
      await afterWrite('Cambios guardados.');
    },
  });
}

function toggleSuspend(p) {
  if (!can('editar_personas')) return;
  const suspend = p.estado === 'activa';
  if (suspend && p.id === session.accountId) { toast('No puedes suspender tu propia cuenta.', 'danger'); return; }
  openConfirm({
    title: suspend ? `¿Suspender a ${p.nombre}?` : `¿Reactivar a ${p.nombre}?`,
    message: suspend
      ? 'Recepción rechazará su ingreso (por cara o QR) y, si es personal, perderá el acceso al panel. Sus datos se conservan.'
      : 'Podrá volver a ingresar al club en su horario.',
    confirmLabel: suspend ? 'Suspender' : 'Reactivar',
    tone: suspend ? 'danger' : 'gold',
    iconName: suspend ? 'ban' : 'check-circle',
    onConfirm: async () => {
      await backend().actualizarPersona(p.id, { estado: suspend ? 'suspendida' : 'activa' });
      await afterWrite(suspend ? `${escapeHtml(p.nombre)} quedó suspendido(a).` : `${escapeHtml(p.nombre)} fue reactivado(a).`);
    },
  });
}

// =============================================================================
// Detalles
// =============================================================================
function personEventsHtml(id) {
  const evs = state.eventos.filter((e) => e.persona_id === id).slice(0, 4);
  if (!evs.length) return '<p class="cell-muted">Sin eventos recientes en recepción.</p>';
  return `<ul class="mini-list mini-list--flush">${evs.map((e) => `<li class="mini-item">
      <span class="stat__icon">${icon(e.cara !== 'no_usada' ? 'face' : 'qr')}</span>
      <div class="mini-item__body">
        <div class="mini-item__title">${fmtDateTime(e.fecha)}</div>
        <div class="mini-item__meta">${isOk(e) ? escapeHtml(zoneName(e.destino)) : escapeHtml(MOTIVOS[e.motivo] || e.motivo || '')}</div>
      </div>
      ${badge(RESULTADOS, e.resultado)}
    </li>`).join('')}</ul>`;
}

function personFooter(p) {
  const footer = [];
  if (can('editar_personas')) {
    footer.push({ label: 'Editar', icon: 'edit', onClick: () => editPerson(p) });
    footer.push(p.estado === 'activa'
      ? { label: 'Suspender', icon: 'ban', cls: 'btn--ghost btn--danger-text', onClick: () => toggleSuspend(p) }
      : { label: 'Reactivar', icon: 'check-circle', onClick: () => toggleSuspend(p) });
  }
  if (canChangeRole(p)) footer.push({ label: 'Cambiar rol', icon: 'key', onClick: () => changeRole(p) });
  return footer;
}

function adminNote() {
  return session.rol === 'admin' && !session.caps.migracion
    ? note('Editar personas y asignar roles requiere aplicar las migraciones propuestas 008 y 009. Hoy la base no permite esos cambios desde el panel.')
    : '';
}

function vigenciaText(p) {
  if (!p.vinculo_hasta) return 'Sin vencimiento';
  const vencida = p.vinculo_hasta < dateOnly(Date.now());
  return `${vencida ? '<span class="badge badge--danger">Vencida</span> ' : ''}Hasta ${fmtDate(Date.parse(`${p.vinculo_hasta}T12:00:00`))}`;
}

function openPersonDetail(id) {
  const p = findPerson(id);
  if (!p) { toast('No hay datos visibles de esta persona.', 'info'); return; }
  if (p.categoria) { openVisitDetail(p); return; }
  const staff = p.vinculo === 'personal';
  const tour = p.vinculo === 'regular' ? ['Recorrido de bienvenida', p.requiere_tour ? 'Pendiente' : 'Completado'] : null;
  const body = [
    detailSection('Información', [
      ['ID', `<span class="cell-mono" title="${p.id}">${shortId(p.id)}</span>`],
      ['Registrado', fmtDate(p.miembro_desde)],
      ['Correo', escapeHtml(p.email || '—')],
      ['Teléfono', escapeHtml(p.telefono || '—')],
      ['Rol en la app', ROLES[p.rol]?.label ?? p.rol],
      ['Cuenta en la app', p.tiene_cuenta ? 'Vinculada' : 'Sin cuenta'],
    ]),
    detailSection(staff ? 'Turno y acceso' : 'Acceso', [
      [staff ? 'Turno' : 'Horario permitido', `${p.horario_inicio} – ${p.horario_fin}`],
      staff ? ['Ahora', inShift(p) ? '<span class="badge badge--success">En turno</span>' : '<span class="badge badge--neutral">Fuera de turno</span>'] : ['Visitas este mes', p.visitas_mes],
      ['Último acceso', p.ultimo_acceso ? `${fmtDateTime(p.ultimo_acceso)} <span class="cell-muted">(${fmtRelative(p.ultimo_acceso)})</span>` : 'Sin accesos en los últimos 30 días'],
      ['Vigencia del vínculo', vigenciaText(p)],
      tour,
      ['Reconocimiento facial', p.biometria ? `Consentimiento otorgado · ${fmtDate(p.consentimiento_fecha)}` : 'Sin consentimiento (ingresa con QR)', !tour],
    ]),
    `<section class="detail-section"><h3>Últimos eventos</h3>${personEventsHtml(p.id)}</section>`,
    `<section class="detail-section"><h3>Credencial</h3>${credentialBox(p.credencial, 'El QR lo genera la persona en la app; el panel no lee el token ni su hash.')}</section>`,
    adminNote(),
  ].join('');

  openDetail({
    title: p.nombre,
    subtitle: `${staff ? 'Personal del club' : `Miembro ${VINCULOS[p.vinculo]}`} · ${shortId(p.id)}`,
    avatarName: p.nombre,
    badges: [badge(CATEGORIAS, p.vinculo), badge(ESTADOS_PERSONA, p.estado), badge(ROLES, p.rol)],
    body,
    footer: personFooter(p),
  });
}

function openVisitDetail(v) {
  const isExt = v.categoria === 'externo';
  const host = findPerson(v.responsable_id);
  const active = activeVisit(v);
  const body = [
    detailSection('Visita', [
      ['ID de visita', `<span class="cell-mono" title="${v.id}">${shortId(v.id)}</span>`],
      ['Estado', badge(ESTADOS_VISITA, v.estado)],
      isExt ? ['Empresa', escapeHtml(v.empresa)] : ['Correo', escapeHtml(v.email || '—')],
      [isExt ? 'Responsable' : 'Anfitrión', host ? `${escapeHtml(host.nombre)} ${badge(CATEGORIAS, host.vinculo)}` : '—'],
      ['Destino', escapeHtml(zoneName(v.destino))],
      ['Ventana de acceso', fmtWindow(v.inicio, v.fin)],
      ['Motivo', escapeHtml(v.motivo || '—'), true],
    ]),
    detailSection('Vigencia y datos', [
      ['Registrada', fmtDateTime(v.creado_en)],
      ['Pierde la autorización', `${fmtDateTime(v.fin)} <span class="cell-muted">(${fmtRelative(v.fin)})</span>`],
      ['Ingreso registrado', v.usado_en ? fmtDateTime(v.usado_en) : 'Aún no ingresa'],
      ['Nivel de ayuda', v.nivel_ayuda ? NIVELES_AYUDA[v.nivel_ayuda] : 'Se elige al llegar'],
    ]),
    note(`Al vencer, el servidor borra su nombre, correo, visita y QR en menos de ${POLICY.limpiezaMinutos} minutos, aunque esta página esté cerrada. Los eventos se conservan sin esos datos.`),
    isExt ? note('Los trabajadores externos siempre ingresan con acompañamiento del personal.') : '',
    active
      ? `<section class="detail-section"><h3>QR de visita</h3>${credentialBox(v.credencial, 'El token se entregó una sola vez al crear la invitación; para reenviarlo hay que revocar y crear otra.')}</section>`
      : '',
  ].join('');

  const footer = [];
  if (active && can('revocar')) footer.push({ label: 'Revocar acceso', icon: 'ban', cls: 'btn--ghost btn--danger-text', onClick: () => revokeVisit(v) });

  openDetail({
    title: v.nombre,
    subtitle: isExt ? `${escapeHtml(v.empresa)} · ${shortId(v.id)}` : `Invitado de ${escapeHtml(host?.nombre ?? '—')} · ${shortId(v.id)}`,
    avatarName: v.nombre,
    badges: [badge(CATEGORIAS, v.categoria), badge(ESTADOS_VISITA, v.estado)],
    body,
    footer,
  });
}

function openEventDetail(e) {
  if (!e) return;
  const body = [
    `<section class="detail-section"><h3>Evidencia</h3><div class="evidence">
      <div class="evidence__item"><small>Cara</small><strong>${escapeHtml(EVIDENCIA_CARA[e.cara] || e.cara)}</strong>
        <small>${e.distancia != null ? `Distancia ${e.distancia.toFixed(3)}` : 'Sin lectura facial'}${e.modo ? ` · ${e.modo}` : ''}</small></div>
      <div class="evidence__item"><small>QR</small><strong>${escapeHtml(EVIDENCIA_QR[e.qr] || e.qr)}</strong>
        <small>${e.qr === 'no_presentado' ? 'No se presentó credencial' : 'Credencial leída'}</small></div>
      <div class="evidence__item"><small>Fuente</small><strong>${e.fuente === 'robot' ? 'Robot de recepción' : 'Simulación'}</strong>
        <small>${e.duracion_ms != null ? `Atención: ${(e.duracion_ms / 1000).toFixed(1)} s` : 'Sin duración registrada'}</small></div>
    </div></section>`,
    detailSection('Resolución', [
      ['Resultado', badge(RESULTADOS, e.resultado)],
      ['Categoría', categoryBadge(e.categoria)],
      ['Motivo', e.motivo ? escapeHtml(MOTIVOS[e.motivo] || e.motivo) : '—'],
      ['Fecha y hora', `${fmtDate(e.fecha)} · ${fmtTime(e.fecha)}`],
      ['Destino', e.destino ? escapeHtml(zoneName(e.destino)) : '—'],
      ['Nivel de ayuda', e.nivel_ayuda ? NIVELES_AYUDA[e.nivel_ayuda] : '—'],
    ]),
    e.resultado === 'corregido' ? detailSection('Corrección de recepción', [
      ['Corregido por', escapeHtml(e.corregido_por || '—')],
      ['Fecha', fmtDateTime(e.corregido_en)],
      ['Motivo', escapeHtml(e.correccion_motivo || '—'), true],
    ]) : '',
    note(`La evidencia guarda estados y distancias, nunca imágenes. A los ${POLICY.eventosDesvincularDias} días el evento pierde sus datos personales y a los ${POLICY.eventosEliminarDias} se elimina (política propuesta).`),
  ].join('');

  const footer = [];
  if (findPerson(e.persona_id)) footer.push({ label: 'Ver persona', icon: 'eye', onClick: () => openPersonDetail(e.persona_id) });
  if (e.resultado === 'pendiente_revision' && can('corregir_eventos')) footer.push({ label: 'Corregir evento', icon: 'edit', cls: 'btn--gold', onClick: () => openCorrection(e) });

  openDetail({
    title: e.persona,
    subtitle: `Evento ${shortId(e.id)} · ${fmtRelative(e.fecha)}`,
    avatarName: e.persona,
    avatarKnown: !!e.persona_id,
    badges: [badge(RESULTADOS, e.resultado), categoryBadge(e.categoria)],
    body,
    footer,
  });
}

// =============================================================================
// Tablas: configuración por sección
// =============================================================================
const personActions = (p) => [
  { act: 'view', icon: 'eye', label: 'Ver detalle' },
  can('editar_personas') && { act: 'edit', icon: 'edit', label: 'Editar', tone: 'gold' },
  can('editar_personas') && (p.estado === 'activa'
    ? { act: 'toggle', icon: 'ban', label: 'Suspender', tone: 'danger' }
    : { act: 'toggle', icon: 'check-circle', label: 'Reactivar', tone: 'success' }),
].filter(Boolean);

const visitActions = (v) => [
  { act: 'view', icon: 'eye', label: 'Ver detalle' },
  can('revocar') && activeVisit(v) && { act: 'revoke', icon: 'ban', label: 'Revocar acceso', tone: 'danger' },
].filter(Boolean);

const personHandlers = { view: (p) => openPersonDetail(p.id), edit: editPerson, toggle: toggleSuspend };
const visitHandlers = { view: openVisitDetail, revoke: revokeVisit };

const lastAccessCol = {
  key: 'ultimo_acceso',
  label: 'Último acceso',
  render: (p) => `<span class="cell-nowrap" title="${fmtDateTime(p.ultimo_acceso)}">${p.ultimo_acceso ? fmtRelative(p.ultimo_acceso) : '—'}</span>`,
  sortValue: (p) => p.ultimo_acceso || 0,
  csv: (p) => iso(p.ultimo_acceso) || '',
};
const estadoPersonaCol = {
  key: 'estado', label: 'Estado',
  render: (p) => `${badge(ESTADOS_PERSONA, p.estado)}${p.vinculo_hasta && p.vinculo_hasta < dateOnly(Date.now()) ? ' <span class="badge badge--danger badge--plain">Vencida</span>' : ''}`,
};
const contactCol = {
  key: 'email', label: 'Contacto',
  render: (p) => `<div>${escapeHtml(p.email || '—')}</div><div class="cell-muted">${escapeHtml(p.telefono || '')}</div>`,
  csv: (p) => p.email,
};
const horarioCol = { key: 'horario_inicio', label: 'Horario', render: (p) => `<span class="cell-nowrap">${p.horario_inicio} – ${p.horario_fin}</span>` };
const identCol = { key: 'biometria', label: 'Identificación', render: identCell, sortValue: (p) => (p.biometria ? 1 : 0), csv: (p) => (p.biometria ? 'Cara + QR' : 'Solo QR') };
const windowCol = {
  key: 'inicio', label: 'Ventana', render: (v) => `<span class="cell-nowrap">${fmtWindow(v.inicio, v.fin)}</span>`,
  csv: (v) => `${iso(v.inicio)} - ${iso(v.fin)}`,
};
const venceCol = {
  key: 'fin', label: 'Vence',
  render: (v) => (activeVisit(v) ? `<span class="cell-nowrap">${fmtRelative(v.fin)}</span>` : '<span class="cell-muted">—</span>'),
  csv: (v) => iso(v.fin),
};
const destinoCol = { key: 'destino', label: 'Destino', render: (v) => `<span class="cell-nowrap">${escapeHtml(zoneName(v.destino))}</span>`, sortValue: (v) => zoneName(v.destino) };
const estadoVisitaCol = { key: 'estado', label: 'Estado', render: (v) => badge(ESTADOS_VISITA, v.estado) };

const filterEstadoPersona = { key: 'estado', label: 'Todos los estados', options: optionsFrom(ESTADOS_PERSONA) };
const filterBiometria = {
  key: 'biometria', label: 'Toda identificación', options: [['si', 'Cara + QR'], ['no', 'Solo QR']],
  test: (p, v) => p.biometria === (v === 'si'),
};
const filterEstadoVisita = { key: 'estado', label: 'Todos los estados', options: optionsFrom(ESTADOS_VISITA) };

function memberStats(list, label) {
  const activos = list.filter((m) => m.estado === 'activa').length;
  const bio = list.filter((m) => m.biometria).length;
  return [
    { label: `Total ${label}`, value: list.length, hint: `${list.length - activos} suspendidos`, icon: label === 'VIP' ? 'crown' : 'users', accent: true },
    { label: 'Activos', value: activos, hint: `${pct(activos, list.length)}% del total`, icon: 'check-circle', tone: 'success' },
    { label: 'Con reconocimiento facial', value: bio, hint: `${pct(bio, list.length)}% con consentimiento`, icon: 'face', tone: 'teal' },
  ];
}

function visitStats(list, isExt) {
  const enCurso = list.filter((v) => v.estado === 'en_curso').length;
  const prog = list.filter((v) => v.estado === 'programada').length;
  const soon = list.filter((v) => activeVisit(v) && v.fin - Date.now() < 3 * HOUR).length;
  return [
    { label: isExt ? 'En sitio ahora' : 'Visitas en curso', value: enCurso, hint: isExt ? 'Con acompañamiento' : 'Dentro del club', icon: isExt ? 'hardhat' : 'ticket', accent: true },
    { label: 'Programadas', value: prog, hint: 'Con QR vigente', icon: 'calendar', tone: 'gold' },
    { label: 'Vencen en menos de 3 h', value: soon, hint: '24 h tras su registro', icon: 'clock', tone: 'warning' },
    isExt
      ? { label: 'Empresas', value: new Set(list.map((v) => v.empresa)).size, hint: 'Proveedores distintos', icon: 'badge' }
      : { label: 'Canceladas', value: list.filter((v) => v.estado === 'cancelada').length, hint: 'QR revocado', icon: 'ban', tone: 'danger' },
  ];
}

const TABLES = {
  vip: {
    rows: () => state.vip,
    noun: ['miembro', 'miembros'],
    search: (p) => [p.id, p.nombre, p.email, p.telefono],
    filters: [filterEstadoPersona, filterBiometria],
    columns: [
      { key: 'nombre', label: 'Miembro', primary: true, render: (p) => personCell(p.nombre, shortId(p.id)), csv: (p) => p.nombre },
      contactCol, horarioCol, identCol,
      { key: 'visitas_mes', label: 'Visitas (mes)' },
      lastAccessCol, estadoPersonaCol,
    ],
    actions: personActions,
    handlers: personHandlers,
    stats: () => [
      ...memberStats(state.vip, 'VIP'),
      { label: 'Visitas este mes', value: state.vip.reduce((s, m) => s + m.visitas_mes, 0), hint: 'Suma de todos los VIP', icon: 'login', tone: 'gold' },
    ],
    exportName: 'miembros-vip',
  },

  regulares: {
    rows: () => state.regulares,
    noun: ['miembro', 'miembros'],
    search: (p) => [p.id, p.nombre, p.email, p.telefono],
    filters: [
      filterEstadoPersona,
      { key: 'requiere_tour', label: 'Todo recorrido', options: [['si', 'Recorrido pendiente'], ['no', 'Recorrido completado']], test: (p, v) => p.requiere_tour === (v === 'si') },
      filterBiometria,
    ],
    columns: [
      { key: 'nombre', label: 'Miembro', primary: true, render: (p) => personCell(p.nombre, shortId(p.id)), csv: (p) => p.nombre },
      contactCol, horarioCol, identCol,
      { key: 'requiere_tour', label: 'Recorrido', render: (p) => (p.requiere_tour ? '<span class="badge badge--warning">Pendiente</span>' : '<span class="badge badge--neutral">Completado</span>'), csv: (p) => (p.requiere_tour ? 'Pendiente' : 'Completado') },
      lastAccessCol, estadoPersonaCol,
    ],
    actions: personActions,
    handlers: personHandlers,
    stats: () => [
      ...memberStats(state.regulares, 'regulares'),
      { label: 'Recorrido pendiente', value: state.regulares.filter((m) => m.requiere_tour).length, hint: 'Miembros nuevos', icon: 'pin', tone: 'warning' },
    ],
    exportName: 'miembros-regulares',
  },

  invitados: {
    rows: () => state.invitados,
    noun: ['invitación', 'invitaciones'],
    placeholder: 'Buscar por invitado, anfitrión o ID…',
    search: (v) => [v.id, v.nombre, v.email, personName(v.responsable_id), v.motivo],
    filters: [filterEstadoVisita, { key: 'destino', label: 'Todos los destinos', options: ['sala_vip', ...ZONAS_MIEMBRO].map((z) => [z, zoneName(z)]) }],
    columns: [
      { key: 'nombre', label: 'Invitado', primary: true, render: (v) => personCell(v.nombre, escapeHtml(v.email || '')), csv: (v) => v.nombre },
      { key: 'responsable_id', label: 'Anfitrión', render: (v) => { const h = findPerson(v.responsable_id); return h ? `<div class="cell-nowrap">${escapeHtml(h.nombre)}</div><div>${badge(CATEGORIAS, h.vinculo)}</div>` : '—'; }, sortValue: (v) => personName(v.responsable_id), csv: (v) => personName(v.responsable_id) },
      destinoCol, windowCol, venceCol, estadoVisitaCol,
    ],
    actions: visitActions,
    handlers: visitHandlers,
    defaultSort: { key: 'inicio', dir: 'desc' },
    stats: () => visitStats(state.invitados, false),
    exportName: 'invitados',
  },

  personal: {
    rows: () => state.personal,
    noun: ['empleado', 'empleados'],
    placeholder: 'Buscar por nombre, correo o ID…',
    search: (p) => [p.id, p.nombre, p.email, ROLES[p.rol]?.label],
    filters: [{ key: 'rol', label: 'Todos los roles', options: optionsFrom(ROLES) }, filterEstadoPersona],
    columns: [
      { key: 'nombre', label: 'Empleado', primary: true, render: (p) => personCell(p.nombre, escapeHtml(p.email || '')), csv: (p) => p.nombre },
      { key: 'horario_inicio', label: 'Turno', render: (p) => `<div class="cell-nowrap">${p.horario_inicio} – ${p.horario_fin}</div>${inShift(p) ? '<div class="cell-muted">En turno ahora</div>' : ''}` },
      { key: 'rol', label: 'Rol', render: (p) => badge(ROLES, p.rol) },
      identCol, lastAccessCol, estadoPersonaCol,
    ],
    actions: personActions,
    handlers: personHandlers,
    stats: () => {
      const list = state.personal;
      return [
        { label: 'Total del personal', value: list.length, hint: `${list.filter((p) => p.estado === 'activa').length} activos`, icon: 'badge', accent: true },
        { label: 'En turno ahora', value: list.filter(inShift).length, hint: `Hora actual ${nowHHMM()}`, icon: 'clock', tone: 'success' },
        { label: 'Con rol de panel', value: list.filter((p) => PANEL_ROLES.includes(p.rol)).length, hint: 'Admin, informática u operador', icon: 'shield', tone: 'gold' },
        { label: 'Con reconocimiento facial', value: list.filter((p) => p.biometria).length, hint: 'Con consentimiento', icon: 'face', tone: 'teal' },
      ];
    },
    exportName: 'personal',
  },

  externos: {
    rows: () => state.externos,
    noun: ['registro', 'registros'],
    placeholder: 'Buscar por nombre, empresa o motivo…',
    search: (v) => [v.id, v.nombre, v.email, v.empresa, v.motivo, personName(v.responsable_id)],
    filters: [filterEstadoVisita, { key: 'destino', label: 'Todos los destinos', options: Object.keys(ZONAS).map((z) => [z, zoneName(z)]) }],
    columns: [
      { key: 'nombre', label: 'Trabajador', primary: true, render: (v) => personCell(v.nombre, escapeHtml(v.empresa || '')), csv: (v) => `${v.nombre} (${v.empresa})` },
      { key: 'motivo', label: 'Motivo', render: (v) => `<span class="cell-muted">${escapeHtml(v.motivo || '—')}</span>` },
      { key: 'responsable_id', label: 'Responsable', render: (v) => `<span class="cell-nowrap">${escapeHtml(personName(v.responsable_id))}</span>`, sortValue: (v) => personName(v.responsable_id), csv: (v) => personName(v.responsable_id) },
      destinoCol, windowCol, venceCol, estadoVisitaCol,
    ],
    actions: visitActions,
    handlers: visitHandlers,
    defaultSort: { key: 'inicio', dir: 'desc' },
    stats: () => visitStats(state.externos, true),
    exportName: 'externos',
  },

  historial: {
    rows: () => state.eventos,
    noun: ['evento', 'eventos'],
    pageSize: 10,
    placeholder: 'Buscar por persona o ID de evento…',
    search: (e) => [e.id, e.persona, MOTIVOS[e.motivo], zoneName(e.destino)],
    filters: [
      { key: 'resultado', label: 'Todos los resultados', options: optionsFrom(RESULTADOS) },
      { key: 'categoria', label: 'Todas las categorías', options: [...optionsFrom(CATEGORIAS), ['sin', 'Sin resolver']], test: (e, v) => (v === 'sin' ? !e.categoria : e.categoria === v) },
      { key: 'periodo', label: 'Últimos 30 días', options: [['24h', 'Últimas 24 horas'], ['7d', 'Últimos 7 días']], test: (e, v) => Date.now() - e.fecha <= (v === '24h' ? DAY : 7 * DAY) },
      { key: 'fuente', label: 'Toda fuente', options: [['robot', 'Robot'], ['simulacion', 'Simulación']] },
    ],
    columns: [
      { key: 'fecha', label: 'Fecha', render: (e) => `<div class="cell-nowrap">${fmtDateTime(e.fecha)}</div><div class="cell-muted">${fmtRelative(e.fecha)}</div>`, csv: (e) => iso(e.fecha) },
      { key: 'persona', label: 'Persona', primary: true, render: (e) => personCell(e.persona, `<span class="cell-mono">${shortId(e.id)}</span>`, !!e.persona_id) },
      { key: 'categoria', label: 'Categoría', render: (e) => categoryBadge(e.categoria), sortValue: (e) => e.categoria || 'zz', csv: (e) => CATEGORIAS[e.categoria]?.label || 'Sin resolver' },
      { key: 'cara', label: 'Método', render: (e) => `<span class="cell-icons" title="Cara: ${EVIDENCIA_CARA[e.cara] || e.cara} · QR: ${EVIDENCIA_QR[e.qr] || e.qr}">${icon('face', e.cara === 'reconocida' ? 'on' : '')}${icon('qr', e.qr === 'valida' ? 'on' : '')}</span>`, sortable: false, csv: (e) => `Cara: ${EVIDENCIA_CARA[e.cara] || e.cara} / QR: ${EVIDENCIA_QR[e.qr] || e.qr}` },
      { key: 'resultado', label: 'Resultado', render: (e) => badge(RESULTADOS, e.resultado), csv: (e) => RESULTADOS[e.resultado]?.label },
      { key: 'destino', label: 'Destino / motivo', render: (e) => (isOk(e) ? escapeHtml(zoneName(e.destino)) : `<span class="cell-muted">${escapeHtml(MOTIVOS[e.motivo] || e.motivo || '—')}</span>`), sortValue: (e) => (isOk(e) ? zoneName(e.destino) : MOTIVOS[e.motivo]), csv: (e) => (isOk(e) ? zoneName(e.destino) : MOTIVOS[e.motivo] || e.motivo) },
      { key: 'fuente', label: 'Fuente', render: (e) => `<span class="badge badge--plain badge--neutral">${e.fuente === 'robot' ? 'Robot' : 'Simulación'}</span>` },
    ],
    actions: (e) => [
      { act: 'view', icon: 'eye', label: 'Ver detalle' },
      e.resultado === 'pendiente_revision' && can('corregir_eventos') && { act: 'correct', icon: 'edit', label: 'Corregir', tone: 'gold' },
    ].filter(Boolean),
    handlers: { view: openEventDetail, correct: openCorrection },
    defaultSort: { key: 'fecha', dir: 'desc' },
    stats: () => {
      const last = state.eventos.filter((e) => Date.now() - e.fecha <= DAY);
      const ok = last.filter(isOk);
      const timed = ok.filter((e) => e.duracion_ms != null);
      const avg = timed.length ? timed.reduce((s, e) => s + e.duracion_ms, 0) / timed.length / 1000 : 0;
      return [
        { label: 'Eventos (24 h)', value: last.length, hint: `${state.eventos.length} en 30 días`, icon: 'history', accent: true },
        { label: 'Tasa de orientación', value: `${pct(ok.length, last.length)}%`, hint: 'Orientados o corregidos', icon: 'check-circle', tone: 'success' },
        { label: 'Pendientes de revisión', value: pendingEvents().length, hint: 'Esperan a recepción', icon: 'alert', tone: 'warning' },
        { label: 'Tiempo medio de atención', value: timed.length ? `${avg.toFixed(1)} s` : '—', hint: 'Por llegada orientada', icon: 'clock', tone: 'gold' },
      ];
    },
    exportName: 'historial-accesos',
  },

  usuarios: {
    rows: people,
    noun: ['cuenta', 'cuentas'],
    placeholder: 'Buscar por nombre, correo o ID…',
    search: (p) => [p.id, p.nombre, p.email, ROLES[p.rol]?.label],
    filters: [
      { key: 'rol', label: 'Todos los roles', options: optionsFrom(ROLES) },
      { key: 'vinculo', label: 'Todo vínculo', options: Object.entries(VINCULOS) },
      { key: 'cuenta', label: 'Con y sin cuenta', options: [['si', 'Con cuenta en la app'], ['no', 'Sin cuenta']], test: (p, v) => p.tiene_cuenta === (v === 'si') },
      filterEstadoPersona,
    ],
    columns: [
      { key: 'nombre', label: 'Persona', primary: true, render: (p) => personCell(p.nombre, escapeHtml(p.email || '')), csv: (p) => p.nombre },
      { key: 'vinculo', label: 'Vínculo', render: (p) => badge(CATEGORIAS, p.vinculo) },
      { key: 'rol', label: 'Rol', render: (p) => badge(ROLES, p.rol), sortValue: (p) => ['admin', 'informatica', 'operador', 'usuario'].indexOf(p.rol) },
      {
        key: 'tiene_cuenta', label: 'Cuenta en la app',
        render: (p) => (p.tiene_cuenta ? '<span class="badge badge--success badge--plain">Vinculada</span>' : '<span class="badge badge--neutral badge--plain">Sin cuenta</span>'),
        sortValue: (p) => (p.tiene_cuenta ? 1 : 0), csv: (p) => (p.tiene_cuenta ? 'Vinculada' : 'Sin cuenta'),
      },
      estadoPersonaCol,
    ],
    actions: (p) => [
      { act: 'view', icon: 'eye', label: 'Ver detalle' },
      canChangeRole(p) && { act: 'role', icon: 'key', label: 'Cambiar rol', tone: 'gold' },
    ].filter(Boolean),
    handlers: { view: (p) => openPersonDetail(p.id), role: changeRole },
    defaultSort: { key: 'rol', dir: 'asc' },
  },
};

// =============================================================================
// Motor de tablas (búsqueda, filtros, orden y paginación)
// =============================================================================
const tableState = {};

function initTable(key) {
  const cfg = TABLES[key];
  const root = $(`[data-table-root="${key}"]`);
  tableState[key] = { q: '', filters: {}, sort: cfg.defaultSort ? { ...cfg.defaultSort } : null, page: 1 };

  root.innerHTML = `
    <div class="toolbar">
      <label class="search">${icon('search')}
        <input class="input" type="search" data-role="search" aria-label="Buscar"
          placeholder="${cfg.placeholder || 'Buscar por nombre, correo o ID…'}">
      </label>
      ${cfg.filters.map((f) => `<select data-filter="${f.key}" aria-label="${f.label}">
        <option value="">${f.label}</option>
        ${f.options.map(([v, l]) => `<option value="${escapeHtml(v)}">${escapeHtml(l)}</option>`).join('')}
      </select>`).join('')}
      <button class="btn btn--ghost btn--sm" type="button" data-role="reset">Limpiar</button>
      ${cfg.exportName ? `<button class="btn btn--ghost btn--sm" type="button" data-role="export">${icon('download')} CSV</button>` : ''}
      <span class="toolbar__count" data-role="count"></span>
    </div>
    <div class="table-scroll">
      <table class="data-table">
        <thead><tr>
          ${cfg.columns.map((c) => (c.sortable === false
            ? `<th scope="col">${c.label}</th>`
            : `<th scope="col" class="is-sortable" data-sort="${c.key}"><span class="th-sort">${c.label}${icon('sort')}</span></th>`)).join('')}
          <th scope="col" class="col-actions">Acciones</th>
        </tr></thead>
        <tbody></tbody>
      </table>
    </div>
    <div class="table-footer">
      <span data-role="range"></span>
      <div class="pager" data-role="pager"></div>
    </div>`;

  const st = tableState[key];
  $('[data-role="search"]', root).addEventListener('input', (e) => { st.q = e.target.value; st.page = 1; renderRows(key); });
  $$('[data-filter]', root).forEach((sel) => sel.addEventListener('change', () => {
    st.filters[sel.dataset.filter] = sel.value;
    st.page = 1;
    renderRows(key);
  }));
  $('[data-role="reset"]', root).addEventListener('click', () => resetTable(key));
  $('[data-role="export"]', root)?.addEventListener('click', () => exportCsv(key));

  $('thead', root).addEventListener('click', (e) => {
    const th = e.target.closest('[data-sort]');
    if (!th) return;
    const k = th.dataset.sort;
    st.sort = st.sort?.key === k ? { key: k, dir: st.sort.dir === 'asc' ? 'desc' : 'asc' } : { key: k, dir: 'asc' };
    renderRows(key);
  });

  $('tbody', root).addEventListener('click', (e) => {
    const btn = e.target.closest('[data-act]');
    if (!btn) return;
    const row = cfg.rows().find((r) => r.id === btn.closest('tr').dataset.id);
    if (row) cfg.handlers[btn.dataset.act]?.(row);
  });

  $('[data-role="pager"]', root).addEventListener('click', (e) => {
    const btn = e.target.closest('[data-page]');
    if (!btn || btn.disabled) return;
    st.page = Number(btn.dataset.page);
    renderRows(key);
    root.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
}

function resetTable(key) {
  const root = $(`[data-table-root="${key}"]`);
  const st = tableState[key];
  st.q = '';
  st.filters = {};
  st.page = 1;
  $('[data-role="search"]', root).value = '';
  $$('[data-filter]', root).forEach((sel) => { sel.value = ''; });
  renderRows(key);
}

function setTableFilter(key, filterKey, value) {
  resetTable(key);
  tableState[key].filters[filterKey] = value;
  $(`[data-table-root="${key}"] [data-filter="${filterKey}"]`).value = value;
  renderRows(key);
}

function filteredRows(key) {
  const cfg = TABLES[key];
  const st = tableState[key];
  const q = normalize(st.q.trim());
  let rows = cfg.rows().filter((r) => {
    if (q && !normalize(cfg.search(r).join(' ')).includes(q)) return false;
    return cfg.filters.every((f) => {
      const v = st.filters[f.key];
      if (!v) return true;
      return f.test ? f.test(r, v) : String(r[f.key]) === v;
    });
  });
  if (st.sort) {
    const col = cfg.columns.find((c) => c.key === st.sort.key);
    const val = col?.sortValue || ((r) => r[st.sort.key]);
    const dir = st.sort.dir === 'asc' ? 1 : -1;
    rows = [...rows].sort((a, b) => {
      const x = val(a);
      const y = val(b);
      const res = typeof x === 'number' && typeof y === 'number'
        ? x - y
        : String(x ?? '').localeCompare(String(y ?? ''), 'es', { sensitivity: 'base' });
      return res * dir;
    });
  }
  return rows;
}

function renderRows(key) {
  const cfg = TABLES[key];
  const st = tableState[key];
  const root = $(`[data-table-root="${key}"]`);
  const rows = filteredRows(key);
  const size = cfg.pageSize || 8;
  const pages = Math.max(1, Math.ceil(rows.length / size));
  st.page = Math.min(st.page, pages);
  const start = (st.page - 1) * size;
  const slice = rows.slice(start, start + size);

  $('tbody', root).innerHTML = slice.length
    ? slice.map((r) => `<tr data-id="${r.id}">
        ${cfg.columns.map((c) => `<td data-label="${c.label}" class="${c.primary ? 'col-primary' : ''}">
          <div class="td-content">${c.render ? c.render(r) : escapeHtml(r[c.key] ?? '—')}</div></td>`).join('')}
        <td class="col-actions"><div class="row-actions">
          ${cfg.actions(r).map((a) => `<button class="act ${a.tone ? `act--${a.tone}` : ''}" type="button"
            data-act="${a.act}" title="${a.label}" aria-label="${a.label}">${icon(a.icon)}</button>`).join('')}
        </div></td>
      </tr>`).join('')
    : `<tr class="empty-row"><td colspan="${cfg.columns.length + 1}">
        <div class="empty">${icon('search')}<p>${cfg.rows().length ? 'No hay resultados con estos criterios.' : 'No hay registros todavía.'}</p></div></td></tr>`;

  $$('th[data-sort]', root).forEach((th) => {
    const sorted = st.sort?.key === th.dataset.sort;
    th.classList.toggle('is-sorted', sorted);
    th.setAttribute('aria-sort', sorted ? (st.sort.dir === 'asc' ? 'ascending' : 'descending') : 'none');
  });

  const [one, many] = cfg.noun;
  $('[data-role="count"]', root).textContent = `${rows.length} ${rows.length === 1 ? one : many}`;
  $('[data-role="range"]', root).textContent = rows.length ? `Mostrando ${start + 1}–${start + slice.length} de ${rows.length}` : 'Sin resultados';

  let first = Math.max(1, st.page - 2);
  const last = Math.min(pages, first + 4);
  first = Math.max(1, last - 4);
  const nums = [];
  for (let i = first; i <= last; i++) {
    nums.push(`<button type="button" data-page="${i}" class="${i === st.page ? 'is-current' : ''}" aria-label="Página ${i}">${i}</button>`);
  }
  $('[data-role="pager"]', root).innerHTML = `
    <button type="button" data-page="${st.page - 1}" ${st.page === 1 ? 'disabled' : ''} aria-label="Página anterior">${icon('chevron-left')}</button>
    ${nums.join('')}
    <button type="button" data-page="${st.page + 1}" ${st.page === pages ? 'disabled' : ''} aria-label="Página siguiente">${icon('chevron-right')}</button>`;
}

function renderStats(key) {
  const el = $(`[data-stats="${key}"]`);
  if (el && TABLES[key].stats) el.innerHTML = TABLES[key].stats().map(statCard).join('');
}

function exportCsv(key) {
  const cfg = TABLES[key];
  const rows = filteredRows(key);
  const tmp = document.createElement('div');
  const text = (html) => { tmp.innerHTML = html; return tmp.textContent.replace(/\s+/g, ' ').trim(); };
  const cell = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`;
  const lines = [
    ['ID', ...cfg.columns.map((c) => c.label)].map(cell).join(';'),
    ...rows.map((r) => [r.id, ...cfg.columns.map((c) => (c.csv ? c.csv(r) : c.render ? text(c.render(r)) : r[c.key]))].map(cell).join(';')),
  ];
  const blob = new Blob([`﻿${lines.join('\r\n')}`], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = Object.assign(document.createElement('a'), { href: url, download: `nclub-${cfg.exportName}-${isLive() ? 'supabase' : 'demo'}.csv` });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  toast(`Se exportaron ${rows.length} filas. Contiene datos personales: guárdalo solo lo necesario.`);
}

// =============================================================================
// Dashboard
// =============================================================================
function renderDashboard() {
  const now = Date.now();
  const last24 = state.eventos.filter((e) => now - e.fecha <= DAY);
  const ok24 = last24.filter(isOk);
  const inside = insideNow();
  const pending = pendingEvents();
  const todayStr = new Date().toDateString();

  const stats = [
    { label: 'Personas dentro ahora', value: inside.length, hint: 'Estimado con llegadas de las últimas 4 h', icon: 'users', accent: true },
    { label: 'Accesos orientados (24 h)', value: ok24.length, hint: `${pct(ok24.length, last24.length)}% de ${last24.length} llegadas`, icon: 'check-circle', tone: 'success' },
    { label: 'Rechazos (24 h)', value: last24.filter((e) => e.resultado === 'rechazado').length, hint: 'Horario, credencial o identidad', icon: 'ban', tone: 'danger' },
    { label: 'Pendientes de revisión', value: pending.length, hint: 'Esperan decisión de recepción', icon: 'alert', tone: 'warning' },
  ];
  if (can('ver_visitas')) {
    stats.push(
      { label: 'Invitados hoy', value: state.invitados.filter((v) => v.estado !== 'cancelada' && (v.estado === 'en_curso' || new Date(v.inicio).toDateString() === todayStr)).length, hint: `${state.invitados.filter((v) => v.estado === 'en_curso').length} en curso`, icon: 'ticket', tone: 'teal' },
      { label: 'Externos en sitio', value: state.externos.filter((v) => v.estado === 'en_curso').length, hint: 'Siempre acompañados', icon: 'hardhat', tone: 'gold' },
    );
  } else {
    stats.push(
      { label: 'Miembros activos', value: [...state.vip, ...state.regulares].filter((p) => p.estado === 'activa').length, hint: 'VIP y regulares', icon: 'users', tone: 'teal' },
      { label: 'Personal en turno', value: state.personal.filter(inShift).length, hint: `Hora actual ${nowHHMM()}`, icon: 'badge', tone: 'gold' },
    );
  }
  $('[data-stats="dashboard"]').innerHTML = stats.map(statCard).join('');

  const hourStart = new Date(now);
  hourStart.setMinutes(0, 0, 0);
  const buckets = [];
  for (let i = 11; i >= 0; i--) {
    const from = hourStart.getTime() - i * HOUR;
    const evs = state.eventos.filter((e) => e.fecha >= from && e.fecha < from + HOUR);
    buckets.push({ from, ok: evs.filter(isOk).length, bad: evs.filter((e) => !isOk(e)).length });
  }
  const max = Math.max(1, ...buckets.map((b) => b.ok + b.bad));
  $('#hourChart').innerHTML = buckets.map((b) => `
    <div class="bar" title="${fmtTime(b.from)}–${fmtTime(b.from + HOUR)}: ${b.ok} orientados, ${b.bad} rechazados o en revisión">
      <span class="bar__value">${b.ok + b.bad || ''}</span>
      <div class="bar__stack">
        <div class="bar__ok" style="height:${(b.ok / max) * 100}%"></div>
        <div class="bar__bad" style="height:${(b.bad / max) * 100}%"></div>
      </div>
      <span class="bar__label">${fmtTime(b.from).slice(0, 2)}h</span>
    </div>`).join('');

  $('#categoryList').innerHTML = Object.entries(CATEGORIAS).map(([key, c]) => {
    const n = ok24.filter((e) => e.categoria === key).length;
    return `<div class="progress-row">
      <div class="progress-row__top"><span>${c.label}</span><span>${n} · ${pct(n, ok24.length)}%</span></div>
      <div class="progress"><div class="progress__fill" style="width:${pct(n, ok24.length)}%;background:${c.color}"></div></div>
    </div>`;
  }).join('');

  $('#activityList').innerHTML = state.eventos.length
    ? state.eventos.slice(0, 8).map((e) => `
      <li class="activity__item" data-event="${e.id}" tabindex="0" role="button" aria-label="Ver evento de ${escapeHtml(e.persona)}">
        ${avatar(e.persona, '', !!e.persona_id)}
        <div class="activity__body">
          <div class="activity__title">${escapeHtml(e.persona)}</div>
          <div class="activity__meta">${e.cara !== 'no_usada' ? 'Reconocimiento facial' : e.qr !== 'no_presentado' ? 'Código QR' : '—'}
            · ${isOk(e) ? escapeHtml(zoneName(e.destino)) : escapeHtml(MOTIVOS[e.motivo] || e.motivo || '')}</div>
        </div>
        <div class="activity__side">
          ${badge(RESULTADOS, e.resultado)}
          <span class="activity__time">${fmtRelative(e.fecha)}</span>
        </div>
      </li>`).join('')
    : `<li class="empty">${icon('history')}<p>No hay eventos en los últimos 30 días.</p></li>`;

  const byZone = {};
  inside.forEach((e) => { byZone[e.destino] = (byZone[e.destino] || 0) + 1; });
  $('#zoneList').innerHTML = Object.entries(CAPACIDAD).map(([z, cap]) => {
    const n = byZone[z] || 0;
    const p = pct(n, cap);
    const tone = p >= 85 ? 'danger' : p >= 60 ? 'warning' : p >= 30 ? 'gold' : '';
    return `<div class="progress-row">
      <div class="progress-row__top"><span>${escapeHtml(zoneName(z))}</span><span>${n} / ${cap}</span></div>
      <div class="progress"><div class="progress__fill ${tone ? `progress__fill--${tone}` : ''}" style="width:${Math.min(100, p)}%"></div></div>
    </div>`;
  }).join('') || `<p class="empty">Sin zonas con capacidad definida.</p>`;

  $('#pendingList').innerHTML = pending.length
    ? pending.slice(0, 5).map((e) => `<li class="mini-item">
        ${avatar(e.persona, 'avatar--sm', !!e.persona_id)}
        <div class="mini-item__body">
          <div class="mini-item__title">${escapeHtml(e.persona)}</div>
          <div class="mini-item__meta">${escapeHtml(MOTIVOS[e.motivo] || e.motivo || '')} · ${fmtRelative(e.fecha)}</div>
        </div>
        <button class="btn btn--ghost btn--sm" type="button" data-review="${e.id}">${can('corregir_eventos') ? 'Revisar' : 'Ver'}</button>
      </li>`).join('')
    : `<li class="empty">${icon('check-circle')}<p>No hay eventos pendientes. Todo al día.</p></li>`;

  const avisos = unansweredAvisos();
  const telHref = (t) => `tel:${String(t).replace(/[^\d+]/g, '')}`;
  $('#avisosList').innerHTML = state.avisos === null
    ? `<li class="empty">${icon('info')}<p>Los avisos de llegada (migración 007) no están disponibles en este proyecto.</p></li>`
    : avisos.length
      ? avisos.map((a) => `<li class="mini-item">
        ${avatar(a.visitante, 'avatar--sm')}
        <div class="mini-item__body">
          <div class="mini-item__title">${escapeHtml(a.visitante)} espera a ${escapeHtml(a.destinatario)}</div>
          <div class="mini-item__meta">${escapeHtml(CATEGORIAS[a.categoria]?.label || '')} · encuentro: ${escapeHtml(zoneName(a.punto))} · llegó ${fmtRelative(a.fecha)}</div>
          <div class="aviso__contacto">
            ${a.telefono ? `<a href="${telHref(a.telefono)}">Llamar: ${escapeHtml(a.telefono)}</a>` : ''}
            ${a.email ? `<a href="mailto:${escapeHtml(a.email)}">${icon('mail')} ${escapeHtml(a.email)}</a>` : ''}
            ${!a.telefono && !a.email ? '<span>Sin teléfono ni correo registrados: búscalo en el club.</span>' : ''}
          </div>
        </div>
        ${a.visita_id ? `<button class="btn btn--ghost btn--sm" type="button" data-visit="${a.visita_id}">Ver visita</button>` : ''}
      </li>`).join('')
      : `<li class="empty">${icon('check-circle')}<p>Todos los anfitriones respondieron sus avisos.</p></li>`;

  const upcoming = [...state.invitados, ...state.externos]
    .filter((v) => v.estado === 'programada' && v.inicio > now)
    .sort((a, b) => a.inicio - b.inicio)
    .slice(0, 6);
  $('#upcomingList').innerHTML = upcoming.length
    ? upcoming.map((v) => `<li class="mini-item mini-item--link" data-visit="${v.id}" tabindex="0" role="button">
        ${avatar(v.nombre, 'avatar--sm')}
        <div class="mini-item__body">
          <div class="mini-item__title">${escapeHtml(v.nombre)}</div>
          <div class="mini-item__meta">${v.categoria === 'externo' ? escapeHtml(v.empresa) : `Invitado de ${escapeHtml(personName(v.responsable_id))}`} · ${escapeHtml(zoneName(v.destino))}</div>
        </div>
        <div class="activity__side">
          ${badge(CATEGORIAS, v.categoria)}
          <span class="activity__time">${fmtDateTime(v.inicio)}</span>
        </div>
      </li>`).join('')
    : `<li class="empty">${icon('calendar')}<p>No hay llegadas programadas.</p></li>`;
}

async function simulateArrival() {
  if (isLive()) return;
  const btn = $('#simulateBtn');
  setBusy(btn, true);
  const ev = demoArrival(Date.now(), 'simulacion');
  try {
    await reload();
  } finally {
    setBusy(btn, false);
  }
  $('#activityList .activity__item')?.classList.add('is-new');
  const shown = state.eventos.find((e) => e.id === ev.id);
  const type = ev.resultado === 'orientado' ? 'success' : ev.resultado === 'rechazado' ? 'danger' : 'info';
  const detail = isOk(ev) ? `orientado a ${zoneName(ev.orientacion?.destino)}` : RESULTADOS[ev.resultado].label.toLowerCase();
  toast(`Llegada simulada: <strong>${escapeHtml(shown?.persona || 'Persona')}</strong> — ${escapeHtml(detail)}.`, type);
}

// =============================================================================
// Usuarios, auditoría y políticas
// =============================================================================
function renderRoles() {
  const all = people();
  const count = (rol) => all.filter((p) => p.rol === rol).length;
  const cards = [
    { rol: 'admin', iconName: 'shield', desc: 'Control total del panel.', perms: ['Edita estado, vínculo, horario y vigencia', 'Asigna cualquier rol', 'Todo lo de recepción'] },
    { rol: 'informatica', iconName: 'key', desc: 'Cuentas y soporte técnico.', perms: ['Asigna roles (no administradores)', 'Ve miembros, personal y eventos', 'Sin acceso a invitados ni externos'] },
    { rol: 'operador', iconName: 'badge', desc: 'Recepción y seguridad.', perms: ['Crea invitaciones y externos', 'Revoca accesos', 'Corrige eventos pendientes'] },
    { rol: 'usuario', iconName: 'users', desc: 'Miembros y personal en la app móvil.', perms: ['Ve su perfil y su QR', 'Invita (miembros)', 'Sin acceso al panel'] },
  ];
  $('#rolesGrid').innerHTML = cards.map((c) => `<article class="card role-card role-card--${c.rol}">
    <div class="role-card__top">
      <span class="role-card__title"><span class="stat__icon ${c.rol === 'admin' ? 'stat__icon--gold' : ''}">${icon(c.iconName)}</span>${ROLES[c.rol].label}</span>
      <span class="role-card__count">${count(c.rol)}</span>
    </div>
    <p>${c.desc}</p>
    <ul>${c.perms.map((p) => `<li>${icon('check')}${p}</li>`).join('')}</ul>
  </article>`).join('');
}

function renderAudit() {
  const list = state.auditoria;
  const el = $('#auditList');
  if (!list) {
    el.innerHTML = `<li class="empty">${icon('info')}<p>La auditoría requiere la migración propuesta 009.</p></li>`;
    return;
  }
  const describe = (a) => Object.entries(a.cambios).map(([k, [antes, despues]]) => {
    const fmt = (v) => (k === 'rol' ? ROLES[v]?.label : k === 'vinculo' ? VINCULOS[v] : k === 'estado' ? ESTADOS_PERSONA[v]?.label : v === null ? '—' : String(v)) ?? String(v);
    return `${k.replace(/_/g, ' ')}: ${escapeHtml(fmt(antes))} → <strong>${escapeHtml(fmt(despues))}</strong>`;
  }).join(' · ') || 'Sin cambios';
  el.innerHTML = list.length
    ? list.slice(0, 20).map((a) => `<li class="mini-item">
        <span class="stat__icon">${icon(a.accion === 'asignar_rol' ? 'key' : 'edit')}</span>
        <div class="mini-item__body">
          <div class="mini-item__title">${escapeHtml(a.actor)} → ${escapeHtml(a.persona)}</div>
          <div class="mini-item__meta">${describe(a)}</div>
        </div>
        <span class="activity__time">${fmtDateTime(a.fecha)}</span>
      </li>`).join('')
    : `<li class="empty">${icon('check-circle')}<p>Sin cambios registrados.</p></li>`;
}

function renderPolicies() {
  const migr = session.caps.migracion;
  const live = isLive();
  const status = (ok, text) => `<span class="badge ${ok ? 'badge--success' : 'badge--warning'}">${text}</span>`;
  const db = window.NClubDB;
  const cards = [
    {
      title: 'Acceso de invitados y externos', iconName: 'clock',
      status: !live ? status(true, 'Simulado en la demo') : migr ? status(true, 'Lo aplica la base (trigger)') : status(false, 'Falta migración 009'),
      body: `La autorización vence <strong>exactamente ${POLICY.accesoTemporalHoras} h después del registro</strong> de la invitación, para el QR y para el reconocimiento facial.
        ${live && !migr ? 'Hoy el panel crea las invitaciones con 24 h, pero la base todavía acepta otras ventanas desde la app.' : ''}`,
    },
    {
      title: 'Eliminación de datos personales', iconName: 'trash',
      status: live ? status(true, 'pg_cron (migración 003)') : status(true, 'Simulado en la demo'),
      body: `Cada ${POLICY.limpiezaMinutos} minutos el servidor borra al invitado o externo vencido junto con su visita y su QR, aunque el panel esté cerrado.
        Los archivos de fotos en Storage no se borran por cascada (ver docs/SUPABASE.md).`,
    },
    {
      title: 'Historial de eventos', iconName: 'history',
      status: !live || migr ? status(true, !live ? 'Simulado en la demo' : 'Job diario de retención') : status(false, 'Propuesta 009'),
      body: `Política independiente: a los ${POLICY.eventosDesvincularDias} días el evento pierde persona, visita, foto y texto libre; a los ${POLICY.eventosEliminarDias} días se elimina.
        El panel muestra los últimos 30 días.`,
    },
    {
      title: 'Roles y permisos', iconName: 'shield',
      status: !live ? status(true, 'Modelo propuesto (demo)') : migr ? status(true, 'admin · informática · operador') : status(false, 'Solo operador y admin'),
      body: 'RLS y las funciones de la base deciden qué se ve y qué se puede cambiar. El panel solo oculta lo que no corresponde al rol.',
    },
    {
      title: 'Registro de cuentas', iconName: 'lock',
      status: status(true, 'Sin registro en el panel'),
      body: 'El panel solo permite iniciar sesión. La app móvil sí registra miembros (quedan como regulares con rol usuario y no pueden entrar al panel). Los roles solo los cambia administración o informática.',
    },
    {
      title: 'Reconocimiento facial y QR', iconName: 'face',
      status: status(true, 'Sin cambios desde el panel'),
      body: 'Umbrales, fotos y huellas los gestionan el robot y la app. El panel nunca lee fotos, embeddings, tokens ni sus hashes.',
    },
    {
      title: 'Horarios', iconName: 'calendar',
      status: status(true, 'Restricciones CHECK'),
      body: `Miembros entre ${POLICY.miembros.join(' y ')}. Personal entre ${POLICY.personal.join(' y ')}, máximo ${POLICY.turnoMaxHoras} horas por turno.`,
    },
    {
      title: 'Conexión', iconName: 'database',
      status: live ? status(true, 'Supabase') : status(false, db?.configured ? 'Demostración' : 'Sin configurar'),
      body: live
        ? `Proyecto <span class="cell-mono">${escapeHtml(db.projectHost)}</span> · datos leídos ${fmtDateTime(state.loadedAt)}.
          ${state.warnings.map((w) => `<br>${icon('alert')} ${escapeHtml(w)}`).join('')}`
        : (db?.configured ? 'Supabase está configurado; estás viendo la demostración.' : escapeHtml(db?.problem || 'js/supabase.js no está configurado.')),
    },
  ];
  $('#policyGrid').innerHTML = cards.map((c) => `<article class="card policy-card">
    <div class="policy-card__top"><span class="stat__icon">${icon(c.iconName)}</span><h2>${c.title}</h2></div>
    ${c.status}
    <p>${c.body}</p>
  </article>`).join('');
}

// =============================================================================
// Sesión: inicio de sesión, demo y carga de datos
// =============================================================================
function setLoading(text) {
  $('#loadingText').textContent = text;
  $('#loadingScreen').hidden = false;
}

function showLogin(message = '') {
  session = null;
  closeModal();
  document.body.classList.remove('is-booting', 'is-live', 'is-demo');
  $('#loadingScreen').hidden = true;
  $('#app').hidden = true;
  $('#authScreen').hidden = false;
  const err = $('#loginError');
  err.innerHTML = message ? `${icon('alert')}<span>${escapeHtml(message)}</span>` : '';
  $('#authProject').textContent = window.NClubDB?.projectHost ? `Proyecto: ${window.NClubDB.projectHost}` : '';
  setBusy($('#loginSubmit'), false);
  $('#loginForm [name="password"]').value = '';
  $('#loginForm [name="email"]').focus();
}

function showApp() {
  document.body.classList.remove('is-booting');
  $('#loadingScreen').hidden = true;
  $('#authScreen').hidden = true;
  $('#app').hidden = false;
  updateModeUI();
  showView();
}

async function reload() {
  const snap = await backend().load();
  applySnapshot(snap);
  refreshAll();
}

async function startLive() {
  const db = window.NClubDB;
  setLoading('Verificando permisos…');
  let access;
  try {
    access = await db.getAccess();
  } catch (err) {
    await db.signOut().catch(() => {});
    showLogin(err.message);
    return;
  }
  const p = access.persona;
  const rol = access.permisos ? access.permisos.rol : (access.isOperator ? p?.rol : null);
  if (!p) {
    await db.signOut();
    showLogin('Tu cuenta no está vinculada a una persona del club.');
    return;
  }
  if (!PANEL_ROLES.includes(rol)) {
    await db.signOut();
    showLogin(p.estado !== 'activa'
      ? 'Tu cuenta está suspendida.'
      : `Tu cuenta (rol ${ROLES[p.rol]?.label ?? p.rol}) no tiene acceso al panel. Pide a informática que te asigne un rol.`);
    return;
  }
  session = { mode: 'live', rol, accountId: p.id, caps: computeCaps(access.permisos, access.isOperator, rol) };
  setLoading('Cargando datos…');
  try {
    await reload();
  } catch (err) {
    if (err.expired) { sessionExpired(err.message); return; }
    await db.signOut().catch(() => {});
    showLogin(`No se pudieron leer los datos: ${err.message}`);
    return;
  }
  showApp();
  state.warnings.forEach((w) => toast(escapeHtml(w), 'info'));
}

async function startDemo(rol) {
  if (!demo.db) seedDemo();
  session = { mode: 'demo', rol, accountId: demo.accounts[rol], caps: { ...computeCaps(permisosFor(rol), true, rol) } };
  setLoading('Preparando la demostración…');
  $('#authScreen').hidden = true;
  await reload();
  showApp();
}

function sessionExpired(message) {
  if (isLive()) {
    window.NClubDB.signOut().catch(() => {});
    showLogin(message || 'La sesión expiró. Inicia sesión de nuevo.');
  } else {
    toast(escapeHtml(message), 'danger');
  }
}

function openRolePicker() {
  const roles = PANEL_ROLES.map((r) => {
    const p = demo.db?.personas.find((x) => x.id === demo.accounts[r]);
    return `<button class="role-option" type="button" data-rol="${r}">
      <span class="stat__icon">${icon(r === 'admin' ? 'shield' : r === 'informatica' ? 'key' : 'badge')}</span>
      <span><strong>${ROLES[r].label}</strong><small>${p ? escapeHtml(p.nombre_demo) : 'Cuenta de demostración'}</small></span>
    </button>`;
  }).join('');
  openModal(`${modalHeader({ title: 'Explorar la demostración', subtitle: 'Datos ficticios. Elige con qué rol quieres ver el panel.' })}
    <div class="modal__body"><div class="role-options">${roles}</div>
    ${note('La demostración usa el modelo de permisos propuesto (migraciones 008–009) y no se conecta a ninguna base de datos.')}</div>`, {
    onMount: (root) => {
      $$('[data-rol]', root).forEach((btn) => btn.addEventListener('click', async () => {
        closeModal();
        await startDemo(btn.dataset.rol);
        toast(`Viendo la demostración como ${ROLES[btn.dataset.rol].label}.`, 'info');
      }));
    },
  });
}

function openAccountPanel() {
  const p = account();
  const live = isLive();
  const body = [
    detailSection('Sesión', [
      ['Cuenta', escapeHtml(p?.nombre || '—')],
      ['Correo', escapeHtml(p?.email || '—')],
      ['Rol', ROLES[session.rol]?.label],
      ['Datos', live ? `Supabase · ${escapeHtml(window.NClubDB.projectHost)}` : 'Demostración (ficticios)'],
      ['Leídos', fmtDateTime(state.loadedAt)],
      ['Modelo de permisos', session.caps.migracion ? 'Con migraciones 008–009' : 'Actual (sin 008–009)'],
    ]),
    `<section class="detail-section"><h3>Puede</h3><ul class="cap-list">${CAP_KEYS.map((k) => `<li class="${can(k) ? 'yes' : 'no'}">${icon(can(k) ? 'check' : 'x')} ${k.replace(/_/g, ' ')}</li>`).join('')}</ul></section>`,
  ].join('');
  const footer = [];
  if (live) {
    footer.push({ label: 'Cerrar sesión', icon: 'logout', cls: 'btn--ghost btn--danger-text', onClick: confirmSignOut });
  } else {
    footer.push({ label: 'Cambiar rol', icon: 'key', onClick: openRolePicker });
    if (window.NClubDB?.configured) footer.push({ label: 'Ir al inicio de sesión', icon: 'login', onClick: () => showLogin() });
  }
  openDetail({ title: p?.nombre || 'Cuenta', subtitle: ROLES[session.rol]?.label, avatarName: p?.nombre, badges: [badge(ROLES, session.rol)], body, footer });
}

function confirmSignOut() {
  openConfirm({
    title: '¿Cerrar sesión?',
    message: 'Se borrará la sesión de este navegador. Los datos del panel no se guardan en el equipo.',
    confirmLabel: 'Cerrar sesión',
    iconName: 'logout',
    onConfirm: async () => {
      await window.NClubDB.signOut();
      showLogin();
    },
  });
}

// =============================================================================
// Navegación y estado global
// =============================================================================
function updateModeUI() {
  const live = isLive();
  const p = account();
  document.body.classList.toggle('is-live', live);
  document.body.classList.toggle('is-demo', !live);

  $('#modeBannerText').innerHTML = live
    ? `<strong>Conectado a Supabase.</strong> Datos reales de <span class="cell-mono">${escapeHtml(window.NClubDB.projectHost)}</span>,
       leídos ${fmtTime(state.loadedAt)}. Rol: ${ROLES[session.rol].label}.${session.caps.migracion ? '' : ' La base aún no tiene las migraciones 008–009: solo funciones de recepción.'}`
    : `<strong>Demostración con datos ficticios</strong> como ${ROLES[session.rol].label}. Imita las reglas de la base (roles, 24 h, limpieza); nada se guarda.`;
  $('#bannerBtn').innerHTML = live ? `${icon('refresh')} Actualizar` : `${icon('key')} Cambiar rol`;
  $('#modePillText').textContent = live ? 'EN VIVO' : 'DEMO';
  $('#modePill').title = live ? 'Datos reales de Supabase' : 'Toda la información de esta página es ficticia';
  $('#modeTitle').textContent = live ? 'Supabase' : 'Modo demostración';
  $('#modeSubtitle').textContent = live ? `${ROLES[session.rol].label} · últimos 30 días` : `Datos ficticios · ${ROLES[session.rol].label}`;
  $('#footerMode').textContent = live ? `Supabase · ${window.NClubDB.projectHost}` : 'Datos ficticios de demostración';
  $('#dashSubtitle').textContent = live ? 'Resumen del acceso al club con datos reales (últimos 30 días).' : 'Resumen del acceso al club (datos de demostración).';
  $('#userName').textContent = p?.nombre || '—';
  $('#userRole').textContent = ROLES[session.rol]?.label || '—';
  $('#userInitials').textContent = initials(p?.nombre);

  const views = allowedViews();
  $$('.nav__link').forEach((a) => { a.hidden = !views.includes(a.dataset.nav); });
  $$('.nav__label').forEach((label) => {
    let el = label.nextElementSibling;
    let any = false;
    while (el && !el.classList.contains('nav__label')) { if (!el.hidden) any = true; el = el.nextElementSibling; }
    label.hidden = !any;
  });
  $$('[data-needs]').forEach((el) => { el.hidden = !can(el.dataset.needs); });
  $$('.demo-only').forEach((el) => { el.hidden = live; });
}

function showView() {
  if (!session) return;
  let view = location.hash.slice(1);
  const views = allowedViews();
  if (!VIEW_TITLES[view]) view = 'dashboard';
  if (!views.includes(view)) {
    if (location.hash && location.hash !== '#dashboard') toast('Tu rol no tiene acceso a esa sección.', 'info');
    view = 'dashboard';
    history.replaceState(null, '', '#dashboard');
  }
  $$('.view').forEach((s) => { s.hidden = s.dataset.view !== view; });
  $$('.nav__link').forEach((a) => {
    const on = a.dataset.nav === view;
    a.classList.toggle('is-active', on);
    if (on) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
  });
  $('#topbarTitle').textContent = VIEW_TITLES[view];
  document.title = `${VIEW_TITLES[view]} · N Club — Access Management`;
  document.body.classList.remove('sidebar-open');
  window.scrollTo(0, 0);
}

function renderCounts() {
  const active = (list) => list.filter(activeVisit).length;
  const pending = pendingEvents().length;
  const counts = {
    vip: state.vip.length,
    regulares: state.regulares.length,
    invitados: active(state.invitados) || '',
    personal: state.personal.length,
    externos: active(state.externos) || '',
    historial: pending || '',
  };
  Object.entries(counts).forEach(([k, v]) => { $(`[data-count="${k}"]`).textContent = v; });
  const avisos = unansweredAvisos().length;
  $('#bellCount').textContent = pending + avisos || '';
  $('#bellBtn').title = [pending && `${pending} eventos pendientes de revisión`, avisos && `${avisos} avisos de llegada sin respuesta`]
    .filter(Boolean).join(' · ') || 'Sin pendientes';
}

function refreshAll() {
  Object.keys(TABLES).forEach((k) => { renderStats(k); renderRows(k); });
  renderDashboard();
  renderRoles();
  renderAudit();
  renderPolicies();
  renderCounts();
  if (session) updateModeUI();
}

async function refreshClick() {
  const btn = $('#refreshBtn');
  btn.classList.add('is-spinning');
  try {
    await reload();
    toast('Datos actualizados.', 'info');
  } catch (err) {
    handleError(err, 'No se pudieron actualizar los datos');
  } finally {
    btn.classList.remove('is-spinning');
  }
}

function bindGlobalEvents() {
  window.addEventListener('hashchange', showView);

  document.addEventListener('click', (e) => {
    const go = e.target.closest('[data-go]');
    if (go) { location.hash = go.dataset.go; return; }
    const nw = e.target.closest('[data-new]');
    if (nw) { openVisitForm(nw.dataset.new); return; }
    const ev = e.target.closest('[data-event]');
    if (ev) { openEventDetail(state.eventos.find((x) => x.id === ev.dataset.event)); return; }
    const rv = e.target.closest('[data-review]');
    if (rv) {
      const target = state.eventos.find((x) => x.id === rv.dataset.review);
      if (can('corregir_eventos')) openCorrection(target); else openEventDetail(target);
      return;
    }
    const vs = e.target.closest('[data-visit]');
    if (vs) openPersonDetail(vs.dataset.visit);
  });

  document.addEventListener('keydown', (e) => {
    if ((e.key === 'Enter' || e.key === ' ') && e.target.matches('[data-event], [data-visit]')) {
      e.preventDefault();
      e.target.click();
    }
  });

  $('#loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const form = e.target;
    const email = form.email.value.trim();
    const password = form.password.value;
    const errBox = $('#loginError');
    const fail = (msg, field) => { errBox.innerHTML = `${icon('alert')}<span>${escapeHtml(msg)}</span>`; form[field]?.focus(); };
    if (!email || !password) return fail('Escribe tu correo y tu contraseña.', email ? 'password' : 'email');
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return fail('El correo no tiene un formato válido.', 'email');
    if (!window.NClubDB?.configured) return fail(window.NClubDB?.problem || 'Supabase no está configurado.', 'email');
    errBox.innerHTML = '';
    const btn = $('#loginSubmit');
    setBusy(btn, true);
    try {
      await window.NClubDB.signIn(email, password);
      form.password.value = '';
      await startLive();
    } catch (err) {
      setBusy(btn, false);
      fail(err.message, 'password');
    }
  });

  $('#demoBtn').addEventListener('click', openRolePicker);
  $('#simulateBtn').addEventListener('click', simulateArrival);
  $('#refreshBtn').addEventListener('click', refreshClick);
  $('#bannerBtn').addEventListener('click', () => (isLive() ? refreshClick() : openRolePicker()));
  $('#userChip').addEventListener('click', openAccountPanel);
  $('#sidebarOpen').addEventListener('click', () => document.body.classList.add('sidebar-open'));
  $('#sidebarClose').addEventListener('click', () => document.body.classList.remove('sidebar-open'));
  $('#sidebarOverlay').addEventListener('click', () => document.body.classList.remove('sidebar-open'));

  $('#bellBtn').addEventListener('click', () => {
    if (!pendingEvents().length && unansweredAvisos().length) {
      // Solo hay avisos sin respuesta: se muestran en el dashboard.
      location.hash = 'dashboard';
      setTimeout(() => $('.dash-avisos')?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 50);
      return;
    }
    if (!can('ver_eventos')) return;
    location.hash = 'historial';
    setTableFilter('historial', 'resultado', 'pendiente_revision');
    if (!pendingEvents().length) toast('No hay eventos pendientes de revisión.', 'info');
  });
}

async function init() {
  const today = longDateFmt.format(new Date());
  $('#topbarDate').textContent = today.charAt(0).toUpperCase() + today.slice(1);
  bindGlobalEvents();
  Object.keys(TABLES).forEach(initTable);

  // Mantiene al día los tiempos relativos; en la demo corre también la "limpieza del servidor".
  setInterval(async () => {
    if (!session) return;
    if (!isLive()) { try { await reload(); } catch { /* la demo no falla */ } } else { renderDashboard(); renderCounts(); }
  }, 60 * 1000);

  const db = window.NClubDB;
  if (db?.configured) {
    db.onAuthChange((event) => { if (event === 'SIGNED_OUT' && isLive()) showLogin('La sesión se cerró.'); });
    setLoading('Verificando la sesión…');
    const existing = await db.getSession().catch(() => null);
    if (existing) await startLive(); else showLogin();
  } else {
    await startDemo('admin');
  }
}

init();
