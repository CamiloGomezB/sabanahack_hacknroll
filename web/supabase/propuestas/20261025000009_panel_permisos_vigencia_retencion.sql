-- =============================================================================================
-- PROPUESTA · NO APLICADA · Permisos del panel web, vigencia de 24 h y retención del historial
--
-- Requiere 20261025000008_rol_informatica.sql. No elimina tablas, columnas ni datos al aplicarse,
-- y no cambia registrar_llegada(), generar_mi_qr(), las fotografías ni las políticas existentes.
-- crear_invitacion() conserva su firma y su lógica para todos los roles actuales; solo se añade
-- que el rol nuevo "informatica" cuenta como "usuario" al invitar (sección 3b).
-- Todo lo que añade:
--
--   1. Rol de la sesión para el panel: mi_rol_panel(), es_admin(), es_informatica().
--   2. Lectura para informática: personas del club (nunca invitados ni externos) y eventos.
--   3. Administración validada en el servidor y auditada:
--        asignar_rol()               admin e informática
--        admin_actualizar_persona()  solo admin
--        panel_permisos()            lo que puede hacer la sesión (el panel lo lee al entrar)
--   4. Invitados y externos: la autorización vence EXACTAMENTE 24 h después del registro de la
--      invitación (triggers en visitas y credenciales). La limpieza de sus datos personales sigue
--      a cargo de limpiar_visitas_vencidas() (pg_cron, cada 5 min), sin depender del panel.
--   5. Retención independiente del historial (pg_cron, diario). ATENCIÓN: este job sí elimina
--      datos cuando se cumplen los plazos; revisa los plazos antes de aprobar:
--        - a los 90 días el evento pierde sus vínculos personales (persona, visita, credencial,
--          foto, quién corrigió y el texto libre de la corrección);
--        - a los 365 días se eliminan los eventos y la auditoría del panel.
-- =============================================================================================

-- ---------------------------------------------------------------------------------------------
-- 1. Rol de la sesión
-- ---------------------------------------------------------------------------------------------
-- Rol de la persona con sesión iniciada, solo si está activa y su vínculo no venció.
create or replace function public.mi_rol_panel()
returns public.rol_app language sql stable security definer set search_path = '' as $$
  select rol from public.personas
   where usuario_id = auth.uid() and estado = 'activa'
     and (vinculo_hasta is null or vinculo_hasta >= (now() at time zone 'America/Bogota')::date);
$$;

create or replace function public.es_admin()
returns boolean language sql stable security definer set search_path = '' as $$
  select coalesce(public.mi_rol_panel() = 'admin', false);
$$;

create or replace function public.es_informatica()
returns boolean language sql stable security definer set search_path = '' as $$
  select coalesce(public.mi_rol_panel() = 'informatica', false);
$$;

-- ---------------------------------------------------------------------------------------------
-- 2. Lectura para informática (las políticas permisivas se suman a las existentes)
-- ---------------------------------------------------------------------------------------------
create policy "informática ve las personas del club" on public.personas
  for select to authenticated using (vinculo <> 'ninguno' and (select public.es_informatica()));

create policy "informática ve los eventos" on public.eventos
  for select to authenticated using ((select public.es_informatica()));

-- ---------------------------------------------------------------------------------------------
-- 3. Auditoría y administración
-- ---------------------------------------------------------------------------------------------
-- Solo guarda quién cambió qué campo administrativo (rol, estado, vínculo, horario, vigencia).
create table public.auditoria_panel (
  id          uuid primary key default gen_random_uuid(),
  actor_id    uuid references public.personas (id) on delete set null,
  accion      text not null check (accion in ('asignar_rol', 'actualizar_persona')),
  persona_id  uuid references public.personas (id) on delete set null,
  cambios     jsonb not null default '{}'::jsonb,
  creado_en   timestamptz not null default now()
);
create index auditoria_panel_creado_idx  on public.auditoria_panel (creado_en);
create index auditoria_panel_actor_idx   on public.auditoria_panel (actor_id);
create index auditoria_panel_persona_idx on public.auditoria_panel (persona_id);

alter table public.auditoria_panel enable row level security;
revoke all on public.auditoria_panel from anon;
revoke insert, update, delete on public.auditoria_panel from authenticated;
create policy "admin e informática ven la auditoría" on public.auditoria_panel
  for select to authenticated using ((select public.mi_rol_panel()) in ('admin', 'informatica'));

-- Asigna un rol. Reglas:
--   - lo hacen admin o informática; nadie cambia su propio rol;
--   - la persona debe tener cuenta, y los roles de panel son solo para el personal;
--   - informática no asigna ni quita el rol de administrador.
create or replace function public.asignar_rol(p_persona uuid, p_rol public.rol_app)
returns void language plpgsql security definer set search_path = '' as $$
declare
  v_rol   public.rol_app := public.mi_rol_panel();
  v_actor uuid := public.mi_persona_id();
  v_obj   public.personas;
begin
  if v_rol is null or v_rol not in ('admin', 'informatica') then
    raise exception 'Solo administración o informática pueden asignar roles.' using errcode = '42501';
  end if;
  select * into v_obj from public.personas where id = p_persona for update;
  if v_obj.id is null then
    raise exception 'La persona no existe.';
  elsif v_obj.id = v_actor then
    raise exception 'No puedes cambiar tu propio rol.';
  elsif v_obj.usuario_id is null then
    raise exception 'La persona no tiene cuenta en la app.';
  elsif p_rol <> 'usuario' and v_obj.vinculo <> 'personal' then
    raise exception 'Solo el personal del club puede tener un rol de panel.';
  elsif v_rol = 'informatica' and (p_rol = 'admin' or v_obj.rol = 'admin') then
    raise exception 'Informática no puede asignar ni quitar el rol de administrador.' using errcode = '42501';
  end if;
  if v_obj.rol = p_rol then
    return;
  end if;
  update public.personas set rol = p_rol where id = p_persona;
  insert into public.auditoria_panel (actor_id, accion, persona_id, cambios)
  values (v_actor, 'asignar_rol', p_persona, jsonb_build_object('rol', jsonb_build_array(v_obj.rol, p_rol)));
end;
$$;

-- Cambia los datos administrativos de un miembro o del personal. Los parámetros null no cambian
-- nada; p_sin_vencimiento quita vinculo_hasta. Los CHECK de personas validan horarios y tour.
create or replace function public.admin_actualizar_persona(
  p_persona         uuid,
  p_estado          public.estado_persona default null,
  p_vinculo         public.vinculo_club   default null,
  p_horario_inicio  time                  default null,
  p_horario_fin     time                  default null,
  p_vinculo_hasta   date                  default null,
  p_sin_vencimiento boolean               default false,
  p_requiere_tour   boolean               default null
)
returns void language plpgsql security definer set search_path = '' as $$
declare
  v_actor   uuid := public.mi_persona_id();
  v_antes   public.personas;
  v_despues public.personas;
  v_vinculo public.vinculo_club;
begin
  if not public.es_admin() then
    raise exception 'Solo un administrador puede editar personas.' using errcode = '42501';
  end if;
  select * into v_antes from public.personas where id = p_persona for update;
  if v_antes.id is null then
    raise exception 'La persona no existe.';
  elsif v_antes.vinculo = 'ninguno' then
    raise exception 'Los invitados y externos se gestionan desde su visita.';
  elsif p_vinculo = 'ninguno' then
    raise exception 'El vínculo debe ser regular, vip o personal.';
  elsif v_antes.id = v_actor and p_estado = 'suspendida' then
    raise exception 'No puedes suspender tu propia cuenta.';
  end if;

  v_vinculo := coalesce(p_vinculo, v_antes.vinculo);
  update public.personas set
    estado         = coalesce(p_estado, estado),
    vinculo        = v_vinculo,
    horario_inicio = coalesce(p_horario_inicio, horario_inicio),
    horario_fin    = coalesce(p_horario_fin, horario_fin),
    vinculo_hasta  = case when p_sin_vencimiento then null else coalesce(p_vinculo_hasta, vinculo_hasta) end,
    requiere_tour  = case when v_vinculo = 'regular' then coalesce(p_requiere_tour, requiere_tour) else false end,
    rol            = case when v_vinculo = 'personal' then rol else 'usuario' end
   where id = p_persona
  returning * into v_despues;

  insert into public.auditoria_panel (actor_id, accion, persona_id, cambios)
  select v_actor, 'actualizar_persona', p_persona,
         coalesce(jsonb_object_agg(a.key, jsonb_build_array(a.value, d.value)), '{}'::jsonb)
    from jsonb_each(to_jsonb(v_antes)) a
    join jsonb_each(to_jsonb(v_despues)) d on d.key = a.key
   where a.key in ('estado', 'vinculo', 'horario_inicio', 'horario_fin', 'vinculo_hasta', 'requiere_tour', 'rol')
     and a.value is distinct from d.value;
end;
$$;

-- Lo que puede hacer la sesión. El panel lo usa para mostrar u ocultar secciones; la seguridad
-- real la siguen aplicando RLS y las comprobaciones dentro de cada función.
create or replace function public.panel_permisos()
returns jsonb language sql stable security definer set search_path = '' as $$
  with r as (select public.mi_rol_panel() as rol)
  select jsonb_build_object(
    'version',                  1,
    'rol',                      r.rol,
    'ver_personas',             coalesce(r.rol in ('admin', 'informatica', 'operador'), false),
    'ver_visitas',              coalesce(r.rol in ('admin', 'operador'), false),
    'ver_eventos',              coalesce(r.rol in ('admin', 'informatica', 'operador'), false),
    'invitar',                  coalesce(r.rol in ('admin', 'operador'), false),
    'revocar',                  coalesce(r.rol in ('admin', 'operador'), false),
    'corregir_eventos',         coalesce(r.rol in ('admin', 'operador'), false),
    'asignar_roles',            coalesce(r.rol in ('admin', 'informatica'), false),
    'editar_personas',          coalesce(r.rol = 'admin', false),
    'ver_auditoria',            coalesce(r.rol in ('admin', 'informatica'), false),
    'acceso_temporal_horas',    24,
    'eventos_desvincular_dias', 90,
    'eventos_eliminar_dias',    365)
  from r;
$$;

revoke execute on function public.mi_rol_panel() from public, anon;
revoke execute on function public.es_admin() from public, anon;
revoke execute on function public.es_informatica() from public, anon;
revoke execute on function public.asignar_rol(uuid, public.rol_app) from public, anon;
revoke execute on function public.admin_actualizar_persona(uuid, public.estado_persona, public.vinculo_club, time, time, date, boolean, boolean) from public, anon;
revoke execute on function public.panel_permisos() from public, anon;
grant  execute on function public.mi_rol_panel() to authenticated;
grant  execute on function public.es_admin() to authenticated;
grant  execute on function public.es_informatica() to authenticated;
grant  execute on function public.asignar_rol(uuid, public.rol_app) to authenticated;
grant  execute on function public.admin_actualizar_persona(uuid, public.estado_persona, public.vinculo_club, time, time, date, boolean, boolean) to authenticated;
grant  execute on function public.panel_permisos() to authenticated;

-- ---------------------------------------------------------------------------------------------
-- 3b. crear_invitacion(): igual que en la 003, pero informática no tiene privilegios de recepción.
--     Sin este cambio, la comprobación original (rol = 'usuario') dejaría invitar a informática.
--     Como cualquier persona del personal, informática puede seguir registrando externos.
-- ---------------------------------------------------------------------------------------------
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
  v_sin_rol boolean;
begin
  select * into v_yo from public.personas where usuario_id = auth.uid();
  if v_yo.id is null or v_yo.estado <> 'activa' then
    raise exception 'Necesitas una cuenta activa del club.';
  end if;
  v_sin_rol := v_yo.rol in ('usuario', 'informatica');
  if p_categoria = 'invitado' and v_yo.vinculo not in ('regular', 'vip') and v_sin_rol then
    raise exception 'Solo los miembros invitan.';
  elsif p_categoria = 'externo' and v_yo.vinculo <> 'personal' and v_sin_rol then
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

-- ---------------------------------------------------------------------------------------------
-- 4. Invitados y externos: autorización exactamente 24 h después del registro
-- ---------------------------------------------------------------------------------------------
-- El registro es visitas.creado_en (crear_invitacion crea persona, visita y credencial juntas).
-- fin se fija en creado_en + 24 h sin importar lo que pida quien invita, y la visita debe empezar
-- antes de ese momento. registrar_llegada() ya rechaza visitas fuera de [inicio, fin] y
-- credenciales vencidas, así que no hay que tocarla.
create or replace function public.fijar_vigencia_visita_24h()
returns trigger language plpgsql set search_path = '' as $$
begin
  if new.categoria in ('invitado', 'externo') then
    if tg_op = 'UPDATE' then
      new.creado_en := old.creado_en;
    end if;
    new.fin := new.creado_en + interval '24 hours';
    if new.inicio >= new.fin then
      raise exception 'La visita debe empezar antes de % (24 h después del registro).', new.fin;
    end if;
  end if;
  return new;
end;
$$;

-- Solo se dispara si cambian estas columnas: los cambios de estado del robot no lo activan.
create trigger visitas_vigencia_24h
  before insert or update of inicio, fin, categoria, creado_en on public.visitas
  for each row execute function public.fijar_vigencia_visita_24h();

create or replace function public.fijar_vigencia_credencial_24h()
returns trigger language plpgsql set search_path = '' as $$
declare
  v_limite timestamptz;
begin
  if new.tipo = 'qr_visita' then
    select v.creado_en + interval '24 hours' into v_limite from public.visitas v where v.id = new.visita_id;
    if v_limite is not null then
      new.valido_hasta := v_limite;
      if new.valido_desde >= v_limite then
        raise exception 'La credencial debe empezar antes de % (24 h después del registro).', v_limite;
      end if;
    end if;
  end if;
  return new;
end;
$$;

-- revocar_invitacion() y generar_mi_qr() solo cambian revocada_en: no disparan este trigger.
create trigger credenciales_vigencia_24h
  before insert or update of valido_desde, valido_hasta, tipo, visita_id on public.credenciales
  for each row execute function public.fijar_vigencia_credencial_24h();

revoke execute on function public.fijar_vigencia_visita_24h() from public, anon, authenticated;
revoke execute on function public.fijar_vigencia_credencial_24h() from public, anon, authenticated;

-- ---------------------------------------------------------------------------------------------
-- 5. Retención del historial (política independiente de la limpieza de invitados)
-- ---------------------------------------------------------------------------------------------
create or replace function public.aplicar_retencion_historial()
returns void language plpgsql security definer set search_path = '' as $$
begin
  -- 90 días: el evento queda como estadística sin datos personales.
  update public.eventos
     set persona_candidata_id = null, visita_id = null, credencial_id = null, foto_id = null,
         corregido_por = null, correccion_motivo = null
   where creado_en < now() - interval '90 days'
     and (persona_candidata_id is not null or visita_id is not null or credencial_id is not null
          or foto_id is not null or corregido_por is not null or correccion_motivo is not null);

  -- 365 días: se eliminan.
  delete from public.eventos where creado_en < now() - interval '365 days';
  delete from public.auditoria_panel where creado_en < now() - interval '365 days';
end;
$$;
revoke execute on function public.aplicar_retencion_historial() from public, anon, authenticated;

-- 08:15 UTC = 03:15 en Bogotá.
select cron.schedule('retencion-historial', '15 8 * * *', $$ select public.aplicar_retencion_historial(); $$);
