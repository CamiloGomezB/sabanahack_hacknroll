import { NotAllowed } from '@/components/NotAllowed';
import { canRegisterExternal } from '@/features/auth/permissions';
import { useActiveSession } from '@/features/auth/SessionProvider';
import { ExternalServiceScreen } from '@/features/staff/ExternalServiceScreen';

export default function ExternalRoute() {
  const { session } = useActiveSession();
  if (session.status === 'pass' || !session.persona || !canRegisterExternal(session)) {
    return <NotAllowed title="Equipo externo" message="Solo el personal activo del club gestiona trabajadores externos." />;
  }
  return <ExternalServiceScreen requester={session.persona.nombre_demo} />;
}
