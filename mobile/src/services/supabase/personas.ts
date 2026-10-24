import { PERSONA_COLUMNS, type Persona } from '@/types/database';

import { requireSupabase } from './client';

export async function fetchMyPersona(userId: string): Promise<Persona | null> {
  const { data, error } = await requireSupabase()
    .from('personas')
    .select(PERSONA_COLUMNS)
    .eq('usuario_id', userId)
    .maybeSingle();
  if (error) throw error;
  return (data as Persona | null) ?? null;
}

export interface NewPersonaInput {
  userId: string;
  nombre: string;
  email: string;
  telefono?: string | null;
  consentimientoBiometrico: boolean;
}

/**
 * Crea el perfil del usuario recién registrado. Solo se envían las columnas que la migración
 * permite insertar a `authenticated`; el vínculo queda en 'regular' por defecto y VIP / personal
 * solo los asigna el club.
 */
export async function createMyPersona(input: NewPersonaInput): Promise<Persona> {
  const { data, error } = await requireSupabase()
    .from('personas')
    .insert({
      usuario_id: input.userId,
      nombre_demo: input.nombre.trim(),
      email: input.email.trim().toLowerCase(),
      telefono: input.telefono?.trim() || null,
      consentimiento_biometrico: input.consentimientoBiometrico,
      consentimiento_fecha: input.consentimientoBiometrico ? new Date().toISOString() : null,
    })
    .select(PERSONA_COLUMNS)
    .single();
  if (error) throw error;
  return data as Persona;
}

/** Retirar el consentimiento dispara personas_retirar_huellas, que borra las huellas faciales. */
export async function updateMyConsent(userId: string, consent: boolean): Promise<Persona> {
  const { data, error } = await requireSupabase()
    .from('personas')
    .update({
      consentimiento_biometrico: consent,
      consentimiento_fecha: consent ? new Date().toISOString() : null,
    })
    .eq('usuario_id', userId)
    .select(PERSONA_COLUMNS)
    .single();
  if (error) throw error;
  return data as Persona;
}
