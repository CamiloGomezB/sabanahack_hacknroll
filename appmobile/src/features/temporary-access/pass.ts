/**
 * Pase de acceso temporal (invitado o trabajador externo).
 *
 * Los invitados y externos no tienen cuenta (personas.usuario_id es null) y RLS no les deja leer
 * nada. Por eso el anfitrión les comparte un "código de pase" que contiene el token del QR y los
 * datos de la visita que el anfitrión ya conoce. El QR solo codifica el token; la validez final la
 * decide registrar_llegada() en el servidor al escanearlo.
 */

export type PassKind = 'real' | 'demo';
export type PassCategory = 'invitado' | 'externo';
export type PassStatus = 'pendiente' | 'vigente' | 'vencido';

export interface AccessPass {
  v: 1;
  kind: PassKind;
  tipo: PassCategory;
  token: string;
  nombre: string;
  empresa: string | null;
  anfitrion: string;
  destino: string;
  motivo: string | null;
  /** ISO 8601 (UTC) */
  desde: string;
  hasta: string;
  visitaId: string | null;
}

const PREFIX = 'NC1.';

export function passStatus(pass: Pick<AccessPass, 'desde' | 'hasta'>, now: Date = new Date()): PassStatus {
  const t = now.getTime();
  if (t < new Date(pass.desde).getTime()) return 'pendiente';
  if (t > new Date(pass.hasta).getTime()) return 'vencido';
  return 'vigente';
}

export const PASS_STATUS_LABEL: Record<PassStatus, string> = {
  pendiente: 'Pendiente de activación',
  vigente: 'Acceso vigente',
  vencido: 'Acceso vencido',
};

// --- Codificación del código compartible (UTF-8 + base64url) -------------------------------

function utf8Encode(text: string): string {
  let out = '';
  for (const ch of text) {
    const cp = ch.codePointAt(0) ?? 0;
    if (cp < 0x80) out += String.fromCharCode(cp);
    else if (cp < 0x800) out += String.fromCharCode(0xc0 | (cp >> 6), 0x80 | (cp & 63));
    else if (cp < 0x10000)
      out += String.fromCharCode(0xe0 | (cp >> 12), 0x80 | ((cp >> 6) & 63), 0x80 | (cp & 63));
    else
      out += String.fromCharCode(
        0xf0 | (cp >> 18),
        0x80 | ((cp >> 12) & 63),
        0x80 | ((cp >> 6) & 63),
        0x80 | (cp & 63),
      );
  }
  return out;
}

function utf8Decode(bytes: string): string {
  let out = '';
  for (let i = 0; i < bytes.length; ) {
    const b = bytes.charCodeAt(i);
    let cp: number;
    if (b < 0x80) {
      cp = b;
      i += 1;
    } else if (b < 0xe0) {
      cp = ((b & 31) << 6) | (bytes.charCodeAt(i + 1) & 63);
      i += 2;
    } else if (b < 0xf0) {
      cp = ((b & 15) << 12) | ((bytes.charCodeAt(i + 1) & 63) << 6) | (bytes.charCodeAt(i + 2) & 63);
      i += 3;
    } else {
      cp =
        ((b & 7) << 18) |
        ((bytes.charCodeAt(i + 1) & 63) << 12) |
        ((bytes.charCodeAt(i + 2) & 63) << 6) |
        (bytes.charCodeAt(i + 3) & 63);
      i += 4;
    }
    out += String.fromCodePoint(cp);
  }
  return out;
}

export function encodePassCode(pass: AccessPass): string {
  const b64 = btoa(utf8Encode(JSON.stringify(pass)));
  return PREFIX + b64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function isIsoDate(v: unknown): v is string {
  return typeof v === 'string' && !Number.isNaN(new Date(v).getTime());
}

/** Devuelve null si el código no es un pase válido de N Club. */
export function decodePassCode(code: string): AccessPass | null {
  const trimmed = code.trim();
  const start = trimmed.indexOf(PREFIX);
  if (start < 0) return null;
  const body = trimmed.slice(start + PREFIX.length).split(/\s/)[0] ?? '';
  try {
    const b64 = body.replace(/-/g, '+').replace(/_/g, '/');
    const json = JSON.parse(utf8Decode(atob(b64 + '='.repeat((4 - (b64.length % 4)) % 4)))) as Record<
      string,
      unknown
    >;
    if (
      json.v !== 1 ||
      (json.kind !== 'real' && json.kind !== 'demo') ||
      (json.tipo !== 'invitado' && json.tipo !== 'externo') ||
      typeof json.token !== 'string' ||
      typeof json.nombre !== 'string' ||
      typeof json.anfitrion !== 'string' ||
      typeof json.destino !== 'string' ||
      !isIsoDate(json.desde) ||
      !isIsoDate(json.hasta)
    ) {
      return null;
    }
    // Un pase real siempre trae el token hexadecimal de 64 caracteres que genera nuevo_token().
    if (json.kind === 'real' && !/^[0-9a-f]{64}$/.test(json.token)) return null;
    if (json.tipo === 'externo' && typeof json.empresa !== 'string') return null;
    return {
      v: 1,
      kind: json.kind,
      tipo: json.tipo,
      token: json.token,
      nombre: json.nombre,
      empresa: typeof json.empresa === 'string' ? json.empresa : null,
      anfitrion: json.anfitrion,
      destino: json.destino,
      motivo: typeof json.motivo === 'string' ? json.motivo : null,
      desde: json.desde,
      hasta: json.hasta,
      visitaId: typeof json.visitaId === 'string' ? json.visitaId : null,
    };
  } catch {
    return null;
  }
}
