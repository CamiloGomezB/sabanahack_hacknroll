import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useState } from 'react';

import { spaceName } from '@/constants/spaces';
import type { SessionState } from '@/features/auth/SessionProvider';
import { DEMO_STAFF_TASKS, type StaffTask } from '@/features/demo/demoData';
import { useAsync } from '@/hooks/useAsync';
import { fetchMisTareas, marcarTarea, type TareaRow } from '@/services/supabase/tareas';
import { friendlyError } from '@/utils/format';
import { clubDateString, formatClock } from '@/utils/time';

export interface TaskWithState extends StaffTask {
  done: boolean;
}

type StaffSession = Extract<SessionState, { status: 'real' | 'demo' }>;

const toTask = (t: TareaRow): TaskWithState => ({
  id: t.id,
  title: t.titulo,
  area: t.area ? spaceName(t.area) : 'Sin área',
  time: t.hora ? formatClock(t.hora) : 'Sin hora',
  done: t.estado === 'completada',
});

/**
 * Con cuenta real: las tareas de hoy de `tareas_personal` (las asigna el club) y marcar_tarea para
 * completarlas; el robot las lee al recibir a la persona (contexto_llegada).
 * En demostración: tareas de ejemplo, con el estado guardado solo en este teléfono.
 */
export function useStaffTasks(session: StaffSession) {
  const personaId = session.persona?.id ?? 'sin-persona';
  const real = session.status === 'real';
  const today = clubDateString();
  const key = `nclub_tasks_${personaId}_${today}`;

  const load = useCallback(async (): Promise<TaskWithState[]> => {
    if (real) return (await fetchMisTareas(personaId, today)).map(toTask);
    const raw = await AsyncStorage.getItem(key).catch(() => null);
    const done = raw ? (JSON.parse(raw) as Record<string, boolean>) : {};
    return DEMO_STAFF_TASKS.map((t) => ({ ...t, done: Boolean(done[t.id]) }));
  }, [real, personaId, today, key]);
  const { state, reload } = useAsync(load, 'No se pudieron cargar tus tareas.');

  // Cambios marcados en esta pantalla sobre la lista cargada (se descartan al recargar).
  const [edits, setEdits] = useState<{ base?: TaskWithState[]; done: Record<string, boolean> }>({ done: {} });
  const [toggleError, setToggleError] = useState<string | null>(null);
  const loaded = state.data ?? [];
  const pending = edits.base === state.data ? edits.done : {};
  const tasks = loaded.map((t) => (t.id in pending ? { ...t, done: pending[t.id] } : t));

  const toggle = (id: string) => {
    const current = tasks.find((t) => t.id === id);
    if (!current) return;
    const done = { ...pending, [id]: !current.done };
    setEdits({ base: state.data, done });
    setToggleError(null);
    if (real) {
      marcarTarea(id, !current.done).catch((e: unknown) => {
        setToggleError(friendlyError(e, 'No se pudo actualizar la tarea.'));
        reload(); // vuelve al estado que tiene la base
      });
    } else {
      const all = Object.fromEntries(tasks.map((t) => [t.id, t.id in done ? done[t.id] : t.done]));
      AsyncStorage.setItem(key, JSON.stringify(all)).catch(() => undefined);
    }
  };

  return {
    tasks,
    toggle,
    loading: state.status === 'loading',
    error: state.status === 'error' ? state.error : toggleError,
    simulated: !real,
    reload,
  };
}
