import { router, useLocalSearchParams } from 'expo-router';
import { useMemo, useState } from 'react';

import { Notice } from '@/components/Card';
import { Logo } from '@/components/Logo';
import { NotAllowed } from '@/components/NotAllowed';
import { PillButton } from '@/components/PillButton';
import { Screen } from '@/components/Screen';
import { canInviteGuests, canRegisterExternal } from '@/features/auth/permissions';
import { useActiveSession } from '@/features/auth/SessionProvider';
import { InvitationForm } from '@/features/invitations/InvitationForm';
import { invitationsServiceFor, type InvitationInput } from '@/features/invitations/service';
import { AccessPassView } from '@/features/temporary-access/AccessPassView';
import type { AccessPass } from '@/features/temporary-access/pass';
import { friendlyError } from '@/utils/format';

export default function InviteScreen() {
  const { session } = useActiveSession();
  const params = useLocalSearchParams<{ tipo?: string }>();
  const categoria = params.tipo === 'externo' ? 'externo' : 'invitado';
  const service = useMemo(() => invitationsServiceFor(session), [session]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<AccessPass | null>(null);

  const allowed = categoria === 'externo' ? canRegisterExternal(session) : canInviteGuests(session);
  const title = categoria === 'externo' ? 'Acceso de trabajador externo' : 'Invitar a alguien';

  if (!allowed || !service) {
    return (
      <NotAllowed
        title={title}
        message={
          categoria === 'externo'
            ? 'Solo el personal activo del club u operadores registran trabajadores externos.'
            : 'Solo los miembros con membresía activa pueden invitar. Los invitados no pueden crear otras invitaciones.'
        }
      />
    );
  }

  async function submit(input: InvitationInput) {
    if (!service) return;
    setSubmitting(true);
    setError(null);
    try {
      const { pass } = await service.create(input);
      setCreated(pass);
    } catch (e) {
      setError(friendlyError(e, 'No se pudo registrar la invitación.'));
    } finally {
      setSubmitting(false);
    }
  }

  if (created) {
    return (
      <Screen back title={categoria === 'externo' ? 'Acceso registrado' : 'Invitación creada'}>
        <Notice
          tone={created.kind === 'demo' ? 'demo' : 'success'}
          icon={created.kind === 'demo' ? 'flask-outline' : 'checkmark-circle-outline'}
          title={created.kind === 'demo' ? 'Invitación de demostración creada' : 'Invitación registrada en N Club'}
          message={
            created.kind === 'demo'
              ? 'Se guardó solo en este teléfono. No existe en Supabase.'
              : 'La visita y su credencial QR quedaron registradas. Comparte el pase con la persona invitada.'
          }
        />
        <AccessPassView pass={created} audience="host" />
        <PillButton label="Volver al inicio" variant="outline" onPress={() => router.replace('/home')} />
      </Screen>
    );
  }

  return (
    <Screen back title={title} dense>
      <Logo size={80} />
      {service.demo ? (
        <Notice tone="demo" icon="flask-outline" title="Modo demostración" message="La invitación no se enviará a Supabase." />
      ) : null}
      <InvitationForm
        categoria={categoria}
        profile={session.profile}
        submitting={submitting}
        submitError={error}
        onSubmit={(input) => void submit(input)}
      />
    </Screen>
  );
}
