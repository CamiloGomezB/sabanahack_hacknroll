'use strict';

/* =============================================================================
   N Club — Acceso a Supabase

   Usa el MISMO proyecto que la app móvil (App_registro_Nclub). Aquí solo van la URL y la
   clave PÚBLICA (publishable o anon): son EXPO_PUBLIC_SUPABASE_URL y
   EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY del .env de la app. Nunca la service_role ni una
   sb_secret_: este archivo se descarga en el navegador de quien abra la página.

   Seguridad: todo pasa por RLS y por las comprobaciones dentro de las funciones de la base.
   - Lecturas: solo select con columnas explícitas (nunca "*").
   - Escrituras: solo llamadas a funciones (RPC) que validan el rol en el servidor. Este módulo
     no hace insert, update ni delete directos.
   - No hay registro de usuarios: solo inicio de sesión con cuentas que ya existen.
   ========================================================================== */

const SUPABASE_CONFIG = {
  url: '',            // p. ej. https://abcdefghijklmnop.supabase.co
  publishableKey: '', // p. ej. sb_publishable_… (o la clave anon, que empieza por eyJ…)
};

// Columnas verificadas en las migraciones. Quedan fuera a propósito: credenciales.token_hash,
// la tabla fotografias (rutas y embeddings), eventos.foto_id y eventos.credencial_id.
const COLUMNS = {
  personas: 'id,usuario_id,nombre_demo,email,telefono,vinculo,rol,estado,requiere_tour,'
    + 'horario_inicio,horario_fin,vinculo_hasta,consentimiento_biometrico,consentimiento_fecha,creado_en',
  visitas: 'id,persona_id,responsable_id,categoria,motivo,empresa,destino,inicio,fin,estado,nivel_ayuda,creado_en',
  credenciales: 'id,persona_id,visita_id,tipo,valido_desde,valido_hasta,revocada_en,creado_en',
  eventos: 'id,visita_id,persona_candidata_id,fuente,evidencia,categoria,resultado,motivo,orientacion,'
    + 'duracion_ms,creado_en,corregido_por,correccion_motivo,corregido_en,modo_reconocimiento',
  espacios: 'clave,nombre,capacidad',                                   // migración 006 (opcional)
  avisos: 'id,destinatario_id,visita_id,tipo,mensaje,punto_encuentro,estado,creado_en,actualizado_en', // 007 (opcional)
  auditoria_panel: 'id,actor_id,accion,persona_id,cambios,creado_en',   // propuesta 009 (opcional)
};

const HISTORY_DAYS = 30;
const MAX_EVENTS = 1000;

(function () {
  const config = window.NCLUB_SUPABASE_CONFIG || SUPABASE_CONFIG;

  function isSecretKey(key) {
    if (key.startsWith('sb_secret_')) return true;
    const parts = key.split('.');
    if (parts.length !== 3) return false;
    try {
      const payload = JSON.parse(atob(parts[1].replace(/-/g, '+').replace(/_/g, '/')));
      return payload.role === 'service_role';
    } catch {
      return false;
    }
  }

  function setupProblem() {
    const { url, publishableKey } = config;
    if (!url || !publishableKey) return 'Falta la URL o la clave pública en js/supabase.js.';
    if (!/^https:\/\/[a-z0-9-]+\.supabase\.co\/?$/i.test(url)) return 'La URL no parece la de un proyecto de Supabase (https://<ref>.supabase.co).';
    if (isSecretKey(publishableKey)) return 'La clave configurada es SECRETA (service_role o sb_secret_). Bórrala de js/supabase.js y usa la clave pública.';
    if (!window.supabase?.createClient) return 'No se pudo cargar la librería supabase-js (¿sin conexión a internet?).';
    return null;
  }

  const problem = setupProblem();
  const client = problem
    ? null
    : window.supabase.createClient(config.url.replace(/\/$/, ''), config.publishableKey, {
      auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: false, storageKey: 'nclub-panel-auth' },
    });

  // Traduce los errores de PostgREST / Postgres / red a mensajes para la persona usuaria.
  function toError(error, context) {
    const raw = error?.message || String(error || '');
    const err = new Error(raw);
    err.code = error?.code;
    if (/Failed to fetch|NetworkError|Load failed/i.test(raw)) {
      err.message = 'No hay conexión con Supabase. Revisa internet e inténtalo de nuevo.';
      err.network = true;
    } else if (error?.code === 'PGRST301' || /JWT expired|invalid JWT/i.test(raw)) {
      err.message = 'La sesión expiró. Inicia sesión de nuevo.';
      err.expired = true;
    } else if (error?.code === 'PGRST202') {
      err.message = `La función ${context} no existe en la base de datos: falta aplicar la migración propuesta.`;
      err.missing = true;
    } else if (error?.code === 'PGRST205' || error?.code === '42P01') {
      err.message = `La tabla ${context} no existe en el proyecto.`;
      err.missing = true;
    } else if (error?.code === '42501') {
      err.message = /^permission denied/i.test(raw) ? `Permiso denegado por la base de datos (${context}).` : raw;
      err.denied = true;
    } else if (error?.code === '23514') {
      err.message = `Los datos no cumplen las reglas de la base de datos (${context}).`;
    } else if (error?.code === '42703') {
      err.message = `Columna inexistente en ${context}: ${raw}`;
    }
    return err;
  }

  async function guard(context, run) {
    let res;
    try {
      res = await run();
    } catch (e) {
      throw toError(e, context);
    }
    if (res.error) throw toError(res.error, context);
    return res.data;
  }

  const read = (table, build) => guard(table, () => build(client.from(table).select(COLUMNS[table]))).then((d) => d ?? []);
  const rpc = (fn, args) => guard(fn, () => client.rpc(fn, args));
  const optional = (promise) => promise.catch((err) => (err.missing ? err : Promise.reject(err)));
  const since = () => new Date(Date.now() - HISTORY_DAYS * 24 * 60 * 60 * 1000).toISOString();

  const api = {
    configured: !problem,
    problem,
    projectHost: problem ? null : new URL(config.url).host,
    historyDays: HISTORY_DAYS,

    async getSession() {
      if (!client) return null;
      const { data } = await client.auth.getSession();
      return data.session;
    },

    onAuthChange(callback) {
      client?.auth.onAuthStateChange((event) => callback(event));
    },

    // Solo cuentas existentes. El panel no ofrece registro.
    async signIn(email, password) {
      let res;
      try {
        res = await client.auth.signInWithPassword({ email: email.trim().toLowerCase(), password });
      } catch (e) {
        throw toError(e, 'auth');
      }
      if (res.error) {
        const msg = res.error.message || '';
        if (/invalid login credentials/i.test(msg)) throw new Error('Correo o contraseña incorrectos.');
        if (/email not confirmed/i.test(msg)) throw new Error('La cuenta aún no confirmó su correo.');
        if (/rate limit|too many/i.test(msg)) throw new Error('Demasiados intentos. Espera unos minutos.');
        throw toError(res.error, 'auth');
      }
    },

    async signOut() {
      await client?.auth.signOut();
    },

    // Quién es la sesión y qué puede hacer. panel_permisos() es de la propuesta 009: si no
    // existe, se usa el modelo actual (es_operador = rol operador o admin).
    async getAccess() {
      const [personaId, isOperator, permisos] = await Promise.all([
        rpc('mi_persona_id'),
        rpc('es_operador'),
        optional(rpc('panel_permisos')),
      ]);
      let persona = null;
      if (personaId) {
        const rows = await read('personas', (q) => q.eq('id', personaId).limit(1));
        persona = rows[0] ?? null;
      }
      return { personaId, persona, isOperator: !!isOperator, permisos: permisos instanceof Error ? null : permisos };
    },

    // Lee solo lo que el rol puede ver: RLS filtraría igual, así se evitan consultas inútiles.
    async loadSnapshot({ verVisitas, verEventos, verAuditoria }) {
      const from = since();
      const none = Promise.resolve([]);
      const ultimoDia = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
      const [personas, visitas, credenciales, eventos, espacios, auditoria, avisos] = await Promise.all([
        read('personas', (q) => q.order('nombre_demo').limit(5000)),
        verVisitas ? read('visitas', (q) => q.gte('fin', from).order('inicio', { ascending: false }).limit(5000)) : none,
        verVisitas ? read('credenciales', (q) => q.is('revocada_en', null).limit(10000)) : none,
        verEventos ? read('eventos', (q) => q.gte('creado_en', from).order('creado_en', { ascending: false }).limit(MAX_EVENTS)) : none,
        optional(read('espacios', (q) => q.eq('activo', true))),
        verAuditoria ? optional(read('auditoria_panel', (q) => q.order('creado_en', { ascending: false }).limit(200))) : none,
        // Avisos de llegada al anfitrión (007): RLS deja verlos a recepción (es_operador()).
        verVisitas ? optional(read('avisos', (q) => q.gte('creado_en', ultimoDia).order('creado_en', { ascending: false }).limit(500))) : none,
      ]);
      const warnings = [];
      if (avisos instanceof Error) warnings.push('Los avisos de llegada (migración 007) no están en el proyecto: no se pueden ver los que quedaron sin respuesta.');
      if (espacios instanceof Error) warnings.push('El catálogo de espacios (migración 006) no está en el proyecto: se usan los nombres locales de las zonas.');
      if (eventos.length === MAX_EVENTS) warnings.push(`Se muestran solo los ${MAX_EVENTS} eventos más recientes.`);
      return {
        personas,
        visitas,
        credenciales,
        eventos,
        espacios: espacios instanceof Error ? null : espacios,
        auditoria: auditoria instanceof Error ? null : auditoria,
        avisos: avisos instanceof Error ? null : avisos,
        warnings,
        loadedAt: Date.now(),
      };
    },

    // --- Escrituras: solo funciones existentes que validan permisos en el servidor ------------
    // crear_invitacion (003): el responsable es quien la crea. Devuelve el token UNA sola vez.
    crearInvitacion(d) {
      return rpc('crear_invitacion', {
        p_nombre: d.nombre,
        p_email: d.email,
        p_destino: d.destino,
        p_inicio: new Date(d.inicio).toISOString(),
        p_fin: new Date(d.fin).toISOString(),
        p_categoria: d.categoria,
        p_empresa: d.empresa || null,
        p_motivo: d.motivo || null,
      });
    },

    revocarInvitacion(visitaId, motivo) {
      return rpc('revocar_invitacion', { p_visita: visitaId, p_motivo: motivo || null });
    },

    corregirEvento(eventoId, categoria, motivo, personaId) {
      return rpc('corregir_evento', { p_evento: eventoId, p_categoria: categoria, p_motivo: motivo, p_persona: personaId || null });
    },

    // Propuesta 009: si no está aplicada, la base responde PGRST202 y el panel lo explica.
    asignarRol(personaId, rol) {
      return rpc('asignar_rol', { p_persona: personaId, p_rol: rol });
    },

    actualizarPersona(personaId, c) {
      return rpc('admin_actualizar_persona', {
        p_persona: personaId,
        p_estado: c.estado ?? null,
        p_vinculo: c.vinculo ?? null,
        p_horario_inicio: c.horario_inicio ?? null,
        p_horario_fin: c.horario_fin ?? null,
        p_vinculo_hasta: c.vinculo_hasta ?? null,
        p_sin_vencimiento: !!c.sin_vencimiento,
        p_requiere_tour: c.requiere_tour ?? null,
      });
    },
  };

  window.NClubDB = Object.freeze(api);
})();
