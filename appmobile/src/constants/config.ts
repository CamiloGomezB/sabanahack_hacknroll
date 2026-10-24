const url = process.env.EXPO_PUBLIC_SUPABASE_URL ?? '';
// Solo clave pública (publishable / anon). Nunca service_role.
const key =
  process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY ?? process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY ?? '';

export const config = {
  supabaseUrl: url,
  supabaseKey: key,
  supabaseConfigured: url.startsWith('http') && key.length > 0 && !url.includes('TU-PROYECTO'),
  /** Zona horaria del club. Colombia no tiene horario de verano: UTC-5 fijo. */
  clubTimeZone: 'America/Bogota',
  clubUtcOffsetHours: -5,
} as const;
