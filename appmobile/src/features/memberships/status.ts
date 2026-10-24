import type { Persona } from '@/types/database';
import { clubDateString, formatDateLabel } from '@/utils/time';

export interface MembershipStatus {
  active: boolean;
  label: string;
  detail: string | null;
}

/**
 * Activa = personas.estado 'activa' y vinculo_hasta sin vencer (hoy en Colombia),
 * el mismo criterio que usa registrar_llegada() para la acreditación permanente.
 */
export function membershipStatus(p: Persona): MembershipStatus {
  if (p.estado !== 'activa') {
    return { active: false, label: 'Inactiva', detail: 'Membresía suspendida por el club.' };
  }
  if (p.vinculo_hasta && p.vinculo_hasta < clubDateString()) {
    return { active: false, label: 'Inactiva', detail: `Venció el ${formatDateLabel(p.vinculo_hasta)}.` };
  }
  return {
    active: true,
    label: 'Activa',
    detail: p.vinculo_hasta ? `Vigente hasta el ${formatDateLabel(p.vinculo_hasta)}.` : null,
  };
}
