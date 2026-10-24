import { requireSupabase, supabase } from './client';

export type EstadoAviso = 'emitido' | 'recibido' | 'aceptado' | 'sin_respuesta';

/** Aviso de llegada de un invitado o externo (tabla public.avisos, migración 20261024000007). */
export interface Aviso {
  id: string;
  visita_id: string | null;
  tipo: 'llegada_invitado' | 'llegada_externo';
  mensaje: string;
  punto_encuentro: string | null;
  estado: EstadoAviso;
  creado_en: string;
}

const AVISO_COLUMNS = 'id,visita_id,tipo,mensaje,punto_encuentro,estado,creado_en';

/** Avisos propios de las últimas 24 h; RLS solo deja ver los del destinatario. */
export async function fetchMyAvisos(personaId: string): Promise<Aviso[]> {
  const desde = new Date(Date.now() - 24 * 3600 * 1000).toISOString();
  const { data, error } = await requireSupabase()
    .from('avisos')
    .select(AVISO_COLUMNS)
    .eq('destinatario_id', personaId)
    .gte('creado_en', desde)
    .order('creado_en', { ascending: false });
  if (error) throw error;
  return (data ?? []) as Aviso[];
}

export async function responderAviso(id: string, estado: 'recibido' | 'aceptado'): Promise<void> {
  const { error } = await requireSupabase().rpc('responder_aviso', { p_aviso: id, p_estado: estado });
  if (error) throw error;
}

// client.channel(topic) reutiliza el canal si ya existe uno con ese mismo topic (p. ej. uno que
// esta por cerrarse: removeChannel espera a que el servidor confirme el unsubscribe antes de
// quitarlo de la lista). Si ArrivalNotices se vuelve a montar con el mismo personaId antes de que
// eso termine (al volver a Inicio después de crear una invitación, por ejemplo), el canal que
// devuelve ya pasó por subscribe() y el .on() de abajo revienta con "cannot add ... after
// subscribe()". Un sufijo único por llamada evita que un canal nuevo se tope con uno viejo.
let contadorAvisos = 0;

/** Llama a `onChange` cuando llega o cambia un aviso propio (Supabase Realtime). */
export function subscribeAvisos(personaId: string, onChange: () => void): () => void {
  if (!supabase) return () => {};
  const client = supabase;
  const channel = client
    .channel(`avisos-${personaId}-${++contadorAvisos}`)
    .on('postgres_changes', { event: '*', schema: 'public', table: 'avisos', filter: `destinatario_id=eq.${personaId}` }, onChange)
    .subscribe();
  return () => {
    void client.removeChannel(channel);
  };
}
