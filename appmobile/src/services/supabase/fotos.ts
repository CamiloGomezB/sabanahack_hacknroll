import { FOTO_COLUMNS, type Fotografia } from '@/types/database';
import { base64ToBytes } from '@/utils/base64';

import { requireSupabase } from './client';

const BUCKET = 'fotos';
/** Fotos de registro que puede tener una persona: con dos o tres buenas basta. */
export const MAX_FOTOS = 3;

/** Sus fotos de registro, la más nueva primero (RLS: solo las suyas). */
export async function fetchMisFotos(personaId: string): Promise<Fotografia[]> {
  const { data, error } = await requireSupabase()
    .from('fotografias')
    .select(FOTO_COLUMNS)
    .eq('persona_id', personaId)
    .eq('uso', 'registro')
    .order('tomada_en', { ascending: false });
  if (error) throw error;
  return (data ?? []) as Fotografia[];
}

/**
 * Sube la foto al bucket privado `fotos/<auth.uid()>/` y registra la fila de `fotografias`
 * (uso registro, autorizada). La huella NO la calcula la app: el backend del robot la calcula y
 * la deja en `huella_estado` ('lista' o 'sin_cara').
 */
export async function subirFotoRegistro(userId: string, personaId: string, base64: string): Promise<Fotografia> {
  const db = requireSupabase();
  const ahora = new Date().toISOString();
  const ruta = `${userId}/${Date.now()}.jpg`;
  const subida = await db.storage
    .from(BUCKET)
    .upload(ruta, base64ToBytes(base64), { contentType: 'image/jpeg', upsert: false });
  if (subida.error) throw subida.error;
  const { data, error } = await db
    .from('fotografias')
    .insert({
      persona_id: personaId,
      cargada_por: personaId,
      ruta,
      uso: 'registro',
      autorizada: true,
      autorizacion_fecha: ahora,
      tomada_en: ahora,
    })
    .select(FOTO_COLUMNS)
    .single();
  if (error) {
    await db.storage.from(BUCKET).remove([ruta]);
    throw error;
  }
  return data as Fotografia;
}

/** Borra la foto y su huella (la fila y el archivo). */
export async function borrarFoto(foto: Fotografia): Promise<void> {
  const db = requireSupabase();
  const { error } = await db.from('fotografias').delete().eq('id', foto.id);
  if (error) throw error;
  await db.storage.from(BUCKET).remove([foto.ruta]);
}

/** Enlace temporal (5 min) para ver la foto en la app. */
export async function urlDeFoto(ruta: string): Promise<string | null> {
  const { data } = await requireSupabase().storage.from(BUCKET).createSignedUrl(ruta, 300);
  return data?.signedUrl ?? null;
}
