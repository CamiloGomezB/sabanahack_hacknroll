// Tipos escritos a mano a partir de las migraciones 20261023000003 a 20261023000005.
// Las tablas miembros / accesos_temporales del esquema inicial ya no existen.

export type VinculoClub = 'ninguno' | 'regular' | 'vip' | 'personal';
export type RolApp = 'usuario' | 'operador' | 'admin';
export type EstadoPersona = 'activa' | 'suspendida';
export type CategoriaVisita = 'regular' | 'vip' | 'personal' | 'invitado' | 'externo';
export type EstadoVisita = 'programada' | 'en_curso' | 'finalizada' | 'cancelada';
export type TipoCredencial = 'qr_personal' | 'qr_visita';

export interface Persona {
  id: string;
  usuario_id: string | null;
  nombre_demo: string;
  email: string | null;
  telefono: string | null;
  vinculo: VinculoClub;
  rol: RolApp;
  estado: EstadoPersona;
  requiere_tour: boolean;
  /** time sin zona, hora local de Colombia, p. ej. "06:00:00" */
  horario_inicio: string | null;
  horario_fin: string | null;
  /** date (YYYY-MM-DD); null = sin vencimiento */
  vinculo_hasta: string | null;
  consentimiento_biometrico: boolean;
  consentimiento_fecha: string | null;
  /** Cómo prefiere que le hable el robot (solo el tono). Migración 20261024000007. */
  trato: string | null;
}

export interface Visita {
  id: string;
  persona_id: string;
  responsable_id: string | null;
  categoria: CategoriaVisita;
  motivo: string | null;
  empresa: string | null;
  destino: string | null;
  inicio: string;
  fin: string;
  estado: EstadoVisita;
}

export interface Credencial {
  id: string;
  persona_id: string;
  visita_id: string | null;
  tipo: TipoCredencial;
  token_hash: string;
  valido_desde: string;
  valido_hasta: string | null;
  revocada_en: string | null;
}

/** Estado de la huella de una foto de registro (migración 20261024000009). */
export type EstadoHuella = 'pendiente' | 'lista' | 'sin_cara';

/** Foto de registro de la persona. La huella la calcula el backend, nunca la app. */
export interface Fotografia {
  id: string;
  ruta: string;
  tomada_en: string;
  huella_estado: EstadoHuella;
  huella_detalle: string | null;
}

export const FOTO_COLUMNS = 'id,ruta,tomada_en,huella_estado,huella_detalle';

/** Respuesta de public.crear_invitacion */
export interface CrearInvitacionResult {
  visita_id: string;
  token: string;
}

/** Columnas de personas que se piden al servidor. */
export const PERSONA_COLUMNS =
  'id,usuario_id,nombre_demo,email,telefono,vinculo,rol,estado,requiere_tour,horario_inicio,horario_fin,vinculo_hasta,consentimiento_biometrico,consentimiento_fecha,trato';
