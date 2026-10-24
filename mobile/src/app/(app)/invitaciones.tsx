import { router } from 'expo-router';
import { useCallback, useMemo, useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { Badge, GlassCard, Notice } from '@/components/Card';
import { NotAllowed } from '@/components/NotAllowed';
import { PillButton } from '@/components/PillButton';
import { Screen } from '@/components/Screen';
import { EmptyView, ErrorView, LoadingView } from '@/components/StateViews';
import { Txt } from '@/components/Txt';
import { spaceName } from '@/constants/spaces';
import { spacing } from '@/constants/theme';
import { canInviteGuests, canRegisterExternal } from '@/features/auth/permissions';
import { useActiveSession } from '@/features/auth/SessionProvider';
import { invitationsServiceFor, type InvitationRecord } from '@/features/invitations/service';
import { VISIT_STATE } from '@/features/invitations/visitState';
import { useAsync } from '@/hooks/useAsync';
import { friendlyError } from '@/utils/format';
import { formatClubRange } from '@/utils/time';

export default function InvitationsScreen() {
  const { session } = useActiveSession();
  const service = useMemo(() => invitationsServiceFor(session), [session]);
  const staff = session.profile === 'personal';
  const load = useCallback(async () => (service ? service.list() : []), [service]);
  const { state, reload } = useAsync(load, 'No se pudieron cargar las invitaciones.');

  if (!service) {
    return <NotAllowed title="Invitaciones" message="Los invitados y trabajadores externos no gestionan invitaciones." />;
  }

  const canCreate = staff ? canRegisterExternal(session) : canInviteGuests(session);

  return (
    <Screen back title={staff ? 'Accesos registrados' : 'Mis invitaciones'} dense>
      {service.demo ? (
        <Notice tone="demo" icon="flask-outline" title="Datos de demostración" message="Lista guardada solo en este teléfono." />
      ) : (
        <Txt variant="caption" align="center">
          Las visitas terminadas se eliminan automáticamente del sistema (limpieza programada del club).
        </Txt>
      )}
      {canCreate ? (
        <PillButton
          label={staff ? 'Registrar trabajador externo' : 'Nueva invitación'}
          icon="add"
          onPress={() => router.push({ pathname: '/invitar', params: { tipo: staff ? 'externo' : 'invitado' } })}
        />
      ) : null}

      {state.status === 'loading' ? <LoadingView /> : null}
      {state.status === 'error' ? <ErrorView message={state.error} onRetry={() => void reload()} /> : null}
      {state.status === 'success' && state.data.length === 0 ? (
        <EmptyView message={staff ? 'No has registrado accesos externos.' : 'Aún no has invitado a nadie.'} />
      ) : null}
      {state.status === 'success'
        ? state.data.map((inv) => (
            <InvitationItem
              key={inv.id}
              inv={inv}
              onRevoke={async () => {
                await service.revoke(inv.id);
                await reload();
              }}
            />
          ))
        : null}
    </Screen>
  );
}

function InvitationItem({ inv, onRevoke }: { inv: InvitationRecord; onRevoke: () => Promise<void> }) {
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const st = VISIT_STATE[inv.estado];
  const revocable = inv.estado === 'programada' || inv.estado === 'en_curso';

  async function revoke() {
    setBusy(true);
    setError(null);
    try {
      await onRevoke();
    } catch (e) {
      setError(friendlyError(e, 'No se pudo revocar.'));
    } finally {
      setBusy(false);
      setConfirm(false);
    }
  }

  return (
    <GlassCard>
      <View style={styles.header}>
        <View style={styles.flex}>
          <Txt variant="subtitle">{inv.nombre}</Txt>
          {inv.email ? <Txt variant="caption">{inv.email}</Txt> : null}
        </View>
        <View style={styles.badges}>
          <Badge label={inv.categoria === 'externo' ? 'Externo' : 'Invitado'} tone="gold" />
          <Badge label={st.label} tone={st.tone} />
        </View>
      </View>
      {inv.empresa ? <Txt variant="caption">Empresa: {inv.empresa}</Txt> : null}
      <Txt variant="caption">
        {spaceName(inv.destino)} · {formatClubRange(inv.inicio, inv.fin)}
      </Txt>
      {error ? <Txt variant="caption" color="#ff8a80">{error}</Txt> : null}
      <View style={styles.actions}>
        <PillButton
          label="Ver pase"
          variant="outline"
          icon="qr-code-outline"
          style={styles.action}
          onPress={() => router.push({ pathname: '/acceso/[id]', params: { id: inv.id } })}
        />
        {revocable ? (
          confirm ? (
            <PillButton label="Confirmar revocación" variant="danger" style={styles.action} loading={busy} onPress={() => void revoke()} />
          ) : (
            <PillButton label="Revocar" variant="ghost" style={styles.action} onPress={() => setConfirm(true)} />
          )
        ) : null}
      </View>
    </GlassCard>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: 'row', gap: spacing.sm },
  flex: { flex: 1 },
  badges: { gap: 4, alignItems: 'flex-end' },
  actions: { flexDirection: 'row', gap: spacing.sm, marginTop: spacing.xs },
  action: { width: 'auto', flex: 1 },
});
