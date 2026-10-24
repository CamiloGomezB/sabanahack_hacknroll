import AsyncStorage from '@react-native-async-storage/async-storage';

import type { ProfileKind } from '@/constants/profiles';
import { RESERVATION_RULES, SPACES, getSpace, type SpaceConfig } from '@/constants/spaces';
import type { SessionState } from '@/features/auth/SessionProvider';
import {
  cancelarReserva,
  disponibilidadEspacio,
  fetchEspacios,
  fetchMisReservas,
  fetchReglaReserva,
  reservarEspacio,
  type EspacioRow,
} from '@/services/supabase/reservas';
import type { Persona } from '@/types/database';
import { friendlyError } from '@/utils/format';
import { addDays, clubDateString, clubMinutesOfDay, clubToUtc, parseTimeToMinutes } from '@/utils/time';

/**
 * Dos repositorios con la misma interfaz:
 *  - real (cuenta de Supabase): catálogo `espacios`, reglas `reglas_reserva` y las funciones
 *    disponibilidad_espacio / reservar_espacio / cancelar_reserva, que validan plan, horario,
 *    anticipación y cruces en la base. Lo que se reserva aquí lo ve el robot al recibir a la
 *    persona (contexto_llegada) y recepción en el panel web.
 *  - demo: disponibilidad simulada y reservas guardadas solo en este teléfono.
 */

export interface Reservation {
  id: string;
  spaceKey: string;
  date: string;
  startMinutes: number;
  hours: number;
  createdAt: string;
  demo: boolean;
}

export interface Slot {
  startMinutes: number;
  available: boolean;
  reason?: 'ocupado' | 'pasado' | 'tuya';
}

export interface ReservationRules {
  maxAdvanceDays: number;
  maxHoursPerBooking: number;
}

export interface ReservationsCatalog {
  /** Espacios que el plan puede reservar. */
  spaces: SpaceConfig[];
  /** Espacios reservables solo con otro plan (se muestran bloqueados). */
  locked: SpaceConfig[];
  rules: ReservationRules | null;
}

export type ReserveResult = { ok: true; reservation: Reservation } | { ok: false; message: string };

export type ReservationsRepository =
  | {
      supported: true;
      demo: boolean;
      catalog(): Promise<ReservationsCatalog>;
      slots(spaceKey: string, date: string): Promise<Slot[]>;
      reserve(spaceKey: string, date: string, startMinutes: number, hours: number): Promise<ReserveResult>;
      list(): Promise<Reservation[]>;
      cancel(id: string): Promise<void>;
    }
  | { supported: false; reason: string };

type Active = Extract<SessionState, { status: 'real' | 'pass' | 'demo' }>;

const SLOT_MINUTES = 60;

function splitCatalog(spaces: readonly SpaceConfig[], profile: ProfileKind, rules: ReservationRules | null) {
  return {
    spaces: spaces.filter((s) => s.reservableBy.includes(profile)),
    locked: spaces.filter((s) => s.reservableBy.length > 0 && !s.reservableBy.includes(profile)),
    rules,
  };
}

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
    async catalog() {
      return splitCatalog(SPACES, profile, rules ?? null);
    },
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

// Íconos de los espacios que solo están en la base (los de la app vienen de constants/spaces).
const DB_SPACE_ICONS: Record<string, SpaceConfig['icon']> = {
  canchas: 'tennisball-outline',
  gimnasio: 'barbell-outline',
  piscina: 'water-outline',
  restaurante: 'restaurant-outline',
  sala_vip: 'diamond-outline',
};

function toSpaceConfig(row: EspacioRow): SpaceConfig {
  const local = getSpace(row.clave);
  return {
    key: row.clave,
    name: row.nombre,
    description: row.descripcion ?? local?.description ?? '',
    icon: local?.icon ?? DB_SPACE_ICONS[row.clave] ?? 'location-outline',
    capacity: row.capacidad ?? local?.capacity ?? 0,
    reservableBy: row.reservable_por.filter((v): v is 'regular' | 'vip' => v === 'regular' || v === 'vip'),
    invitableBy: local?.invitableBy ?? [],
  };
}

function realRepository(profile: ProfileKind, persona: Persona): ReservationsRepository {
  const toReservation = (r: { id: string; espacio: string; inicio: string; fin: string; creado_en: string }) => {
    const start = new Date(r.inicio);
    return {
      id: r.id,
      spaceKey: r.espacio,
      date: clubDateString(start),
      startMinutes: clubMinutesOfDay(start),
      hours: Math.round((new Date(r.fin).getTime() - start.getTime()) / 3_600_000),
      createdAt: r.creado_en,
      demo: false,
    } satisfies Reservation;
  };

  async function list(): Promise<Reservation[]> {
    return (await fetchMisReservas(persona.id)).map(toReservation);
  }

  return {
    supported: true,
    demo: false,
    async catalog() {
      const [rows, regla] = await Promise.all([fetchEspacios(), fetchReglaReserva(persona.vinculo)]);
      const rules = regla
        ? { maxAdvanceDays: regla.max_dias_anticipacion, maxHoursPerBooking: regla.max_horas_por_reserva }
        : null;
      return splitCatalog(rows.map(toSpaceConfig), profile, rules);
    },
    async slots(spaceKey, date) {
      const [rows, mine] = await Promise.all([disponibilidadEspacio(spaceKey, date), list()]);
      const now = Date.now();
      return rows.map((row) => {
        const start = new Date(row.inicio);
        const startMinutes = clubMinutesOfDay(start);
        if (row.disponible) return { startMinutes, available: true };
        const yours = mine.some(
          (r) => r.spaceKey === spaceKey && r.date === date && startMinutes >= r.startMinutes && startMinutes < r.startMinutes + r.hours * 60,
        );
        const reason: Slot['reason'] = yours ? 'tuya' : start.getTime() <= now ? 'pasado' : 'ocupado';
        return { startMinutes, available: false, reason };
      });
    },
    async reserve(spaceKey, date, startMinutes, hours) {
      try {
        const id = await reservarEspacio(spaceKey, clubToUtc(date, startMinutes), hours);
        return {
          ok: true,
          reservation: { id, spaceKey, date, startMinutes, hours, createdAt: new Date().toISOString(), demo: false },
        };
      } catch (e) {
        return { ok: false, message: friendlyError(e, 'No se pudo guardar la reserva.') };
      }
    },
    list,
    cancel: cancelarReserva,
  };
}

export function reservationsRepositoryFor(session: Active): ReservationsRepository {
  if (session.status === 'real') {
    return realRepository(session.profile, session.persona);
  }
  if (session.status === 'demo' && session.persona) {
    const p = session.persona;
    return demoRepository(
      session.profile,
      p.id,
      parseTimeToMinutes(p.horario_inicio ?? '06:00'),
      parseTimeToMinutes(p.horario_fin ?? '21:00'),
    );
  }
  return { supported: false, reason: 'Las reservas son para miembros con cuenta.' };
}

export const SLOT_LENGTH_MINUTES = SLOT_MINUTES;
