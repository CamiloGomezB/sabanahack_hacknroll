-- =============================================================================================
-- Reconocimiento real junto al simulado
--
-- - registrar_llegada compara solo con huellas del mismo modelo (p_modelo): las de un modelo real
--   no se mezclan con las sintéticas de la demo. Los umbrales los pasa quien llama, según el modelo.
-- - Un invitado o externo reconocido por cara (si registró su foto) entra con su visita activa,
--   sin necesidad de QR. La orientación siempre corresponde a la visita activa.
-- =============================================================================================
drop function public.registrar_llegada(extensions.vector, text, text, boolean, uuid, double precision, double precision, double precision, text);

create or replace function public.registrar_llegada(
  p_embedding      extensions.vector(512) default null,
  p_token          text default null,
  p_modo           text default 'real',          -- 'real' o 'simulado'
  p_captura_valida boolean default true,         -- false: no se detectó una cara usable
  p_foto           uuid default null,            -- foto de llegada (para auditar la prueba)
  p_umbral         double precision default 0.40, -- hasta aquí la cara se acepta
  p_umbral_duda    double precision default 0.50, -- más allá de esto: desconocida
  p_margen         double precision default 0.05, -- distancia mínima entre los dos mejores
  p_fuente         text default 'robot',
  p_modelo         text default null             -- solo compara huellas de este modelo
)
returns jsonb
language plpgsql
volatile
security definer
set search_path = public, extensions
as $$
declare
  v_cand_id    uuid;
  v_dist       double precision;
  v_dist2      double precision;
  v_cara       text := 'no_usada';
  v_detalle    text;
  v_cred       public.credenciales;
  v_qr         text := 'no_presentado';
  v_persona    public.personas;
  v_visita     public.visitas;
  v_categoria  public.categoria_visita;
  v_resultado  public.resultado_evento := 'orientado';
  v_motivo     text;
  v_evidencia  jsonb;
  v_evento     uuid;
begin
  if p_modo not in ('real', 'simulado') then
    raise exception 'p_modo debe ser real o simulado.';
  end if;

  -- 1. Reconocimiento: solo fotos de registro autorizadas, del mismo modelo, de personas con
  --    consentimiento. Se toma la mejor distancia de cada persona y se comparan los dos mejores.
  if not p_captura_valida then
    v_cara := 'captura_no_valida';
  elsif p_embedding is not null then
    with por_persona as (
      select f.persona_id, min(f.embedding <=> p_embedding) as dist
        from public.fotografias f
        join public.personas p on p.id = f.persona_id
       where f.uso = 'registro' and f.autorizada and f.embedding is not null
         and (p_modelo is null or f.modelo = p_modelo)
         and p.consentimiento_biometrico
       group by f.persona_id
    ), ordenado as (
      select persona_id, dist, row_number() over (order by dist) as n from por_persona
    )
    select max(persona_id::text) filter (where n = 1)::uuid,
           max(dist) filter (where n = 1), max(dist) filter (where n = 2)
      into v_cand_id, v_dist, v_dist2
      from ordenado where n <= 2;

    if v_dist is null or v_dist > p_umbral_duda then
      v_cara := 'desconocida'; v_cand_id := null;
    elsif v_dist2 is not null and v_dist2 - v_dist < p_margen then
      v_cara := 'ambigua'; v_detalle := 'candidatos_cercanos';
    elsif v_dist > p_umbral then
      v_cara := 'ambigua'; v_detalle := 'entre_umbrales';
    else
      v_cara := 'reconocida';
    end if;
  end if;

  -- 2. Credencial.
  if p_token is not null then
    select * into v_cred from public.credenciales where token_hash = public.hash_token(p_token);
    v_qr := case when not found then 'no_encontrada'
                 when v_cred.revocada_en is not null then 'revocada'
                 when now() < v_cred.valido_desde then 'aun_no_valida'
                 when v_cred.valido_hasta is not null and now() > v_cred.valido_hasta then 'vencida'
                 else 'valida' end;
  end if;

  -- 3. Decisión. El robot no crea permisos ni resuelve contradicciones: las pasa a recepción.
  --    Una cara desconocida no significa "no miembro": significa que no se pudo identificar.
  if v_qr = 'valida' and v_cara = 'reconocida' and v_cand_id <> v_cred.persona_id then
    v_resultado := 'pendiente_revision'; v_motivo := 'contradiccion_cara_credencial';
  elsif v_qr in ('no_encontrada', 'revocada', 'aun_no_valida', 'vencida') then
    v_resultado := 'rechazado'; v_motivo := 'credencial_' || v_qr;
  elsif v_qr = 'valida' then
    select * into v_persona from public.personas where id = v_cred.persona_id;
  elsif v_cara = 'reconocida' then
    select * into v_persona from public.personas where id = v_cand_id;
  elsif v_cara = 'ambigua' then
    v_resultado := 'pendiente_revision'; v_motivo := 'identidad_ambigua';
  elsif v_cara = 'captura_no_valida' then
    v_resultado := 'pendiente_revision'; v_motivo := 'captura_no_valida';
  else
    v_resultado := 'rechazado'; v_motivo := 'no_identificado';
  end if;

  if v_resultado = 'orientado' and v_persona.estado <> 'activa' then
    v_resultado := 'rechazado'; v_motivo := 'persona_suspendida';
  end if;

  -- 4. Acreditación vigente y visita: la del QR de visita; si no, la invitación u orden de trabajo
  --    activa de la persona; si no, una nueva para el miembro o el personal en su horario.
  if v_resultado = 'orientado' then
    if v_cred.tipo = 'qr_visita' then
      select * into v_visita from public.visitas where id = v_cred.visita_id;
      if v_visita.estado = 'cancelada' then
        v_resultado := 'rechazado'; v_motivo := 'visita_cancelada';
      else
        v_categoria := v_visita.categoria;
        update public.visitas set estado = 'en_curso' where id = v_visita.id;
      end if;
    else
      select * into v_visita from public.visitas
       where persona_id = v_persona.id and categoria in ('invitado', 'externo')
         and estado in ('programada', 'en_curso') and now() between inicio and fin
       order by inicio desc limit 1;
      if found then
        v_categoria := v_visita.categoria;
        update public.visitas set estado = 'en_curso' where id = v_visita.id;
      elsif v_persona.vinculo = 'ninguno' then
        v_resultado := 'rechazado'; v_motivo := 'sin_visita_activa';
      elsif v_persona.vinculo_hasta is not null
            and v_persona.vinculo_hasta < (now() at time zone 'America/Bogota')::date then
        v_resultado := 'rechazado'; v_motivo := 'acreditacion_vencida';
        v_categoria := v_persona.vinculo::text::public.categoria_visita;
      elsif not public.en_horario(v_persona.horario_inicio, v_persona.horario_fin) then
        v_resultado := 'rechazado'; v_motivo := 'fuera_de_horario';
        v_categoria := v_persona.vinculo::text::public.categoria_visita;
      else
        v_categoria := v_persona.vinculo::text::public.categoria_visita;
        insert into public.visitas (persona_id, categoria, inicio, fin, estado)
        values (v_persona.id, v_categoria, now(),
                (date_trunc('day', now() at time zone 'America/Bogota') + v_persona.horario_fin)
                  at time zone 'America/Bogota',
                'en_curso')
        returning * into v_visita;
      end if;
    end if;
  end if;

  v_evidencia := jsonb_build_object(
    'cara', v_cara, 'detalle', v_detalle, 'distancia', round(v_dist::numeric, 3),
    'distancia_segundo', round(v_dist2::numeric, 3), 'qr', v_qr,
    'modo', case when v_cara <> 'no_usada' then p_modo end, 'modelo', p_modelo);

  insert into public.eventos (visita_id, persona_candidata_id, credencial_id, foto_id, fuente,
                              modo_reconocimiento, evidencia, categoria, resultado, motivo)
  values (v_visita.id, coalesce(v_persona.id, v_cand_id), v_cred.id, p_foto, p_fuente,
          case when v_cara <> 'no_usada' then p_modo end, v_evidencia, v_categoria, v_resultado,
          v_motivo)
  returning id into v_evento;

  return jsonb_build_object(
    'evento_id', v_evento,
    'resultado', v_resultado,
    'motivo', v_motivo,
    'evidencia', v_evidencia,
    'categoria', v_categoria,
    'nombre', case when v_resultado = 'orientado' then v_persona.nombre_demo end,
    'visita_id', v_visita.id,
    'destino', v_visita.destino,
    'empresa', v_visita.empresa,
    'requiere_tour', coalesce(v_persona.requiere_tour, false) and v_resultado = 'orientado',
    'ayuda_disponible', case when v_resultado = 'orientado'
                             then to_jsonb(public.ayuda_disponible(v_categoria)) end,
    'horario', case when v_motivo = 'fuera_de_horario'
                    then to_char(v_persona.horario_inicio, 'HH24:MI') || '-'
                         || to_char(v_persona.horario_fin, 'HH24:MI') end
  );
end;
$$;

revoke execute on function public.registrar_llegada(extensions.vector, text, text, boolean, uuid, double precision, double precision, double precision, text, text) from public, anon, authenticated;
grant  execute on function public.registrar_llegada(extensions.vector, text, text, boolean, uuid, double precision, double precision, double precision, text, text) to service_role;
