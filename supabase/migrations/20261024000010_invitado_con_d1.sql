-- Invitados y externos van siempre acompañados por el D1: no conocen el club. Los miembros y el
-- personal siguen eligiendo entre indicación, mapa o acompañamiento.
create or replace function public.ayuda_disponible(p_categoria public.categoria_visita)
returns public.nivel_ayuda[] language sql immutable set search_path = '' as $$
  select case
    when p_categoria in ('invitado', 'externo') then array['acompanamiento']::public.nivel_ayuda[]
    else array['indicacion', 'mapa', 'acompanamiento']::public.nivel_ayuda[]
  end;
$$;
