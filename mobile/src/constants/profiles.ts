import type { CategoriaVisita, VinculoClub } from '@/types/database';

/** Los cinco perfiles de la aplicación. Coinciden con public.categoria_visita. */
export type ProfileKind = CategoriaVisita;

export const PROFILE_LABELS: Record<ProfileKind, string> = {
  regular: 'Miembro Regular',
  vip: 'Miembro VIP',
  personal: 'Personal del club',
  invitado: 'Invitado',
  externo: 'Trabajador externo',
};

/** Prefijo del identificador visible. La base no guarda un código legible: se deriva del UUID. */
export const PROFILE_CODE_PREFIX: Record<ProfileKind, string> = {
  regular: 'MR',
  vip: 'VIP',
  personal: 'PC',
  invitado: 'IN',
  externo: 'EX',
};

export function isMemberProfile(p: ProfileKind): p is 'regular' | 'vip' {
  return p === 'regular' || p === 'vip';
}

export function isPassProfile(p: ProfileKind): p is 'invitado' | 'externo' {
  return p === 'invitado' || p === 'externo';
}

/** Vínculos de la base que tienen cuenta y panel propio en la app. */
export function vinculoToProfile(v: VinculoClub): ProfileKind | null {
  return v === 'ninguno' ? null : v;
}
