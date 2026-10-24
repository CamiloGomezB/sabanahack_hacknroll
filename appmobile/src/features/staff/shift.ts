import type { Persona } from '@/types/database';
import { clubMinutesOfDay, formatClock, formatDuration, parseTimeToMinutes } from '@/utils/time';

export interface ShiftInfo {
  start: string;
  end: string;
  duration: string;
  /** Estado respecto a la hora actual en Colombia (como public.en_horario). */
  phase: 'antes' | 'en_turno' | 'terminado';
}

/** El turno sale de personas.horario_inicio / horario_fin (máximo 8 h, entre 04:00 y 22:00). */
export function shiftFromPersona(p: Persona, now: Date = new Date()): ShiftInfo | null {
  if (!p.horario_inicio || !p.horario_fin) return null;
  const start = parseTimeToMinutes(p.horario_inicio);
  const end = parseTimeToMinutes(p.horario_fin);
  const current = clubMinutesOfDay(now);
  return {
    start: formatClock(p.horario_inicio),
    end: formatClock(p.horario_fin),
    duration: formatDuration(end - start),
    phase: current < start ? 'antes' : current < end ? 'en_turno' : 'terminado',
  };
}

export const SHIFT_PHASE_LABEL: Record<ShiftInfo['phase'], string> = {
  antes: 'Tu turno aún no empieza',
  en_turno: 'En turno',
  terminado: 'Turno terminado',
};
