import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState } from 'react';

import { DEMO_STAFF_TASKS, type StaffTask } from '@/features/demo/demoData';
import { clubDateString } from '@/utils/time';

export interface TaskWithState extends StaffTask {
  done: boolean;
}

/**
 * SIMULADO en todos los modos: el esquema no tiene tareas ni asignaciones. El estado
 * pendiente / completado se guarda solo en este teléfono y se reinicia cada día.
 */
export function useStaffTasks(personaId: string) {
  const key = `nclub_tasks_${personaId}_${clubDateString()}`;
  const [done, setDone] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    AsyncStorage.getItem(key)
      .then((raw) => {
        if (alive) setDone(raw ? (JSON.parse(raw) as Record<string, boolean>) : {});
      })
      .catch(() => undefined)
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [key]);

  const toggle = useCallback(
    (id: string) => {
      setDone((prev) => {
        const next = { ...prev, [id]: !prev[id] };
        AsyncStorage.setItem(key, JSON.stringify(next)).catch(() => undefined);
        return next;
      });
    },
    [key],
  );

  const tasks: TaskWithState[] = DEMO_STAFF_TASKS.map((t) => ({ ...t, done: Boolean(done[t.id]) }));
  return { tasks, toggle, loading, simulated: true as const };
}
