import { requireSupabase } from './client';

export interface TareaRow {
  id: string;
  titulo: string;
  area: string | null;
  hora: string | null;
  estado: 'pendiente' | 'completada';
}

/** Tareas asignadas a la persona para una fecha (RLS "ve sus tareas"). */
export async function fetchMisTareas(personaId: string, fecha: string): Promise<TareaRow[]> {
  const { data, error } = await requireSupabase()
    .from('tareas_personal')
    .select('id,titulo,area,hora,estado')
    .eq('persona_id', personaId)
    .eq('fecha', fecha)
    .order('hora', { ascending: true, nullsFirst: false });
  if (error) throw error;
  return (data ?? []) as TareaRow[];
}

/** public.marcar_tarea: solo la persona asignada puede marcarla. */
export async function marcarTarea(id: string, completada: boolean): Promise<void> {
  const { error } = await requireSupabase().rpc('marcar_tarea', { p_tarea: id, p_completada: completada });
  if (error) throw error;
}
