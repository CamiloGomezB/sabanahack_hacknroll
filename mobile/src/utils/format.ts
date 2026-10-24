import { PROFILE_CODE_PREFIX, type ProfileKind } from '@/constants/profiles';

/**
 * Identificador visible del miembro. La base solo tiene un UUID, así que el código se deriva de él
 * (prefijo del perfil + 4 caracteres): sirve para mostrar y atender, no como credencial.
 */
export function memberCode(profile: ProfileKind, personaId: string): string {
  const tail = personaId.replace(/-/g, '').slice(0, 4).toUpperCase();
  return `${PROFILE_CODE_PREFIX[profile]}-${tail}`;
}

export function firstName(fullName: string): string {
  return fullName.trim().split(/\s+/)[0] ?? fullName;
}

export function initials(fullName: string): string {
  const parts = fullName.trim().split(/\s+/).filter(Boolean);
  return parts
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() ?? '')
    .join('');
}

/** Mensaje legible sin exponer tokens ni detalles internos. */
export function friendlyError(error: unknown, fallback = 'Ocurrió un error. Inténtalo de nuevo.'): string {
  if (error && typeof error === 'object' && 'message' in error) {
    const msg = String((error as { message: unknown }).message);
    if (/network request failed|failed to fetch|fetch failed/i.test(msg)) {
      return 'No hay conexión con el servidor. Revisa tu internet.';
    }
    if (/invalid login credentials/i.test(msg)) return 'Correo o contraseña incorrectos.';
    if (/email not confirmed/i.test(msg)) return 'Debes confirmar tu correo antes de iniciar sesión.';
    if (/user already registered/i.test(msg)) return 'Ya existe una cuenta con ese correo.';
    if (/solo los miembros|necesitas una cuenta|no puedes revocar|solo el personal|no está configurado/i.test(msg)) {
      return msg;
    }
    if (/permission denied|row-level security/i.test(msg)) return 'No tienes permiso para realizar esta acción.';
  }
  return fallback;
}
