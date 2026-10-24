import * as Crypto from 'expo-crypto';
import { useCallback, useEffect, useState } from 'react';

import type { SessionState } from '@/features/auth/SessionProvider';
import { demoQrValue } from '@/features/demo/demoData';
import { fetchActivePersonalCredential, generateMyQrToken } from '@/services/supabase/credentials';
import { secureGet, secureSet, storageKey } from '@/services/storage/secureStore';
import { friendlyError } from '@/utils/format';

/**
 *  - real: hay un token local cuyo sha256 coincide con una credencial qr_personal vigente.
 *  - demo: QR de demostración, no autoriza el ingreso.
 *  - missing: no hay token utilizable en este teléfono (se puede generar uno nuevo).
 *  - unavailable: la membresía no permite QR.
 */
export type MemberQrState =
  | { status: 'loading' }
  | { status: 'real'; token: string; validUntil: string | null }
  | { status: 'demo'; value: string }
  | { status: 'missing'; reason: string }
  | { status: 'unavailable'; reason: string }
  | { status: 'error'; message: string };

type Active = Extract<SessionState, { status: 'real' | 'pass' | 'demo' }>;

const tokenKey = (personaId: string) => storageKey('nclub_qr', personaId);

async function sha256Hex(text: string): Promise<string> {
  return Crypto.digestStringAsync(Crypto.CryptoDigestAlgorithm.SHA256, text, {
    encoding: Crypto.CryptoEncoding.HEX,
  });
}

async function resolveRealQr(personaId: string): Promise<MemberQrState> {
  try {
    const [credential, token] = await Promise.all([
      fetchActivePersonalCredential(personaId),
      secureGet(tokenKey(personaId)),
    ]);
    if (!credential) return { status: 'missing', reason: 'Aún no tienes un QR personal activo.' };
    if (credential.valido_hasta && new Date(credential.valido_hasta).getTime() < Date.now()) {
      return { status: 'missing', reason: 'Tu QR personal venció.' };
    }
    if (!token || (await sha256Hex(token)) !== credential.token_hash) {
      return {
        status: 'missing',
        reason: 'Tu QR activo se generó en otro dispositivo o ya no está en este teléfono.',
      };
    }
    return { status: 'real', token, validUntil: credential.valido_hasta };
  } catch (e) {
    return { status: 'error', message: friendlyError(e, 'No se pudo cargar tu QR.') };
  }
}

export function useMemberQr(session: Active, membershipActive: boolean) {
  const personaId = session.status === 'real' ? session.persona.id : null;
  const demoProfile = session.status === 'demo' ? session.profile : null;
  const [nonce, setNonce] = useState(0);
  const [result, setResult] = useState<{ key: string; state: MemberQrState } | null>(null);
  const [generating, setGenerating] = useState(false);
  const key = `${personaId ?? ''}|${nonce}`;

  useEffect(() => {
    if (demoProfile || !personaId || !membershipActive) return;
    let alive = true;
    void resolveRealQr(personaId).then((state) => alive && setResult({ key, state }));
    return () => {
      alive = false;
    };
  }, [key, personaId, demoProfile, membershipActive]);

  /** Llama a generar_mi_qr(): revoca el QR anterior y guarda el nuevo token en el llavero. */
  const generate = useCallback(async () => {
    if (!personaId) return;
    setGenerating(true);
    try {
      const token = await generateMyQrToken();
      await secureSet(tokenKey(personaId), token);
      setNonce((n) => n + 1);
    } catch (e) {
      setResult({ key, state: { status: 'error', message: friendlyError(e, 'No se pudo generar el QR.') } });
    } finally {
      setGenerating(false);
    }
  }, [personaId, key]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  let state: MemberQrState;
  if (demoProfile) state = { status: 'demo', value: demoQrValue(demoProfile) };
  else if (!membershipActive) {
    state = { status: 'unavailable', reason: 'Tu membresía no está activa: el QR personal no está disponible.' };
  } else if (!result || result.key !== key) state = { status: 'loading' };
  else state = result.state;

  return { state, generate, generating, reload };
}
