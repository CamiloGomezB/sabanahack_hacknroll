import type { Ionicons } from '@expo/vector-icons';
import type { ComponentProps } from 'react';

import type { ProfileKind } from '@/constants/profiles';

type IconName = ComponentProps<typeof Ionicons>['name'];

/**
 * SUPUESTO / DEMOSTRACIÓN: la base de datos no define los espacios de N Club. Esta lista es una
 * configuración editable con nombres genéricos; hay que reemplazarla por los espacios reales (o por
 * una tabla `espacios`, ver supabase/proposed). La clave (`key`) es lo que se guarda en
 * `visitas.destino` ("clave de la zona").
 */
export const SPACES_ARE_PLACEHOLDERS = true;

export interface SpaceConfig {
  key: string;
  name: string;
  description: string;
  icon: IconName;
  capacity: number;
  /** Perfiles que pueden reservarlo. Vacío: zona de servicio, no reservable. */
  reservableBy: ProfileKind[];
  /** Perfiles que pueden indicarlo como destino de una invitación. */
  invitableBy: ProfileKind[];
}

export const SPACES: readonly SpaceConfig[] = [
  {
    key: 'salon-social',
    name: 'Salón social',
    description: 'Espacio común para reuniones y encuentros.',
    icon: 'cafe-outline',
    capacity: 12,
    reservableBy: ['regular', 'vip'],
    invitableBy: ['regular', 'vip', 'personal'],
  },
  {
    key: 'terraza',
    name: 'Terraza',
    description: 'Área al aire libre con servicio de mesa.',
    icon: 'sunny-outline',
    capacity: 20,
    reservableBy: ['regular', 'vip'],
    invitableBy: ['regular', 'vip', 'personal'],
  },
  {
    key: 'sala-lectura',
    name: 'Sala de lectura',
    description: 'Zona silenciosa para trabajo individual.',
    icon: 'book-outline',
    capacity: 8,
    reservableBy: ['regular', 'vip'],
    invitableBy: ['regular', 'vip', 'personal'],
  },
  {
    key: 'salon-privado',
    name: 'Salón privado VIP',
    description: 'Salón de uso exclusivo para miembros VIP.',
    icon: 'diamond-outline',
    capacity: 10,
    reservableBy: ['vip'],
    invitableBy: ['vip', 'personal'],
  },
  {
    key: 'comedor-reservado',
    name: 'Comedor reservado',
    description: 'Comedor privado con atención personalizada.',
    icon: 'restaurant-outline',
    capacity: 8,
    reservableBy: ['vip'],
    invitableBy: ['vip', 'personal'],
  },
  {
    key: 'sala-juntas',
    name: 'Sala de juntas VIP',
    description: 'Sala equipada para reuniones de trabajo.',
    icon: 'people-outline',
    capacity: 14,
    reservableBy: ['vip'],
    invitableBy: ['vip', 'personal'],
  },
  {
    key: 'zona-servicio',
    name: 'Zona de servicio',
    description: 'Áreas operativas del club (acceso acompañado).',
    icon: 'construct-outline',
    capacity: 0,
    reservableBy: [],
    invitableBy: ['personal'],
  },
];

export function getSpace(key: string | null | undefined): SpaceConfig | undefined {
  return SPACES.find((s) => s.key === key);
}

export function spaceName(key: string | null | undefined): string {
  return getSpace(key)?.name ?? (key ? key : 'Sin destino');
}

export function reservableSpacesFor(profile: ProfileKind): SpaceConfig[] {
  return SPACES.filter((s) => s.reservableBy.includes(profile));
}

export function invitableSpacesFor(profile: ProfileKind): SpaceConfig[] {
  return SPACES.filter((s) => s.invitableBy.includes(profile));
}

/**
 * SUPUESTO: reglas de reserva por perfil. El miembro regular accede a menos espacios y con
 * menor antelación que el VIP. Ajustar según las políticas reales del club.
 */
export const RESERVATION_RULES: Partial<
  Record<ProfileKind, { maxAdvanceDays: number; maxHoursPerBooking: number }>
> = {
  regular: { maxAdvanceDays: 7, maxHoursPerBooking: 2 },
  vip: { maxAdvanceDays: 14, maxHoursPerBooking: 4 },
};
