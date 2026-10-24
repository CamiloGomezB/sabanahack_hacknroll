import type { VinculoClub } from '@/types/database';

import { requireSupabase } from './client';

export interface EspacioRow {
  clave: string;
  nombre: string;
  descripcion: string | null;
  capacidad: number | null;
  reservable_por: VinculoClub[];
}

export interface ReglaReserva {
  max_dias_anticipacion: number;
  max_horas_por_reserva: number;
}

export interface ReservaRow {
  id: string;
  espacio: string;
  inicio: string;
  fin: string;
  creado_en: string;
}

/** Catálogo `espacios` (RLS "catálogo visible": solo los activos). */
export async function fetchEspacios(): Promise<EspacioRow[]> {
  const { data, error } = await requireSupabase()
    .from('espacios')
    .select('clave,nombre,descripcion,capacidad,reservable_por')
    .eq('activo', true)
    .order('nombre');
  if (error) throw error;
  return (data ?? []) as EspacioRow[];
}

/** Reglas de reserva del vínculo (`reglas_reserva`). Null si el vínculo no puede reservar. */
export async function fetchReglaReserva(vinculo: VinculoClub): Promise<ReglaReserva | null> {
  const { data, error } = await requireSupabase()
    .from('reglas_reserva')
    .select('max_dias_anticipacion,max_horas_por_reserva')
    .eq('vinculo', vinculo)
    .maybeSingle();
  if (error) throw error;
  return (data as ReglaReserva | null) ?? null;
}

/** public.disponibilidad_espacio: franjas de 1 h dentro del horario de la persona. */
export async function disponibilidadEspacio(
  espacio: string,
  fecha: string,
): Promise<{ inicio: string; disponible: boolean }[]> {
  const { data, error } = await requireSupabase().rpc('disponibilidad_espacio', {
    p_espacio: espacio,
    p_fecha: fecha,
  });
  if (error) throw error;
  return (data ?? []) as { inicio: string; disponible: boolean }[];
}

/** public.reservar_espacio: valida plan, horario, anticipación y cruce de franjas en la base. */
export async function reservarEspacio(espacio: string, inicio: Date, horas: number): Promise<string> {
  const { data, error } = await requireSupabase().rpc('reservar_espacio', {
    p_espacio: espacio,
    p_inicio: inicio.toISOString(),
    p_horas: horas,
  });
  if (error) throw error;
  return data as string;
}

/** Mis reservas confirmadas que aún no terminan (RLS "ve sus reservas"). */
export async function fetchMisReservas(personaId: string): Promise<ReservaRow[]> {
  const { data, error } = await requireSupabase()
    .from('reservas')
    .select('id,espacio,inicio,fin,creado_en')
    .eq('persona_id', personaId)
    .eq('estado', 'confirmada')
    .gt('fin', new Date().toISOString())
    .order('inicio');
  if (error) throw error;
  return (data ?? []) as ReservaRow[];
}

export async function cancelarReserva(id: string): Promise<void> {
  const { error } = await requireSupabase().rpc('cancelar_reserva', { p_reserva: id });
  if (error) throw error;
}
