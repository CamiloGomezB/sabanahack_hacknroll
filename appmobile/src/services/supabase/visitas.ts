import type { CategoriaVisita, CrearInvitacionResult, EstadoVisita } from '@/types/database';

import { requireSupabase } from './client';

export interface CrearInvitacionParams {
  nombre: string;
  email: string;
  destino: string;
  inicio: Date;
  fin: Date;
  categoria: Extract<CategoriaVisita, 'invitado' | 'externo'>;
  empresa?: string | null;
  motivo?: string | null;
}

/** public.crear_invitacion: crea persona, visita y credencial qr_visita; devuelve el token una vez. */
export async function crearInvitacion(p: CrearInvitacionParams): Promise<CrearInvitacionResult> {
  const { data, error } = await requireSupabase().rpc('crear_invitacion', {
    p_nombre: p.nombre.trim(),
    p_email: p.email.trim().toLowerCase(),
    p_destino: p.destino,
    p_inicio: p.inicio.toISOString(),
    p_fin: p.fin.toISOString(),
    p_categoria: p.categoria,
    p_empresa: p.empresa?.trim() || null,
    p_motivo: p.motivo?.trim() || null,
  });
  if (error) throw error;
  const result = data as Partial<CrearInvitacionResult> | null;
  if (!result?.visita_id || !result.token) throw new Error('Respuesta inesperada al crear la invitación.');
  return { visita_id: result.visita_id, token: result.token };
}

export interface EnviarInvitacionParams {
  visitaId: string;
  /** Texto plano: solo existe en este momento, justo después de crearInvitacion(). */
  token: string;
  email: string;
  nombre: string;
  anfitrion: string;
  destino: string;
  destinoNombre: string;
  categoria: Extract<CategoriaVisita, 'invitado' | 'externo'>;
  empresa: string | null;
  motivo: string | null;
  /** ISO 8601 */
  desde: string;
  hasta: string;
}

/** Edge Function enviar-invitacion: le manda al invitado su pase (QR) por correo (Resend). No
 *  tumba la invitación si falla: ya quedó creada, el anfitrión siempre puede compartirla a mano. */
export async function enviarInvitacionPorCorreo(
  p: EnviarInvitacionParams,
): Promise<{ ok: boolean; error?: string }> {
  try {
    const { data, error } = await requireSupabase().functions.invoke('enviar-invitacion', { body: p });
    if (error) return { ok: false, error: error.message };
    const r = data as { ok?: boolean; error?: string } | null;
    return { ok: Boolean(r?.ok), error: r?.ok ? undefined : r?.error ?? 'respuesta inesperada' };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : 'error desconocido' };
  }
}

export async function revocarInvitacion(visitaId: string, motivo?: string): Promise<void> {
  const { error } = await requireSupabase().rpc('revocar_invitacion', {
    p_visita: visitaId,
    p_motivo: motivo ?? null,
  });
  if (error) throw error;
}

export interface VisitaConPersona {
  id: string;
  categoria: CategoriaVisita;
  motivo: string | null;
  empresa: string | null;
  destino: string | null;
  inicio: string;
  fin: string;
  estado: EstadoVisita;
  persona: { nombre_demo: string; email: string | null } | null;
}

/** Visitas de las que soy responsable (RLS "ve sus visitas e invitaciones"). */
export async function fetchVisitasComoResponsable(personaId: string): Promise<VisitaConPersona[]> {
  const { data, error } = await requireSupabase()
    .from('visitas')
    .select(
      'id,categoria,motivo,empresa,destino,inicio,fin,estado,persona:personas!persona_id(nombre_demo,email)',
    )
    .eq('responsable_id', personaId)
    .in('categoria', ['invitado', 'externo'])
    .order('inicio', { ascending: false })
    .limit(50);
  if (error) throw error;
  return (data ?? []) as unknown as VisitaConPersona[];
}
