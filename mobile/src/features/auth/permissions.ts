import type { ProfileKind } from '@/constants/profiles';
import { RESERVATION_RULES } from '@/constants/spaces';
import { membershipStatus } from '@/features/memberships/status';
import type { RolApp } from '@/types/database';

import type { SessionState } from './SessionProvider';

type Active = Extract<SessionState, { status: 'real' | 'pass' | 'demo' }>;

function rol(s: Active): RolApp {
  return s.status === 'real' ? s.persona.rol : 'usuario';
}

function isActivePersona(s: Active): boolean {
  if (s.status === 'pass' || !s.persona) return false;
  return membershipStatus(s.persona).active;
}

// Mismas reglas que public.crear_invitacion: regulares y VIP invitan; personal u operadores
// registran externos. El servidor vuelve a validarlo: esto solo decide qué se muestra.
export function canInviteGuests(s: Active): boolean {
  return isActivePersona(s) && (s.profile === 'regular' || s.profile === 'vip' || rol(s) !== 'usuario');
}

export function canRegisterExternal(s: Active): boolean {
  return isActivePersona(s) && (s.profile === 'personal' || rol(s) !== 'usuario');
}

export function canReserve(s: Active): boolean {
  return isActivePersona(s) && Boolean(RESERVATION_RULES[s.profile as ProfileKind]);
}
