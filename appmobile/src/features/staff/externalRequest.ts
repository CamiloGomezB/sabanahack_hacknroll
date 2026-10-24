import { spaceName } from '@/constants/spaces';
import { formatDateLabel } from '@/utils/time';
import { validateRequired, type FieldErrors } from '@/utils/validation';

/**
 * Consulta de servicio externo. No existe tabla ni proceso de contratación en el backend:
 * la solicitud se prepara y se puede compartir con administración, pero NO se registra ni
 * se confirma ninguna contratación. Lo único real es el acceso del trabajador (crear_invitacion).
 */
export const SERVICE_TYPES = [
  'Mantenimiento',
  'Limpieza especializada',
  'Montaje de eventos',
  'Tecnología / audiovisuales',
  'Jardinería',
  'Otro',
] as const;

export interface ExternalRequestValues {
  serviceType: string;
  description: string;
  area: string;
  date: string | null;
  workers: string;
  provider: string;
}

export type ExternalRequestField = keyof ExternalRequestValues;

export function validateExternalRequest(v: ExternalRequestValues): FieldErrors<ExternalRequestField> {
  const workers = Number(v.workers);
  return {
    serviceType: v.serviceType ? undefined : 'Elige el tipo de servicio.',
    description:
      validateRequired(v.description, 'Describe lo que se necesita.') ??
      (v.description.trim().length < 10 ? 'Agrega un poco más de detalle.' : undefined),
    area: v.area ? undefined : 'Elige el área del servicio.',
    date: v.date ? undefined : 'Elige la fecha requerida.',
    workers:
      Number.isInteger(workers) && workers >= 1 && workers <= 50 ? undefined : 'Indica un número entre 1 y 50.',
  };
}

export function requestSummary(v: ExternalRequestValues, requester: string): string {
  return [
    'Solicitud de servicio externo — N Club',
    '(pendiente de aprobación: no es una contratación confirmada)',
    '',
    `Solicita: ${requester}`,
    `Servicio: ${v.serviceType}`,
    `Detalle: ${v.description.trim()}`,
    `Área: ${spaceName(v.area)}`,
    `Fecha requerida: ${v.date ? formatDateLabel(v.date) : '—'}`,
    `Personas: ${v.workers}`,
    v.provider.trim() ? `Proveedor sugerido: ${v.provider.trim()}` : null,
  ]
    .filter((l) => l !== null)
    .join('\n');
}
