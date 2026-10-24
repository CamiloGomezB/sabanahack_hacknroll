import type { Credencial } from '@/types/database';

import { requireSupabase } from './client';

/** Última credencial QR personal no revocada (RLS: solo las propias). */
export async function fetchActivePersonalCredential(personaId: string): Promise<Credencial | null> {
  const { data, error } = await requireSupabase()
    .from('credenciales')
    .select('id,persona_id,visita_id,tipo,token_hash,valido_desde,valido_hasta,revocada_en')
    .eq('persona_id', personaId)
    .eq('tipo', 'qr_personal')
    .is('revocada_en', null)
    .order('creado_en', { ascending: false })
    .limit(1)
    .maybeSingle();
  if (error) throw error;
  return (data as Credencial | null) ?? null;
}

/**
 * public.generar_mi_qr(): revoca el QR personal anterior y devuelve el token nuevo.
 * La base solo guarda su hash, así que el token solo se puede leer esta vez.
 */
export async function generateMyQrToken(): Promise<string> {
  const { data, error } = await requireSupabase().rpc('generar_mi_qr');
  if (error) throw error;
  if (typeof data !== 'string' || data.length < 32) {
    throw new Error('Respuesta inesperada al generar el QR.');
  }
  return data;
}
