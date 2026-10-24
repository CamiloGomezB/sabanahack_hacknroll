import { hasProfile, useActiveSession } from '@/features/auth/SessionProvider';
import { MemberHome } from '@/features/memberships/MemberHome';
import { StaffHome } from '@/features/staff/StaffHome';
import { GuestHome } from '@/features/temporary-access/GuestHome';

/** Redirige al panel del perfil autenticado. */
export default function HomeScreen() {
  const { session } = useActiveSession();

  if (session.status === 'pass') return <GuestHome pass={session.pass} />;
  if (hasProfile(session, ['regular', 'vip'])) return <MemberHome session={session} />;
  if (hasProfile(session, ['personal'])) return <StaffHome session={session} />;
  if (session.status === 'demo' && session.pass) return <GuestHome pass={session.pass} />;
  return null;
}
