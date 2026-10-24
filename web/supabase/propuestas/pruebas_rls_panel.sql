-- =============================================================================================
-- Pruebas de RLS, roles del panel, vigencia de 24 h, limpieza y retención.
--
-- EJECUTAR SOLO en una base local (supabase start) o en una rama de Supabase con las
-- migraciones 001–005 y las propuestas 008 y 009 aplicadas. NUNCA en producción.
-- Todo va en una transacción que termina en ROLLBACK: no deja datos.
-- Cada prueba imprime "OK Tn ..." o se detiene con "FALLO Tn ...".
--
-- Estado: escrito pero NO ejecutado (no hay una base de pruebas disponible). Puede necesitar ajustes.
-- =============================================================================================
begin;

-- ---------------------------------------------------------------------------------------------
-- Datos de prueba (como postgres; RLS no aplica)
-- ---------------------------------------------------------------------------------------------
insert into auth.users (id, email) values
  ('a0000000-0000-4000-8000-000000000001', 'admin@prueba.test'),
  ('a0000000-0000-4000-8000-000000000002', 'informatica@prueba.test'),
  ('a0000000-0000-4000-8000-000000000003', 'operador@prueba.test'),
  ('a0000000-0000-4000-8000-000000000004', 'miembro@prueba.test'),
  ('a0000000-0000-4000-8000-000000000005', 'personal@prueba.test');

insert into public.personas (id, usuario_id, nombre_demo, email, vinculo, rol, horario_inicio, horario_fin, requiere_tour) values
  ('b0000000-0000-4000-8000-000000000001', 'a0000000-0000-4000-8000-000000000001', 'Admin Prueba',       'admin@prueba.test',       'personal', 'admin',       '08:00', '16:00', false),
  ('b0000000-0000-4000-8000-000000000002', 'a0000000-0000-4000-8000-000000000002', 'Informática Prueba', 'informatica@prueba.test', 'personal', 'informatica', '08:00', '16:00', false),
  ('b0000000-0000-4000-8000-000000000003', 'a0000000-0000-4000-8000-000000000003', 'Operador Prueba',    'operador@prueba.test',    'personal', 'operador',    '06:00', '14:00', false),
  ('b0000000-0000-4000-8000-000000000004', 'a0000000-0000-4000-8000-000000000004', 'Miembro Prueba',     'miembro@prueba.test',     'regular',  'usuario',     '06:00', '21:00', true),
  ('b0000000-0000-4000-8000-000000000005', 'a0000000-0000-4000-8000-000000000005', 'Personal Prueba',    'personal@prueba.test',    'personal', 'usuario',     '06:00', '14:00', false);

insert into public.eventos (persona_candidata_id, fuente, resultado, categoria) values
  ('b0000000-0000-4000-8000-000000000004', 'simulacion', 'orientado', 'regular');

-- ---------------------------------------------------------------------------------------------
-- T1 · anon no lee nada ni llama funciones del panel
-- ---------------------------------------------------------------------------------------------
set local role anon;
do $$
declare ok_select boolean := false; ok_rpc boolean := false;
begin
  begin perform 1 from public.personas limit 1;
  exception when insufficient_privilege then ok_select := true; end;
  begin perform public.panel_permisos();
  exception when insufficient_privilege then ok_rpc := true; end;
  if not (ok_select and ok_rpc) then raise exception 'FALLO T1: anon tiene acceso'; end if;
  raise notice 'OK T1 anon sin acceso a tablas ni a panel_permisos()';
end $$;
reset role;

-- ---------------------------------------------------------------------------------------------
-- T2 · un miembro (rol usuario) solo ve su fila y ningún evento
-- ---------------------------------------------------------------------------------------------
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"a0000000-0000-4000-8000-000000000004","role":"authenticated"}', true);
do $$
begin
  if (select count(*) from public.personas) <> 1 then raise exception 'FALLO T2: el miembro ve otras personas'; end if;
  if (select count(*) from public.eventos) <> 0 then raise exception 'FALLO T2: el miembro ve eventos'; end if;
  if (public.panel_permisos() ->> 'ver_personas')::boolean then raise exception 'FALLO T2: panel_permisos'; end if;
  raise notice 'OK T2 miembro: solo su perfil, sin eventos ni permisos de panel';
end $$;

-- ---------------------------------------------------------------------------------------------
-- T3 · operador: ve personas y eventos; no administra
-- ---------------------------------------------------------------------------------------------
select set_config('request.jwt.claims', '{"sub":"a0000000-0000-4000-8000-000000000003","role":"authenticated"}', true);
do $$
declare p jsonb := public.panel_permisos(); ok1 boolean := false; ok2 boolean := false;
begin
  if (select count(*) from public.personas where email like '%@prueba.test') <> 5 then raise exception 'FALLO T3: personas'; end if;
  if (select count(*) from public.eventos) < 1 then raise exception 'FALLO T3: eventos'; end if;
  if not (p ->> 'invitar')::boolean or (p ->> 'asignar_roles')::boolean then raise exception 'FALLO T3: permisos %', p; end if;
  begin perform public.asignar_rol('b0000000-0000-4000-8000-000000000005', 'operador');
  exception when insufficient_privilege then ok1 := true; end;
  begin perform public.admin_actualizar_persona('b0000000-0000-4000-8000-000000000004', p_estado => 'suspendida');
  exception when insufficient_privilege then ok2 := true; end;
  if not (ok1 and ok2) then raise exception 'FALLO T3: el operador pudo administrar'; end if;
  raise notice 'OK T3 operador: lee personas y eventos, no asigna roles ni edita personas';
end $$;

-- ---------------------------------------------------------------------------------------------
-- T4 · invitación: vence exactamente 24 h después del registro aunque pidan 7 días
-- ---------------------------------------------------------------------------------------------
do $$
declare r jsonb; v public.visitas; c public.credenciales;
begin
  r := public.crear_invitacion('Invitado Prueba', 'invitado@prueba.test', 'restaurante', now(), now() + interval '7 days');
  select * into v from public.visitas where id = (r ->> 'visita_id')::uuid;
  if v.fin <> v.creado_en + interval '24 hours' then raise exception 'FALLO T4: fin = %', v.fin; end if;
  select * into c from public.credenciales where visita_id = v.id;
  if c.valido_hasta <> v.fin then raise exception 'FALLO T4: credencial vence %', c.valido_hasta; end if;
  raise notice 'OK T4 visita y QR vencen a las 24 h del registro (%)', v.fin;
end $$;

-- T5 · una visita que empieza 24 h o más después del registro se rechaza
do $$
declare ok boolean := false;
begin
  begin perform public.crear_invitacion('Tarde Prueba', 'tarde@prueba.test', 'restaurante', now() + interval '2 days', now() + interval '3 days');
  exception when others then ok := sqlerrm like '%24 h%'; end;
  if not ok then raise exception 'FALLO T5: se aceptó una visita fuera de las 24 h'; end if;
  raise notice 'OK T5 visita fuera de la vigencia rechazada';
end $$;

-- ---------------------------------------------------------------------------------------------
-- T6 · informática: ve el club y los eventos, no a los invitados; asigna roles con límites
-- ---------------------------------------------------------------------------------------------
select set_config('request.jwt.claims', '{"sub":"a0000000-0000-4000-8000-000000000002","role":"authenticated"}', true);
do $$
declare ok_admin boolean := false; ok_quitar boolean := false; ok_propio boolean := false;
        ok_miembro boolean := false; ok_editar boolean := false; ok_invitar boolean := false;
begin
  begin perform public.crear_invitacion('No Debe', 'nodebe@prueba.test', 'restaurante', now(), now() + interval '1 hour');
  exception when others then ok_invitar := sqlerrm like '%miembros invitan%'; end;
  if not ok_invitar then raise exception 'FALLO T6: informática pudo crear una invitación'; end if;

  if (select count(*) from public.personas where email like '%@prueba.test') <> 5 then raise exception 'FALLO T6: personas'; end if;
  if (select count(*) from public.personas where vinculo = 'ninguno') <> 0 then raise exception 'FALLO T6: ve invitados'; end if;
  if (select count(*) from public.visitas) <> 0 then raise exception 'FALLO T6: ve visitas'; end if;
  if (select count(*) from public.credenciales) <> 0 then raise exception 'FALLO T6: ve credenciales'; end if;
  if (select count(*) from public.eventos) < 1 then raise exception 'FALLO T6: no ve eventos'; end if;

  perform public.asignar_rol('b0000000-0000-4000-8000-000000000005', 'operador');

  begin perform public.asignar_rol('b0000000-0000-4000-8000-000000000005', 'admin');
  exception when insufficient_privilege then ok_admin := true; end;
  begin perform public.asignar_rol('b0000000-0000-4000-8000-000000000001', 'usuario');
  exception when insufficient_privilege then ok_quitar := true; end;
  begin perform public.asignar_rol('b0000000-0000-4000-8000-000000000002', 'operador');
  exception when others then ok_propio := sqlerrm like '%propio rol%'; end;
  begin perform public.asignar_rol('b0000000-0000-4000-8000-000000000004', 'operador');
  exception when others then ok_miembro := sqlerrm like '%personal%'; end;
  begin perform public.admin_actualizar_persona('b0000000-0000-4000-8000-000000000004', p_estado => 'suspendida');
  exception when insufficient_privilege then ok_editar := true; end;

  if not (ok_admin and ok_quitar and ok_propio and ok_miembro and ok_editar) then
    raise exception 'FALLO T6: límites de informática (% % % % %)', ok_admin, ok_quitar, ok_propio, ok_miembro, ok_editar;
  end if;
  raise notice 'OK T6 informática: lectura limitada y asignación de roles con restricciones';
end $$;

-- ---------------------------------------------------------------------------------------------
-- T7 · admin: edita personas con auditoría; no se suspende a sí mismo
-- ---------------------------------------------------------------------------------------------
select set_config('request.jwt.claims', '{"sub":"a0000000-0000-4000-8000-000000000001","role":"authenticated"}', true);
do $$
declare p public.personas; ok_self boolean := false;
begin
  perform public.admin_actualizar_persona('b0000000-0000-4000-8000-000000000004', p_vinculo => 'vip');
  select * into p from public.personas where id = 'b0000000-0000-4000-8000-000000000004';
  if p.vinculo <> 'vip' or p.requiere_tour then raise exception 'FALLO T7: vínculo/tour'; end if;
  perform public.admin_actualizar_persona('b0000000-0000-4000-8000-000000000004', p_estado => 'suspendida');
  begin perform public.admin_actualizar_persona('b0000000-0000-4000-8000-000000000001', p_estado => 'suspendida');
  exception when others then ok_self := sqlerrm like '%propia cuenta%'; end;
  if not ok_self then raise exception 'FALLO T7: el admin se suspendió'; end if;
  if (select count(*) from public.auditoria_panel where persona_id in
        ('b0000000-0000-4000-8000-000000000004', 'b0000000-0000-4000-8000-000000000005')) < 3 then
    raise exception 'FALLO T7: auditoría incompleta';
  end if;
  raise notice 'OK T7 admin edita con auditoría';
end $$;

-- El operador no ve la auditoría.
select set_config('request.jwt.claims', '{"sub":"a0000000-0000-4000-8000-000000000003","role":"authenticated"}', true);
do $$
begin
  if (select count(*) from public.auditoria_panel) <> 0 then raise exception 'FALLO T7b: el operador ve la auditoría'; end if;
  raise notice 'OK T7b auditoría oculta para operadores';
end $$;
reset role;

-- ---------------------------------------------------------------------------------------------
-- T8 · los cambios de estado (robot) no disparan el trigger de 24 h
-- ---------------------------------------------------------------------------------------------
do $$
declare v public.visitas; antes timestamptz;
begin
  select * into v from public.visitas where persona_id = (select id from public.personas where email = 'invitado@prueba.test');
  antes := v.fin;
  update public.visitas set estado = 'en_curso' where id = v.id;
  if (select fin from public.visitas where id = v.id) <> antes then raise exception 'FALLO T8'; end if;
  raise notice 'OK T8 cambiar el estado no altera la vigencia';
end $$;

-- ---------------------------------------------------------------------------------------------
-- T9 · limpieza en el servidor: el externo vencido se borra y su evento queda sin vínculos
-- ---------------------------------------------------------------------------------------------
do $$
declare v_persona uuid := 'b0000000-0000-4000-8000-0000000000e1'; v_evento uuid;
begin
  insert into public.personas (id, nombre_demo, email, vinculo, horario_inicio, horario_fin, requiere_tour)
  values (v_persona, 'Externo Vencido', 'externo@prueba.test', 'ninguno', null, null, false);
  insert into public.visitas (persona_id, responsable_id, categoria, empresa, destino, inicio, fin, creado_en)
  values (v_persona, 'b0000000-0000-4000-8000-000000000003', 'externo', 'Empresa Prueba', 'mantenimiento',
          now() - interval '24 hours', now(), now() - interval '25 hours');
  insert into public.eventos (persona_candidata_id, fuente, resultado, categoria)
  values (v_persona, 'simulacion', 'orientado', 'externo') returning id into v_evento;

  perform public.limpiar_visitas_vencidas();

  if exists (select 1 from public.personas where id = v_persona) then raise exception 'FALLO T9: no se borró'; end if;
  if (select persona_candidata_id from public.eventos where id = v_evento) is not null then
    raise exception 'FALLO T9: el evento conserva el vínculo';
  end if;
  raise notice 'OK T9 datos del externo vencido borrados; el evento se conserva';
end $$;

-- ---------------------------------------------------------------------------------------------
-- T10 · retención: a los 90 días sin datos personales, a los 365 días eliminado
-- ---------------------------------------------------------------------------------------------
do $$
declare e90 uuid; e400 uuid; ev public.eventos;
begin
  insert into public.eventos (persona_candidata_id, fuente, resultado, categoria, correccion_motivo, creado_en)
  values ('b0000000-0000-4000-8000-000000000004', 'simulacion', 'corregido', 'regular', 'texto libre', now() - interval '100 days')
  returning id into e90;
  insert into public.eventos (fuente, resultado, creado_en)
  values ('simulacion', 'rechazado', now() - interval '400 days') returning id into e400;

  perform public.aplicar_retencion_historial();

  select * into ev from public.eventos where id = e90;
  if ev.id is null or ev.persona_candidata_id is not null or ev.correccion_motivo is not null then
    raise exception 'FALLO T10: el evento de 100 días conserva datos personales';
  end if;
  if exists (select 1 from public.eventos where id = e400) then raise exception 'FALLO T10: no se eliminó el de 400 días'; end if;
  raise notice 'OK T10 retención aplicada';
end $$;

rollback;
