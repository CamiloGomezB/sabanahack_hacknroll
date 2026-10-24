-- =============================================================================================
-- PROPUESTA · NO APLICADA · Ajuste de datos existentes a la regla de 24 h
--
-- MODIFICA FILAS EXISTENTES. Aplicar solo después de la 009 y con aprobación explícita.
-- Revisa primero cuántas filas cambian con las consultas de vista previa del final.
--
--   - Invitaciones vigentes que empiezan 24 h o más después de su registro: no caben en la regla,
--     así que se cancelan y su QR se revoca.
--   - Las demás se recortan a creado_en + 24 h (el trigger de la 009 fija fin y valido_hasta).
--     Si ese momento ya pasó, la visita queda vencida y limpiar_visitas_vencidas() borrará los
--     datos personales del invitado o externo en menos de 5 minutos.
-- =============================================================================================

update public.visitas
   set estado = 'cancelada'
 where categoria in ('invitado', 'externo')
   and estado in ('programada', 'en_curso')
   and inicio >= creado_en + interval '24 hours';

update public.credenciales c
   set revocada_en = now(), motivo_revocacion = 'fuera de la vigencia de 24 h'
  from public.visitas v
 where c.visita_id = v.id
   and c.revocada_en is null
   and v.categoria in ('invitado', 'externo')
   and v.inicio >= v.creado_en + interval '24 hours';

-- "set x = x" basta para que el trigger recalcule el límite.
update public.visitas
   set fin = fin
 where categoria in ('invitado', 'externo')
   and inicio < creado_en + interval '24 hours'
   and fin is distinct from creado_en + interval '24 hours';

update public.credenciales c
   set valido_hasta = c.valido_hasta
  from public.visitas v
 where c.visita_id = v.id
   and c.tipo = 'qr_visita'
   and v.inicio < v.creado_en + interval '24 hours'
   and c.valido_hasta is distinct from v.creado_en + interval '24 hours';

-- Vista previa (ejecutar antes, por separado):
-- select count(*) filter (where inicio >= creado_en + interval '24 hours') as se_cancelan,
--        count(*) filter (where inicio <  creado_en + interval '24 hours'
--                           and fin is distinct from creado_en + interval '24 hours') as se_recortan
--   from public.visitas
--  where categoria in ('invitado', 'externo') and estado in ('programada', 'en_curso');
