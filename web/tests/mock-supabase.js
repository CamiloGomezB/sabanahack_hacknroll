/* =============================================================================
   Supabase FALSO para probar el panel sin tocar el proyecto real.

   Lo inyecta tests/serve-mock.js en lugar de supabase-js. Imita:
     - el esquema de las migraciones 001–005 (y la 006 con ?espacios=1);
     - RLS: anon sin acceso, usuarios solo lo suyo, es_operador() ve todo;
     - las RPC existentes (mi_persona_id, es_operador, crear_invitacion, revocar_invitacion,
       corregir_evento) y, con ?migracion=009, las de la propuesta 009 y el trigger de 24 h;
     - errores reales de PostgREST: 42501, 42703, PGRST202, PGRST205, PGRST301 y de red.
   Datos y credenciales 100 % ficticios. Es una imitación: no reemplaza probar RLS en Postgres
   (supabase/propuestas/pruebas_rls_panel.sql).
   ========================================================================== */
(function () {
  'use strict';

  const params = new URLSearchParams(location.search);
  const M009 = params.get('migracion') === '009';
  const ESPACIOS = params.get('espacios') === '1';
  const AVISOS = params.get('avisos') === '1'; // tabla avisos (migración 007)
  const PASSWORD = 'prueba-nclub-2026'; // contraseña de prueba de todas las cuentas ficticias
  const H = 3600e3;
  const iso = (t) => new Date(t).toISOString();
  const uuid = (n) => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
  const hex = () => Array.from({ length: 64 }, () => Math.floor(Math.random() * 16).toString(16)).join('');
  let seq = 500;

  const SCHEMA = {
    personas: ['id', 'usuario_id', 'nombre_demo', 'email', 'telefono', 'vinculo', 'rol', 'estado', 'requiere_tour', 'horario_inicio', 'horario_fin',
      'consentimiento_biometrico', 'consentimiento_fecha', 'creado_en', 'actualizado_en', 'vinculo_hasta'],
    visitas: ['id', 'persona_id', 'responsable_id', 'categoria', 'motivo', 'empresa', 'destino', 'inicio', 'fin', 'estado', 'nivel_ayuda', 'creado_en'],
    credenciales: ['id', 'persona_id', 'visita_id', 'tipo', 'token_hash', 'valido_desde', 'valido_hasta', 'revocada_en', 'motivo_revocacion', 'restricciones', 'creado_en'],
    eventos: ['id', 'visita_id', 'persona_candidata_id', 'credencial_id', 'fuente', 'evidencia', 'categoria', 'resultado', 'motivo', 'orientacion', 'duracion_ms',
      'creado_en', 'corregido_por', 'correccion_motivo', 'corregido_en', 'foto_id', 'modo_reconocimiento'],
    fotografias: ['id', 'persona_id', 'ruta', 'uso', 'tomada_en', 'autorizada', 'autorizacion_fecha', 'embedding', 'modelo', 'cargada_por', 'creado_en'],
  };
  if (ESPACIOS) SCHEMA.espacios = ['clave', 'nombre', 'descripcion', 'capacidad', 'reservable_por', 'activo'];
  if (AVISOS) SCHEMA.avisos = ['id', 'destinatario_id', 'visita_id', 'tipo', 'mensaje', 'punto_encuentro', 'estado', 'creado_en', 'actualizado_en'];
  if (M009) SCHEMA.auditoria_panel = ['id', 'actor_id', 'accion', 'persona_id', 'cambios', 'creado_en'];

  const T = Date.now();
  const users = [
    { id: uuid(101), email: 'admin@prueba.test' },
    { id: uuid(102), email: 'operador@prueba.test' },
    { id: uuid(103), email: 'informatica@prueba.test' },
    { id: uuid(104), email: 'miembro@prueba.test' },
    { id: uuid(105), email: 'suspendido@prueba.test' },
  ];
  const P = (n, extra) => ({
    id: uuid(n), usuario_id: null, nombre_demo: '', email: null, telefono: null, vinculo: 'regular', rol: 'usuario', estado: 'activa',
    requiere_tour: false, horario_inicio: '06:00:00', horario_fin: '21:00:00', consentimiento_biometrico: false, consentimiento_fecha: null,
    creado_en: iso(T - 300 * 24 * H), actualizado_en: iso(T - 10 * 24 * H), vinculo_hasta: null, ...extra,
  });
  const db = {
    personas: [
      P(1, { usuario_id: uuid(101), nombre_demo: 'Ana Admin (prueba)', email: 'admin@prueba.test', vinculo: 'personal', rol: 'admin', horario_inicio: '08:00:00', horario_fin: '16:00:00' }),
      P(2, { usuario_id: uuid(102), nombre_demo: 'Óscar Operador (prueba)', email: 'operador@prueba.test', telefono: '+57 300 555 0102', vinculo: 'personal', rol: 'operador', horario_inicio: '06:00:00', horario_fin: '14:00:00' }),
      P(3, { usuario_id: uuid(103), nombre_demo: 'Inés Informática (prueba)', email: 'informatica@prueba.test', vinculo: 'personal', rol: M009 ? 'informatica' : 'usuario', horario_inicio: '08:00:00', horario_fin: '16:00:00' }),
      P(4, { usuario_id: uuid(104), nombre_demo: 'Marco Miembro (prueba)', email: 'miembro@prueba.test', requiere_tour: true, consentimiento_biometrico: true, consentimiento_fecha: iso(T - 200 * 24 * H) }),
      P(5, { usuario_id: uuid(105), nombre_demo: 'Sara Suspendida (prueba)', email: 'suspendido@prueba.test', vinculo: 'personal', rol: 'operador', estado: 'suspendida', horario_inicio: '06:00:00', horario_fin: '14:00:00' }),
      P(6, { nombre_demo: 'Valeria VIP (prueba)', email: 'valeria@prueba.test', vinculo: 'vip', consentimiento_biometrico: true, consentimiento_fecha: iso(T - 90 * 24 * H), vinculo_hasta: '2027-06-30' }),
      P(7, { usuario_id: uuid(107), nombre_demo: 'Rafael Regular (prueba)', email: 'rafael@prueba.test' }),
      P(8, { usuario_id: uuid(108), nombre_demo: 'Pedro Personal (prueba)', email: 'pedro@prueba.test', vinculo: 'personal', horario_inicio: '10:00:00', horario_fin: '18:00:00' }),
      P(20, { nombre_demo: 'Iván Invitado (prueba)', email: 'ivan@prueba.test', vinculo: 'ninguno', horario_inicio: null, horario_fin: null, creado_en: iso(T - 2 * H) }),
      P(21, { nombre_demo: 'Elsa Externa (prueba)', email: 'elsa@prueba.test', vinculo: 'ninguno', horario_inicio: null, horario_fin: null, creado_en: iso(T - 1 * H) }),
    ],
    visitas: [
      { id: uuid(30), persona_id: uuid(20), responsable_id: uuid(2), categoria: 'invitado', motivo: 'Almuerzo', empresa: null, destino: 'restaurante', inicio: iso(T - H), fin: iso(T + 22 * H), estado: 'en_curso', nivel_ayuda: 'mapa', creado_en: iso(T - 2 * H) },
      { id: uuid(31), persona_id: uuid(21), responsable_id: uuid(2), categoria: 'externo', motivo: 'Revisión de bombas', empresa: 'AquaPrueba', destino: 'piscina', inicio: iso(T + 2 * H), fin: iso(T + 23 * H), estado: 'programada', nivel_ayuda: null, creado_en: iso(T - H) },
      { id: uuid(32), persona_id: uuid(6), responsable_id: null, categoria: 'vip', motivo: null, empresa: null, destino: 'sala_vip', inicio: iso(T - 0.5 * H), fin: iso(T + 5 * H), estado: 'en_curso', nivel_ayuda: 'indicacion', creado_en: iso(T - 0.5 * H) },
    ],
    credenciales: [
      { id: uuid(40), persona_id: uuid(20), visita_id: uuid(30), tipo: 'qr_visita', token_hash: hex(), valido_desde: iso(T - H), valido_hasta: iso(T + 22 * H), revocada_en: null, motivo_revocacion: null, restricciones: {}, creado_en: iso(T - 2 * H) },
      { id: uuid(41), persona_id: uuid(21), visita_id: uuid(31), tipo: 'qr_visita', token_hash: hex(), valido_desde: iso(T + 2 * H), valido_hasta: iso(T + 23 * H), revocada_en: null, motivo_revocacion: null, restricciones: {}, creado_en: iso(T - H) },
      { id: uuid(42), persona_id: uuid(4), visita_id: null, tipo: 'qr_personal', token_hash: hex(), valido_desde: iso(T - 100 * 24 * H), valido_hasta: null, revocada_en: null, motivo_revocacion: null, restricciones: {}, creado_en: iso(T - 100 * 24 * H) },
    ],
    eventos: [
      { id: uuid(50), visita_id: null, persona_candidata_id: uuid(7), credencial_id: null, fuente: 'robot', evidencia: { cara: 'ambigua', detalle: 'entre_umbrales', distancia: 0.452, qr: 'no_presentado', modo: 'real' }, categoria: null, resultado: 'pendiente_revision', motivo: 'identidad_ambigua', orientacion: null, duracion_ms: null, creado_en: iso(T - 10 * 60e3), corregido_por: null, correccion_motivo: null, corregido_en: null, foto_id: null, modo_reconocimiento: 'real' },
      { id: uuid(51), visita_id: uuid(32), persona_candidata_id: uuid(6), credencial_id: null, fuente: 'robot', evidencia: { cara: 'reconocida', distancia: 0.21, qr: 'no_presentado', modo: 'real' }, categoria: 'vip', resultado: 'orientado', motivo: null, orientacion: { destino: 'sala_vip', nivel_ayuda: 'indicacion' }, duracion_ms: 3100, creado_en: iso(T - 30 * 60e3), corregido_por: null, correccion_motivo: null, corregido_en: null, foto_id: null, modo_reconocimiento: 'real' },
      { id: uuid(52), visita_id: uuid(30), persona_candidata_id: uuid(20), credencial_id: uuid(40), fuente: 'robot', evidencia: { cara: 'no_usada', qr: 'valida' }, categoria: 'invitado', resultado: 'orientado', motivo: null, orientacion: { destino: 'restaurante', nivel_ayuda: 'mapa' }, duracion_ms: 4200, creado_en: iso(T - 55 * 60e3), corregido_por: null, correccion_motivo: null, corregido_en: null, foto_id: null, modo_reconocimiento: null },
      { id: uuid(53), visita_id: null, persona_candidata_id: null, credencial_id: null, fuente: 'simulacion', evidencia: { cara: 'desconocida', qr: 'no_presentado', modo: 'simulado' }, categoria: null, resultado: 'rechazado', motivo: 'no_identificado', orientacion: null, duracion_ms: 1500, creado_en: iso(T - 2 * H), corregido_por: null, correccion_motivo: null, corregido_en: null, foto_id: null, modo_reconocimiento: 'simulado' },
      { id: uuid(54), visita_id: null, persona_candidata_id: null, credencial_id: null, fuente: 'robot', evidencia: { cara: 'no_usada', qr: 'valida' }, categoria: 'externo', resultado: 'orientado', motivo: null, orientacion: { destino: 'mantenimiento', nivel_ayuda: 'acompanamiento' }, duracion_ms: 2500, creado_en: iso(T - 30 * H), corregido_por: null, correccion_motivo: null, corregido_en: null, foto_id: null, modo_reconocimiento: null },
    ],
    fotografias: [],
    espacios: [
      { clave: 'restaurante', nombre: 'Restaurante', descripcion: '', capacidad: 40, reservable_por: ['regular', 'vip'], activo: true },
      { clave: 'sala_vip', nombre: 'Sala VIP', descripcion: '', capacidad: 10, reservable_por: ['vip'], activo: true },
      { clave: 'piscina', nombre: 'Piscina', descripcion: '', capacidad: 30, reservable_por: ['regular', 'vip'], activo: true },
    ],
    avisos: [
      { id: uuid(60), destinatario_id: uuid(2), visita_id: uuid(30), tipo: 'llegada_invitado', mensaje: 'Iván Invitado (prueba) llegó a N Club. Encuentro: Restaurante.', punto_encuentro: 'restaurante', estado: 'sin_respuesta', creado_en: iso(T - 50 * 60e3), actualizado_en: iso(T - 49 * 60e3) },
    ],
    auditoria_panel: [],
  };

  const log = [];
  const listeners = [];
  let failNext = null;
  let expired = false;
  const KEY = 'nclub-mock-session';

  const sessionUser = () => { try { return sessionStorage.getItem(KEY); } catch { return null; } };
  const me = () => db.personas.find((p) => p.usuario_id && p.usuario_id === sessionUser()) || null;
  const esOperador = () => { const p = me(); return !!p && p.estado === 'activa' && ['operador', 'admin'].includes(p.rol); };
  const rolPanel = () => { const p = me(); return p && p.estado === 'activa' && (!p.vinculo_hasta || p.vinculo_hasta >= iso(Date.now()).slice(0, 10)) ? p.rol : null; };
  const esInformatica = () => M009 && rolPanel() === 'informatica';
  const delay = () => new Promise((r) => setTimeout(r, 120));
  const pgErr = (code, message) => ({ data: null, error: { code, message, details: null, hint: null } });
  const raise = (message) => { const e = new Error(message); e.pg = { code: 'P0001', message }; throw e; };
  const denied = (message) => { const e = new Error(message); e.pg = { code: '42501', message }; throw e; };

  // Políticas RLS (003, 004 y propuesta 009).
  function visible(table, row) {
    const yo = me();
    const yoId = yo?.id;
    switch (table) {
      case 'personas':
        return row.usuario_id === sessionUser() || esOperador() || (esInformatica() && row.vinculo !== 'ninguno')
          || db.visitas.some((v) => v.persona_id === row.id && v.responsable_id === yoId);
      case 'visitas': return row.persona_id === yoId || row.responsable_id === yoId || esOperador();
      case 'credenciales': return row.persona_id === yoId || esOperador();
      case 'eventos': return esOperador() || esInformatica();
      case 'fotografias': return row.persona_id === yoId || esOperador();
      case 'espacios': return row.activo;
      case 'avisos': return row.destinatario_id === yoId || esOperador();
      case 'auditoria_panel': return ['admin', 'informatica'].includes(rolPanel());
      default: return false;
    }
  }

  async function runQuery(q) {
    await delay();
    log.push({ type: 'select', table: q.table, columns: q.cols, filters: q.used.slice() });
    if (failNext) { const f = failNext; failNext = null; if (f === 'network') throw new TypeError('Failed to fetch'); return pgErr('XX000', 'Error simulado'); }
    if (expired) return pgErr('PGRST301', 'JWT expired');
    if (!SCHEMA[q.table]) return pgErr('PGRST205', `Could not find the table 'public.${q.table}' in the schema cache`);
    if (!sessionUser()) return pgErr('42501', `permission denied for table ${q.table}`);
    const cols = q.cols === '*' ? SCHEMA[q.table] : q.cols.split(',').map((c) => c.trim());
    const bad = [...cols, ...q.used].find((c) => !SCHEMA[q.table].includes(c));
    if (bad) return pgErr('42703', `column ${q.table}.${bad} does not exist`);
    let rows = db[q.table].filter((r) => visible(q.table, r)).filter((r) => q.filters.every((f) => f(r)));
    if (q.order) {
      const { col, asc } = q.order;
      rows = rows.slice().sort((a, b) => (a[col] > b[col] ? 1 : a[col] < b[col] ? -1 : 0) * (asc ? 1 : -1));
    }
    if (q.limit != null) rows = rows.slice(0, q.limit);
    return { data: rows.map((r) => Object.fromEntries(cols.map((c) => [c, JSON.parse(JSON.stringify(r[c] ?? null))]))), error: null };
  }

  function from(table) {
    const q = { table, cols: '*', filters: [], used: [], order: null, limit: null };
    const api = {
      select(cols) { q.cols = cols; return api; },
      eq(c, v) { q.used.push(c); q.filters.push((r) => r[c] === v); return api; },
      gte(c, v) { q.used.push(c); q.filters.push((r) => r[c] != null && r[c] >= v); return api; },
      is(c, v) { q.used.push(c); q.filters.push((r) => (r[c] ?? null) === v); return api; },
      order(c, opts = {}) { q.used.push(c); q.order = { col: c, asc: opts.ascending !== false }; return api; },
      limit(n) { q.limit = n; return api; },
      // El panel solo lee: cualquier escritura directa se registra como error de la prueba.
      insert() { log.push({ type: 'WRITE', table }); return api; },
      update() { log.push({ type: 'WRITE', table }); return api; },
      delete() { log.push({ type: 'WRITE', table }); return api; },
      then(resolve, reject) { return runQuery(q).then(resolve, reject); },
    };
    return api;
  }

  // --- RPC ---------------------------------------------------------------------------------
  function audit(accion, personaId, cambios) {
    db.auditoria_panel.push({ id: uuid(++seq), actor_id: me()?.id ?? null, accion, persona_id: personaId, cambios, creado_en: iso(Date.now()) });
  }

  const RPC = {
    mi_persona_id: () => me()?.id ?? null,
    es_operador: () => esOperador(),

    crear_invitacion(a) {
      const yo = me();
      if (!yo || yo.estado !== 'activa') raise('Necesitas una cuenta activa del club.');
      const sinRol = yo.rol === 'usuario' || (M009 && yo.rol === 'informatica');
      if (a.p_categoria === 'invitado' && !['regular', 'vip'].includes(yo.vinculo) && sinRol) raise('Solo los miembros invitan.');
      if (a.p_categoria === 'externo' && yo.vinculo !== 'personal' && sinRol) raise('Solo el personal o un operador registran trabajadores externos.');
      if (!['invitado', 'externo'].includes(a.p_categoria)) raise('Una invitación solo puede ser para invitado o externo.');
      if (a.p_categoria === 'externo' && !a.p_empresa) { const e = new Error('violates check constraint "externo_con_empresa"'); e.pg = { code: '23514', message: e.message }; throw e; }
      const creado = Date.now();
      let fin = a.p_fin;
      if (M009) { // trigger visitas_vigencia_24h
        fin = iso(creado + 24 * H);
        if (a.p_inicio >= fin) raise(`La visita debe empezar antes de ${fin} (24 h después del registro).`);
      } else if (!(a.p_fin > a.p_inicio)) { const e = new Error('violates check constraint "ventana_valida"'); e.pg = { code: '23514', message: e.message }; throw e; }
      const persona = P(++seq, { nombre_demo: a.p_nombre, email: a.p_email, vinculo: 'ninguno', horario_inicio: null, horario_fin: null, creado_en: iso(creado) });
      const visita = { id: uuid(++seq), persona_id: persona.id, responsable_id: yo.id, categoria: a.p_categoria, motivo: a.p_motivo, empresa: a.p_empresa, destino: a.p_destino, inicio: a.p_inicio, fin, estado: 'programada', nivel_ayuda: null, creado_en: iso(creado) };
      db.personas.push(persona);
      db.visitas.push(visita);
      db.credenciales.push({ id: uuid(++seq), persona_id: persona.id, visita_id: visita.id, tipo: 'qr_visita', token_hash: hex(), valido_desde: a.p_inicio, valido_hasta: fin, revocada_en: null, motivo_revocacion: null, restricciones: { zonas: [a.p_destino] }, creado_en: iso(creado) });
      return { visita_id: visita.id, token: hex() };
    },

    revocar_invitacion(a) {
      const v = db.visitas.find((x) => x.id === a.p_visita);
      if (!v || !(v.responsable_id === me()?.id || esOperador())) raise('No puedes revocar esta invitación.');
      v.estado = 'cancelada';
      db.credenciales.filter((c) => c.visita_id === v.id && !c.revocada_en).forEach((c) => { c.revocada_en = iso(Date.now()); c.motivo_revocacion = a.p_motivo || 'revocada por el responsable'; });
      return null;
    },

    corregir_evento(a) {
      if (!esOperador()) raise('Solo un operador de recepción puede corregir eventos.');
      if (!String(a.p_motivo || '').trim()) raise('La corrección necesita un motivo.');
      const e = db.eventos.find((x) => x.id === a.p_evento);
      if (!e) return null;
      Object.assign(e, { categoria: a.p_categoria, resultado: 'corregido', corregido_por: me().id, correccion_motivo: a.p_motivo, corregido_en: iso(Date.now()), persona_candidata_id: a.p_persona || e.persona_candidata_id });
      return null;
    },
  };

  if (M009) {
    Object.assign(RPC, {
      panel_permisos() {
        const r = rolPanel();
        const is = (...x) => x.includes(r);
        return {
          version: 1, rol: r, ver_personas: is('admin', 'informatica', 'operador'), ver_visitas: is('admin', 'operador'),
          ver_eventos: is('admin', 'informatica', 'operador'), invitar: is('admin', 'operador'), revocar: is('admin', 'operador'),
          corregir_eventos: is('admin', 'operador'), asignar_roles: is('admin', 'informatica'), editar_personas: is('admin'),
          ver_auditoria: is('admin', 'informatica'), acceso_temporal_horas: 24, eventos_desvincular_dias: 90, eventos_eliminar_dias: 365,
        };
      },
      asignar_rol(a) {
        const r = rolPanel();
        if (!['admin', 'informatica'].includes(r)) denied('Solo administración o informática pueden asignar roles.');
        const obj = db.personas.find((p) => p.id === a.p_persona);
        if (!obj) raise('La persona no existe.');
        if (obj.id === me().id) raise('No puedes cambiar tu propio rol.');
        if (!obj.usuario_id) raise('La persona no tiene cuenta en la app.');
        if (a.p_rol !== 'usuario' && obj.vinculo !== 'personal') raise('Solo el personal del club puede tener un rol de panel.');
        if (r === 'informatica' && (a.p_rol === 'admin' || obj.rol === 'admin')) denied('Informática no puede asignar ni quitar el rol de administrador.');
        if (obj.rol !== a.p_rol) { audit('asignar_rol', obj.id, { rol: [obj.rol, a.p_rol] }); obj.rol = a.p_rol; }
        return null;
      },
      admin_actualizar_persona(a) {
        if (rolPanel() !== 'admin') denied('Solo un administrador puede editar personas.');
        const p = db.personas.find((x) => x.id === a.p_persona);
        if (!p) raise('La persona no existe.');
        if (p.vinculo === 'ninguno') raise('Los invitados y externos se gestionan desde su visita.');
        if (p.id === me().id && a.p_estado === 'suspendida') raise('No puedes suspender tu propia cuenta.');
        const antes = { ...p };
        const vinculo = a.p_vinculo ?? p.vinculo;
        Object.assign(p, {
          estado: a.p_estado ?? p.estado, vinculo,
          horario_inicio: a.p_horario_inicio ? `${a.p_horario_inicio}:00` : p.horario_inicio,
          horario_fin: a.p_horario_fin ? `${a.p_horario_fin}:00` : p.horario_fin,
          vinculo_hasta: a.p_sin_vencimiento ? null : (a.p_vinculo_hasta ?? p.vinculo_hasta),
          requiere_tour: vinculo === 'regular' ? (a.p_requiere_tour ?? p.requiere_tour) : false,
          rol: vinculo === 'personal' ? p.rol : 'usuario',
        });
        const cambios = {};
        ['estado', 'vinculo', 'horario_inicio', 'horario_fin', 'vinculo_hasta', 'requiere_tour', 'rol'].forEach((k) => { if (antes[k] !== p[k]) cambios[k] = [antes[k], p[k]]; });
        audit('actualizar_persona', p.id, cambios);
        return null;
      },
    });
  }

  async function rpc(fn, args = {}) {
    await delay();
    log.push({ type: 'rpc', fn, args: Object.keys(args) });
    if (failNext) { const f = failNext; failNext = null; if (f === 'network') throw new TypeError('Failed to fetch'); return pgErr('XX000', 'Error simulado'); }
    if (expired) return pgErr('PGRST301', 'JWT expired');
    if (!RPC[fn]) return pgErr('PGRST202', `Could not find the function public.${fn} without parameters in the schema cache`);
    if (!sessionUser()) return pgErr('42501', `permission denied for function ${fn}`);
    try {
      return { data: JSON.parse(JSON.stringify(RPC[fn](args) ?? null)), error: null };
    } catch (e) {
      if (e.pg) return { data: null, error: e.pg };
      throw e;
    }
  }

  const emit = (event) => listeners.forEach((cb) => setTimeout(() => cb(event, null), 0));

  const client = {
    from,
    rpc,
    auth: {
      async getSession() {
        const u = sessionUser();
        return { data: { session: u ? { access_token: 'mock', user: { id: u } } : null }, error: null };
      },
      onAuthStateChange(cb) { listeners.push(cb); return { data: { subscription: { unsubscribe() {} } } }; },
      async signInWithPassword({ email, password }) {
        await delay();
        log.push({ type: 'auth', action: 'signIn', email });
        const u = users.find((x) => x.email === email);
        if (!u || password !== PASSWORD) return { data: null, error: { message: 'Invalid login credentials', status: 400 } };
        sessionStorage.setItem(KEY, u.id);
        expired = false;
        emit('SIGNED_IN');
        return { data: { session: { user: { id: u.id } } }, error: null };
      },
      async signUp() { log.push({ type: 'auth', action: 'signUp' }); return { data: null, error: { message: 'Signups not allowed for this instance' } }; },
      async signOut() { sessionStorage.removeItem(KEY); emit('SIGNED_OUT'); return { error: null }; },
    },
  };

  window.supabase = { createClient: () => client };
  // Control para las pruebas desde la consola o el navegador automatizado.
  window.__mockSupabase = {
    db, log, password: PASSWORD, migracion009: M009,
    failNext(kind = 'network') { failNext = kind; },
    expire() { expired = true; },
    writes: () => log.filter((l) => l.type === 'WRITE'),
  };
})();
