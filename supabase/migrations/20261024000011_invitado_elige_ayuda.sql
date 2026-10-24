-- Deshace 20261024000010: el invitado vuelve a elegir entre indicación, mapa o acompañamiento del
-- D1 (se le pregunta apenas llega, sin esperar al anfitrión). Solo el externo va siempre con el D1.
create or replace function public.ayuda_disponible(p_categoria public.categoria_visita)
returns public.nivel_ayuda[] language sql immutable set search_path = '' as $$
  select case p_categoria
    when 'externo' then array['acompanamiento']::public.nivel_ayuda[]
    else array['indicacion', 'mapa', 'acompanamiento']::public.nivel_ayuda[]
  end;
$$;
