-- =============================================================================
-- N Club · Rediseño: personas, credenciales, visitas y eventos
--
--   personas      : quién es (vínculo permanente con el club, rol en la app, biometría opcional)
--   credenciales  : cómo lo demuestra (QR con token protegido, vigencia, revocación, restricciones)
--   visitas       : a qué viene hoy (categoría, responsable, destino, horario, nivel de ayuda)
--   eventos       : qué pasó en recepción (evidencia, categoría resuelta, orientación, resultado)
--
-- La orientación corresponde a la VISITA activa, no a una etiqueta permanente: un empleado puede
-- venir otro día como invitado. Para el MVP, cada vínculo distinto es un perfil separado.
-- Reemplaza miembros / accesos_temporales (estaban vacías).
-- =============================================================================

-- --- Quitar el esquema anterior --------------------------------------------------------------
select cron.unschedule('limpiar-accesos-vencidos');
drop function if exists public.identificar_por_cara(extensions.vector, double precision);
drop function if exists public.validar_qr(text);
drop function if exists public.completar_tour(uuid);
drop function if exists public.marcar_ingreso_temporal(uuid);
drop function if exists public.respuesta_miembro(public.miembros, text);
drop function if exists public.en_horario(time, time);
drop table if exists public.accesos_temporales;
drop table if exists public.miembros;
drop function if exists public.nuevo_qr_token();
drop type if exists public.tipo_miembro;
drop type if exists public.tipo_acceso_temporal;

-- --- Tipos ------------------------------------------------------------------------------------
create type public.vinculo_club     as enum ('ninguno', 'regular', 'vip', 'personal');
create type public.rol_app          as enum ('usuario', 'operador', 'admin');
create type public.estado_persona   as enum ('activa', 'suspendida');
create type public.categoria_visita as enum ('regular', 'vip', 'personal', 'invitado', 'externo');
create type public.estado_visita    as enum ('programada', 'en_curso', 'finalizada', 'cancelada');
create type public.tipo_credencial  as enum ('qr_personal', 'qr_visita');
create type public.nivel_ayuda      as enum ('indicacion', 'mapa', 'acompanamiento');
create type public.resultado_evento as enum ('orientado', 'rechazado', 'pendiente_revision',
                                             'corregido');

-- --- personas ---------------------------------------------------------------------------------
create table public.personas (
  id                        uuid primary key default gen_random_uuid(),
  -- Cuenta de Supabase Auth (las contraseñas las maneja Auth). Los invitados no tienen cuenta.
  usuario_id                uuid unique references auth.users (id) on delete cascade,
  nombre_demo               text not null,
  email                     text,
  telefono                  text,
  -- Quien se registra en la app queda como miembro regular. VIP, personal y roles los asigna el club.
  vinculo                   public.vinculo_club not null default 'regular',
  rol                       public.rol_app not null default 'usuario',
  estado                    public.estado_persona not null default 'activa',
  requiere_tour             boolean not null default true,
  horario_inicio            time default '06:00',
  horario_fin               time default '21:00',
  -- Biometría voluntaria: siempre hay alternativa con QR o atención humana.
  foto_ref                  text,                       -- ruta en el bucket privado "fotos"
  face_embedding            extensions.vector(512),
  consentimiento_biometrico boolean not null default false,
  consentimiento_fecha      timestamptz,
  creado_en                 timestamptz not null default now(),
  actualizado_en            timestamptz not null default now(),

  constraint solo_regular_requiere_tour check (vinculo = 'regular' or not requiere_tour),
  constraint horario_valido check (
    (vinculo = 'ninguno' and horario_inicio is null and horario_fin is null)
    or (vinculo in ('regular', 'vip') and horario_fin > horario_inicio
        and horario_inicio >= '06:00' and horario_fin <= '21:00')
    or (vinculo = 'personal' and horario_fin > horario_inicio
        and horario_inicio >= '04:00' and horario_fin <= '22:00'
        and horario_fin - horario_inicio <= interval '8 hours')
  ),
  constraint huella_con_consentimiento check (face_embedding is null or consentimiento_biometrico)
);

create trigger personas_actualizado_en
  before update on public.personas
  for each row execute function public.tocar_actualizado_en();

-- --- visitas ----------------------------------------------------------------------------------
create table public.visitas (
  id              uuid primary key default gen_random_uuid(),
  persona_id      uuid not null references public.personas (id) on delete cascade,
  responsable_id  uuid references public.personas (id) on delete set null,  -- anfitrión o responsable
  categoria       public.categoria_visita not null,
  motivo          text,
  empresa         text,
  destino         text,                       -- clave de la zona; un miembro lo elige al llegar
  inicio          timestamptz not null,
  fin             timestamptz not null,
  estado          public.estado_visita not null default 'programada',
  nivel_ayuda     public.nivel_ayuda,
  creado_en       timestamptz not null default now(),

  constraint ventana_valida check (fin > inicio),
  constraint externo_con_empresa check (categoria <> 'externo' or empresa is not null),
  constraint temporal_con_responsable_y_destino check (
    categoria not in ('invitado', 'externo') or (responsable_id is not null and destino is not null)
  )
);

create index visitas_persona_idx     on public.visitas (persona_id);
create index visitas_responsable_idx on public.visitas (responsable_id);
create index visitas_fin_idx         on public.visitas (fin);

-- --- credenciales -----------------------------------------------------------------------------
create table public.credenciales (
  id                 uuid primary key default gen_random_uuid(),
  persona_id         uuid not null references public.personas (id) on delete cascade,
  visita_id          uuid references public.visitas (id) on delete cascade,
  tipo               public.tipo_credencial not null,
  token_hash         text not null unique,      -- sha256 del token; el token solo se entrega una vez
  valido_desde       timestamptz not null default now(),
  valido_hasta       timestamptz,
  revocada_en        timestamptz,
  motivo_revocacion  text,
  restricciones      jsonb not null default '{}'::jsonb,  -- p. ej. {"zonas": ["restaurante"]}
  creado_en          timestamptz not null default now(),

  constraint vigencia_valida check (valido_hasta is null or valido_hasta > valido_desde),
  constraint qr_visita_con_visita check (
    (tipo = 'qr_personal' and visita_id is null) or (tipo = 'qr_visita' and visita_id is not null)
  )
);

create index credenciales_persona_idx on public.credenciales (persona_id);
create index credenciales_visita_idx  on public.credenciales (visita_id);

-- --- eventos ----------------------------------------------------------------------------------
-- La evidencia guarda estados y distancias, no datos personales ni imágenes.
create table public.eventos (
  id                    uuid primary key default gen_random_uuid(),
  visita_id             uuid references public.visitas (id) on delete set null,
  persona_candidata_id  uuid references public.personas (id) on delete set null,
  credencial_id         uuid references public.credenciales (id) on delete set null,
  fuente                text not null default 'simulacion' check (fuente in ('robot', 'simulacion')),
  evidencia             jsonb not null default '{}'::jsonb,
  categoria             public.categoria_visita,          -- categoría resuelta (null si no se pudo)
  resultado             public.resultado_evento not null,
  motivo                text,
  orientacion           jsonb,                            -- destino, nivel de ayuda, ruta
  duracion_ms           integer,
  creado_en             timestamptz not null default now(),
  corregido_por         uuid references public.personas (id) on delete set null,
  correccion_motivo     text,
  corregido_en          timestamptz
);

create index eventos_visita_idx     on public.eventos (visita_id);
create index eventos_candidata_idx  on public.eventos (persona_candidata_id);
create index eventos_credencial_idx on public.eventos (credencial_id);
create index eventos_corregido_idx  on public.eventos (corregido_por);
create index eventos_pendientes_idx on public.eventos (creado_en) where resultado = 'pendiente_revision';

-- --- Utilidades -------------------------------------------------------------------------------
create or replace function public.hash_token(p_token text)
returns text language sql immutable set search_path = '' as $$
  select encode(extensions.digest(p_token, 'sha256'), 'hex');
$$;

create or replace function public.nuevo_token()
returns text language sql volatile set search_path = '' as $$
  select encode(extensions.gen_random_bytes(32), 'hex');
$$;

create or replace function public.en_horario(p_inicio time, p_fin time)
returns boolean language sql stable set search_path = '' as $$
  select (now() at time zone 'America/Bogota')::time >= p_inicio
     and (now() at time zone 'America/Bogota')::time <  p_fin;
$$;

-- Persona del usuario con sesión iniciada.
create or replace function public.mi_persona_id()
returns uuid language sql stable security definer set search_path = '' as $$
  select id from public.personas where usuario_id = auth.uid();
$$;

create or replace function public.es_operador()
returns boolean language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.personas
                  where usuario_id = auth.uid() and estado = 'activa'
                    and rol in ('operador', 'admin'));
$$;

-- Ayuda que puede elegir cada categoría. El externo siempre va acompañado (zonas restringidas).
create or replace function public.ayuda_disponible(p_categoria public.categoria_visita)
returns public.nivel_ayuda[] language sql immutable set search_path = '' as $$
  select case p_categoria
    when 'externo' then array['acompanamiento']::public.nivel_ayuda[]
    else array['indicacion', 'mapa', 'acompanamiento']::public.nivel_ayuda[]
  end;
$$;

-- =============================================================================================
-- Robot (solo con la clave de servicio, desde el backend)
-- =============================================================================================

-- Recibe la evidencia (huella facial y/o token del QR), resuelve la categoría y registra el evento.
-- Devuelve solo lo necesario para orientar.
create or replace function public.registrar_llegada(
  p_embedding  extensions.vector(512) default null,
  p_token      text default null,
  p_umbral     double precision default 0.40,   -- hasta aquí la cara se acepta
  p_umbral_duda double precision default 0.50,  -- entre umbral y esto: duda, va a recepción
  p_fuente     text default 'robot'
)
returns jsonb
language plpgsql
volatile
security definer
set search_path = public, extensions
as $$
declare
  v_cand       public.personas;
  v_dist       double precision;
  v_cara       text := 'no_usada';
  v_cred       public.credenciales;
  v_qr         text := 'no_presentado';
  v_persona    public.personas;
  v_visita     public.visitas;
  v_categoria  public.categoria_visita;
  v_resultado  public.resultado_evento := 'orientado';
  v_motivo     text;
  v_evento     uuid;
begin
  -- 1. Evidencia facial (solo personas con consentimiento).
  if p_embedding is not null then
    select * into v_cand from public.personas
     where face_embedding is not null and consentimiento_biometrico
     order by face_embedding <=> p_embedding limit 1;
    if found then
      v_dist := v_cand.face_embedding <=> p_embedding;
    end if;
    v_cara := case when v_dist is null then 'sin_candidato'
                   when v_dist <= p_umbral then 'reconocida'
                   when v_dist <= p_umbral_duda then 'dudosa'
                   else 'no_reconocida' end;
    if v_cara not in ('reconocida', 'dudosa') then
      v_cand := null;
    end if;
  end if;

  -- 2. Credencial.
  if p_token is not null then
    select * into v_cred from public.credenciales where token_hash = public.hash_token(p_token);
    v_qr := case when not found then 'no_encontrada'
                 when v_cred.revocada_en is not null then 'revocada'
                 when now() < v_cred.valido_desde then 'aun_no_valida'
                 when v_cred.valido_hasta is not null and now() > v_cred.valido_hasta then 'vencida'
                 else 'valida' end;
  end if;

  -- 3. Decisión. El robot no crea permisos ni resuelve contradicciones: las pasa a recepción.
  if v_qr = 'valida' and v_cara = 'reconocida' and v_cand.id <> v_cred.persona_id then
    v_resultado := 'pendiente_revision'; v_motivo := 'contradiccion_cara_credencial';
  elsif v_qr in ('no_encontrada', 'revocada', 'aun_no_valida', 'vencida') then
    v_resultado := 'rechazado'; v_motivo := 'credencial_' || v_qr;
  elsif v_qr = 'valida' then
    select * into v_persona from public.personas where id = v_cred.persona_id;
  elsif v_cara = 'reconocida' then
    v_persona := v_cand;
  elsif v_cara = 'dudosa' then
    v_resultado := 'pendiente_revision'; v_motivo := 'identidad_dudosa';
  else
    v_resultado := 'rechazado'; v_motivo := 'no_identificado';
  end if;

  if v_resultado = 'orientado' and v_persona.estado <> 'activa' then
    v_resultado := 'rechazado'; v_motivo := 'persona_suspendida';
  end if;

  -- 4. Visita: la del QR de visita, o una nueva para el miembro / personal que llega.
  if v_resultado = 'orientado' then
    if v_cred.tipo = 'qr_visita' then
      select * into v_visita from public.visitas where id = v_cred.visita_id;
      if v_visita.estado = 'cancelada' then
        v_resultado := 'rechazado'; v_motivo := 'visita_cancelada';
      else
        v_categoria := v_visita.categoria;
        update public.visitas set estado = 'en_curso' where id = v_visita.id;
      end if;
    elsif v_persona.vinculo = 'ninguno' then
      v_resultado := 'rechazado'; v_motivo := 'sin_visita_activa';
    elsif not public.en_horario(v_persona.horario_inicio, v_persona.horario_fin) then
      v_resultado := 'rechazado'; v_motivo := 'fuera_de_horario';
      v_categoria := v_persona.vinculo::text::public.categoria_visita;
    else
      v_categoria := v_persona.vinculo::text::public.categoria_visita;
      insert into public.visitas (persona_id, categoria, inicio, fin, estado)
      values (v_persona.id, v_categoria, now(),
              (date_trunc('day', now() at time zone 'America/Bogota') + v_persona.horario_fin)
                at time zone 'America/Bogota',
              'en_curso')
      returning * into v_visita;
    end if;
  end if;

  insert into public.eventos (visita_id, persona_candidata_id, credencial_id, fuente, evidencia,
                              categoria, resultado, motivo)
  values (v_visita.id, coalesce(v_persona.id, v_cand.id), v_cred.id, p_fuente,
          jsonb_build_object('cara', v_cara, 'distancia', round(v_dist::numeric, 3), 'qr', v_qr),
          v_categoria, v_resultado, v_motivo)
  returning id into v_evento;

  return jsonb_build_object(
    'evento_id', v_evento,
    'resultado', v_resultado,
    'motivo', v_motivo,
    'evidencia', jsonb_build_object('cara', v_cara, 'distancia', round(v_dist::numeric, 3),
                                    'qr', v_qr),
    'categoria', v_categoria,
    'nombre', case when v_resultado = 'orientado' then v_persona.nombre_demo end,
    'visita_id', v_visita.id,
    'destino', v_visita.destino,
    'empresa', v_visita.empresa,
    'requiere_tour', coalesce(v_persona.requiere_tour, false) and v_resultado = 'orientado',
    'ayuda_disponible', case when v_resultado = 'orientado'
                             then to_jsonb(public.ayuda_disponible(v_categoria)) end,
    'horario', case when v_motivo = 'fuera_de_horario'
                    then to_char(v_persona.horario_inicio, 'HH24:MI') || '-'
                         || to_char(v_persona.horario_fin, 'HH24:MI') end
  );
end;
$$;

-- La persona eligió su nivel de ayuda y el robot la orientó.
create or replace function public.registrar_orientacion(
  p_evento      uuid,
  p_nivel       public.nivel_ayuda,
  p_destino     text default null,
  p_duracion_ms integer default null,
  p_ruta        jsonb default null
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_ev public.eventos;
begin
  select * into v_ev from public.eventos where id = p_evento;
  if v_ev.resultado not in ('orientado', 'corregido') then
    raise exception 'El evento % no está habilitado para orientar (%).', p_evento, v_ev.resultado;
  end if;
  if not p_nivel = any (public.ayuda_disponible(v_ev.categoria)) then
    raise exception 'Nivel de ayuda % no disponible para %.', p_nivel, v_ev.categoria;
  end if;
  update public.visitas
     set nivel_ayuda = p_nivel, destino = coalesce(destino, p_destino)
   where id = v_ev.visita_id;
  update public.eventos
     set orientacion = jsonb_build_object('nivel_ayuda', p_nivel,
                                          'destino', (select destino from public.visitas
                                                       where id = v_ev.visita_id),
                                          'ruta', p_ruta),
         duracion_ms = p_duracion_ms
   where id = p_evento;
end;
$$;

-- El D1 terminó el recorrido de bienvenida de un miembro regular.
create or replace function public.completar_tour(p_persona uuid)
returns void language sql security definer set search_path = public as $$
  update public.personas set requiere_tour = false where id = p_persona;
$$;

revoke execute on function public.registrar_llegada(extensions.vector, text, double precision, double precision, text) from public, anon, authenticated;
revoke execute on function public.registrar_orientacion(uuid, public.nivel_ayuda, text, integer, jsonb) from public, anon, authenticated;
revoke execute on function public.completar_tour(uuid) from public, anon, authenticated;
grant  execute on function public.registrar_llegada(extensions.vector, text, double precision, double precision, text) to service_role;
grant  execute on function public.registrar_orientacion(uuid, public.nivel_ayuda, text, integer, jsonb) to service_role;
grant  execute on function public.completar_tour(uuid) to service_role;

-- =============================================================================================
-- App móvil y web (usuario con sesión iniciada)
-- =============================================================================================

-- Genera el QR personal del miembro o del personal. Revoca el anterior y devuelve el token
-- (la base solo guarda su hash; si se pierde, se genera otro).
create or replace function public.generar_mi_qr()
returns text
language plpgsql
security definer
set search_path = public
as $$
declare
  v_yo    public.personas;
  v_token text := public.nuevo_token();
begin
  select * into v_yo from public.personas where usuario_id = auth.uid();
  if v_yo.id is null or v_yo.estado <> 'activa' or v_yo.vinculo = 'ninguno' then
    raise exception 'Solo los miembros y el personal activos tienen QR personal.';
  end if;
  update public.credenciales
     set revocada_en = now(), motivo_revocacion = 'reemplazada'
   where persona_id = v_yo.id and tipo = 'qr_personal' and revocada_en is null;
  insert into public.credenciales (persona_id, tipo, token_hash)
  values (v_yo.id, 'qr_personal', public.hash_token(v_token));
  return v_token;
end;
$$;

-- Crea la persona invitada, su visita y su QR. Devuelve el token para enviarlo por correo.
-- Regulares y VIP invitan; el personal y los operadores registran trabajadores externos.
create or replace function public.crear_invitacion(
  p_nombre     text,
  p_email      text,
  p_destino    text,
  p_inicio     timestamptz,
  p_fin        timestamptz,
  p_categoria  public.categoria_visita default 'invitado',
  p_empresa    text default null,
  p_motivo     text default null
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_yo      public.personas;
  v_persona uuid;
  v_visita  uuid;
  v_token   text := public.nuevo_token();
begin
  select * into v_yo from public.personas where usuario_id = auth.uid();
  if v_yo.id is null or v_yo.estado <> 'activa' then
    raise exception 'Necesitas una cuenta activa del club.';
  end if;
  if p_categoria = 'invitado' and v_yo.vinculo not in ('regular', 'vip') and v_yo.rol = 'usuario' then
    raise exception 'Solo los miembros invitan.';
  elsif p_categoria = 'externo' and v_yo.vinculo <> 'personal' and v_yo.rol = 'usuario' then
    raise exception 'Solo el personal o un operador registran trabajadores externos.';
  elsif p_categoria not in ('invitado', 'externo') then
    raise exception 'Una invitación solo puede ser para invitado o externo.';
  end if;

  insert into public.personas (nombre_demo, email, vinculo, requiere_tour, horario_inicio, horario_fin)
  values (p_nombre, p_email, 'ninguno', false, null, null)
  returning id into v_persona;
  insert into public.visitas (persona_id, responsable_id, categoria, motivo, empresa, destino,
                              inicio, fin)
  values (v_persona, v_yo.id, p_categoria, p_motivo, p_empresa, p_destino, p_inicio, p_fin)
  returning id into v_visita;
  insert into public.credenciales (persona_id, visita_id, tipo, token_hash, valido_desde,
                                   valido_hasta, restricciones)
  values (v_persona, v_visita, 'qr_visita', public.hash_token(v_token), p_inicio, p_fin,
          jsonb_build_object('zonas', jsonb_build_array(p_destino)));
  return jsonb_build_object('visita_id', v_visita, 'token', v_token);
end;
$$;

-- El responsable (o un operador) cancela una invitación y revoca su QR.
create or replace function public.revocar_invitacion(p_visita uuid, p_motivo text default null)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  if not exists (select 1 from public.visitas
                  where id = p_visita
                    and (responsable_id = public.mi_persona_id() or public.es_operador())) then
    raise exception 'No puedes revocar esta invitación.';
  end if;
  update public.visitas set estado = 'cancelada' where id = p_visita;
  update public.credenciales
     set revocada_en = now(), motivo_revocacion = coalesce(p_motivo, 'revocada por el responsable')
   where visita_id = p_visita and revocada_en is null;
end;
$$;

-- Recepción corrige una resolución dejando motivo; la evidencia original no se toca.
-- Si confirma quién es la persona (p_persona), el evento queda ligado a su visita activa, o a una
-- visita nueva si es miembro o personal, para que el robot pueda orientarla.
create or replace function public.corregir_evento(
  p_evento    uuid,
  p_categoria public.categoria_visita,
  p_motivo    text,
  p_persona   uuid default null
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_visita uuid;
begin
  if not public.es_operador() then
    raise exception 'Solo un operador de recepción puede corregir eventos.';
  end if;
  if coalesce(trim(p_motivo), '') = '' then
    raise exception 'La corrección necesita un motivo.';
  end if;
  if p_persona is not null then
    select id into v_visita from public.visitas
     where persona_id = p_persona and estado in ('programada', 'en_curso')
       and now() between inicio and fin
     order by inicio desc limit 1;
    if v_visita is null and p_categoria in ('invitado', 'externo') then
      raise exception 'Esa persona no tiene una invitación vigente; créala con crear_invitacion.';
    elsif v_visita is null then
      insert into public.visitas (persona_id, categoria, motivo, inicio, fin, estado)
      values (p_persona, p_categoria, 'habilitada por recepción', now(), now() + interval '4 hours',
              'en_curso')
      returning id into v_visita;
    end if;
  end if;
  update public.eventos
     set categoria = p_categoria, resultado = 'corregido', corregido_por = public.mi_persona_id(),
         correccion_motivo = p_motivo, corregido_en = now(),
         persona_candidata_id = coalesce(p_persona, persona_candidata_id),
         visita_id = coalesce(v_visita, visita_id)
   where id = p_evento;
end;
$$;

revoke execute on function public.generar_mi_qr() from public, anon;
revoke execute on function public.crear_invitacion(text, text, text, timestamptz, timestamptz, public.categoria_visita, text, text) from public, anon;
revoke execute on function public.revocar_invitacion(uuid, text) from public, anon;
revoke execute on function public.corregir_evento(uuid, public.categoria_visita, text, uuid) from public, anon;
revoke execute on function public.mi_persona_id() from public, anon;
revoke execute on function public.es_operador() from public, anon;
grant  execute on function public.generar_mi_qr() to authenticated;
grant  execute on function public.crear_invitacion(text, text, text, timestamptz, timestamptz, public.categoria_visita, text, text) to authenticated;
grant  execute on function public.revocar_invitacion(uuid, text) to authenticated;
grant  execute on function public.corregir_evento(uuid, public.categoria_visita, text, uuid) to authenticated;
grant  execute on function public.mi_persona_id() to authenticated;
grant  execute on function public.es_operador() to authenticated;

-- =============================================================================================
-- Permisos por fila (RLS)
-- =============================================================================================
alter table public.personas     enable row level security;
alter table public.visitas      enable row level security;
alter table public.credenciales enable row level security;
alter table public.eventos      enable row level security;

revoke all on public.personas, public.visitas, public.credenciales, public.eventos from anon;
revoke insert, update, delete on public.personas, public.visitas, public.credenciales,
  public.eventos from authenticated;

-- El usuario solo escribe sus datos personales: vínculo, rol, estado, horario, tour y huella
-- facial los controla el club.
grant insert (usuario_id, nombre_demo, email, telefono, foto_ref, consentimiento_biometrico,
              consentimiento_fecha) on public.personas to authenticated;
grant update (nombre_demo, telefono, foto_ref, consentimiento_biometrico, consentimiento_fecha)
  on public.personas to authenticated;

create policy "ve su perfil, sus invitados o todo si es operador" on public.personas
  for select to authenticated using (
    usuario_id = (select auth.uid())
    or (select public.es_operador())
    or exists (select 1 from public.visitas v
                where v.persona_id = personas.id
                  and v.responsable_id = (select public.mi_persona_id()))
  );
create policy "crea su propio perfil" on public.personas
  for insert to authenticated with check (usuario_id = (select auth.uid()));
create policy "edita su propio perfil" on public.personas
  for update to authenticated
  using (usuario_id = (select auth.uid())) with check (usuario_id = (select auth.uid()));

create policy "ve sus visitas e invitaciones" on public.visitas
  for select to authenticated using (
    persona_id = (select public.mi_persona_id())
    or responsable_id = (select public.mi_persona_id())
    or (select public.es_operador())
  );

create policy "ve sus credenciales" on public.credenciales
  for select to authenticated using (
    persona_id = (select public.mi_persona_id()) or (select public.es_operador())
  );

create policy "recepción ve los eventos" on public.eventos
  for select to authenticated using ((select public.es_operador()));

-- =============================================================================================
-- Limpieza: se borran los invitados y externos cuando termina su visita. Los eventos se
-- conservan sin datos personales (sus referencias quedan en null).
-- =============================================================================================
create or replace function public.limpiar_visitas_vencidas()
returns void language sql security definer set search_path = public as $$
  delete from public.personas p
   where p.vinculo = 'ninguno' and p.usuario_id is null
     and not exists (select 1 from public.visitas v where v.persona_id = p.id and v.fin >= now());
  update public.visitas set estado = 'finalizada'
   where fin < now() and estado in ('programada', 'en_curso');
$$;
revoke execute on function public.limpiar_visitas_vencidas() from public, anon, authenticated;

select cron.schedule('limpiar-visitas-vencidas', '*/5 * * * *',
                     $$ select public.limpiar_visitas_vencidas(); $$);
