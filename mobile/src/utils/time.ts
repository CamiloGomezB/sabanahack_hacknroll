import { config } from '@/constants/config';

// Todo el negocio del club se evalúa en hora de Colombia (UTC-5, sin horario de verano),
// igual que public.en_horario() y registrar_llegada() en la base de datos.

const OFFSET_MS = config.clubUtcOffsetHours * 3600 * 1000;
const DAYS = ['dom', 'lun', 'mar', 'mié', 'jue', 'vie', 'sáb'];
const MONTHS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];

const pad = (n: number) => String(n).padStart(2, '0');

/** Fecha "de pared" en Colombia (los campos UTC del Date desplazado son la hora local). */
function clubWall(date: Date): Date {
  return new Date(date.getTime() + OFFSET_MS);
}

/** YYYY-MM-DD en hora de Colombia. */
export function clubDateString(date: Date = new Date()): string {
  const w = clubWall(date);
  return `${w.getUTCFullYear()}-${pad(w.getUTCMonth() + 1)}-${pad(w.getUTCDate())}`;
}

/** Minutos desde medianoche (hora de Colombia). */
export function clubMinutesOfDay(date: Date = new Date()): number {
  const w = clubWall(date);
  return w.getUTCHours() * 60 + w.getUTCMinutes();
}

export function addDays(dateStr: string, days: number): string {
  const [y, m, d] = dateStr.split('-').map(Number);
  const t = new Date(Date.UTC(y, m - 1, d + days));
  return `${t.getUTCFullYear()}-${pad(t.getUTCMonth() + 1)}-${pad(t.getUTCDate())}`;
}

/** Instante UTC que corresponde a una fecha y hora locales de Colombia. */
export function clubToUtc(dateStr: string, minutesOfDay: number): Date {
  const [y, m, d] = dateStr.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, d, 0, minutesOfDay) - OFFSET_MS);
}

/** "06:00:00" o "06:00" -> 360. */
export function parseTimeToMinutes(time: string): number {
  const [h, m] = time.split(':').map(Number);
  return h * 60 + (m || 0);
}

export function formatMinutes(minutes: number): string {
  return `${pad(Math.floor(minutes / 60))}:${pad(minutes % 60)}`;
}

export function formatClock(time: string | null): string {
  return time ? formatMinutes(parseTimeToMinutes(time)) : '—';
}

export function formatDuration(totalMinutes: number): string {
  const h = Math.floor(totalMinutes / 60);
  const m = totalMinutes % 60;
  if (h === 0) return `${m} min`;
  return m === 0 ? `${h} h` : `${h} h ${m} min`;
}

/** "mar 27 oct" */
export function formatDateLabel(dateStr: string): string {
  const [y, m, d] = dateStr.split('-').map(Number);
  const dow = new Date(Date.UTC(y, m - 1, d)).getUTCDay();
  return `${DAYS[dow]} ${d} ${MONTHS[m - 1]}`;
}

/** "mar 27 oct, 14:30" en hora de Colombia. */
export function formatClubDateTime(date: Date | string): string {
  const dt = typeof date === 'string' ? new Date(date) : date;
  return `${formatDateLabel(clubDateString(dt))}, ${formatMinutes(clubMinutesOfDay(dt))}`;
}

/** "mar 27 oct, 14:00 – 18:00" (o con ambas fechas si cruza de día). */
export function formatClubRange(start: Date | string, end: Date | string): string {
  const s = typeof start === 'string' ? new Date(start) : start;
  const e = typeof end === 'string' ? new Date(end) : end;
  if (clubDateString(s) === clubDateString(e)) {
    return `${formatDateLabel(clubDateString(s))}, ${formatMinutes(clubMinutesOfDay(s))} – ${formatMinutes(clubMinutesOfDay(e))}`;
  }
  return `${formatClubDateTime(s)} → ${formatClubDateTime(e)}`;
}

/** YYYY-MM-DD de hoy en Colombia + n días. */
export function upcomingDates(count: number, startOffset = 0): string[] {
  const today = clubDateString();
  return Array.from({ length: count }, (_, i) => addDays(today, startOffset + i));
}
