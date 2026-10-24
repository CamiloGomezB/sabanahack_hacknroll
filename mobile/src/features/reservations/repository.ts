import AsyncStorage from '@react-native-async-storage/async-storage';

import type { ProfileKind } from '@/constants/profiles';
import { RESERVATION_RULES, getSpace } from '@/constants/spaces';
import type { SessionState } from '@/features/auth/SessionProvider';
import { addDays, clubDateString, clubMinutesOfDay, parseTimeToMinutes } from '@/utils/time';

/**
 * El esquema actual NO tiene tablas ni funciones de espacios o reservas. Por eso:
 *  - en modo demostración se usa un repositorio local con disponibilidad simulada;
 *  - con una cuenta real no se puede verificar disponibilidad ni guardar: el repositorio lo
 *    declara y la interfaz no permite confirmar. Ver supabase/proposed/ para el modelo necesario.
 */

export interface Reservation {
  id: string;
  spaceKey: string;
  date: string;
  startMinutes: number;
  hours: number;
  createdAt: string;
  demo: true;
}

export interface Slot {
  startMinutes: number;
  available: boolean;
  reason?: 'ocupado' | 'pasado' | 'tuya';
}

export type ReserveResult = { ok: true; reservation: Reservation } | { ok: false; message: string };

export type ReservationsRepository =
  | {
      supported: true;
      demo: true;
      slots(spaceKey: string, date: string): Promise<Slot[]>;
      reserve(spaceKey: string, date: string, startMinutes: number, hours: number): Promise<ReserveResult>;
      list(): Promise<Reservation[]>;
      cancel(id: string): Promise<void>;
    }
  | { supported: false; reason: string };

type Active = Extract<SessionState, { status: 'real' | 'pass' | 'demo' }>;

const SLOT_MINUTES = 60;

function hash(text: string): number {
  let h = 2166136261;
  for (let i = 0; i < text.length; i++) h = Math.imul(h ^ text.charCodeAt(i), 16777619);
  // Mezcla final para que las franjas ocupadas no salgan en un patrón periódico.
  h ^= h >>> 16;
  h = Math.imul(h, 0x85ebca6b);
  h ^= h >>> 13;
  return h >>> 0;
}

/** Ocupación simulada determinista: ~1 de cada 4 franjas aparece ocupada. */
function demoOccupied(spaceKey: string, date: string, minutes: number): boolean {
  return hash(`${spaceKey}|${date}|${minutes}`) % 4 === 0;
}

function demoRepository(profile: ProfileKind, personaId: string, open: number, close: number): ReservationsRepository {
  const key = `nclub_demo_reservations_${personaId}`;
  const rules = RESERVATION_RULES[profile];

  async function read(): Promise<Reservation[]> {
    try {
      const raw = await AsyncStorage.getItem(key);
      return raw ? (JSON.parse(raw) as Reservation[]) : [];
    } catch {
      return [];
    }
  }

  async function slots(spaceKey: string, date: string): Promise<Slot[]> {
    const mine = (await read()).filter((r) => r.spaceKey === spaceKey && r.date === date);
    const today = clubDateString();
    const nowMin = clubMinutesOfDay();
    const out: Slot[] = [];
    for (let m = open; m + SLOT_MINUTES <= close; m += SLOT_MINUTES) {
      if (mine.some((r) => m >= r.startMinutes && m < r.startMinutes + r.hours * 60)) {
        out.push({ startMinutes: m, available: false, reason: 'tuya' });
      } else if (date === today && m <= nowMin) {
        out.push({ startMinutes: m, available: false, reason: 'pasado' });
      } else if (demoOccupied(spaceKey, date, m)) {
        out.push({ startMinutes: m, available: false, reason: 'ocupado' });
      } else {
        out.push({ startMinutes: m, available: true });
      }
    }
    return out;
  }

  return {
    supported: true,
    demo: true,
    slots,
    async reserve(spaceKey, date, startMinutes, hours) {
      const space = getSpace(spaceKey);
      if (!rules || !space || !space.reservableBy.includes(profile)) {
        return { ok: false, message: 'Tu perfil no puede reservar este espacio.' };
      }
      if (hours < 1 || hours > rules.maxHoursPerBooking) {
        return { ok: false, message: `Puedes reservar hasta ${rules.maxHoursPerBooking} h seguidas.` };
      }
      const today = clubDateString();
      if (date < today || date > addDays(today, rules.maxAdvanceDays)) {
        return { ok: false, message: `Solo puedes reservar hasta ${rules.maxAdvanceDays} días por adelantado.` };
      }
      // Se vuelve a comprobar la disponibilidad justo antes de guardar.
      const current = await slots(spaceKey, date);
      for (let i = 0; i < hours; i++) {
        const slot = current.find((s) => s.startMinutes === startMinutes + i * SLOT_MINUTES);
        if (!slot || !slot.available) {
          return { ok: false, message: 'La franja elegida ya no está disponible.' };
        }
      }
      const reservation: Reservation = {
        id: `demo-${Date.now().toString(36)}`,
        spaceKey,
        date,
        startMinutes,
        hours,
        createdAt: new Date().toISOString(),
        demo: true,
      };
      await AsyncStorage.setItem(key, JSON.stringify([reservation, ...(await read())]));
      return { ok: true, reservation };
    },
    async list() {
      const today = clubDateString();
      return (await read())
        .filter((r) => r.date >= today)
        .sort((a, b) => a.date.localeCompare(b.date) || a.startMinutes - b.startMinutes);
    },
    async cancel(id) {
      await AsyncStorage.setItem(key, JSON.stringify((await read()).filter((r) => r.id !== id)));
    },
  };
}

export function reservationsRepositoryFor(session: Active): ReservationsRepository {
  if (session.status === 'demo' && session.persona) {
    const p = session.persona;
    return demoRepository(
      session.profile,
      p.id,
      parseTimeToMinutes(p.horario_inicio ?? '06:00'),
      parseTimeToMinutes(p.horario_fin ?? '21:00'),
    );
  }
  return {
    supported: false,
    reason:
      'La base de datos todavía no tiene espacios ni reservas, así que no se puede verificar la disponibilidad ni guardar una reserva. Puedes consultar los espacios de tu plan.',
  };
}

export const SLOT_LENGTH_MINUTES = SLOT_MINUTES;
