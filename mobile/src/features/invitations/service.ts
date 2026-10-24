import AsyncStorage from '@react-native-async-storage/async-storage';

import type { SessionState } from '@/features/auth/SessionProvider';
import { demoQrValue } from '@/features/demo/demoData';
import type { AccessPass, PassCategory } from '@/features/temporary-access/pass';
import { deleteIssuedPass, loadIssuedPass, saveIssuedPass } from '@/features/temporary-access/passStorage';
import { crearInvitacion, fetchVisitasComoResponsable, revocarInvitacion } from '@/services/supabase/visitas';
import type { EstadoVisita } from '@/types/database';

export interface InvitationInput {
  categoria: PassCategory;
  nombre: string;
  email: string;
  destino: string;
  inicio: Date;
  fin: Date;
  empresa: string | null;
  motivo: string | null;
}

export interface InvitationRecord {
  id: string;
  categoria: PassCategory;
  nombre: string;
  email: string | null;
  destino: string;
  empresa: string | null;
  motivo: string | null;
  inicio: string;
  fin: string;
  /** Estado de la visita en la base (programada, en_curso, ...). En demo, simulado. */
  estado: EstadoVisita;
  demo: boolean;
}

export interface InvitationsService {
  readonly demo: boolean;
  list(): Promise<InvitationRecord[]>;
  create(input: InvitationInput): Promise<{ record: InvitationRecord; pass: AccessPass }>;
  revoke(id: string): Promise<void>;
  /** Pase guardado en este teléfono (el token solo se entrega una vez al crearlo). */
  getPass(id: string): Promise<AccessPass | null>;
}

type Active = Extract<SessionState, { status: 'real' | 'pass' | 'demo' }>;

function realService(personaId: string, hostName: string): InvitationsService {
  return {
    demo: false,
    async list() {
      const rows = await fetchVisitasComoResponsable(personaId);
      return rows.map((r) => ({
        id: r.id,
        categoria: r.categoria === 'externo' ? 'externo' : 'invitado',
        nombre: r.persona?.nombre_demo ?? 'Invitado',
        email: r.persona?.email ?? null,
        destino: r.destino ?? '',
        empresa: r.empresa,
        motivo: r.motivo,
        inicio: r.inicio,
        fin: r.fin,
        estado: r.estado,
        demo: false,
      }));
    },
    async create(input) {
      const { visita_id, token } = await crearInvitacion({ ...input });
      const pass: AccessPass = {
        v: 1,
        kind: 'real',
        tipo: input.categoria,
        token,
        nombre: input.nombre.trim(),
        empresa: input.empresa?.trim() || null,
        anfitrion: hostName,
        destino: input.destino,
        motivo: input.motivo?.trim() || null,
        desde: input.inicio.toISOString(),
        hasta: input.fin.toISOString(),
        visitaId: visita_id,
      };
      await saveIssuedPass(visita_id, pass);
      return {
        pass,
        record: {
          id: visita_id,
          categoria: input.categoria,
          nombre: pass.nombre,
          email: input.email.trim().toLowerCase(),
          destino: input.destino,
          empresa: pass.empresa,
          motivo: pass.motivo,
          inicio: pass.desde,
          fin: pass.hasta,
          estado: 'programada',
          demo: false,
        },
      };
    },
    async revoke(id) {
      await revocarInvitacion(id);
      await deleteIssuedPass(id).catch(() => undefined);
    },
    getPass: loadIssuedPass,
  };
}

// --- Demostración: se guarda solo en este teléfono, marcado como demo --------------------

const DEMO_KEY = 'nclub_demo_invitations';
type DemoEntry = { record: InvitationRecord; pass: AccessPass };

async function readDemo(key: string): Promise<DemoEntry[]> {
  try {
    const raw = await AsyncStorage.getItem(key);
    return raw ? (JSON.parse(raw) as DemoEntry[]) : [];
  } catch {
    return [];
  }
}

async function writeDemo(key: string, entries: DemoEntry[]): Promise<void> {
  await AsyncStorage.setItem(key, JSON.stringify(entries));
}

function demoService(hostId: string, hostName: string): InvitationsService {
  const key = `${DEMO_KEY}_${hostId}`;
  return {
    demo: true,
    async list() {
      return (await readDemo(key)).map((e) => e.record);
    },
    async create(input) {
      const id = `demo-${Date.now().toString(36)}`;
      const pass: AccessPass = {
        v: 1,
        kind: 'demo',
        tipo: input.categoria,
        token: demoQrValue(id),
        nombre: input.nombre.trim(),
        empresa: input.empresa?.trim() || null,
        anfitrion: hostName,
        destino: input.destino,
        motivo: input.motivo?.trim() || null,
        desde: input.inicio.toISOString(),
        hasta: input.fin.toISOString(),
        visitaId: null,
      };
      const record: InvitationRecord = {
        id,
        categoria: input.categoria,
        nombre: pass.nombre,
        email: input.email.trim().toLowerCase(),
        destino: input.destino,
        empresa: pass.empresa,
        motivo: pass.motivo,
        inicio: pass.desde,
        fin: pass.hasta,
        estado: 'programada',
        demo: true,
      };
      await writeDemo(key, [{ record, pass }, ...(await readDemo(key))].slice(0, 30));
      return { record, pass };
    },
    async revoke(id) {
      const entries = await readDemo(key);
      await writeDemo(
        key,
        entries.map((e) => (e.record.id === id ? { ...e, record: { ...e.record, estado: 'cancelada' } } : e)),
      );
    },
    async getPass(id) {
      return (await readDemo(key)).find((e) => e.record.id === id)?.pass ?? null;
    },
  };
}

export function invitationsServiceFor(session: Active): InvitationsService | null {
  if (session.status === 'real') return realService(session.persona.id, session.persona.nombre_demo);
  if (session.status === 'demo' && session.persona) return demoService(session.persona.id, session.persona.nombre_demo);
  return null;
}
