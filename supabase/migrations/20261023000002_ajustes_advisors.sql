-- =============================================================================
-- Ajustes sugeridos por los advisors de Supabase
--   - search_path fijo en las funciones auxiliares
--   - auth.uid() envuelto en (select ...) para que las políticas lo evalúen una sola vez
-- =============================================================================

alter function public.nuevo_qr_token()                          set search_path = public;
alter function public.tocar_actualizado_en()                    set search_path = public;
alter function public.en_horario(time, time)                    set search_path = public;
alter function public.respuesta_miembro(public.miembros, text)  set search_path = public;

alter policy "miembro ve su fila" on public.miembros
  using (id = (select auth.uid()));
alter policy "miembro crea su fila" on public.miembros
  with check (id = (select auth.uid()));
alter policy "miembro edita su fila" on public.miembros
  using (id = (select auth.uid())) with check (id = (select auth.uid()));

alter policy "miembro ve sus invitaciones" on public.accesos_temporales
  using (invitado_por = (select auth.uid()));
alter policy "miembro borra sus invitaciones" on public.accesos_temporales
  using (invitado_por = (select auth.uid()));
alter policy "miembro crea invitaciones" on public.accesos_temporales
  with check (
    invitado_por = (select auth.uid())
    and exists (
      select 1 from public.miembros m
       where m.id = (select auth.uid()) and m.activo
         and ((accesos_temporales.tipo = 'invitado' and m.tipo in ('regular', 'vip'))
           or (accesos_temporales.tipo = 'externo'  and m.tipo = 'personal'))
    )
  );
