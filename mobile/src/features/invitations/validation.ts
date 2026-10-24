import type { PassCategory } from '@/features/temporary-access/pass';
import { clubToUtc } from '@/utils/time';
import { validateEmail, validateName, validateRequired, type FieldErrors } from '@/utils/validation';

/**
 * Ventana horaria permitida (hora de Colombia). SUPUESTO: se reutilizan los límites del esquema
 * (horario_valido): miembros 06:00–21:00 para invitados; personal 04:00–22:00 para externos.
 */
export const VISIT_HOURS: Record<PassCategory, { start: number; end: number }> = {
  invitado: { start: 6 * 60, end: 21 * 60 },
  externo: { start: 4 * 60, end: 22 * 60 },
};

export const MAX_ADVANCE_DAYS = 30;

export interface InvitationFormValues {
  nombre: string;
  email: string;
  destino: string;
  empresa: string;
  motivo: string;
  date: string | null;
  startMinutes: number | null;
  endMinutes: number | null;
}

export type InvitationField = keyof InvitationFormValues | 'window';

export function validateInvitation(
  categoria: PassCategory,
  v: InvitationFormValues,
  now: Date = new Date(),
): FieldErrors<InvitationField> {
  const errors: FieldErrors<InvitationField> = {
    nombre: validateName(v.nombre),
    email: validateEmail(v.email),
    destino: v.destino ? undefined : 'Elige el destino autorizado.',
  };
  if (categoria === 'externo') {
    errors.empresa = validateRequired(v.empresa, 'La empresa es obligatoria para un trabajador externo.');
    errors.motivo = validateRequired(v.motivo, 'Describe el servicio que va a realizar.');
  }
  if (!v.date) errors.date = 'Elige la fecha de la visita.';
  if (v.startMinutes === null || v.endMinutes === null) {
    errors.window = 'Elige la hora de inicio y de fin.';
  } else if (v.date) {
    const { start, end } = VISIT_HOURS[categoria];
    if (v.endMinutes <= v.startMinutes) errors.window = 'La hora de fin debe ser posterior a la de inicio.';
    else if (v.startMinutes < start || v.endMinutes > end) errors.window = 'La visita está fuera del horario permitido.';
    else if (clubToUtc(v.date, v.endMinutes).getTime() <= now.getTime()) errors.window = 'Esa franja ya pasó.';
  }
  return errors;
}
