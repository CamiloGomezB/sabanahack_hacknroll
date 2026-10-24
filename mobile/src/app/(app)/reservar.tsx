import { NotAllowed } from '@/components/NotAllowed';
import { canReserve } from '@/features/auth/permissions';
import { hasProfile, useActiveSession } from '@/features/auth/SessionProvider';
import { ReservationScreen } from '@/features/reservations/ReservationScreen';

export default function ReserveRoute() {
  const { session } = useActiveSession();
  if (!hasProfile(session, ['regular', 'vip']) || !canReserve(session)) {
    return (
      <NotAllowed
        title="Reservar espacio"
        message="Las reservas son para miembros regulares y VIP con membresía activa."
      />
    );
  }
  return <ReservationScreen session={session} />;
}
