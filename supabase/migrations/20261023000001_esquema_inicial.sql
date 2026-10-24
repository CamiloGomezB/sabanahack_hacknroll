-- =============================================================================
-- N Club · Esquema inicial
--   miembros            : miembros regulares, VIP y personal del club (cara + QR)
--   accesos_temporales  : invitados y trabajadores externos (solo QR, con vencimiento)
-- =============================================================================

create extension if not exists vector with schema extensions;
create extension if not exists pg_cron;

create type public.tipo_miembro as enum ('regular', 'vip', 'personal');
create type public.tipo_acceso_temporal as enum ('invitado', 'externo');

-- Token aleatorio de 64 caracteres hexadecimales para los QR.
create or replace function public.nuevo_qr_token()
returns text
language sql
volatile
as $$
  select replace(gen_random_uuid()::text, '-', '') || replace(gen_random_uuid()::text, '-', '');
$$;

-- -----------------------------------------------------------------------------
-- miembros
-- -----------------------------------------------------------------------------
create table public.miembros (
  id                        uuid primary key references auth.users (id) on delete cascade,
  nombre                    text not null,
  apellido                  text not null,
  email                     text not null unique,
  telefono                  text,
  tipo                      public.tipo_miembro not null default 'regular',
  -- Solo un miembro regular nuevo necesita el recorrido guiado por el D1.
  requiere_tour             boolean not null default true,
  -- Horario permitido de ingreso (hora local de Colombia).
  horario_inicio            time not null default '06:00',
  horario_fin               time not null default '21:00',
  foto_url                  text,
  -- Huella facial (512 dimensiones: ArcFace / Facenet512). La calcula el backend a partir de la foto.
  face_embedding            extensions.vector(512),
  qr_token                  text not null unique default public.nuevo_qr_token(),
  consentimiento_biometrico boolean not null default false,
  consentimiento_fecha      timestamptz,
  activo                    boolean not null default true,
  creado_en                 timestamptz not null default now(),
  actualizado_en            timestamptz not null default now(),

  -- Un VIP ya fue miembro regular y el personal ya conoce el club: ninguno requiere tour.
  constraint solo_regular_requiere_tour check (tipo = 'regular' or not requiere_tour),

  -- Miembros: dentro de 06:00–21:00. Personal: turno dentro de 04:00–22:00 de máximo 8 horas.
  constraint horario_valido check (
    horario_fin > horario_inicio
    and (
      (tipo in ('regular', 'vip')
        and horario_inicio >= '06:00' and horario_fin <= '21:00')
      or
      (tipo = 'personal'
        and horario_inicio >= '04:00' and horario_fin <= '22:00'
        and horario_fin - horario_inicio <= interval '8 hours')
    )
  ),

  -- Sin consentimiento no se guarda la huella facial (Ley 1581 de 2012).
  constraint huella_con_consentimiento check (face_embedding is null or consentimiento_biometrico)
);

create or replace function public.tocar_actualizado_en()
returns trigger
language plpgsql
as $$
begin
  new.actualizado_en := now();
  return new;
end;
$$;

create trigger miembros_actualizado_en
  before update on public.miembros
  for each row execute function public.tocar_actualizado_en();

-- -----------------------------------------------------------------------------
-- accesos_temporales
-- -----------------------------------------------------------------------------
create table public.accesos_temporales (
  id            uuid primary key default gen_random_uuid(),
  tipo          public.tipo_acceso_temporal not null,
  nombre        text not null,
  email         text not null,
  empresa       text,
  invitado_por  uuid not null references public.miembros (id) on delete cascade,
  destino       text not null,
  qr_token      text not null unique default public.nuevo_qr_token(),
  valido_desde  timestamptz not null,
  valido_hasta  timestamptz not null,
  usado_en      timestamptz,
  creado_en     timestamptz not null default now(),

  constraint ventana_valida check (valido_hasta > valido_desde),
  constraint externo_con_empresa check (tipo = 'invitado' or empresa is not null)
);

create index accesos_temporales_valido_hasta_idx on public.accesos_temporales (valido_hasta);
create index accesos_temporales_invitado_por_idx on public.accesos_temporales (invitado_por);

-- Borrado automático de los accesos vencidos cada 5 minutos.
select cron.schedule(
  'limpiar-accesos-vencidos',
  '*/5 * * * *',
  $$ delete from public.accesos_temporales where valido_hasta < now(); $$
);

-- -----------------------------------------------------------------------------
-- Funciones para el robot (solo con la clave de servicio)
-- -----------------------------------------------------------------------------
create or replace function public.en_horario(p_inicio time, p_fin time)
returns boolean
language sql
stable
as $$
  select (now() at time zone 'America/Bogota')::time >= p_inicio
     and (now() at time zone 'America/Bogota')::time <  p_fin;
$$;

-- Respuesta común para un miembro identificado (por cara o por QR).
create or replace function public.respuesta_miembro(m public.miembros, p_metodo text)
returns jsonb
language sql
stable
as $$
  select case
    when not m.activo then
      jsonb_build_object('valido', false, 'motivo', 'miembro_inactivo', 'metodo', p_metodo,
                         'id', m.id, 'categoria', m.tipo)
    when not public.en_horario(m.horario_inicio, m.horario_fin) then
      jsonb_build_object('valido', false, 'motivo', 'fuera_de_horario', 'metodo', p_metodo,
                         'id', m.id, 'categoria', m.tipo, 'nombre', m.nombre,
                         'horario_inicio', m.horario_inicio, 'horario_fin', m.horario_fin)
    else
      jsonb_build_object('valido', true, 'origen', 'miembro', 'metodo', p_metodo,
                         'id', m.id, 'categoria', m.tipo, 'nombre', m.nombre,
                         'apellido', m.apellido, 'requiere_guia', m.requiere_tour)
  end;
$$;

-- Reconocimiento facial: busca el miembro más parecido. Si la distancia supera el umbral,
-- la persona se trata como "no miembro" y el robot pide el QR.
create or replace function public.identificar_por_cara(
  p_embedding extensions.vector(512),
  p_umbral    double precision default 0.4
)
returns jsonb
language plpgsql
stable
security definer
set search_path = public, extensions
as $$
declare
  v_id        uuid;
  v_distancia double precision;
  m           public.miembros;
begin
  select id, face_embedding <=> p_embedding
    into v_id, v_distancia
    from public.miembros
   where face_embedding is not null
     and consentimiento_biometrico
   order by face_embedding <=> p_embedding
   limit 1;

  if v_id is null or v_distancia > p_umbral then
    return jsonb_build_object('valido', false, 'motivo', 'no_reconocido', 'metodo', 'cara',
                              'es_miembro', false, 'distancia', v_distancia);
  end if;

  select * into m from public.miembros where id = v_id;
  return public.respuesta_miembro(m, 'cara')
         || jsonb_build_object('es_miembro', true, 'distancia', v_distancia);
end;
$$;

-- QR: primero busca en miembros y luego en accesos temporales.
create or replace function public.validar_qr(p_token text)
returns jsonb
language plpgsql
stable
security definer
set search_path = public, extensions
as $$
declare
  m public.miembros;
  a public.accesos_temporales;
begin
  select * into m from public.miembros where qr_token = p_token;
  if found then
    return public.respuesta_miembro(m, 'qr');
  end if;

  select * into a from public.accesos_temporales where qr_token = p_token;
  if found then
    if now() < a.valido_desde then
      return jsonb_build_object('valido', false, 'motivo', 'aun_no_valido', 'metodo', 'qr',
                                'categoria', a.tipo, 'valido_desde', a.valido_desde);
    end if;
    if now() > a.valido_hasta then
      return jsonb_build_object('valido', false, 'motivo', 'vencido', 'metodo', 'qr',
                                'categoria', a.tipo);
    end if;
    return jsonb_build_object(
      'valido', true, 'origen', 'temporal', 'metodo', 'qr',
      'id', a.id, 'categoria', a.tipo, 'nombre', a.nombre, 'empresa', a.empresa,
      'destino', a.destino, 'requiere_guia', true,
      'invitado_por', (select nombre || ' ' || apellido from public.miembros where id = a.invitado_por)
    );
  end if;

  return jsonb_build_object('valido', false, 'motivo', 'qr_no_encontrado', 'metodo', 'qr');
end;
$$;

-- El D1 terminó el primer recorrido de un miembro regular.
create or replace function public.completar_tour(p_miembro uuid)
returns void
language sql
security definer
set search_path = public
as $$
  update public.miembros set requiere_tour = false where id = p_miembro;
$$;

-- Marca la hora en que un invitado o externo ingresó.
create or replace function public.marcar_ingreso_temporal(p_acceso uuid)
returns void
language sql
security definer
set search_path = public
as $$
  update public.accesos_temporales set usado_en = now() where id = p_acceso and usado_en is null;
$$;

revoke execute on function public.identificar_por_cara(extensions.vector, double precision) from public, anon, authenticated;
revoke execute on function public.validar_qr(text)                     from public, anon, authenticated;
revoke execute on function public.completar_tour(uuid)                 from public, anon, authenticated;
revoke execute on function public.marcar_ingreso_temporal(uuid)        from public, anon, authenticated;
grant  execute on function public.identificar_por_cara(extensions.vector, double precision) to service_role;
grant  execute on function public.validar_qr(text)                     to service_role;
grant  execute on function public.completar_tour(uuid)                 to service_role;
grant  execute on function public.marcar_ingreso_temporal(uuid)        to service_role;

-- -----------------------------------------------------------------------------
-- Seguridad para la app móvil (RLS). El backend usa la clave de servicio y no pasa por aquí.
-- -----------------------------------------------------------------------------
alter table public.miembros           enable row level security;
alter table public.accesos_temporales enable row level security;

-- La app solo puede escribir los datos personales; la categoría, el tour, el horario,
-- el QR y la huella facial los controla el club.
revoke insert, update on public.miembros from anon, authenticated;
grant  insert (id, nombre, apellido, email, telefono, foto_url,
               consentimiento_biometrico, consentimiento_fecha) on public.miembros to authenticated;
grant  update (nombre, apellido, telefono, foto_url,
               consentimiento_biometrico, consentimiento_fecha) on public.miembros to authenticated;

create policy "miembro ve su fila" on public.miembros
  for select to authenticated using (id = auth.uid());
create policy "miembro crea su fila" on public.miembros
  for insert to authenticated with check (id = auth.uid());
create policy "miembro edita su fila" on public.miembros
  for update to authenticated using (id = auth.uid()) with check (id = auth.uid());

revoke insert, update on public.accesos_temporales from anon, authenticated;
grant  insert (tipo, nombre, email, empresa, invitado_por, destino, valido_desde, valido_hasta)
  on public.accesos_temporales to authenticated;

create policy "miembro ve sus invitaciones" on public.accesos_temporales
  for select to authenticated using (invitado_por = auth.uid());
create policy "miembro borra sus invitaciones" on public.accesos_temporales
  for delete to authenticated using (invitado_por = auth.uid());
-- Supuesto: los miembros (regulares y VIP) invitan; solo el personal registra trabajadores externos.
create policy "miembro crea invitaciones" on public.accesos_temporales
  for insert to authenticated with check (
    invitado_por = auth.uid()
    and exists (
      select 1 from public.miembros m
       where m.id = auth.uid() and m.activo
         and ((accesos_temporales.tipo = 'invitado' and m.tipo in ('regular', 'vip'))
           or (accesos_temporales.tipo = 'externo'  and m.tipo = 'personal'))
    )
  );

-- -----------------------------------------------------------------------------
-- Fotos de las caras (Storage privado): cada usuario en su carpeta <uid>/
-- -----------------------------------------------------------------------------
insert into storage.buckets (id, name, public)
values ('fotos', 'fotos', false)
on conflict (id) do nothing;

create policy "usuario sube su foto" on storage.objects
  for insert to authenticated
  with check (bucket_id = 'fotos' and (storage.foldername(name))[1] = auth.uid()::text);
create policy "usuario ve su foto" on storage.objects
  for select to authenticated
  using (bucket_id = 'fotos' and (storage.foldername(name))[1] = auth.uid()::text);
create policy "usuario reemplaza su foto" on storage.objects
  for update to authenticated
  using (bucket_id = 'fotos' and (storage.foldername(name))[1] = auth.uid()::text);
