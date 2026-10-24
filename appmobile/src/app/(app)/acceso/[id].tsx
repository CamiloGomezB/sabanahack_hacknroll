import { useLocalSearchParams } from 'expo-router';
import { useCallback, useMemo } from 'react';

import { Notice } from '@/components/Card';
import { NotAllowed } from '@/components/NotAllowed';
import { Screen } from '@/components/Screen';
import { ErrorView, LoadingView } from '@/components/StateViews';
import { useActiveSession } from '@/features/auth/SessionProvider';
import { invitationsServiceFor } from '@/features/invitations/service';
import { AccessPassView } from '@/features/temporary-access/AccessPassView';
import { useAsync } from '@/hooks/useAsync';

/** Pase emitido por el anfitrión, para volver a mostrarlo o compartirlo. */
export default function IssuedPassScreen() {
  const { session } = useActiveSession();
  const { id } = useLocalSearchParams<{ id: string }>();
  const service = useMemo(() => invitationsServiceFor(session), [session]);
  const load = useCallback(async () => (service && id ? service.getPass(id) : null), [service, id]);
  const { state, reload } = useAsync(load, 'No se pudo leer el pase.');

  if (!service) return <NotAllowed title="Pase" message="Tu perfil no emite pases." />;

  return (
    <Screen back title="Pase emitido" dense>
      {state.status === 'loading' ? <LoadingView /> : null}
      {state.status === 'error' ? <ErrorView message={state.error} onRetry={() => void reload()} /> : null}
      {state.status === 'success' && !state.data ? (
        <Notice
          tone="warning"
          icon="key-outline"
          title="El código de este pase no está en este teléfono"
          message="La base de datos solo guarda el hash del token y lo entrega una única vez, al crear la invitación. Si necesitas volver a enviarlo, revoca esta invitación y crea una nueva."
        />
      ) : null}
      {state.status === 'success' && state.data ? <AccessPassView pass={state.data} audience="host" /> : null}
    </Screen>
  );
}
