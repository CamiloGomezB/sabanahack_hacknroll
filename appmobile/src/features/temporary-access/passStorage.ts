import { secureDelete, secureGet, secureSet, storageKey } from '@/services/storage/secureStore';

import { decodePassCode, encodePassCode, type AccessPass } from './pass';

// Pase que abrió en este teléfono un invitado o externo (sin cuenta).
const GUEST_PASS_KEY = 'nclub_guest_pass';

export async function loadGuestPass(): Promise<AccessPass | null> {
  const code = await secureGet(GUEST_PASS_KEY);
  return code ? decodePassCode(code) : null;
}

export async function saveGuestPass(pass: AccessPass): Promise<void> {
  await secureSet(GUEST_PASS_KEY, encodePassCode(pass));
}

export async function clearGuestPass(): Promise<void> {
  await secureDelete(GUEST_PASS_KEY);
}

// Pases que emitió el anfitrión: el token solo se entrega una vez, así que se guarda en el llavero
// del teléfono del anfitrión para poder volver a mostrarlo o compartirlo.
export async function saveIssuedPass(visitaId: string, pass: AccessPass): Promise<void> {
  await secureSet(storageKey('nclub_issued', visitaId), encodePassCode(pass));
}

export async function loadIssuedPass(visitaId: string): Promise<AccessPass | null> {
  const code = await secureGet(storageKey('nclub_issued', visitaId));
  return code ? decodePassCode(code) : null;
}

export async function deleteIssuedPass(visitaId: string): Promise<void> {
  await secureDelete(storageKey('nclub_issued', visitaId));
}
