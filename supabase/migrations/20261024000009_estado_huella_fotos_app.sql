-- Fotos de registro que sube la app móvil: la huella facial la calcula el backend del robot
-- (simulation/huellas_app.py, también dentro de recepcion_fija.py --supabase). La app muestra en
-- qué va cada foto: pendiente (todavía no se procesa), lista (ya sirve para reconocer) o sin_cara
-- (no se encontró una cara que sirva; el detalle dice por qué y la persona puede tomar otra).

alter table public.fotografias
  add column if not exists huella_estado text not null default 'pendiente'
    check (huella_estado in ('pendiente', 'lista', 'sin_cara')),
  add column if not exists huella_detalle text;

update public.fotografias set huella_estado = 'lista' where embedding is not null;

-- La app lee el estado de sus fotos (RLS: solo las suyas); no lo puede escribir.
grant select (huella_estado, huella_detalle) on public.fotografias to authenticated;

create or replace function public.guardar_huella(p_foto uuid, p_embedding extensions.vector(512),
                                                 p_modelo text)
returns void language sql security definer set search_path = public as $$
  update public.fotografias
     set embedding = p_embedding, modelo = p_modelo, huella_estado = 'lista', huella_detalle = null
   where id = p_foto;
$$;
revoke execute on function public.guardar_huella(uuid, extensions.vector, text) from public, anon, authenticated;
grant  execute on function public.guardar_huella(uuid, extensions.vector, text) to service_role;
