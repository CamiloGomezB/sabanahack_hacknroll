const ALFABETO = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
const VALOR = new Map([...ALFABETO].map((c, i) => [c, i]));

/**
 * Base64 → bytes. Supabase Storage en React Native sube un ArrayBuffer sin problemas (un Blob
 * a veces llega vacío), y la cámara entrega la foto en base64.
 */
export function base64ToBytes(base64: string): Uint8Array {
  const limpio = base64.replace(/[^A-Za-z0-9+/]/g, '');
  const bytes = new Uint8Array(Math.floor((limpio.length * 3) / 4));
  let n = 0;
  for (let i = 0; i < limpio.length; i += 4) {
    const a = VALOR.get(limpio[i]) ?? 0;
    const b = VALOR.get(limpio[i + 1]) ?? 0;
    const c = VALOR.get(limpio[i + 2]);
    const d = VALOR.get(limpio[i + 3]);
    bytes[n++] = (a << 2) | (b >> 4);
    if (c !== undefined) bytes[n++] = ((b & 15) << 4) | (c >> 2);
    if (c !== undefined && d !== undefined) bytes[n++] = ((c & 3) << 6) | d;
  }
  return bytes.subarray(0, n);
}
