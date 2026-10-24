import { useCallback, useEffect, useState } from 'react';

import { friendlyError } from '@/utils/format';

export type AsyncState<T> =
  | { status: 'loading'; data?: undefined; error?: undefined }
  | { status: 'success'; data: T; error?: undefined }
  | { status: 'error'; data?: undefined; error: string };

type Settled<T> = { fn: () => Promise<T>; nonce: number; state: AsyncState<T> };

/**
 * Ejecuta `fn` (memorizada con useCallback) y expone carga, error y recarga. El estado de carga se
 * deriva: mientras el resultado guardado no corresponda a la `fn` y la recarga actuales, se carga.
 */
export function useAsync<T>(fn: () => Promise<T>, errorMessage?: string) {
  const [nonce, setNonce] = useState(0);
  const [settled, setSettled] = useState<Settled<T> | null>(null);

  useEffect(() => {
    let alive = true;
    fn().then(
      (data) => alive && setSettled({ fn, nonce, state: { status: 'success', data } }),
      (e: unknown) => alive && setSettled({ fn, nonce, state: { status: 'error', error: friendlyError(e, errorMessage) } }),
    );
    return () => {
      alive = false;
    };
  }, [fn, nonce, errorMessage]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);
  const state: AsyncState<T> =
    settled && settled.fn === fn && settled.nonce === nonce ? settled.state : { status: 'loading' };

  return { state, reload };
}
