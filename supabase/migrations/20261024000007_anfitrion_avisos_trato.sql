-- =============================================================================================
-- ANFITRIÓN: lo que el robot necesita para preparar el siguiente paso de cada visita.
--   personas.trato          : cómo prefiere la persona que le hable el robot (solo el tono)
--   visitas.punto_encuentro : dónde se encuentra el invitado con su anfitrión (o el externo con su
--                             responsable); si es null, el destino de la visita
--   avisos                  : aviso de llegada al anfitrión o responsable, con su estado. "Emitido"
--                             no significa "enterado": recibido y aceptado los marca la app
--   novedades               : novedades operativas para el personal al iniciar el turno
--   contexto_llegada()      : lo que el robot consulta después de registrar_llegada (solo backend)
-- =============================================================================================

-- --- Cómo hablarle a cada persona -------------------------------------------------------------
alter table public.personas
  add column trato text check (trato is null or length(trim(trato)) between 1 and 400);
comment on column public.personas.trato is
  'Cómo prefiere que le hable el robot (formal o cercano, breve, nombre preferido...). Lo escribe la persona en la app o el club. Solo cambia el tono: nunca permisos ni decisiones.';
grant insert (trato) on public.personas to authenticated;
grant update (trato) on public.personas to authenticated;

-- --- Punto de encuentro de la visita -----------------------------------------------------------
alter table public.visitas
  add column punto_encuentro text references public.espacios (clave);
comment on column public.visitas.punto_encuentro is
  'Espacio donde el anfitrión o responsable recibe a la persona. Null: el destino de la visita.';

-- El anfitrión o responsable puede cambiar el punto de encuentro de sus visitas vigentes.
create or replace function public.cambiar_punto_encuentro(p_visita uuid, p_espacio text)
returns void language plpgsql security definer set search_path = '' as $$
begin
  if not exists (select 1 from public.espacios where clave = p_espacio and activo) then
    raise exception 'Ese espacio no existe.';
  end if;
  update public.visitas set punto_encuentro = p_espacio
   where id = p_visita and estado in ('programada', 'en_curso')
     and (responsable_id = public.mi_persona_id() or public.es_operador());
  if not found then
    raise exception 'No puedes cambiar el encuentro de esta visita.';
  end if;
end;
$$;

-- --- Avisos de llegada ------------------------------------------------------------------------
create type public.estado_aviso as enum ('emitido', 'recibido', 'aceptado', 'sin_respuesta');

create table public.avisos (
  id               uuid primary key default gen_random_uuid(),
  destinatario_id  uuid not null references public.personas (id) on delete cascade,
  visita_id        uuid references public.visitas (id) on delete cascade,
  tipo             text not null check (tipo in ('llegada_invitado', 'llegada_externo')),
  mensaje          text not null,
  punto_encuentro  text references public.espacios (clave),
  estado           public.estado_aviso not null default 'emitido',
  creado_en        timestamptz not null default now(),
  actualizado_en   timestamptz not null default now()
);
create index avisos_destinatario_idx on public.avisos (destinatario_id, creado_en desc);
create index avisos_visita_idx on public.avisos (visita_id);

-- Cuando registrar_llegada pone en curso la visita de un invitado o externo, se avisa a su
-- anfitrión o responsable. Es un trigger para no tocar registrar_llegada.
create or replace function public.avisar_llegada()
returns trigger language plpgsql security definer set search_path = '' as $$
declare
  v_nombre  text;
  v_punto   text := coalesce(new.punto_encuentro, new.destino);
  v_espacio text;
  v_lugar   text;
begin
  if new.responsable_id is null or new.categoria not in ('invitado', 'externo') then
    return new;
  end if;
  select nombre_demo into v_nombre from public.personas where id = new.persona_id;
  select clave, nombre into v_espacio, v_lugar from public.espacios where clave = v_punto;
  insert into public.avisos (destinatario_id, visita_id, tipo, mensaje, punto_encuentro)
  values (new.responsable_id, new.id,
          case new.categoria when 'invitado' then 'llegada_invitado' else 'llegada_externo' end,
          case new.categoria
            when 'invitado' then format('%s llegó a N Club. Encuentro: %s.', v_nombre,
                                        coalesce(v_lugar, v_punto, 'recepción'))
            else format('%s%s llegó para: %s. Encuentro: %s.', v_nombre,
                        coalesce(' (' || new.empresa || ')', ''),
                        coalesce(new.motivo, 'su orden de trabajo'),
                        coalesce(v_lugar, v_punto, 'recepción'))
          end,
          v_espacio);
  return new;
end;
$$;

create trigger visitas_avisar_llegada
  after update of estado on public.visitas
  for each row when (new.estado = 'en_curso' and old.estado is distinct from 'en_curso')
  execute function public.avisar_llegada();

-- El destinatario marca el aviso como recibido o aceptado desde la app.
create or replace function public.responder_aviso(p_aviso uuid, p_estado public.estado_aviso)
returns void language plpgsql security definer set search_path = '' as $$
begin
  if p_estado not in ('recibido', 'aceptado') then
    raise exception 'Solo puedes marcar el aviso como recibido o aceptado.';
  end if;
  update public.avisos set estado = p_estado, actualizado_en = now()
   where id = p_aviso and destinatario_id = public.mi_persona_id() and estado <> 'aceptado';
  if not found then
    raise exception 'No puedes responder este aviso.';
  end if;
end;
$$;

-- --- Novedades del personal -------------------------------------------------------------------
create table public.novedades (
  id          uuid primary key default gen_random_uuid(),
  titulo      text not null check (length(trim(titulo)) > 0),
  detalle     text,
  area        text references public.espacios (clave),
  fecha       date not null default (now() at time zone 'America/Bogota')::date,
  tipo        text not null default 'operativa' check (tipo in ('evento', 'acceso', 'operativa')),
  creada_por  uuid references public.personas (id) on delete set null,
  creado_en   timestamptz not null default now()
);
create index novedades_fecha_idx on public.novedades (fecha);

-- --- Lo que el robot consulta tras registrar la llegada ---------------------------------------
-- Trato, reservas de hoy, visita (responsable y punto de encuentro), tareas y novedades del
-- personal. Solo backend (service_role), como registrar_llegada.
create or replace function public.contexto_llegada(p_persona uuid, p_visita uuid default null)
returns jsonb language sql stable security definer set search_path = '' as $$
  with hoy as (select (now() at time zone 'America/Bogota')::date as d)
  select jsonb_build_object(
    'trato', (select trato from public.personas where id = p_persona),
    'reservas', coalesce((
      select jsonb_agg(jsonb_build_object('espacio', r.espacio, 'nombre', e.nombre,
                                          'inicio', r.inicio, 'fin', r.fin) order by r.inicio)
        from public.reservas r join public.espacios e on e.clave = r.espacio, hoy
       where r.persona_id = p_persona and r.estado = 'confirmada'
         and (r.inicio at time zone 'America/Bogota')::date = hoy.d and r.fin > now()), '[]'),
    'visita', (
      select jsonb_build_object('responsable', p.nombre_demo,
                                'punto_encuentro', coalesce(v.punto_encuentro, v.destino),
                                'motivo', v.motivo, 'empresa', v.empresa)
        from public.visitas v left join public.personas p on p.id = v.responsable_id
       where v.id = p_visita),
    'tareas', coalesce((
      select jsonb_agg(jsonb_build_object('titulo', t.titulo, 'area', t.area, 'hora', t.hora)
                       order by t.hora nulls last)
        from public.tareas_personal t, hoy
       where t.persona_id = p_persona and t.fecha = hoy.d and t.estado = 'pendiente'), '[]'),
    'novedades', case when (select vinculo from public.personas where id = p_persona) = 'personal'
      then coalesce((
        select jsonb_agg(jsonb_build_object('titulo', n.titulo, 'detalle', n.detalle,
                                            'area', n.area, 'tipo', n.tipo))
          from public.novedades n, hoy where n.fecha = hoy.d), '[]')
      else '[]' end);
$$;

-- =============================================================================================
-- Permisos y RLS
-- =============================================================================================
alter table public.avisos    enable row level security;
alter table public.novedades enable row level security;
revoke all on public.avisos, public.novedades from anon;
revoke insert, update, delete on public.avisos, public.novedades from authenticated;

create policy "ve sus avisos" on public.avisos for select to authenticated using (
  destinatario_id = (select public.mi_persona_id()) or (select public.es_operador())
);
create policy "el personal ve las novedades" on public.novedades for select to authenticated using (
  (select public.es_operador()) or exists (
    select 1 from public.personas p
     where p.id = (select public.mi_persona_id()) and p.vinculo = 'personal' and p.estado = 'activa')
);

revoke execute on function public.avisar_llegada() from public, anon, authenticated;
revoke execute on function public.contexto_llegada(uuid, uuid) from public, anon, authenticated;
revoke execute on function public.responder_aviso(uuid, public.estado_aviso) from public, anon;
revoke execute on function public.cambiar_punto_encuentro(uuid, text) from public, anon;
grant  execute on function public.responder_aviso(uuid, public.estado_aviso) to authenticated;
grant  execute on function public.cambiar_punto_encuentro(uuid, text) to authenticated;

-- La app recibe los avisos en vivo (pop-up) con Supabase Realtime; RLS sigue filtrando.
do $$
begin
  if exists (select 1 from pg_publication where pubname = 'supabase_realtime') then
    alter publication supabase_realtime add table public.avisos;
  end if;
end;
$$;
