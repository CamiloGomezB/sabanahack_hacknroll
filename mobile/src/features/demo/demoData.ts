/**
 * DATOS DE DEMOSTRACIÓN. Nada de este archivo existe en Supabase ni autoriza el ingreso.
 * Permiten recorrer los cinco perfiles sin crear cuentas reales.
 */
import type { ProfileKind } from '@/constants/profiles';
import type { AccessPass } from '@/features/temporary-access/pass';
import type { Persona } from '@/types/database';

export const DEMO_QR_PREFIX = 'NCLUB-DEMO-NO-AUTORIZA-INGRESO';

export function demoQrValue(label: string): string {
  return `${DEMO_QR_PREFIX}:${label}`;
}

function demoPersona(id: string, nombre: string, vinculo: Persona['vinculo'], extra: Partial<Persona> = {}): Persona {
  return {
    id,
    usuario_id: null,
    nombre_demo: nombre,
    email: null,
    telefono: null,
    vinculo,
    rol: 'usuario',
    estado: 'activa',
    requiere_tour: vinculo === 'regular',
    horario_inicio: '06:00:00',
    horario_fin: '21:00:00',
    vinculo_hasta: null,
    consentimiento_biometrico: false,
    consentimiento_fecha: null,
    ...extra,
  };
}

export const DEMO_PERSONAS: Record<'regular' | 'vip' | 'personal', Persona> = {
  regular: demoPersona('0020d3m0-0000-4000-8000-000000000001', 'Laura Gómez (demo)', 'regular'),
  vip: demoPersona('07a1d3m0-0000-4000-8000-000000000002', 'Andrés Ríos (demo)', 'vip'),
  personal: demoPersona('0c51d3m0-0000-4000-8000-000000000003', 'Camila Torres (demo)', 'personal', {
    horario_inicio: '07:00:00',
    horario_fin: '15:00:00',
  }),
};

/** Pase de demostración con una ventana relativa a "ahora" para ver los tres estados. */
export function demoPass(tipo: 'invitado' | 'externo', shift: 'pendiente' | 'vigente' | 'vencido' = 'vigente'): AccessPass {
  const now = Date.now();
  const hour = 3600 * 1000;
  const windows = {
    pendiente: [now + 2 * hour, now + 6 * hour],
    vigente: [now - hour, now + 4 * hour],
    vencido: [now - 6 * hour, now - 2 * hour],
  } as const;
  const [desde, hasta] = windows[shift];
  return {
    v: 1,
    kind: 'demo',
    tipo,
    token: demoQrValue(tipo),
    nombre: tipo === 'invitado' ? 'Mariana Duarte (demo)' : 'Jorge Pérez (demo)',
    empresa: tipo === 'externo' ? 'Servicios Técnicos Demo S.A.S.' : null,
    anfitrion: tipo === 'invitado' ? DEMO_PERSONAS.regular.nombre_demo : DEMO_PERSONAS.personal.nombre_demo,
    destino: tipo === 'invitado' ? 'terraza' : 'zona-servicio',
    motivo: tipo === 'externo' ? 'Mantenimiento de aire acondicionado' : null,
    desde: new Date(desde).toISOString(),
    hasta: new Date(hasta).toISOString(),
    visitaId: null,
  };
}

/** SIMULADO: no existe tabla de tareas del personal (ver supabase/proposed). */
export interface StaffTask {
  id: string;
  title: string;
  area: string;
  time: string;
}

export const DEMO_STAFF_TASKS: StaffTask[] = [
  { id: 't1', title: 'Revisar montaje del salón social', area: 'Salón social', time: '07:30' },
  { id: 't2', title: 'Recibir proveedor de mantenimiento', area: 'Zona de servicio', time: '09:00' },
  { id: 't3', title: 'Confirmar reservas de la terraza', area: 'Terraza', time: '11:00' },
  { id: 't4', title: 'Inventario de la sala de lectura', area: 'Sala de lectura', time: '13:00' },
  { id: 't5', title: 'Entrega de turno', area: 'Recepción', time: '14:30' },
];

export const DEMO_PROFILE_OPTIONS: { profile: ProfileKind; title: string; subtitle: string }[] = [
  { profile: 'regular', title: 'Miembro regular', subtitle: 'QR personal, invitaciones y reservas básicas' },
  { profile: 'vip', title: 'Miembro VIP', subtitle: 'Más espacios, invitaciones y reservas' },
  { profile: 'personal', title: 'Personal del club', subtitle: 'Tareas, turno y equipo externo' },
  { profile: 'invitado', title: 'Invitado', subtitle: 'Pase temporal de un miembro' },
  { profile: 'externo', title: 'Trabajador externo', subtitle: 'Acceso temporal de servicio' },
];
