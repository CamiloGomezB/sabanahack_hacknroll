-- =============================================================================================
-- PROPUESTA — NO APLICADA. Revisar con el club antes de moverla a supabase/migrations.
--
-- La app ya tiene interfaces y datos de demostración para estas funciones; esta migración define el
-- modelo que falta para persistirlas con las mismas reglas que el resto del esquema:
--   espacios / reglas_reserva / reservas : catálogo real, reglas por vínculo y reservas sin solape
--   tareas_personal                      : tareas del día de cada persona del personal
--   solicitudes_servicio                 : consulta / solicitud de equipo externo (no es contratación)
-- Horas evaluadas en hora de Colombia, igual que public.en_horario().
-- =============================================================================================

create extension if not exists btree_gist with schema extensions;

-- --- Catálogo de espacios ---------------------------------------------------------------------
-- La clave es la misma que se guarda en visitas.destino ("clave de la zona").
create table public.espacios (
  clave           text primary key check (clave ~ '^[a-z0-9-]+$'),
  nombre          text not null,
  descripcion     text,
  capacidad       integer not null default 0 check (capacidad >= 0),
  reservable_por  public.vinculo_club[] not null default '{}',
  activo          boolean not null default true
);

create table public.reglas_reserva (
  vinculo                public.vinculo_club primary key check (vinculo in ('regular', 'vip')),
  max_dias_anticipacion  integer not null check (max_dias_anticipacion between 0 and 90),
  max_horas_por_reserva  integer not null check (max_horas_por_reserva between 1 and 12)
);

-- Valores de ejemplo (los mismos supuestos de src/constants/spaces.ts). Reemplazar por los reales.
insert into public.reglas_reserva values ('regular', 7, 2), ('vip', 14, 4);

-- --- Reservas -----------------------------------------------------------------------------------
create type public.estado_reserva as enum ('confirmada', 'cancelada');

create table public.reservas (
  id          uuid primary key default gen_random_uuid(),
  persona_id  uuid not null references public.personas (id) on delete cascade,
  espacio     text not null references public.espacios (clave),
  inicio      timestamptz not null,
  fin         timestamptz not null,
  estado      public.estado_reserva not null default 'confirmada',
  creado_en   timestamptz not null default now(),

  constraint reserva_ventana check (fin > inicio),
  -- Un espacio no puede tener dos reservas confirmadas que se crucen.
  constraint reserva_sin_solape exclude using gist (
    espacio with =, tstzrange(inicio, fin) with &&
  ) where (estado = 'confirmada')
);
create index reservas_persona_idx on public.reservas (persona_id);

-- Franjas de una hora del día pedido, dentro del horario de la persona, con su disponibilidad.
create or replace function public.disponibilidad_espacio(p_espacio text, p_fecha date)
returns table (inicio timestamptz, disponible boolean)
language plpgsql stable security definer set search_path = public as $$
declare
  v_yo  public.personas;
  h     time;
  v_ini timestamptz;
begin
  select * into v_yo from public.personas where usuario_id = auth.uid();
  if v_yo.id is null or not exists (
       select 1 from public.espacios e
        where e.clave = p_espacio and e.activo and v_yo.vinculo = any (e.reservable_por)) then
    raise exception 'No puedes consultar este espacio.';
  end if;
  h := v_yo.horario_inicio;
  while h + interval '1 hour' <= v_yo.horario_fin loop
    v_ini := (p_fecha + h) at time zone 'America/Bogota';
    inicio := v_ini;
    disponible := v_ini > now() and not exists (
      select 1 from public.reservas r
       where r.espacio = p_espacio and r.estado = 'confirmada'
         and tstzrange(r.inicio, r.fin) && tstzrange(v_ini, v_ini + interval '1 hour'));
    return next;
    h := h + interval '1 hour';
  end loop;
end;
$$;

-- Verifica permisos, reglas y disponibilidad; el constraint de exclusión evita carreras.
create or replace function public.reservar_espacio(p_espacio text, p_inicio timestamptz, p_horas integer)
returns uuid
language plpgsql security definer set search_path = public as $$
declare
  v_yo     public.personas;
  v_regla  public.reglas_reserva;
  v_local  timestamp := p_inicio at time zone 'America/Bogota';
  v_id     uuid;
begin
  select * into v_yo from public.personas where usuario_id = auth.uid();
  if v_yo.id is null or v_yo.estado <> 'activa'
     or (v_yo.vinculo_hasta is not null and v_yo.vinculo_hasta < (now() at time zone 'America/Bogota')::date) then
    raise exception 'Necesitas una membresía activa.';
  end if;
  select * into v_regla from public.reglas_reserva where vinculo = v_yo.vinculo;
  if not found or not exists (
       select 1 from public.espacios e
        where e.clave = p_espacio and e.activo and v_yo.vinculo = any (e.reservable_por)) then
    raise exception 'Tu plan no permite reservar este espacio.';
  end if;
  if p_horas < 1 or p_horas > v_regla.max_horas_por_reserva then
    raise exception 'Puedes reservar hasta % h seguidas.', v_regla.max_horas_por_reserva;
  end if;
  if p_inicio <= now()
     or v_local::date > (now() at time zone 'America/Bogota')::date + v_regla.max_dias_anticipacion then
    raise exception 'Fecha fuera del rango permitido.';
  end if;
  if v_local::time < v_yo.horario_inicio or (v_local + make_interval(hours => p_horas))::time > v_yo.horario_fin
     or (v_local + make_interval(hours => p_horas))::date <> v_local::date then
    raise exception 'La reserva está fuera de tu horario.';
  end if;

  begin
    insert into public.reservas (persona_id, espacio, inicio, fin)
    values (v_yo.id, p_espacio, p_inicio, p_inicio + make_interval(hours => p_horas))
    returning id into v_id;
  exception when exclusion_violation then
    raise exception 'La franja elegida ya no está disponible.';
  end;
  return v_id;
end;
$$;

create or replace function public.cancelar_reserva(p_reserva uuid)
returns void language plpgsql security definer set search_path = public as $$
begin
  update public.reservas set estado = 'cancelada'
   where id = p_reserva and estado = 'confirmada'
     and (persona_id = public.mi_persona_id() or public.es_operador());
  if not found then
    raise exception 'No puedes cancelar esta reserva.';
  end if;
end;
$$;

-- --- Tareas del personal ------------------------------------------------------------------------
create type public.estado_tarea as enum ('pendiente', 'completada');

create table public.tareas_personal (
  id             uuid primary key default gen_random_uuid(),
  persona_id     uuid not null references public.personas (id) on delete cascade,
  titulo         text not null check (length(trim(titulo)) > 0),
  area           text references public.espacios (clave),
  fecha          date not null default (now() at time zone 'America/Bogota')::date,
  hora           time,
  estado         public.estado_tarea not null default 'pendiente',
  completada_en  timestamptz,
  asignada_por   uuid references public.personas (id) on delete set null,
  creado_en      timestamptz not null default now()
);
create index tareas_persona_fecha_idx on public.tareas_personal (persona_id, fecha);

create or replace function public.marcar_tarea(p_tarea uuid, p_completada boolean)
returns void language plpgsql security definer set search_path = public as $$
begin
  update public.tareas_personal
     set estado = case when p_completada then 'completada' else 'pendiente' end::public.estado_tarea,
         completada_en = case when p_completada then now() end
   where id = p_tarea and persona_id = public.mi_persona_id();
  if not found then
    raise exception 'No puedes modificar esta tarea.';
  end if;
end;
$$;

-- --- Solicitudes de servicio externo -----------------------------------------------------------
-- Registra la consulta; la contratación la aprueba un operador. El acceso de cada trabajador se
-- sigue creando con public.crear_invitacion(..., 'externo', empresa, motivo).
create type public.estado_solicitud as enum ('enviada', 'en_revision', 'aprobada', 'rechazada', 'cancelada');

create table public.solicitudes_servicio (
  id                  uuid primary key default gen_random_uuid(),
  solicitante_id      uuid not null references public.personas (id) on delete cascade,
  tipo_servicio       text not null,
  descripcion         text not null check (length(trim(descripcion)) >= 10),
  area                text not null references public.espacios (clave),
  fecha_requerida     date not null,
  trabajadores        integer not null check (trabajadores between 1 and 50),
  proveedor_sugerido  text,
  estado              public.estado_solicitud not null default 'enviada',
  revisada_por        uuid references public.personas (id) on delete set null,
  revisada_en         timestamptz,
  creado_en           timestamptz not null default now()
);
create index solicitudes_solicitante_idx on public.solicitudes_servicio (solicitante_id);

create or replace function public.resolver_solicitud(p_solicitud uuid, p_estado public.estado_solicitud)
returns void language plpgsql security definer set search_path = public as $$
begin
  if not public.es_operador() then
    raise exception 'Solo un operador resuelve solicitudes.';
  end if;
  update public.solicitudes_servicio
     set estado = p_estado, revisada_por = public.mi_persona_id(), revisada_en = now()
   where id = p_solicitud;
end;
$$;

-- =============================================================================================
-- Permisos y RLS
-- =============================================================================================
alter table public.espacios             enable row level security;
alter table public.reglas_reserva       enable row level security;
alter table public.reservas             enable row level security;
alter table public.tareas_personal      enable row level security;
alter table public.solicitudes_servicio enable row level security;

revoke all on public.espacios, public.reglas_reserva, public.reservas, public.tareas_personal,
              public.solicitudes_servicio from anon;
revoke insert, update, delete on public.espacios, public.reglas_reserva, public.reservas,
              public.tareas_personal from authenticated;
revoke insert, update, delete on public.solicitudes_servicio from authenticated;

create policy "catálogo visible" on public.espacios for select to authenticated using (activo);
create policy "reglas visibles" on public.reglas_reserva for select to authenticated using (true);

create policy "ve sus reservas" on public.reservas for select to authenticated using (
  persona_id = (select public.mi_persona_id()) or (select public.es_operador())
);

create policy "ve sus tareas" on public.tareas_personal for select to authenticated using (
  persona_id = (select public.mi_persona_id()) or (select public.es_operador())
);

create policy "ve sus solicitudes" on public.solicitudes_servicio for select to authenticated using (
  solicitante_id = (select public.mi_persona_id()) or (select public.es_operador())
);
grant insert (solicitante_id, tipo_servicio, descripcion, area, fecha_requerida, trabajadores,
              proveedor_sugerido) on public.solicitudes_servicio to authenticated;
create policy "el personal solicita" on public.solicitudes_servicio for insert to authenticated
  with check (
    solicitante_id = (select public.mi_persona_id())
    and exists (select 1 from public.personas p
                 where p.id = solicitante_id and p.estado = 'activa'
                   and (p.vinculo = 'personal' or p.rol in ('operador', 'admin')))
  );

revoke execute on function public.disponibilidad_espacio(text, date) from public, anon;
revoke execute on function public.reservar_espacio(text, timestamptz, integer) from public, anon;
revoke execute on function public.cancelar_reserva(uuid) from public, anon;
revoke execute on function public.marcar_tarea(uuid, boolean) from public, anon;
revoke execute on function public.resolver_solicitud(uuid, public.estado_solicitud) from public, anon;
grant  execute on function public.disponibilidad_espacio(text, date) to authenticated;
grant  execute on function public.reservar_espacio(text, timestamptz, integer) to authenticated;
grant  execute on function public.cancelar_reserva(uuid) to authenticated;
grant  execute on function public.marcar_tarea(uuid, boolean) to authenticated;
grant  execute on function public.resolver_solicitud(uuid, public.estado_solicitud) to authenticated;
