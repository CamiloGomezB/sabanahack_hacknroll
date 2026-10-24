import type { EstadoVisita } from '@/types/database';

export const VISIT_STATE: Record<
  EstadoVisita,
  { label: string; tone: 'success' | 'warning' | 'danger' | 'neutral' }
> = {
  programada: { label: 'Programada', tone: 'warning' },
  en_curso: { label: 'En curso', tone: 'success' },
  finalizada: { label: 'Finalizada', tone: 'neutral' },
  cancelada: { label: 'Cancelada', tone: 'danger' },
};
