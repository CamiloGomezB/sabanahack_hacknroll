import type { Session } from '@supabase/supabase-js';
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';

import { vinculoToProfile, type ProfileKind } from '@/constants/profiles';
import { DEMO_PERSONAS, demoPass } from '@/features/demo/demoData';
import type { AccessPass } from '@/features/temporary-access/pass';
import { clearGuestPass, loadGuestPass, saveGuestPass } from '@/features/temporary-access/passStorage';
import { supabase } from '@/services/supabase/client';
import { createMyPersona, fetchMyPersona } from '@/services/supabase/personas';
import type { Persona } from '@/types/database';
import { friendlyError } from '@/utils/format';

/**
 * Tres orígenes de sesión, separados a propósito:
 *  - real: cuenta de Supabase Auth; el perfil sale de personas.vinculo (lo asigna el club, RLS
 *    impide que el usuario lo cambie).
 *  - pass: invitado o externo sin cuenta que abrió el código de pase que le compartieron.
 *  - demo: datos locales de demostración; nunca toca Supabase.
 */
export type SessionState =
  | { status: 'loading' }
  | { status: 'signedOut' }
  | { status: 'noAccess'; message: string }
  | { status: 'real'; userId: string; persona: Persona; profile: 'regular' | 'vip' | 'personal' }
  | { status: 'pass'; profile: 'invitado' | 'externo'; pass: AccessPass }
  | { status: 'demo'; profile: ProfileKind; persona: Persona | null; pass: AccessPass | null };

export interface SignUpInput {
  nombre: string;
  email: string;
  password: string;
  telefono: string;
  consentimientoBiometrico: boolean;
}

interface SessionContextValue {
  session: SessionState;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (input: SignUpInput) => Promise<{ needsEmailConfirmation: boolean }>;
  signOut: () => Promise<void>;
  enterDemo: (profile: ProfileKind) => void;
  openPass: (pass: AccessPass) => Promise<void>;
  refreshPersona: () => Promise<void>;
  setPersona: (persona: Persona) => void;
}

const SessionContext = createContext<SessionContextValue | null>(null);

type MetaData = { nombre?: unknown; telefono?: unknown; consentimiento_biometrico?: unknown };

async function resolveRealSession(session: Session): Promise<SessionState> {
  const user = session.user;
  let persona = await fetchMyPersona(user.id);
  if (!persona) {
    // Primer inicio de sesión tras confirmar el correo: se crea el perfil con los datos del registro.
    const meta = (user.user_metadata ?? {}) as MetaData;
    persona = await createMyPersona({
      userId: user.id,
      nombre: typeof meta.nombre === 'string' && meta.nombre.trim() ? meta.nombre : (user.email ?? 'Miembro').split('@')[0],
      email: user.email ?? '',
      telefono: typeof meta.telefono === 'string' ? meta.telefono : null,
      consentimientoBiometrico: meta.consentimiento_biometrico === true,
    });
  }
  const profile = vinculoToProfile(persona.vinculo);
  if (profile !== 'regular' && profile !== 'vip' && profile !== 'personal') {
    return { status: 'noAccess', message: 'Tu cuenta no tiene un vínculo activo con el club.' };
  }
  return { status: 'real', userId: user.id, persona, profile };
}

/** Sin cuenta: pase guardado en el teléfono o sesión cerrada. Con cuenta: su persona. */
async function resolveSession(authSession: Session | null): Promise<SessionState> {
  if (!authSession) {
    const pass = await loadGuestPass().catch(() => null);
    return pass ? { status: 'pass', profile: pass.tipo, pass } : { status: 'signedOut' };
  }
  try {
    return await resolveRealSession(authSession);
  } catch (e) {
    return { status: 'noAccess', message: friendlyError(e, 'No se pudo cargar tu perfil.') };
  }
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<SessionState>({ status: 'loading' });
  // El modo demo y el pase de invitado no deben ser pisados por eventos de Supabase Auth.
  const localModeRef = useRef(false);

  const applyAuthSession = useCallback((authSession: Session | null) => {
    if (localModeRef.current) return Promise.resolve();
    return resolveSession(authSession).then((next) => {
      // Un pase o la demo pudieron abrirse mientras se resolvía la sesión de Auth.
      if (localModeRef.current) return;
      if (next.status === 'pass') localModeRef.current = true;
      setSession(next);
    });
  }, []);

  useEffect(() => {
    if (!supabase) {
      void applyAuthSession(null);
      return;
    }
    const { data } = supabase.auth.onAuthStateChange((event, authSession) => {
      if (event === 'TOKEN_REFRESHED' || event === 'USER_UPDATED') return;
      // No se llama a Supabase dentro del callback (puede bloquear el cliente): se difiere.
      setTimeout(() => void applyAuthSession(authSession), 0);
    });
    return () => data.subscription.unsubscribe();
  }, [applyAuthSession]);

  const signIn = useCallback(async (email: string, password: string) => {
    if (!supabase) throw new Error('El backend no está configurado.');
    localModeRef.current = false;
    const { error } = await supabase.auth.signInWithPassword({ email: email.trim().toLowerCase(), password });
    if (error) throw error;
  }, []);

  const signUp = useCallback(async (input: SignUpInput) => {
    if (!supabase) throw new Error('El backend no está configurado.');
    localModeRef.current = false;
    const { data, error } = await supabase.auth.signUp({
      email: input.email.trim().toLowerCase(),
      password: input.password,
      options: {
        data: {
          nombre: input.nombre.trim(),
          telefono: input.telefono.trim() || null,
          consentimiento_biometrico: input.consentimientoBiometrico,
        },
      },
    });
    if (error) throw error;
    // Con confirmación de correo activa no hay sesión todavía: el perfil se crea al primer ingreso.
    return { needsEmailConfirmation: !data.session };
  }, []);

  const signOut = useCallback(async () => {
    const wasLocal = localModeRef.current;
    localModeRef.current = false;
    await clearGuestPass().catch(() => undefined);
    if (supabase && !wasLocal) {
      await supabase.auth.signOut().catch(() => undefined);
    }
    setSession({ status: 'signedOut' });
  }, []);

  const enterDemo = useCallback((profile: ProfileKind) => {
    localModeRef.current = true;
    if (profile === 'invitado' || profile === 'externo') {
      setSession({ status: 'demo', profile, persona: null, pass: demoPass(profile) });
    } else {
      setSession({ status: 'demo', profile, persona: DEMO_PERSONAS[profile], pass: null });
    }
  }, []);

  const openPass = useCallback(async (pass: AccessPass) => {
    localModeRef.current = true;
    if (pass.kind === 'demo') {
      setSession({ status: 'demo', profile: pass.tipo, persona: null, pass });
      return;
    }
    await saveGuestPass(pass);
    setSession({ status: 'pass', profile: pass.tipo, pass });
  }, []);

  const refreshPersona = useCallback(async () => {
    if (!supabase) return;
    const { data } = await supabase.auth.getSession();
    await applyAuthSession(data.session);
  }, [applyAuthSession]);

  const setPersona = useCallback((persona: Persona) => {
    setSession((s) => (s.status === 'real' ? { ...s, persona } : s));
  }, []);

  const value = useMemo(
    () => ({ session, signIn, signUp, signOut, enterDemo, openPass, refreshPersona, setPersona }),
    [session, signIn, signUp, signOut, enterDemo, openPass, refreshPersona, setPersona],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionContextValue {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error('useSession debe usarse dentro de SessionProvider');
  return ctx;
}

export function isSignedIn(s: SessionState): s is Extract<SessionState, { status: 'real' | 'pass' | 'demo' }> {
  return s.status === 'real' || s.status === 'pass' || s.status === 'demo';
}

/** Sesión con persona (real o demo) de alguno de los perfiles indicados. */
export function hasProfile<P extends ProfileKind>(
  s: SessionState,
  profiles: readonly P[],
): s is Extract<SessionState, { status: 'real' | 'demo' }> & { profile: P } {
  return (s.status === 'real' || s.status === 'demo') && (profiles as readonly ProfileKind[]).includes(s.profile);
}

/** Sesión activa (para pantallas dentro del grupo autenticado). */
export function useActiveSession() {
  const ctx = useSession();
  if (!isSignedIn(ctx.session)) throw new Error('Pantalla protegida usada sin sesión');
  return { ...ctx, session: ctx.session };
}
