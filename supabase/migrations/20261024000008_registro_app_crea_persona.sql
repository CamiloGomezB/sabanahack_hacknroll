-- Registro de la app móvil: el perfil (personas) se guarda en el mismo momento del registro.
--
-- Antes la app creaba la fila de personas en el primer inicio de sesión. Con la confirmación de
-- correo activa, quien se registraba y no volvía a entrar quedaba solo en auth.users, sin perfil:
-- recepción no lo veía y el robot no lo podía reconocer. Ahora un trigger sobre auth.users crea el
-- perfil con los datos que manda la app en signUp (options.data: nombre, telefono,
-- consentimiento_biometrico). La app sigue creando el perfil si no lo encuentra (cuentas de antes).
--
-- Igual que el insert de la app: vínculo 'regular' por defecto; VIP y personal los asigna el club.

create or replace function public.crear_persona_de_registro()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  meta jsonb := coalesce(new.raw_user_meta_data, '{}'::jsonb);
  consiente boolean := coalesce(meta->>'consentimiento_biometrico', '') = 'true';
begin
  insert into public.personas (usuario_id, nombre_demo, email, telefono,
                               consentimiento_biometrico, consentimiento_fecha)
  values (
    new.id,
    coalesce(nullif(left(trim(meta->>'nombre'), 120), ''),
             nullif(split_part(coalesce(new.email, ''), '@', 1), ''), 'Miembro'),
    lower(new.email),
    nullif(left(trim(meta->>'telefono'), 40), ''),
    consiente,
    case when consiente then now() end
  )
  on conflict (usuario_id) do nothing;
  return new;
end;
$$;

revoke execute on function public.crear_persona_de_registro() from public, anon, authenticated;

drop trigger if exists registro_crea_persona on auth.users;
create trigger registro_crea_persona
  after insert on auth.users
  for each row execute function public.crear_persona_de_registro();

-- Cuentas que ya se registraron y nunca entraron: se les crea el perfil ahora.
insert into public.personas (usuario_id, nombre_demo, email, telefono,
                             consentimiento_biometrico, consentimiento_fecha)
select u.id,
       coalesce(nullif(left(trim(u.raw_user_meta_data->>'nombre'), 120), ''),
                nullif(split_part(coalesce(u.email, ''), '@', 1), ''), 'Miembro'),
       lower(u.email),
       nullif(left(trim(u.raw_user_meta_data->>'telefono'), 40), ''),
       coalesce(u.raw_user_meta_data->>'consentimiento_biometrico', '') = 'true',
       case when coalesce(u.raw_user_meta_data->>'consentimiento_biometrico', '') = 'true'
            then u.created_at end
from auth.users u
where not exists (select 1 from public.personas p where p.usuario_id = u.id);
